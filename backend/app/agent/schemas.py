"""Structured-output contracts for the agent.

These are the "type contract" layer: the LLM must fit these shapes, so the rest
of the system (frontend render, persistence, eval) never deals with free text.
"""
from typing import Literal

from pydantic import BaseModel, Field


class Metric(BaseModel):
    key: str
    value: str
    dir: Literal["good", "bad"]


class SkinAnalysis(BaseModel):
    summary: str
    metrics: list[Metric] = Field(default_factory=list)
    tool_calls: list[str] = Field(default_factory=list)


class Advice(BaseModel):
    items: list[str]
    disclaimer: str = ""
    escalate: bool = False
