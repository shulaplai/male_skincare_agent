"""Ingredient parsing / normalisation tests.

The dictionary is a seed (see the module docstring) — these tests pin the
*behaviour* (fold names, keep order, never guess), not the dictionary's size.

One test goes further and checks every citation against the real corpus. A
citation that cannot be found is worse than no citation: it looks like evidence.
That test reads `data/skincoach.db`, which does not exist in CI, so it skips
there and runs locally.
"""
import sqlite3
from pathlib import Path

import pytest

from app.agent.ingredients import (
    INGREDIENTS,
    NON_CLAIM_ROLES,
    canonical,
    display_zh,
    is_base,
    is_recognised,
    parse_ingredients,
    prescription_block,
    role_of,
)


# ---------------------------------------------------------------------------
# Name folding — the thing coverage matching depends on
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    ["Salicylic Acid", "salicylic acid", "SALICYLIC ACID", "水楊酸", "BHA", "beta hydroxy acid"],
)
def test_same_ingredient_folds_to_one_key(name):
    assert canonical(name) == "salicylic_acid"


def test_punctuation_and_spacing_do_not_matter():
    assert canonical("Alpha-Arbutin") == canonical("alpha arbutin") == "alpha_arbutin"
    assert canonical("Alcohol Denat.") == "alcohol_denat"


def test_chinese_survives_normalisation():
    assert canonical("神經醯胺") == "ceramide_np"
    assert canonical("玻尿酸") == "hyaluronic_acid"
    assert canonical("傳明酸") == "tranexamic_acid"


def test_unknown_returns_none_not_a_guess():
    assert canonical("TradeNameium X-9") is None
    assert canonical("") is None
    assert is_recognised("TradeNameium X-9") is False


# ---------------------------------------------------------------------------
# display_zh (D5)
# ---------------------------------------------------------------------------


def test_display_zh_translates_known_names():
    assert display_zh("Salicylic Acid") == "水楊酸"
    assert display_zh("azelaic acid") == "杜鵰花酸"


def test_display_zh_never_invents_a_translation():
    """An unrecognised name must come back verbatim, not translated."""
    assert display_zh("TradeNameium X-9") == "TradeNameium X-9"


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------


def test_bases_are_recognised_but_are_not_claim_roles():
    """Bases must be recognised (or every product reports a noisy unknown list)
    but must not enter coverage matching — a product is never 'missing' a
    preservative."""
    assert is_recognised("Water") is True
    assert is_base("Water") is True
    assert is_base("Phenoxyethanol") is True
    assert role_of("Phenoxyethanol") == "preservative"


def test_actives_are_not_bases():
    for name in ("Salicylic Acid", "Niacinamide", "Centella Asiatica Extract", "Glycerin"):
        assert is_base(name) is False


# ---------------------------------------------------------------------------
# Parsing real INCI text
# ---------------------------------------------------------------------------


def test_parse_realistic_inci_list():
    text = (
        "Aqua, Salicylic Acid 2%, Niacinamide, Glycerin, "
        "Sodium Hyaluronate, Phenoxyethanol, Parfum"
    )
    parsed = parse_ingredients(text)

    assert [p.key for p in parsed] == [
        "aqua",
        "salicylic_acid",
        "niacinamide",
        "glycerin",
        "hyaluronic_acid",
        "phenoxyethanol",
        "parfum",
    ]
    assert all(p.recognised for p in parsed)
    # Order preserved: INCI is descending by concentration.
    assert parsed[0].key == "aqua"
    # Percentage extracted and removed from the name.
    sal = parsed[1]
    assert sal.percent == 2.0
    assert sal.zh == "水楊酸"


def test_parse_keeps_comma_inside_a_real_ingredient_name():
    """`1,2-Hexanediol` is one ingredient; a bare comma-split would break it."""
    parsed = parse_ingredients("Aqua, 1,2-Hexanediol, Glycerin")
    raws = [p.raw for p in parsed]
    assert raws[1] == "1,2-Hexanediol"


# ---------------------------------------------------------------------------
# The user's own label must not glue onto the first ingredient
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "成份：Aqua, Glycerin, Niacinamide",  # the case the original fix covered
        "成份係 Aqua, Glycerin, Niacinamide",  # measured: natural Cantonese, no colon
        "成分包括 Aqua, Glycerin, Niacinamide",
        "成份如下：Aqua, Glycerin, Niacinamide",
        "全成分有 Aqua, Glycerin, Niacinamide",
        "INCI Aqua, Glycerin, Niacinamide",
        "Ingredients are: Aqua, Glycerin, Niacinamide",
    ],
)
def test_list_label_never_becomes_part_of_the_first_ingredient(text):
    """「成份係 Aqua, …」 used to parse the first token as `係 Aqua`.

    Measured on the real chat path: `unknown` came back as `['係 Aqua']`, so the coach
    told the user 「成份表第一個係「Aqua」（水），係我程式未認得嘅寫法」 — reporting that it
    cannot recognise *water*. The label (and the connective particle after it) belongs to
    the user's sentence, not to the INCI list.
    """
    parsed = parse_ingredients(text)
    assert parsed[0].raw == "Aqua", (text, parsed[0].raw)
    assert parsed[0].key == "aqua"


def test_list_label_marker_only_does_not_eat_an_ingredient():
    """A Latin INCI name is never mistaken for the connective word."""
    parsed = parse_ingredients("Aqua, Isopropyl Myristate, Glycerin")
    assert [p.raw for p in parsed] == ["Aqua", "Isopropyl Myristate", "Glycerin"]


def test_parse_handles_chinese_and_mixed_input():
    parsed = parse_ingredients("水、水楊酸 2%、菸鹼醯胺、TradeNameium X-9")
    assert parsed[0].key == "aqua"
    assert parsed[1].key == "salicylic_acid"
    assert parsed[2].key == "niacinamide"
    assert parsed[3].key is None
    assert parsed[3].recognised is False


def test_parse_handles_newlines_and_semicolons():
    parsed = parse_ingredients("Aqua\nGlycerin; Niacinamide")
    assert [p.key for p in parsed] == ["aqua", "glycerin", "niacinamide"]


def test_parse_dedupes_and_ignores_empty_segments():
    parsed = parse_ingredients("Aqua,, Water, ; ,Glycerin")
    assert [p.key for p in parsed] == ["aqua", "glycerin"]


def test_parse_empty_input():
    assert parse_ingredients("") == []


# ---------------------------------------------------------------------------
# Hard block list
# ---------------------------------------------------------------------------


def test_prescription_block_matches_aliases():
    assert prescription_block("Isotretinoin") == "isotretinoin"
    assert prescription_block("Accutane") == "isotretinoin"
    assert prescription_block("異維A酸") == "isotretinoin"


def test_prescription_block_leaves_otc_actives_alone():
    """Deliberately narrow: these are OTC somewhere, so they are not hard-blocked."""
    assert prescription_block("Salicylic Acid") is None
    assert prescription_block("Adapalene") is None
    assert prescription_block("Hydrocortisone") is None


# ---------------------------------------------------------------------------
# Seed integrity
# ---------------------------------------------------------------------------


def test_seed_keys_are_unique():
    keys = [i.key for i in INGREDIENTS]
    assert len(keys) == len(set(keys))


def test_claims_are_citable_and_formula_roles_are_not():
    """The audit's bar: a claim must be citable, a role label need not be.

    `active` must carry a citation. Formula-only roles must carry none — a
    citation there would imply a claim nobody is making. `emollient` /
    `humectant` / `barrier` are intentionally unconstrained: ceramide is cited by
    the skin-barrier page, dimethicone is not.
    """
    for i in INGREDIENTS:
        if i.role == "active":
            assert i.corpus, f"{i.key} claims efficacy with nothing to cite"
        if i.role in NON_CLAIM_ROLES:
            assert not i.corpus, f"{i.key} is a formula-only role but carries a citation"


def test_seed_size_is_flagged_as_below_target():
    """Guard against the seed quietly being mistaken for the finished list.

    Target is >=200 from IECIC (D4). This asserts we are still nowhere near it,
    so the number in the docs cannot silently drift out of sync with the code.
    """
    assert len(INGREDIENTS) < 200


# ---------------------------------------------------------------------------
# Citations must be real
# ---------------------------------------------------------------------------

_REAL_DB = Path(__file__).resolve().parents[1] / "data" / "skincoach.db"


@pytest.mark.skipif(
    not _REAL_DB.exists(),
    reason="real corpus DB not present (CI has no data/ dir) — local-only check",
)
def test_every_citation_resolves_in_the_real_corpus():
    """A citation that cannot be found is worse than no citation: it looks like evidence.

    Skips in CI. Run locally (`cd backend && ./.venv/bin/python -m pytest
    tests/test_ingredients.py`) against the ingested corpus.
    """
    conn = sqlite3.connect(f"file:{_REAL_DB}?mode=ro", uri=True)
    try:
        checked = 0
        for i in INGREDIENTS:
            for cite in i.corpus:
                source, _, title = cite.partition(" :: ")
                assert source and title, f"{i.key}: malformed citation {cite!r}"
                # Same whitespace tolerance as tests/test_guide.py: corpus titles
                # contain non-breaking spaces (U+00A0).
                n = conn.execute(
                    "select count(*) from chunks where source = ? "
                    "and trim(replace(replace(title, char(160), ' '), '  ', ' ')) = ?",
                    (source, " ".join(title.split())),
                ).fetchone()[0]
                assert n > 0, f"{i.key}: citation not found in corpus → {cite!r}"
                checked += 1
        assert checked >= 10, "citation check did not actually run"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# The label a user types in front of the list is not an ingredient
# ---------------------------------------------------------------------------


def test_a_leading_label_is_not_part_of_the_first_ingredient():
    """Measured on the real path: 「成份：Aqua, …」 made the coach say it did not
    recognise water.

    The label glued onto the first token, so `成份：Aqua` was unknown and `Aqua` never
    reached the dictionary. The label is the user's own heading, not the list.
    """
    from app.agent.ingredients import strip_list_marker

    assert strip_list_marker("成份：Aqua, Glycerin") == "Aqua, Glycerin"
    assert strip_list_marker("成分: Aqua, Glycerin") == "Aqua, Glycerin"
    assert strip_list_marker("INCI: Aqua, Glycerin") == "Aqua, Glycerin"
    assert strip_list_marker("Ingredients: Aqua") == "Aqua"
    # No label: untouched, and a name that merely contains a marker word survives.
    assert strip_list_marker("Aqua, Glycerin") == "Aqua, Glycerin"

    parsed = parse_ingredients("成份：Aqua, Glycerin, Niacinamide")
    assert [p.key for p in parsed] == ["aqua", "glycerin", "niacinamide"]
    assert parsed[0].raw == "Aqua", "the label must not survive onto the raw name"


@pytest.mark.parametrize("spelling", ["Aqua", "water", "Water (Aqua)", "Aqua (Water)", "水"])
def test_real_label_spellings_of_water_are_recognised(spelling):
    """Both bracketed INCI spellings appear on ordinary labels, and neither was known."""
    assert canonical(spelling) == "aqua"
