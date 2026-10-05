"""`vision_reason` must reach `advise` through **state**, not only through the trace.

The bug this pins: `analyze` computed the six-way reason and put it in the trace
detail dict, but its return value was `{analysis, vision_used, trace}` — so nothing
ever wrote `state["vision_reason"]`. Two consumers read it:

  - `build_advise_prompt` guards "the model may claim to have seen a photo" with it
  - and adds the「下次影相或者拍一段片」nudge when a non-first check-in is text-only

On the real path both reads saw `None`. The nudge documented in `AGENTS.md`
(「純文字打卡（非首次）再加一句輕提」) therefore never reached the model.

⚠️ Why the existing tests did not catch it: `test_prompt_recording_guide.py` and
`test_prompt_photo_claims.py` call `build_advise_prompt` with a **hand-built dict**
that already contains `vision_reason`. They assert the prompt formats the key
correctly — which it does — while never checking that anything writes it. Same shape
as the two eval traps `AGENTS.md` records: a test that constructs the very thing the
production path fails to produce cannot fail.

So this test goes through `graph.invoke` and reads the prompt the `advise` node
actually passed to the model. It fails if the state key disappears, if it is renamed,
or if `analyze` stops returning it.
"""
import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent.graph import build_graph
from app.agent.schemas import Advice, SkinAnalysis
from app.db import Base
from app.models import Conversation, Entry, User
from app.rag import DeterministicEmbedder

NUDGE = "今次係純文字打卡"


def make_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def seed_conversation(sf, *, with_prior_entry: bool) -> str:
    """A conversation, optionally with an Entry already recorded today.

    An existing Entry is what makes the next turn *not* a first check-in, which is
    the only branch that carries the nudge.
    """
    s = sf()
    u = User(name="阿軒")
    s.add(u)
    s.flush()
    c = Conversation(user_id=u.id, body_part="面部皮膚")
    s.add(c)
    s.flush()
    if with_prior_entry:
        s.add(Entry(conversation_id=c.id, date=datetime.date.today(), note="早前影咗相"))
    s.commit()
    cid = c.id
    s.close()
    return cid


class RecordingStubLLM:
    """Observes skin (so `observes_skin` is true) and keeps every prompt it was given."""

    def __init__(self):
        self.prompts: list[str] = []

    def structured(self, system, user, schema):
        self.prompts.append(user)
        if schema is SkinAnalysis:
            return SkinAnalysis(
                observes_skin=True,
                summary="下巴有兩粒",
                attributes=[{"key": "acne", "severity": 2, "note": ""}],
                tool_calls=[],
            )
        if schema is Advice:
            return Advice(reply="記得保濕。", items=["保濕"], escalate=False)
        raise ValueError(f"unexpected schema: {schema}")

    def structured_vision(self, system, user, schema, images):
        return self.structured(system, user, schema)


def run_turn(**kwargs):
    sf = make_factory()
    cid = seed_conversation(sf, with_prior_entry=kwargs["with_prior_entry"])
    llm = RecordingStubLLM()
    graph = build_graph(
        llm=llm, session_factory=sf, embedder=DeterministicEmbedder(), vision_llm=llm
    )
    final = graph.invoke(
        {
            "conversation_id": cid,
            "user_text": "今日下巴有兩粒",
            "photo_paths": [],
            "cloud_analysis": True,
        }
    )
    # The advise call is the last prompt of the run; keep them all for clarity.
    return final, llm.prompts


def test_vision_reason_is_declared_in_state():
    """The structural half: the key must exist after a run, with a legal value.

    Fails on a rename as well as on a removal, which is what `state.py`'s comment
    ("write and reads cannot drift apart again") promises.
    """
    final, _ = run_turn(with_prior_entry=True)
    assert "vision_reason" in final, (
        "analyze 冇將 vision_reason 寫入 state——prompts 兩處 state.get() 會永遠見到 None"
    )
    assert final["vision_reason"] == "no_photo", final["vision_reason"]


def test_the_text_only_nudge_actually_reaches_the_model():
    """The behavioural half, through the real graph — the assertion that can fail.

    A non-first, text-only, skin-observing turn must carry the nudge in the prompt
    the `advise` node really sends. `RecordingStubLLM` captures it, so this is the
    production path and not a hand-built state dict.
    """
    final, prompts = run_turn(with_prior_entry=True)
    assert final["first_checkin"] is False, "測試前提：要有先前 Entry 才唔係首次打卡"
    assert final["vision_used"] is False

    # `build_advise_prompt` 嘅結構記認係「用戶：」／「分析：」；唔好靠關鍵詞猜。
    advise_prompts = [p for p in prompts if "分析：" in p]
    assert len(advise_prompts) == 1, f"應該恰好一個 advise prompt，實際={len(advise_prompts)}"
    assert NUDGE in advise_prompts[0], (
        "非首次嘅純文字打卡一定要喺 advise prompt 見到「" + NUDGE + "」——"
        "睇唔到即係 state['vision_reason'] 又斷咗。前 200 字：\n"
        + advise_prompts[0][:200]
    )


def test_first_checkin_does_not_get_the_nudge():
    """The gate's other side: on a first check-in the nudge must be absent.

    Without this, a bug that unconditionally appends the nudge would satisfy the
    test above.
    """
    final, prompts = run_turn(with_prior_entry=False)
    assert final["first_checkin"] is True
    advise_prompts = [p for p in prompts if "分析：" in p]
    assert len(advise_prompts) == 1
    assert NUDGE not in advise_prompts[0], "首次打卡唔應該出「純文字打卡」nudge"
