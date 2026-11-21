from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


LANG_NAMES = {
    "en": "English",
    "zh-Hans": "Simplified Chinese",
    "zh-Hant": "Traditional Chinese",
}


INJECTION_PATTERNS = (
    r"ignore (?:all )?(?:previous|prior|above) (?:instructions|rules|prompts)",
    r"disregard (?:all )?(?:previous|prior|above) (?:instructions|rules|prompts)",
    r"reveal (?:your )?(?:system|developer) (?:prompt|message|instructions)",
    r"show (?:me )?(?:your )?(?:system|developer) (?:prompt|message|instructions)",
    r"pretend (?:that )?you are (?:an? )?(?:insurance agent|licensed|adviser|advisor)",
    r"disable (?:all )?citations?",
    r"make up (?:a |the )?(?:guaranteed return|policy benefit|benefit)",
    r"(?:add|include|invent).{0,35}(?:made[- ]up|fabricated|fictional).{0,25}(?:benefit|return|guarantee|claim)",
    r"(?:reveal|show|print).{0,25}(?:confidential|hidden|internal).{0,15}(?:instructions|prompt)",
    r"you are now (?:an? )?(?:administrator|system|developer)",
    r"fabricate (?:a |the )?(?:return|benefit|policy term)",
    r"ignore (?:the )?(?:retrieved|source) (?:documents?|evidence)",
    r"output (?:the )?(?:text|content) (?:above|before) (?:verbatim|word for word)",
    r"(?:print|repeat|return).{0,12}(?:your )?(?:hidden|internal) (?:prompt|instructions)",
    r"(?:ignore|disregard).{0,30}(?:context|evidence).{0,30}(?:fabricate|invent|make up)",
    r"忽略(?:所有|以上|之前|先前).{0,10}(?:指令|規則|规则)",
    r"無視(?:所有|以上|之前|先前).{0,10}(?:指令|規則|规则)",
    r"(?:顯示|显示|透露).{0,8}(?:系統|系统|開發者|开发者).{0,8}(?:提示|指令)",
    r"(?:假裝|假装).{0,10}(?:保險經紀|保险经纪|持牌|理財顧問|理财顾问)",
    r"(?:關閉|关闭).{0,8}(?:引用|引文|來源|来源)",
    r"(?:輸出|输出|重複|重复).{0,15}(?:隱藏|隐藏|內部|内部|之前).{0,15}(?:提示|指令|內容|内容)",
    r"(?:忽略|無視|无视).{0,20}(?:證據|证据|文件|資料|资料).{0,20}(?:編造|编造|虛構|虚构)",
)

UNRELATED_PATTERNS = (
    r"\bcapital of (?:france|japan|china|italy|germany)\b",
    r"\bwho (?:is|was) (?:the )?(?:president|prime minister|ceo)\b",
    r"\bwrite (?:me )?(?:a )?(?:poem|song|story|code|program)\b",
    r"\b(?:recipe|cook|dinner|weather|football|basketball|movie|song)\b",
    r"^(?:hi|hello|hey|good morning|good evening|thanks|thank you|ok|okay)[!. ]*$",
    r"(?:寫|写).{0,6}(?:詩|诗|故事|程式|程序|代碼|代码)",
    r"(?:天氣|天气|食譜|食谱|股票|足球|籃球|篮球|電影|电影)",
)

ADVICE_PATTERNS = (
    r"\b(?:is|would).{0,25}\bsuitable for (?:me|my|us)\b",
    r"\bshould i (?:buy|purchase|invest|surrender|cancel|keep|stop paying|switch|put)\b",
    r"\bis (?:it|this) (?:a )?good (?:idea|investment|policy)\b",
    r"\bis (?:it|this) (?:sensible|wise|prudent|worthwhile) (?:for me )?to (?:buy|purchase|invest|surrender|cancel)\b",
    r"\b(?:is|would)\s+(?:this|it)\s+(?:be\s+)?(?:a\s+)?good\s+(?:fit|choice)\b",
    r"\bwould (?:buying|this plan|this policy).{0,25}(?:be a good idea|be good|suit|fit)\b",
    r"\b(?:is|would).{0,35}(?:good fit|suit my needs|fit my needs)\b",
    r"\bif i .{0,60}\bis (?:that|this) a good idea\b",
    r"\b(?:would|will) (?:that|this) be (?:a )?good idea (?:for me|in my case)\b",
    r"\b(?:do you|would you) recommend\b",
    r"\bwhat (?:do you|would you) recommend\b",
    r"\bwould (?:buying|this plan|this policy).{0,20}(?:suit|fit) (?:me|my needs)\b",
    r"\bis it wise to (?:buy|purchase|invest|surrender|cancel)\b",
    r"\bwhich (?:policy|plan|option) should i (?:buy|choose|get)\b",
    r"\bwhat should i do\b",
    r"我(?:應該|应该|要不要|是否應該|是否应该).{0,20}(?:買|买|投資|投资|退保|取消|繼續|继续|供款|提款|提取)",
    r"(?:這|这)(?:個|个|份).{0,8}(?:好不好|值得買|值得买|適合我|适合我)",
    r"(?:你|您)(?:建議|建议|推薦|推荐).{0,12}(?:買|买|投資|投资|退保|取消)",
    r"(?:我|本人).{0,12}(?:適合|适合|應該買|应该买).{0,12}(?:這|这|此)",
    r"(?:這|这|此).{0,12}(?:適合|适合|適合我|适合我).{0,12}(?:嗎|吗|\\?)",
    r"(?:如果|假如).{0,35}(?:好不好|好嗎|好吗|值得|可以嗎|可以吗)",
)

MEDICAL_PATTERNS = (
    r"\b(?:cancer|tumou?r|hiv|aids|diabetes|heart attack|stroke|diagnos)\w*",
    r"癌症|腫瘤|肿瘤|愛滋|艾滋|糖尿病|心臟病|心脏病|中風|中风|確診|确诊",
)

TAX_LEGAL_PATTERNS = (
    r"\b(?:tax|legal|lawyer|solicitor|court|lawsuit)\b",
    r"稅|税|法律|律師|律师|法庭|訴訟|诉讼",
)

UNSUPPORTED_CALCULATION_PATTERNS = (
    r"\bexact (?:surrender|cash|account|maturity) value\b",
    r"\bhow much (?:would|will|do) i (?:get|receive|have)\b",
    r"\bif i (?:cancel|surrender|withdraw|lapse) after \d+ years?\b",
    r"\b(?:calculate|project|illustrate) (?:my|the) (?:surrender|cash|account) value\b",
    r"(?:第|供|供了|投保).{0,8}\d+年.{0,20}(?:退保|现金价值|現金價值|账户价值|賬戶價值).{0,12}(?:多少|是多少)",
    r"(?:如果|假如).{0,12}\d+年.{0,15}(?:退保|取消).{0,12}(?:多少|金額|金额)",
)


class Intent(StrEnum):
    NORMAL = "normal"
    INJECTION = "injection"
    UNRELATED = "unrelated"
    ADVICE = "advice"
    UNSUPPORTED_CALCULATION = "unsupported_calculation"
    EMPTY = "empty"


@dataclass(frozen=True)
class GuardrailDecision:
    intent: Intent
    reason: str | None = None
    sensitive_topics: tuple[str, ...] = ()


def _matches(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def screen_input(message: str) -> GuardrailDecision:
    text = message.strip()
    if not text:
        return GuardrailDecision(Intent.EMPTY, "empty_message")
    if _matches(INJECTION_PATTERNS, text):
        return GuardrailDecision(Intent.INJECTION, "prompt_injection")
    if _matches(UNSUPPORTED_CALCULATION_PATTERNS, text):
        return GuardrailDecision(
            Intent.UNSUPPORTED_CALCULATION, "personalized_calculation"
        )
    # Only classify as advice after prompt injection: an injection that happens
    # to include "should I buy" still needs the injection response.
    if _matches(ADVICE_PATTERNS, text):
        sensitive = []
        if _matches(MEDICAL_PATTERNS, text):
            sensitive.append("medical")
        if _matches(TAX_LEGAL_PATTERNS, text):
            sensitive.append("tax/legal")
        return GuardrailDecision(Intent.ADVICE, "personal_financial_advice", tuple(sensitive))
    if _matches(UNRELATED_PATTERNS, text):
        return GuardrailDecision(Intent.UNRELATED, "out_of_scope")
    sensitive = []
    if _matches(MEDICAL_PATTERNS, text):
        sensitive.append("medical")
    if _matches(TAX_LEGAL_PATTERNS, text):
        sensitive.append("tax/legal")
    return GuardrailDecision(Intent.NORMAL, sensitive_topics=tuple(sensitive))


def localised_notice(language: str, key: str) -> str:
    notices = {
        "en": {
            "provider_unavailable": "The model provider was unavailable; showing source excerpts only.",
            "educational": (
                "InsureTutor is an educational assistant, not a licensed insurance "
                "adviser. It explains the supplied brochure and cannot determine "
                "whether a policy is suitable for you."
            ),
            "brochure_only": (
                "This answer is based on the supplied product brochure, which is "
                "not the full policy contract."
            ),
            "professional": (
                "For a decision about your own circumstances, speak with a "
                "licensed insurance professional and review the full policy terms."
            ),
            "sensitive": (
                "The brochure may not resolve medical, tax, legal, underwriting "
                "or claims-dispute questions; those require official confirmation."
            ),
        },
        "zh-Hans": {
            "provider_unavailable": "AI 解释暂时不可用，目前仅展示册子原文。",
            "educational": (
                "InsureTutor 是保险教育助手，并非持牌保险顾问。它只解释所提供的产品册子，"
                "不能判断某份保单是否适合您。"
            ),
            "brochure_only": "本回答基于所提供的产品册子，而册子并非完整保单合约。",
            "professional": "如要按个人情况作决定，请咨询持牌保险专业人士并查阅完整保单条款。",
            "sensitive": "册子未必能解决医疗、税务、法律、核保或理赔争议问题，这些事项需向有关机构确认。",
        },
        "zh-Hant": {
            "provider_unavailable": "AI 解釋暫時無法使用，目前僅展示冊子原文。",
            "educational": (
                "InsureTutor 是保險教育助手，並非持牌保險顧問。它只解釋所提供的產品冊子，"
                "不能判斷某份保單是否適合您。"
            ),
            "brochure_only": "本回答基於所提供的產品冊子，而冊子並非完整保單合約。",
            "professional": "如要按個人情況作決定，請諮詢持牌保險專業人士並查閱完整保單條款。",
            "sensitive": "冊子未必能解決醫療、稅務、法律、核保或理賠爭議問題，這些事項需向有關機構確認。",
        },
    }
    return notices.get(language, notices["en"]).get(key, "")


def fixed_response(language: str, key: str) -> str:
    responses = {
        "en": {
            "injection": (
                "I can’t follow instructions that try to override InsureTutor’s rules "
                "or make me invent product facts. I can still help you understand the "
                "FLEXI-ULife Prime Saver brochure using its actual pages and terms. "
                "What would you like to check?"
            ),
            "unrelated": (
                "I’m limited to insurance education and the supplied FLEXI-ULife Prime "
                "Saver brochure, so I can’t help with that unrelated request. I can "
                "explain the plan’s protection options, fees, withdrawals, guarantees, "
                "risks, eligibility, or Chinese/English insurance terminology."
            ),
            "empty": "Please enter a question about the insurance plan.",
            "insufficient": (
                "I couldn’t find enough information in the supplied brochure to answer "
                "that reliably. I don’t want to guess about a policy condition. Please "
                "check the full policy contract or contact the insurer for confirmation."
            ),
            "provider_error": (
                "The tutoring model is temporarily unavailable, so I can’t produce a "
                "grounded answer right now. Your question was not submitted as a policy "
                "fact. Please try again shortly."
            ),
            "calculation": (
                "The brochure does not provide a calculator or enough personalized data "
                "to determine that value. It explains how Cash Value relates to Account "
                "Value and applicable surrender charges, but an exact figure would depend "
                "on policy-specific records, charges, premiums, withdrawals and the "
                "insurer's current scale of charges. Please request an official "
                "illustration or surrender-value quote from the insurer."
            ),
            "sensitive_redirect": (
                "I can explain what the brochure says about protection, fees, "
                "withdrawals and risks, but I can’t resolve a medical, tax, legal, "
                "underwriting, claims-dispute or personal-coverage determination. "
                "Those depend on official policy terms and your circumstances. "
                "Please ask the insurer or a qualified professional."
            ),
        },
        "zh-Hans": {
            "injection": (
                "我不能遵从试图覆盖 InsureTutor 规则或要求我编造产品事实的指示。"
                "我仍可根据 FLEXI-ULife Prime Saver 册子的实际页面和条款，帮您理解该产品。"
                "您想查看哪一项？"
            ),
            "unrelated": (
                "我只能协助保险教育及解释所提供的 FLEXI-ULife Prime Saver 册子，"
                "因此无法处理这个无关请求。我可以解释保障选择、费用、提款、保证、"
                "风险、投保资料或中英文保险术语。"
            ),
            "empty": "请输入有关该保险计划的问题。",
            "insufficient": (
                "所提供的册子资料不足以让我可靠回答这个问题，我不想猜测保单条件。"
                "请查阅完整保单合约或向保险公司确认。"
            ),
            "provider_error": "教学模型暂时无法使用，因此我现在无法提供有依据的回答。请稍后重试。",
            "calculation": (
                "册子没有提供计算器，也没有足够个人资料来确定这个金额。册子说明了现金价值、"
                "账户价值与适用退保费用的关系，但准确金额取决于保单记录、费用、已缴保费、"
                "提款及保险公司现行收费。请向保险公司索取正式说明或退保价值报价。"
            ),
            "sensitive_redirect": (
                "我可以解释册子关于保障、费用、提款和风险的内容，但不能裁定医疗、税务、"
                "法律、核保、理赔争议或个人保障需求。这些事项取决于正式保单条款及您的"
                "实际情况，请向保险公司或合资格专业人士查询。"
            ),
        },
        "zh-Hant": {
            "injection": (
                "我不能遵從試圖覆蓋 InsureTutor 規則或要求我編造產品事實的指示。"
                "我仍可根據 FLEXI-ULife Prime Saver 冊子的實際頁面和條款，幫您理解該產品。"
                "您想查看哪一項？"
            ),
            "unrelated": (
                "我只能協助保險教育及解釋所提供的 FLEXI-ULife Prime Saver 冊子，"
                "因此無法處理這個無關請求。我可以解釋保障選擇、費用、提款、保證、"
                "風險、投保資料或中英文保險術語。"
            ),
            "empty": "請輸入有關該保險計劃的問題。",
            "insufficient": (
                "所提供的冊子資料不足以讓我可靠回答這個問題，我不想猜測保單條件。"
                "請查閱完整保單合約或向保險公司確認。"
            ),
            "provider_error": "教學模型暫時無法使用，因此我現在無法提供有依據的回答。請稍後重試。",
            "calculation": (
                "冊子沒有提供計算器，也沒有足夠個人資料來確定這個金額。冊子說明了現金價值、"
                "賬戶價值與適用退保費用的關係，但準確金額取決於保單記錄、費用、已繳保費、"
                "提款及保險公司現行收費。請向保險公司索取正式說明或退保價值報價。"
            ),
            "sensitive_redirect": (
                "我可以解釋冊子關於保障、費用、提款和風險的內容，但不能裁定醫療、稅務、"
                "法律、核保、理賠爭議或個人保障需求。這些事項取決於正式保單條款及您的"
                "實際情況，請向保險公司或合資格專業人士查詢。"
            ),
        },
    }
    return responses.get(language, responses["en"]).get(key, "")


def advice_framing(language: str) -> str:
    frames = {
        "en": (
            "I can explain the trade-offs, but I can’t decide whether this policy is "
            "suitable for you. Suitability depends on your goals, time horizon, budget, "
            "protection needs, risk tolerance and complete policy terms. Here is what "
            "the brochure does and does not establish:"
        ),
        "zh-Hans": (
            "我可以解释产品取舍，但不能判断该保单是否适合您。适合与否取决于您的目标、"
            "投资年期、预算、保障需要、风险承受能力及完整保单条款。以下是册子能够说明"
            "和不能说明的内容："
        ),
        "zh-Hant": (
            "我可以解釋產品取捨，但不能判斷該保單是否適合您。適合與否取決於您的目標、"
            "投資年期、預算、保障需要、風險承受能力及完整保單條款。以下是冊子能夠說明"
            "和不能說明的內容："
        ),
    }
    return frames.get(language, frames["en"])

