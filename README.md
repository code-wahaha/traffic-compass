# 流量罗盘 · Traffic Compass

> 抖音作品发布前的 **AI 合规自查 + 流量潜力评分** 工具。
> 粘贴你的口播文案 → 一键查出违规风险、给出最小改动建议、并按赛道权重打出"流量潜力分"。

发抖音最怕两件事：**违规限流**、**辛苦做了没流量**。流量罗盘在你点"发布"之前先帮你过一遍：

- 🛡 **违规自查**：广告法极限词、绝对化用语、引流导流、封建迷信、AI 能力夸大/焦虑营销、医疗/金融/法律/教育资质红线……读语境判断，**不见词就杀**（"我妈是最好的人"不会被误报）。
- ✍️ **最小改动建议**：只换违规的那几个词，**保留你的口语腔和节奏**，不把你的话改成 AI 腔。
- 📈 **流量潜力评分**：满分 100，按 AI 口播赛道权重打分（**收藏价值 28% + 开头钩子 20%** 为核心），指出最该补的短板。
- 💬 **追问改写**：出报告后还能继续问"为什么会限流""帮我把开头改强一点"。

> ⚠️ 合规判定是**参考**不是法律意见；流量潜力是**文案维度**的估算（不含画面/封面/口播节奏/发布时间/账号权重），**不承诺播放量**。

---

## 两种用法

### A. Web 应用（`webapp/`）
一个 FastAPI 后端 + 单文件聊天前端，本地或服务器都能跑。**只需一个 DeepSeek Key 即可使用核心功能。**

### B. Claude Code 技能（`skill/`）
把审核规则做成可装的 Agent 技能，在 Claude Code 里说"帮我自查这条抖音"即可触发，规则数据在 `skill/references/`。

---

## 快速开始（Web 应用）

```bash
cd webapp
pip install -r requirements.txt

# 配置 DeepSeek Key（二选一）：
#  1) 复制 _data/apikeys.example.json 为 _data/apikeys.json 并填入
#  2) 或设环境变量 DEEPSEEK_KEY=你的密钥
cp _data/apikeys.example.json _data/apikeys.json   # 然后编辑填 key

python app.py
# 打开 http://127.0.0.1:8900
```

默认是**文字粘贴模式**（无需任何 cookie）。把口播文案贴进去就能用。

---

## 配置说明

| 变量 | 必填 | 用途 |
|---|---|---|
| `DEEPSEEK_KEY` | ✅ | 审核大脑（纠错 + 语境违规 + 流量评分） |
| `DEEPSEEK_MODEL` | 否 | 默认 `deepseek-v4-flash`（快省）；`deepseek-v4-pro` 更准更慢 |
| `BAILIAN_KEY` | 否 | 仅"链接提取"用（阿里云百炼 ASR 语音转文字） |
| `DISABLE_EXTRACT` | 否 | 设 `1` 关闭链接提取，只用文字模式（无 cookie 时建议） |
| `DOUYIN_COOKIE_BASE` | 否 | 链接提取用的抖音登录态 cookie 基目录 |

> **链接提取（抖音链接 → 文字）是可选高级功能**，需自备抖音登录 cookie（放到 `<base>/chrome_data/douyin_cookies.json`）+ 百炼 Key，并安装 `dashscope` `playwright`。不配也完全不影响核心的文案自查。

---

## 项目结构

```
流量罗盘-开源/
├── webapp/                  # Web 应用（FastAPI + 单文件前端）
│   ├── app.py               # 后端路由：/api/audit /api/chat /api/extract /api/platforms
│   ├── llm.py               # DeepSeek 调用（审核大脑 + 追问改写）
│   ├── audit_skill.md       # ⭐核心：喂给 DeepSeek 的审核系统提示词（改规则改这里）
│   ├── engine.py            # 确定性规则引擎（违禁词召回网 + 防误杀 + 评分）
│   ├── extract.py           # 可选：抖音链接 → 文字（playwright + 百炼 ASR）
│   ├── config.py            # key/模型配置（env 优先）
│   ├── rules/douyin.json    # 抖音规则包（加平台 = 仿此再放一个 json）
│   ├── static/index.html    # 深色聊天 UI（单文件）
│   └── _data/apikeys.example.json
├── skill/                   # Claude Code 技能版（同一套规则）
│   ├── SKILL.md
│   ├── references/          # 违禁词库 / 白名单 / AI标注与资质 / 预测模型
│   └── scripts/log_record.py
├── docs/                    # 规则手册来源、设计文档、测试样例
├── .env.example
└── LICENSE                  # MIT
```

---

## 工作原理

```
口播文案
  → engine.py 代码预扫（确定性"必查名单"召回网，防漏看）
  → DeepSeek（带 audit_skill.md 审核大脑）：纠错 + 语境违规复核 + 流量潜力评分
  → 结构化报告（纠错原文 / 违规清单 / 亮点 / 改进 / 七维评分）
  → 可继续 /api/chat 追问、改写
```

**两层把关**：代码引擎负责"宁可多列"的召回（不漏），DeepSeek 负责"读语境"的精判（不误杀）。

---

## 扩展到其他平台（如小红书）

1. 仿 `webapp/rules/douyin.json` 写一份 `rules/xiaohongshu.json`（设 `"enabled": true`）。
2. 在 `audit_skill.md` 补充该平台的特有规则。
3. 前端下拉自动出现，无需改代码。

---

## 免责声明

本项目仅为**创作者自查辅助工具**。合规判定基于公开平台规则整理，**不构成法律意见**；平台规则随时变化，请以官方最新规则为准。流量潜力为基于经验与文案维度的**估算**，实际表现受画面、封面、发布时机、账号权重等大量变量影响，**不对任何播放/收益结果做承诺**。

## 开源协议

[MIT](./LICENSE) © code-wahaha
