"""Guide tests.

Structure + the load-bearing one: **every citation must resolve in the real
corpus**. A citation that cannot be found is worse than no citation — it looks
like evidence. That check already caught a wrong citation in `ingredients.py`
(a missing trailing period), so it is applied here too. It reads
`backend/data/skincoach.db`, absent in CI, so it skips there.

The other thing pinned here is the *absence* of uncited claims dressed up as
findings: the 「一次只加一樣新產品」 callout must stay explicitly labelled as app
guidance, because the corpus has no source for it.
"""
import re
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.guide import build_guide, section_ids
from app.main import app

_REAL_DB = Path(__file__).resolve().parents[1] / "data" / "skincoach.db"


# ---------------------------------------------------------------------------
# Structure — matches what was asked for
# ---------------------------------------------------------------------------


def test_sections_cover_the_four_requested_topics():
    assert section_ids() == ["daily", "order", "by_skin", "cautions"]


def test_guide_is_self_consistent():
    g = build_guide()
    assert g.title
    assert g.subtitle
    # `sources` is the aggregate of the per-block citations, nothing else.
    per_block = [c for s in g.sections for b in s.blocks for c in b.citations]
    assert g.sources == list(dict.fromkeys(per_block))
    assert len(g.sources) >= 8


def test_every_callout_has_text_and_a_known_tone():
    tones = {"info", "warn", "tip"}
    for s in build_guide().sections:
        for b in s.blocks:
            if b.type == "callout":
                assert b.text.strip()
                assert b.tone in tones
            if b.type in ("list", "steps", "actives"):
                assert b.items
            if b.type == "image":
                assert b.image_id, "an image block needs an id for the placeholder"


def test_endpoint_serves_the_guide():
    r = TestClient(app).get("/api/guide")
    assert r.status_code == 200
    body = r.json()
    assert [s["id"] for s in body["sections"]] == ["daily", "order", "by_skin", "cautions"]
    assert body["sources"]


# ---------------------------------------------------------------------------
# No drift from the recommender
# ---------------------------------------------------------------------------


def test_actives_section_is_generated_from_the_rule_table():
    """The guide cannot disagree with the agent: both read `recommend.RULES`."""
    from app.agent.ingredients import display_zh
    from app.agent.recommend import RULES

    blocks = [b for s in build_guide().sections for b in s.blocks if b.type == "actives"]
    assert len(blocks) == 1, "expected exactly one generated actives table"
    items = blocks[0].items
    assert len(items) == len(RULES), "one row per rule, no hand-written extras"

    for item in items:
        assert "主選：" in item and "次選：" in item

    joined = "\n".join(items)
    for rule in RULES:
        # D5: Chinese names wherever a name exists.
        assert display_zh(rule.primary[0]) in joined
        assert display_zh(rule.alternative[0]) in joined
        # Both reasons are carried through verbatim.
        assert rule.primary[1] in joined
        assert rule.alternative[1] in joined


# ---------------------------------------------------------------------------
# Honesty
# ---------------------------------------------------------------------------


def test_uncited_app_advice_is_labelled_as_such():
    """The corpus has no source for "one new product at a time"."""
    labelled = [
        b
        for s in build_guide().sections
        for b in s.blocks
        if "一次只加一樣新產品" in b.text
    ]
    assert labelled, "the callout disappeared; if removed on purpose, drop this test"
    for b in labelled:
        assert "app 建議" in b.text, "uncited advice must be labelled, not dressed as evidence"
        assert b.citations == [], "if a citation was found, cite it instead of the label"


def test_guide_states_no_dose_and_points_at_a_doctor():
    """Narrower than the guardrail on purpose.

    `contains_medical_advice` is built for *advice* text and trips on the bare word
    處方藥 — but the guide legitimately mentions prescription medication in order to
    say "follow your doctor". What must never appear here is a **dose**.
    """
    from app.agent.guardrails import DOSE_RE

    text = "\n".join(
        "\n".join([b.text, *b.items]) for s in build_guide().sections for b in s.blocks
    )
    assert DOSE_RE.search(text) is None, "the guide must not state a dose"
    assert "皮膚科" in text or "睇醫生" in text, "cautions must point at a doctor"


# ---------------------------------------------------------------------------
# Citations must be real
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _REAL_DB.exists(),
    reason="real corpus DB not present (CI has no data/ dir) — local-only check",
)
def test_every_guide_citation_resolves_in_the_real_corpus():
    conn = sqlite3.connect(f"file:{_REAL_DB}?mode=ro", uri=True)
    try:
        for cite in build_guide().sources:
            source, _, title = cite.partition(" :: ")
            assert source and title, f"malformed citation {cite!r}"
            # Titles in the corpus contain non-breaking spaces (U+00A0) — e.g. one
            # PMC title has "Application\xa0of". Comparing raw strings fails on an
            # invisible character; collapsing whitespace runs is the correct
            # tolerance (it cannot hide a wrong word).
            n = conn.execute(
                "select count(*) from chunks where source = ? "
                "and trim(replace(replace(title, char(160), ' '), '  ', ' ')) = ?",
                (source, " ".join(title.split())),
            ).fetchone()[0]
            assert n > 0, f"citation not found in corpus → {cite!r}"
    finally:
        conn.close()
