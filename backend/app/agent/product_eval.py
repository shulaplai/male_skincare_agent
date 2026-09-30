"""Evaluate a product the user pasted (deterministic core).

Pure functions — no DB, no DOM (doctrine #6).

## Design (see docs/product-eval-plan.md §3.3–§3.5)

The core question is **coverage matching**, not a prescription classification:

    user's pasted ingredient list  ∩  the actives we recommended for them

A "which ingredients are prescription?" list would be the wrong axis — the corpus
itself documents azelaic acid as freely purchasable at <=10% and prescription at
15%, and differently per jurisdiction. So instead:

* ingredients we recognise → participate in coverage matching;
* ingredients we do NOT recognise → reported as `unknown[]` and **never guessed
  at** (no invented translation, no invented benefit);
* the tiny `PRESCRIPTION_ONLY` list is only a hard stop, not the main judgement.

`unknown[]` is **informational, not a conflict**. A real INCI list has 20–40
entries and the seed dictionary is currently 31 (D4 pending), so almost every
product has something we do not recognise — letting that cap the verdict at
`caution` would make `good` unreachable and tell the user nothing. Unknown names
are reported verbatim instead, and if we recognise *no* efficacy ingredient at all
the verdict is `insufficient_info`.

**Nothing here writes to the database.** A product *evaluation* must never create
an `Entry`: `Entry` is the daily skin state and change detection / timeline /
anchors all diff it, so a question about a product would silently become a day of
skin data. The endpoint returns this value and persists nothing (v1).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .guardrails import (
    DEFAULT_DISCLAIMER,
    ESCALATION_MESSAGE,
    contains_medical_advice,
)
from .ingredients import (
    ParsedIngredient,
    canonical,
    display_zh,
    is_base,
    parse_ingredients,
    prescription_block,
)
from .recommend import Recommendation, recommend_actives

Verdict = Literal["good", "caution", "avoid", "insufficient_info"]


@dataclass(frozen=True)
class Conflict:
    kind: str  # prescription | duplicate_active | stacking_risk | profile_conflict | unknown_ingredients
    text: str  # zh, user-facing


@dataclass(frozen=True)
class ProductEvaluation:
    verdict: Verdict
    # zh names of actives we recognise in the product (bases excluded).
    recognised: tuple[str, ...]
    # raw strings we could not identify — surfaced verbatim, never translated.
    unknown: tuple[str, ...]
    # recommended actives this product DOES contain (coverage).
    matched: tuple[str, ...]
    # recommended actives it does NOT contain.
    missing: tuple[str, ...]
    conflicts: tuple[Conflict, ...]
    recommendation: Recommendation
    escalate: bool
    disclaimer: str


def _efficacy_keys(parsed: list[ParsedIngredient]) -> list[str]:
    """Recognised ingredient keys that carry a claim (bases excluded)."""
    out: list[str] = []
    for p in parsed:
        if p.key and not is_base(p.key) and p.key not in out:
            out.append(p.key)
    return out


def evaluate_product(
    ingredients_text: str,
    *,
    attributes: dict[str, int] | None = None,
    pigmentation: bool = False,
    in_use: dict[str, str] | None = None,
) -> ProductEvaluation:
    """Score a pasted product against the user's profile. Writes nothing.

    `ingredients_text` is what the user pasted (INCI list, Chinese, or both).
    `in_use` maps ingredient key → the user's own product name, for the
    "you already use this active" check.
    """
    in_use = in_use or {}
    parsed = parse_ingredients(ingredients_text)
    keys = _efficacy_keys(parsed)
    unknown = tuple(p.raw for p in parsed if not p.recognised)

    recommendation = recommend_actives(
        attributes, pigmentation=pigmentation, in_use=in_use
    )
    recommended_keys = {s.key for s in recommendation.suggestions}
    # `missing` counts PRIMARIES only: an alternative is something the user may
    # switch to, so calling it "missing" would tell them they lack something they
    # never needed. Alternatives still count as a match when present.
    primary_keys = {s.key for s in recommendation.primaries}
    matched = tuple(display_zh(k) for k in keys if k in recommended_keys)
    missing = tuple(display_zh(k) for k in sorted(primary_keys - set(keys)))
    recognised = tuple(display_zh(k) for k in keys)

    conflicts: list[Conflict] = []

    # --- hard stop: essentially-always-prescription names --------------------
    blocked = [b for b in (prescription_block(k) for k in keys + [p.raw for p in parsed]) if b]
    if blocked:
        uniq = sorted(set(blocked))
        conflicts.append(
            Conflict(
                kind="prescription",
                text=(
                    "呢個產品含處方藥成份（" + "、".join(uniq) + "），我唔可以評論佢適唔適合你。"
                    "呢類成份要由醫生評估同處方。"
                ),
            )
        )

    # --- stacking: the user already uses this active -------------------------
    for key, product_name in in_use.items():
        if key in keys:
            conflicts.append(
                Conflict(
                    kind="duplicate_active",
                    text=(
                        f"你已經用緊「{product_name}」（含{display_zh(key)}），"
                        f"呢支都有 {display_zh(key)} —— 兩支一齊用會過度去角質或者刺激，"
                        f"揀一支就夠。"
                    ),
                )
            )

    # --- profile conflicts --------------------------------------------------
    dryness = (attributes or {}).get("dryness", 0)
    acids = {"salicylic_acid", "glycolic_acid", "lactic_acid"}
    if dryness >= 2 and acids & set(keys):
        conflicts.append(
            Conflict(
                kind="profile_conflict",
                text=(
                    "你而家乾燥分數偏高，呢支有去角質酸。要用就一星期 2–3 次、"
                    "之後補返保濕，唔好每日用。"
                ),
            )
        )
    if pigmentation and not ({"alpha_arbutin", "tranexamic_acid", "azelaic_acid"} & set(keys)):
        conflicts.append(
            Conflict(
                kind="profile_conflict",
                text="你想處理色素／暗瘡印，但呢支冇對應成份（熊果素／傳明酸／杜鵰花酸）。",
            )
        )

    # --- verdict ------------------------------------------------------------
    if blocked:
        # Safety dominates: no coverage talk next to a prescription ingredient.
        verdict: Verdict = "avoid"
    elif not keys:
        verdict = "insufficient_info"
    elif conflicts:
        verdict = "caution"
    elif not matched:
        # We understood the product fine — it just contains nothing this user
        # needs. That is a real answer, not missing information.
        verdict = "caution"
    else:
        verdict = "good"

    if blocked:
        # Suppress coverage entirely. Showing `matched: ['水楊酸']` next to an
        # `avoid` verdict reads as "mostly fine, just one bad ingredient" — which
        # is not a message this app should ever produce about a prescription drug.
        #
        # `recognised` goes too, and for the same reason: it is rendered to the reader
        # ("產品嘅其他認得嘅功效成份") and a row of humectants beside `avoid` reads as a
        # feature list. Found by a chat test whose fixture pasted tretinoin and got back
        # `recognised: ('甘油', '泛醇', '尿囊素')`.
        #
        # `unknown` deliberately **stays**: it is the honest "we could not classify this"
        # statement, and it is where the hard-stop name itself is reported verbatim.
        matched = ()
        missing = ()
        recognised = ()

    return ProductEvaluation(
        verdict=verdict,
        recognised=recognised,
        unknown=unknown,
        matched=matched,
        missing=missing,
        conflicts=tuple(conflicts),
        recommendation=recommendation,
        escalate=bool(blocked),
        disclaimer=DEFAULT_DISCLAIMER,
    )


def escalation_text() -> str:
    """Reused when the narrative must be replaced (see `guardrails.ESCALATION_MESSAGE`)."""
    return ESCALATION_MESSAGE


def guard_narrative(narrative: str, evaluation: ProductEvaluation) -> str:
    """Apply the medical guardrail to the LLM's narrative for this feature.

    The product-evaluation narrative is a SECOND free-text surface the user reads,
    so it needs the same protection `apply_guardrails` gives `Advice.reply` —
    otherwise this feature re-introduces the exact hole that was just closed.
    """
    if not narrative:
        return narrative
    if contains_medical_advice(narrative):
        return ESCALATION_MESSAGE
    return narrative

__all__ = [
    "Conflict",
    "ProductEvaluation",
    "Verdict",
    "canonical",
    "evaluate_product",
    "escalation_text",
    "guard_narrative",
]
