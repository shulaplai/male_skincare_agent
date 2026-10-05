"""LangGraph agent state.

`trace` collects one entry per node (node name, duration, and a small summary of
what that node produced). It is the run's debug trail: `graph.stream()` shows the
per-node deltas live, and `/api/consult` returns the final trace so a "reply
looks wrong" report can be traced back to the exact stage. LangGraph merges list
fields with `operator.add`, so each node appends instead of overwriting.
"""
import operator
from typing import Annotated, TypedDict


class TraceStep(TypedDict, total=False):
    node: str
    ms: float
    keys: list[str]
    # node-specific, small summaries (never the full prompt/photo)
    detail: dict


class AgentState(TypedDict, total=False):
    conversation_id: str
    user_text: str
    photo_paths: list[str]
    # Privacy consent mirror (Q18): True only when the conversation opted in to
    # cloud analysis. analyze refuses to send photos when it is False.
    cloud_analysis: bool
    vision_used: bool
    # *Why* vision did or did not contribute: `photo_unreadable | vision_error | used |
    # consent_off | fake_llm | no_photo`. Declared here because two consumers read it —
    # `build_advise_prompt` decides whether the model may claim to have seen a photo,
    # and whether a non-first text-only check-in gets the「下次影相／拍片」nudge.
    #
    # ⚠️ It used to be computed in `analyze` and dropped into the **trace detail
    # only**, never returned into state. So `state.get("vision_reason")` was always
    # `None` on the real path (the nudge never reached the model, and AGENTS.md
    # documented it as working), while the prompt tests passed because they
    # hand-built the key in a dict. Declaring it makes write and reads drift-proof.
    vision_reason: str
    # 用戶上傳嘅係一段短片（唔係相）：`{"duration": 12.4, "frames": 6}`。
    # 前端／主觀上係「一條片」——抽格係內部實作，prompt 要講「條片」而唔好數格。
    clip: dict | None
    analysis: dict | None
    tool_results: list[dict]
    # A pasted ingredient list is a *question*, not a check-in — and the deterministic
    # core already knows how to score coverage. When the user's message looks like an
    # INCI list the `tools` node fills this in, and `advise` only writes the comparison.
    product_eval: dict | None
    recent_messages: list[str]
    first_checkin: bool
    advice: dict | None
    escalate: bool
    trace: Annotated[list[TraceStep], operator.add]
