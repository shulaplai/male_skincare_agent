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
    #: Did this turn actually observe the user's skin?
    #:
    #: This is the gate for writing a daily `Entry` (see `graph.persist`). Without it
    #: every message was treated as a check-in: `ANALYZE_SYSTEM` says "未提及就畀 0",
    #: so asking「呢支精華得唔得？」produced an all-zero analysis which *replaced* the
    #: day's real readings — and the fake "改善" it generated was then frozen into the
    #: timeline, because only one agent event per day is allowed. Measured on the live
    #: path: the model returns all six attributes as 0 for a product question and says
    #: so in its own reply ("六項指標全部都係「未提及／0」").
    #:
    #: Judging "does this text describe skin state?" is language work, so it is an LLM
    #: decision rather than a keyword list — a keyword scan cannot tell
    #: 「呢支會唔會令我爆瘡？」(a question) from 「下巴爆咗兩粒」(an observation).
    #: Defaults to False: when unsure, do not write a day of data.
    observes_skin: bool = Field(
        default=False,
        description=(
            "用戶今次嘅訊息有冇描述佢**而家**嘅皮膚狀況？有就可以評分。"
            "只係問產品／成份、問知識、打招呼、講其他嘢 → false。"
            "有附上並睇到相 → true。**唔確定就 false。**"
        ),
    )
    summary: str
    metrics: list[Metric] = Field(default_factory=list)
    attributes: list[Attribute] = Field(default_factory=list)
    # Tools the model wants run for this turn. Names must come from
    # `tools.WHITELIST`; unknown names are ignored at execution time (and are
    # recorded in the run trace). The description matters: without it the model
    # had no idea which tools exist (see prompts.TOOL_GUIDE).
    tool_calls: list[str] = Field(
        default_factory=list,
        description=(
            "呢個係**字串陣列**，唔係 function call —— 填工具名落嚟，由程式代你執行。"
            "只可以用：get_skin_profile（讀長期記憶）、get_recent_entries（讀最近紀錄）、"
            "search_knowledge（檢索護膚知識庫）。唔需要就留空 array。"
        ),
    )


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


class ProductNarrative(BaseModel):
    """The coach's prose answer for a product evaluation.

    Structured rather than free text so it stays inside the type-contract layer
    (doctrine #3). `summary` is the only field the user reads, so it gets the same
    medical guardrail as `Advice.reply` (see `product_eval.guard_narrative`).
    """

    summary: str = ""
