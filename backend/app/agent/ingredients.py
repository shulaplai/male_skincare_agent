"""Ingredient normalisation and a small, sourced ingredient dictionary.

Pure functions only — no DB, no DOM (doctrine #6: `prompts.py` / `attributes.py` /
`memory.py` / this module must be importable directly by the eval harness).

## Why normalisation is load-bearing, not cosmetic

"Has this product got the ingredient we recommended?" only has a defensible answer
if `Salicylic Acid`, `水楊酸`, `BHA` and `beta hydroxy acid` all collapse to one
key. The same goes for parsing what the user pastes: it may be English INCI,
Chinese, a trade name, or a mix.

## ⚠️ D4 status: this is a SEED, not the target

The agreed target is **>=200 ingredients sourced from 中國《已使用化妝品原料目錄》
(IECIC)**. That file is not in this repo, and hand-writing 200 names — especially
their official Chinese names — would be inventing facts, which is the exact failure
mode this project's own audit was built to catch. So:

* every **efficacy-carrying** entry below carries a `corpus` provenance string that
  can be checked against the real DB (`source :: title`);
* **ubiquitous base/role ingredients** (water, preservatives, thickeners) carry
  `corpus=()` and are labelled `role` — no efficacy claim is made about them, so
  there is nothing to cite. Without them every pasted product would report a noisy
  `unknown[]` and the feature would look broken;
* `PRESCRIPTION_ONLY` is deliberately **incomplete** — see its comment.

Expanding this to IECIC is a data task, not a coding task. Until then, anything not
recognised is honestly reported as unknown rather than guessed at.
"""
import re
from dataclasses import dataclass
from typing import Literal

Role = Literal[
    "active",       # does something to the skin; eligible for coverage matching
    "humectant",
    "emollient",
    "barrier",
    "solvent",
    "preservative",
    "surfactant",
    "uv_filter",
    "ph_adjuster",
    "chelator",
    "thickener",
    "antioxidant",
    "fragrance",
]

# Roles that only describe what an ingredient *is* in the formula. Nothing is
# claimed about them, so they need no citation and are excluded from coverage
# matching (a product is never "missing" a preservative).
#
# Deliberately NOT including "emollient" / "humectant" / "barrier": those sit
# between the two cases — ceramide is cited by the skin-barrier page while
# dimethicone is not — so which of them carry a claim is decided by the
# recommendation table (docs/product-eval-plan.md §3.2a), not by a role label.
NON_CLAIM_ROLES: frozenset[str] = frozenset(
    {
        "solvent",
        "preservative",
        "surfactant",
        "uv_filter",
        "ph_adjuster",
        "chelator",
        "thickener",
        "antioxidant",
        "fragrance",
    }
)


@dataclass(frozen=True)
class Ingredient:
    key: str
    inci: str
    zh: str
    role: Role
    aliases: tuple[str, ...] = ()
    # "source :: title" strings, checkable against the live `chunks` table.
    corpus: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Seed dictionary
# ---------------------------------------------------------------------------

INGREDIENTS: tuple[Ingredient, ...] = (
    # --- actives with a corpus citation -------------------------------------
    Ingredient(
        key="salicylic_acid",
        inci="Salicylic Acid",
        zh="水楊酸",
        role="active",
        aliases=("BHA", "beta hydroxy acid", "beta hydroxy"),
        corpus=("incidecoder.com :: Salicylic Acid", "dermnetnz.org :: Acne"),
    ),
    Ingredient(
        key="azelaic_acid",
        inci="Azelaic Acid",
        zh="杜鵰花酸",
        role="active",
        aliases=("壬二酸", "nonanedioic acid"),
        # The concentration/jurisdiction split that killed the "prescription list"
        # design lives in this very page (see docs/product-eval-plan.md §3.5).
        corpus=("incidecoder.com :: Azelaic Acid",),
    ),
    Ingredient(
        key="niacinamide",
        inci="Niacinamide",
        zh="菸鹼醯胺",
        role="active",
        aliases=("烟酰胺", "nicotinamide", "vitamin B3", "vitamin b3"),
        corpus=("incidecoder.com :: Niacinamide",),
    ),
    Ingredient(
        key="retinol",
        inci="Retinol",
        zh="視黃醇",
        role="active",
        aliases=("A醇", "vitamin A", "vitamin a"),
        corpus=("incidecoder.com :: Retinol",),
    ),
    Ingredient(
        key="alpha_arbutin",
        inci="Alpha-Arbutin",
        zh="α-熊果素",
        role="active",
        aliases=("alpha arbutin", "arbutin", "熊果素"),
        corpus=("incidecoder.com :: Alpha-Arbutin",),
    ),
    Ingredient(
        key="tranexamic_acid",
        inci="Tranexamic Acid",
        zh="傳明酸",
        role="active",
        aliases=("氨甲環酸",),
        corpus=("PMC11439988 :: Tranexamic Acid for the Treatment of Hyperpigmentation and Telangiectatic Disorders Other Than Melasma: An Update.",),
    ),
    Ingredient(
        key="glycolic_acid",
        inci="Glycolic Acid",
        zh="甘醇酸",
        role="active",
        aliases=("AHA", "alpha hydroxy acid"),
        corpus=("PMC10988741 :: Overview of popular cosmeceuticals in dermatology.",),
    ),
    Ingredient(
        key="lactic_acid",
        inci="Lactic Acid",
        zh="乳酸",
        role="active",
        aliases=(),
        corpus=("PMC10988741 :: Overview of popular cosmeceuticals in dermatology.",),
    ),
    Ingredient(
        key="centella_asiatica",
        inci="Centella Asiatica Extract",
        zh="積雪草萃取",
        role="active",
        aliases=("centella", "cica", "madecassoside", "積雪草"),
        corpus=("PMC12936241 :: Egyptian National Consensus on Dermocosmetic Ingredient Selection Across Common Dermatology Scenarios: A RAND/UCLA Appropriateness Study.",),
    ),
    Ingredient(
        key="panthenol",
        inci="Panthenol",
        zh="泛醇",
        role="active",
        aliases=("vitamin B5", "vitamin b5", "dexpanthenol", "維生素B5", "d-panthenol"),
        corpus=("incidecoder.com :: Panthenol",),
    ),
    Ingredient(
        key="urea",
        inci="Urea",
        zh="尿素",
        role="active",
        aliases=("carbamide",),
        corpus=("PMC10988741 :: Overview of popular cosmeceuticals in dermatology.",),
    ),
    # --- barrier / humectant ------------------------------------------------
    Ingredient(
        key="ceramide_np",
        inci="Ceramide NP",
        zh="神經醯胺 NP",
        role="barrier",
        aliases=("ceramide", "神經醯胺", "神经酰胺"),
        corpus=("dermnetnz.org :: Skin barrier function",),
    ),
    Ingredient(
        key="hyaluronic_acid",
        inci="Sodium Hyaluronate",
        zh="玻尿酸鈉",
        role="humectant",
        aliases=("hyaluronic acid", "HA", "透明質酸", "玻尿酸"),
        corpus=("incidecoder.com :: Hyaluronic Acid",),
    ),
    Ingredient(
        key="glycerin",
        inci="Glycerin",
        zh="甘油",
        role="humectant",
        aliases=("glycerol",),
        corpus=("incidecoder.com :: Glycerin",),
    ),
    Ingredient(
        key="allantoin",
        inci="Allantoin",
        zh="尿囊素",
        role="active",
        aliases=(),
        corpus=("PMC10988741 :: Overview of popular cosmeceuticals in dermatology.",),
    ),
    # --- ubiquitous bases: no efficacy claim, so nothing to cite -------------
    Ingredient(
        key="aqua",
        inci="Aqua",
        zh="水",
        role="solvent",
        # The bracketed INCI spellings are common on real labels ("Water (Aqua)" /
        # "Aqua (Water)"). Without them the first ingredient of a perfectly ordinary
        # list came back as unknown, and the coach reported not recognising water.
        aliases=("water", "purified water", "水", "water (aqua)", "aqua (water)"),
    ),
    Ingredient(key="butylene_glycol", inci="Butylene Glycol", zh="丁二醇", role="solvent"),
    Ingredient(key="pentylene_glycol", inci="Pentylene Glycol", zh="戊二醇", role="solvent"),
    Ingredient(key="cetearyl_alcohol", inci="Cetearyl Alcohol", zh="鯨蠟硬脂醇", role="emollient"),
    Ingredient(key="dimethicone", inci="Dimethicone", zh="聚二甲基矽氧烷", role="emollient"),
    Ingredient(
        key="alcohol_denat",
        inci="Alcohol Denat.",
        zh="變性酒精",
        role="solvent",
        # Reformulated as a distinct entry on purpose: it is the classic
        # "this product may be too drying" flag, so it must be recognised even
        # though it is a base.
    ),
    Ingredient(key="phenoxyethanol", inci="Phenoxyethanol", zh="苯氧乙醇", role="preservative"),
    Ingredient(key="ethylhexylglycerin", inci="Ethylhexylglycerin", zh="乙基己基甘油", role="preservative"),
    Ingredient(key="chlorphenesin", inci="Chlorphenesin", zh="氯苯甘醚", role="preservative"),
    Ingredient(key="xanthan_gum", inci="Xanthan Gum", zh="黃原膠", role="thickener"),
    Ingredient(key="carbomer", inci="Carbomer", zh="卡波姆", role="thickener"),
    Ingredient(key="citric_acid", inci="Citric Acid", zh="檸檬酸", role="ph_adjuster"),
    Ingredient(key="sodium_hydroxide", inci="Sodium Hydroxide", zh="氫氧化鈉", role="ph_adjuster"),
    Ingredient(key="disodium_edta", inci="Disodium EDTA", zh="EDTA 二鈉", role="chelator"),
    Ingredient(key="tocopherol", inci="Tocopherol", zh="生育酚", role="antioxidant", aliases=("vitamin E", "vitamin e")),
    Ingredient(key="parfum", inci="Parfum", zh="香料", role="fragrance", aliases=("fragrance", "perfume", "香精")),
)

# ---------------------------------------------------------------------------
# Hard blocks
# ---------------------------------------------------------------------------

# Deliberately NARROW and INCOMPLETE.
#
# This is not the "which ingredients are prescription?" list — that question has
# no ingredient-level answer (the corpus itself documents azelaic acid as OTC at
# <=10% and prescription at 15%, and differently per jurisdiction; see
# docs/product-eval-plan.md §3.5). It only holds names that are essentially
# always prescription, where seeing the name in a consumer product at all is a
# signal to stop and refer.
#
# Borderline members were left OUT on purpose: `adapalene` and `hydrocortisone`
# are OTC in some markets, and `benzoyl peroxide` is a normal cosmetic active in
# HK. Completeness is IECIC's job (D4), not a hand-written list's.
PRESCRIPTION_ONLY: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("tretinoin", ("retin-a", "retacnyl")),
    ("isotretinoin", ("accutane", "roaccutane", "異維a酸")),
    ("clindamycin", ()),
    ("betamethasone", ()),
    ("hydroquinone", ()),
)

# ---------------------------------------------------------------------------
# Lookup index
# ---------------------------------------------------------------------------

_NON_KEY = re.compile(r"[^0-9a-z\u4e00-\u9fff]+")


def _norm(text: str) -> str:
    """Fold a name to a comparable key: lowercase, punctuation and spacing gone.

    CJK is preserved — `\\u4e00-\\u9fff` is the CJK Unified Ideographs block, so
    「水楊酸」 survives while `Alpha-Arbutin` / `alpha arbutin` / `ALPHA ARBUTIN`
    all become `alphaarbutin`.
    """
    return _NON_KEY.sub("", text.lower())


_BY_KEY: dict[str, Ingredient] = {i.key: i for i in INGREDIENTS}
_ALIAS_INDEX: dict[str, str] = {}
for _i in INGREDIENTS:
    for _name in (_i.inci, _i.zh, _i.key.replace("_", " "), *_i.aliases):
        _ALIAS_INDEX.setdefault(_norm(_name), _i.key)

_PRESCRIPTION_INDEX: dict[str, str] = {}
for _canon, _aliases in PRESCRIPTION_ONLY:
    for _name in (_canon, *_aliases):
        _PRESCRIPTION_INDEX.setdefault(_norm(_name), _canon)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def canonical(name: str) -> str | None:
    """`Salicylic Acid` / `水楊酸` / `BHA` → `"salicylic_acid"`; unknown → None."""
    if not name:
        return None
    return _ALIAS_INDEX.get(_norm(name))


def is_recognised(name: str) -> bool:
    return canonical(name) is not None


def ingredient(key: str) -> Ingredient | None:
    return _BY_KEY.get(key)


def display_zh(name: str) -> str:
    """Best Chinese name for a raw ingredient string.

    D5: answers should use Chinese wherever possible. For an **unknown**
    ingredient this returns the raw text unchanged — translating a name we do not
    recognise would be inventing a fact about what the product contains.
    """
    key = canonical(name)
    if key is None:
        return name.strip()
    return _BY_KEY[key].zh


def role_of(name: str) -> Role | None:
    key = canonical(name)
    return _BY_KEY[key].role if key else None


def mentioned_keys(text: str) -> set[str]:
    """Ingredient keys *appearing anywhere* in free text (e.g. a product name).

    Deliberately different from `parse_ingredients`: an INCI list is comma-separated,
    a product NAME is not — 「水楊酸 toner」 has no separator, so the list parser
    would treat the whole thing as one unknown token.

    Matching is done on the normalised text, which means ASCII aliases can hit
    inside longer words. So short ASCII aliases (fewer than 3 characters, e.g.
    `HA`) are skipped here; CJK aliases of any length are kept because CJK has no
    word boundaries and 「水楊酸」 is not a prefix of anything else in the seed.
    """
    haystack = _norm(text or "")
    if not haystack:
        return set()
    found: set[str] = set()
    for alias, key in _ALIAS_INDEX.items():
        if not alias:
            continue
        ascii_alias = alias.isascii()
        if ascii_alias and len(alias) < 3:
            continue
        if alias in haystack:
            found.add(key)
    return found


def is_base(name: str) -> bool:
    """True for formula-only roles (solvent / preservative / thickener / …).

    Bases are recognised — so they do not pollute the `unknown` list on every
    pasted product — but they never take part in coverage matching: a product is
    not "missing" a preservative.
    """
    role = role_of(name)
    return role in NON_CLAIM_ROLES


def prescription_block(name: str) -> str | None:
    """The canonical prescription name if `name` is on the narrow hard-block list."""
    if not name:
        return None
    return _PRESCRIPTION_INDEX.get(_norm(name))


@dataclass(frozen=True)
class ParsedIngredient:
    raw: str
    key: str | None
    zh: str | None
    percent: float | None

    @property
    def recognised(self) -> bool:
        return self.key is not None


# Separators in real INCI lists: ", " / ";" / Chinese commas / newlines.
# The lookahead keeps `1,2-Hexanediol` in one piece — a bare comma-split would
# cut it in half and turn a real ingredient into two unknown ones.
_SPLIT = re.compile(r"\s*[,;，；、]\s*|\n+")
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def _split_list(text: str) -> list[str]:
    parts = [p.strip() for p in _SPLIT.split(text)]
    # Re-join the "1" + "2-Hexanediol" case produced by splitting `1,2-Hexanediol`.
    merged: list[str] = []
    for part in parts:
        if merged and re.fullmatch(r"\d+", merged[-1]) and re.match(r"^\d", part):
            merged[-1] = f"{merged[-1]},{part}"
        else:
            merged.append(part)
    return [p for p in merged if p]


def parse_ingredients(text: str) -> list[ParsedIngredient]:
    """Parse a pasted INCI list into canonical ingredients.

    Order is preserved (INCI lists are descending by concentration, which is
    meaningful). Unrecognised entries come back with `key=None` — never guessed.

    A leading label (`成份：` / `INCI:`) is stripped first. Without that the label glues
    onto the first ingredient — `成份：Aqua` is not a name we know, so `Aqua` came back
    unknown and the coach told the user it did not recognise water. Measured on the real
    path before this was fixed.
    """
    out: list[ParsedIngredient] = []
    seen: set[str] = set()
    for raw in _split_list(strip_list_marker(text or "")):
        # Strip a trailing percentage before lookup: `Salicylic Acid 2%`.
        pct_match = _PERCENT.search(raw)
        percent = float(pct_match.group(1)) if pct_match else None
        name = _PERCENT.sub("", raw).strip()
        if not name:
            continue
        key = canonical(name)
        if key is not None:
            if key in seen:
                continue
            seen.add(key)
            out.append(ParsedIngredient(raw=raw, key=key, zh=_BY_KEY[key].zh, percent=percent))
        else:
            out.append(ParsedIngredient(raw=name, key=None, zh=None, percent=percent))
    return out


#: An INCI name as it appears in a list: mostly Latin, no spaces-as-sentences, short.
#: Digits/parentheses/hyphens/slashes/periods are all normal (`1,2-Hexanediol`,
#: `Butylene Glycol`, `Sodium Hyaluronate Crosspolymer-2`).
_INCI_TOKEN = re.compile(r"^[A-Za-z][A-Za-z0-9()\-/.,'’\s]{1,60}$")

#: Words that introduce a list, in either language. Their presence is strong evidence
#: even when the list itself is short.
_LIST_MARKERS = (
    "成份", "成分", "全成分", "配料", "ingredients", "inci", "ingrédients",
)

#: Connective words a user writes *between* the label and the list. Cantonese does not
#: need a colon — 「成份係 Aqua, Glycerin, …」 and 「成分包括 Aqua, …」 are at least as
#: natural as 「成份：」 — so stripping only the marker left the particle glued to the
#: first ingredient. Measured on the real path: 「成份係 Aqua, Glycerin, Niacinamide,
#: Salicylic Acid, …」 parsed the first token as `係 Aqua`, which put Aqua (water) into
#: `unknown[]` and made the coach tell the user 「成份表第一個係「Aqua」（水），係我程式未
#: 認得嘅寫法」. Safe to strip because these are CJK function words — an INCI name is
#: Latin, so this cannot eat a real ingredient.
_LIST_CONNECTORS = re.compile(
    r"^\s*[：:，,、]?\s*(?:係|是|有|包括|包含|如下|為)\s*[：:，,、]?\s*"
    r"|^\s*(?:are|is|includes?|as\s+follows)\b\s*[：:，,、]?\s*",
    re.IGNORECASE,
)


def strip_list_marker(text: str) -> str:
    """Drop a leading list label (`成份：` / `成份係` / `INCI:` / `Ingredients are:`).

    Measured on the real path: a user who pastes 「成份：Aqua, Glycerin, ...」 had the first
    token parsed as `成份：Aqua`, which is not an ingredient — so `Aqua` was reported in
    `unknown[]` and the coach told the user it did not recognise water. The marker (and
    the little connective word that often follows it) is the user's own label, not part
    of the list, so it is removed before parsing.
    """
    if not text:
        return text
    lowered = text.lower()
    out = text
    for m in _LIST_MARKERS:
        idx = lowered.find(m)
        if idx != -1:
            out = text[idx + len(m):]
            break
    out = out.lstrip("：: 　")
    # Applied twice so 「成份係：Aqua」 (connector then colon) is fully unwrapped.
    for _ in range(2):
        stripped = _LIST_CONNECTORS.sub("", out, count=1)
        if stripped == out:
            break
        out = stripped
    return out.strip()


def looks_like_ingredient_list(text: str, *, min_tokens: int = 5) -> bool:
    """Is this message a pasted ingredient list rather than ordinary prose?

    Used to decide whether to run the deterministic product evaluation in chat. It must
    **not** consult the seed dictionary: a real INCI list has 20–40 entries and the
    dictionary is currently 31, so a real product usually contains many entries we do
    not know. Requiring several *recognised* actives would therefore miss exactly the
    messages this is for.

    So the signal is structural instead — many comma-separated Latin-looking tokens —
    which ordinary Cantonese chat almost never produces. A marker word (`成份`/`INCI`)
    lowers the bar, since the user has told us what they pasted.

    Deliberately conservative: a false negative just means the coach answers as usual,
    while a false positive would run coverage matching against the user's own product
    list and make the app talk about ingredients they never pasted.
    """
    if not text:
        return False
    has_marker = any(m in text.lower() for m in _LIST_MARKERS)
    body = strip_list_marker(text)
    if not body:
        return False

    tokens = _split_list(body)
    # Percentages are stripped first, exactly as `parse_ingredients` does: "Salicylic
    # Acid 2%" is one of the commonest ways a user pastes a list, and `%` is not a
    # character an INCI name contains — so matching the raw token would miss it.
    inci_like = []
    for t in tokens:
        cleaned = _PERCENT.sub("", t).strip()
        if cleaned and len(cleaned) <= 60 and _INCI_TOKEN.match(cleaned):
            inci_like.append(cleaned)
    needed = max(2, min_tokens - 2) if has_marker else min_tokens
    if len(inci_like) < needed:
        return False
    # Two or three Latin words in a Cantonese sentence is prose ("我用 CeraVe 同 The
    # Ordinary"); a list is mostly Latin by *volume*, not just by count.
    latin_chars = sum(len(t) for t in inci_like)
    return latin_chars >= 40
