"""Deterministic safety guardrails (no LLM).

These are the "medical guardrail" layer from the architecture: hard rules that
run regardless of what the model produced, so safety never depends on the model
behaving.

⚠️ **Scanned fields**: both `Advice.reply` and `Advice.items`. `reply` is the
text the user actually reads (the chat bubble — `frontend/src/App.tsx`,
`res.advice.reply || res.analysis.summary`), so a guardrail that only looked at
`items` left the user-facing field completely unprotected. Measured before the
fix: the same sentence「建議你每日口服抗生素 50mg」was replaced with the escalation
message when placed in `items`, and passed through verbatim when placed in
`reply`.
"""
import re

from .schemas import Advice

DEFAULT_DISCLAIMER = (
    "以上建議只供參考，唔構成醫療意見。如果情況持續或惡化，請諮詢皮膚科醫生。"
)

RED_FLAGS = [
    "大面積",
    "潰瘍",
    "流膿",
    "持續出血",
    "擴散得好快",
    "高燒",
    "劇痛",
    "呼吸困難",
    "突然爆發",
    "腫到",
]

# Substring terms. Chinese has no word boundaries, so substring matching is the
# pragmatic choice here. Every ASCII entry must be long enough that it cannot
# appear inside an unrelated word — that is why the bare unit `"mg"` is NOT in
# this list (see `DOSE_RE`).
MEDICAL_TERMS = [
    "口服",
    "劑量",
    "毫克",
    "抗生素",
    "類固醇",
    "處方藥",
    # Both spellings: `isotretinoin` does not contain `tretinoin` the other way round,
    # and a standalone topical tretinoin product is exactly the case the product
    # evaluation hard-stops on (`ingredients.PRESCRIPTION_ONLY`).
    "tretinoin",
    "isotretinoin",
    "accutane",
    "異維a酸",
    "消炎藥",
]

# Dose units need a boundary, and only pharmacological units qualify.
#
# Why not a plain substring `"mg"`: it matched inside unrelated ASCII words, and
# fixing the `reply` gap (above) widened the scanned text from two short bullets
# to a 2-5 sentence paragraph — so a sloppy match now escalates far more often.
# Why `g` / `ml` are deliberately absent: they are ordinary *package sizes*
# ("呢支 30g"), not doses, and the product-evaluation feature will talk about
# them constantly. Escalating those would train users to ignore the warning.
DOSE_RE = re.compile(r"(?<![a-z])\d+(?:[.,]\d+)?\s*(?:mg|mcg|µg|ug|iu)\b", re.IGNORECASE)

ESCALATION_MESSAGE = (
    "你嘅情況可能涉及醫療層面，我唔可以俾呢方面嘅建議。"
    "請盡快諮詢皮膚科醫生。"
)


def contains_any(text: str, terms: list[str]) -> bool:
    low = text.lower()
    return any(t.lower() in low for t in terms)


def contains_medical_advice(text: str) -> bool:
    """True if `text` names a medical intervention or states a drug dose.

    Single entry point for the medical rule so `apply_guardrails` (which rewrites)
    and `eval.safety.check_safety` (which grades) can never drift apart.
    """
    return contains_any(text, MEDICAL_TERMS) or DOSE_RE.search(text) is not None


def advice_text(advice: Advice) -> str:
    """Everything the user will see, in one string (reply + bullet items)."""
    return "\n".join([advice.reply, *advice.items])


def apply_guardrails(advice: Advice, user_text: str) -> tuple[Advice, bool]:
    # Escalation is decided deterministically, not by the model's own flag.
    escalate = contains_any(user_text, RED_FLAGS)

    reply = advice.reply
    items = list(advice.items)
    if contains_medical_advice(advice_text(advice)):
        escalate = True
        # `reply` must be replaced too: it is the bubble the user reads, and
        # leaving the medical sentence there while only sanitising the bullet
        # list would show the unsafe text anyway.
        reply = ESCALATION_MESSAGE
        items = [ESCALATION_MESSAGE]

    disclaimer = advice.disclaimer or DEFAULT_DISCLAIMER
    final = advice.model_copy(
        update={"reply": reply, "items": items, "disclaimer": disclaimer, "escalate": escalate}
    )
    return final, escalate
