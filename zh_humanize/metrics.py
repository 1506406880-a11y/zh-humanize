# -*- coding: utf-8 -*-
"""指标计算。

原则：只算能指出「改哪一句」的东西。整篇分布类指标只报告，不设改写目标。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List

from . import rules as R
from .text import Doc, cv, han_len, median, parse, per_k

CUE_RE = re.compile(
    r"(一句话总结|一句话概括|总结一下|核心是|核心在于|关键是|关键在于|本质是|"
    r"根本原因是|原因很简单|原因如下|问题在于|真相是|现实是|重点是|结论是|"
    r"结论很|答案很|如下|以下几点|两点|三点|几个方面|这里有个|记住一句)\s*$"
)
DELIM = "，。；：！？\n（）()「」“”"


@dataclass
class Example:
    para: int
    sentence: str
    match: str


@dataclass
class Finding:
    rule: R.Rule
    count: float = 0
    density: float = 0.0
    unit: str = "次/千字"
    status: str = "ok"
    examples: List[Example] = field(default_factory=list)
    detail: Dict[str, object] = field(default_factory=dict)


@dataclass
class Report:
    doc: Doc
    findings: List[Finding]
    summary: Dict[str, int]
    meta: Dict[str, object]


def _snippet(text: str, limit: int = 90) -> str:
    text = re.sub(r"\s+", "", text)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _pattern_finding(doc: Doc, rule: R.Rule) -> Finding:
    hits: List[Example] = []
    for para in doc.paragraphs:
        for rx in R.compiled(rule.id):
            for m in rx.finditer(para.text):
                hits.append(Example(para.index, _snippet(para.text), m.group(0).strip()))
    count = len(hits)
    density = per_k(count, doc.han)
    if count == 0:
        status = "ok"
    elif density >= rule.threshold:
        status = "hit"
    else:
        status = "watch"
    return Finding(rule, count, density, "次/千字", status, hits[:3])


def _long_premodifier(doc: Doc) -> Finding:
    rule = R.RULES_BY_ID["long_premodifier"]
    hits: List[Example] = []
    for para in doc.paragraphs:
        text = para.text
        consumed = -1
        for m in re.finditer("的", text):
            if m.start() <= consumed:
                continue
            seg_start = 0
            for i in range(m.start() - 1, -1, -1):
                if text[i] in DELIM:
                    seg_start = i + 1
                    break
            seg = text[seg_start:m.start()]
            if han_len(seg) >= 15:
                hits.append(Example(para.index, _snippet(text), _snippet(seg + "的…", 40)))
                consumed = m.start() + 8
    count = len(hits)
    density = per_k(count, doc.han)
    status = "ok" if count == 0 else ("hit" if density >= rule.threshold else "watch")
    return Finding(rule, count, density, "次/千字", status, hits[:3])


def _cue_colon(doc: Doc) -> Finding:
    rule = R.RULES_BY_ID["cue_colon"]
    hits: List[Example] = []
    for para in doc.paragraphs:
        text = para.text
        for m in re.finditer(r"[：:]", text):
            left = text[max(0, m.start() - 16):m.start()]
            if CUE_RE.search(left):
                hits.append(Example(para.index, _snippet(text), _snippet(left + "：", 40)))
    count = len(hits)
    density = per_k(count, doc.han)
    status = "ok" if count == 0 else ("hit" if density >= rule.threshold else "watch")
    return Finding(rule, count, density, "次/千字", status, hits[:3])


def _dense_enum(doc: Doc) -> Finding:
    rule = R.RULES_BY_ID["dense_enum"]
    hits: List[Example] = []
    for para in doc.paragraphs:
        for clause in re.split(r"[，。；！？!?]", para.text):
            if clause.count("、") >= 2:
                items = [x for x in clause.split("、") if han_len(x) > 0]
                if len(items) >= 3:
                    hits.append(Example(para.index, _snippet(para.text), _snippet(clause, 60)))
    count = len(hits)
    density = per_k(count, doc.han)
    status = "ok" if count == 0 else ("hit" if density >= rule.threshold else "watch")
    return Finding(rule, count, density, "次/千字", status, hits[:3])


FUNC_CHARS = set("的了在是和与及或被把将从而就都也还又很更最不没着过吗呢吧啊之其者所")
WH_RE = re.compile(r"什么|哪个|哪些|谁|怎么|怎样|如何|为什么|多少|几个|是否")
SKEL_PUNCT = "，。！？、；："


def _skeleton(sentence: str) -> str:
    """把句子压成「功能词 + 标点 + 内容词占位」的骨架。

    只保留虚词和疑问词，实词一律折成 H。这样比较的是句法骨架，
    不是句子长度——长度巧合不会被当成同构。
    """
    text = WH_RE.sub("W", sentence)
    out: List[str] = []
    prev_placeholder = False
    for ch in text:
        if ch in SKEL_PUNCT:
            out.append(ch)
            prev_placeholder = False
        elif "\u4e00" <= ch <= "\u9fff":
            if ch in FUNC_CHARS:
                out.append(ch)
                prev_placeholder = False
            elif not prev_placeholder:
                out.append("H")
                prev_placeholder = True
        elif ch == "W":
            out.append("W")
            prev_placeholder = False
        elif ch.isdigit():
            if not prev_placeholder:
                out.append("N")
                prev_placeholder = True
    return "".join(out)


def _adjacent_isomorphism(doc: Doc) -> Finding:
    rule = R.RULES_BY_ID["adjacent_isomorphism"]
    hits: List[Example] = []
    triple = 0
    for para in doc.paragraphs:
        sents = [s for s in doc.sents if s.para == para.index and s.length >= 5]
        skels = [_skeleton(s.text) for s in sents]
        i = 0
        while i < len(sents) - 1:
            same = skels[i] == skels[i + 1] and len(skels[i]) >= 4
            if same:
                hits.append(Example(para.index, _snippet(sents[i].text + sents[i + 1].text), "相邻同构"))
                if i + 2 < len(sents) and skels[i + 1] == skels[i + 2]:
                    triple += 1
                    i += 2
                else:
                    i += 2
            else:
                i += 1
    count = len(hits)
    density = per_k(count, doc.han)
    status = "ok" if count == 0 else ("hit" if density >= rule.threshold else "watch")
    return Finding(rule, count, density, "次/千字", status, hits[:3], {"triples": triple})


def _chain(doc: Doc) -> Finding:
    rule = R.RULES_BY_ID["chain"]
    paras = doc.paragraphs
    flagged: List[int] = []
    for para in paras:
        first = para.text.strip().split("。")[0]
        if any(first.startswith(marker) for marker in R.CHAIN_MARKERS):
            flagged.append(para.index)
    runs: List[int] = []
    run = 0
    prev = None
    for idx in flagged:
        if prev is not None and idx == prev + 1:
            run += 1
        else:
            run = 1
        runs.append(run)
        prev = idx
    max_run = max(runs) if runs else 0
    examples = [Example(p.index, _snippet(p.text), "承接起段") for p in paras if p.index in flagged][:3]
    status = "hit" if max_run >= 3 else ("watch" if flagged else "ok")
    return Finding(rule, float(len(flagged)), float(len(flagged)), "段", status, examples, {"max_run": max_run})


def _synonym_rotation(doc: Doc) -> Finding:
    rule = R.RULES_BY_ID["synonym_rotation"]
    hits: List[Example] = []
    for para in doc.paragraphs:
        rotated = []
        for group in R.SYNONYM_GROUPS:
            present = [w for w in group if w in para.text]
            if len(present) >= 3:
                rotated.extend(present[:3])
        if rotated:
            hits.append(Example(para.index, _snippet(para.text), "／".join(rotated)))
    para_count = max(1, len(doc.paragraphs))
    density = round(len(hits) / para_count, 3)
    status = "ok" if not hits else ("hit" if density >= rule.threshold else "watch")
    return Finding(rule, float(len(hits)), density, "次/段", status, hits[:3])


def _section_geometry(doc: Doc) -> Finding:
    rule = R.RULES_BY_ID["section_geometry"]
    headings = doc.headings
    if len(headings) < 2:
        return Finding(rule, 0, 0.0, "节", "ok", [], {"insufficient": True})
    lengths: List[float] = []
    sentences: List[int] = []
    index_map = {p.index: i for i, p in enumerate(doc.paras)}
    for i, head in enumerate(headings):
        start = index_map[head.index]
        end = index_map[headings[i + 1].index] if i + 1 < len(headings) else len(doc.paras)
        seg = [p for p in doc.paras[start + 1:end] if not p.is_heading]
        lengths.append(float(sum(p.han for p in seg)))
        sentences.append(sum(1 for s in doc.sents if any(p.index == s.para for p in seg)))
    section_cv = cv(lengths)
    per_k = round(len(headings) * 1000.0 / doc.han, 3) if doc.han else 0.0
    med_sent = median([float(x) for x in sentences])
    status = "hit" if (per_k > 1.0 or section_cv < 0.25) else "ok"
    return Finding(
        rule, float(len(headings)), per_k, "个/千字", status, [],
        {"section_cv": section_cv, "median_sentences": med_sent,
         "section_lengths": [int(x) for x in lengths]},
    )


def _sentence_cv(doc: Doc) -> Finding:
    rule = R.RULES_BY_ID["sentence_cv"]
    lens = [float(s.length) for s in doc.sents if s.length >= 4]
    if len(lens) < 12:
        return Finding(rule, 0, 0.0, "—", "ok", [], {"insufficient": True, "sentences": len(lens)})
    ordered = sorted(lens)
    p10 = ordered[int(len(ordered) * 0.1)]
    p90 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.9))]
    adjacent_same = 0
    pairs = 0
    for a, b in zip(lens, lens[1:]):
        pairs += 1
        if abs(a - b) <= 3:
            adjacent_same += 1
    return Finding(
        rule, 0, cv(lens), "CV", "report", [],
        {"mean": round(sum(lens) / len(lens), 2), "p10": p10, "p90": p90,
         "short_ratio": round(sum(1 for x in lens if x <= 12) / len(lens), 3),
         "long_ratio": round(sum(1 for x in lens if x >= 60) / len(lens), 3),
         "adjacent_same_ratio": round(adjacent_same / max(1, pairs), 3),
         "sentences": len(lens)},
    )


def _paragraph_cv(doc: Doc) -> Finding:
    rule = R.RULES_BY_ID["paragraph_cv"]
    lens = [float(p.han) for p in doc.paragraphs if p.han >= 10]
    if len(lens) < 4:
        return Finding(rule, 0, 0.0, "CV", "ok", [], {"insufficient": True})
    single = sum(1 for p in doc.paragraphs if len([s for s in doc.sents if s.para == p.index]) <= 1)
    return Finding(
        rule, 0, cv(lens), "CV", "report", [],
        {"mean": round(sum(lens) / len(lens), 1), "paragraphs": len(lens),
         "single_sentence_ratio": round(single / max(1, len(doc.paragraphs)), 3)},
    )


def _mattr_chars(text: str, window: int = 100) -> float:
    chars = [c for c in text if "\u4e00" <= c <= "\u9fff"]
    if len(chars) < window:
        return 0.0
    step = max(1, window // 2)
    values = []
    for i in range(0, len(chars) - window + 1, step):
        seg = chars[i:i + window]
        values.append(len(set(seg)) / float(window))
    return round(sum(values) / len(values), 4) if values else 0.0


def _lexical_diversity(doc: Doc) -> Finding:
    rule = R.RULES_BY_ID["lexical_diversity"]
    chars = [c for c in doc.masked if "\u4e00" <= c <= "\u9fff"]
    tokens = [chars[i] + chars[i + 1] for i in range(len(chars) - 1)]
    if len(tokens) < 100:
        return Finding(rule, 0, 0.0, "—", "ok", [], {"insufficient": True})
    repeat = 1.0 - len(set(tokens)) / float(len(tokens))
    return Finding(
        rule, 0, _mattr_chars(doc.masked), "MATTR-100", "report", [],
        {"mattr100_char": _mattr_chars(doc.masked),
         "bigram_repeat_ratio": round(repeat, 4),
         "tokens": len(tokens),
         "note": "无分词依赖的字符代理，绝对值不可与论文 MTLD 数字比较，只看同体裁前后变化"},
    )


def _count_words(doc: Doc, words) -> int:
    return sum(doc.masked.count(w) for w in words)


def _count_regex(doc: Doc, patterns) -> int:
    total = 0
    for p in patterns:
        total += len(re.findall(p, doc.masked))
    return total


def analyze(text: str) -> Report:
    doc = parse(text)
    findings: List[Finding] = []

    for rule in R.RULES:
        if rule.kind == "pattern" and rule.id == "long_premodifier":
            findings.append(_long_premodifier(doc))
        elif rule.kind == "pattern" and rule.id == "cue_colon":
            findings.append(_cue_colon(doc))
        elif rule.kind == "pattern" and rule.id == "dense_enum":
            findings.append(_dense_enum(doc))
        elif rule.kind == "pattern":
            findings.append(_pattern_finding(doc, rule))
        elif rule.id == "adjacent_isomorphism":
            findings.append(_adjacent_isomorphism(doc))
        elif rule.id == "chain":
            findings.append(_chain(doc))
        elif rule.id == "synonym_rotation":
            findings.append(_synonym_rotation(doc))
        elif rule.id == "section_geometry":
            findings.append(_section_geometry(doc))
        elif rule.id == "sentence_cv":
            findings.append(_sentence_cv(doc))
        elif rule.id == "paragraph_cv":
            findings.append(_paragraph_cv(doc))
        elif rule.id == "lexical_diversity":
            findings.append(_lexical_diversity(doc))
        elif rule.id == "dash":
            paired = doc.masked.count("——")
            single = doc.masked.replace("——", "").count("—")
            n = paired + single
            findings.append(Finding(rule, n, per_k(n, doc.han), "次/千字",
                                    "hit" if per_k(n, doc.han) > rule.threshold else "ok"))
        elif rule.id == "semicolon":
            n = doc.masked.count("；") + doc.masked.count(";")
            findings.append(Finding(rule, n, per_k(n, doc.han), "次/千字",
                                    "hit" if per_k(n, doc.han) > rule.threshold else "ok"))
        elif rule.id == "question_ratio":
            n = doc.masked.count("？") + doc.masked.count("?")
            findings.append(Finding(rule, n, per_k(n, doc.han), "次/千字", "ignore"))
        elif rule.id == "blacklist_words":
            n = _count_words(doc, R.BLACKLIST_WORDS)
            found = [w for w in R.BLACKLIST_WORDS if w in doc.masked]
            findings.append(Finding(rule, n, per_k(n, doc.han), "次/千字", "ignore",
                                    detail={"found": found}))
        elif rule.id == "ordinal_markers":
            n = _count_words(doc, R.ORDINAL_WORDS)
            findings.append(Finding(rule, n, per_k(n, doc.han), "次/千字", "ignore"))
        elif rule.id == "this_means":
            n = _count_words(doc, R.THIS_MEANS_WORDS)
            findings.append(Finding(rule, n, per_k(n, doc.han), "次/千字", "ignore"))
        elif rule.id == "precise_numbers":
            n = len(re.findall(r"\d+(?:\.\d+)?%?", doc.masked))
            findings.append(Finding(rule, n, per_k(n, doc.han), "个/千字", "ignore"))
        elif rule.id == "nominalization":
            n = _count_regex(doc, R.NOMINALIZATION_PATTERNS)
            findings.append(Finding(rule, n, per_k(n, doc.han), "次/千字", "ignore"))

    summary = {
        "A_hit": sum(1 for f in findings if f.rule.grade == "A" and f.status == "hit"),
        "A_watch": sum(1 for f in findings if f.rule.grade == "A" and f.status == "watch"),
        "B_hit": sum(1 for f in findings if f.rule.grade == "B" and f.status == "hit"),
        "B_watch": sum(1 for f in findings if f.rule.grade == "B" and f.status == "watch"),
        "C_report": sum(1 for f in findings if f.rule.grade == "C"),
        "F_report": sum(1 for f in findings if f.rule.grade == "F"),
        "X_ignored": sum(1 for f in findings if f.rule.grade == "X"),
    }
    meta = {
        "han": doc.han,
        "paragraphs": len(doc.paragraphs),
        "sentences": len(doc.sents),
        "headings": len(doc.headings),
    }
    return Report(doc, findings, summary, meta)
