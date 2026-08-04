"""Versioned fixtures used by the public MewCode demo."""

from __future__ import annotations

from .models import Scenario


FILES: dict[str, dict[str, str]] = {
    "checkout": {
        "src/checkout.py": (
            "def checkout(quantity: int, unit_price: float) -> float:\n"
            "    return quantity * unit_price\n"
        ),
        "tests/test_checkout.py": (
            "from src.checkout import checkout\n\n"
            "def test_negative_quantity_is_rejected():\n"
            "    try:\n"
            "        checkout(-1, 12.0)\n"
            "    except ValueError:\n"
            "        return\n"
            "    raise AssertionError('negative quantity must fail')\n"
        ),
    },
    "auth-service": {
        "src/api.py": (
            "from .auth import require_user\n\n"
            "def profile(request):\n"
            "    user = require_user(request.headers.get('Authorization'))\n"
            "    return {'id': user.id}\n"
        ),
        "src/auth.py": (
            "def require_user(header):\n"
            "    if not header:\n"
            "        raise PermissionError('missing token')\n"
            "    return decode_token(header)\n"
        ),
        "tests/test_api.py": "def test_profile_requires_token(): ...\n",
    },
}


SCENARIOS = [
    Scenario(
        key="trace-auth-flow",
        title="定位鉴权调用链",
        mode="read-only",
        prompt="找到 profile 接口的鉴权入口，并说明缺少 Token 时的调用链。",
        fixture="auth-service",
        goal="演示 Glob、Grep、ReadFile 的自主只读工具循环。",
        expected_tools=["Glob", "Grep", "ReadFile"],
    ),
    Scenario(
        key="fix-negative-quantity",
        title="修复负数结算缺陷",
        mode="write",
        prompt="修复负数商品数量仍可进入结算的问题，并验证测试。",
        fixture="checkout",
        goal="演示写入权限门、最小修改和测试验证。",
        expected_tools=["Grep", "ReadFile", "EditFile", "Pytest"],
    ),
]


def list_scenarios() -> list[Scenario]:
    return SCENARIOS


def get_scenario(key: str) -> Scenario | None:
    return next((item for item in SCENARIOS if item.key == key), None)
