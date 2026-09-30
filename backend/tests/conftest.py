"""Global test guards.

## `no_real_llm` — why this exists

`backend/.env` holds a real DeepSeek key, so `get_llm()` returns a real adapter
whenever a test path calls it. That is not a hypothetical: a newly added API test
for `POST /api/conversations/{cid}/products/evaluate` did exactly that and spent
six real API calls (~10s) before anyone noticed, because the endpoint builds its
own LLM internally instead of taking one as a parameter.

Patching `get_llm` would not be enough — several modules do
`from app.agent.llm import get_llm`, so they hold their own reference. Patching the
adapters' `_client()` is the choke point that every path must pass through, no
matter how it imported the factory. `FakeLLM` never calls `_client()`, so tests
that legitimately use `FakeLLM` are unaffected.

If a test genuinely needs a real provider it has to opt out explicitly
(`@pytest.mark.no_real_llm_opt_out` + `monkeypatch.undo()`), which makes the
intent — and the spend — visible in review.
"""
import pytest

from app.agent.llm import AnthropicLLM, OpenAICompatLLM


def _forbid(*args, **kwargs):
    raise AssertionError(
        "a test tried to build a real LLM client — this would hit the network and "
        "spend real API credit. Inject FakeLLM instead (see tests/conftest.py)."
    )


@pytest.fixture(autouse=True)
def no_real_llm(request, monkeypatch):
    if request.node.get_closest_marker("no_real_llm_opt_out"):
        yield
        return
    monkeypatch.setattr(OpenAICompatLLM, "_client", _forbid)
    monkeypatch.setattr(AnthropicLLM, "_client", _forbid)
    yield


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "no_real_llm_opt_out: allow a test to construct a real LLM client (it will "
        "spend API credit and needs the network)",
    )
