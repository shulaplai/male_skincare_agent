"""Recommendation table + product evaluation tests.

These pin the *decisions* the user made, not just the mechanics:

* D1/D6 — two tiers (主選／次選), coverage matching instead of a prescription list;
* D7 — pigmentation arrives as a note keyword or an explicit flag, never as a 7th
  attribute;
* §3.5 — formula roles stay out of coverage matching;
* the hard stop list stays narrow.
"""
import pytest

from app.agent.product_eval import evaluate_product, guard_narrative
from app.agent.recommend import (
    TRIGGER_FLOOR,
    actives_in_name,
    mentions_pigmentation,
    recommend_actives,
)
from app.agent.guardrails import ESCALATION_MESSAGE


# ---------------------------------------------------------------------------
# recommend_actives
# ---------------------------------------------------------------------------


def test_trigger_floor_is_the_schema_convention():
    """>=2 means "problem" (attributes.direction_for) — 1 must not fire."""
    assert TRIGGER_FLOOR == 2
    assert recommend_actives({"acne": 1}).suggestions == ()
    assert recommend_actives({"acne": 2}).suggestions != ()


def test_each_trigger_yields_a_primary_and_an_alternative():
    rec = recommend_actives({"redness": 2})
    assert [s.key for s in rec.primaries] == ["azelaic_acid"]
    alts = [s for s in rec.suggestions if not s.is_primary]
    assert [s.zh for s in alts] == ["泛醇"]
    assert rec.triggers == ("redness",)


def test_an_active_that_is_primary_somewhere_stays_primary():
    """Salicylic acid is primary for acne and only an alternative for oiliness."""
    rec = recommend_actives({"acne": 3, "oiliness": 3})
    sal = next(s for s in rec.suggestions if s.key == "salicylic_acid")
    assert sal.is_primary
    # Both reasons are kept, so the user sees why it appeared twice.
    assert len(sal.reasons) == 2


def test_no_trigger_means_no_suggestions():
    rec = recommend_actives({"acne": 0, "dryness": 1})
    assert rec.suggestions == ()
    assert rec.warnings == ()


def test_dry_and_acne_together_warns_instead_of_silently_stacking_acids():
    rec = recommend_actives({"acne": 2, "dryness": 2})
    assert any("唔好同時上高濃度酸" in w for w in rec.warnings)


def test_active_already_in_use_warns_against_buying_a_second_one():
    rec = recommend_actives({"acne": 2}, in_use={"salicylic_acid": "水楊酸 toner"})
    assert any("水楊酸 toner" in w and "唔需要再買" in w for w in rec.warnings)


def test_pigmentation_is_a_trigger_of_its_own():
    rec = recommend_actives({}, pigmentation=True)
    assert rec.triggers == ("pigmentation",)
    assert [s.zh for s in rec.primaries] == ["α-熊果素"]


# ---------------------------------------------------------------------------
# D7: where "pigmentation" comes from
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    ["下巴爆完瘡留咗好多印", "想搞暗瘡印", "面上有色素沉澱", "鼻翼有黑印", "痘印淡咗好多"],
)
def test_pigmentation_hints_match(text):
    assert mentions_pigmentation(text) is True


@pytest.mark.parametrize("text", ["印尼之旅", "打印機壞咗", "我對佢印象好好", "冇印", ""])
def test_bare_yin_does_not_match(text):
    """A bare 「印」 would false-positive on 印尼／打印／印象."""
    assert mentions_pigmentation(text) is False


# ---------------------------------------------------------------------------
# evaluate_product — coverage matching (D1)
# ---------------------------------------------------------------------------


def test_covers_all_primaries_is_good():
    r = evaluate_product(
        "Aqua, Salicylic Acid 2%, Niacinamide, Glycerin",
        attributes={"acne": 2, "oiliness": 2},
    )
    assert r.verdict == "good"
    assert set(r.matched) == {"水楊酸", "菸鹼醯胺"}
    assert r.missing == ()
    assert r.conflicts == ()


def test_alternatives_do_not_count_as_missing():
    """A 次選 is something to switch to, not something the user lacks."""
    r = evaluate_product("Aqua, Azelaic Acid 10%", attributes={"acne": 2})
    assert r.verdict == "good"
    assert r.missing == ("水楊酸",)  # the primary, not the alternative


def test_recognised_but_useless_is_caution_not_missing_info():
    r = evaluate_product("Aqua, Glycerin, Tocopherol", attributes={"acne": 3})
    assert r.verdict == "caution"
    assert r.matched == ()


def test_nothing_recognised_is_insufficient_info():
    r = evaluate_product("Fooium Baride, Quxxane", attributes={"acne": 2})
    assert r.verdict == "insufficient_info"
    assert r.recognised == ()


def test_unknown_ingredients_are_reported_verbatim_and_do_not_cap_the_verdict():
    """A real INCI list has 20-40 entries; the seed is 31.

    Unknowns are informational — letting them force `caution` would make `good`
    unreachable and tell the user nothing.
    """
    r = evaluate_product(
        "Aqua, Salicylic Acid 2%, Niacinamide, SomeTradeNameium",
        attributes={"acne": 2, "oiliness": 2},
    )
    assert r.verdict == "good"
    assert r.unknown == ("SomeTradeNameium",)


def test_bases_do_not_participate_in_coverage():
    """Water / preservatives must be recognised but never "matched"."""
    r = evaluate_product("Aqua, Phenoxyethanol, Parfum", attributes={"acne": 2})
    assert "水" not in r.matched
    assert "苯氧乙醇" not in r.matched
    assert r.verdict == "insufficient_info"  # nothing efficacy-bearing recognised


# ---------------------------------------------------------------------------
# Hard stop (stays narrow)
# ---------------------------------------------------------------------------


def test_prescription_ingredient_avoids_and_escalates():
    r = evaluate_product("Aqua, Isotretinoin", attributes={"acne": 2})
    assert r.verdict == "avoid"
    assert r.escalate is True
    assert any(c.kind == "prescription" for c in r.conflicts)


def test_avoid_wins_over_coverage():
    """No coverage talk next to a prescription ingredient."""
    r = evaluate_product("Aqua, Salicylic Acid 2%, Isotretinoin", attributes={"acne": 2})
    assert r.verdict == "avoid"
    assert r.matched == ()


def test_otc_actives_are_not_hard_blocked():
    for text in ("Aqua, Adapalene 0.1%", "Aqua, Hydrocortisone 1%"):
        r = evaluate_product(text, attributes={"acne": 2})
        assert r.verdict != "avoid"


# ---------------------------------------------------------------------------
# Conflicts
# ---------------------------------------------------------------------------


def test_duplicate_active_against_products_already_in_use():
    r = evaluate_product(
        "Aqua, Salicylic Acid 2%",
        attributes={"acne": 2},
        in_use={"salicylic_acid": "水楊酸 toner"},
    )
    assert r.verdict == "caution"
    assert any(c.kind == "duplicate_active" for c in r.conflicts)


def test_dry_skin_plus_acid_is_a_profile_conflict():
    r = evaluate_product("Aqua, Glycolic Acid 10%", attributes={"dryness": 2})
    assert r.verdict == "caution"
    assert any(c.kind == "profile_conflict" for c in r.conflicts)


def test_pigmentation_goal_unmet_is_a_profile_conflict():
    r = evaluate_product("Aqua, Glycerin", attributes={"acne": 2}, pigmentation=True)
    assert any("色素" in c.text for c in r.conflicts)


def test_pigmentation_goal_met_is_good():
    r = evaluate_product("Aqua, Alpha-Arbutin", pigmentation=True)
    assert r.verdict == "good"


# ---------------------------------------------------------------------------
# actives_in_name — how "already in use" is detected today
# ---------------------------------------------------------------------------


def test_actives_in_name_finds_the_active():
    assert actives_in_name("水楊酸 toner") == {"salicylic_acid"}
    assert actives_in_name("Niacinamide 10% serum") == {"niacinamide"}


def test_actives_in_name_returns_nothing_rather_than_guessing():
    assert actives_in_name("神奇精華") == set()
    assert actives_in_name("") == set()


# ---------------------------------------------------------------------------
# The narrative is a second user-facing surface — guard it
# ---------------------------------------------------------------------------


def test_narrative_with_medical_advice_is_replaced():
    r = evaluate_product("Aqua, Salicylic Acid 2%", attributes={"acne": 2})
    assert guard_narrative("你可以每日口服抗生素 50mg。", r) == ESCALATION_MESSAGE


def test_clean_narrative_passes_through():
    r = evaluate_product("Aqua, Salicylic Acid 2%", attributes={"acne": 2})
    text = "呢支有水楊酸 2%，啱你需要嘅方向；一星期 2–3 次就夠。"
    assert guard_narrative(text, r) == text


def test_package_size_in_narrative_is_not_escalated():
    """「30g 裝」is a size, not a dose — the product feature says this constantly."""
    r = evaluate_product("Aqua, Salicylic Acid 2%", attributes={"acne": 2})
    text = "呢支 30g，可以用到兩個月。"
    assert guard_narrative(text, r) == text
