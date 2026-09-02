"""Seed a deterministic DEMO database (Q10/Q19).

Writes to a SEPARATE sqlite file (default `data/demo.db`) — it never touches
your real dev DB (`data/skincoach.db`). Generates ~90 days of realistic-looking
(but clearly synthetic) entries, diet/product causes, memory and a chat thread,
so the interview demo / UI walkthrough has data to show without polluting real
records.

Usage (from backend/):
    ./.venv/bin/python scripts/seed_demo.py                # -> data/demo.db
    SKINCOACH_DATABASE_URL=sqlite:///./data/demo.db ./.venv/bin/python -m uvicorn app.main:app --port 8001

Deterministic: same seed -> same data (dates are computed relative to today so
the demo always looks fresh). Real photos are NOT fabricated — entries carry
attributes/metrics but no images (an honest empty state in the UI).
"""
from __future__ import annotations

import argparse
import datetime
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.db import Base  # noqa: E402
from app.models import (  # noqa: E402
    ChatMessage,
    Conversation,
    Entry,
    Insight,
    Product,
    TimelineEvent,
    User,
    new_id,
)

ATTR_KEYS = ["acne", "oiliness", "redness", "dryness", "pores", "texture"]
ATTR_ZH = {
    "acne": "暗瘡",
    "oiliness": "油光",
    "redness": "泛紅",
    "dryness": "乾燥",
    "pores": "毛孔",
    "texture": "質感",
}
SEED = 20260209
N_DAYS = 90


def _day(offset: int) -> datetime.date:
    """offset 0 = today, negative = past."""
    return datetime.date.today() + datetime.timedelta(days=offset)


def _sev_curve(rng: random.Random, offset: int, base: float, amp: float, noise: float) -> int:
    """Deterministic 0..3 severity for a day offset."""
    t = -offset  # 0..N
    wave = amp * rng.choice([-1, 1]) * rng.random() if rng.random() < 0.4 else amp * 0.2 * rng.random()
    val = base + 0.0 * t + wave + rng.uniform(-noise, noise)
    return max(0, min(3, int(round(val))))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="./data/demo.db", help="output sqlite path")
    parser.add_argument("--days", type=int, default=N_DAYS)
    args = parser.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    engine = create_engine(f"sqlite:///{out}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    rng = random.Random(SEED)

    user = User(name="示範用戶")
    session.add(user)
    session.flush()
    face = Conversation(user_id=user.id, body_part="面部皮膚", icon="🧔", cloud_analysis=True)
    scalp = Conversation(user_id=user.id, body_part="頭皮", icon="🧑🦲", cloud_analysis=False)
    session.add_all([face, scalp])
    session.flush()

    # Products the demo user "uses" on the face.
    toner = Product(conversation_id=face.id, name="水楊酸 Toner", category="化妝水", ingredients=["水楊酸", "B5"])
    b5 = Product(conversation_id=face.id, name="B5 保濕精華", category="精華", ingredients=["維他命B5"])
    sunscreen = Product(conversation_id=face.id, name="清爽防曬 SPF50", category="防曬", ingredients=["氧化鋅"])
    session.add_all([toner, b5, sunscreen])
    session.flush()

    # Deterministic "story": acne/oiliness gradually improve; two spicy-diet
    # episodes each cause a short redness flare (so the correlation detector
    # finds a repeated pattern in the demo data).
    spicy_days = [70, 45, 22, 6]
    last_day_attrs: dict[str, int] = {}
    for offset in range(-args.days, 1):
        d = _day(offset)
        attrs: dict[str, int] = {
            "acne": _sev_curve(rng, offset, base=2.4, amp=0.35, noise=0.2),
            "oiliness": _sev_curve(rng, offset, base=2.0, amp=0.3, noise=0.25),
            "redness": _sev_curve(rng, offset, base=1.2, amp=0.25, noise=0.15),
            "dryness": _sev_curve(rng, offset, base=1.5, amp=0.3, noise=0.2),
            "pores": _sev_curve(rng, offset, base=2.0, amp=0.15, noise=0.1),
            "texture": _sev_curve(rng, offset, base=1.8, amp=0.2, noise=0.15),
        }
        # Gradual improvement for acne over the demo period.
        progress = (-offset) / args.days
        attrs["acne"] = max(0, min(3, attrs["acne"] - round(progress * 1.6)))
        # Redness flares 2–3 days after each spicy episode.
        for sd in spicy_days:
            delta = offset + sd
            if 0 <= delta <= 3:
                attrs["redness"] = min(3, attrs["redness"] + 1)
        last_day_attrs = attrs

        attr_list = [{"key": k, "severity": v, "note": ""} for k, v in attrs.items()]
        metrics = []
        if attrs["acne"] >= 2:
            metrics.append({"key": "暗瘡", "value": "有幾粒", "dir": "bad"})
        elif offset in (0, -1):
            metrics.append({"key": "暗瘡", "value": "少咗", "dir": "good"})
        if attrs["redness"] >= 2:
            metrics.append({"key": "泛紅", "value": "明顯", "dir": "bad"})

        diet: list[str] = []
        products: list[str] = []
        note = ""
        if offset in (-i for i in spicy_days):
            diet = ["食咗辣底"]
            note = "尋晚打邊爐，食咗辣底。"
        if -offset % 12 == 0:
            diet = [*diet, "飲咗杯珍珠奶茶"]
        # Routine: toner daily-ish, B5 every 2 days, sunscreen on day trips.
        if -offset % 2 == 0:
            products.append(toner.id)
        if -offset % 3 == 0:
            products.append(b5.id)
        if -offset % 4 == 0:
            products.append(sunscreen.id)

        entry = Entry(
            conversation_id=face.id,
            date=d,
            note=note or f"第 {-offset} 日打卡。",
            metrics=metrics,
            attributes=attr_list,
            diet=diet,
            products=products,
        )
        session.add(entry)

        if -offset in spicy_days:
            session.add(
                TimelineEvent(conversation_id=None, date=d, text="食咗辣底", source="user")
            )
        if -offset % 12 == 0:
            session.add(
                TimelineEvent(conversation_id=None, date=d, text="飲咗杯珍珠奶茶", source="user")
            )
        if -offset == 0:
            session.add(
                TimelineEvent(conversation_id=face.id, date=d, text="開始用：B5 保濕精華", source="user")
            )

    # A couple of scalp entries so the second conversation is not empty.
    for offset in (-1, 0):
        session.add(
            Entry(
                conversation_id=scalp.id,
                date=_day(offset),
                attributes=[{"key": "dryness", "severity": 1}, {"key": "texture", "severity": 1}],
                note="頭皮有啲痕。",
            )
        )

    # Memory derived from the latest face state (deterministic rows so the
    # right panel shows "AI 記得你" without needing a live consult).
    for key, sev in last_day_attrs.items():
        direction = "problem" if sev >= 2 else "normal"
        session.add(
            Insight(
                conversation_id=face.id,
                kind="derived",
                tag=key,
                direction=direction,
                text=f"{ATTR_ZH.get(key, key)}：{'中等' if sev == 2 else '嚴重' if sev == 3 else '輕微' if sev == 1 else '正常'}",
                confidence=0.75,
                expires_at=datetime.datetime.now() + datetime.timedelta(days=30),
            )
        )
    # Global facts + a preference (diet evidence is seeded above).
    session.add(
        Insight(conversation_id=None, kind="fact", tag="user_fact", text="對花生敏感，避開花生製品")
    )
    session.add(
        Insight(conversation_id=face.id, kind="preference", tag="product:水楊酸 Toner", text="常用產品：水楊酸 Toner")
    )

    # A minimal chat thread so the chat view is not empty after load.
    session.add_all(
        [
            ChatMessage(conversation_id=face.id, role="user", text="朝早洗面，搽咗水楊酸 toner。", payload={}),
            ChatMessage(
                conversation_id=face.id,
                role="coach",
                text="收到！今日暗瘡比起上星期少咗。我會繼續記住你嘅 routine，繼續影相打卡就得。",
                payload={
                    "summary": "示範數據：整體穩定好轉。",
                    "metrics": [{"key": "暗瘡", "value": "少咗", "dir": "good"}],
                    "attributes": [{"key": "acne", "severity": 1}],
                    "advice": ["繼續每日防曬", "保濕要做足"],
                    "disclaimer": "",
                    "escalate": False,
                    "vision_used": False,
                },
            ),
        ]
    )
    session.commit()
    n_entries = session.query(Entry).count()
    session.close()

    print(f"✅ demo DB written: {out}（{n_entries} entries · {args.days} 日）")
    print()
    print("起 demo server（用返呢個 DB）：")
    print(f"  cd backend")
    print(f"  SKINCOACH_DATABASE_URL=sqlite:///{out} ./.venv/bin/python -m uvicorn app.main:app --port 8001")
    print()
    print("註：呢個係示範數據（synthetic），同你嘅真紀錄分開。要回真嘢就照常用 data/skincoach.db。")


if __name__ == "__main__":
    main()
