# -*- coding: utf-8 -*-
"""报告渲染：Markdown / JSON。"""
from __future__ import annotations

from typing import Dict, List

from .metrics import Finding, Report

GRADE_LABEL = {
    "A": "A · 两轮同向，建议改",
    "B": "B · 条件显著，复核后改",
    "C": "C · 整篇分布，只报告",
    "F": "F · 单模型指纹，不定罪",
    "X": "X · 已否决，永不改",
}


def _fmt(x) -> str:
    if isinstance(x, float):
        return ("%.3f" % x).rstrip("0").rstrip(".")
    return str(x)


def _detail(f: Finding) -> str:
    d = f.detail
    if f.rule.id == "sentence_cv":
        if d.get("insufficient"):
            return "句数不足 %s 句，跳过" % d.get("sentences", 12)
        return "CV %s｜均值 %s｜P10–P90 %s–%s｜短句 %.0f%%｜长句 %.0f%%｜相邻句长差≤3 占 %.0f%%" % (
            _fmt(d["cv"] if "cv" in d else f.density), d["mean"], d["p10"], d["p90"],
            d["short_ratio"] * 100, d["long_ratio"] * 100, d["adjacent_same_ratio"] * 100,
        )
    if f.rule.id == "paragraph_cv":
        if d.get("insufficient"):
            return "段落不足，跳过"
        return "CV %s｜均值 %s 字｜单句段占 %.0f%%" % (
            _fmt(f.density), d["mean"], d["single_sentence_ratio"] * 100,
        )
    if f.rule.id == "section_geometry":
        if d.get("insufficient"):
            return "小标题不足 2 个，跳过"
        return "节长 CV %s｜每节中位句数 %s｜节长 %s" % (
            _fmt(d["section_cv"]), _fmt(d["median_sentences"]),
            "／".join(str(x) for x in d["section_lengths"][:8]),
        )
    if f.rule.id == "lexical_diversity":
        if d.get("insufficient"):
            return "文本过短，跳过"
        return "字符 MATTR-100 %s｜二元组重复率 %.1f%%（%s 个二元组；%s）" % (
            _fmt(d["mattr100_char"]), d["bigram_repeat_ratio"] * 100,
            d["tokens"], d.get("note", ""),
        )
    if f.rule.id == "chain":
        return "承接起段 %d 段｜最长连环 %s" % (int(f.count), d.get("max_run", 0))
    if f.rule.id == "adjacent_isomorphism":
        return "同构组 %d 组｜其中三连 %s 组" % (int(f.count), d.get("triples", 0))
    if f.rule.id == "synonym_rotation":
        return "同段出现 3 个以上近义词的段落 %d 个" % int(f.count)
    if f.rule.id == "blacklist_words":
        found = d.get("found") or []
        return "出现 %d 次：%s" % (int(f.count), "、".join(found) if found else "无")
    return ""


def render_markdown(report: Report, title: str = "中文写作体检报告") -> str:
    m = report.meta
    s = report.summary
    lines: List[str] = []
    lines.append("# %s" % title)
    lines.append("")
    lines.append(
        "正文 %d 字 · %d 段 · %d 句 · %d 个小标题" % (
            m["han"], m["paragraphs"], m["sentences"], m["headings"]
        )
    )
    lines.append("")
    lines.append(
        "> 本报告只给可定位的句法命中，不判断作者身份，不输出「AI 率」。"
        "统计显著说的是语料层面的差异，不等于这一篇「是 AI 写的」。"
    )
    lines.append("")

    lines.append("## 摘要")
    lines.append("")
    lines.append("| 等级 | 计数 | 含义 |")
    lines.append("|---|---|---|")
    lines.append("| A 命中 | %d | 两轮同向，默认建议改 |" % s["A_hit"])
    lines.append("| A 观察 | %d | 有命中但未达本篇门槛 |" % s["A_watch"])
    lines.append("| B 命中 | %d | 复核后改 |" % s["B_hit"])
    lines.append("| B 观察 | %d | 有命中但未达门槛 |" % s["B_watch"])
    lines.append("| C 报告 | %d | 整篇分布，只报数 |" % s["C_report"])
    lines.append("| F 指纹 | %d | 方向随模型，不定罪 |" % s["F_report"])
    lines.append("| X 已否决 | %d | 计数展示，永不据此改 |" % s["X_ignored"])
    lines.append("")

    for grade in ("A", "B"):
        group = [f for f in report.findings if f.rule.grade == grade]
        lines.append("## %s" % GRADE_LABEL[grade])
        lines.append("")
        if not group:
            lines.append("无。")
            lines.append("")
            continue
        for f in group:
            mark = {"hit": "命中", "watch": "观察", "ok": "未命中"}.get(f.status, f.status)
            lines.append("### %s · %s" % (f.rule.name, mark))
            lines.append("")
            lines.append("- 密度：%s %s（门槛 %s）" % (_fmt(f.density), f.unit, _fmt(f.rule.threshold)))
            lines.append("- 证据：%s" % f.rule.evidence)
            lines.append("- 为什么：%s" % f.rule.why)
            lines.append("- 怎么改：%s" % f.rule.fix)
            if f.examples:
                ordinal = {p.index: i + 1 for i, p in enumerate(report.doc.paragraphs)}
                lines.append("- 原文：")
                for ex in f.examples:
                    lines.append("  - ¶%d｜%s" % (ordinal.get(ex.para, ex.para + 1), ex.sentence))
            lines.append("")

    lines.append("## %s" % GRADE_LABEL["C"])
    lines.append("")
    lines.append("| 指标 | 读数 | 人类参考 | 处置 |")
    lines.append("|---|---|---|---|")
    for f in report.findings:
        if f.rule.grade != "C":
            continue
        read = _fmt(f.density) + (" " + f.unit if f.unit not in ("—", "CV") else "")
        lines.append("| %s | %s | %s | %s |" % (
            f.rule.name, read, f.rule.reference or "—",
            "只报告" if not f.detail.get("insufficient") else "样本不足",
        ))
    lines.append("")
    for f in report.findings:
        if f.rule.grade == "C" and _detail(f):
            lines.append("- %s：%s" % (f.rule.name, _detail(f)))
    lines.append("")
    lines.append("结构类指标只报告，不设目标值。为了把句长 CV 拉到某个数而把句子拆碎，"
                 "是这类工具最常见的破坏。")
    lines.append("")

    lines.append("## %s" % GRADE_LABEL["F"])
    lines.append("")
    lines.append("指纹是模型使用偏好，不能反推这篇由哪个模型写成。")
    lines.append("")
    for f in report.findings:
        if f.rule.grade != "F":
            continue
        lines.append("- %s：%s %s（人类参考 %s）— %s" % (
            f.rule.name, _fmt(f.density), f.unit, f.rule.reference or "—", f.rule.why,
        ))
    lines.append("")

    lines.append("## %s" % GRADE_LABEL["X"])
    lines.append("")
    lines.append("| 特征 | 本篇计数 | 配对实测 | 处置 |")
    lines.append("|---|---|---|---|")
    for f in report.findings:
        if f.rule.grade != "X":
            continue
        lines.append("| %s | %s | %s | 不改 |" % (
            f.rule.name, _fmt(f.count), f.rule.evidence,
        ))
    lines.append("")
    lines.append("这些项目在配对语料里与人类写作没有稳定差异，或方向相反。"
                 "把它们清零不会让文章更像人写，只会让文章更空。")
    lines.append("")

    lines.append("## 下一步")
    lines.append("")
    lines.append("1. 只处理 A 级命中，每处只改解决问题所必需的部分。")
    lines.append("2. B 级逐条复核，保留要给出具体理由（引文、术语、修辞、信息关系）。")
    lines.append("3. C 级不改，除非作者明确要求调结构。")
    lines.append("4. 改完复测，确认 A 级清零、C 级没有大幅摆动。")
    lines.append("")
    return "\n".join(lines)


def to_dict(report: Report) -> Dict[str, object]:
    return {
        "meta": report.meta,
        "summary": report.summary,
        "findings": [
            {
                "id": f.rule.id,
                "name": f.rule.name,
                "grade": f.rule.grade,
                "status": f.status,
                "count": f.count,
                "density": f.density,
                "unit": f.unit,
                "threshold": f.rule.threshold,
                "evidence": f.rule.evidence,
                "examples": [
                    {"para": e.para + 1, "sentence": e.sentence, "match": e.match}
                    for e in f.examples
                ],
                "detail": f.detail,
            }
            for f in report.findings
        ],
        "disclaimer": "本报告不判断作者身份，不输出 AI 概率。",
    }


def render_compare(before: Report, after: Report) -> str:
    lines: List[str] = []
    lines.append("# 改写前后对比")
    lines.append("")
    lines.append("| 指标 | 改前 | 改后 |")
    lines.append("|---|---|---|")
    lines.append("| 正文汉字 | %d | %d |" % (before.meta["han"], after.meta["han"]))
    for f in before.findings:
        if f.rule.grade not in ("A", "B"):
            continue
        other = next((x for x in after.findings if x.rule.id == f.rule.id), None)
        if other is None:
            continue
        lines.append("| %s | %s %s | %s %s |" % (
            f.rule.name, _fmt(f.density), f.unit, _fmt(other.density), other.unit,
        ))
    lines.append("")
    lines.append("| 结构指标 | 改前 | 改后 |")
    lines.append("|---|---|---|")
    for rid in ("sentence_cv", "paragraph_cv", "section_geometry", "lexical_diversity"):
        a = next((x for x in before.findings if x.rule.id == rid), None)
        b = next((x for x in after.findings if x.rule.id == rid), None)
        if a and b:
            lines.append("| %s | %s | %s |" % (a.rule.name, _fmt(a.density), _fmt(b.density)))
    lines.append("")
    lines.append("结构指标允许小幅摆动，但不追求把任何一项推到目标值。")
    lines.append("")
    return "\n".join(lines)
