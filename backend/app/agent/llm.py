"""LLM abstraction behind a single `structured()` interface.

- `FakeLLM` is deterministic, used for tests and when no key is configured, so
  the whole agent graph runs end-to-end without any API key (the "no key still
  works" principle).
- `AnthropicLLM` / `OpenAICompatLLM` are the real adapters, loaded lazily.

`get_llm(kind=...)` picks the model by task: photo analysis should use a
vision-capable model (`kind="vision"`), everything else the plain text model.
DeepSeek V4 is the default provider (HK-reachable, vision since 2026-08).
"""
import logging
from typing import TypeVar

from langchain_core.exceptions import OutputParserException
from pydantic import BaseModel

from ..config import settings
from .schemas import Advice, Metric, SkinAnalysis, TimelineSummary

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)

#: Appended as a second system message when the model produced an unparseable reply.
#: Kept explicit about *why* it failed, so the model can correct the shape rather than
#: guess again. Measured: this is what makes the retry actually work.
FORMAT_CORRECTION = (
    "⚠️ 你上一次回覆冇跟格式。你只可以輸出 schema 定義嘅結構化物件；"
    "**唔可以 call 任何 function**。要要求工具，就將工具名放入 `tool_calls` "
    "欄位嘅**字串陣列**（例如 [\"search_knowledge\"]），唔係當佢係一個 function 嚟 call。"
)


class FakeLLM:
    def structured(self, system: str, user: str, schema: type[T]) -> T:
        if schema is SkinAnalysis:
            return SkinAnalysis(
                # FakeLLM 模擬「用戶描述咗皮膚」嘅情況 → True，令 test／eval 行為同真打卡一致。
                # 要試「唔應該寫紀錄」嘅路徑，test 會自己砌一個 observes_skin=False 嘅 model。
                observes_skin=True,
                summary="下巴有新暗瘡，T 字位偏油，兩頰中性",
                metrics=[
                    Metric(key="新暗瘡", value="+2", dir="bad"),
                    Metric(key="油光", value="-18%", dir="good"),
                ],
                attributes=[
                    {"key": "acne", "severity": 2, "note": "下顎線"},
                    {"key": "oiliness", "severity": 2, "note": "T 字位"},
                    {"key": "redness", "severity": 1, "note": ""},
                ],
                tool_calls=["get_skin_profile", "search_knowledge"],
            )  # type: ignore[return-value]
        if schema is Advice:
            return Advice(
                reply=(
                    "睇咗你嘅情況：下巴有兩粒新暗瘡、T 字位偏油，兩頰就中性。"
                    "新暗瘡多數同最近變數有關，我建議先暫停新產品三日，用單一變數測試搵出邊樣致敏；"
                    "同時做好保濕同每日防曬，修復返皮膚屏障。我會一路記住你嘅進度。"
                ),
                items=[
                    "暫停新產品 3 日，用單一變數測試搵出致敏源",
                    "做好保濕同每日防曬，修復皮膚屏障",
                ],
                disclaimer="",
                escalate=False,
            )  # type: ignore[return-value]
        if schema is TimelineSummary:
            return TimelineSummary(events=["（示範）暗瘡惡化↑ 下巴多咗兩粒新瘡。"])
        raise ValueError(f"FakeLLM 唔識呢個 schema: {schema}")

    def structured_vision(self, system: str, user: str, schema: type[T], images: list[dict]) -> T:
        # Fake vision == fake text analysis; used by tests and no-key demos.
        return self.structured(system, user, schema)


class AnthropicLLM:
    def __init__(self, model: str | None = None):
        self.model = model or settings.anthropic_model

    def _client(self):
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=self.model, api_key=settings.anthropic_api_key)

    def structured(self, system: str, user: str, schema: type[T]) -> T:
        runnable = self._client().with_structured_output(schema)
        return runnable.invoke([("system", system), ("human", user)])

    def structured_vision(self, system: str, user: str, schema: type[T], images: list[dict]) -> T:
        content: list[dict] = []
        for img in images:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img["media_type"],
                        "data": img["data"],
                    },
                }
            )
        content.append({"type": "text", "text": user})
        runnable = self._client().with_structured_output(schema)
        return runnable.invoke([("system", system), ("human", content)])


class OpenAICompatLLM:
    """For OpenAI-compatible providers (DeepSeek / Gemini / OpenRouter / …)."""

    def __init__(self, model: str, base_url: str | None = None):
        self.model = model
        self.base_url = base_url

    def _client(self):
        from langchain_openai import ChatOpenAI

        kwargs: dict = {
            "model": self.model,
            "api_key": settings.deepseek_api_key or settings.openai_api_key,
        }
        if self.base_url:
            kwargs["base_url"] = self.base_url
        # DeepSeek V4 enables thinking mode by default, and thinking mode
        # rejects a forced `tool_choice` (which `with_structured_output`
        # sends) with HTTP 400. Structured extraction therefore runs with
        # thinking disabled (`thinking.type: "disabled"`). Only DeepSeek
        # understands this extra body field, so it is gated on its base URL.
        if self.base_url and "deepseek.com" in self.base_url:
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        return ChatOpenAI(**kwargs)

    def _runnable(self, schema: type[T]):
        # DeepSeek / OpenAI-compat providers support function calling, not
        # `response_format: json_schema`, so force tool-based extraction.
        return self._client().with_structured_output(schema, method="function_calling")

    def _invoke(self, runnable, messages, attempts: int = 3):
        """Invoke the structured runnable, retrying with an explicit correction.

        The provider occasionally emits a *tool call* named after one of the tools
        advertised in `prompts.TOOL_GUIDE` (e.g. `search_knowledge`) instead of filling
        the schema. langchain's `PydanticToolsParser(first_tool_only=True)` takes
        `tool_calls[0]` without checking its name, so that surfaces as
        `OutputParserException: Unknown tool type: ...`.

        Measured on the live path: it hits hardest on **product/ingredient questions** —
        exactly when the model most wants `search_knowledge`. And a bare retry of the
        *same* messages was not enough (two failures in a row observed). So the retry
        appends an explicit correction saying that only the schema may be produced.

        That is not a fabricated fallback: we ask the model to answer the same question
        in the right shape. A final failure is left to propagate on purpose — there is no
        honest fallback analysis, and inventing one would persist fabricated data as the
        user's record. `service.run_consult` turns it into a readable 503, not a bare 500.
        """
        for attempt in range(1, attempts + 1):
            try:
                return runnable.invoke(messages)
            except OutputParserException as e:
                logger.warning(
                    "structured output parse failed (attempt %d/%d): %s", attempt, attempts, e
                )
                if attempt == attempts:
                    raise
                messages = [*messages, ("system", FORMAT_CORRECTION)]

    def structured(self, system: str, user: str, schema: type[T]) -> T:
        return self._invoke(self._runnable(schema), [("system", system), ("human", user)])

    def structured_vision(self, system: str, user: str, schema: type[T], images: list[dict]) -> T:
        # Standard OpenAI-compatible image_url content blocks (base64 data URL).
        content: list[dict] = [{"type": "text", "text": user}]
        for img in images:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{img['media_type']};base64,{img['data']}",
                    },
                }
            )
        return self._invoke(self._runnable(schema), [("system", system), ("human", content)])


def get_llm(kind: str = "text"):
    """Pick the LLM adapter for a task kind.

    `kind="vision"` selects a vision-capable model (photo analysis);
    `kind="text"` (default) selects the plain chat model for advice/memory.
    Resolution order: the configured provider first, then any key that is set;
    falls back to FakeLLM when no key is configured (offline demo).
    """
    provider = settings.llm_provider

    def deepseek_llm() -> OpenAICompatLLM:
        model = settings.deepseek_vision_model if kind == "vision" else settings.deepseek_text_model
        return OpenAICompatLLM(model=model, base_url="https://api.deepseek.com/v1")

    if provider == "deepseek" and settings.deepseek_api_key:
        return deepseek_llm()
    if provider == "anthropic" and settings.anthropic_api_key:
        return AnthropicLLM(model=settings.anthropic_model)
    if provider == "openai" and settings.openai_api_key:
        return OpenAICompatLLM(model=settings.openai_model, base_url="https://api.openai.com/v1")
    if settings.deepseek_api_key:
        return deepseek_llm()
    if settings.anthropic_api_key:
        return AnthropicLLM()
    if settings.openai_api_key:
        return OpenAICompatLLM(model=settings.openai_model)
    return FakeLLM()
