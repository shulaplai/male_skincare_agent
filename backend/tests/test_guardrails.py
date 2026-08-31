from app.agent.guardrails import apply_guardrails
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
