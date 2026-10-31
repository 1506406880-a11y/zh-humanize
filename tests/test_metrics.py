# -*- coding: utf-8 -*-
"""指标与规则的回归测试。"""
import unittest

from zh_humanize import analyze


def finding(report, rule_id):
    return next(f for f in report.findings if f.rule.id == rule_id)


class TestPatterns(unittest.TestCase):
    def test_antithesis(self):
        text = "真正的壁垒不是技术，而是认知。这不是效率问题，而是组织问题。"
        self.assertEqual(finding(analyze(text), "antithesis").count, 2)

    def test_antithesis_does_not_match_plain_negation(self):
        text = "这不是技术问题。"
        self.assertEqual(finding(analyze(text), "antithesis").count, 0)

    def test_cue_colon(self):
        text = "一句话总结：这个方案成本太高。原因很简单：交付晚了。"
        self.assertEqual(finding(analyze(text), "cue_colon").count, 2)

    def test_plain_colon_is_not_cue(self):
        text = "会议定在周三：上午九点，三楼。"
        self.assertEqual(finding(analyze(text), "cue_colon").count, 0)

    def test_opening_scaffold(self):
        self.assertEqual(finding(analyze("说白了，这件事做不成。"), "opening_scaffold").count, 1)

    def test_long_premodifier(self):
        text = "这是一个能够同时满足合规、成本、交付速度和业务灵活性的平台。"
        self.assertGreaterEqual(finding(analyze(text), "long_premodifier").count, 1)

    def test_dense_enum(self):
        text = "我们需要采集、清洗、标注和训练数据。"
        self.assertEqual(finding(analyze(text), "dense_enum").count, 1)

    def test_topic_shell(self):
        text = "对于早期团队来说，招人是最难的事。"
        self.assertEqual(finding(analyze(text), "translationese_shell").count, 1)


class TestStructure(unittest.TestCase):
    def test_isomorphic_triple(self):
        text = "叫什么名字？承载什么功能？嵌入哪个生态？"
        f = finding(analyze(text), "adjacent_isomorphism")
        self.assertGreaterEqual(f.count, 1)
        self.assertEqual(f.detail["triples"], 1)

    def test_unrelated_short_sentences_are_not_isomorphic(self):
        text = "今天下雨了。明天可能放晴。后天再说吧。"
        self.assertEqual(finding(analyze(text), "adjacent_isomorphism").count, 0)

    def test_synonym_rotation(self):
        text = "我们要优化流程，提升效率，增强体验，改善交付。"
        self.assertEqual(finding(analyze(text), "synonym_rotation").count, 1)


class TestRejected(unittest.TestCase):
    def test_blacklist_words_are_not_scored_as_ai(self):
        text = "首先，我们要赋能业务，形成闭环，抓住抓手。这意味着效率提升。"
        report = analyze(text)
        self.assertEqual(report.summary["A_hit"], 0)
        self.assertEqual(finding(report, "blacklist_words").status, "ignore")
        self.assertEqual(finding(report, "ordinal_markers").status, "ignore")
        self.assertEqual(finding(report, "this_means").status, "ignore")


class TestParsing(unittest.TestCase):
    def test_code_block_is_masked(self):
        text = "正文一句话。\n\n```\n不是A而是B。不是C而是D。\n```\n"
        self.assertEqual(finding(analyze(text), "antithesis").count, 0)

    def test_empty_input(self):
        report = analyze("")
        self.assertEqual(report.meta["han"], 0)
        self.assertEqual(report.summary["A_hit"], 0)

    def test_heading_is_not_prose(self):
        text = "# 不是A而是B的标题\n\n真正的问题不是技术，而是认知。"
        self.assertEqual(finding(analyze(text), "antithesis").count, 1)


if __name__ == "__main__":
    unittest.main()
