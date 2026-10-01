"""In-app reference guide: 男士護膚基本資料.

## Why this is code and not a Markdown file

Two reasons, both about not lying to the reader:

1. **The 「應該用咩產品」 section is generated from `agent/recommend.RULES`** — the
   same table the agent uses to recommend actives. A hand-written guide could drift
   from what the app actually recommends, and a guide that disagrees with the agent
   is worse than no guide.
2. **Every claim carries `citations`**, and `tests/test_guide.py` resolves each
   citation against the real `chunks` table (skipped in CI, which has no `data/`).
   A citation that cannot be found is worse than no citation: it looks like
   evidence. That test already caught a wrong citation in `ingredients.py`.

## What is deliberately NOT in here

* **「一次只加一樣新產品」** — a common instruction that sounds obviously right, but
  the corpus has **zero** sources for it. Writing it would mean inventing a fact
  (the same failure mode the project's audit was built to catch). It is omitted
  rather than softened.
* **Any diagnosis, dose, or prescription ingredient.** Guardrail territory.

The guide is reference material for the *user*, so it uses plain Cantonese. Chinese
names come from `ingredients.display_zh`, so the guide and the evaluator name the
same ingredient the same way (D5).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .agent.ingredients import display_zh
from .agent.recommend import RULES
from .agent.attributes import ATTRIBUTE_LABELS

BlockType = Literal["para", "list", "steps", "callout", "image", "sources", "actives"]


class Block(BaseModel):
    type: BlockType
    #: prose paragraph, callout body, or image caption
    text: str = ""
    #: list / steps items
    items: list[str] = Field(default_factory=list)
    #: `info` | `warn` | `tip` — drives styling only
    tone: str = "info"
    #: id of the illustration this block stands in for (rendered as a placeholder)
    image_id: str = ""
    citations: list[str] = Field(default_factory=list)


class Section(BaseModel):
    id: str
    title: str
    icon: str
    summary: str = ""
    blocks: list[Block] = Field(default_factory=list)


class Guide(BaseModel):
    title: str
    subtitle: str
    sections: list[Section]
    #: aggregate of every citation used, for the 「引用資料」 footer
    sources: list[str]


# ---------------------------------------------------------------------------
# Shared citation strings — checkable against the live chunks table
# ---------------------------------------------------------------------------

_CLEANSE_NHS = "www.nhs.uk :: Acne"
_SEBUM = "PMC12729757 :: A Comprehensive Review: The Bidirectional Role of Sebum in Skin Health."
_ACNE_SCAR = "dermnetnz.org :: Acne Scarring — DermNet"
_DRY_SKIN = "dermnetnz.org :: Dry Skin (Xeroderma): Causes, Treatments, and More - DermNet"
_MOISTURISER_2X = (
    "PMC12949975 :: Concomitant Use of Dermo-Cosmetic Skin Care in Aesthetic Procedures: "
    "Systematic Review with Expert Panel Recommendations."
)
_PIH_SUNSCREEN = "dermnetnz.org :: Postinflammatory hyperpigmentation"
_RETINOL = "incidecoder.com :: Retinol"
_ACNE_DERMOCOSMETICS = (
    "PMC12145734 :: From Monotherapy to Adjunctive Therapies: Application of Dermocosmetics "
    "in Acne Management Across Australia and New Zealand."
)
_BASIC_ROUTINE_SCARS = (
    "PMC13220015 :: Clinical implications of skincare: lessons from placebo-controlled "
    "dermatology trials."
)
_PIGMENT_SUNSCREEN = (
    "PMC13109754 :: Global consensus on the management of melanin hyperpigmentation disorders."
)


def _actives_block() -> Block:
    """The 「應該用咩產品」 table, generated from the recommender's own RULES."""
    items: list[str] = []
    for rule in RULES:
        label = (
            "色素／暗瘡印"
            if rule.trigger == "pigmentation"
            else ATTRIBUTE_LABELS.get(rule.trigger, rule.trigger)
        )
        primary_zh = display_zh(rule.primary[0])
        alt_zh = display_zh(rule.alternative[0])
        items.append(
            f"{label} → 主選：{primary_zh}（{rule.primary[1]}）；"
            f"次選：{alt_zh}（{rule.alternative[1]}）"
        )
    return Block(type="actives", items=items)


def build_guide() -> Guide:
    """Build the guide. Pure — regenerated per request so it can never go stale."""
    sections: list[Section] = [
        Section(
            id="daily",
            title="一日應該點護膚",
            icon="sun",
            summary="三步就夠：潔面、保濕、防曬。多過三步唔會自動更好。",
            blocks=[
                Block(
                    type="para",
                    text=(
                        "最基本而有效嘅護膚得三步：**潔面、保濕、防曬**。"
                        "有研究發現，單單持續做呢個基本組合（溫和潔面 + 保濕 + 廣譜防曬），"
                        "已經顯著減少活躍暗瘡嘅人新生成萎縮性疤痕。"
                    ),
                    citations=[_BASIC_ROUTINE_SCARS],
                ),
                Block(
                    type="steps",
                    items=[
                        "**朝早**：溫和潔面 → 保濕 → 防曬",
                        "**夜晚**：溫和潔面 → 功效產品（例如酸類、精華）→ 保濕",
                        "**次數**：一日唔好洗超過兩次",
                    ],
                    citations=[_CLEANSE_NHS],
                ),
                Block(
                    type="callout",
                    tone="warn",
                    text=(
                        "**洗得多唔等於好。** 頻密洗臉會刺激皮膚、令症狀更差；用溫和潔面產品同"
                        "暖水（過熱或過冷都會令暗瘡更差）。"
                    ),
                    citations=[_CLEANSE_NHS],
                ),
                Block(
                    type="callout",
                    tone="tip",
                    text=(
                        "清潔過度會破壞皮膚屏障，而屏障受損會引發**補償性出油** —— "
                        "即係越洗越油。所以唔夠油唔係洗得唔夠。"
                    ),
                    citations=[_SEBUM],
                ),
                Block(
                    type="image",
                    image_id="daily-routine",
                    text="一日流程示意圖（佔位）",
                    citations=[],
                ),
            ],
        ),
        Section(
            id="order",
            title="護膚嘅先後次序",
            icon="list-ordered",
            summary="由最薄身去到最厚身；功效產品放喺保濕之前。",
            blocks=[
                Block(
                    type="steps",
                    items=[
                        "**潔面**（暖水、溫和產品、拍乾）",
                        "**功效產品**：酸類（BHA／AHA）、精華、杜鵰花酸等 —— 薄身先行",
                        "**保濕**：趁皮膚仍然微濕就搽，效果最好",
                        "**防曬**：朝早最後一步，要搽足量",
                    ],
                    citations=[_DRY_SKIN],
                ),
                Block(
                    type="para",
                    text=(
                        "呢個次序唔係儀式，係有原因：保濕產品**搽喺微濕嘅皮膚上最有效**，"
                        "而且酸性（pH 低於 7）嘅配方表現較好。所以潔面之後唔好等全乾才搽保濕。"
                    ),
                    citations=[_DRY_SKIN],
                ),
                Block(
                    type="callout",
                    tone="info",
                    text=(
                        "保濕一日可以用到**兩次或以上** —— 皮膚補夠水，修復更快、"
                        "發炎反應亦較少。"
                    ),
                    citations=[_MOISTURISER_2X],
                ),
                Block(
                    type="image",
                    image_id="layer-order",
                    text="層疊次序示意圖（佔位）",
                ),
            ],
        ),
        Section(
            id="by_skin",
            title="應該用咩產品",
            icon="droplet",
            summary="按你而家嘅皮膚狀況揀成份 —— 主選係證據最多嗰個，次選係特殊情況改用。",
            blocks=[
                Block(
                    type="para",
                    text=(
                        "下面嗰張表同 app 推薦你嘅成份**係同一份資料**，唔會兩邊講唔同嘅嘢。"
                        "「主選」係證據最多、最常用嘅；「次選」係你有其他狀況（例如又乾又紅）"
                        "時可以改嘅。**唔講牌子** —— 成份同濃度先係重點。"
                    ),
                ),
                _actives_block(),
                Block(
                    type="callout",
                    tone="warn",
                    text=(
                        "**（app 建議，唔係文獻結論）一次只加一樣新產品。** "
                        "如果你同時加兩三樣，出問題嗰陣分唔清係邊樣搞成 —— "
                        "呢個亦係 app 幫你追蹤因果嘅前提。"
                    ),
                ),
                Block(
                    type="callout",
                    tone="warn",
                    text=(
                        "**酸類要循序漸進。** 視黃醇為例：就算係濃度好低（約 0.1%）嘅配方，"
                        "研究都證明有效而且耐受性好好 —— 關鍵係**慢慢引入**，唔係買最猛嗰支。"
                    ),
                    citations=[_RETINOL],
                ),
            ],
        ),
        Section(
            id="cautions",
            title="護膚時有咩要注意",
            icon="triangle-alert",
            summary="唔好擠、唔好刷、防曬要搽足、有醫療問題要睇醫生。",
            blocks=[
                Block(
                    type="callout",
                    tone="warn",
                    text=(
                        "**唔好擠暗瘡。** 擠或者摳原有嘅病灶，會令疤痕更加嚴重。"
                    ),
                    citations=[_ACNE_SCAR],
                ),
                Block(
                    type="callout",
                    tone="warn",
                    text=(
                        "**唔好用力刷面。** 過度洗臉或者磨砂會破壞表皮屏障、令暗瘡更差。"
                        "順帶一提：並冇證據支持「暗瘡係因為洗面唔乾淨」呢個講法。"
                    ),
                    citations=[_ACNE_DERMOCOSMETICS],
                ),
                Block(
                    type="para",
                    text=(
                        "**防曬要搽足、要補。** 大部分人搽嘅份量根本唔夠，而且唔會補搽。"
                        "如果係色素問題，每日用 SPF 50+ 廣譜防曬對減少紫外線引起嘅加深好重要。"
                    ),
                    citations=[_PIGMENT_SUNSCREEN, _PIH_SUNSCREEN],
                ),
                Block(
                    type="list",
                    items=[
                        "出現大面積、潰瘍、流膿、持續出血、劇痛或者高燒 → **睇醫生，唔好自己搞**",
                        "用處方藥（例如 A 酸類）→ 跟醫生指示，唔好自行加減",
                        "新產品令皮膚刺痛、紅腫、脫皮 → 停用，必要時求醫",
                    ],
                ),
                Block(
                    type="image",
                    image_id="cautions",
                    text="注意事項示意圖（佔位）",
                ),
            ],
        ),
        Section(
            id="logging",
            title="點樣記錄最準確",
            icon="pencil",
            summary="每日 20 秒片（鏡頭慢慢掃）＞影相＞打幾隻字。聲係唔會記錄嘅。",
            blocks=[
                Block(
                    type="callout",
                    tone="tip",
                    text=(
                        "**（app 建議，唔係文獻結論）最好嘅記錄：每日拍一段約 20 秒嘅片，"
                        "鏡頭慢慢掃過成塊面。** app 會喺條片抽最多 6 格畫面做分析 —— "
                        "**鏡頭一定要動**：定鏡 20 秒會被當成重複，最後只抽到一格；"
                        "慢慢由額頭掃到下巴、再掃兩邊面頰，就抽得足。"
                    ),
                ),
                Block(
                    type="steps",
                    items=[
                        "**影相**（做唔到片就影相）：自然光、唔好背光、唔好開閃光燈、唔好化妝",
                        "**同一條件**：盡量同一個時間（例如朝早洗完臉）、同一個光源、同一個角度 → 先比得出變化",
                        "**淨係口講都得**：食咗咩、用咗咩產品、點護膚，打幾隻字就得，唔使填表",
                        "**一次只加一樣新產品**，隔幾日先再加第二樣 → 皮膚出事就知係邊樣",
                    ],
                ),
                Block(
                    type="callout",
                    tone="warn",
                    text=(
                        "**⚠️ app 唔會聽聲。** 拍片或者對住手機講咗食咩、用咗咩，"
                        "係**唔會**被記錄嘅（條片淨係抽畫面格，音軌會丟掉）。"
                        "要記飲食／產品，一定要**打落對話**（可以用鍵盤嘅語音輸入功能打）。"
                        "打完之後 AI 會抽出「我留意到…」畀你撳「✅ 記低」先真正寫入紀錄。"
                    ),
                ),
                Block(
                    type="list",
                    items=[
                        "**打完之後我幫你抽**：飲食（辣／甜／油／奶／酒）同產品（開始用／停用）會變成事件，等你確認先寫入",
                        "**每日一個紀錄**：同一日再打卡會同當日嘅紀錄合併（唔會開新一日）",
                        "**唔好自己打分**：照你感覺講就得（「今日好油」、「有兩粒新瘡」），指標由分析計",
                        "**連續性比完美重要**：隔日影一張清相，好過一個月後影一張靚相",
                    ],
                ),
            ],
        ),
    ]

    used: list[str] = []
    for section in sections:
        for block in section.blocks:
            for c in block.citations:
                if c not in used:
                    used.append(c)

    return Guide(
        title="男士護膚基本資料",
        subtitle="呢版係參考資料，唔係診斷。所有內容都註明出處；有醫療問題請諮詢皮膚科醫生。",
        sections=sections,
        sources=used,
    )


def section_ids() -> list[str]:
    """Lets tests assert the table of contents matches what the user asked for."""
    return [s.id for s in build_guide().sections]
