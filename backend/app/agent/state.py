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
    analysis: dict | None
    tool_results: list[dict]
    recent_messages: list[str]
    first_checkin: bool
    advice: dict | None
    escalate: bool
    trace: Annotated[list[TraceStep], operator.add]
