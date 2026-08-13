"""
NTE 刮刮乐 - AstrBot 插件
复刻 NTE 游戏的刮刮乐玩法
"""

import base64
from datetime import date, datetime
import json
import random
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import aiohttp

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import Node, Nodes, Plain, At
from astrbot.core.utils.astrbot_path import get_astrbot_data_path
from astrbot.core.utils.quoted_message_parser import extract_quoted_message_text


# ============================================================
# 卡片档位配置（2 万 / 3 万 / 5 万方斯三档）
# ============================================================
CARD_POSITIONS = 15
CARD_ROWS = 3
CARD_COLS = 5

# 各档卡片配置：
#   cost       - 售价（方斯）
#   cell_tiers - 单格可用奖金档位
#   prize_dist - 总奖金概率分布表（来自游戏实际数据）[(总奖金, 概率%), ...]
CARD_TYPES = {
    20000: {
        "cost": 20000,
        "daily_limit": 20,
        "bookmark_reward": 1,
        "positions": 15,
        "layout": [5, 5, 5],
        "cell_tiers": [10000, 20000, 30000, 50000, 100000, 150000,
                       200000, 300000, 500000],
        "prize_dist": [
            (0, 28.4892), (10000, 54.4646), (20000, 10.8929), (30000, 5.8654), (40000, 0.1173),
            (50000, 0.0922), (60000, 0.013), (70000, 0.0038), (80000, 0.0096), (90000, 0.008),
            (100000, 0.0155), (110000, 0.0017), (120000, 0.0044), (130000, 0.0019), (140000, 0.0019),
            (150000, 0.0038), (160000, 0.0021), (170000, 0.0006), (180000, 0.0013), (190000, 0.0008),
            (200000, 0.0082), (210000, 0.0003), (220000, 0.0003), (230000, 0.0003), (240000, 0.0003),
            (250000, 0.0002), (260000, 0.0002), (280000, 0.0001), (290000, 0.0001), (300000, 0.0001),
            (350000, 0.00004), (400000, 0.00004), (500000, 0.00004),
        ],
    },
    30000: {
        "cost": 30000,
        "daily_limit": 30,
        "bookmark_reward": 3,
        "positions": 15,
        "layout": [5, 5, 5],
        "cell_tiers": [10000, 20000, 30000, 50000, 100000, 150000, 200000,
                       300000, 500000, 800000, 1000000, 1500000],
        "prize_dist": [
            (0, 22.7142), (20000, 25.959), (30000, 25.959), (40000, 9.7346), (50000, 6.4898),
            (60000, 1.9469), (70000, 0.649), (80000, 1.6224), (90000, 1.6224), (100000, 1.9469),
            (110000, 0.1298), (120000, 0.3569), (130000, 0.1622), (140000, 0.1947), (150000, 0.2596),
            (160000, 0.013), (170000, 0.0065), (180000, 0.0211), (190000, 0.0065), (200000, 0.0227),
            (210000, 0.0081), (220000, 0.0065), (230000, 0.0065), (240000, 0.0146), (250000, 0.0114),
            (260000, 0.0065), (270000, 0.0081), (280000, 0.0032), (290000, 0.0032), (300000, 0.0341),
            (320000, 0.0032), (330000, 0.0019), (340000, 0.0019), (350000, 0.0052), (360000, 0.0052),
            (380000, 0.0019), (390000, 0.0019), (400000, 0.0091), (420000, 0.0026), (430000, 0.0006),
            (440000, 0.0006), (450000, 0.0084), (460000, 0.0013), (470000, 0.0006), (480000, 0.0013),
            (490000, 0.0013), (500000, 0.0078), (510000, 0.0003), (520000, 0.0003), (530000, 0.0003),
            (540000, 0.0003), (550000, 0.001), (560000, 0.0003), (570000, 0.0002), (580000, 0.0002),
            (590000, 0.0002), (600000, 0.0031), (620000, 0.0005), (630000, 0.0003), (640000, 0.0003),
            (650000, 0.0013), (660000, 0.0006), (680000, 0.0003), (690000, 0.0003), (700000, 0.0015),
            (720000, 0.0003), (750000, 0.0011), (800000, 0.0016), (820000, 0.0002), (830000, 0.0002),
            (840000, 0.0002), (850000, 0.0003), (860000, 0.0003), (880000, 0.0002), (890000, 0.0002),
            (900000, 0.0023), (920000, 0.0003), (930000, 0.0002), (940000, 0.0002), (950000, 0.0008),
            (960000, 0.0003), (980000, 0.0002), (990000, 0.0002), (1000000, 0.0019), (1020000, 0.0001),
            (1030000, 0.0001), (1040000, 0.0001), (1050000, 0.0002), (1060000, 0.0001), (1080000, 0.0001),
            (1090000, 0.0001), (1100000, 0.0004), (1120000, 0.0001), (1150000, 0.0002), (1200000, 0.0003),
            (1220000, 0.00003), (1230000, 0.00003), (1240000, 0.00003), (1250000, 0.0001), (1260000, 0.0001),
            (1280000, 0.00003), (1290000, 0.00003), (1300000, 0.0004), (1320000, 0.00003), (1350000, 0.0001),
            (1400000, 0.0002), (1450000, 0.0001), (1500000, 0.0003),
        ],
    },
    50000: {
        "cost": 50000,
        "daily_limit": 50,
        "bookmark_reward": 5,
        "positions": 12,
        "layout": [4, 4, 4],
        "cell_tiers": [20000, 50000, 100000, 150000, 200000,
                       300000, 500000, 800000, 1000000, 1500000],
        "prize_dist": [
            (0, 21.1851), (20000, 10.5926), (40000, 21.1851), (50000, 21.1851), (60000, 2.7541),
            (70000, 2.7541), (80000, 2.7541), (90000, 2.7541), (100000, 8.2622), (110000, 0.4237),
            (120000, 1.2711), (130000, 0.4237), (140000, 1.2711), (150000, 1.6948), (160000, 0.1907),
            (170000, 0.1271), (180000, 0.1907), (190000, 0.1271), (200000, 0.4449), (210000, 0.0212),
            (220000, 0.0318), (230000, 0.0212), (240000, 0.0318), (250000, 0.0741), (260000, 0.0318),
            (280000, 0.0318), (300000, 0.1059), (320000, 0.0013), (340000, 0.0013), (350000, 0.0042),
            (360000, 0.0013), (380000, 0.0013), (400000, 0.0055), (420000, 0.0008), (440000, 0.0008),
            (450000, 0.0042), (460000, 0.0008), (470000, 0.0004), (480000, 0.0008), (490000, 0.0004),
            (500000, 0.0064), (510000, 0.0002), (520000, 0.0002), (530000, 0.0002), (540000, 0.0002),
            (550000, 0.0017), (560000, 0.0002), (580000, 0.0002), (600000, 0.0032), (620000, 0.0006),
            (640000, 0.0006), (650000, 0.0019), (660000, 0.0006), (680000, 0.0006), (700000, 0.0034),
            (750000, 0.0019), (800000, 0.0034), (820000, 0.0002), (840000, 0.0002), (850000, 0.0004),
            (860000, 0.0002), (880000, 0.0002), (900000, 0.0018), (920000, 0.0001), (940000, 0.0001),
            (950000, 0.0007), (960000, 0.0001), (980000, 0.0001), (1000000, 0.0018), (1020000, 0.00004),
            (1040000, 0.00004), (1050000, 0.0002), (1060000, 0.00004), (1080000, 0.00004), (1100000, 0.0003),
            (1150000, 0.0001), (1200000, 0.0004), (1220000, 0.00002), (1240000, 0.00002), (1250000, 0.0001),
            (1260000, 0.00002), (1280000, 0.00002), (1300000, 0.0003), (1350000, 0.0001), (1400000, 0.0003),
            (1450000, 0.00004), (1500000, 0.0002), (1520000, 0.00002), (1540000, 0.00002), (1550000, 0.00004),
            (1560000, 0.00002), (1580000, 0.00002), (1600000, 0.0003), (1620000, 0.00002), (1640000, 0.00002),
            (1650000, 0.0001), (1660000, 0.00002), (1680000, 0.00002), (1700000, 0.0001), (1750000, 0.0001),
            (1800000, 0.0003), (1900000, 0.0001), (1950000, 0.00002), (2000000, 0.0001), (2020000, 0.00002),
            (2040000, 0.00002), (2050000, 0.00004), (2060000, 0.00002), (2080000, 0.00002), (2100000, 0.0001),
            (2150000, 0.00004), (2200000, 0.0001), (2300000, 0.0001), (2400000, 0.0001), (2450000, 0.00002),
            (2500000, 0.0001),
        ],
    },
}

# 构建各档概率权重组与派生信息
for _card_conf in CARD_TYPES.values():
    _card_conf["prize_values"] = [p for p, _ in _card_conf["prize_dist"]]
    _card_conf["prize_weights"] = [w for _, w in _card_conf["prize_dist"]]
    _card_conf["max_prize"] = max(p for p, _ in _card_conf["prize_dist"])
    _card_conf["label"] = f"{_card_conf['cost'] // 10000}万"

# 初始余额
INITIAL_BALANCE = 3000000

# 每日限购已按档位独立配置于 CARD_TYPES（2万=20 / 3万=30 / 5万=50）

# 刮取钱档位 [(金额, 描述), ...]
PENSION_TIERS = [
    (300000,  "管理局给娜娜莉的医疗补贴下来了，手头宽裕了些"),
    (500000,  "雨燕出行跑了一天单，腰都要断了，赚点辛苦钱。"),
    (700000,  "背着店长偷偷把伊波恩抵押了…发了笔小财！"),
    (1000000, "赶上粉爪大劫案，浑水摸鱼捞了一笔，赶紧跑路！"),
]

# 注册的全部 LLM 工具名（用于开关统一激活/停用）
LLM_TOOL_NAMES = [
    "scratch_ntc_card",
    "daily_pension",
    "check_scratch_balance",
    "give_money",
    "give_cards",
    "admin_approve_request",
    "admin_reject_request",
    "list_pending_requests",
]


# ----------------------------------------------------------
# 卡片生成（基于精确概率分布）
# ----------------------------------------------------------
def _decompose_prize(total: int, cell_tiers: List[int],
                     positions: int = CARD_POSITIONS) -> List[int]:
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


# ----------------------------------------------------------
# 排行榜 HTML 模板
# ----------------------------------------------------------
LEADERBOARD_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<link rel="preconnect" href="https://cdn.jsdelivr.net">
<link rel="stylesheet" crossorigin="anonymous" href="https://cdn.jsdelivr.net/npm/misans@4.1.0/lib/Normal/MiSans-Medium.min.css" /> 
<link rel="stylesheet" crossorigin="anonymous" href="https://cdn.jsdelivr.net/npm/misans@4.1.0/lib/Normal/MiSans-Bold.min.css" />
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{height:fit-content}
body{font-family:"MiSans",sans-serif;width:840px;}
.outer-frame{background: linear-gradient(180deg, #232225, #FFF584);width: 840px;padding: 16px;min-height:100vh;}
.title{text-align:right;font-size:42px;font-weight:1000;transform:skewX(-7deg);color:#F0C954;padding:8px 16px 12px 0}
.header{display:flex;align-items:center;background:linear-gradient(180deg,#3a3020,#2a2218);border:1px solid rgba(0,0,0,.1);border-radius:12px;margin-bottom:12px}
.header div{font-size:20px;font-weight:700;color:#D2D2D2;-webkit-text-stroke:#000000 1px}
.h-rank{flex:260 0 0;text-align:center;background:#9F7D42;border-radius:12px 0 0 12px}
.h-name{flex:790 0 0;padding:0 16px;background:#7D46A2}
.h-name span{padding-left:100px}
.h-money{flex:510 0 0;text-align:center;background:#464544;padding:0 15px 0 0;border-radius:0 12px 12px 0}
.h-rank span,.h-name span,.h-money span{display:inline-block;transform:skewX(-7deg)}
.card{margin-bottom:8px;overflow:hidden}
.row{display:flex;align-items:stretch;min-height:78px;overflow:hidden;position:relative}
.badge{flex:260 0 0;display:flex;flex-direction:column;align-items:center;justify-content:center;position:relative;--r:6px;-webkit-mask:radial-gradient(circle at 8px 8px,transparent var(--r),#fff var(--r)) -8px -8px/100% 100% no-repeat,radial-gradient(circle at calc(100% - 8px) 8px,transparent var(--r),#fff var(--r)) 8px -8px/100% 100% no-repeat,radial-gradient(circle at calc(100% - 8px) calc(100% - 8px),transparent var(--r),#fff var(--r)) 8px 8px/100% 100% no-repeat,radial-gradient(circle at 8px calc(100% - 8px),transparent var(--r),#fff var(--r)) -8px 8px/100% 100% no-repeat;mask:radial-gradient(circle at 8px 8px,transparent var(--r),#fff var(--r)) -8px -8px/100% 100% no-repeat,radial-gradient(circle at calc(100% - 8px) 8px,transparent var(--r),#fff var(--r)) 8px -8px/100% 100% no-repeat,radial-gradient(circle at calc(100% - 8px) calc(100% - 8px),transparent var(--r),#fff var(--r)) 8px 8px/100% 100% no-repeat,radial-gradient(circle at 8px calc(100% - 8px),transparent var(--r),#fff var(--r)) -8px 8px/100% 100% no-repeat}
.badge::before{content:'';position:absolute;inset:0;pointer-events:none;--r:8px;--w:2px;--c:#3C3833;--xc:#838383;background:radial-gradient(var(--r) at var(--r) var(--r),transparent calc(97% - var(--w)),var(--c) calc(100% - var(--w)) 98%,transparent) calc(-1*var(--r)) calc(-1*var(--r))/100% 100% no-repeat,radial-gradient(var(--r) at calc(100% - var(--r)) var(--r),transparent calc(97% - var(--w)),var(--c) calc(100% - var(--w)) 98%,transparent) var(--r) calc(-1*var(--r))/100% 100% no-repeat,radial-gradient(var(--r) at calc(100% - var(--r)) calc(100% - var(--r)),transparent calc(97% - var(--w)),var(--c) calc(100% - var(--w)) 98%,transparent) var(--r) var(--r)/100% 100% no-repeat,radial-gradient(var(--r) at var(--r) calc(100% - var(--r)),transparent calc(97% - var(--w)),var(--c) calc(100% - var(--w)) 98%,transparent) calc(-1*var(--r)) var(--r)/100% 100% no-repeat,linear-gradient(var(--c),var(--c)) var(--r) 0/calc(100% - 2*var(--r)) var(--w) no-repeat,linear-gradient(var(--c),var(--c)) var(--r) 100%/calc(100% - 2*var(--r)) var(--w) no-repeat,linear-gradient(var(--c),var(--c)) 0 var(--r)/var(--w) calc(100% - 2*var(--r)) no-repeat,repeating-linear-gradient(to bottom,var(--xc) 0,var(--xc) 3px,transparent 3px,transparent 6px) 100% var(--r)/var(--w) calc(100% - 2*var(--r)) no-repeat}
.badge .num{font-size:32px;font-weight:900;line-height:1;color:#FFF;transform:skewX(-7deg);-webkit-text-stroke:2px #090909;z-index:1}
.badge .line{position:absolute;right:0;top:10%;height:80%;width:1px}
.name-section{flex:790 0 0;display:flex;flex-direction:column;justify-content:space-between;padding:5px 16px;position:relative;min-width:0;background:linear-gradient(180deg,#DDD,#FFF);--r:6px;-webkit-mask:radial-gradient(circle at 8px 8px,transparent var(--r),#fff var(--r)) -8px -8px/100% 100% no-repeat,radial-gradient(circle at calc(100% - 8px) 8px,transparent var(--r),#fff var(--r)) 8px -8px/100% 100% no-repeat,radial-gradient(circle at calc(100% - 8px) calc(100% - 8px),transparent var(--r),#fff var(--r)) 8px 8px/100% 100% no-repeat,radial-gradient(circle at 8px calc(100% - 8px),transparent var(--r),#fff var(--r)) -8px 8px/100% 100% no-repeat;mask:radial-gradient(circle at 8px 8px,transparent var(--r),#fff var(--r)) -8px -8px/100% 100% no-repeat,radial-gradient(circle at calc(100% - 8px) 8px,transparent var(--r),#fff var(--r)) 8px -8px/100% 100% no-repeat,radial-gradient(circle at calc(100% - 8px) calc(100% - 8px),transparent var(--r),#fff var(--r)) 8px 8px/100% 100% no-repeat,radial-gradient(circle at 8px calc(100% - 8px),transparent var(--r),#fff var(--r)) -8px 8px/100% 100% no-repeat}
.name-section::before{content:'';position:absolute;inset:0;pointer-events:none;--r:8px;--w:2px;--c:#3C3833;--xc:#838383;background:radial-gradient(var(--r) at var(--r) var(--r),transparent calc(97% - var(--w)),var(--c) calc(100% - var(--w)) 98%,transparent) calc(-1*var(--r)) calc(-1*var(--r))/100% 100% no-repeat,radial-gradient(var(--r) at calc(100% - var(--r)) var(--r),transparent calc(97% - var(--w)),var(--c) calc(100% - var(--w)) 98%,transparent) var(--r) calc(-1*var(--r))/100% 100% no-repeat,radial-gradient(var(--r) at calc(100% - var(--r)) calc(100% - var(--r)),transparent calc(97% - var(--w)),var(--c) calc(100% - var(--w)) 98%,transparent) var(--r) var(--r)/100% 100% no-repeat,radial-gradient(var(--r) at var(--r) calc(100% - var(--r)),transparent calc(97% - var(--w)),var(--c) calc(100% - var(--w)) 98%,transparent) calc(-1*var(--r)) var(--r)/100% 100% no-repeat,linear-gradient(var(--c),var(--c)) var(--r) 0/calc(100% - 2*var(--r)) var(--w) no-repeat,linear-gradient(var(--c),var(--c)) var(--r) 100%/calc(100% - 2*var(--r)) var(--w) no-repeat,repeating-linear-gradient(to bottom,var(--xc) 0,var(--xc) 3px,transparent 3px,transparent 6px) 0 var(--r)/var(--w) calc(100% - 2*var(--r)) no-repeat,repeating-linear-gradient(to bottom,var(--xc) 0,var(--xc) 3px,transparent 3px,transparent 6px) 100% var(--r)/var(--w) calc(100% - 2*var(--r)) no-repeat}
.id-prefix{font-size:8px;padding:0 8px;color:#000;background:#A2A2A2;border-radius:8px}
.id-text{font-size:8px;opacity:.5;margin-bottom:3px;font-weight:700}
.name-text{font-size:18px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-left:100px}
.barcode{margin-top:6px;height:10px;width:80px}
.money-section{flex:510 0 0;display:flex;align-items:center;justify-content:flex-end;padding:12px 15px 12px 0;gap:10px;background:linear-gradient(180deg,#DDD,#FFF);position:relative;--r:6px;-webkit-mask:radial-gradient(circle at 8px 8px,transparent var(--r),#fff var(--r)) -8px -8px/100% 100% no-repeat,radial-gradient(circle at calc(100% - 8px) 8px,transparent var(--r),#fff var(--r)) 8px -8px/100% 100% no-repeat,radial-gradient(circle at calc(100% - 8px) calc(100% - 8px),transparent var(--r),#fff var(--r)) 8px 8px/100% 100% no-repeat,radial-gradient(circle at 8px calc(100% - 8px),transparent var(--r),#fff var(--r)) -8px 8px/100% 100% no-repeat;mask:radial-gradient(circle at 8px 8px,transparent var(--r),#fff var(--r)) -8px -8px/100% 100% no-repeat,radial-gradient(circle at calc(100% - 8px) 8px,transparent var(--r),#fff var(--r)) 8px -8px/100% 100% no-repeat,radial-gradient(circle at calc(100% - 8px) calc(100% - 8px),transparent var(--r),#fff var(--r)) 8px 8px/100% 100% no-repeat,radial-gradient(circle at 8px calc(100% - 8px),transparent var(--r),#fff var(--r)) -8px 8px/100% 100% no-repeat}
.money-section::before{content:'';position:absolute;inset:0;pointer-events:none;--r:8px;--w:2px;--c:#3C3833;--xc:#838383;background:radial-gradient(var(--r) at var(--r) var(--r),transparent calc(97% - var(--w)),var(--c) calc(100% - var(--w)) 98%,transparent) calc(-1*var(--r)) calc(-1*var(--r))/100% 100% no-repeat,radial-gradient(var(--r) at calc(100% - var(--r)) var(--r),transparent calc(97% - var(--w)),var(--c) calc(100% - var(--w)) 98%,transparent) var(--r) calc(-1*var(--r))/100% 100% no-repeat,radial-gradient(var(--r) at calc(100% - var(--r)) calc(100% - var(--r)),transparent calc(97% - var(--w)),var(--c) calc(100% - var(--w)) 98%,transparent) var(--r) var(--r)/100% 100% no-repeat,radial-gradient(var(--r) at var(--r) calc(100% - var(--r)),transparent calc(97% - var(--w)),var(--c) calc(100% - var(--w)) 98%,transparent) calc(-1*var(--r)) var(--r)/100% 100% no-repeat,linear-gradient(var(--c),var(--c)) var(--r) 0/calc(100% - 2*var(--r)) var(--w) no-repeat,linear-gradient(var(--c),var(--c)) var(--r) 100%/calc(100% - 2*var(--r)) var(--w) no-repeat,linear-gradient(var(--c),var(--c)) 100% var(--r)/var(--w) calc(100% - 2*var(--r)) no-repeat,repeating-linear-gradient(to bottom,var(--xc) 0,var(--xc) 3px,transparent 3px,transparent 6px) 0 var(--r)/var(--w) calc(100% - 2*var(--r)) no-repeat}
.coin-icon{height:24px;width:auto;flex-shrink:0;margin-right:0}
.money-text{font-size:25px;font-weight:900;color:#FFC431;-webkit-text-stroke:1.5px #090909;text-stroke:1px #090909}
.hot-tag{position:absolute;right:16px;bottom:4px;font-size:8px;letter-spacing:1px;opacity:.25;font-weight:700}
.dash{width:1px;align-self:stretch;margin:12px 0;border-left:1px dashed rgba(150,130,80,.4);flex-shrink:0}
.card-normal .badge{background:#5D7893}
.card-normal .badge .line{background:#c0b090}
.card-normal .name-text{color:#2a2218}
.card-normal .id-text{color:#a09070}
.card-normal .barcode{background:repeating-linear-gradient(90deg,transparent 0,transparent 2px,rgba(100,80,40,.12) 2px,rgba(100,80,40,.12) 3px,transparent 3px,transparent 5px)}
.card-normal .dash{border-left-color:#c0b090}
.card-normal .hot-tag{color:#a09070}
.card-r1 .badge{background:linear-gradient(180deg,#c8a030,#8a6a18)}
.card-r2 .badge{background:linear-gradient(180deg,#b0b0b0,#707070)}
.card-r3 .badge{background:linear-gradient(180deg,#c08040,#7a4a20)}
</style></head><body>
<div class="outer-frame">
<div class="title">{{ title }}</div>
<div class="header">
    <div class="h-rank"><span>排名</span></div>
    <div class="h-name"><span>名称</span></div>
    <div class="h-money"><span>财富值</span></div>
</div>
{% for item in items %}
<div class="card card-normal {% if item.rank <= 3 %}card-r{{ item.rank }}{% endif %}">
    <div class="row">
        <div class="badge"><div class="num">{{ item.rank }}</div></div>
        <div class="name-section">
            <div class="id-text"><span class="id-prefix">NTE</span> NO.{{ '%06d' % item.uid_int if item.uid_int else '000000' }}</div>
            <div class="name-text">{{ item.name }}</div>
            <div class="barcode"></div>
        </div>
        <div class="money-section"><img src="{{ coin_icon }}" alt="Coin" class="coin-icon"><div class="money-text">{{ item.amount }}</div></div>
    </div>
</div>
{% endfor %}
</div>
</body></html>"""


# ============================================================
# 插件主类
# ============================================================
@register(
    "nte_scratch_card",
    "CavinGou",
    "复刻 NTE 游戏的刮刮乐玩法",
    "1.3.0",
)
class NteScratchCardPlugin(Star):
    """NTE 刮刮乐插件"""

    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        self.data_dir = Path(get_astrbot_data_path()) / "plugin_data" / self.name

        self._balance_path = self.data_dir / "balance.json"
        self._stats_path = self.data_dir / "stats.json"

        # NapCat 配置
        self.napcat_host = self.config.get("napcat_host", "127.0.0.1:3000")
        self.napcat_token = self.config.get("napcat_token", "")

        # 每日限购已按档位独立配置于 CARD_TYPES（2万=20 / 3万=30 / 5万=50）

        # 富爪榜排除天数：超过 N 天未抽卡的用户不进榜（0 = 不过滤）
        self._lb_inactive_days = max(0, int(self.config.get("leaderboard_inactive_days", 7)))

        # 刮取钱档位（从配置读取，回退到代码常量）
        self._pension_tiers = self._parse_pension_tiers(
            self.config.get("pension_tiers", []))

        # LLM 工具总开关（默认开启）；关闭时统一停用所有注册的 LLM 工具，
        # 模型将看不到这些工具、不会通过自然语言触发
        self._enable_llm = bool(self.config.get("enable_llm_tools", True))
        try:
            for name in LLM_TOOL_NAMES:
                if self._enable_llm:
                    self.context.activate_llm_tool(name)
                else:
                    self.context.deactivate_llm_tool(name)
        except Exception as e:
            logger.warning(f"LLM 工具开关应用失败: {e}")

        # 待审批申请（成员申请 -> 管理员审批）
        self._pending_path = self.data_dir / "pending_requests.json"
        self._pending_requests: List[dict] = []
        self._req_seq = 0

        # uid -> 余额
        self._user_balance: Dict[str, int] = {}
        # uid -> {total_spent, total_won, cards_bought, cards_won}
        self._user_stats: Dict[str, dict] = {}

        self._load()

    # ----------------------------------------------------------
    # 数据持久化
    # ----------------------------------------------------------
    def _load(self):
        for path, attr in [(self._balance_path, "_user_balance"),
                            (self._stats_path, "_user_stats")]:
            if path.exists():
                try:
                    setattr(self, attr, json.loads(path.read_text("utf-8")))
                except Exception as e:
                    logger.error(f"加载 {path.name} 失败: {e}")
                    setattr(self, attr, {})

        # 加载待审批申请
        if self._pending_path.exists():
            try:
                self._pending_requests = json.loads(
                    self._pending_path.read_text("utf-8"))
                for r in self._pending_requests:
                    try:
                        n = int(str(r.get("id", "REQ-0")).split("-")[-1])
                        self._req_seq = max(self._req_seq, n)
                    except Exception:
                        pass
            except Exception as e:
                logger.error(f"加载 {self._pending_path.name} 失败: {e}")
                self._pending_requests = []

    def _save_balance(self):
        self._balance_path.write_text(
            json.dumps(self._user_balance, ensure_ascii=False), "utf-8")

    def _parse_pension_tiers(self, raw) -> List[Tuple[int, str]]:
        """解析配置中的取钱档位为 [(金额, 描述), ...]"""
        if not raw or not isinstance(raw, list):
            return list(PENSION_TIERS)
        try:
            tiers = []
            for item in raw:
                if not isinstance(item, dict):
                    continue
                amount = int(item.get("amount", 0))
                desc = str(item.get("desc", "")).strip()
                if amount <= 0 or not desc:
                    continue
                tiers.append((amount, desc))
            return tiers if len(tiers) >= 2 else list(PENSION_TIERS)
        except Exception:
            return list(PENSION_TIERS)

    def _save_stats(self):
        self._stats_path.write_text(
            json.dumps(self._user_stats, ensure_ascii=False), "utf-8")

    def _save_pending(self):
        self._pending_path.write_text(
            json.dumps(self._pending_requests, ensure_ascii=False), "utf-8")

    def _ensure_user(self, uid: str):
        if uid not in self._user_balance:
            self._user_balance[uid] = INITIAL_BALANCE
        if uid not in self._user_stats:
            self._user_stats[uid] = {
                "total_spent": 0,
                "total_won": 0,
                "cards_bought": 0,
                "cards_won": 0,
                "daily_date": "",
                "daily_bought": 0,
                "daily_extra": 0,
                "daily_bought_by_tier": {str(k): 0 for k in CARD_TYPES},
                "daily_extra_by_tier": {str(k): 0 for k in CARD_TYPES},
                "daily_spent": 0,
                "daily_won": 0,
                "daily_cards_won": 0,
                "pension_date": "",
                "cycle_order": [],
                "cycle_pos": 0,
                "group_id": "",
                "last_scratch_date": "",
                "bookmarks": 0,  # 回声书签（道具），购卡累计，未来可兑换
            }

    def _tier_daily(self, stats: dict) -> Tuple[dict, dict]:
        """获取/初始化各档今日已购张数与额外额度（各档独立限购）。
        返回 (daily_bought_by_tier, daily_extra_by_tier)，key 为档位字符串。"""
        bought = stats.setdefault(
            "daily_bought_by_tier", {str(k): 0 for k in CARD_TYPES})
        extra = stats.setdefault(
            "daily_extra_by_tier", {str(k): 0 for k in CARD_TYPES})
        for k in CARD_TYPES:
            bought.setdefault(str(k), 0)
            extra.setdefault(str(k), 0)
        return bought, extra

    # ----------------------------------------------------------
    # NapCat API: 获取群成员信息
    # ----------------------------------------------------------
    async def _get_member_info(self, group_id: str, user_id: str) -> Tuple[Optional[dict], Optional[str]]:
        """通过 NapCat API 获取群成员信息。返回 (data_dict, error)"""
        try:
            headers = {"Authorization": f"Bearer {self.napcat_token}"} if self.napcat_token else {}
            payload = {"group_id": int(group_id), "user_id": int(user_id), "no_cache": False}
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"http://{self.napcat_host}/get_group_member_info",
                    headers=headers, json=payload, timeout=10
                ) as resp:
                    data = await resp.json()
                    if data.get("status") == "ok" and "data" in data:
                        return data["data"], None
                    return None, str(data)
        except Exception as e:
            return None, str(e)

    async def _get_group_members(self, group_id: str) -> Tuple[Optional[List[dict]], Optional[str]]:
        """通过 NapCat API 获取群成员列表。返回 (成员列表, error)"""
        try:
            headers = {"Authorization": f"Bearer {self.napcat_token}"} if self.napcat_token else {}
            payload = {"group_id": int(group_id), "no_cache": False}
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"http://{self.napcat_host}/get_group_member_list",
                    headers=headers, json=payload, timeout=15
                ) as resp:
                    data = await resp.json()
                    if data.get("status") == "ok" and "data" in data:
                        return data["data"], None
                    return None, str(data)
        except Exception as e:
            return None, str(e)

    # ----------------------------------------------------------
    # 指令: /刮刮乐[2|3|5] [数量]  - 购买指定档位并立即刮开
    # ----------------------------------------------------------
    def _parse_count(self, event: AstrMessageEvent) -> int:
        """解析购卡数量参数（默认 1，至少 1）"""
        args = event.message_str.strip().split()
        count = 1
        if len(args) >= 2:
            try:
                count = int(args[1])
                if count < 1:
                    count = 1
            except ValueError:
                pass
        return count

    async def _reply_scratch(self, event: AstrMessageEvent, card_type: int):
        """执行购卡并输出结果：单张为普通文本，多张为合并转发。"""
        async for r in self._do_scratch(event, self._parse_count(event), card_type):
            if isinstance(r, str):
                yield event.plain_result(r)
            else:
                yield event.chain_result(r)

    @filter.command("刮刮乐")
    async def scratch(self, event: AstrMessageEvent):
        """购买 5 万档刮刮卡并立即刮开，支持一次多张：/刮刮乐 10"""
        async for r in self._reply_scratch(event, 50000):
            yield r

    @filter.command("刮刮乐2")
    async def scratch2(self, event: AstrMessageEvent):
        """购买 2 万档刮刮卡并立即刮开：/刮刮乐2 [数量]"""
        async for r in self._reply_scratch(event, 20000):
            yield r

    @filter.command("刮刮乐3")
    async def scratch3(self, event: AstrMessageEvent):
        """购买 3 万档刮刮卡并立即刮开：/刮刮乐3 [数量]"""
        async for r in self._reply_scratch(event, 30000):
            yield r

    @filter.command("刮刮乐5")
    async def scratch5(self, event: AstrMessageEvent):
        """购买 5 万档刮刮卡并立即刮开：/刮刮乐5 [数量]"""
        async for r in self._reply_scratch(event, 50000):
            yield r

    @filter.command("刮全部")
    async def scratch_all(self, event: AstrMessageEvent):
        """购买全部档位今日剩余额度并立即刮开：/刮全部"""
        async for r in self._do_scratch_all(event):
            if isinstance(r, str):
                yield event.plain_result(r)
            else:
                yield event.chain_result(r)

    async def _do_scratch_all(self, event: AstrMessageEvent):
        """购买全部档位今日剩余额度并刮开，结果汇总为一条合并转发（汇总在前，各张随后）。"""
        uid = event.get_sender_id()
        self._ensure_user(uid)
        stats = self._user_stats[uid]
        today = date.today().isoformat()
        stats["last_scratch_date"] = today  # 记录最后抽卡日期（用于富爪榜过滤）
        if stats.get("daily_date") != today:
            stats["daily_date"] = today
            stats["daily_bought"] = 0
            stats["daily_extra"] = 0
            stats["daily_spent"] = 0
            stats["daily_won"] = 0
            stats["daily_cards_won"] = 0
            for _k in CARD_TYPES:
                stats.setdefault("daily_bought_by_tier", {})[str(_k)] = 0
                stats.setdefault("daily_extra_by_tier", {})[str(_k)] = 0

        bought_by_tier, extra_by_tier = self._tier_daily(stats)
        # 各档今日剩余张数
        remaining = {
            k: max(0, CARD_TYPES[k]["daily_limit"]
                   + extra_by_tier.get(str(k), 0)
                   - bought_by_tier.get(str(k), 0))
            for k in CARD_TYPES
        }
        total_count = sum(remaining.values())
        if total_count <= 0:
            yield "❌ 今日各档都已刮完，没有可购买的额度了！"
            return

        total_cost = sum(
            remaining[k] * CARD_TYPES[k]["cost"] for k in CARD_TYPES)
        if self._user_balance[uid] < total_cost:
            yield (
                f"❌ 余额不足！刮完全部 {total_count} 张需要 {_fmt_money(total_cost)} 方斯，"
                f"当前只有 {_fmt_money(self._user_balance[uid])} 方斯"
            )
            return

        # 扣款与统计
        self._user_balance[uid] -= total_cost
        stats["total_spent"] += total_cost
        stats["cards_bought"] += total_count
        stats["daily_bought"] += total_count
        stats["daily_spent"] += total_cost

        bot_uin = event.get_self_id()
        node_list = []
        tier_summaries = []
        total_won_all = 0
        win_count_all = 0

        for k in sorted(CARD_TYPES):
            conf = CARD_TYPES[k]
            n = remaining[k]
            if n <= 0:
                continue
            tier_won = 0
            tier_win = 0
            for i in range(1, n + 1):
                card = _generate_card(conf)
                prize = card["total_prize"]
                total_won_all += prize
                tier_won += prize
                if prize > 0:
                    win_count_all += 1
                    tier_win += 1
                stats["total_won"] += prize
                stats["daily_won"] += prize

                board = _card_to_str(card)
                prize_line = f"🎉 中奖 {_fmt_money(prize)} 方斯" if prize > 0 else "😅 未中奖"
                card_text = (
                    f"🎴 {conf['label']} · 第 {i}/{n} 张\n"
                    f"{board}\n"
                    f"{prize_line}\n"
                )
                node_list.append(Node(
                    name="刮刮乐",
                    uin=bot_uin,
                    content=[Plain(text=card_text)]
                ))
            bought_by_tier[str(k)] += n
            stats["bookmarks"] = stats.get("bookmarks", 0) + n * conf["bookmark_reward"]
            tier_summaries.append(
                f"{conf['label']} × {n} 张："
                f"{'🎉' if tier_win else '😅'} 中 {tier_win} 张，"
                f"共 {_fmt_money(tier_won)} 方斯"
            )

        # 发奖
        self._user_balance[uid] += total_won_all
        stats["cards_won"] += win_count_all
        stats["daily_cards_won"] += win_count_all
        self._save_balance()
        self._save_stats()
        net = stats["total_won"] - stats["total_spent"]
        batch_net = total_won_all - total_cost

        remaining_desc = "  ".join(
            f"{CARD_TYPES[k]['label']} "
            f"{max(0, CARD_TYPES[k]['daily_limit'] + extra_by_tier.get(str(k), 0) - bought_by_tier.get(str(k), 0))}张"
            for k in sorted(CARD_TYPES))

        bookmark_gained = sum(
            remaining[k] * CARD_TYPES[k]["bookmark_reward"] for k in CARD_TYPES)
        summary_lines = [
            f"🎴 刮刮乐 · 全部档位（共 {total_count} 张）",
            *tier_summaries,
            f"🔖 获得 {bookmark_gained} 个回声书签（累计 {stats.get('bookmarks', 0)} 个）",
            f"📊 本次收入: {'+' if batch_net >= 0 else '-'}{_fmt_money(abs(batch_net))} 方斯",
            f"📊 累计收入: {'+' if net >= 0 else '-'}{_fmt_money(abs(net))} 方斯",
            f"📅 今日剩余: {remaining_desc}",
            f"💰 当前余额: {_fmt_money(self._user_balance[uid])} 方斯",
        ]
        summary_nodes = [
            Node(name="刮刮乐", uin=bot_uin, content=[Plain(text=line)])
            for line in summary_lines
        ]
        # 汇总在前，各张随后
        node_list = summary_nodes + node_list

        yield [Nodes(nodes=node_list)]

    async def _do_scratch(self, event: AstrMessageEvent, count: int = 1,
                          card_type: int = 50000):
        """购买并刮开 count 张指定档位刮刮卡，生成结果：单张为 str，多张为合并转发节点列表。"""
        card_conf = CARD_TYPES.get(int(card_type), CARD_TYPES[50000])
        uid = event.get_sender_id()
        self._ensure_user(uid)

        # 记录用户所在群号
        try:
            gid = str(event.message_obj.group_id)
            if gid:
                self._user_stats[uid]["group_id"] = gid
        except Exception:
            pass

        # 检查每日限购（各档独立）
        stats = self._user_stats[uid]
        today = date.today().isoformat()
        stats["last_scratch_date"] = today  # 记录最后抽卡日期（用于富爪榜过滤）
        if stats.get("daily_date") != today:
            stats["daily_date"] = today
            stats["daily_bought"] = 0
            stats["daily_extra"] = 0
            stats["daily_spent"] = 0
            stats["daily_won"] = 0
            stats["daily_cards_won"] = 0
            for _k in CARD_TYPES:
                stats.setdefault("daily_bought_by_tier", {})[str(_k)] = 0
                stats.setdefault("daily_extra_by_tier", {})[str(_k)] = 0

        tier_key = str(int(card_type)) if int(card_type) in CARD_TYPES else "50000"
        bought_by_tier, extra_by_tier = self._tier_daily(stats)
        tier_limit = card_conf["daily_limit"]
        total_daily_tier = tier_limit + extra_by_tier[tier_key]
        remaining_daily = total_daily_tier - bought_by_tier[tier_key]
        if count > remaining_daily:
            yield f"❌ {card_conf['label']}档今日剩余 {remaining_daily} 张，不够买 {count} 张！"
            return

        # 检查余额
        total_cost = card_conf["cost"] * count
        if self._user_balance[uid] < total_cost:
            yield (
                f"❌ 余额不足！需要 {_fmt_money(total_cost)} 方斯，"
                f"当前只有 {_fmt_money(self._user_balance[uid])} 方斯"
            )
            return

        # 批量购卡
        self._user_balance[uid] -= total_cost
        stats["total_spent"] += total_cost
        stats["cards_bought"] += count
        stats["daily_bought"] += count
        stats["daily_spent"] += total_cost
        bought_by_tier[tier_key] += count
        stats["bookmarks"] = stats.get("bookmarks", 0) + count * card_conf["bookmark_reward"]

        total_won_all = 0
        win_count = 0

        if count == 1:
            # 单张：直接发结果
            card = _generate_card(card_conf)
            prize = card["total_prize"]
            total_won_all = prize
            win_count = 1 if prize > 0 else 0
            stats["total_won"] += prize
            stats["daily_won"] += prize

            board = _card_to_str(card)
            prize_line = f"🎉 中奖 {_fmt_money(prize)} 方斯！" if prize > 0 else "😅 未中奖"
            self._user_balance[uid] += prize
            stats["cards_won"] += win_count
            stats["daily_cards_won"] += win_count
            self._save_balance()
            self._save_stats()
            net = stats["total_won"] - stats["total_spent"]

            remaining_now = total_daily_tier - bought_by_tier[tier_key]
            lines = [
                f"🎴 刮刮乐 · {card_conf['label']}",
                board,
                prize_line,
                f"🔖 获得 {card_conf['bookmark_reward']} 个回声书签（累计 {stats.get('bookmarks', 0)} 个）",
                f"",
                f"💰 余额: {_fmt_money(self._user_balance[uid])} 方斯  |  📊 {'+' if net >= 0 else '-'}{_fmt_money(abs(net))}",
                f"📅 {card_conf['label']}档今日剩余: {remaining_now} / {total_daily_tier} 张",
            ]
            yield "\n".join(lines)
        else:
            # 多张：用合并转发
            bot_uin = event.get_self_id()
            node_list = []

            for i in range(1, count + 1):
                card = _generate_card(card_conf)
                prize = card["total_prize"]
                total_won_all += prize
                if prize > 0:
                    win_count += 1
                stats["total_won"] += prize
                stats["daily_won"] += prize

                board = _card_to_str(card)
                prize_line = f"🎉 中奖 {_fmt_money(prize)} 方斯" if prize > 0 else "😅 未中奖"
                card_text = (
                    f"🎴 {card_conf['label']} · 第 {i}/{count} 张\n"
                    f"{board}\n"
                    f"{prize_line}\n"
                )
                node_list.append(Node(
                    name="刮刮乐",
                    uin=bot_uin,
                    content=[Plain(text=card_text)]
                ))

            # 发奖
            self._user_balance[uid] += total_won_all
            stats["cards_won"] += win_count
            stats["daily_cards_won"] += win_count
            self._save_balance()
            self._save_stats()
            net = stats["total_won"] - stats["total_spent"]
            won_desc = f"🎉 中 {win_count}/{count} 张，共 {_fmt_money(total_won_all)} 方斯" if win_count > 0 else "😅 全部未中奖"

            # 汇总每项拆成单条消息（作为合并转发最前的一组节点）
            remaining_now = total_daily_tier - bought_by_tier[tier_key]
            batch_net = total_won_all - total_cost
            summary_lines = [
                won_desc,
                f"� 获得 {count * card_conf['bookmark_reward']} 个回声书签（累计 {stats.get('bookmarks', 0)} 个）",
                f"�📊 本次收入: {'+' if batch_net >= 0 else '-'}{_fmt_money(abs(batch_net))} 方斯",
                f"📊 累计收入: {'+' if net >= 0 else '-'}{_fmt_money(abs(net))} 方斯",
                f"📅 {card_conf['label']}档今日剩余: {remaining_now} / {total_daily_tier} 张",
                f"💰 当前余额: {_fmt_money(self._user_balance[uid])} 方斯",
            ]
            summary_nodes = [
                Node(name="刮刮乐", uin=bot_uin, content=[Plain(text=line)])
                for line in summary_lines
            ]
            # 汇总各项在前，后面再分各张
            node_list = summary_nodes + node_list

            yield [Nodes(nodes=node_list)]

    # ----------------------------------------------------------
    # 指令: /刮刮乐帮助  - 显示帮助
    # ----------------------------------------------------------
    @filter.command("刮刮乐帮助")
    async def help_cmd(self, event: AstrMessageEvent):
        """显示帮助信息"""
        lines = [
            "🎴 NTE 刮刮乐 - 帮助\n",
            "━━━ 指令列表 ━━━",
            f"刮刮乐 [数量]    购买5万档刮刮卡",
            f"刮刮乐2 [数量]   购买2万档刮刮卡",
            f"刮刮乐3 [数量]   购买3万档刮刮卡",
            f"刮刮乐5 [数量]   购买5万档刮刮卡",
            f"刮全部           刮完三档今日剩余额度",
            f"刮取钱           每日随机领取方斯（{len(self._pension_tiers)}档循环，发完重洗）",
            f"刮余额           查看余额和游戏统计",
            f"富爪榜           累计盈亏排行榜",
            f"富爪日榜         今日盈亏排行榜",
            f"刮刮乐帮助       显示此帮助",
        ]
        # 管理员专属指令
        if event.is_admin():
            lines += [
                "━━━ 管理员指令 ━━━",
                f"刮发钱 @用户 金额    给指定用户增加方斯余额",
                f"刮发卡 [数量] @用户  给指定用户增加今日额外购卡额度",
            ]
        lines += [
            "\n━━━ 介绍 ━━━",
            f"初始余额: 300万",
            "每日限购(各档独立): " + " / ".join(
                f"{CARD_TYPES[k]['label']} {CARD_TYPES[k]['daily_limit']}张"
                for k in sorted(CARD_TYPES)),
            "档位售价: " + " / ".join(
                _fmt_money(CARD_TYPES[k]["cost"]) for k in sorted(CARD_TYPES)) + " 方斯",
            "回声书签: " + " / ".join(
                f"{CARD_TYPES[k]['label']}+{CARD_TYPES[k]['bookmark_reward']}"
                for k in sorted(CARD_TYPES)) + "（购卡累计，未来可兑换）",
            f"格子: 3×5  |  最高奖: {_fmt_money(CARD_TYPES[50000]['max_prize'])} 方斯",
        ]
        yield event.plain_result("\n".join(lines))

    # ----------------------------------------------------------
    # 指令: /刮取钱  - 每日领取随机方斯
    # ----------------------------------------------------------
    @filter.command("刮取钱")
    async def pension(self, event: AstrMessageEvent):
        """每日阶段性领取方斯（周期内顺序随机）"""
        yield event.plain_result(await self._do_pension(event))

    async def _do_pension(self, event: AstrMessageEvent) -> str:
        """领取每日方斯福利，返回结果文本。"""
        uid = event.get_sender_id()
        self._ensure_user(uid)
        stats = self._user_stats[uid]

        today = date.today().isoformat()
        if stats.get("pension_date") == today:
            return "❌ 今天已经领过了，明天再来吧 😊"

        # 初始化或重新洗牌
        cycle_order = stats.get("cycle_order", [])
        cycle_pos = stats.get("cycle_pos", 0)
        tiers_len = len(self._pension_tiers)
        # 如果档位数量变了（配置修改过），也强制重置
        if (not cycle_order or cycle_pos >= tiers_len
                or len(cycle_order) != tiers_len
                or any(i >= tiers_len for i in cycle_order)):
            cycle_order = list(range(tiers_len))
            random.shuffle(cycle_order)
            cycle_pos = 0

        idx = cycle_order[cycle_pos]
        amount, msg = self._pension_tiers[idx]

        stats["pension_date"] = today
        stats["cycle_order"] = cycle_order
        stats["cycle_pos"] = cycle_pos + 1
        self._user_balance[uid] += amount
        self._save_balance()
        self._save_stats()

        return (
            f"💝 {msg}\n"
            f"获得 {_fmt_money(amount)} 方斯！\n"
            f"💰 当前余额: {_fmt_money(self._user_balance[uid])} 方斯"
        )

    # ----------------------------------------------------------
    # 指令: /余额  - 查看余额和统计
    # ----------------------------------------------------------
    @filter.command("刮余额")
    async def check_balance(self, event: AstrMessageEvent):
        """查看余额和游戏统计"""
        yield event.plain_result(await self._do_check_balance(event))

    async def _do_check_balance(self, event: AstrMessageEvent) -> str:
        """查看余额和游戏统计，返回结果文本。"""
        uid = event.get_sender_id()
        self._ensure_user(uid)

        balance = self._user_balance[uid]
        stats = self._user_stats[uid]

        # 跨天后重置每日限购
        today = date.today().isoformat()
        if stats.get("daily_date") != today:
            stats["daily_date"] = today
            stats["daily_bought"] = 0
            stats["daily_extra"] = 0
            stats["daily_spent"] = 0
            stats["daily_won"] = 0
            stats["daily_cards_won"] = 0
            for _k in CARD_TYPES:
                stats.setdefault("daily_bought_by_tier", {})[str(_k)] = 0
                stats.setdefault("daily_extra_by_tier", {})[str(_k)] = 0
            self._save_stats()

        net = stats["total_won"] - stats["total_spent"]
        win_rate = (stats["cards_won"] / stats["cards_bought"] * 100
                    if stats["cards_bought"] > 0 else 0)

        # 各档独立限购汇总
        bought_by_tier, extra_by_tier = self._tier_daily(stats)
        remaining_desc = "  |  ".join(
            f"{CARD_TYPES[k]['label']} "
            f"{CARD_TYPES[k]['daily_limit'] + extra_by_tier.get(str(k), 0) - bought_by_tier.get(str(k), 0)}"
            f"/{CARD_TYPES[k]['daily_limit'] + extra_by_tier.get(str(k), 0)}张"
            for k in sorted(CARD_TYPES)
        )

        lines = [
            "📊 个人数据\n",
            f"💰 余额: {_fmt_money(balance)} 方斯",
            f"📈 累计盈亏: {'+' if net >= 0 else '-'}{_fmt_money(abs(net))} 方斯",
            f"📅 今日剩余: {remaining_desc}",
            "",
            f"🔖 回声书签: {stats.get('bookmarks', 0)} 个（购卡累计，可用于未来兑换）",
            f"🎴 购买次数: {stats['cards_bought']} 张",
            f"🏆 中奖次数: {stats['cards_won']} 次",
            f"📊 中奖率: {win_rate:.1f}%",
            f"💵 总投入: {_fmt_money(stats['total_spent'])} 方斯",
            f"💵 总奖金: {_fmt_money(stats['total_won'])} 方斯",
        ]
        return "\n".join(lines)

    # ----------------------------------------------------------
    # 指令: /刮卡排行  - 排行榜
    # ----------------------------------------------------------
    @filter.command("富爪榜")
    async def leaderboard(self, event: AstrMessageEvent):
        """查看本群累计盈亏排行榜（不限数量）"""
        # 检查是否有实际购买过卡片的用户
        has_buyers = any(
            s.get("cards_bought", 0) > 0
            for s in self._user_stats.values()
        )
        if not has_buyers:
            yield event.plain_result("📭 暂无数据，快来 /刮刮乐 吧！")
            return

        # 获取当前群号，用于群隔离
        current_group = ""
        try:
            current_group = str(event.message_obj.group_id)
        except Exception:
            pass

        # 通过 NapCat API 获取当前群全部成员（含群名片），做跨群统一
        group_uids = set()
        name_map = {}
        members_data, _ = await self._get_group_members(current_group)
        if members_data:
            for m in members_data:
                uid = str(m.get("user_id", ""))
                if uid:
                    group_uids.add(uid)
                    name_map[uid] = m.get("card") or m.get("nickname", "")
        else:
            # 拿不到成员列表时回退：通过 group_id 字段筛选
            for uid, stats in self._user_stats.items():
                if stats.get("group_id") == current_group:
                    group_uids.add(uid)

        # 过滤：超过 N 天未抽卡的用户不进榜（N=0 不过滤）
        def _is_active(uid: str, stats: dict) -> bool:
            if self._lb_inactive_days <= 0:
                return True
            last = stats.get("last_scratch_date", "")
            if not last:
                return True  # 无记录视为活跃，避免误伤老用户
            try:
                days = (date.today() - date.fromisoformat(last)).days
            except ValueError:
                return True
            return days <= self._lb_inactive_days

        # 筛选当前群买过卡的用户（跨群统一 — 按当前群成员列表而非刮卡时的群）
        items = [
            (uid, stats.get("total_won", 0) - stats.get("total_spent", 0))
            for uid, stats in self._user_stats.items()
            if stats.get("cards_bought", 0) > 0
            and uid in group_uids
            and _is_active(uid, stats)
        ]
        if not items:
            yield event.plain_result("📭 暂无数据，快来 /刮刮乐 吧！")
            return

        items.sort(key=lambda x: x[1], reverse=True)

        def _get_name(uid: str) -> str:
            raw = name_map.get(uid, "")
            if not raw:
                return uid[-4:]
            return raw  # 不限制长度，由模板渲染时自动省略

        # 用 HTML 模板渲染排行榜图片
        try:
            rows_data = []
            for idx, (uid, net) in enumerate(items, 1):
                name = _get_name(uid)
                try:
                    uid_int = int(uid)
                except (ValueError, TypeError):
                    uid_int = 0
                rows_data.append({
                    "rank": idx,
                    "name": name,
                    "net": net,
                    "amount": _fmt_money(net),
                    "uid_int": uid_int,
                })
            # 读取 fons.png 转 base64 嵌入模板（t2i 远程服务无法访问本地文件）
            coin_png = Path(__file__).resolve().parent / "assets" / "fons.png"
            coin_b64 = base64.b64encode(coin_png.read_bytes()).decode()
            coin_data_uri = f"data:image/png;base64,{coin_b64}"
            url = await self.html_render(LEADERBOARD_HTML, {
                "title": "富爪榜",
                "total": len(items),
                "items": rows_data,
                "coin_icon": coin_data_uri,
            }, options={"type": "jpeg", "quality":100})
            yield event.image_result(url)
            return
        except Exception as e:
            logger.error(f"排行榜生图失败: {e}")

        # 回退文本榜
        lines = ["🏆 海特洛富爪榜\n"]
        for idx, (uid, net) in enumerate(items, 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(idx, f" {idx}. " if idx < 10 else f"{idx}.")
            sign = "+" if net >= 0 else "-"
            lines.append(f"{medal} {_get_name(uid)}   {sign}{_fmt_money(abs(net))} 方斯")

        yield event.plain_result("\n".join(lines))

    # ----------------------------------------------------------
    # 指令: /富爪日榜  - 今日盈亏排行榜
    # ----------------------------------------------------------
    @filter.command("富爪日榜")
    async def daily_leaderboard(self, event: AstrMessageEvent):
        """查看本群今日盈亏排行榜"""
        today = date.today().isoformat()

        # 检查今天是否有刮过卡的用户
        has_buyers = any(
            s.get("daily_date") == today and s.get("daily_spent", 0) > 0
            for s in self._user_stats.values()
        )
        if not has_buyers:
            yield event.plain_result("📭 今天还没有人刮卡，快来 /刮刮乐 吧！")
            return

        # 获取当前群号，用于群隔离
        current_group = ""
        try:
            current_group = str(event.message_obj.group_id)
        except Exception:
            pass

        # 通过 NapCat API 获取当前群全部成员（含群名片），做跨群统一
        group_uids = set()
        name_map = {}
        members_data, _ = await self._get_group_members(current_group)
        if members_data:
            for m in members_data:
                uid = str(m.get("user_id", ""))
                if uid:
                    group_uids.add(uid)
                    name_map[uid] = m.get("card") or m.get("nickname", "")
        else:
            # 拿不到成员列表时回退：通过 group_id 字段筛选
            for uid, stats in self._user_stats.items():
                if stats.get("group_id") == current_group:
                    group_uids.add(uid)

        # 筛选当前群今天刮过卡的用户，按今日盈亏排序
        items = [
            (uid, stats.get("daily_won", 0) - stats.get("daily_spent", 0))
            for uid, stats in self._user_stats.items()
            if stats.get("daily_date") == today
            and stats.get("daily_spent", 0) > 0
            and uid in group_uids
        ]
        if not items:
            yield event.plain_result("📭 今天还没有人刮卡，快来 /刮刮乐 吧！")
            return

        items.sort(key=lambda x: x[1], reverse=True)

        def _get_name(uid: str) -> str:
            raw = name_map.get(uid, "")
            if not raw:
                return uid[-4:]
            return raw  # 不限制长度，由模板渲染时自动省略

        # 用 HTML 模板渲染排行榜图片
        try:
            rows_data = []
            for idx, (uid, net) in enumerate(items, 1):
                name = _get_name(uid)
                try:
                    uid_int = int(uid)
                except (ValueError, TypeError):
                    uid_int = 0
                rows_data.append({
                    "rank": idx,
                    "name": name,
                    "net": net,
                    "amount": _fmt_money(net),
                    "uid_int": uid_int,
                })
            coin_png = Path(__file__).resolve().parent / "assets" / "fons.png"
            coin_b64 = base64.b64encode(coin_png.read_bytes()).decode()
            coin_data_uri = f"data:image/png;base64,{coin_b64}"
            url = await self.html_render(LEADERBOARD_HTML, {
                "title": "富爪日榜",
                "total": len(items),
                "items": rows_data,
                "coin_icon": coin_data_uri,
            }, options={"type": "jpeg", "quality": 100})
            yield event.image_result(url)
            return
        except Exception as e:
            logger.error(f"日榜生图失败: {e}")

        # 回退文本榜
        lines = ["🏆 海特洛富爪日榜\n"]
        for idx, (uid, net) in enumerate(items, 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(idx, f" {idx}. " if idx < 10 else f"{idx}.")
            sign = "+" if net >= 0 else "-"
            lines.append(f"{medal} {_get_name(uid)}   {sign}{_fmt_money(abs(net))} 方斯")

        yield event.plain_result("\n".join(lines))

    # ----------------------------------------------------------
    # 指令: /发钱 @用户 金额  - 管理员发钱
    # ----------------------------------------------------------
    @filter.command("刮发钱")
    async def give_money(self, event: AstrMessageEvent):
        """管理员给指定用户加方斯"""
        if not self._is_admin(event):
            yield event.plain_result("❌ 仅管理员可使用此指令")
            return
        uid = event.get_sender_id()
        self._ensure_user(uid)

        # 解析目标用户
        target_uid = None
        for comp in event.get_messages():
            if isinstance(comp, At):
                target_uid = str(comp.qq)
                break

        if not target_uid:
            yield event.plain_result("❌ 请 @ 要发钱的用户")
            return

        # 解析金额
        args = event.message_str.strip().split()
        amount = 0
        for a in args:
            try:
                amount = int(a)
                break
            except ValueError:
                continue

        if amount <= 0:
            yield event.plain_result("❌ 请输入有效金额")
            return

        self._ensure_user(target_uid)
        target_name = await self._get_target_name(event, target_uid)
        yield event.plain_result(
            await self._do_give_money(target_uid, target_name, amount)
        )

    async def _do_give_money(self, target_uid: str, target_name: str, amount: int) -> str:
        """给指定用户发方斯余额，返回结果文本。"""
        self._user_balance[target_uid] += amount
        self._save_balance()
        return (
            f"💸 发钱成功！\n"
            f"{target_name} 获得 {_fmt_money(amount)} 方斯\n"
            f"当前余额: {_fmt_money(self._user_balance[target_uid])} 方斯"
        )

    # ----------------------------------------------------------
    # 指令: /刮发卡 [数量] @用户  - 管理员发额外卡次数
    # ----------------------------------------------------------
    @filter.command("刮发卡")
    async def give_extra_cards(self, event: AstrMessageEvent):
        """管理员给指定用户增加今日可购买的卡次数"""
        if not self._is_admin(event):
            yield event.plain_result("❌ 仅管理员可使用此指令")
            return

        # 解析目标用户
        target_uid = None
        for comp in event.get_messages():
            if isinstance(comp, At):
                target_uid = str(comp.qq)
                break

        if not target_uid:
            yield event.plain_result("❌ 请 @ 要发卡的用户")
            return

        # 解析数量与档位（数字∈档位视为档位，其余正整数视为数量；默认 5 万档 1 张）
        args = event.message_str.strip().split()
        extra = 1
        tier = 50000
        for a in args:
            try:
                v = int(a)
            except ValueError:
                continue
            if v in CARD_TYPES:
                tier = v
            elif v >= 1:
                extra = v
        if extra < 1:
            extra = 1

        self._ensure_user(target_uid)
        target_name = await self._get_target_name(event, target_uid)
        yield event.plain_result(
            await self._do_give_cards(target_uid, target_name, extra, tier)
        )

    async def _do_give_cards(self, target_uid: str, target_name: str, extra: int,
                             tier: int = 50000) -> str:
        """给指定用户增加指定档位今日可购卡额度，返回结果文本。"""
        card_conf = CARD_TYPES.get(int(tier), CARD_TYPES[50000])
        tier_key = str(int(tier)) if int(tier) in CARD_TYPES else "50000"
        stats = self._user_stats[target_uid]

        # 如果是新的一天，先重置
        today = date.today().isoformat()
        if stats.get("daily_date") != today:
            stats["daily_date"] = today
            stats["daily_bought"] = 0
            stats["daily_extra"] = 0
            stats["daily_spent"] = 0
            stats["daily_won"] = 0
            stats["daily_cards_won"] = 0
            for _k in CARD_TYPES:
                stats.setdefault("daily_bought_by_tier", {})[str(_k)] = 0
                stats.setdefault("daily_extra_by_tier", {})[str(_k)] = 0

        # 累加该档位额外次数
        _, extra_by_tier = self._tier_daily(stats)
        extra_by_tier[tier_key] = extra_by_tier.get(tier_key, 0) + extra
        self._save_stats()

        limit = card_conf["daily_limit"]
        total_daily = limit + extra_by_tier[tier_key]
        bought_by_tier, _ = self._tier_daily(stats)
        remaining = total_daily - bought_by_tier.get(tier_key, 0)

        return (
            f"🎴 发卡成功！\n"
            f"{target_name} 获得 {card_conf['label']}档 +{extra} 张额外额度\n"
            f"📅 今日可购: {remaining} / {total_daily} 张"
        )

    # ----------------------------------------------------------
    # 指令: /转载 @用户 金额  - 用户转账
    # ----------------------------------------------------------
    @filter.command("刮转账")
    async def transfer(self, event: AstrMessageEvent):
        """将自己的方斯转给指定用户"""
        uid = event.get_sender_id()
        self._ensure_user(uid)

        # 解析目标用户
        target_uid = None
        for comp in event.get_messages():
            if isinstance(comp, At):
                target_uid = str(comp.qq)
                break

        if not target_uid:
            yield event.plain_result("❌ 请 @ 要转账的用户")
            return

        if target_uid == uid:
            yield event.plain_result("❌ 不能转给自己")
            return

        # 解析金额
        args = event.message_str.strip().split()
        amount = 0
        for a in args:
            try:
                amount = int(a)
                break
            except ValueError:
                continue

        if amount <= 0:
            yield event.plain_result("❌ 请输入有效金额")
            return

        if self._user_balance[uid] < amount:
            yield event.plain_result(
                f"❌ 余额不足！需要 {_fmt_money(amount)} 方斯，"
                f"当前只有 {_fmt_money(self._user_balance[uid])} 方斯"
            )
            return

        self._user_balance[uid] -= amount
        self._ensure_user(target_uid)
        self._user_balance[target_uid] += amount
        self._save_balance()

        # 通过 NapCat API 获取目标用户群名片
        target_name = target_uid[-4:]
        try:
            gid = str(event.message_obj.group_id)
            if gid:
                member_data, _ = await self._get_member_info(gid, target_uid)
                if member_data:
                    name = member_data.get("card") or member_data.get("nickname", "")
                    if name:
                        target_name = (name[:9] + "…") if len(name) > 10 else name
        except Exception:
            pass

        yield event.plain_result(
            f"💸 转账成功！\n"
            f"转出 {_fmt_money(amount)} 方斯 → {target_name}\n"
            f"💰 当前余额: {_fmt_money(self._user_balance[uid])} 方斯"
        )

    # ----------------------------------------------------------
    # LLM 工具（自然语言触发）：由 AstrBot Agent 根据用户意图自动调用
    # 需在 AstrBot 中配置支持 function-calling 的 LLM Provider
    # 管理员工具（发钱/发卡/审批）内部带 admin 权限校验；目标用户由
    # 大模型传昵称/QQ 号，工具内匹配群成员，降低 prompt 注入滥用风险
    # ----------------------------------------------------------
    def _is_admin(self, event: AstrMessageEvent) -> bool:
        """判断当前发送者是否为 AstrBot 管理员（event.is_admin()，其 role 由 AstrBot 后台 admins_id 填充）。"""
        return event.is_admin()

    async def _get_admins(self, event: AstrMessageEvent) -> List[str]:
        """获取可被 @ 到的管理员 uid 列表：直接使用 AstrBot 配置的 admins_id。"""
        try:
            cfg = self.context.get_config(umo=event.unified_msg_origin)
            admins = [str(a) for a in cfg.get("admins_id", []) if str(a).strip()]
            # 过滤掉 AstrBot 默认占位符 "astrbot"（未真正配置管理员时）
            admins = [a for a in admins if a.lower() != "astrbot"]
            return admins
        except Exception:
            pass
        return []

    def _find_pending(self, request_id: str) -> Optional[dict]:
        """按编号查找待审批申请。"""
        rid = str(request_id or "").strip().upper()
        for r in self._pending_requests:
            if str(r.get("id", "")).upper() == rid:
                return r
        return None

    async def _resolve_request(self, event: AstrMessageEvent, request_id: str) -> Optional[dict]:
        """解析审批目标申请：优先按编号，其次按引用消息中的编号，再次唯一待审批。"""
        if request_id and request_id.strip():
            return self._find_pending(request_id)
        try:
            quoted = await extract_quoted_message_text(event)
            if quoted:
                m = re.search(r"REQ-\d+", quoted)
                if m:
                    req = self._find_pending(m.group(0))
                    if req:
                        return req
        except Exception:
            pass
        pending = [r for r in self._pending_requests if r.get("status") == "pending"]
        if len(pending) == 1:
            return pending[0]
        return None

    def _pending_list_text(self, max_show: int = 10) -> str:
        """生成待审批清单文本。"""
        pending = [r for r in self._pending_requests if r.get("status") == "pending"]
        if not pending:
            return "📭 当前没有待审批的申请"
        lines = [f"📋 待审批申请（共 {len(pending)} 条）："]
        for r in pending[:max_show]:
            if r["type"] == "money":
                detail = f"{_fmt_money(r.get('amount', 0))} 方斯"
            else:
                _t = r.get("tier", 50000)
                _tlabel = CARD_TYPES.get(int(_t), CARD_TYPES[50000])["label"]
                detail = f"{_tlabel}档 +{r.get('extra', 1)} 张额度"
            lines.append(
                f"• {r['id']} {r.get('nickname', r['uid'])} 申请 {detail}"
                f"（{r.get('created_at', '')}）")
        if len(pending) > max_show:
            lines.append(f"… 还有 {len(pending) - max_show} 条")
        lines.append("回复「批准 <编号>」或「拒绝 <编号>」处理")
        return "\n".join(lines)

    async def _create_request(self, event: AstrMessageEvent, req_type: str,
                              amount: int = 0, extra: int = 0, tier: int = 50000) -> dict:
        """创建一条待审批申请并持久化，返回请求字典。"""
        self._req_seq += 1
        req_id = f"REQ-{self._req_seq:06d}"
        uid = event.get_sender_id()
        req = {
            "id": req_id,
            "uid": uid,
            "nickname": uid[-4:],
            "type": req_type,
            "amount": amount,
            "extra": extra,
            "tier": int(tier) if int(tier) in CARD_TYPES else 50000,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "pending",
            "approved_by": "",
            "approved_at": "",
            "group_id": "",
        }
        try:
            req["group_id"] = str(event.message_obj.group_id)
        except Exception:
            pass
        req["nickname"] = await self._get_target_name(event, uid)
        self._pending_requests.append(req)
        self._save_pending()
        return req

    async def _notify_admins(self, event: AstrMessageEvent, text: str) -> Optional[list]:
        """返回要在当前会话 @ 本群管理员的通知消息组件；找不到管理员返回 None。"""
        admins = await self._get_admins(event)
        if not admins:
            return None
        nodes: List = []
        for a in admins:
            nodes.append(At(qq=a))
        nodes.append(Plain(text=f"\n{text}"))
        return nodes

    async def _get_target_name(self, event: AstrMessageEvent, target_uid: str) -> str:
        """通过 NapCat API 获取目标用户群名片（失败回退为 uid 后四位）"""
        target_name = target_uid[-4:]
        try:
            gid = str(event.message_obj.group_id)
            if gid:
                member_data, _ = await self._get_member_info(gid, target_uid)
                if member_data:
                    name = member_data.get("card") or member_data.get("nickname", "")
                    if name:
                        target_name = (name[:9] + "…") if len(name) > 10 else name
        except Exception:
            pass
        return target_name

    async def _resolve_target(self, event: AstrMessageEvent, target: str) -> Tuple[Optional[str], str]:
        """解析目标用户：优先取 @ 组件，其次自称（我/自己），否则按群昵称/QQ 号匹配群成员。
        返回 (uid, 展示名)；找不到返回 (None, "")。"""
        # 1. 优先取 @
        for comp in event.get_messages():
            if isinstance(comp, At):
                uid = str(comp.qq)
                return uid, uid[-4:]
        # 1.5 自称：target 为「我/自己/本人/me/self」时返回发送者
        me = str(target or "").strip().lower()
        if me in ("我", "自己", "本人", "me", "self"):
            uid = event.get_sender_id()
            return uid, await self._get_target_name(event, uid)
        # 2. 按昵称/QQ 号匹配群成员
        try:
            gid = str(event.message_obj.group_id)
            if gid:
                members, _ = await self._get_group_members(gid)
                if members:
                    target = str(target or "").strip()
                    for m in members:
                        name = (m.get("card") or m.get("nickname") or "").strip()
                        uid = str(m.get("user_id", ""))
                        if target and target in (name, uid):
                            display = (name[:9] + "…") if len(name) > 10 else name
                            return uid, display or uid[-4:]
        except Exception:
            pass
        return None, ""

    @filter.llm_tool(name="scratch_ntc_card")
    async def scratch_ntc_card(self, event: AstrMessageEvent, count: int = 1,
                               tier: int = 50000):
        """帮用户购买并刮开异环刮刮卡，返回中奖结果与最新余额。可选卡档位 2 万 / 3 万 / 5 万。

        Args:
            count(number): 要刮的刮刮卡张数，最小 1，默认 1
            tier(number): 卡档位售价，可选 20000 / 30000 / 50000，默认 50000
        """
        card_type = int(tier) if int(tier) in CARD_TYPES else 50000
        async for r in self._do_scratch(event, max(1, int(count)), card_type):
            if isinstance(r, str):
                yield event.plain_result(r)
            else:
                yield event.chain_result(r)

    @filter.llm_tool(name="daily_pension")
    async def daily_pension(self, event: AstrMessageEvent):
        """帮用户每日领取一次免费方斯福利，每天只能领一次。"""
        yield event.plain_result(await self._do_pension(event))

    @filter.llm_tool(name="check_scratch_balance")
    async def llm_check_balance(self, event: AstrMessageEvent):
        """帮用户查看刮刮乐余额、累计盈亏与今日剩余购卡次数。"""
        yield event.plain_result(await self._do_check_balance(event))

    @filter.llm_tool(name="give_money")
    async def llm_give_money(self, event: AstrMessageEvent, target: str, amount: int):
        """给用户发放方斯余额。若说话者是管理员则直接发放；否则自动转为申请并通知管理员批准。管理员说「给我/我自己」即表示发给自己；普通用户申请只能给自己。

        Args:
            target(string): 目标用户的群昵称或 QQ 号，如"张三"或"123456"；「我」「自己」「本人」表示本人
            amount(number): 要发放/申请的方斯金额，必须是正整数
        """
        if self._is_admin(event):
            target_uid, target_name = await self._resolve_target(event, target)
            if not target_uid:
                yield event.plain_result(f"❌ 找不到用户「{target}」，请确认群昵称或 QQ 号")
                return
            if amount <= 0:
                yield event.plain_result("❌ 请输入有效金额")
                return
            self._ensure_user(target_uid)
            yield event.plain_result(
                await self._do_give_money(target_uid, target_name, amount)
            )
            return
        # 非管理员：转为申请流程（只能申请给自己）
        async for r in self._do_request_money(event, amount):
            yield r

    async def _do_request_money(self, event: AstrMessageEvent, amount: int):
        """成员申请发放方斯到自己账户（需管理员批准）。"""
        uid = event.get_sender_id()
        self._ensure_user(uid)
        if amount <= 0:
            yield event.plain_result("❌ 请输入有效金额")
            return
        req = await self._create_request(event, "money", amount=amount)
        notify = (
            f"📨 新申请 {req['id']}\n"
            f"{req['nickname']} 申请 {_fmt_money(amount)} 方斯\n"
            f"回复「批准 {req['id']}」或「拒绝 {req['id']}」"
        )
        notify_nodes = await self._notify_admins(event, notify)
        if notify_nodes:
            yield event.chain_result(notify_nodes)
        else:
            yield event.plain_result(
                "⚠️ 找不到可通知的管理员（请在 AstrBot 后台配置管理员），申请已记录，可由管理员在群里审批")
        yield event.plain_result(
            f"📨 申请已提交：{_fmt_money(amount)} 方斯（{req['id']}）\n"
            f"⏳ 等待管理员批准后到账"
        )

    @filter.llm_tool(name="give_cards")
    async def llm_give_cards(self, event: AstrMessageEvent, target: str, extra: int = 1,
                             tier: int = 50000):
        """给用户增加今日购卡额度。若说话者是管理员则直接发放；否则自动转为申请并通知管理员批准。管理员说「给我/我自己」即表示发给自己；普通用户申请只能给自己。可指定卡档位。

        Args:
            target(string): 目标用户的群昵称或 QQ 号，如"张三"或"123456"；「我」「自己」「本人」表示本人
            extra(number): 额外增加的购卡张数，默认 1
            tier(number): 卡档位售价，可选 20000 / 30000 / 50000，默认 50000
        """
        card_type = int(tier) if int(tier) in CARD_TYPES else 50000
        if self._is_admin(event):
            target_uid, target_name = await self._resolve_target(event, target)
            if not target_uid:
                yield event.plain_result(f"❌ 找不到用户「{target}」，请确认群昵称或 QQ 号")
                return
            self._ensure_user(target_uid)
            yield event.plain_result(
                await self._do_give_cards(target_uid, target_name, max(1, int(extra)), card_type)
            )
            return
        # 非管理员：转为申请流程（只能申请给自己）
        async for r in self._do_request_cards(event, extra, card_type):
            yield r

    async def _do_request_cards(self, event: AstrMessageEvent, extra: int,
                                tier: int = 50000):
        """成员申请购卡额度到自己账户（需管理员批准）。"""
        uid = event.get_sender_id()
        self._ensure_user(uid)
        extra = max(1, int(extra))
        card_conf = CARD_TYPES.get(int(tier), CARD_TYPES[50000])
        req = await self._create_request(event, "cards", extra=extra, tier=tier)
        notify = (
            f"📨 新申请 {req['id']}\n"
            f"{req['nickname']} 申请 {card_conf['label']}档 +{extra} 张购卡额度\n"
            f"回复「批准 {req['id']}」或「拒绝 {req['id']}」"
        )
        notify_nodes = await self._notify_admins(event, notify)
        if notify_nodes:
            yield event.chain_result(notify_nodes)
        else:
            yield event.plain_result(
                "⚠️ 找不到可通知的管理员（请在 AstrBot 后台配置管理员），申请已记录，可由管理员在群里审批")
        yield event.plain_result(
            f"📨 申请已提交：{card_conf['label']}档 +{extra} 张额度（{req['id']}）\n"
            f"⏳ 等待管理员批准后生效"
        )

    @filter.llm_tool(name="admin_approve_request")
    async def admin_approve_request(self, event: AstrMessageEvent, request_id: str = ""):
        """批准一条待审批的发钱/发卡申请并立即发放，仅管理员可用。可以直接引用机器人发的申请消息后说「同意/批准」，无需填写编号。

        Args:
            request_id(string): 待审批申请编号，形如 REQ-000001。可省略：会优先从你引用的申请消息识别，或仅有一条待审批时自动匹配
        """
        if not self._is_admin(event):
            yield event.plain_result("❌ 仅管理员可审批")
            return
        req = await self._resolve_request(event, request_id)
        if not req:
            yield event.plain_result(self._pending_list_text())
            return
        if req["type"] == "money":
            self._ensure_user(req["uid"])
            result = await self._do_give_money(
                req["uid"], req["nickname"], req.get("amount", 0))
        else:
            self._ensure_user(req["uid"])
            result = await self._do_give_cards(
                req["uid"], req["nickname"],
                max(1, int(req.get("extra", 1))),
                req.get("tier", 50000))
        req["status"] = "approved"
        req["approved_by"] = event.get_sender_id()
        req["approved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._save_pending()
        yield event.plain_result(f"✅ 已批准 {req['id']}\n{result}")

    @filter.llm_tool(name="admin_reject_request")
    async def admin_reject_request(self, event: AstrMessageEvent, request_id: str = ""):
        """拒绝一条待审批的发钱/发卡申请，仅管理员可用。可以直接引用机器人发的申请消息后说「拒绝」，无需填写编号。

        Args:
            request_id(string): 待审批申请编号，形如 REQ-000001。可省略：会优先从你引用的申请消息识别，或仅有一条待审批时自动匹配
        """
        if not self._is_admin(event):
            yield event.plain_result("❌ 仅管理员可审批")
            return
        req = await self._resolve_request(event, request_id)
        if not req:
            yield event.plain_result(self._pending_list_text())
            return
        req["status"] = "rejected"
        self._save_pending()
        yield event.plain_result(f"❌ 已拒绝 {req['id']}")

    @filter.llm_tool(name="list_pending_requests")
    async def list_pending_requests(self, event: AstrMessageEvent):
        """查看当前所有待审批的发钱/发卡申请，仅管理员可用。"""
        if not self._is_admin(event):
            yield event.plain_result("❌ 仅管理员可查看")
            return
        yield event.plain_result(self._pending_list_text())

    # ----------------------------------------------------------
    # 插件销毁
    # ----------------------------------------------------------
    async def terminate(self):
        self._save_balance()
        self._save_stats()
        logger.info("NTE 刮刮乐插件已卸载，数据已保存。")
