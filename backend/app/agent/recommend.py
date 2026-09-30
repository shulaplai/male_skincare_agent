"""Active-ingredient recommendation table (deterministic).

Pure functions — no DB, no DOM (doctrine #6), so the eval harness and tests can
import this directly.

## This is the ONE source of truth for "what should this user look for"

Two consumers read it and must never drift apart:

* `product_eval.evaluate_product` — coverage matching for a product the user pasted
  ("does it contain what we recommended?");
* the in-app guide's 「應該用咩產品」 section — the human-readable version.

That is why the table lives in code and not in prose: a guide that could disagree
with what the agent recommends is worse than no guide.

## Provenance

Every row cites its corpus basis in `docs/product-eval-plan.md` §3.2a, which was
verified against the real `chunks` table. The rules are general cosmetic
knowledge drawn from that corpus — **not clinical guidance** — so every surfaced
answer carries `guardrails.DEFAULT_DISCLAIMER`.

## Two tiers (user decision D1/D6)

Each trigger yields a **主選** (primary: the active with the most evidence) and a
**次選** (alternative: what to switch to in a specific situation, e.g. when the
user is also dry or red). The user picks; the app does not name brands.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .attributes import ATTRIBUTE_LABELS
from .ingredients import display_zh, is_base, mentioned_keys

# ---------------------------------------------------------------------------
# Pigmentation: a real dimension the 6-attribute schema cannot express (D7)
# ---------------------------------------------------------------------------

# Multi-character hints only. A bare 「印」 is NOT a hint on purpose — 印尼 /
# 打印 / 印象 would all false-positive, and a false pigmentation signal would
# route the user to depigmenting actives they never asked about.
#
# Known limitation: this is a keyword scan over the user's own words. It misses
# phrasings nobody listed (「下巴黑咗」) and it cannot be tracked over time the way
# a real attribute can (see docs/product-eval-plan.md §3.2a — a 7th attribute
# would be the thorough fix, at the cost of a versioned schema migration).
PIGMENTATION_HINTS: tuple[str, ...] = (
    "暗瘡印",
    "瘡印",
    "痘印",
    "留印",
    "留低印",
    "有色素",
    "色素",
    "沉澱",
    "黑印",
    "啡印",
    "去印",
    "淡印",
    "印淡",
    "印仔",
    "melasma",
    "hyperpigmentation",
    "pih",
)


# 「留…印」 with up to a few filler characters between, e.g. 「留咗好多印」.
# `(?!意)` keeps 留意 out — 「留意打印機」 must not read as pigmentation.
_PIGMENTATION_RE = re.compile(r"留(?!意)[^，。！？,.!?\n]{0,6}印")


def mentions_pigmentation(text: str) -> bool:
    """True if the user's own words mention marks / dark spots / pigmentation."""
    if not text:
        return False
    low = text.lower()
    return any(h in low for h in PIGMENTATION_HINTS) or _PIGMENTATION_RE.search(low) is not None


# ---------------------------------------------------------------------------
# The table
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Rule:
    """One trigger → primary + alternative active."""

    trigger: str  # attribute key, or "pigmentation"
    # (ingredient key, zh reason) — primary first.
    primary: tuple[str, str]
    alternative: tuple[str, str]


RULES: tuple[Rule, ...] = (
    Rule(
        trigger="acne",
        primary=("salicylic_acid", "針對毛孔阻塞，減少粉刺同新瘡"),
        alternative=("azelaic_acid", "同時有泛紅或者玫瑰痤瘡傾向時較溫和"),
    ),
    Rule(
        trigger="oiliness",
        primary=("niacinamide", "調節皮脂分泌，唔似刺激嘅控油成份"),
        alternative=("salicylic_acid", "油光同時有黑頭粉刺時一齊處理"),
    ),
    Rule(
        trigger="dryness",
        primary=("ceramide_np", "修復皮膚屏障，由根源減少水份流失"),
        alternative=("hyaluronic_acid", "想即時補水感就揀呢個"),
    ),
    Rule(
        trigger="redness",
        primary=("azelaic_acid", "抗炎，對泛紅同玫瑰痤瘡傾向最有證據"),
        alternative=("panthenol", "想溫和舒緩、唔想用酸就揀呢個"),
    ),
    Rule(
        trigger="pores",
        primary=("niacinamide", "改善毛孔外觀，唔會令皮膚變薄"),
        alternative=("retinol", "低濃度起步、隔日一次，要配合防曬"),
    ),
    Rule(
        trigger="texture",
        primary=("glycolic_acid", "溫和代謝角質，改善粗糙"),
        alternative=("urea", "想同時保濕就揀呢個，刺激性較低"),
    ),
    Rule(
        trigger="pigmentation",
        primary=("alpha_arbutin", "抑制黑色素，針對暗瘡印同色素沉澱"),
        alternative=("tranexamic_acid", "色素較頑固或者同時有荷斑時考慮"),
    ),
)

# Severity at/above which a trigger fires. Matches the schema's own convention
# (`attributes.direction_for`: >=2 is a problem).
TRIGGER_FLOOR = 2


@dataclass(frozen=True)
class ActiveSuggestion:
    """One recommended active, already de-duplicated across triggers."""

    key: str
    zh: str
    tier: str  # "primary" | "alternative"
    reasons: tuple[str, ...]  # zh, why — may come from several triggers

    @property
    def is_primary(self) -> bool:
        return self.tier == "primary"


@dataclass(frozen=True)
class Recommendation:
    suggestions: tuple[ActiveSuggestion, ...]
    triggers: tuple[str, ...]  # attribute keys + "pigmentation" that fired
    warnings: tuple[str, ...]  # zh, deterministic conflict notes

    @property
    def primaries(self) -> tuple[ActiveSuggestion, ...]:
        return tuple(s for s in self.suggestions if s.is_primary)


def _merge(
    bucket: dict[str, dict],
    key: str,
    tier: str,
    reason: str,
) -> None:
    entry = bucket.setdefault(key, {"primary": False, "reasons": []})
    if tier == "primary":
        entry["primary"] = True
    if reason not in entry["reasons"]:
        entry["reasons"].append(reason)


def recommend_actives(
    attributes: dict[str, int] | None = None,
    *,
    pigmentation: bool = False,
    in_use: dict[str, str] | None = None,
) -> Recommendation:
    """Deterministic actives recommendation for a user's current profile.

    `attributes` is `{attribute key: 0-3 severity}` (from `Entry.attributes`).
    `in_use` maps ingredient key → the user's own product name, used to warn about
    stacking the same active twice.
    """
    attributes = attributes or {}
    in_use = in_use or {}
    fired: list[str] = []
    warnings: list[str] = []
    bucket: dict[str, dict] = {}

    for rule in RULES:
        if rule.trigger == "pigmentation":
            fires = pigmentation
        else:
            sev = attributes.get(rule.trigger)
            fires = sev is not None and sev >= TRIGGER_FLOOR
        if not fires:
            continue

        fired.append(rule.trigger)
        where = "色素／暗瘡印" if rule.trigger == "pigmentation" else ATTRIBUTE_LABELS.get(rule.trigger, rule.trigger)
        _merge(bucket, rule.primary[0], "primary", f"{where}：{rule.primary[1]}")
        _merge(bucket, rule.alternative[0], "alternative", f"{where}：{rule.alternative[1]}")

    # --- deterministic conflicts -------------------------------------------
    acne = attributes.get("acne", 0)
    dryness = attributes.get("dryness", 0)
    if acne >= TRIGGER_FLOOR and dryness >= TRIGGER_FLOOR:
        warnings.append(
            "你又爆瘡又乾燥：唔好同時上高濃度酸同去角質。分早晚，或者隔日輪流，"
            "並且一定要補返保濕。"
        )
    if any(t in ("glycolic_acid",) for t in bucket) and acne >= TRIGGER_FLOOR:
        warnings.append("果酸同抗痘成份同日用會太刺激，建議分開早晚。")

    for key, product_name in in_use.items():
        if key in bucket:
            warnings.append(
                f"你已經用緊「{product_name}」（含{display_zh(key)}），"
                f"唔需要再買一支同類嘅 —— 疊加會過度去角質或者刺激。"
            )

    suggestions: list[ActiveSuggestion] = []
    for key, info in bucket.items():
        # An active that is primary for any trigger stays primary.
        suggestions.append(
            ActiveSuggestion(
                key=key,
                zh=display_zh(key),
                tier="primary" if info["primary"] else "alternative",
                reasons=tuple(info["reasons"]),
            )
        )
    # Primary first, then alphabetical by key for stable output.
    suggestions.sort(key=lambda s: (not s.is_primary, s.key))

    return Recommendation(
        suggestions=tuple(suggestions),
        triggers=tuple(fired),
        warnings=tuple(warnings),
    )


def actives_in_name(name: str) -> set[str]:
    """Best-effort actives from a product *name* the user typed.

    `Product.ingredients` is never populated (see docs/product-eval-plan.md §2.2),
    so until the user pastes a real INCI list this is how "you already use a
    salicylic acid toner" is detected. A name that matches nothing returns an
    empty set rather than a guess.
    """
    return {k for k in mentioned_keys(name) if not is_base(k)}
