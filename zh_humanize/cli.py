# -*- coding: utf-8 -*-
"""命令行入口。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from .metrics import analyze
from .report import render_compare, render_markdown, to_dict

VERSION = "0.1.0"


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _write(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


def _selftest() -> int:
    cases = [
        ("真正的壁垒不是技术，而是认知。", "antithesis", 1),
        ("并非模型不够强，而是需求没想清楚。", "antithesis", 1),
        ("一句话总结：这个方案成本太高。", "cue_colon", 1),
        ("原因很简单：交付晚了。", "cue_colon", 1),
        ("对于早期团队来说，招人是最难的事。", "translationese_shell", 1),
        ("先说结论，这个方向不成立。", "opening_scaffold", 1),
    ]
    ok = True
    for text, rid, expected in cases:
        report = analyze(text)
        finding = next(f for f in report.findings if f.rule.id == rid)
        if finding.count != expected:
            print("FAIL %s: expected %d got %d in %r" % (rid, expected, finding.count, text))
            ok = False
    if ok:
        print("selftest: 6/6 ok")
    return 0 if ok else 1


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        prog="zh-humanize",
        description="中文写作的 AI 痕迹体检：可复算的句法指标，不输出 AI 率。",
    )
    parser.add_argument("files", nargs="*", help="待检测的 Markdown / 纯文本文件")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--md", metavar="PATH", help="把 Markdown 报告写到文件")
    parser.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"),
                        help="对比两份文本的指标变化")
    parser.add_argument("--fail-on", choices=["A", "B", "none"], default="none",
                        help="CI 用：出现该等级命中时退出码为 1")
    parser.add_argument("--selftest", action="store_true", help="运行内置自检")
    parser.add_argument("--version", action="version", version="zh-humanize " + VERSION)
    args = parser.parse_args(argv)

    if args.selftest:
        return _selftest()

    if args.compare:
        before = analyze(_read(args.compare[0]))
        after = analyze(_read(args.compare[1]))
        text = render_compare(before, after)
        if args.md:
            _write(args.md, text)
            print("written: %s" % args.md)
        else:
            print(text)
        return 0

    if not args.files:
        parser.print_help()
        return 2

    failed = False
    for path in args.files:
        try:
            raw = _read(path)
        except OSError as exc:
            print("cannot read %s: %s" % (path, exc), file=sys.stderr)
            return 2

        report = analyze(raw)
        title = "中文写作体检报告 · %s" % Path(path).name

        if args.json:
            print(json.dumps(to_dict(report), ensure_ascii=False, indent=2))
            continue

        text = render_markdown(report, title)
        if args.md:
            target = args.md if len(args.files) == 1 else "%s.%s" % (args.md, Path(path).stem)
            _write(target, text)
            print("written: %s" % target)
        else:
            print(text)

        if args.fail_on != "none":
            key = args.fail_on + "_hit"
            if report.summary.get(key, 0) > 0:
                failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
