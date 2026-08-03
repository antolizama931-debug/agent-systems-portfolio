"""Versioned demo tasks. Public users cannot supply executable repository code."""

from __future__ import annotations

from .models import Scenario


SCENARIOS: dict[str, Scenario] = {
    "python-average-empty": Scenario(
        key="python-average-empty",
        title="修复空列表平均值异常",
        repository="fixture/python-average",
        language="Python",
        issue="average([]) 当前触发 ZeroDivisionError；期望返回 0.0，同时保持非空输入行为不变。",
        risk="low",
        target_file="calculator.py",
        before='    return sum(values) / len(values)',
        after='    if not values:\n        return 0.0\n    return sum(values) / len(values)',
        test_command=["python", "-I", "-m", "pytest", "-q"],
        acceptance=["空列表返回 0.0", "非空列表平均值计算保持正确", "全部 Pytest 用例通过"],
    ),
    "python-slug-separators": Scenario(
        key="python-slug-separators",
        title="修复 Slug 连续分隔符",
        repository="fixture/python-slug",
        language="Python",
        issue="slugify 对连续空格和标点会产生多个连字符；期望输出单个、无首尾连字符的 slug。",
        risk="low",
        target_file="slug.py",
        before='    normalized = value.strip().lower().replace(" ", "-")\n    return re.sub(r"[^a-z0-9-]", "", normalized)',
        after='    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())\n    return normalized.strip("-")',
        test_command=["python", "-I", "-m", "pytest", "-q"],
        acceptance=["连续分隔符折叠为单个连字符", "清除首尾连字符", "全部 Pytest 用例通过"],
    ),
}


def list_scenarios() -> list[Scenario]:
    return list(SCENARIOS.values())


def get_scenario(key: str) -> Scenario | None:
    return SCENARIOS.get(key)

