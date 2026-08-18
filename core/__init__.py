"""
NTE 刮刮乐 - core 核心包

聚合配置、卡片工具与排行榜模板，作为 main.py 的支撑层。
子包内部互相导入使用相对导入（from .config import ... 等）。
"""

# 汇总导出（供 main.py 统一 from .core import ... 使用）
from . import card_utils, config, leaderboard_template
from .card_utils import (
    _card_to_str,
    _decompose_prize,
    _fmt_money,
    _generate_card,
    _prize_label,
)
from .config import (
    AMULET_BACKDOOR_COST,
    AMULET_HAND_COST,
    BOOKMARK_CARD_MULT,
    BOOKMARK_MONEY_AMOUNT,
    BOOKMARK_MONEY_UNIT,
    CARD_COLS,
    CARD_POSITIONS,
    CARD_ROWS,
    CARD_TYPES,
    INITIAL_BALANCE,
    LLM_TOOL_NAMES,
    PENSION_TIERS,
)
from .leaderboard_template import LEADERBOARD_HTML

__all__ = [
    "AMULET_BACKDOOR_COST", "AMULET_HAND_COST", "BOOKMARK_CARD_MULT",
    "BOOKMARK_MONEY_AMOUNT", "BOOKMARK_MONEY_UNIT",
    "CARD_COLS", "CARD_POSITIONS", "CARD_ROWS", "CARD_TYPES",
    "INITIAL_BALANCE", "LLM_TOOL_NAMES", "PENSION_TIERS",
    "LEADERBOARD_HTML",
    "_card_to_str", "_decompose_prize", "_fmt_money", "_generate_card", "_prize_label",
]
