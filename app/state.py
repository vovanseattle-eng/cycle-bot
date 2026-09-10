from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup

from app.cycle import CycleSnapshot, cfg_from_user, snapshot_cfg
from app.dates import today_in


class Flow(StatesGroup):
    pick_plen = State()
    pick_clen = State()
    pick_sex_prot = State()
    pick_next = State()
    diary_note = State()


def user_snap(user: dict) -> CycleSnapshot:
    today = today_in(user.get("tz"))
    return snapshot_cfg(cfg_from_user(user, today), today)
