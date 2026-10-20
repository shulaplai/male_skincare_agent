"""修復「影片抽格」事故（2026-10-20）留低嘅假數據。

## 出咗咩事

`Chat.tsx` 當時只送 `{duration, frames}`（冇 `video_id`），後端於是當「冇相」：
`photo_paths=[]` → vision 冇跑 → analyze 收到嘅 prompt 只有
「（用戶訊息：（已上傳皮膚影片）／（無相，純文字））」。模型就將個 placeholder 當成
證據，自己作咗六個 attribute、`observes_skin=true`，`persist` 於是寫咗當日 Entry。
真 DB 證據：coach 訊息 `vision_used=False`，body 卻寫「睇你條片…泛紅由 0 回升到 1」。

真格（6 張）其實一直喺 disk（`data/photos/`），所以可以重跑一次真 vision 覆寫當日數字。

## 用法

    # 只報告：會修邊條 entry、用邊條片、刪邊兩條訊息（唔寫 DB、唔叫 LLM）
    ./.venv/bin/python scripts/repair_clip_entry.py

    # 真係修（會叫 1 次真 vision + 1 次 advise，並寫入真 DB）
    ./.venv/bin/python scripts/repair_clip_entry.py --apply

    # 指定某一條片（例如同時有幾條片喺同一日）
    ./.venv/bin/python scripts/repair_clip_entry.py --apply --video-id ec45db870a9c4d3e8ce90cf8b1db1a1c

## 佢做咩

1. 搵 `note` 含「（已上傳皮膚影片）」嘅 Entry（即係「靠 placeholder 寫出嚟」嗰啲）。
2. 喺同一個 conversation、同一日搵返對應嘅 `videos` row，確認抽格仍然喺 disk。
3. `--apply` 時：
   - 刪走當時嗰對假訊息（user 嘅片 chip + 跟住嗰條講大話嘅 coach 回覆）；
   - 用同一批真格重跑 `service.run_consult()`（走正常 graph：analyze → advise → persist），
     `merge_attributes` 會用真讀數覆寫當日六個 attribute。

重跑會同時更新 memory／timeline／insights（佢哋食同一批 attribute）—— 呢個係想要嘅：
假數字唔應該留喺任何衍生資料入面。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.agent import service  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import ChatMessage, Conversation, Entry, Video  # noqa: E402
from app.photo import photo_exists  # noqa: E402

PLACEHOLDER = "已上傳皮膚影片"
FAKE_NOTE = f"（{PLACEHOLDER}）"


def _payload(msg: ChatMessage) -> dict:
    raw = msg.payload or {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return {}


def _frames_of(video: Video) -> list[str]:
    raw = video.frames or "[]"
    try:
        frames = json.loads(raw) if isinstance(raw, str) else list(raw)
    except (TypeError, ValueError):
        return []
    return [f for f in frames if isinstance(f, str)]


def _day(value) -> str:
    """`YYYY-MM-DD`，唔理佢係 str 定 datetime/date（`entries.date` 係真 `date` 型別，
    `videos.created_at` 係 `datetime` —— 直接比會永遠唔相等）。"""
    if not value:
        return ""
    if isinstance(value, str):
        return value[:10]
    return value.strftime("%Y-%m-%d")


def _same_day(created_at, date) -> bool:
    return bool(_day(created_at)) and _day(created_at) == _day(date)


def find_targets(db, video_id: str | None) -> list[dict]:
    """回傳每個要修嘅 entry 連埋證據（唔改任何嘢）。"""
    out: list[dict] = []
    entries = db.scalars(select(Entry).order_by(Entry.date.desc())).all()
    for entry in entries:
        if FAKE_NOTE not in (entry.note or ""):
            continue
        videos = db.scalars(
            select(Video)
            .where(Video.conversation_id == entry.conversation_id)
            .order_by(Video.created_at.desc())
        ).all()
        if video_id:
            videos = [v for v in videos if v.id == video_id]
        else:
            videos = [v for v in videos if _same_day(v.created_at, entry.date)]
        usable = next(
            (
                v
                for v in videos
                if (frames := _frames_of(v)) and all(photo_exists(f) for f in frames)
            ),
            None,
        )

        # 當時嗰對假訊息：user（有 clip、冇 photos、text 係 placeholder）+ 跟住嗰條 coach
        msgs = db.scalars(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == entry.conversation_id)
            .order_by(ChatMessage.created_at)
        ).all()
        fake_pair: tuple[ChatMessage, ChatMessage | None] | None = None
        for i, m in enumerate(msgs):
            p = _payload(m)
            if (
                m.role == "user"
                and p.get("clip")
                and not (p.get("photos") or [])
                and PLACEHOLDER in (m.text or "")
            ):
                nxt = msgs[i + 1] if i + 1 < len(msgs) else None
                if nxt is not None and nxt.role != "coach":
                    nxt = None
                fake_pair = (m, nxt)

        out.append(
            {
                "entry": entry,
                "video": usable,
                "frames": _frames_of(usable) if usable else [],
                "fake_pair": fake_pair,
                "fake_ids": [m.id for m in fake_pair if m is not None] if fake_pair else [],
            }
        )
    return out


def describe(target: dict) -> str:
    entry: Entry = target["entry"]
    video: Video | None = target["video"]
    attrs = [
        f"{a.get('key')}={a.get('severity')}"
        for a in (entry.attributes or [])
        if isinstance(a, dict)
    ]
    lines = [
        f"entry {entry.id}  {entry.date}  conv {entry.conversation_id}",
        f"  而家嘅數字：{', '.join(attrs) or '(冇)'}",
        f"  note: {entry.note or ''}",
    ]
    if video is None:
        lines.append("  ⚠️ 搵唔到可用嘅片（同日、同 conversation、格仍然喺 disk）→ 跳過")
    else:
        lines.append(
            f"  用片 {video.id}（{video.duration:.1f} 秒，{len(target['frames'])} 格全部喺 disk）"
        )
    pair = target["fake_pair"]
    if pair is None:
        lines.append("  假訊息：搵唔到（可能已經刪過）")
    else:
        user, coach = pair
        stamp = user.created_at
        coach_id = coach.id if coach is not None else "(冇)"
        lines.append(f"  會刪訊息：user #{user.id} + coach #{coach_id}（{stamp}）")
        if coach is not None:
            claim = (coach.text or "").replace("\n", " ")[:60]
            lines.append(f"    講大話嗰句：{claim}…")
    return "\n".join(lines)


def repair(db, target: dict) -> dict:
    entry: Entry = target["entry"]
    video: Video = target["video"]
    frames: list[str] = target["frames"]

    # 先重跑：由 `resolve_clip_frames` 自己由 DB 攞格 → 真 vision → persist 覆寫當日。
    # 重跑失敗（例如 503 parse）就即刻拋，假訊息一條都唔會少 —— 唔會出現「刪咗證據但
    # 數字未修」嘅半完成狀態。
    result = service.run_consult(
        entry.conversation_id,
        FAKE_NOTE,
        photo_paths=[],
        clip={
            "video_id": video.id,
            "duration": video.duration,
            "frames": len(frames),
        },
    )

    # 重跑成功之後，才清走當時嗰對假訊息（user 片 chip + 講大話嘅 coach 回覆）
    removed = 0
    for mid in target["fake_ids"]:
        msg = db.get(ChatMessage, mid)
        if msg is not None:
            db.delete(msg)
            removed += 1
    if removed:
        db.commit()

    db.expire_all()
    fresh = db.get(Entry, entry.id)
    attrs = [
        f"{a.get('key')}={a.get('severity')}"
        for a in ((fresh.attributes if fresh else None) or [])
        if isinstance(a, dict)
    ]
    return {
        "removed_messages": removed,
        "vision_used": result.get("vision_used"),
        "attributes": attrs,
        "entry_written": result.get("entry_written"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="真係寫（唔加就只報告）")
    ap.add_argument("--video-id", default=None, help="指定用邊條片")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        targets = find_targets(db, args.video_id)
        if not targets:
            print("冇嘢要修：搵唔到 note 含「已上傳皮膚影片」而且有真格喺 disk 嘅 entry。")
            return 0

        print(f"搵到 {len(targets)} 條要修嘅 entry\n")
        for t in targets:
            print(describe(t))
            print()

        if not args.apply:
            print("（dry-run：冇寫過任何嘢。加 --apply 才會真係重跑。）")
            return 0

        conv_ids = {str(t["entry"].conversation_id) for t in targets if t["video"]}
        for cid in conv_ids:
            conv = db.get(Conversation, cid)
            if conv is not None and not conv.cloud_analysis:
                print(f"⚠️ conversation {cid} 關咗雲分析 → 唔會跑 vision，跳過（先開返先修）。")
                return 2

        for t in targets:
            if t["video"] is None:
                continue
            print(f"重跑 {t['entry'].date} …（真 LLM，要幾秒）")
            info = repair(db, t)
            print(
                f"  完成：vision_used={info['vision_used']} entry_written={info['entry_written']}"
                f"（清走 {info['removed_messages']} 條假訊息）"
            )
            print(f"  新數字：{', '.join(info['attributes']) or '(冇)'}")
        print("\n搞掂。建議再行一次 dry-run 確認冇 entry 再符合條件。")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
