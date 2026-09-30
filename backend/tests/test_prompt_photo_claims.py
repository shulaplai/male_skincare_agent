"""The prompt must not tell the model to claim evidence that does not exist.

Found by using the app as a first-time user, with a *text-only* first check-in
(「今日下巴爆咗兩粒瘡，T字位好油」, no photo). The reply opened with
「呢張相已經幫你建立咗 baseline」 although the run log recorded `has_photo: false`,
`vision_used: false`, `vision_reason: "no_photo"`.

Cause was not the model: the `first_checkin` block in `build_advise_prompt` said
「呢個係用戶嘅第一個紀錄／第一次上載皮膚相」 and 「呢張相會成為佢嘅 baseline」 unconditionally.
`first_checkin` only means "this conversation has no Entry yet", which a text check-in
satisfies just as well as a photo one.

This is the mirror image of the #15 bug (telling the model "local mode" while holding a
photo it could not read): both make the agent assert something false about the user's own
upload. The block is now worded from `vision_reason`, and these tests pin both branches
plus the consent-off note.
"""
from app.agent.prompts import build_advise_prompt, build_analyze_prompt


def _state(**over):
    state = {
        "analysis": {"observes_skin": True, "attributes": [], "metrics": []},
        "user_text": "今日下巴爆咗兩粒瘡，T字位好油",
        "tool_results": [],
        "recent_messages": [],
        "first_checkin": True,
    }
    state.update(over)
    return state


def test_first_text_checkin_does_not_claim_a_photo():
    prompt = build_advise_prompt(_state(vision_used=False, vision_reason="no_photo"))
    # The *claim* is what matters: the block also quotes the forbidden phrases in order to
    # ban them, so asserting on the bare word 「呢張相」 would fail for the wrong reason.
    assert "呢張相會成為" not in prompt
    assert "第一次上載皮膚相" not in prompt
    assert "冇俾相" in prompt
    # …and it must not swing the other way either: no photo was sent, so "I cannot see it"
    # would be just as false as "I can see it".
    assert "唔好叫佢補相" in prompt
    assert "唔好講你「睇唔到」相" in prompt


def test_first_photo_checkin_keeps_the_baseline_wording():
    prompt = build_advise_prompt(_state(vision_used=True, vision_reason="used"))
    assert "呢張相會成為" in prompt
    assert "冇俾相" not in prompt


def test_consent_off_note_names_local_mode_not_a_malfunction():
    note = build_analyze_prompt("呢張係近鏡，睇下點", has_photo=True)
    assert "本地模式" in note
    assert "唔好講『讀唔到』" in note
    assert "☁️" in note  # tells the user how to change it


def test_no_photo_note_stays_neutral():
    note = build_analyze_prompt("下巴爆咗兩粒", has_photo=False)
    assert note.endswith("（無相，純文字）")
