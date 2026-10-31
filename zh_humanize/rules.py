# -*- coding: utf-8 -*-
"""规则表。

每条规则都带证据等级。等级不是「可信度打分」，而是「这条规则在配对实测里
站不站得住、以及该不该动手改」：

A  两轮同向、可定位、默认建议改
B  条件显著或弱一档，复核后改
C  整篇分布，只报告，不为凑数值改
F  单模型指纹，方向随模型变，不定罪
X  已否决：实测与人类无差异或方向相反，永不据此删改

证据主要来自两组公开的中文对照实测：
  第一轮 629 篇（AI 300 / 人类 329）
  第二轮 270 对同题同事实配对复测
出处见 README「证据」一节。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    grade: str
    kind: str
    evidence: str
    why: str
    fix: str
    threshold: float = 0.0
    reference: str = ""
    patterns: Tuple[str, ...] = ()


RULES: Tuple[Rule, ...] = (
    Rule(
        id="antithesis",
        name="翻案腔 / 对举",
        grade="A",
        kind="pattern",
        evidence="配对复测 GPT δ+0.88 / Opus δ+0.72；第一轮 3.4 倍",
        why="先替读者立一个他并没有的误解，再推翻。判断被拆成两半，信息量没有增加。",
        fix="直接给正面判断，先结论后依据；不要为了保留对比而把反面整句删掉。",
        threshold=0.3,
        reference="人类约 0.22 次/千字",
        patterns=(
            r"不是[^。！？\n]{1,30}?[，,]?\s*而是",
            r"并非[^。！？\n]{1,30}?[，,]?\s*而是",
            r"不在于[^。！？\n]{1,30}?[，,]?\s*而在于",
            r"与其说[^。！？\n]{1,30}?[，,]?\s*不如说",
            r"看似[^。！？\n]{1,20}?[，,]?\s*(?:实则|其实|实际上?)",
            r"表面上?[^。！？\n]{0,15}?[，,]\s*实际上?",
        ),
    ),
    Rule(
        id="cue_colon",
        name="提示语冒号",
        grade="A",
        kind="pattern",
        evidence="第一轮 3.8 倍；配对复测语义层 2.1 倍",
        why="冒号前那半句只负责宣告「下面有结论」，本身不承载信息。",
        fix="提示语不承担信息就删掉直接写；前句承接上文时只把冒号换成句号或逗号。",
        threshold=0.2,
        reference="人类约 0.08 次/千字",
    ),
    Rule(
        id="long_premodifier",
        name="过长前置定语",
        grade="A",
        kind="pattern",
        evidence="第一轮 0.42 次/千字；配对复测 GPT δ+0.48 / Opus δ+0.54",
        why="中心词前挂了十五字以上的修饰，读者要等到句末才知道主语是什么。这是翻译腔里最稳的一种。",
        fix="拆成两个分句：先让主语和动作出现，再把条件、范围、修饰接上。",
        threshold=0.3,
        reference="人类明显更低",
    ),
    Rule(
        id="dense_enum",
        name="顿号密集罗列",
        grade="A",
        kind="pattern",
        evidence="第一轮 AI 3.21 / 人类 1.78；配对复测 1.45 倍",
        why="一个分句里连排三项以上，用顿号把不同维度的东西压平成同一结构。",
        fix="能概括就概括；必须保留时改变其中一项的句法，不让它们排成同一队。",
        threshold=2.0,
        reference="人类约 1.78 次/千字",
    ),
    Rule(
        id="opening_scaffold",
        name="起手式",
        grade="A",
        kind="pattern",
        evidence="第一轮 3.2 倍，量小但稳定",
        why="「说白了」「说穿了」「先说结论」是给下面的话加注意力，不是内容。",
        fix="删掉，直接给判断。",
        threshold=0.15,
        reference="接近 0",
        patterns=(r"说白了|说穿了|先说结论|直说吧|不客气地说",),
    ),
    Rule(
        id="translationese_shell",
        name="话题壳与时间从句",
        grade="B",
        kind="pattern",
        evidence="翻译腔 18 种筛到 4 种后保留；方向稳定，强度中等",
        why="「对于……来说」「在……方面」「当……时」把本来可以直接说的主语推到壳子后面。",
        fix="删壳让从句直接作前一分句；删掉会让时间关系变模糊的保留。",
        threshold=0.3,
        reference="—",
        patterns=(
            r"当[^。！？\n]{2,40}?时[，,]",
            r"对于[^。！？\n]{1,20}?来说[，,]",
            r"就[^。！？\n]{1,20}?而言[，,]",
            r"在[^。！？\n]{1,20}?方面[，,]",
        ),
    ),
    Rule(
        id="connector_initial",
        name="句首连接词当路标",
        grade="B",
        kind="pattern",
        evidence="翻译腔四型之一；连续段落同款开头时最明显",
        why="「然而，」「因此，」「此外，」替读者标好了转折，读者不用自己判断。",
        fix="移到主语后，或换成「不过」「其实」；论证确实需要显式路标时不改。",
        threshold=1.0,
        reference="—",
        patterns=(
            r"(?:^|[。！？\n])\s*(?:然而|因此|此外|同时|另外|实际上|事实上|更重要的是|换言之|值得注意的是|需要指出的是|综上所述|总的来说|由此可见)[，,]",
        ),
    ),
    Rule(
        id="adjacent_isomorphism",
        name="相邻句骨架复刻",
        grade="B",
        kind="structure",
        evidence="第一轮每百段 9.41 / 4.81；配对复测 1.6 倍，三连 2.75 倍",
        why="相邻几句的逗号位置、成分顺序、收尾方式完全一样，读起来像模板填空。",
        fix="打散其中一句：合并、拆分、换语序或改短句。只改句内，不动段落顺序。",
        threshold=0.5,
        reference="—",
    ),
    Rule(
        id="chain",
        name="段间衔接连环",
        grade="B",
        kind="structure",
        evidence="明确承接 AI 98.9% vs 人类 95.2%；段间跳转 AI 2.1% vs 人类 7.2%",
        why="每段都接住上一段末句，读者全程被动，不需要自己建立联系。",
        fix="在连环里选一两处直接切话题，让话题跟着材料走。承担因果或伏笔功能的接口不改。",
        threshold=3.0,
        reference="人类约每 14 段跳一次",
    ),
    Rule(
        id="synonym_rotation",
        name="同义轮换",
        grade="B",
        kind="structure",
        evidence="配对复测 AI 0.83–0.86 次/段 vs 人类 0.49（单模型判据，弱一档）",
        why="同一概念在一段里换着说法，读者要做「X 就是 Y」的额外连接。",
        fix="统一回原名。人类范本本来就是反复用同一个词。",
        threshold=0.8,
        reference="人类约 0.49 次/段",
    ),
    Rule(
        id="sentence_cv",
        name="句长离散度",
        grade="C",
        kind="distribution",
        evidence="第一轮 0.87 倍；配对复测两轮均无差异",
        why="流行说法是「AI 句子太齐」，但配对语料里人机没有稳定差异。",
        fix="只报告，不为凑 CV 把句子改得忽长忽短。机械参差化比不改更糟。",
        reference="配对复测人类约 0.54",
    ),
    Rule(
        id="paragraph_cv",
        name="段落长度离散度",
        grade="C",
        kind="distribution",
        evidence="弱信号，仅作结构参考",
        why="通篇段落等长会显得像卡片，但这不是稳定的人机差异。",
        fix="只在确有阅读障碍时调整；不按配额拆合段落。",
        reference="—",
    ),
    Rule(
        id="section_geometry",
        name="小标题切得过碎",
        grade="C",
        kind="distribution",
        evidence="节长方差 δ−0.91/−0.75；小标题密度 δ+0.65/+0.83；每节句数 δ−0.63/−0.79",
        why="三千字的文章切成七八节，每节两三句，像是先列大纲再填空。",
        fix="只报告。合并小节属于结构改动，需作者决定。",
        reference="AI 中位 7 节 vs 人类 1 节",
    ),
    Rule(
        id="lexical_diversity",
        name="词汇多样性（字符代理）",
        grade="C",
        kind="distribution",
        evidence="配对复测 MTLD/MATTR 生成侧更高：GPT δ+0.91/+0.75，Opus δ+0.55/+0.55",
        why="AI 不敢重复用词，同段反复换同义词；人类会原词重用。方向与直觉相反。本工具用无分词的字符代理测，绝对值不可与论文数字对标。",
        fix="只报告。要降多样性，靠同义轮换规则统一原名，不靠堆生僻词。",
        reference="AI 更高",
    ),
    Rule(
        id="dash",
        name="破折号",
        grade="F",
        kind="fingerprint",
        evidence="GPT −0.54（比人类还少）/ Opus +0.95（100% 文章使用）",
        why="破折号是模型使用偏好，不是 AI 共性。方向完全取决于文本像谁。",
        fix=">2/千字时逐处检查；承担必要强调或人物语气时保留。缺失不补。",
        threshold=2.0,
        reference="人类约 0.80 次/千字",
    ),
    Rule(
        id="semicolon",
        name="分号",
        grade="F",
        kind="fingerprint",
        evidence="GPT δ+0.80；Opus δ−0.11",
        why="分号把多个层次压进一句，是 GPT 系的偏好，不是所有模型。",
        fix="逐处看能否安全拆成句号；确有并列层级时保留。",
        threshold=1.5,
        reference="—",
    ),
    Rule(
        id="question_ratio",
        name="问句",
        grade="X",
        kind="rejected",
        evidence="GPT δ−0.59（人类更多）；问句小标题按占比算无差异",
        why="「AI 爱用问句」是分母陷阱：AI 小标题本来就多。",
        fix="永不删问句、设问和问句小标题。删了更像 AI。",
        reference="人类更多",
    ),
    Rule(
        id="blacklist_words",
        name="漂亮词黑名单",
        grade="X",
        kind="rejected",
        evidence="配对复测 δ+0.10，不显著",
        why="赋能、闭环、抓手、底层逻辑这些词被当成 AI 味代表，但同题同事实配对后与人类无差异。",
        fix="永不据此删改。词本身不构成判断，句子的组织方式才构成。",
        reference="无差异",
    ),
    Rule(
        id="ordinal_markers",
        name="首先 / 其次 / 总之",
        grade="X",
        kind="rejected",
        evidence="配对复测 δ+0.02，对当代模型完全失效；序数词小标题方向反转（人类 8.6% vs AI 4.9%）",
        why="这一类连接词已经被模型学会按需使用，不再是稳定指纹。",
        fix="永不据此删改。删掉「首先」不会让文章更像人写。",
        reference="无差异或人类更多",
    ),
    Rule(
        id="this_means",
        name="「这意味着」复述",
        grade="X",
        kind="rejected",
        evidence="三项口径全部反向：人类 0.027 vs AI 0.016 次/千字",
        why="这是人类常用的解释动作，不是 AI 口癖。",
        fix="永不删。",
        reference="人类更多",
    ),
    Rule(
        id="precise_numbers",
        name="精确数字堆砌",
        grade="X",
        kind="rejected",
        evidence="δ−0.06；配对后差异消失，此前是话题混杂造成的假象",
        why="AI 并不比人类更爱堆数字；反过来「补数字」也不该做。",
        fix="永不据此增删数字。",
        reference="无差异",
    ),
    Rule(
        id="nominalization",
        name="名词化 / 进行＋动词",
        grade="X",
        kind="rejected",
        evidence="绝对值小于 0.2，未达显著",
        why="「进行了优化」「具有……意义」读着重，但在同题语料里不是稳定的人机差异。",
        fix="不据此批量改写；确有阅读障碍时按普通润色处理。",
        reference="无差异",
    ),
)

RULES_BY_ID = {r.id: r for r in RULES}

# 这些词只在 X 级里计数展示，用来证明工具「故意不管」它们。
BLACKLIST_WORDS = (
    "赋能", "闭环", "抓手", "底层逻辑", "顶层设计", "颗粒度", "拉通",
    "对齐", "沉淀", "组合拳", "全链路", "降本增效", "认知跃迁", "价值释放",
)
ORDINAL_WORDS = ("首先", "其次", "再次", "最后", "其一", "其二", "第一，", "第二，", "第三，")
THIS_MEANS_WORDS = ("这意味着", "这表明", "这说明", "这也就解释了")
NOMINALIZATION_PATTERNS = (
    r"进行[了着]?[\u4e00-\u9fff]{1,4}",
    r"实现了[^，。！？\n]{1,12}的(?:提升|增长|改善|突破)",
    r"起到了[^，。！？\n]{1,10}作用",
    r"具有[^，。！？\n]{1,10}意义",
)
CHAIN_MARKERS = (
    "这也解释了", "这就解释了", "从这个角度", "从这个意义上", "换句话说",
    "更重要的是", "正因为如此", "这意味着", "所以说", "由此可见",
    "基于此", "在这个意义上", "换言之",
)
SYNONYM_GROUPS = (
    ("优化", "增强", "提升", "提高", "改善", "强化"),
    ("构建", "搭建", "建设", "打造"),
    ("解决", "应对", "处理", "缓解"),
    ("核心", "关键", "重点", "要害"),
    ("路径", "路线", "方式", "办法"),
)

_COMPILED = {
    r.id: tuple(re.compile(p) for p in r.patterns) for r in RULES if r.patterns
}


def compiled(rule_id: str):
    return _COMPILED.get(rule_id, ())
