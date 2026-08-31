import datetime

from app.memory import MAX_CONFIDENCE, MemoryInsight, is_expired, make_derived, reconcile

NOW = datetime.datetime(2025, 12, 14, 9, 0, 0)


def test_consistent_evidence_strengthens_confidence():
    existing = make_derived("a", "skin_type", "T 字位偏油", 0.8, NOW)
    candidate = make_derived("b", "skin_type", "T 字位偏油", 0.8, NOW)

    result = reconcile(existing, candidate, NOW)

    assert len(result) == 1
    assert result[0].confidence == 0.85  # 0.8 + 0.05 step


def test_confidence_is_capped():
    existing = make_derived("a", "skin_type", "T 字位偏油", 0.95, NOW)
    candidate = make_derived("b", "skin_type", "T 字位偏油", 0.95, NOW)

    result = reconcile(existing, candidate, NOW)

    assert result[0].confidence == MAX_CONFIDENCE


def test_contradiction_supersedes_and_versions():
    existing = make_derived("a", "skin_type", "偏油", 0.8, NOW)
    candidate = make_derived("b", "skin_type", "偏乾", 0.7, NOW)

    result = reconcile(existing, candidate, NOW)

    assert len(result) == 2
    old, new = result
    assert old.superseded_by == "b"
    assert new.version == 2
    assert new.text == "偏乾"


def test_different_tags_are_left_alone():
    existing = make_derived("a", "skin_type", "偏油", 0.8, NOW)
    candidate = make_derived("b", "product_reaction", "toner 致痘", 0.6, NOW)

    result = reconcile(existing, candidate, NOW)

    assert len(result) == 2


def test_derived_insight_expires():
    insight = make_derived("a", "skin_type", "偏油", 0.8, NOW)
    after = NOW + datetime.timedelta(days=31)

    assert is_expired(insight, after) is True
    assert is_expired(insight, NOW) is False


def test_fact_and_preference_do_not_decay():
    fact = MemoryInsight(id="f", kind="fact", tag="", text="baseline 相存檔")
    pref = MemoryInsight(id="p", kind="preference", tag="", text="鍾意清爽質地")

    assert is_expired(fact, NOW + datetime.timedelta(days=365)) is False
    assert is_expired(pref, NOW + datetime.timedelta(days=365)) is False
