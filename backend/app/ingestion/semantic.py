from __future__ import annotations

"""Small, deterministic bilingual annotations for insurance-domain retrieval.

The source brochure is bilingual but queries can use vocabulary that the
brochure expresses differently (for example "cash out" vs "withdrawal"). These
aliases are appended only to the search representation; the citation excerpt
always stays verbatim from the source.
"""

import re


CONCEPTS: dict[str, tuple[str, ...]] = {
    "interest": (
        "interest rate 4% 4.0% 0.25% 2.5% guaranteed non-guaranteed assumed rate",
        "利息 派息率 息率 保證 非保證 假設 長線利率保證",
    ),
    "bonus": (
        "extra bonus retrospective additional interest 2.75% 5.5% every five years",
        "額外回報 額外利息 紅利 獎賞 2.75% 5.5% 每5年",
    ),
    "withdrawal": (
        "withdraw cash value automatic periodic withdrawal surrender charge monthly charges lapse",
        "提款 提取現金 現金價值 定期提款 退保費用 每月費用 保單失效 斷單",
    ),
    "level": (
        "Level Benefit account value basic sum insured death benefit savings",
        "固定壽險保障 身故保障 賬戶價值 基本保障額 儲蓄",
    ),
    "increasing": (
        "Increasing Benefit Increasing Benefit Plus death benefit capital growth",
        "遞增壽險保障 特級遞增壽險保障 身故保障 資金增長",
    ),
    "incremental": (
        "Incremental Benefit 50% account value balancing savings protection",
        "漸進壽險保障 賬戶價值的50% 平衡保障 儲蓄",
    ),
    "charges": (
        "premium expense charge cost of insurance administrative charge surrender charge withdrawal charge",
        "保費行政費用 保險成本 一般行政費用 退保費用 提款費用 收費",
    ),
    "flexibility": (
        "increase decrease sum insured policy enhancement guaranteed insurability skip premium",
        "增加保障額 減少保障額 保單增值權益 保證可保權益 暫停繳付保費 保費彈性",
    ),
    "protection": (
        "unemployment terminal illness supplementary waiver critical illness accident",
        "失業保障 末期病症 附加保障 豁免保費 嚴重疾病 意外保障",
    ),
    "risk": (
        "early surrender inflation credit risk lapse exclusions duty disclosure cooling off",
        "提早退保 通脹風險 信貸風險 保單失效 不保事項 提供資料責任 冷靜期",
    ),
    "account": (
        "account value cash value premium charges interest death benefit",
        "賬戶價值 現金價值 保費 費用 利息 身故保障",
    ),
    "eligibility": (
        "issue age benefit term premium payment term currency currencies",
        "投保年齡 保障年期 繳付保費年期 貨幣",
    ),
    "currency": (
        "policy currency currencies Hong Kong US$ HK$ Macau MOP",
        "保單貨幣 货币 港元 美元 澳門元",
    ),
    "payment": (
        "payment mode annual semi-annual quarterly monthly",
        "繳費方式 每年 每半年 每季 每月",
    ),
}

TRIGGERS: dict[str, tuple[str, ...]] = {
    "interest": (
        "interest",
        "rate",
        "4%",
        "2.5",
        "利息",
        "利率",
        "息率",
        "派息",
        "保证",
        "保證",
    ),
    "bonus": (
        "bonus",
        "retrospective",
        "extra",
        "奖金",
        "獎金",
        "红利",
        "紅利",
        "额外",
        "額外",
    ),
    "withdrawal": (
        "withdraw",
        "cash out",
        "surrender",
        "lapse",
        "提款",
        "提取",
        "退保",
        "断单",
        "斷單",
        "取钱",
        "取錢",
    ),
    "level": ("level benefit", "fixed benefit", "固定寿险", "固定壽險", "level"),
    "increasing": ("increasing benefit", "plus", "递增", "遞增", "特级", "特級"),
    "incremental": ("incremental", "渐进", "漸進"),
    "charges": (
        "charge",
        "fee",
        "cost of insurance",
        "费用",
        "費用",
        "收费",
        "收費",
        "成本",
    ),
    "flexibility": (
        "flexib",
        "skip",
        "suspend premium",
        "increase cover",
        "灵活",
        "靈活",
        "暂停",
        "暫停",
        "加保",
    ),
    "protection": (
        "unemployment",
        "terminal",
        "supplementary",
        "waiver",
        "失业",
        "失業",
        "末期",
        "附加",
        "豁免",
    ),
    "risk": (
        "risk",
        "exclusion",
        "lapse",
        "inflation",
        "credit",
        "风险",
        "風險",
        "不保",
        "通胀",
        "通脹",
    ),
    "account": ("account value", "cash value", "账户", "賬戶", "现金价值", "現金價值"),
    "eligibility": (
        "age",
        "eligible",
        "eligibility",
        "term",
        "currency",
        "policy issued",
        "年龄",
        "年齡",
        "年期",
        "货币",
        "貨幣",
    ),
}

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "could",
    "do",
    "does",
    "for",
    "from",
    "how",
    "i",
    "if",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "please",
    "should",
    "so",
    "the",
    "this",
    "that",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "will",
    "with",
    "under",
    "would",
    "you",
    "your",
    "tell",
    "about",
    "explain",
}

STOP_CJK = {
    "的",
    "了",
    "是",
    "我",
    "你",
    "吗",
    "呢",
    "吧",
    "請",
    "请",
    "這",
    "这",
    "個",
    "个",
    "嗎",
}


def expand_query(text: str, all_concepts: bool = False) -> str:
    lower = text.lower()
    additions: list[str] = []
    if any(trigger in lower for trigger in ("currenc", "货币", "貨幣")):
        additions.extend(CONCEPTS["currency"])
    if any(trigger in lower for trigger in ("payment mode", "缴费方式", "繳費方式")):
        additions.extend(CONCEPTS["payment"])
    for concept, triggers in TRIGGERS.items():
        if all_concepts or any(trigger in lower for trigger in triggers):
            additions.extend(CONCEPTS[concept])
    if not additions:
        return text
    return f"{text}\n\nDomain vocabulary: {' '.join(additions)}"


def _stem(word: str) -> str:
    # Deliberately conservative stemming for insurance retrieval. This is not
    # a linguistic stemmer, just enough to match common inflections without
    # conflating policy terms.
    for suffix, replacement in (
        ("guaranteed", "guarantee"),
        ("withdrawals", "withdraw"),
        ("withdrawal", "withdraw"),
        ("withdrawing", "withdraw"),
        ("charges", "charge"),
        ("charged", "charge"),
        ("payments", "premium"),
        ("modes", "mode"),
        ("premiums", "premium"),
        ("benefits", "benefit"),
        ("years", "year"),
        ("surrender", "surrender"),
        ("increasing", "increase"),
        ("increased", "increase"),
        ("crediting", "credit"),
        ("credited", "credit"),
        ("interest", "interest"),
        ("fees", "fee"),
        ("claims", "claim"),
        ("miss", "skip"),
        ("missing", "skip"),
        ("skipping", "skip"),
    ):
        if word == suffix:
            return replacement
    if word.endswith("ies") and len(word) > 4 and word not in {"series", "species"}:
        return word[:-3] + "y"
    return word


def tokenize(text: str) -> list[str]:
    """Tokenize English words and Chinese character bigrams.

    Character bigrams are a lightweight, deterministic alternative to a
    language-specific tokenizer and work for both Simplified and Traditional
    Chinese. They are only used for lexical ranking; excerpts are untouched.
    """
    text = normalize_term(text)
    text = re.sub(r"[！？。；，、,.!?;:]+", " ", text)
    words = [
        _stem(word)
        for word in re.findall(r"[a-z0-9]+(?:[.%][a-z0-9]+)*", text)
        if word not in STOP_WORDS and len(word) >= 2
    ]
    cjk = re.findall(r"[\u3400-\u9fff]", text)
    tokens: list[str] = words[:]
    # Segment at punctuation/whitespace rather than taking bigrams across the
    # whole page, which otherwise creates nonsensical cross-clause tokens.
    for run in re.findall(r"[\u3400-\u9fff]{2,}", text):
        if len(run) <= 6 or any(
            concept in run
            for concept in (
                "保險",
                "保险",
                "保單",
                "保单",
                "現金",
                "现金",
                "利息",
                "保證",
                "保证",
            )
        ):
            tokens.append(run)
        for i in range(len(run) - 1):
            bigram = run[i : i + 2]
            if bigram not in STOP_CJK:
                tokens.append(bigram)
    return tokens


def phrase_tokens(text: str) -> list[str]:
    """Return normalized words/phrases for literal evidence coverage checks."""
    normalized = normalize_term(text)
    words = [
        _stem(word)
        for word in re.findall(r"[a-z0-9]+(?:[.%][a-z0-9]+)*", normalized)
        if word not in STOP_WORDS and len(word) >= 2
    ]
    phrases: list[str] = []
    for run in re.findall(r"[\u3400-\u9fff]{2,}", normalized):
        phrases.append(run)
        # Words are normally two to four characters; character bigrams provide
        # a fallback for short term variants such as 简体/繁體.
        phrases.extend(run[i : i + 2] for i in range(len(run) - 1))
    return words + phrases


# Small reviewed script normalization for the bilingual source vocabulary.
# This is retrieval-only; quotations always preserve the original PDF text.
CJK_VARIANTS = str.maketrans(
    "险单证递续从发时这个为么费护释计现价财语轻岁买没听会吗额账钱优长开关过划寿区别继静偿",
    "險單證遞續從發時這個為麼費護釋計現價財語輕歲買沒聽會嗎額賬錢優長開關過劃壽區別繼靜償",
)


def normalize_term(text: str) -> str:
    text = text.lower().translate(CJK_VARIANTS)
    text = text.replace("percentage", "%").replace("percent", "%")
    text = re.sub(r"(?<=\d)\s*%", "%", text)
    return text
