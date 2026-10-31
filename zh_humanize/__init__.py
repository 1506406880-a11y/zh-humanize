# -*- coding: utf-8 -*-
"""zh-humanize：中文写作的 AI 痕迹体检。"""
from .metrics import Finding, Report, analyze

__version__ = "0.1.0"
__all__ = ["analyze", "Report", "Finding", "__version__"]
