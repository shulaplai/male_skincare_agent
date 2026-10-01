"""The AI has to teach the user how to record — that is how the product gets data.

Two things this locks down:

1. **Onboarding always says how to record** (20 s clip with a moving camera > photo >
   plain words), in both branches — the first check-in with a photo and the first
   text-only one.
2. **The one-line nudge is deterministic**, not left to the model's memory: it appears
   only for a text-only check-in that is not the first one (`vision_reason ==
   "no_photo"`), so the user is reminded without being nagged on every turn.

Plus the honest limitation: the app only samples video *frames* (the audio track is
dropped), so the guide must not pretend that saying things out loud gets recorded.
"""
from app.agent import prompts


def _state(**kw) -> dict:
    base = {
        "user_text": "今日塊面好油",
        "analysis": {"observes_skin": True, "summary": "油光", "metrics": [], "attributes": []},
        "tool_results": {},
        "tool_calls": [],
        "first_checkin": False,
        "vision_reason": "no_photo",
    }
    base.update(kw)
    return base


def test_first_text_checkin_teaches_how_to_record():
    p = prompts.build_advise_prompt(_state(first_checkin=True, vision_reason="no_photo"))
    assert "點記錄最準確" in p
    assert "20 秒" in p and "慢慢掃" in p
    # 唔可以因為要教記錄而講返「呢張相」（注意：「呢張相」一詞本身會出現喺禁令句
    # ——「唔好講『呢張相』」—— 所以要斷言嗰句**宣稱**）
    assert "呢張相會成為" not in p


def test_first_photo_checkin_teaches_how_to_record():
    p = prompts.build_advise_prompt(_state(first_checkin=True, vision_reason="used", vision_used=True))
    assert "點記錄最準確" in p
    assert "20 秒" in p


def test_plain_text_checkin_gets_one_short_nudge():
    p = prompts.build_advise_prompt(_state())
    assert "今次係純文字打卡" in p
    assert "唔好多過一句" in p


def test_nudge_is_absent_when_the_user_sent_a_photo():
    p = prompts.build_advise_prompt(_state(vision_reason="used", vision_used=True))
    assert "今次係純文字打卡" not in p
    assert "點記錄最準確" not in p


def test_nudge_is_absent_for_a_non_checkin_question():
    """問產品問題（observes_skin=False）唔應該搭單訓話。"""
    st = _state(analysis={"observes_skin": False, "summary": "s", "metrics": [], "attributes": []})
    p = prompts.build_advise_prompt(st)
    assert "今次係純文字打卡" not in p


def test_recording_guide_says_the_audio_is_not_recorded():
    assert "唔會" in prompts.RECORDING_GUIDE and "聲" in prompts.RECORDING_GUIDE


def test_detected_events_rule_treats_casual_speech_as_events():
    """用戶唔會填表 —— 抽取規則要明講「順口講都要抽」。"""
    assert "順口講" in prompts.ADVISE_SYSTEM
    assert "diet" in prompts.ADVISE_SYSTEM and "product_name" in prompts.ADVISE_SYSTEM
    assert "唔好老作" in prompts.ADVISE_SYSTEM
