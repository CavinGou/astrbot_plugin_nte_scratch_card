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


# 从 core 子包导入配置、工具与模板（相对导入，符合 AstrBot 插件主流惯例）
from .core import (
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
    LEADERBOARD_HTML,
    _card_to_str,
    _decompose_prize,
    _fmt_money,
    _generate_card,
    _prize_label,
)


@register(
    "nte_scratch_card",
    "CavinGou",
    "复刻 NTE 游戏的刮刮乐玩法",
    "1.4.0",
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
                "bookmarks": 0,  # 回声书签（道具），购卡累计，可用于兑换
                "amulet_date": "",  # 当日保底护符生效日期（当日有效，跨天失效）
                "amulet_type": "",  # 当日生效的护符类型："hand"(大手) / "backdoor"(后门)
            }

    def _amulet_active(self, stats: dict) -> str:
        """返回今日生效的护符类型（"" 表示未生效；"hand" 大手；"backdoor" 后门）。"""
        if stats.get("amulet_date", "") != date.today().isoformat():
            return ""
        return stats.get("amulet_type", "")

    def _amulet_status_text(self, stats: dict) -> str:
        """返回护符状态展示文本。"""
        t = self._amulet_active(stats)
        if t == "hand":
            return "🟢 大手生效（未中奖全额返还）"
        if t == "backdoor":
            return "🟢 后门生效（中奖低于成本返差额）"
        return "⚪ 未生效"

    def _amulet_refund_amount(self, stats: dict, card_conf: dict, prize: int) -> int:
        """计算该张卡在护符生效时应获得的方斯（0 表示不触发）。

        大手(hand)：未中奖(prize==0) → 全额返还成本
        后门(backdoor)：中奖低于成本(prize<cost，含未中奖) → 返还差额 cost-prize
        """
        t = self._amulet_active(stats)
        cost = card_conf["cost"]
        if t == "hand" and prize == 0:
            return cost
        if t == "backdoor" and prize < cost:
            return cost - prize
        return 0

    def _bookmark_cost_for_tier(self, card_conf: dict) -> int:
        """计算兑换该档 1 张追加额度所需的书签数。"""
        return BOOKMARK_CARD_MULT * card_conf["bookmark_reward"]

    def _tier_daily(self, stats: dict) -> Tuple[dict, dict]:
        """获取/初始化各档今日已购张数与追加额度（各档独立限购）。
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
        """购买所有档位今日基础限购剩余的全部额度并立即刮开（不含发放的追加额度）：/刮全部"""
        async for r in self._do_scratch_all(event):
            if isinstance(r, str):
                yield event.plain_result(r)
            else:
                yield event.chain_result(r)

    async def _do_scratch_all(self, event: AstrMessageEvent):
        """购买并刮开所有档位今日基础限购剩余的全部额度（不含发放的追加额度），结果用合并转发汇总。"""
        uid = event.get_sender_id()
        self._ensure_user(uid)
        stats = self._user_stats[uid]

        # 记录用户所在群号
        try:
            gid = str(event.message_obj.group_id)
            if gid:
                stats["group_id"] = gid
        except Exception:
            pass

        # 跨天重置每日限购
        today = date.today().isoformat()
        stats["last_scratch_date"] = today
        if stats.get("daily_date") != today:
            stats["daily_date"] = today
            stats["daily_spent"] = 0
            stats["daily_won"] = 0
            stats["daily_cards_won"] = 0
            for _k in CARD_TYPES:
                stats.setdefault("daily_bought_by_tier", {})[str(_k)] = 0
                stats.setdefault("daily_extra_by_tier", {})[str(_k)] = 0

        # 计算各档基础限购剩余额度并规划购买（不含发放的追加额度）
        plans = []  # (tier_key, card_conf, remaining)
        total_cost = 0
        total_cards = 0
        for k in sorted(CARD_TYPES):
            card_conf = CARD_TYPES[k]
            bought_by_tier, _ = self._tier_daily(stats)
            tier_key = str(k)
            remaining = card_conf["daily_limit"] - bought_by_tier.get(tier_key, 0)
            if remaining > 0:
                plans.append((tier_key, card_conf, remaining))
                total_cards += remaining
                total_cost += remaining * card_conf["cost"]

        if not plans:
            yield "❌ 所有档位今日额度都已用完！"
            return

        # 检查余额
        if self._user_balance[uid] < total_cost:
            yield (f"❌ 余额不足！购买全部额度需要 {_fmt_money(total_cost)} 方斯，"
                   f"当前只有 {_fmt_money(self._user_balance[uid])} 方斯")
            return

        # 扣款
        self._user_balance[uid] -= total_cost
        stats["total_spent"] += total_cost
        stats["daily_spent"] += total_cost
        stats["cards_bought"] += total_cards

        bot_uin = event.get_self_id()
        node_list = []
        total_won_all = 0
        win_count_all = 0
        bookmarked_total = 0
        amulet_refund_total = 0
        amulet_used_total = 0
        card_no = 0

        for tier_key, card_conf, remaining in plans:
            bought_by_tier, _ = self._tier_daily(stats)
            # 只购买基础限购额度，全部张数均赠送回声书签
            bought_by_tier[tier_key] = bought_by_tier.get(tier_key, 0) + remaining
            bookmarked_total += remaining * card_conf["bookmark_reward"]

            # 每张卡各占一条节点（与多张购卡一致）
            for _ in range(remaining):
                card_no += 1
                card = _generate_card(card_conf)
                prize = card["total_prize"]
                total_won_all += prize
                if prize > 0:
                    win_count_all += 1
                stats["total_won"] += prize
                stats["daily_won"] += prize

                # 护符：当日保底生效且满足条件 → 返还（刮全部只买基础额度）
                amulet_refund = self._amulet_refund_amount(stats, card_conf, prize)
                if amulet_refund:
                    amulet_used_total += 1
                    amulet_refund_total += amulet_refund
                    total_won_all += amulet_refund
                    stats["total_won"] += amulet_refund
                    stats["daily_won"] += amulet_refund

                board = _card_to_str(card)
                prize_line = f"🎉 中奖 {_fmt_money(prize)} 方斯" if prize > 0 else "😅 未中奖"
                if amulet_refund:
                    prize_line += f"\n🛡️ 护符生效！获得 {_fmt_money(amulet_refund)} 方斯"
                card_text = (
                    f"🎴 {card_conf['label']} · 第 {card_no}/{total_cards} 张\n"
                    f"{board}\n"
                    f"{prize_line}\n"
                )
                node_list.append(Node(
                    name="刮刮乐", uin=bot_uin,
                    content=[Plain(text=card_text)]
                ))

        stats["cards_won"] += win_count_all
        stats["daily_cards_won"] += win_count_all

        # 发奖
        stats["bookmarks"] = stats.get("bookmarks", 0) + bookmarked_total
        self._user_balance[uid] += total_won_all
        self._save_balance()
        self._save_stats()

        net = stats["total_won"] - stats["total_spent"]
        batch_net = total_won_all - total_cost
        won_desc = (f"🏆 中 {win_count_all}/{total_cards} 张，共 {_fmt_money(total_won_all)} 方斯"
                    if win_count_all > 0 else "😅 全部未中奖")
        summary_lines = [
            f"🎴 已刮完全部额度：{total_cards} 张",
            won_desc,
            f"🔖 获得 {bookmarked_total} 个回声书签（累计 {stats.get('bookmarks', 0)} 个）",
        ]
        if amulet_used_total:
            summary_lines.append(
                f"🛡️ 护符生效 {amulet_used_total} 个，获得 {_fmt_money(amulet_refund_total)} 方斯")
        summary_lines += [
            f"📊 本次收入: {'+' if batch_net >= 0 else '-'}{_fmt_money(abs(batch_net))} 方斯",
            f"📊 累计收入: {'+' if net >= 0 else '-'}{_fmt_money(abs(net))} 方斯",
            f"💰 当前余额: {_fmt_money(self._user_balance[uid])} 方斯",
        ]
        # 总结信息单独作为普通消息发出（合并转发有节点上限，避免占用）
        yield "\n".join(summary_lines)
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
        stats["daily_spent"] += total_cost
        # 统计本次购卡中落在「管理员发放的追加额度」内的张数：这些卡不赠送回声书签
        bought_before = bought_by_tier[tier_key]
        extra_used = (
            max(0, bought_before + count - tier_limit)
            - max(0, bought_before - tier_limit)
        )
        bookmarked_count = count - extra_used
        bought_by_tier[tier_key] += count
        stats["bookmarks"] = stats.get("bookmarks", 0) + bookmarked_count * card_conf["bookmark_reward"]

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

            # 护符：当日保底生效、该卡在基础额度内且满足条件 → 返还
            amulet_refund = 0
            amulet_used = 0
            if bought_before < tier_limit:
                amulet_refund = self._amulet_refund_amount(stats, card_conf, prize)
                if amulet_refund:
                    amulet_used = 1

            board = _card_to_str(card)
            prize_line = f"🎉 中奖 {_fmt_money(prize)} 方斯！" if prize > 0 else "😅 未中奖"
            self._user_balance[uid] += prize + amulet_refund
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
            ]
            if amulet_used:
                lines.append(f"🛡️ 护符生效！获得 {_fmt_money(amulet_refund)} 方斯")
            lines += [
                f"🔖 获得 {bookmarked_count * card_conf['bookmark_reward']} 个回声书签（累计 {stats.get('bookmarks', 0)} 个）",
                f"",
                f"💰 余额: {_fmt_money(self._user_balance[uid])} 方斯  |  📊 {'+' if net >= 0 else '-'}{_fmt_money(abs(net))}",
                f"📅 {card_conf['label']}档今日剩余: {remaining_now} / {total_daily_tier} 张",
            ]
            yield "\n".join(lines)
        else:
            # 多张：用合并转发
            bot_uin = event.get_self_id()
            node_list = []
            amulet_refund_total = 0
            amulet_used_total = 0
            # 本次购买中落在基础额度内的张数（前 base_left 张），护符只对基础额度生效
            base_left = max(0, tier_limit - bought_before)

            for i in range(1, count + 1):
                card = _generate_card(card_conf)
                prize = card["total_prize"]
                total_won_all += prize
                if prize > 0:
                    win_count += 1
                stats["total_won"] += prize
                stats["daily_won"] += prize

                # 护符：当日保底生效、该张在基础额度内且满足条件 → 返还
                amulet_refund = 0
                if i <= base_left:
                    amulet_refund = self._amulet_refund_amount(stats, card_conf, prize)
                    if amulet_refund:
                        amulet_used_total += 1
                        amulet_refund_total += amulet_refund
                        total_won_all += amulet_refund
                        stats["total_won"] += amulet_refund
                        stats["daily_won"] += amulet_refund

                board = _card_to_str(card)
                prize_line = f"🎉 中奖 {_fmt_money(prize)} 方斯" if prize > 0 else "😅 未中奖"
                if amulet_refund:
                    prize_line += f"\n🛡️ 护符生效！返还 {_fmt_money(amulet_refund)} 方斯"
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
                f"🔖 获得 {bookmarked_count * card_conf['bookmark_reward']} 个回声书签（累计 {stats.get('bookmarks', 0)} 个）",
            ]
            if amulet_used_total:
                summary_lines.append(
                    f"🛡️ 护符生效 {amulet_used_total} 个，返还 {_fmt_money(amulet_refund_total)} 方斯")
            summary_lines += [
                f"📊 本次收入: {'+' if batch_net >= 0 else '-'}{_fmt_money(abs(batch_net))} 方斯",
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
            f"刮刮乐5 [数量]   购买5万档刮刮卡",
            f"刮刮乐2 [数量]   购买2万档刮刮卡",
            f"刮刮乐3 [数量]   购买3万档刮刮卡",
            f"刮全部           购买各档位今日基础限购的全部额度（不含追加额度）",
            f"刮取钱           每日随机领取方斯（{len(self._pension_tiers)}档循环，发完重洗）",
            f"刮商店           回声书签商店：方斯/追加额度/大手/后门",
            f"刮商店           回声书签商店：方斯/追加额度/大手/后门",
            f"刮余额           查看余额和游戏统计",
            f"富爪榜           累计盈亏排行榜",
            f"富爪日榜         今日盈亏排行榜",
            f"刮刮乐帮助       显示此帮助",
        ]
        # 管理员专属指令
        if event.is_admin():
            lines += [
                "━━━ 管理员指令 ━━━",
                f"刮发钱 @用户 金额    给指定用户发放方斯",
                f"刮发卡 [数量] @用户  给指定用户发放今日追加购卡额度",
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
            f"🔖 回声书签: {stats.get('bookmarks', 0)} 个（可 /刮商店 消费）",
            f"🛡️ 护符: {self._amulet_status_text(stats)}",
            f"🎴 购买次数: {stats['cards_bought']} 张",
            f"🏆 中奖次数: {stats['cards_won']} 次",
            f"📊 中奖率: {win_rate:.1f}%",
            f"💵 总投入: {_fmt_money(stats['total_spent'])} 方斯",
            f"💵 总奖金: {_fmt_money(stats['total_won'])} 方斯",
        ]
        return "\n".join(lines)

    # ----------------------------------------------------------
    # 指令: /刮商店 [商品] [数量] [档位]  - 回声书签商店
    # ----------------------------------------------------------
    @filter.command("刮商店")
    async def scratch_shop(self, event: AstrMessageEvent):
        """回声书签商店：无参数展示货架；带参数直接购买

        用法：
          /刮商店              展示商店货架（商品、价格、我的书签）
          /刮商店 方斯 [数量]  购买方斯
          /刮商店 卡 [数量] [档位] / 卡2 / 卡3 / 卡5  购买该档今日追加额度
          /刮商店 大手         购买「玛门的大手」（1000书签）
          /刮商店 后门         购买「猫丸的后门」（1500书签）
        """
        args = event.message_str.strip().split()
        if args and args[0] in ("刮商店", "/刮商店"):
            args = args[1:]
        if not args:
            yield event.plain_result(self._shop_text(event))
            return
        async for r in self._do_redeem(event, args):
            yield r

    def _shop_text(self, event: AstrMessageEvent) -> str:
        """生成回声书签商店货架文本（按既定版面）"""
        uid = event.get_sender_id()
        self._ensure_user(uid)
        stats = self._user_stats[uid]
        have = stats.get("bookmarks", 0)
        amulet_status = self._amulet_status_text(stats)

        # 各档追加额度价格
        cost2 = self._bookmark_cost_for_tier(CARD_TYPES[20000])
        cost3 = self._bookmark_cost_for_tier(CARD_TYPES[30000])
        cost5 = self._bookmark_cost_for_tier(CARD_TYPES[50000])

        lines = [
            "🛒 回声书签商店\n",
            f"🔖 我的书签: {have} 个",
            "",
            "━━━ 商品列表 ━━━",
            f"💰 {_fmt_money(BOOKMARK_MONEY_AMOUNT)} 方斯         {BOOKMARK_MONEY_UNIT} 书签 ",
            "用法：刮商店 方斯 [数量]",
            "",
            f"🎴 追加额度(2万)     {cost2} 书签",
            "用法：刮商店 卡2 [数量]",
            "",
            f"🎴 追加额度(3万)     {cost3} 书签",
            "用法：刮商店 卡3 [数量]",
            "",
            f"🎴 追加额度(5万)     {cost5} 书签",
            "用法：刮商店 卡 [数量]",
            "用法2：刮商店 卡5 [数量]",
            "",
            f"🛡️ 玛门的大手      {AMULET_HAND_COST} 书签",
            "用法：刮商店 大手",
            "效果：今日基础额度购卡未中奖全额返还成本",
            "",
            f"🛡️ 猫丸的后门      {AMULET_BACKDOOR_COST} 书签",
            "用法：刮商店 后门",
            "效果：今日基础额度购卡中奖低于成本的返还",
            "",
            "━━━ 护符状态 ━━━",
            amulet_status,
        ]
        return "\n".join(lines)

    async def _do_redeem(self, event: AstrMessageEvent, args):
        """兑换核心逻辑：解析参数并分发到具体兑换方法。"""
        if not args:
            yield event.plain_result(self._redeem_help_text())
            return

        kind = args[0]
        # 解析数量与档位：数字 2/3/5（万）或完整档位金额视为档位，其余正整数视为数量
        tier_alias = {2: 20000, 3: 30000, 5: 50000}
        qty = 1
        tier = 50000

        # 商品名到档位的映射（卡/卡5 → 5万；卡2 → 2万；卡3 → 3万）
        tier_kind = {
            "卡2": 20000, "卡二": 20000,
            "卡3": 30000, "卡三": 30000,
            "卡5": 50000, "卡五": 50000,
        }
        if kind in tier_kind:
            tier = tier_kind[kind]
            kind = "卡"

        need_tier = kind in ("卡", "card", "额度")
        for a in args[1:]:
            try:
                v = int(a)
            except ValueError:
                continue
            if need_tier and v in tier_alias:
                tier = tier_alias[v]
            elif need_tier and v in CARD_TYPES:
                tier = v
            elif v >= 1:
                qty = v
        qty = max(1, qty)

        uid = event.get_sender_id()
        self._ensure_user(uid)
        stats = self._user_stats[uid]

        if kind in ("钱", "money", "方斯"):
            yield event.plain_result(self._redeem_money(uid, stats, qty))
            return
        if kind in ("卡", "card", "额度"):
            yield event.plain_result(self._redeem_cards(uid, stats, qty, tier))
            return
        if kind in ("大手", "hand", "玛门的大手"):
            yield event.plain_result(self._redeem_hand(uid, stats))
            return
        if kind in ("后门", "backdoor", "猫丸的后门"):
            yield event.plain_result(self._redeem_backdoor(uid, stats))
            return

        yield event.plain_result(
            f"❌ 未知商品「{kind}」\n" + self._redeem_help_text())

    def _redeem_help_text(self) -> str:
        """兑换帮助文本"""
        lines = [
            "🔖 回声书签兑换\n",
            "━━━ 兑换项目 ━━━",
            f"💰 方斯: {BOOKMARK_MONEY_UNIT} 书签 = {_fmt_money(BOOKMARK_MONEY_AMOUNT)} 方斯",
            f"🎴 追加额度: 各档 1 张 = {BOOKMARK_CARD_MULT}×回报书签",
            f"🛡️ 玛门的大手: {AMULET_HAND_COST} 书签，今日基础额度购卡未中奖全额返还成本",
            f"🛡️ 猫丸的后门: {AMULET_BACKDOOR_COST} 书签，今日基础额度购卡中奖低于成本返差额",
            "",
            "档位回报书签: " + " / ".join(
                f"{CARD_TYPES[k]['label']} {CARD_TYPES[k]['bookmark_reward']}"
                for k in sorted(CARD_TYPES)),
            "各档成本: " + " / ".join(
                f"{CARD_TYPES[k]['label']} {self._bookmark_cost_for_tier(CARD_TYPES[k])}"
                for k in sorted(CARD_TYPES)),
            "",
            "用法:",
            "  刮商店 方斯 [数量]",
            "  刮商店 卡 [数量] [档位]   （或 卡2/卡3/卡5）",
            "  刮商店 大手",
            "  刮商店 后门",
            "档位: 2 / 3 / 5（万），默认 5 万档",
        ]
        return "\n".join(lines)

    def _redeem_money(self, uid: str, stats: dict, qty: int) -> str:
        """书签兑换方斯"""
        need = BOOKMARK_MONEY_UNIT * qty
        have = stats.get("bookmarks", 0)
        if have < need:
            return (
                f"❌ 书签不足！需要 {need} 个，当前只有 {have} 个\n"
                f"（{BOOKMARK_MONEY_UNIT} 书签 = {_fmt_money(BOOKMARK_MONEY_AMOUNT)} 方斯）")
        amount = BOOKMARK_MONEY_AMOUNT * qty
        stats["bookmarks"] = have - need
        self._user_balance[uid] += amount
        self._save_balance()
        self._save_stats()
        return (
            f"💰 兑换成功！\n"
            f"消耗 {need} 个回声书签 → 获得 {_fmt_money(amount)} 方斯\n"
            f"🔖 剩余书签: {stats['bookmarks']} 个\n"
            f"💰 当前余额: {_fmt_money(self._user_balance[uid])} 方斯")

    def _redeem_cards(self, uid: str, stats: dict, qty: int, tier: int) -> str:
        """书签兑换该档今日追加额度"""
        card_conf = CARD_TYPES.get(int(tier), CARD_TYPES[50000])
        tier_key = str(int(tier)) if int(tier) in CARD_TYPES else "50000"
        need = self._bookmark_cost_for_tier(card_conf) * qty
        have = stats.get("bookmarks", 0)
        if have < need:
            return (
                f"❌ 书签不足！兑换 {card_conf['label']}档 {qty} 张额度需要 {need} 个，"
                f"当前只有 {have} 个")
        stats["bookmarks"] = have - need
        _, extra_by_tier = self._tier_daily(stats)
        extra_by_tier[tier_key] = extra_by_tier.get(tier_key, 0) + qty
        self._save_stats()
        return (
            f"🎴 兑换成功！\n"
            f"消耗 {need} 个回声书签 → {card_conf['label']}档 +{qty} 张今日追加额度\n"
            f"🔖 剩余书签: {stats['bookmarks']} 个")

    def _redeem_hand(self, uid: str, stats: dict) -> str:
        """书签兑换「玛门的大手」：今日基础额度购卡未中奖全额返还成本"""
        return self._activate_amulet(stats, "hand", AMULET_HAND_COST,
                                     "玛门的大手",
                                     "今日基础额度购卡未中奖将全额返还成本")

    def _redeem_backdoor(self, uid: str, stats: dict) -> str:
        """书签兑换「猫丸的后门」：今日基础额度购卡中奖低于成本返差额"""
        return self._activate_amulet(stats, "backdoor", AMULET_BACKDOOR_COST,
                                     "猫丸的后门",
                                     "今日基础额度购卡中奖低于成本将返还差额")

    def _activate_amulet(self, stats: dict, amulet_type: str, cost: int,
                         name: str, effect: str) -> str:
        """激活当日保底护符（大手/后门）。同一天只能有一种生效，已有护符时直接拦截。"""
        today = date.today().isoformat()
        active_type = self._amulet_active(stats)
        if active_type:
            active_name = "玛门的大手" if active_type == "hand" else "猫丸的后门"
            return f"❌ 今日「{active_name}」已生效，护符每日限购一种（当日有效，明日可再买）"
        have = stats.get("bookmarks", 0)
        if have < cost:
            return (
                f"❌ 书签不足！购买「{name}」需要 {cost} 个，当前只有 {have} 个")
        stats["bookmarks"] = have - cost
        stats["amulet_date"] = today
        stats["amulet_type"] = amulet_type
        self._save_stats()
        return (
            f"🛡️ {name}生效！\n"
            f"消耗 {cost} 个回声书签 → 今日保底生效\n"
            f"🔖 剩余书签: {stats['bookmarks']} 个\n"
            f"🛡️ {effect}")

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
    # 指令: /刮发卡 [数量] @用户  - 管理员发追加额度
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
            f"{target_name} 获得 {card_conf['label']}档 +{extra} 张追加额度\n"
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
