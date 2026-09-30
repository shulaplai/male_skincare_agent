"""A pasted ingredient list is answered **in chat** — no separate product UI.

The user's decision: when they paste a product (or bring back one the coach suggested),
the comparison shows up as an ordinary conversation turn. So the work happens inside the
`tools` node of the existing graph rather than in a second endpoint the UI has to know
about — and because `persist` already refuses to write an `Entry` for a turn with no skin
evidence, answering a product question this way cannot become a day of skin data.

The division of labour is the point: `product_eval` decides the **facts** (which actives
are present, which of the user's recommendations are missing, what conflicts exist), and
the LLM only phrases them. These tests pin both halves — including that a prose message
mentioning a product does *not* silently run coverage matching against it.
"""
import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent.graph import build_graph
from app.agent.ingredients import looks_like_ingredient_list
from app.agent.prompts import build_advise_prompt
from app.agent.schemas import Advice, SkinAnalysis
from app.db import Base
from app.models import ChatMessage, Conversation, Entry, Insight, Product, TimelineEvent, User
from app.rag import DeterministicEmbedder

# Nicely covers the three interesting buckets: recognised actives, recognised base
# ingredients, and names no seed dictionary would know.
INCI = (
    "Aqua, Glycerin, Niacinamide, Salicylic Acid, Panthenol, "
    "Sodium Hyaluronate, Allantoin, Tocopherol"
)
# Contains tretinoin — a hard-stop, essentially-always-prescription name.
PRESCRIPTION = "Aqua, Glycerin, Tretinoin 0.025%, Panthenol, Allantoin, Carbomer"


def make_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def seed_conversation(sf, *, products=(), with_entry=False) -> str:
    s = sf()
    u = User(name="阿軒")
    s.add(u)
    s.flush()
    c = Conversation(user_id=u.id, body_part="面部皮膚")
    s.add(c)
    s.flush()
    for name in products:
        s.add(Product(conversation_id=c.id, name=name))
    if with_entry:
        # A dry, acne-prone day: dryness 0 so the acid-conflict rule stays quiet and the
        # assertions can be about coverage rather than conflicts.
        s.add(
            Entry(
                conversation_id=c.id,
                date=datetime.date(2026, 1, 1),
                attributes=[
                    {"key": "acne", "severity": 2, "note": ""},
                    {"key": "oiliness", "severity": 2, "note": ""},
                    {"key": "dryness", "severity": 0, "note": ""},
                ],
            )
        )
    s.commit()
    cid = c.id
    s.close()
    return cid


class StubLLM:
    """A model that observes nothing (as the real one does for a list of chemicals).

    `reply` is settable so a test can hand back the *worst* plausible answer and check
    the deterministic guardrail still wins.
    """

    def __init__(self, observes: bool = False, reply: str = "呢支幾好，可以買。"):
        self.observes = observes
        self.reply = reply
        self.last_prompt = None

    def structured(self, system, user, schema):
        if schema is SkinAnalysis:
            return SkinAnalysis(
                observes_skin=self.observes,
                summary="有觀察" if self.observes else "（未提及皮膚狀況）",
                attributes=[{"key": "acne", "severity": 2, "note": ""}],
            )
        self.last_prompt = user
        return Advice(reply=self.reply, items=["做好保濕"], disclaimer="已加免責", escalate=False)

    def structured_vision(self, system, user, schema, images):
        return self.structured(system, user, schema)


def run(sf, llm, cid, text):
    g = build_graph(
        llm=llm, vision_llm=llm, session_factory=sf, embedder=DeterministicEmbedder()
    )
    return g.invoke(
        {
            "conversation_id": cid,
            "user_text": text,
            "photo_paths": [],
            "cloud_analysis": False,
            "trace": [],
        }
    )


def counts(sf, cid) -> dict:
    s = sf()
    try:
        return {
            "entries": s.query(Entry).filter_by(conversation_id=cid).count(),
            "timeline": s.query(TimelineEvent).filter_by(conversation_id=cid).count(),
            "insights": s.query(Insight).filter_by(conversation_id=cid).count(),
            "messages": s.query(ChatMessage).filter_by(conversation_id=cid).count(),
        }
    finally:
        s.close()


# ---------------------------------------------------------------------------
# When is a message an ingredient list?
# ---------------------------------------------------------------------------


PROSE = [
    "下巴爆咗兩粒瘡，用咗水楊酸洗面",
    "呢支精華得唔得？",
    "我用 CeraVe 同 The Ordinary",
    "我今日搽咗 CeraVe Moisturising Cream, 之後出油",
    "我買咗支 The Ordinary Niacinamide 10% + Zinc 1%，想問你覺得點？",
    "Glycerin 係咪好？",
    "今日食咗雞蛋, 牛奶, 麥片",
    "早：CeraVe, 晚：Adapalene",
    "Aqua 同 Water 有咩分別？",
]

REAL_LISTS = [
    INCI,
    "成份：Aqua, Glycerin, Niacinamide, Salicylic Acid, Panthenol, Allantoin",
    "INCI: Water (Aqua), Butylene Glycol, 1,2-Hexanediol, Glycerin, Panthenol, "
    "Allantoin, Carbomer, Tromethamine",
    # Percentages are one of the commonest ways a list arrives, and `%` is not a
    # character an INCI name contains.
    "Niacinamide 5%, Zinc PCA 1%, Aqua, Glycerin, Panthenol",
    "Salicylic Acid 2%, Niacinamide 4%, Zinc PCA 1%, Glycerin, Aqua",
    "Water, Glycerin, Butylene Glycol, 1,2-Hexanediol, Panthenol, Allantoin, "
    "Carbomer, Arginine, Disodium EDTA",
]


@pytest.mark.parametrize("text", PROSE)
def test_prose_is_not_an_ingredient_list(text):
    """A false positive would talk about ingredients the user never pasted.

    `我用 CeraVe 同 The Ordinary` is the case that matters: naming products is normal
    chat, and it must not turn into coverage matching.
    """
    assert looks_like_ingredient_list(text) is False


@pytest.mark.parametrize("text", REAL_LISTS)
def test_real_lists_are_detected(text):
    assert looks_like_ingredient_list(text) is True


def test_the_detector_does_not_depend_on_the_seed_dictionary():
    """A real INCI list is 20–40 entries and our dictionary is 31, so a detector that
    required several *recognised* actives would miss most real products.

    Proves it structurally: this list is almost entirely unknown to us, and still
    detected.
    """
    from app.agent.ingredients import canonical

    exotic = (
        "Water, Caprylic/Capric Triglyceride, Cetearyl Alcohol, Squalane, "
        "Bisabolol, Madecassoside, Zingiber Officinale Root Extract, "
        "Hydroxyethyl Acrylate/Sodium Acryloyldimethyl Taurate Copolymer"
    )
    tokens = exotic.split(", ")
    unknown = [t for t in tokens if canonical(t) is None]
    assert len(unknown) >= 4, f"sanity: this list is mostly unknown to us ({len(unknown)}/{len(tokens)})"
    assert looks_like_ingredient_list(exotic) is True


# ---------------------------------------------------------------------------
# The graph actually runs it
# ---------------------------------------------------------------------------


def test_a_pasted_list_is_evaluated_and_the_reply_cites_real_facts():
    sf = make_factory()
    cid = seed_conversation(sf, with_entry=True)
    llm = StubLLM()

    res = run(sf, llm, cid, INCI)

    ev = res["product_eval"]
    assert ev is not None, "a pasted list must reach the deterministic evaluator"
    assert "水楊酸" in ev["matched"], "salicylic acid is what this user needs"
    assert ev["unknown"] == [], "this list is fully inside the seed dictionary"
    assert ev["verdict"] == "good", "it supplies both actives the rules want"

    # The model is told the computed facts and forbidden from adding its own.
    assert "我已經用程式同佢嘅皮膚紀錄比對過" in llm.last_prompt
    assert "唔可以加入上面冇列出嘅成份" in llm.last_prompt
    # This list happens to supply both of the actives the rules want, so there is no
    # "missing" line — the assertion is about what the model was told, not what we hope.
    assert "產品有、而用戶需要嘅成份：菸鹼醯胺、水楊酸" in llm.last_prompt


def test_a_pasted_list_is_not_a_check_in():
    """The reply is a chat bubble, so nothing about the day changes."""
    sf = make_factory()
    cid = seed_conversation(sf)

    res = run(sf, StubLLM(), cid, INCI)

    c = counts(sf, cid)
    assert c["entries"] == 0, "a list of chemicals is not a skin observation"
    assert c["timeline"] == 0
    assert c["insights"] == 0
    assert c["messages"] == 2, "display truth: the turn is still saved"
    detail = [t for t in res["trace"] if t["node"] == "persist"][0]["detail"]
    assert detail["entry_written"] is False


def test_ordinary_prose_does_not_run_coverage_matching():
    sf = make_factory()
    cid = seed_conversation(sf)

    res = run(sf, StubLLM(), cid, "我用 CeraVe 同 The Ordinary")

    assert res["product_eval"] is None
    detail = [t for t in res["trace"] if t["node"] == "tools"][0]["detail"]
    assert detail["product_eval"] is None


def test_the_users_own_product_is_flagged_as_a_duplicate():
    """`Product.ingredients` is never populated, so the active is read from the name —
    the only signal available, and enough to warn about stacking."""
    sf = make_factory()
    cid = seed_conversation(sf, products=["The Ordinary Salicylic Acid 2% Solution"])

    res = run(sf, StubLLM(), cid, INCI)

    kinds = [c["kind"] for c in res["product_eval"]["conflicts"]]
    assert "duplicate_active" in kinds
    text = " ".join(c["text"] for c in res["product_eval"]["conflicts"])
    assert "The Ordinary Salicylic Acid 2% Solution" in text, "name the product they typed"


def test_a_prescription_ingredient_wins_over_a_cheerful_reply():
    """Deterministic safety: the model's prose never gets the last word here.

    `evaluate_product` already suppresses coverage for a hard-stop ingredient, and the
    standalone route skips its narrative for the same reason. In chat the guardrail node
    replaces the reply instead — and names the ingredient, which is safe and useful
    because the user is the one who pasted it.
    """
    sf = make_factory()
    cid = seed_conversation(sf)
    llm = StubLLM(reply="呢支成份好溫和，早晚都用得，配埋你而家支精華仲好。")

    res = run(sf, llm, cid, PRESCRIPTION)

    ev = res["product_eval"]
    assert ev["escalate"] is True
    assert ev["verdict"] == "avoid"
    assert ev["matched"] == [] and ev["missing"] == [], "coverage is suppressed"
    assert ev["recognised"] == [], "no active list next to an avoid verdict"

    assert res["escalate"] is True
    assert res["advice"]["reply"] != llm.reply, "the cheerful reply must not survive"
    assert "處方藥成份" in res["advice"]["reply"]
    assert "tretinoin" in res["advice"]["reply"].lower()
    detail = [t for t in res["trace"] if t["node"] == "guardrail"][0]["detail"]
    assert detail["forced_by_product_eval"] is True


# ---------------------------------------------------------------------------
# The prompt block itself (pure function)
# ---------------------------------------------------------------------------


def test_advise_prompt_omits_the_block_when_there_is_no_evaluation():
    prompt = build_advise_prompt(
        {
            "user_text": "下巴爆咗兩粒",
            "analysis": {"observes_skin": True, "summary": "x"},
            "tool_results": [],
            "recent_messages": [],
        }
    )
    assert "成份表" not in prompt


def test_advise_prompt_renders_the_evaluation_it_is_given():
    prompt = build_advise_prompt(
        {
            "user_text": INCI,
            "analysis": {"observes_skin": False, "summary": "（未提及皮膚狀況）"},
            "tool_results": [],
            "recent_messages": [],
            "product_eval": {
                "verdict": "caution",
                "recognised": ["水楊酸"],
                "unknown": ["Madecassoside"],
                "matched": ["水楊酸"],
                "missing": ["防曬"],
                "conflicts": [{"kind": "duplicate_active", "text": "你已經用緊「X」。"}],
                "warnings": ["唔好同酸疊住用"],
                "suggestions": [],
                "triggers": [],
                "escalate": False,
                "disclaimer": "只供參考",
            },
        }
    )
    assert "我認唔到嘅成份（原文）：Madecassoside" in prompt
    assert "用戶需要但產品冇嘅成份：防曬" in prompt
    assert "你已經用緊「X」。" in prompt
    # It is a phrasing job, and the prompt has to say so.
    assert "唔好自己判斷成份好唔好" in prompt
    # Real-LLM run said 「我幫你記錄低呢支產品」 while `persist` wrote only a ChatMessage.
    assert "唔好話你「記錄低」咗呢支產品" in prompt


def test_a_labelled_list_reports_no_false_unknowns():
    """End-to-end guard for the label bug, through the graph.

    This is the failure the user would actually see: they paste
    「成份：Aqua, Glycerin, …」 and the coach replies that it does not recognise the first
    ingredient. Every name here is in the seed dictionary, so `unknown` must be empty.
    """
    sf = make_factory()
    cid = seed_conversation(sf, with_entry=True)

    res = run(sf, StubLLM(), cid, "成份：" + INCI)

    ev = res["product_eval"]
    assert ev is not None
    assert ev["unknown"] == [], f"nothing here is unknown to us: {ev['unknown']}"
    assert "水楊酸" in ev["matched"]
