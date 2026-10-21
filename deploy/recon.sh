#!/usr/bin/env bash
# Разведка по cycle-bot на сервере: где каталог, чем запущен, где база,
# какие версии пакетов, git-репозиторий ли это.
#
# Ничего не меняет — только читает. Запуск:
#   bash deploy/recon.sh

set -uo pipefail

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }

echo "=== Хост ==="
hostname

echo
echo "=== PM2: процессы (имя | каталог | скрипт | статус) ==="
if command -v pm2 >/dev/null; then
  pm2 jlist 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
for p in d:
    e = p.get('pm2_env', {})
    print(f\"  {p.get('name'):<22} | cwd={e.get('pm_cwd')} | script={e.get('pm_exec_path')} | {e.get('status')}\")
"
else
  echo "  pm2 не установлен"
fi

echo
echo "=== PM2: параметры cycle-bot ==="
pm2 describe cycle-bot 2>/dev/null | grep -Ei "script path|exec cwd|cwd|interpreter|status|restarts|uptime|pid" || echo "  cycle-bot в pm2 не найден"

# Каталог проекта: сперва пробуем типовые, потом берём из pm2.
APP_DIR=""
for d in /opt/cycle-bot /root/cycle-bot /srv/cycle-bot /var/www/cycle-bot /home/*/cycle-bot /opt/luna /root/luna; do
  if [ -d "$d/app" ]; then APP_DIR="$d"; break; fi
done
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

echo
if [ -z "$APP_DIR" ]; then
  log "Каталог проекта не найден автоматически. Проверь вручную:"
  echo "  pm2 describe cycle-bot | grep -i cwd"
  echo "  find / -maxdepth 4 -type d -name app -path '*cycle*' 2>/dev/null"
  exit 0
fi

log "ПРОЕКТ: $APP_DIR"
cd "$APP_DIR"

echo
echo "=== .env (имена ключей, значения скрыты) ==="
if [ -f .env ]; then
  grep -E '^[A-Za-z_]+=' .env | sed 's/=.*/= <скрыто>/'
  echo "--- путь к базе ---"
  grep -E '^DB_PATH=' .env || echo "  DB_PATH не задан (значит база по умолчанию: ./luna.db)"
  echo "--- DATABASE_URL ---"
  if grep -qE '^DATABASE_URL=.+' .env; then echo "  ДА, задан (Postgres)"; else echo "  нет — база SQLite"; fi
else
  echo "  .env НЕТ"
fi

echo
echo "=== Файлы базы рядом с проектом ==="
ls -la ./*.db 2>/dev/null || echo "  *.db в корне нет"

echo
echo "=== Python и пакеты ==="
for v in .venv venv; do
  if [ -x "$v/bin/python" ]; then
    echo "  VENV: $v"
    "$v/bin/python" --version
    "$v/bin/python" -m pip list 2>/dev/null | grep -Ei "aiogram|magic-filter|aiosqlite|asyncpg" || true
  fi
done
if ! [ -x .venv/bin/python ] && ! [ -x venv/bin/python ]; then
  python3 --version 2>/dev/null
  python3 -m pip list 2>/dev/null | grep -Ei "aiogram|magic-filter" || echo "  пакеты в системном python не видны"
fi

echo
echo "=== Git ==="
if [ -d .git ]; then
  echo "  репозиторий: $(git remote get-url origin 2>/dev/null)"
  echo "  HEAD: $(git rev-parse --short HEAD 2>/dev/null)"
  echo "  ветка: $(git branch --show-current 2>/dev/null)"
  echo "  незакоммиченные правки:"
  git status --short 2>/dev/null | head -15
else
  echo "  НЕ git-репозиторий — файлы обновляются копированием"
fi

echo
log "Готово. Дальше: bash deploy/update.sh"
