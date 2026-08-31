"""LangGraph agent state."""
from typing import TypedDict


class AgentState(TypedDict, total=False):
    conversation_id: str
    user_text: str
    photo_paths: list[str]
    analysis: dict | None
    tool_results: list[dict]
    advice: dict | None
    escalate: bool
    error: str | None
