"""Structured-output contracts for the agent.

These are the "type contract" layer: the LLM must fit these shapes, so the rest
of the system (frontend render, persistence, eval) never deals with free text.

`SkinAnalysis.attributes` is the fixed per-attribute schema (Q22): every
analysis rates the SAME set of attributes on a 0–3 severity scale, so change
detection (code diff over history) and memory reconcile (tag + direction) share
one source of truth. `metrics` is the human-facing display list derived from
the same observation and kept for UI compatibility.
"""
from typing import Literal

from pydantic import BaseModel, Field

AttributeKey = Literal["acne", "oiliness", "redness", "dryness", "pores", "texture"]


class Metric(BaseModel):
    key: str
    value: str
    dir: Literal["good", "bad", "neutral"]


class Attribute(BaseModel):
    key: AttributeKey
    # 0 = none/clear, 1 = mild, 2 = moderate, 3 = severe.
    severity: int = Field(ge=0, le=3)
    note: str = ""


class SkinAnalysis(BaseModel):
    summary: str
    metrics: list[Metric] = Field(default_factory=list)
    attributes: list[Attribute] = Field(default_factory=list)
    tool_calls: list[str] = Field(default_factory=list)


class DetectedEvent(BaseModel):
    """A self-reported event the agent noticed in the user's message (Q49/Q51).

    The user CONFIRMS before anything is written — the model only proposes.
    type: diet (飲食特別嘢) | product_start (開始用新產品) | product_stop (停用).
    """

    type: Literal["diet", "product_start", "product_stop"]
    text: str  # short zh, as the user would say it, e.g. 「食咗辣底」
    tags: list[str] = Field(default_factory=list)  # diet triggers e.g. ["spicy"]
    product_name: str = ""  # for product_start/product_stop


class Advice(BaseModel):
    # `reply` is the coach's narrative answer shown as the message text:
    # 2–5 sentences in Cantonese that explain the analysis, the reasoning
    # behind the advice, and what the app will remember. `items` are the
    # punchy bullet actions rendered in the card.
    reply: str = ""
    items: list[str] = Field(default_factory=list)
    detected_events: list[DetectedEvent] = Field(default_factory=list)
    disclaimer: str = ""
    escalate: bool = False


class TimelineSummary(BaseModel):
    """Natural-language timeline lines for a day with notable changes."""

    events: list[str]
