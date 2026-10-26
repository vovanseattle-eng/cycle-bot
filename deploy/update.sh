#!/usr/bin/env bash
# Обновление cycle-bot на сервере: бэкап базы → новые файлы → перезапуск PM2 → проверка.
#
#   bash deploy/update.sh
#
# Безопасность данных:
#   - база НИКОГДА не перезаписывается, только копируется в backups/ до правок;
#   - .env не перезаписывается;
#   - правка кода не меняет схему БД (нет ни ALTER, ни DROP, ни миграций),
#     поэтому старые записи остаются как есть.

set -uo pipefail

REPO_RAW="https://raw.githubusercontent.com/vovanseattle-eng/cycle-bot/main"
FILES="app/db.py app/notify.py app/handlers.py app/keyboards.py app/texts.py"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[ОШБОКА]\033[0m %s\n' "$*" >&2; exit 1; }

# --- ищем каталог проекта -------------------------------------------------
# Если APP_DIR задан снаружи — уважаем его, иначе ищем сами.
APP_DIR="${APP_DIR:-}"
FOUND_BY_US=0
if [ -z "$APP_DIR" ]; then
  FOUND_BY_US=1
  for d in /opt/cycle-bot /root/cycle-bot /srv/cycle-bot /var/www/cycle-bot /home/*/cycle-bot /opt/luna /root/luna; do
    if [ -d "$d/app" ]; then APP_DIR="$d"; break; fi
  done
fi
if [ -z "$APP_DIR" ] && command -v pm2 >/dev/null; then
  CWD=$(pm2 jlist 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
for p in d:
    if p.get('name') == 'cycle-bot':
        print(p.get('pm2_env', {}).get('pm_cwd') or '')
        break
" 2>/dev/null)
  if [ -n "$CWD" ] && [ -d "$CWD/app" ]; then APP_DIR="$CWD"; fi
fi
[ -n "$APP_DIR" ] || die "каталог проекта не найден. Задай его: APP_DIR=/путь/к/cycle-bot bash deploy/update.sh"
[ -d "$APP_DIR/app" ] || die "в $APP_DIR нет каталога app — это не тот каталог?"

cd "$APP_DIR"
log "Каталог: $APP_DIR"

# --- 1. бэкап базы ДО всего -----------------------------------------------
log "1/5 Бэкап базы"
STAMP=$(date +%Y%m%d-%H%M%S)
mkdir -p backups
DB_PATH_VAL=$(grep -E '^DB_PATH=' .env 2>/dev/null | cut -d= -f2- | tr -d '\r' | tr -d '"' || true)
[ -z "$DB_PATH_VAL" ] && DB_PATH_VAL="luna.db"
# относительный путь — от каталога проекта; ~ — домашний каталог
case "$DB_PATH_VAL" in
  "~/"*) DB_PATH_VAL="$HOME/${DB_PATH_VAL#~/}" ;;
  /*) ;;
  *) DB_PATH_VAL="$APP_DIR/$DB_PATH_VAL" ;;
esac

# Значения из .env читаем в переменные окружения — наружу не печатаем.
# Читаем построчно, а не через `. ./.env`: sourcing падает на строках
# с кавычками или # в значении, а .env на сервере мы не контролируем.
if [ -f .env ]; then
  while IFS= read -r _line || [ -n "$_line" ]; do
    case "$_line" in
      [A-Za-z_]*=*) ;;
      *) continue ;;
    esac
    _key=${_line%%=*}
    _val=${_line#*=}
    # отбрасываем inline-комментарии и окружающие кавычки
    _val=${_val%%#*}
    _val=${_val#\"}; _val=${_val%\"}
    _val=${_val#\'}; _val=${_val%\'}
    _val=$(printf '%s' "$_val" | tr -d '\r')
    export "$_key=$_val"
  done < .env
fi

if [ -n "${DATABASE_URL:-}" ]; then
  if command -v pg_dump >/dev/null; then
    if pg_dump "$DATABASE_URL" | gzip > "backups/db-$STAMP.sql.gz" 2>/dev/null; then
      log "  бэкап Postgres: backups/db-$STAMP.sql.gz"
    else
      warn "  pg_dump не отработал — бэкап БД НЕ создан, проверь вручную"
    fi
  else
    warn "  в .env задана внешняя БД, но pg_dump нет — бэкап БД пропущен"
  fi
elif [ -f "$DB_PATH_VAL" ]; then
  cp -a "$DB_PATH_VAL" "backups/$(basename "$DB_PATH_VAL" .db)-$STAMP.db"
  log "  бэкап SQLite: backups/$(basename "$DB_PATH_VAL" .db)-$STAMP.db"
else
  warn "  файл базы не найден (DB_PATH=$DB_PATH_VAL) — бэкап пропущен"
fi

# --- 2. новые файлы --------------------------------------------------------
log "2/5 Обновление кода"
if [ -d .git ]; then
  git fetch --quiet origin 2>/dev/null
  git checkout -- app/ 2>/dev/null || true
  if git pull --ff-only --quiet origin main 2>/dev/null; then
    log "  git pull: $(git rev-parse --short HEAD)"
  else
    warn "  git pull не удался — качаю файлы напрямую"
    for f in $FILES; do
      curl -fsSL "$REPO_RAW/$f" -o "$f" && log "  скачан $f"
    done
  fi
else
  for f in $FILES; do
    curl -fsSL "$REPO_RAW/$f" -o "$f" && log "  скачан $f"
  done
fi

# --- 3. зависимости --------------------------------------------------------
log "3/5 Зависимости"
if [ -x .venv/bin/python ]; then
  .venv/bin/python -m pip install -q -r requirements.txt && log "  venv обновлён"
elif [ -x venv/bin/python ]; then
  venv/bin/python -m pip install -q -r requirements.txt && log "  venv обновлён"
else
  python3 -m pip install -q --break-system-packages -r requirements.txt 2>/dev/null \
    || python3 -m pip install -q -r requirements.txt 2>/dev/null \
    || warn "  pip не отработал — проверь зависимости вручную"
fi

# --- 4. перезапуск ---------------------------------------------------------
log "4/5 Перезапуск PM2"
if command -v pm2 >/dev/null; then
  pm2 restart cycle-bot --update-env
  pm2 save
else
  warn "  pm2 нет — перезапусти бота вручную (systemd/supervisor)"
fi

# --- 5. проверка -----------------------------------------------------------
log "5/5 Проверка"
sleep 5
if command -v pm2 >/dev/null; then
  pm2 describe cycle-bot 2>/dev/null | grep -Ei "status|restarts|uptime" || true
  echo "--- последние строки лога ---"
  pm2 logs cycle-bot --lines 20 --nostream 2>/dev/null | tail -25
fi

cat <<'EOF'

Готово. Проверь у клиентки:
  Близость → «Вся история» — должны быть видны все её даты.
  Дубль за один день показывается один раз, в базе строки целы.
EOF
