import datetime

from app.agent.attributes import direction_for
from app.memory import (
    MAX_CONFIDENCE,
    MemoryInsight,
    is_expired,
    make_derived,
    make_fact,
    reconcile,
)
from app.memory import DIRECTION_NORMAL, DIRECTION_PROBLEM

NOW = datetime.datetime(2025, 12, 14, 9, 0, 0)


def test_same_direction_strengthens_even_with_different_text():
    # Q14/Q47: reconcile compares tag + direction, NOT text.
    existing = make_derived("a", "acne", "暗瘡：中等", 0.8, NOW, direction=DIRECTION_PROBLEM)
    candidate = make_derived("b", "acne", "暗瘡：嚴重", 0.6, NOW, direction=DIRECTION_PROBLEM)

    result = reconcile(existing, candidate, NOW)

    assert len(result) == 1
    assert result[0].id == "a"  # strengthens the existing insight
    assert result[0].confidence == 0.85  # 0.8 + step
    assert result[0].text == "暗瘡：嚴重"  # text refreshed to latest
    assert result[0].direction == DIRECTION_PROBLEM


def test_confidence_is_capped():
    existing = make_derived("a", "acne", "暗瘡：中等", 0.95, NOW, direction=DIRECTION_PROBLEM)
    candidate = make_derived("b", "acne", "暗瘡：中等", 0.95, NOW, direction=DIRECTION_PROBLEM)

    result = reconcile(existing, candidate, NOW)

    assert result[0].confidence == MAX_CONFIDENCE


def test_direction_flip_supersedes_and_versions():
    # acne problem -> normal: supersede old (history kept), version+1 on new.
    existing = make_derived("a", "acne", "暗瘡：中等", 0.8, NOW, direction=DIRECTION_PROBLEM)
    candidate = make_derived("b", "acne", "暗瘡：正常", 0.6, NOW, direction=DIRECTION_NORMAL)

    result = reconcile(existing, candidate, NOW)

    assert len(result) == 2
    old, new = result
    assert old.superseded_by == "b"
    assert new.version == 2
    assert new.direction == DIRECTION_NORMAL
    assert new.text == "暗瘡：正常"


def test_different_tags_are_left_alone():
    existing = make_derived("a", "acne", "暗瘡：中等", 0.8, NOW, direction=DIRECTION_PROBLEM)
    candidate = make_derived("b", "oiliness", "油光：中等", 0.6, NOW, direction=DIRECTION_PROBLEM)

    result = reconcile(existing, candidate, NOW)

    assert len(result) == 2


def test_fact_and_preference_never_reconcile():
    fact = make_fact("f", "我對凡士林敏感", tag="allergy")
    pref = MemoryInsight(id="p", kind="preference", tag="", text="鍾意清爽質地")
    derived = make_derived("d", "acne", "暗瘡：中等", 0.6, NOW, direction=DIRECTION_PROBLEM)

    assert len(reconcile(fact, derived, NOW)) == 2
    assert len(reconcile(pref, derived, NOW)) == 2


def test_derived_insight_expires():
    insight = make_derived("a", "acne", "暗瘡：中等", 0.8, NOW, direction=DIRECTION_PROBLEM)
    after = NOW + datetime.timedelta(days=31)

    assert is_expired(insight, after) is True
    assert is_expired(insight, NOW) is False


def test_fact_and_preference_do_not_expire():
    fact = make_fact("f", "baseline 相存檔")
    pref = MemoryInsight(id="p", kind="preference", tag="", text="鍾意清爽質地")

    assert is_expired(fact, NOW + datetime.timedelta(days=365)) is False
    assert is_expired(pref, NOW + datetime.timedelta(days=365)) is False


def test_direction_for_boundary():
    # severity >= 2 is a problem; <= 1 is normal.
    assert direction_for(2) == DIRECTION_PROBLEM
    assert direction_for(3) == DIRECTION_PROBLEM
    assert direction_for(1) == DIRECTION_NORMAL
    assert direction_for(0) == DIRECTION_NORMAL
