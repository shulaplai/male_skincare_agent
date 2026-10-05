"""Service layer: run the agent graph with production dependencies.

Keeps a cached embedder (model load is expensive) and picks the LLM by config
(real adapter if a key is set, FakeLLM otherwise). Reads the conversation's
cloud-analysis flag **and** the user's one-time photo consent, so `analyze` knows
whether photos may leave the machine (both are required).

Every consult also appends one JSON line to `settings.run_log_path` (local file,
no photos/keys) containing the per-node trace — that is the post-hoc debug trail
for "the reply looks wrong" (see `scripts/trace_consult.py` for live tracing).
"""
import datetime
import json
import logging
from pathlib import Path

from langchain_core.exceptions import OutputParserException
from fastapi import HTTPException

from ..config import settings
from ..db import SessionLocal
from ..models import Conversation
from ..rag.embeddings import FastembedEmbedder
from .graph import build_graph
from .llm import get_llm

logger = logging.getLogger(__name__)

_embedder: FastembedEmbedder | None = None


def _get_embedder() -> FastembedEmbedder:
    global _embedder
    if _embedder is None:
        # Empty cache_dir = library default (a temp dir macOS likes to wipe,
        # which would silently drop us to the 128-dim hashing embedder).
        _embedder = FastembedEmbedder(cache_dir=settings.embedder_cache_dir or None)
    return _embedder


def write_run_log(conversation_id: str, text: str, result: dict) -> None:
    """Append one JSON line per consult. Best-effort: never breaks a consult."""
    if not settings.run_log_enabled:
        return
    try:
        path = Path(settings.run_log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "conversation_id": conversation_id,
            "user_text": text,
            "vision_used": bool(result.get("vision_used")),
            "escalate": bool(result.get("escalate")),
            "tool_calls": (result.get("analysis") or {}).get("tool_calls", []),
            "tools": [
                {
                    "tool": r.get("tool"),
                    "rows": len(r["result"]) if isinstance(r.get("result"), list) else None,
                    "error": r.get("error"),
                }
                for r in result.get("tool_results", [])
            ],
            "trace": result.get("trace", []),
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as e:  # disk full / read-only data dir — logging must not 500
        logger.warning("run log 寫唔入（%s）：%s", settings.run_log_path, e)


# 同一個字串同時用喺兩條路：POST 嘅 503 body 同 SSE 嘅 `error` frame。
# 兩邊講同一句話，先至唔會出現「串流過嘅失敗訊息唔同」呢種分歧。
CONSULT_PARSE_FAILED = (
    "我今次分析唔到（模型回覆格式唔啱，試過糾正都唔成功）。"
    "你嘅紀錄冇被改動 —— 請再試一次，或者換個講法。"
)


def open_consult(conversation_id: str, photo_paths: list[str] | None) -> bool:
    """查 conversation ＋ 決定相可唔可以出機，回 `cloud_analysis`。

    由 `run_consult` 拆出嚟，因為 SSE route 一定要喺寫任何 header **之前**答 404
    （一旦開始串流，status code 已經送咗，之後淨係可以用 in-band `error` frame）。
    所以 404 同 consent 判斷只有呢一個 implementation，兩條路都行佢。
    """
    session = SessionLocal()
    try:
        conv = session.query(Conversation).filter_by(id=conversation_id).first()
        if conv is None:
            raise HTTPException(status_code=404, detail="conversation not found")
        # Two independent conditions, both required before an image byte leaves the
        # machine: the conversation is cloud-analysed (always true since the
        # 2026-10-01 cloud-only decision) *and* the user granted the one-time
        # consent. Checked here, server-side, so the guarantee never depends on the
        # UI having hidden a button.
        user_consent = bool(conv.user.photo_cloud_consent) if conv.user else False
        cloud_analysis = bool(conv.cloud_analysis) and user_consent
        if photo_paths and not cloud_analysis:
            logger.warning(
                "consult: %d photo(s) attached but cloud vision not allowed "
                "(conversation_flag=%s, user_consent=%s) → text-only",
                len(photo_paths),
                bool(conv.cloud_analysis),
                user_consent,
            )
        return cloud_analysis
    finally:
        session.close()


def _build_consult_graph():
    return build_graph(
        llm=get_llm("text"),
        vision_llm=get_llm("vision"),
        session_factory=SessionLocal,
        embedder=_get_embedder(),
    )


def _consult_state(
    conversation_id: str,
    text: str,
    photo_paths: list[str] | None,
    clip: dict | None,
    cloud_analysis: bool,
) -> dict:
    return {
        "conversation_id": conversation_id,
        "user_text": text,
        "photo_paths": photo_paths or [],
        # `{"duration": 12.4, "frames": 6}` 當用戶上載嘅係片（唔係相）。
        # 有呢個 flag，prompt 才會叫 model 講「條片」而唔係「幾張相」。
        "clip": clip,
        "cloud_analysis": cloud_analysis,
        "trace": [],
    }


def _finish_consult(conversation_id: str, text: str, result: dict) -> dict:
    result["vision_used"] = bool(result.get("vision_used"))
    write_run_log(conversation_id, text, result)
    return result


def run_consult(
    conversation_id: str,
    text: str,
    photo_paths: list[str] | None = None,
    clip: dict | None = None,
) -> dict:
    cloud_analysis = open_consult(conversation_id, photo_paths)
    graph = _build_consult_graph()
    try:
        result = graph.invoke(
            _consult_state(conversation_id, text, photo_paths, clip, cloud_analysis)
        )
    except OutputParserException as e:
        # The model kept answering in the wrong shape even after the corrective retry.
        # Refusing loudly is the honest move: a made-up analysis would be persisted as the
        # user's skin record. The detail is readable, unlike a bare 500 — and it promises
        # only what is true (nothing was written; `persist` never ran).
        logger.error("consult failed: model output could not be parsed: %s", e)
        raise HTTPException(status_code=503, detail=CONSULT_PARSE_FAILED) from e
    return _finish_consult(conversation_id, text, result)


def stream_consult(
    conversation_id: str,
    text: str,
    cloud_analysis: bool,
    photo_paths: list[str] | None = None,
    clip: dict | None = None,
):
    """`run_consult` 做嘅同一件事，但逐個 node 報出嚟（SSE 用）。

    Yield `("node", {"node": name, "ms": ms})` 每次一個 graph node 行完
    （analyze → tools → advise → guardrail → persist），最後 yield
    `("result", dict)`，個 dict 同 `run_consult` 回嘅一模一樣（前端照舊 render）。
    失敗就 yield `("error", CONSULT_PARSE_FAILED)` 然後收工 —— HTTP status 冇得改，
    所以錯誤一定要 in-band 講。

    `cloud_analysis` 由 caller 傳入（route 已經行咗 `open_consult`），令 404 可以
    喺串流開始之前就係一個真 HTTP status。
    """
    graph = _build_consult_graph()
    state = _consult_state(conversation_id, text, photo_paths, clip, cloud_analysis)
    final: dict = state
    try:
        # 兩個 mode 一齊要：「updates」話我知邊個 node 行完咗，「values」最後一個
        # chunk 就係完整 state（唔使自己重現 Annotated list 嘅 reducer）。
        for mode, chunk in graph.stream(state, stream_mode=["updates", "values"]):
            if mode == "updates":
                for node, update in chunk.items():
                    steps = (update or {}).get("trace") or []
                    ms = steps[-1].get("ms") if steps else None
                    yield "node", {"node": node, "ms": ms}
            else:
                final = chunk
    except OutputParserException as e:
        logger.error("consult failed: model output could not be parsed: %s", e)
        yield "error", CONSULT_PARSE_FAILED
        return
    yield "result", _finish_consult(conversation_id, text, final)
