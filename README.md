# NTE 刮刮乐 — AstrBot 插件

🎴 复刻异环的刮刮乐玩法，适用于 AstrBot 聊天机器人平台。


## 插件信息

| 项目 | 值 |
|------|-----|
| 插件名称 | `astrbot_plugin_nte_scratch_card` |
| 展示名 | 异环刮刮乐 |
| 作者 | [CavinGou](https://github.com/CavinGou) |
| 版本 | v1.2.0 |
| 仓库 | [CavinGou/astrbot_plugin_nte_scratch_card](https://github.com/CavinGou/astrbot_plugin_nte_scratch_card) |
| 支持平台 | 仅 OneBot v11（`aiocqhttp`） |
| AstrBot 版本 | `>= 4.17.0` |
| 标签 | 游戏 · 刮刮乐 · 娱乐 · 排行榜 |

## 功能

| 指令 | 说明 |
|------|------|
| `刮刮乐 [数量]` | 一键购买并刮开，支持一次多张（合并转发） |
| `刮取钱` | 周期内顺序随机的四档补助（30/50/70/100 万方斯） |
| `刮余额` | 查看余额和游戏统计数据 |
| `富爪榜` | 查看累计盈亏排行榜（图片） |
| `富爪日榜` | 查看今日盈亏排行榜（图片） |
| `刮转账 @用户 金额` | 将自己的方斯转给指定用户 |
| `刮刮乐帮助` | 显示帮助信息 |

### 管理员指令

| 指令 | 说明 |
|------|------|
| `刮发钱 @用户 金额` | 给指定用户增加方斯余额 |
| `刮发卡 [数量] @用户` | 给指定用户增加今日额外购卡额度 |

### LLM 自然语言指令

接入 AstrBot 的函数调用（`@filter.llm_tool`）后，大模型可根据用户意图自动触发刮卡、查余额、申请与审批等操作，无需输入精确指令：

| 工具 | 触发示例 | 权限 |
|------|----------|------|
| `scratch_ntc_card` | 「帮我刮 5 张卡」「来一张刮刮乐」 | 所有用户 |
| `daily_pension` | 「领一下今天的方斯福利」 | 所有用户 |
| `check_scratch_balance` | 「我还有多少方斯」「看下我的战绩」 | 所有用户 |
| `give_money` | 「给我申请 10 万方斯」「给张三发 10 万方斯」 | 管理员直接发放；普通用户自动转为申请 |
| `give_cards` | 「给我申请 5 张额度」「给我发 5 张卡」 | 管理员直接发放；普通用户自动转为申请 |
| `admin_approve_request` / `admin_reject_request` | 引用申请消息回复「同意 / 批准 / 拒绝」 | 仅 AstrBot 管理员 |
| `list_pending_requests` | 「查看待审批」 | 仅 AstrBot 管理员 |

> 💡 说明：
> - 管理员为 AstrBot 后台「配置 → 通用设置 → 管理员（`admins_id`）」中配置的用户。
> - `give_money` / `give_cards` 会根据说话者身份自动分流：管理员直接发放；普通用户只能提交申请（目标强制为自己），实际发放由管理员批准后执行，降低 prompt 注入滥用风险。
> - 可通过 `enable_llm_tools` 配置项一键关闭 LLM 自然语言指令，关闭后仅保留精确指令。

## 卡片说明

| 项目 | 数值 |
|------|------|
| 售价 | **50,000 方斯** |
| 格子数 | 15 格（3 × 5） |
| 最高奖金 | **250 万方斯** |

### 单格奖金档位

2万 · 5万 · 10万 · 15万 · 20万 · 30万 · 50万 · 80万 · 100万 · 150万

## 概率系统

基于异环实际数据提取的概率。先按概率抽取总奖金，再分解到 15 个格子中。

## 货币系统

- 每位新用户初始持有 **3,000,000 方斯**
- 每次刮卡消耗 50,000 方斯，每日限购 **60 张**（可通过配置调整）
- 每日可领取补助（默认 30/50/70/100 万四个档位，4 天一个周期，周期内顺序随机，档位可自定义）
- 盈亏按累计盈亏（总奖金 - 总投入）排名

## 配置

插件支持通过 AstrBot 后台的可视化配置界面（`_conf_schema.json`）在线调整所有参数：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `pension_tiers` | 列表 | 30/50/70/100 万方斯 | 刮取钱档位，可自定义金额与领取文案 |
| `daily_limit` | 整数 | 60 | 每人每日限购张数 |
| `enable_llm_tools` | 布尔 | true | 启用 LLM 自然语言指令，关闭后大模型无法触发刮卡/发钱/申请等操作 |
| `leaderboard_inactive_days` | 整数 | 7 | 富爪榜排除 N 天以上没抽过卡的用户，0 表示不过滤 |
| `napcat_host` | 字符串 | `127.0.0.1:3000` | NapCat 连接地址，多个地址用逗号分隔 |
| `napcat_token` | 字符串 | 空 | NapCat API Token |

> 💡 排行榜依赖 NapCat API 获取群成员列表与群名片（用于跨群隔离与昵称显示），请确保 `napcat_host` / `napcat_token` 配置正确；否则排行榜将回退为纯文本展示。

## 排行榜

`富爪榜` 与 `富爪日榜` 通过 AstrBot 的**文转图（HTML 渲染）**功能生成 NTE 风格的排行榜图片卡片：

- 使用 `HTML + Jinja2` 模板渲染，调用 AstrBot 的 HTML 渲染服务（t2i / htmlrender）。
- 渲染服务不可用或渲染失败时，会自动**回退为纯文本排行榜**，不影响功能使用。
- `富爪榜` 默认会排除超过 **7 天**未抽卡的用户（可通过配置 `leaderboard_inactive_days` 调整，设为 `0` 不过滤）。
- 相关文档：[AstrBot 文转图（HTML 渲染）](https://docs.astrbot.app/dev/star/guides/html-to-pic.html)

## 平台支持

本插件**仅支持 OneBot v11 协议**（适配器标识符 `aiocqhttp`），推荐使用 [NapCat](https://napcat.napneko.icu/) 接入 QQ。

- ✅ **支持**：QQ（经 NapCat、Lagrange、LLOneBot 等 OneBot v11 实现）
- ❌ **不支持**：QQ 官方机器人（`qq_official`）、Telegram、微信、飞书等其它平台

> ⚠️ 插件依赖 OneBot 的 `get_group_member_list` / `get_group_member_info` 接口（排行榜跨群隔离与昵称显示）、`At` 组件（转账/发钱/发卡）以及合并转发（`Nodes`，批量刮卡）等 QQ 群能力，因此仅在 OneBot v11 下可提供完整功能。

## 安装

将本仓库克隆或下载到 AstrBot 的 `addons` 目录下即可。

```bash
cd addons
git clone https://github.com/CavinGou/astrbot_plugin_nte_scratch_card.git
```

## 数据存储

插件数据保存在 AstrBot 数据目录下的 `plugin_data/nte_scratch_card/`（通常为 `data/plugin_data/nte_scratch_card/`）：
- `balance.json` — 用户余额数据
- `stats.json` — 用户游戏统计数据
- `pending_requests.json` — 成员申请-管理员审批的待审批记录（LLM 自然语言指令使用）

插件配置保存在 AstrBot 的配置系统中，可通过后台可视化界面随时修改。

## 参考

- [AstrBot 项目](https://github.com/AstrBotDevs/AstrBot)
- [AstrBot 插件开发文档](https://docs.astrbot.app/dev/star/plugin-new.html)
