"""Guardrail tests.

The first three existed before the `reply` gap was found. The next four are the
regression net for it: `reply` is the bubble the user actually reads, and it used
to be scanned by nothing.
"""
from app.agent.guardrails import (
    ESCALATION_MESSAGE,
    apply_guardrails,
    contains_medical_advice,
)
from app.agent.schemas import Advice


def test_normal_advice_gets_disclaimer():
    advice = Advice(items=["做好保濕同防曬"], disclaimer="", escalate=False)
    final, escalate = apply_guardrails(advice, "下巴有少少暗瘡")

    assert escalate is False
    assert final.disclaimer != ""
    assert final.items == ["做好保濕同防曬"]


def test_red_flag_escalates():
    advice = Advice(items=["做好保濕"], disclaimer="", escalate=False)
    final, escalate = apply_guardrails(advice, "塊面突然大面積爛晒")

    assert escalate is True


def test_medication_terms_get_replaced():
    advice = Advice(items=["你可以口服某種抗生素"], disclaimer="", escalate=False)
    final, escalate = apply_guardrails(advice, "下巴有暗瘡")

    assert escalate is True
    assert "皮膚科" in final.items[0]


# --------------------------------------------------------------------------
# `reply` coverage (the bug these were written for)
# --------------------------------------------------------------------------


def test_medical_term_in_reply_escalates_and_replaces_reply():
    """A medical claim in `reply` is exactly as visible as one in `items`."""
    advice = Advice(
        reply="建議你每日口服抗生素 50mg，連續兩星期就會好。",
        items=["保持清潔", "做好保濕"],
        disclaimer="",
        escalate=False,
    )
    final, escalate = apply_guardrails(advice, "下巴爆瘡點算？")

    assert escalate is True
    assert final.reply == ESCALATION_MESSAGE
    assert "抗生素" not in final.reply


def test_clean_reply_is_not_touched():
    """Regression guard: widening the scan must not start rewriting normal replies."""
    reply = "你嘅暗瘡由 3/3 落到 2/3，同停咗辣嘢吻合。維持水楊酸隔日一次就夠。"
    advice = Advice(reply=reply, items=["維持水楊酸隔日一次"], disclaimer="", escalate=False)
    final, escalate = apply_guardrails(advice, "下巴好咗")

    assert escalate is False
    assert final.reply == reply
    assert final.items == ["維持水楊酸隔日一次"]


def test_dose_in_reply_escalates():
    advice = Advice(reply="你可以食 500 mcg 嘅某種補充劑。", items=[], disclaimer="", escalate=False)
    final, escalate = apply_guardrails(advice, "下巴爆瘡")

    assert escalate is True
    assert final.reply == ESCALATION_MESSAGE


def test_package_size_is_not_a_dose():
    """`30g` / `50ml` are package sizes, not doses.

    The product-evaluation feature talks about sizes constantly; escalating those
    would make the warning meaningless. Only pharmacological units count.
    """
    reply = "呢支 30g，一般可以用到兩個月；50ml 嘅版本抵啲。"
    advice = Advice(reply=reply, items=["買 30g 裝先試"], disclaimer="", escalate=False)
    final, escalate = apply_guardrails(advice, "呢支精華得唔得？")

    assert escalate is False
    assert final.reply == reply


def test_bare_mg_inside_ascii_word_does_not_match():
    """`mg` as a substring used to match anywhere; now it needs a dose shape."""
    assert contains_medical_advice("the amgine pathway") is False
    assert contains_medical_advice("50mg") is True
    assert contains_medical_advice("500 mcg") is True
    assert contains_medical_advice("2% 水楊酸") is False
