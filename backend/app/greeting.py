"""主動問候（2026-10-21，用戶要求）。

目標：令顧問「有少少打招呼嘅感覺」，就算 user 冇主動講嘢都會每日朝早／夜晚各問一次。
用戶揀咗 **09:00 ＋ 21:00、每日上限 2 次、靜音時段 23:00–08:00**。

規矩（全部 deterministic，唔靠 LLM 自己記）：

* 每個 slot 每日最多一次 —— 靠 `ChatMessage.payload["proactive"]` 記住，重啟都唔會重複；
* 只喺窗口內發：朝早 09:00–11:59、夜晚 21:00–22:59。窗口外（靜音／深夜）一律唔發；
* 用戶可以喺 Settings 關掉（`User.greet_enabled`）；
* 冇數據（新用戶）就問開放式問題，**唔可以**假裝知道皮膚狀況（約定 #10）。

呢個 module 係純邏輯（時間判斷、prompt 組裝、去重判斷）；真正嘅 loop 喺 `scheduler.py`，
寫 DB 嘅部分喺 `main._run_greeting` —— 咁樣 `greeting` 可以先被 test 直接 call。
"""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from .persona import Persona

MORNING_START = dt.time(9, 0)
MORNING_END = dt.time(12, 0)
EVENING_START = dt.time(21, 0)
EVENING_END = dt.time(23, 0)

SLOTS = ("morning", "evening")

SLOT_ZH = {"morning": "朝早", "evening": "夜晚"}


class GreetingProse(BaseModel):
    """What the model returns: one short Cantonese greeting, nothing else."""

    text: str = Field(
        default="",
        description="一句廣東話問候，20–60 字。可以問今日皮膚點／食咗啲咩，但唔可以講具體讀數。",
    )


def slot_for(now: dt.datetime) -> str | None:
    """Which greeting slot is due *right now* (or None).

    Windows are wide on purpose: if the server was asleep at 09:00 it still greets
    when it wakes up at 10:30, but never at 23:30 (quiet hours).
    """
    t = now.time()
    if MORNING_START <= t < MORNING_END:
        return "morning"
    if EVENING_START <= t < EVENING_END:
        return "evening"
    return None


def already_sent(payloads: list[dict], slot: str) -> bool:
    """Has this slot been sent today? `payloads` = today's coach message payloads."""
    return any((p or {}).get("proactive") == slot for p in payloads)


def build_prompt(
    persona: Persona,
    slot: str,
    *,
    last_entry_note: str = "",
    recent_days: int = 0,
    memory_lines: list[str] | None = None,
) -> str:
    """Pure: the greeting prompt. Deliberately small and boring — it is a hello.

    Factual grounding: it may mention *that* it has records (`recent_days`), and it
    may quote what the user wrote (`last_entry_note`), but it must never invent a
    score. When there is nothing, it asks an open question instead.
    """
    parts = [persona.prompt_block()]
    parts.append(
        "【今次係你主動開口，唔係用戶問你】\n"
        f"而家係{SLOT_ZH[slot]}。用 1–2 句廣東話同佢打招呼（好似朋友咁，唔好客服腔），"
        "可以順帶問一句今日皮膚點／食咗啲咩／有冇用新產品。"
    )
    facts: list[str] = []
    if recent_days > 0:
        facts.append(f"佢最近 {recent_days} 日有皮膚紀錄。")
    if last_entry_note.strip():
        facts.append(f"佢上次嘅原話：「{last_entry_note.strip()[:80]}」。")
    if memory_lines:
        facts.append("你記得：" + "；".join(memory_lines[:3]) + "。")
    if facts:
        parts.append("【已知嘅事實（只可以講呢啲，唔可以作數）】\n" + "\n".join(facts))
    else:
        parts.append(
            "【未有紀錄】佢仲未有任何皮膚紀錄。唔好假裝知道佢嘅皮膚狀況，"
            "問佢今日皮膚點或者想唔想開始記錄。"
        )
    parts.append(
        "限制：唔可以講任何具體分數／指標數字；唔可以診斷、開藥、講劑量；"
        "唔好長篇（超過 2 句就太多）；唔好每次都同一句開場白。"
    )
    return "\n\n".join(parts)


def compose(generated: str, slot: str) -> str:
    """Guard the greeting: strip, cap length, drop an empty answer.

    An empty greeting would render as an empty bubble, which looks broken — the
    caller treats `""` as「今次唔發」.
    """
    text = (generated or "").strip()
    if not text:
        return ""
    # 60 字上限：打招呼唔應該變成第二段建議（實測 model 會愈寫愈長）。
    return text[:180]
