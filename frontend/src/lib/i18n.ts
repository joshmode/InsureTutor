import type { LanguageCode } from "./types";

export const LANGUAGES: {
  code: LanguageCode;
  short: string;
  native: string;
  english: string;
}[] = [
  { code: "en", short: "EN", native: "English", english: "English" },
  { code: "zh-Hans", short: "简", native: "简体中文", english: "Simplified Chinese" },
  { code: "zh-Hant", short: "繁", native: "繁體中文", english: "Traditional Chinese" },
];

type Copy = {
  productEyebrow: string;
  productName: string;
  productSubtitle: string;
  sourceTitle: string;
  sourceBody: string;
  viewSource: string;
  newChat: string;
  welcomeKicker: string;
  welcomeTitle: string;
  welcomeBody: string;
  suggestionsLabel: string;
  suggestions: { title: string; prompt: string }[];
  composerPlaceholder: string;
  send: string;
  stop: string;
  disclaimer: string;
  sources: string;
  citations: string;
  noSources: string;
  loading: string;
  retry: string;
  errorTitle: string;
  errorBody: string;
  copied: string;
  copy: string;
  close: string;
  page: string;
  section: string;
  excerpt: string;
  openPdf: string;
  language: string;
  scopeNote: string;
  insufficientNote: string;
  retrievalMode: string;
  educationalBadge: string;
  companionTitle: string;
  companionBody: string;
  planFacts: { label: string; value: string }[];
  structuredNotice: string;
  sourceDrawerKicker: string;
  sourceDrawerBody: string;
  mobileSources: string;
  chatEmptyPrompt: string;
};

const en: Copy = {
  productEyebrow: "YF Life · Universal Life",
  productName: "FLEXI-ULife Prime Saver",
  productSubtitle: "Understand the plan before you decide",
  sourceTitle: "Grounded in the brochure",
  sourceBody:
    "Answers are retrieved from the supplied 20-page product brochure. The brochure is not the full policy contract.",
  viewSource: "View source PDF",
  newChat: "New conversation",
  welcomeKicker: "Your insurance tutor",
  welcomeTitle: "Insurance, in language that makes sense.",
  welcomeBody:
    "Ask about protection, cash value, fees or risk. Every product answer shows the exact brochure page behind it, so you can check the source yourself.",
  suggestionsLabel: "Start with a question",
  suggestions: [
    {
      title: "The basics",
      prompt: "Explain FLEXI-ULife Prime Saver to me like I’m 18 and have never bought insurance.",
    },
    {
      title: "The 4% rate",
      prompt: "Is the 4% interest rate guaranteed? What does the 2.5% guarantee actually mean?",
    },
    {
      title: "Withdrawing money",
      prompt: "What happens if I keep withdrawing money from the policy?",
    },
    {
      title: "Compare protection",
      prompt: "What is the difference between Level Benefit and Increasing Benefit?",
    },
  ],
  composerPlaceholder: "Ask about this insurance plan…",
  send: "Send question",
  stop: "Stop",
  disclaimer:
    "Educational assistant only — not a licensed adviser. Product answers are grounded in the supplied brochure, not your personal circumstances.",
  sources: "Sources",
  citations: "citations",
  noSources: "No source passages were used.",
  loading: "Checking the brochure",
  retry: "Try again",
  errorTitle: "The tutor couldn’t respond",
  errorBody: "Your message was not lost. Check the model configuration and try again.",
  copied: "Copied",
  copy: "Copy answer",
  close: "Close",
  page: "Page",
  section: "Section",
  excerpt: "Source excerpt",
  openPdf: "Open brochure",
  language: "Answer language",
  scopeNote: "Outside the tutor’s scope",
  insufficientNote: "Not enough support in the brochure",
  retrievalMode: "Retrieval",
  educationalBadge: "Educational only",
  companionTitle: "What this plan is",
  companionBody:
    "A universal life plan combining life protection with a savings/account-value component. Some illustrated rates and bonuses are not guaranteed.",
  planFacts: [
    { label: "Document", value: "Product brochure · Jan 2022" },
    { label: "Pages indexed", value: "20 pages" },
    { label: "Protection term", value: "Up to age 100" },
    { label: "Optional add-ons", value: "Not automatically included" },
  ],
  structuredNotice:
    "Product facts come from retrieved brochure passages. Click a citation to inspect the source.",
  sourceDrawerKicker: "Evidence trail",
  sourceDrawerBody:
    "Each numbered citation maps to a real page in the supplied brochure. Excerpts are verbatim retrieval text.",
  mobileSources: "Sources",
  chatEmptyPrompt: "Ask anything about the plan. Start simple — there is no such thing as a basic question here.",
};

const zhHans: Copy = {
  productEyebrow: "万通保险 · 万用寿险",
  productName: "FLEXI-ULife Prime Saver",
  productSubtitle: "先理解计划，再作决定",
  sourceTitle: "以产品册子为依据",
  sourceBody: "回答取自所提供的 20 页产品册子。册子并非完整保单合约。",
  viewSource: "查看原始 PDF",
  newChat: "新对话",
  welcomeKicker: "您的保险学习助手",
  welcomeTitle: "把保险讲清楚，再谈选择。",
  welcomeBody:
    "您可以询问保障、现金价值、费用或风险。每个产品答案都会显示册子的具体页码，方便您自行核对原文。",
  suggestionsLabel: "从一个问题开始",
  suggestions: [
    { title: "先了解产品", prompt: "请用完全没买过保险的 18 岁年轻人也听得懂的方式解释这份计划。" },
    { title: "4% 利率", prompt: "这个保险的 4% 利息是保证的吗？2.5% 的保证又是什么意思？" },
    { title: "提取现金", prompt: "如果我持续从保单提款，会发生什么？" },
    { title: "比较保障", prompt: "固定寿险保障和递增寿险保障有什么区别？" },
  ],
  composerPlaceholder: "询问这份保险计划…",
  send: "发送问题",
  stop: "停止",
  disclaimer: "仅供保险教育，并非持牌顾问。产品回答以册子为依据，不考虑您的个人情况。",
  sources: "资料来源",
  citations: "条引用",
  noSources: "此回答没有使用来源段落。",
  loading: "正在查阅册子",
  retry: "重试",
  errorTitle: "暂时无法回答",
  errorBody: "您的信息没有丢失。请检查模型配置后重试。",
  copied: "已复制",
  copy: "复制回答",
  close: "关闭",
  page: "第",
  section: "章节",
  excerpt: "原文节录",
  openPdf: "打开册子",
  language: "回答语言",
  scopeNote: "超出助手范围",
  insufficientNote: "册子资料不足",
  retrievalMode: "检索",
  educationalBadge: "仅供教育",
  companionTitle: "这是一个什么计划",
  companionBody:
    "结合身故保障与储蓄／账户价值成分的万用寿险。部分示例利率与奖赏并非保证。",
  planFacts: [
    { label: "文件", value: "产品册子 · 2022 年 1 月" },
    { label: "索引页数", value: "20 页" },
    { label: "保障年期", value: "至 100 岁" },
    { label: "附加保障", value: "不会自动包括" },
  ],
  structuredNotice: "产品事实来自检索到的册子段落。点击引用即可查看原文。",
  sourceDrawerKicker: "证据链",
  sourceDrawerBody: "每条编号引用都对应册子中的真实页面。节录为检索到的原文。",
  mobileSources: "来源",
  chatEmptyPrompt: "关于这份计划，尽管问。可以从最简单的问题开始。",
};

const zhHant: Copy = {
  ...zhHans,
  productEyebrow: "萬通保險 · 萬用壽險",
  productSubtitle: "先理解計劃，再作決定",
  sourceTitle: "以產品冊子為依據",
  sourceBody: "回答取自所提供的 20 頁產品冊子。冊子並非完整保單合約。",
  viewSource: "查看原始 PDF",
  newChat: "新對話",
  welcomeKicker: "您的保險學習助手",
  welcomeTitle: "把保險講清楚，再談選擇。",
  welcomeBody:
    "您可以詢問保障、現金價值、費用或風險。每個產品答案都會顯示冊子的具體頁碼，方便您自行核對原文。",
  suggestionsLabel: "從一個問題開始",
  suggestions: [
    { title: "先了解產品", prompt: "請用完全沒買過保險的 18 歲年輕人也聽得懂的方式解釋這份計劃。" },
    { title: "4% 利率", prompt: "這個保險的 4% 利息是保證的嗎？2.5% 的保證又是什麼意思？" },
    { title: "提取現金", prompt: "如果我持續從保單提款，會發生什麼？" },
    { title: "比較保障", prompt: "固定壽險保障和遞增壽險保障有什麼區別？" },
  ],
  composerPlaceholder: "詢問這份保險計劃…",
  send: "發送問題",
  stop: "停止",
  disclaimer: "僅供保險教育，並非持牌顧問。產品回答以冊子為依據，不考慮您的個人情況。",
  sources: "資料來源",
  citations: "條引用",
  noSources: "此回答沒有使用來源段落。",
  loading: "正在查閱冊子",
  retry: "重試",
  errorTitle: "暫時無法回答",
  errorBody: "您的信息沒有丟失。請檢查模型配置後重試。",
  copied: "已複製",
  copy: "複製回答",
  close: "關閉",
  page: "第",
  section: "章節",
  excerpt: "原文節錄",
  openPdf: "打開冊子",
  language: "回答語言",
  scopeNote: "超出助手範圍",
  insufficientNote: "冊子資料不足",
  retrievalMode: "檢索",
  educationalBadge: "僅供教育",
  companionTitle: "這是一個什麼計劃",
  companionBody:
    "結合身故保障與儲蓄／賬戶價值成分的萬用壽險。部分示例利率與獎賞並非保證。",
  planFacts: [
    { label: "文件", value: "產品冊子 · 2022 年 1 月" },
    { label: "索引頁數", value: "20 頁" },
    { label: "保障年期", value: "至 100 歲" },
    { label: "附加保障", value: "不會自動包括" },
  ],
  structuredNotice: "產品事實來自檢索到的冊子段落。點擊引用即可查看原文。",
  sourceDrawerKicker: "證據鏈",
  sourceDrawerBody: "每條編號引用都對應冊子中的真實頁面。節錄為檢索到的原文。",
  mobileSources: "來源",
  chatEmptyPrompt: "關於這份計劃，儘管問。可以從最簡單的問題開始。",
};

export const COPY: Record<LanguageCode, Copy> = {
  en,
  "zh-Hans": zhHans,
  "zh-Hant": zhHant,
};

