"""
NTE 刮刮乐 - AstrBot 插件
复刻 NTE 游戏的刮刮乐玩法
"""

from datetime import date
import json
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import aiohttp

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import Node, Nodes, Plain, At


# ============================================================
# 卡片配置（唯一档位：5 万方斯）
# ============================================================
CARD_EMOJI = "🟣"
CARD_COST = 50000
CARD_POSITIONS = 15
CARD_MAX_PRIZE = 2_500_000
CARD_ROWS = 3
CARD_COLS = 5

# 单格可用奖金档位
CELL_PRIZE_TIERS = [
    20000, 50000, 100000, 150000, 200000,
    300000, 500000, 800000, 1_000_000, 1_500_000,
]

# 总奖金概率分布表（来自游戏实际数据）
# 格式: [(总奖金, 概率%), ...]
TOTAL_PRIZE_DIST = [
    (0, 22.2607),
    (20000, 38.9563),
    (40000, 8.9043),
    (50000, 8.9043),
    (60000, 1.1130),
    (70000, 1.1130),
    (80000, 1.1130),
    (90000, 1.1130),
    (100000, 3.3391),
    (110000, 0.5565),
    (120000, 1.6695),
    (130000, 0.5565),
    (140000, 1.6695),
    (150000, 2.2260),
    (160000, 0.6678),
    (170000, 0.4452),
    (180000, 0.6678),
    (190000, 0.4452),
    (200000, 1.5582),
    (210000, 0.1113),
    (220000, 0.1669),
    (230000, 0.1113),
    (240000, 0.1669),
    (250000, 0.3895),
    (260000, 0.1669),
    (280000, 0.1669),
    (300000, 0.5565),
    (320000, 0.0333),
    (340000, 0.0333),
    (350000, 0.1113),
    (360000, 0.0333),
    (380000, 0.0333),
    (400000, 0.1446),
    (420000, 0.0222),
    (440000, 0.0222),
    (450000, 0.1113),
    (460000, 0.0222),
    (470000, 0.0111),
    (480000, 0.0222),
    (490000, 0.0111),
    (500000, 0.1669),
    (510000, 0.0005),
    (520000, 0.0005),
    (530000, 0.0005),
    (540000, 0.0005),
    (550000, 0.0044),
    (560000, 0.0005),
    (580000, 0.0005),
    (600000, 0.0083),
    (620000, 0.0016),
    (640000, 0.0016),
    (650000, 0.0050),
    (660000, 0.0016),
    (680000, 0.0016),
    (700000, 0.0089),
    (750000, 0.0050),
    (800000, 0.0089),
    (820000, 0.0011),
    (840000, 0.0011),
    (850000, 0.0022),
    (860000, 0.0011),
    (880000, 0.0011),
    (900000, 0.0094),
    (920000, 0.0005),
    (940000, 0.0005),
    (950000, 0.0038),
    (960000, 0.0005),
    (980000, 0.0005),
    (1000000, 0.0094),
    (1020000, 0.0002),
    (1040000, 0.0002),
    (1050000, 0.0010),
    (1060000, 0.0002),
    (1080000, 0.0002),
    (1100000, 0.0017),
    (1150000, 0.0004),
    (1200000, 0.0018),
    (1220000, 0.0001),
    (1240000, 0.0001),
    (1250000, 0.0005),
    (1260000, 0.0001),
    (1280000, 0.0001),
    (1300000, 0.0013),
    (1350000, 0.0004),
    (1400000, 0.0015),
    (1450000, 0.0002),
    (1500000, 0.0008),
    (1520000, 0.0001),
    (1540000, 0.0001),
    (1550000, 0.0002),
    (1560000, 0.0001),
    (1580000, 0.0001),
    (1600000, 0.0013),
    (1620000, 0.0001),
    (1640000, 0.0001),
    (1650000, 0.0004),
    (1660000, 0.0001),
    (1680000, 0.0001),
    (1700000, 0.0007),
    (1750000, 0.0003),
    (1800000, 0.0014),
    (1900000, 0.0007),
    (1950000, 0.0001),
    (2000000, 0.0006),
    (2020000, 0.0001),
    (2040000, 0.0001),
    (2050000, 0.0002),
    (2060000, 0.0001),
    (2080000, 0.0001),
    (2100000, 0.0007),
    (2150000, 0.0002),
    (2200000, 0.0007),
    (2300000, 0.0005),
    (2400000, 0.0005),
    (2450000, 0.0001),
    (2500000, 0.0003),
]

# 构建概率权重组（用于快速随机选择）
_TOTAL_PRIZE_VALUES = [p for p, _ in TOTAL_PRIZE_DIST]
_TOTAL_PRIZE_WEIGHTS = [w for _, w in TOTAL_PRIZE_DIST]

# 初始余额
INITIAL_BALANCE = 3_000_000

# 每日限购
DAILY_LIMIT = 60


# ----------------------------------------------------------
# 卡片生成（基于精确概率分布）
# ----------------------------------------------------------
def _decompose_prize(total: int) -> List[int]:
    """将总奖金精确拆分为 CELL_PRIZE_TIERS 中的档位，不超过 15 格"""
    if total == 0:
        return []

    tiers = sorted(CELL_PRIZE_TIERS)
    min_p = tiers[0]
    # 不可达的剩余金额：10000 和 30000
    BAD = {10000, 30000}
    parts = []
    remaining = total

    while remaining > 0:
        cells_left = CARD_POSITIONS - len(parts)

        if cells_left == 1:
            parts.append(remaining)
            break

        # 候选：不超过剩余金额的档位，且不产生不可达剩余
        cand = [t for t in tiers if t <= remaining]
        valid = [t for t in cand
                 if remaining - t == 0 or remaining - t not in BAD]
        if not valid:
            valid = cand
        if not valid:
            parts[-1] += remaining
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


def _generate_card() -> dict:
    """根据精确概率分布生成一张刮刮卡"""
    # 1. 按精确概率抽总奖金
    total_prize = random.choices(_TOTAL_PRIZE_VALUES, weights=_TOTAL_PRIZE_WEIGHTS, k=1)[0]

    # 2. 拆分为各格奖金
    cell_prizes = _decompose_prize(total_prize)

    # 3. 分配到 15 格（中奖格随机分布位置）
    cells = [{"is_win": False, "prize": 0} for _ in range(CARD_POSITIONS)]
    if cell_prizes:
        # 随机选择中奖位置
        indices = random.sample(range(CARD_POSITIONS), len(cell_prizes))
        for idx, prize in zip(indices, cell_prizes):
            cells[idx] = {"is_win": True, "prize": prize}

    return {"cells": cells, "total_prize": total_prize}


def _card_grid(cells: List[dict]) -> List[List[dict]]:
    """将 cells 一维数组转为二维网格"""
    return [cells[i:i + CARD_COLS] for i in range(0, len(cells), CARD_COLS)]


def _prize_label(amount: int) -> str:
    """奖金金额转短标签"""
    if amount >= 10000:
        w = amount // 10000
        if amount % 10000 == 0:
            return f"{w}万"
        return f"{w}.{amount % 10000 // 1000}万"
    return str(amount)


def _card_to_str(card_data: dict) -> str:
    """将卡片格式化为文本（纯文本，无制表符）"""
    grid = _card_grid(card_data["cells"])
    lines = [f"{CARD_EMOJI} 刮刮卡"]
    for row in grid:
        parts = []
        for c in row:
            if c["is_win"]:
                parts.append(f"{_prize_label(c['prize']):>3}")
            else:
                parts.append("  ❌ ")
        lines.append("  ".join(parts))
    return "\n".join(lines)


def _fmt_money(amount: int) -> str:
    """格式化金额"""
    s = str(amount)
    result = []
    for i, ch in enumerate(reversed(s)):
        if i > 0 and i % 3 == 0:
            result.append(",")
        result.append(ch)
    return "".join(reversed(result))


# ============================================================
# 插件主类
# ============================================================
@register(
    "nte_scratch_card",
    "CavinGou",
    "复刻 NTE 游戏的刮刮乐玩法",
    "1.0.0",
)
class NteScratchCardPlugin(Star):
    """NTE 刮刮乐插件"""

    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        self.data_dir = Path("data/nte_scratch_card")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._balance_path = self.data_dir / "balance.json"
        self._stats_path = self.data_dir / "stats.json"

        # NapCat 配置
        self.napcat_host = self.config.get("napcat_host", "127.0.0.1:3000")
        self.napcat_token = self.config.get("napcat_token", "")

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

    def _save_balance(self):
        self._balance_path.write_text(
            json.dumps(self._user_balance, ensure_ascii=False), "utf-8")

    def _save_stats(self):
        self._stats_path.write_text(
            json.dumps(self._user_stats, ensure_ascii=False), "utf-8")

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
                "pension_date": "",
                "cycle_order": [],
                "cycle_pos": 0,
                "group_id": "",
            }

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
    # 指令: /刮刮乐 [数量]  - 购买并立即刮开
    # ----------------------------------------------------------
    @filter.command("刮刮乐")
    async def scratch(self, event: AstrMessageEvent):
        """购买刮刮卡并立即刮开，支持一次多张：/刮刮乐 10"""
        uid = event.get_sender_id()
        self._ensure_user(uid)

        # 记录用户所在群号
        try:
            gid = str(event.message_obj.group_id)
            if gid:
                self._user_stats[uid]["group_id"] = gid
        except Exception:
            pass

        # 解析数量
        args = event.message_str.strip().split()
        count = 1
        if len(args) >= 2:
            try:
                count = int(args[1])
                if count < 1:
                    count = 1
            except ValueError:
                pass

        # 检查每日限购
        stats = self._user_stats[uid]
        today = date.today().isoformat()
        if stats.get("daily_date") != today:
            stats["daily_date"] = today
            stats["daily_bought"] = 0

        remaining_daily = DAILY_LIMIT - stats["daily_bought"]
        if count > remaining_daily:
            yield event.plain_result(
                f"❌ 今日剩余 {remaining_daily} 张，不够买 {count} 张！"
            )
            return

        # 检查余额
        total_cost = CARD_COST * count
        if self._user_balance[uid] < total_cost:
            yield event.plain_result(
                f"❌ 余额不足！需要 {_fmt_money(total_cost)} 方斯，"
                f"当前只有 {_fmt_money(self._user_balance[uid])} 方斯"
            )
            return

        # 批量购卡
        self._user_balance[uid] -= total_cost
        stats["total_spent"] += total_cost
        stats["cards_bought"] += count
        stats["daily_bought"] += count

        total_won_all = 0
        win_count = 0

        if count == 1:
            # 单张：直接发结果
            card = _generate_card()
            prize = card["total_prize"]
            total_won_all = prize
            win_count = 1 if prize > 0 else 0
            stats["total_won"] += prize

            board = _card_to_str(card)
            prize_line = f"🎉 中奖 {_fmt_money(prize)} 方斯！" if prize > 0 else "😅 未中奖"
            self._user_balance[uid] += prize
            stats["cards_won"] += win_count
            self._save_balance()
            self._save_stats()
            net = stats["total_won"] - stats["total_spent"]

            lines = [
                f"🎴 刮刮乐",
                board,
                prize_line,
                f"",
                f"💰 余额: {_fmt_money(self._user_balance[uid])} 方斯  |  📊 {'+' if net >= 0 else '-'}{_fmt_money(abs(net))}",
                f"📅 今日剩余: {DAILY_LIMIT - stats['daily_bought']} / {DAILY_LIMIT} 张",
            ]
            yield event.plain_result("\n".join(lines))
        else:
            # 多张：用合并转发
            bot_uin = event.get_self_id()
            node_list = []

            for i in range(1, count + 1):
                card = _generate_card()
                prize = card["total_prize"]
                total_won_all += prize
                if prize > 0:
                    win_count += 1
                stats["total_won"] += prize

                board = _card_to_str(card)
                prize_line = f"🎉 中奖 {_fmt_money(prize)} 方斯" if prize > 0 else "😅 未中奖"
                card_text = (
                    f"🎴 第 {i}/{count} 张\n"
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
            self._save_balance()
            self._save_stats()
            net = stats["total_won"] - stats["total_spent"]
            won_desc = f"🎉 中 {win_count}/{count} 张，共 {_fmt_money(total_won_all)} 方斯" if win_count > 0 else "😅 全部未中奖"

            # 添加汇总节点
            batch_net = total_won_all - total_cost
            summary_text = (
                f"📊 刮刮乐 × {count} 汇总\n"
                f"{won_desc}\n"
                f"📊 本次收入: {'+' if batch_net >= 0 else '-'}{_fmt_money(abs(batch_net))} 方斯\n"
                f"📊 累计收入: {'+' if net >= 0 else '-'}{_fmt_money(abs(net))} 方斯\n"
                f"💰 当前余额: {_fmt_money(self._user_balance[uid])} 方斯\n"
                f"📅 今日剩余: {DAILY_LIMIT - stats['daily_bought']} / {DAILY_LIMIT} 张"
            )
            node_list.append(Node(
                name="刮刮乐",
                uin=bot_uin,
                content=[Plain(text=summary_text)]
            ))

            yield event.chain_result([Nodes(nodes=node_list)])

    # ----------------------------------------------------------
    # 指令: /帮助  - 显示帮助
    # ----------------------------------------------------------
    @filter.command("刮刮乐帮助")
    async def help_cmd(self, event: AstrMessageEvent):
        """显示帮助信息"""
        lines = [
            "🎴 NTE 刮刮乐 - 帮助\n",
            "━━━ 指令列表 ━━━",
            f"/刮刮乐 [数量]  购买并刮开，默认1张，支持多张",
            f"/刮取钱         每日随机领取方斯（30/50/70/100 顺序随机 每4天得250w）",
            f"/刮余额         查看余额和游戏统计",
            f"/富爪榜         累计盈亏排行榜",
            f"/刮刮乐帮助     显示此帮助\n",
            "━━━ 介绍 ━━━",
            f"初始余额: 300万  |  每日限购: 60张",
            f"售价: 50,000 方斯  |  格子: 3×5  |  最高奖: 250万",
        ]
        yield event.plain_result("\n".join(lines))

    # ----------------------------------------------------------
    # 指令: /刮取钱  - 每日领取随机方斯
    # ----------------------------------------------------------
    @filter.command("刮取钱")
    async def pension(self, event: AstrMessageEvent):
        """每日阶段性领取方斯（周期内顺序随机）"""
        uid = event.get_sender_id()
        self._ensure_user(uid)
        stats = self._user_stats[uid]

        today = date.today().isoformat()
        if stats.get("pension_date") == today:
            yield event.plain_result(
                f"❌ 今天已经领过了，明天再来吧 😊"
            )
            return

        # 四个档位
        tiers = [
            (300000,  "管理局给娜娜莉的医疗补贴下来了，手头宽裕了些"),
            (500000,  "雨燕出行跑了一天单，腰都要断了，赚点辛苦钱。"),
            (700000,  "背着店长偷偷把伊波恩抵押了…发了笔小财！"),
            (1000000, "赶上粉爪大劫案，浑水摸鱼捞了一笔，赶紧跑路！"),
        ]

        # 初始化或重新洗牌
        cycle_order = stats.get("cycle_order", [])
        cycle_pos = stats.get("cycle_pos", 0)
        if not cycle_order or cycle_pos >= len(cycle_order):
            cycle_order = list(range(len(tiers)))
            random.shuffle(cycle_order)
            cycle_pos = 0

        idx = cycle_order[cycle_pos]
        amount, msg = tiers[idx]

        stats["pension_date"] = today
        stats["cycle_order"] = cycle_order
        stats["cycle_pos"] = cycle_pos + 1
        self._user_balance[uid] += amount
        self._save_balance()
        self._save_stats()

        yield event.plain_result(
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
        uid = event.get_sender_id()
        self._ensure_user(uid)

        balance = self._user_balance[uid]
        stats = self._user_stats[uid]
        net = stats["total_won"] - stats["total_spent"]
        win_rate = (stats["cards_won"] / stats["cards_bought"] * 100
                    if stats["cards_bought"] > 0 else 0)

        lines = [
            "📊 个人数据\n",
            f"💰 余额: {_fmt_money(balance)} 方斯",
            f"📈 累计盈亏: {'+' if net >= 0 else '-'}{_fmt_money(abs(net))} 方斯",
            f"📅 今日剩余: {DAILY_LIMIT - stats.get('daily_bought', 0)} / {DAILY_LIMIT} 张",
            "",
            f"🎴 购买次数: {stats['cards_bought']} 张",
            f"🏆 中奖次数: {stats['cards_won']} 次",
            f"📊 中奖率: {win_rate:.1f}%",
            f"💵 总投入: {_fmt_money(stats['total_spent'])} 方斯",
            f"💵 总奖金: {_fmt_money(stats['total_won'])} 方斯",
        ]
        yield event.plain_result("\n".join(lines))

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

        # 筛选当前群买过卡的用户（跨群统一 — 按当前群成员列表而非刮卡时的群）
        items = [
            (uid, stats.get("total_won", 0) - stats.get("total_spent", 0))
            for uid, stats in self._user_stats.items()
            if stats.get("cards_bought", 0) > 0
            and uid in group_uids
        ]
        if not items:
            yield event.plain_result("📭 暂无数据，快来 /刮刮乐 吧！")
            return

        items.sort(key=lambda x: x[1], reverse=True)

        def _get_name(uid: str) -> str:
            raw = name_map.get(uid, "")
            if not raw:
                return uid[-4:]
            return (raw[:9] + "…") if len(raw) > 10 else raw

        lines = ["🏆 海特洛富爪榜\n"]
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
        if event.role != "admin":
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
            f"💸 发钱成功！\n"
            f"{target_name} 获得 {_fmt_money(amount)} 方斯\n"
            f"当前余额: {_fmt_money(self._user_balance[target_uid])} 方斯"
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
    # 插件销毁
    # ----------------------------------------------------------
    async def terminate(self):
        self._save_balance()
        self._save_stats()
        logger.info("NTE 刮刮乐插件已卸载，数据已保存。")
