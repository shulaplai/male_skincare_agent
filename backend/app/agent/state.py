"""LangGraph agent state."""
from typing import TypedDict


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
    advice: dict | None
    escalate: bool
    error: str | None
