# -*- coding: utf-8 -*-
"""切分与基础计数。

只把正文当分析对象：代码块、行内代码、URL、YAML front matter、引用行、
表格行会被等长屏蔽（用空格），因此原文偏移量不变，示例仍能定位。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

HAN_RANGE = "\u4e00-\u9fff"
HAN_RE = re.compile("[%s]" % HAN_RANGE)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
YAML_RE = re.compile(r"\A---\n.*?\n---\n", re.S)
FENCE_RE = re.compile(r"```.*?```", re.S)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
LINK_RE = re.compile(r"\[([^\]\n]*)\]\([^)\n]*\)")
URL_RE = re.compile(r"https?://[^\s)>\]]+")
HTML_RE = re.compile(r"<[^>\n]{1,200}>")

SENT_END = "。！？!?…"
CLOSERS = "”’」』）)》】\"'"

LIST_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")
STRUCTURAL_PREFIX = ("|", ">")


def han_len(text: str) -> int:
    return len(HAN_RE.findall(text))


def _blank(match: "re.Match[str]") -> str:
    return re.sub(r"[^\n]", " ", match.group(0))


def mask(text: str) -> str:
    """等长屏蔽非正文内容，保持换行与字符偏移。"""
    out = YAML_RE.sub(_blank, text)
    out = FENCE_RE.sub(_blank, out)
    out = INLINE_CODE_RE.sub(_blank, out)
    out = LINK_RE.sub(lambda m: m.group(1) + " " * (len(m.group(0)) - len(m.group(1))), out)
    out = URL_RE.sub(_blank, out)
    out = HTML_RE.sub(_blank, out)

    lines = out.split("\n")
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith(STRUCTURAL_PREFIX):
            lines[i] = " " * len(line)
    return "\n".join(lines)


@dataclass
class Para:
    index: int
    start: int
    text: str
    is_heading: bool = False
    level: int = 0
    line: int = 1

    @property
    def han(self) -> int:
        return han_len(self.text)


@dataclass
class Sent:
    text: str
    start: int
    length: int
    para: int


@dataclass
class Doc:
    raw: str
    masked: str
    paras: List[Para] = field(default_factory=list)
    sents: List[Sent] = field(default_factory=list)
    headings: List[Para] = field(default_factory=list)
    han: int = 0
    lines: int = 0

    @property
    def paragraphs(self) -> List[Para]:
        return [p for p in self.paras if not p.is_heading]

    @property
    def body(self) -> str:
        return self.masked


def _ends_sentence(line: str) -> bool:
    tail = line.rstrip()
    while tail and tail[-1] in CLOSERS:
        tail = tail[:-1]
    return bool(tail) and tail[-1] in SENT_END


def _split_sentences(text: str, base: int, para_index: int) -> List[Sent]:
    flat = text.replace("\n", "")
    result: List[Sent] = []
    start = 0
    i = 0
    n = len(flat)
    while i < n:
        ch = flat[i]
        if ch in SENT_END:
            j = i + 1
            while j < n and flat[j] in SENT_END:
                j += 1
            while j < n and flat[j] in CLOSERS:
                j += 1
            chunk = flat[start:j]
            if han_len(chunk) >= 2:
                result.append(Sent(chunk.strip(), base + start, han_len(chunk), para_index))
            start = j
            i = j
        else:
            i += 1
    tail = flat[start:]
    if han_len(tail) >= 2:
        result.append(Sent(tail.strip(), base + start, han_len(tail), para_index))
    return result


def parse(raw: str) -> Doc:
    masked = mask(raw)
    m_lines = masked.split("\n")
    r_lines = raw.split("\n")

    doc = Doc(raw=raw, masked=masked, lines=len(r_lines))
    offset = 0
    buffer: List[str] = []
    buf_start = 0
    buf_line = 1

    def flush() -> None:
        nonlocal buffer, buf_start
        if not buffer:
            return
        text = "\n".join(buffer)
        para = Para(index=len(doc.paras), start=buf_start, text=text, line=buf_line)
        doc.paras.append(para)
        doc.sents.extend(_split_sentences(text, buf_start, para.index))
        buffer = []

    for idx, (m_line, r_line) in enumerate(zip(m_lines, r_lines)):
        line_no = idx + 1
        line_len = len(r_line)
        stripped = r_line.strip()

        if not stripped:
            flush()
            offset += line_len + 1
            continue

        heading = HEADING_RE.match(r_line)
        if heading:
            flush()
            para = Para(
                index=len(doc.paras),
                start=offset,
                text=heading.group(2),
                is_heading=True,
                level=len(heading.group(1)),
                line=line_no,
            )
            doc.paras.append(para)
            doc.headings.append(para)
            offset += line_len + 1
            continue

        if not m_line.strip():
            flush()
            offset += line_len + 1
            continue

        if r_line.lstrip().startswith(STRUCTURAL_PREFIX) or LIST_RE.match(r_line):
            flush()
            offset += line_len + 1
            continue

        if not buffer:
            buf_start = offset
            buf_line = line_no
        buffer.append(m_line)
        if _ends_sentence(r_line):
            flush()
        offset += line_len + 1

    flush()
    doc.han = sum(p.han for p in doc.paras if not p.is_heading)
    return doc


def clauses(sentence: str) -> List[str]:
    return [c for c in re.split(r"[，,；;：:]", sentence) if c.strip()]


def per_k(count: float, han: int) -> float:
    return round(count * 1000.0 / han, 3) if han else 0.0


def cv(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    if mean == 0:
        return 0.0
    var = sum((v - mean) ** 2 for v in values) / len(values)
    return round((var ** 0.5) / mean, 4)


def median(values: List[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return round(float(ordered[mid]), 3)
    return round((ordered[mid - 1] + ordered[mid]) / 2.0, 3)
