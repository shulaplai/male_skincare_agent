"""LLM abstraction behind a single `structured()` interface.

- `FakeLLM` is deterministic, used for tests and when no key is configured, so
  the whole agent graph runs end-to-end without any API key (the "no key still
  works" principle).
- `AnthropicLLM` / `OpenAICompatLLM` are the real adapters, loaded lazily.
"""
from typing import TypeVar

from pydantic import BaseModel

from ..config import settings
from .schemas import Advice, Metric, SkinAnalysis

T = TypeVar("T", bound=BaseModel)


class FakeLLM:
    def structured(self, system: str, user: str, schema: type[T]) -> T:
        if schema is SkinAnalysis:
            return SkinAnalysis(
                summary="下巴有新暗瘡，T 字位偏油，兩頰中性",
                metrics=[
                    Metric(key="新暗瘡", value="+2", dir="bad"),
                    Metric(key="油光", value="-18%", dir="good"),
                ],
                tool_calls=["get_skin_profile", "search_knowledge"],
            )  # type: ignore[return-value]
        if schema is Advice:
            return Advice(
                items=[
                    "暫停新產品 3 日，用單一變數測試搵出致敏源",
                    "做好保濕同每日防曬，修復皮膚屏障",
                ],
                disclaimer="",
                escalate=False,
            )  # type: ignore[return-value]
        raise ValueError(f"FakeLLM 唔識呢個 schema: {schema}")


class AnthropicLLM:
    def __init__(self, model: str | None = None):
        self.model = model or settings.strong_model

    def _client(self):
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=self.model, api_key=settings.anthropic_api_key)

    def structured(self, system: str, user: str, schema: type[T]) -> T:
        runnable = self._client().with_structured_output(schema)
        return runnable.invoke([("system", system), ("human", user)])


class OpenAICompatLLM:
    """For OpenAI-compatible providers (DeepSeek / Gemini / OpenRouter)."""

    def __init__(self, model: str | None = None, base_url: str | None = None):
        self.model = model or settings.fast_model
        self.base_url = base_url

    def _client(self):
        from langchain_openai import ChatOpenAI

        kwargs = {"model": self.model, "api_key": settings.deepseek_api_key or settings.openai_api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        return ChatOpenAI(**kwargs)

    def structured(self, system: str, user: str, schema: type[T]) -> T:
        # DeepSeek / OpenAI-compat providers support function calling, not
        # `response_format: json_schema`, so force tool-based extraction.
        runnable = self._client().with_structured_output(schema, method="function_calling")
        return runnable.invoke([("system", system), ("human", user)])


def get_llm():
    provider = settings.llm_provider
    if provider == "deepseek" and settings.deepseek_api_key:
        return OpenAICompatLLM(model="deepseek-chat", base_url="https://api.deepseek.com/v1")
    if provider == "openai" and settings.openai_api_key:
        return OpenAICompatLLM(model=settings.strong_model)
    if settings.anthropic_api_key:
        return AnthropicLLM()
    if settings.deepseek_api_key:
        return OpenAICompatLLM(model="deepseek-chat", base_url="https://api.deepseek.com/v1")
    if settings.openai_api_key:
        return OpenAICompatLLM(model=settings.strong_model)
    return FakeLLM()
