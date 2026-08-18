"""
NTE 刮刮乐 - 卡片工具模块

纯函数，不依赖 astrbot / 插件状态：
  - _decompose_prize : 将总奖金拆分为单格档位
  - _generate_card   : 按概率分布生成一张刮刮卡
  - _prize_label     : 奖金金额转短标签
  - _card_to_str     : 卡片格式化为文本
  - _fmt_money       : 金额千分位格式化
"""

import random

from .config import CARD_COLS, CARD_POSITIONS


# ----------------------------------------------------------
# 卡片生成（基于精确概率分布）
# ----------------------------------------------------------
def _decompose_prize(total: int, cell_tiers: list, positions: int = CARD_POSITIONS) -> list:
    """将总奖金精确拆分为 cell_tiers 中的档位，不超过 positions 格。

    通过按 10000 缩放的 DP 校验：只要存在 ≤ positions 格的标准档位组合，
    就一定能拆出纯档位结果（仅当数学上无解时才做最后兜底）。
    """
    if total == 0:
        return []

    tiers = sorted(cell_tiers)
    min_p = tiers[0]
    parts = []
    remaining = total

    # 可表示性 DP：所有档位与总奖金均为 10000 的倍数，缩放到「万」为单位
    unit = 10000
    total_unit = total // unit
    tiers_unit = [t // unit for t in tiers]
    # INF 必须大于最大可用格数，避免「不可表示」被误判为可表示
    INF = positions + 1
    dp = [INF] * (total_unit + 1)
    dp[0] = 0
    for x in range(1, total_unit + 1):
        for t in tiers_unit:
            if t <= x and dp[x - t] + 1 < dp[x]:
                dp[x] = dp[x - t] + 1

    while remaining > 0:
        cells_left = positions - len(parts)

        if cells_left == 1:
            parts.append(remaining)
            break

        # 候选：不超过剩余金额的档位，且剩余金额仍可在剩余格数内用标准档位表示
        cand = [t for t in tiers if t <= remaining]
        valid = [t for t in cand
                 if remaining - t == 0
                 or dp[(remaining - t) // unit] <= cells_left - 1]
        if not valid:
            # 数学上无解时的最后兜底：并入前一格
            if parts:
                parts[-1] += remaining
            else:
                parts.append(remaining)
            break

        # 格子充裕度决定选大还是选小
        min_needed = (remaining + min_p - 1) // min_p
        if min_needed <= cells_left:
            # 随机混合：大额和小额混搭，兼顾视觉冲击和数量多样性
            if remaining >= 100000:
                avg = remaining // cells_left
                large = [t for t in valid if t >= avg]
                if random.random() < 0.3 or not large:
                    chosen = random.choice(valid[:max(1, (len(valid) + 1) // 2)])
                else:
                    chosen = random.choice(large)
            else:
                chosen = random.choice(valid[:max(1, (len(valid) + 1) // 2)])
        else:
            avg = remaining // cells_left
            large = [t for t in valid if t >= avg]
            chosen = random.choice(large if large else valid)

        parts.append(chosen)
        remaining -= chosen

    return parts


def _generate_card(card_conf: dict) -> dict:
    """根据指定档位配置生成一张刮刮卡"""
    # 1. 按该档位精确概率抽总奖金
    total_prize = random.choices(
        card_conf["prize_values"], weights=card_conf["prize_weights"], k=1)[0]

    # 2. 按该档位单格档位拆分为各格奖金
    cell_prizes = _decompose_prize(
        total_prize, card_conf["cell_tiers"], card_conf["positions"])

    # 3. 分配到该档位格子（中奖格随机分布位置）
    cells = [{"is_win": False, "prize": 0}
             for _ in range(card_conf["positions"])]
    if cell_prizes:
        indices = random.sample(
            range(card_conf["positions"]), len(cell_prizes))
        for idx, prize in zip(indices, cell_prizes):
            cells[idx] = {"is_win": True, "prize": prize}

    return {
        "cells": cells,
        "total_prize": total_prize,
        "layout": card_conf["layout"],
    }


def _prize_label(amount: int) -> str:
    """奖金金额转短标签"""
    if amount >= 10000:
        w = amount // 10000
        if amount % 10000 == 0:
            return f"{w}万"
        return f"{w}.{amount % 10000 // 1000}万"
    return str(amount)


def _card_to_str(card_data: dict) -> str:
    """将卡片按档位排布格式化为文本（纯文本，无制表符）"""
    cells = card_data["cells"]
    layout = card_data.get("layout")
    if not layout:
        # 回退：按 CARD_COLS 均分行
        layout = [CARD_COLS] * ((len(cells) + CARD_COLS - 1) // CARD_COLS)
    lines = []
    idx = 0
    for row_len in layout:
        parts = []
        for c in cells[idx:idx + row_len]:
            if c["is_win"]:
                parts.append(f"{_prize_label(c['prize']):>3}")
            else:
                parts.append("  ❌ ")
        lines.append("  ".join(parts))
        idx += row_len
    return "\n".join(lines)


def _fmt_money(amount: int) -> str:
    """格式化金额，支持负数"""
    sign = "-" if amount < 0 else ""
    s = str(abs(amount))
    result = []
    for i, ch in enumerate(reversed(s)):
        if i > 0 and i % 3 == 0:
            result.append(",")
        result.append(ch)
    return sign + "".join(reversed(result))
