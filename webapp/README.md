# 抖音作品自查网页（webapp）

发布前体检：粘贴文案/链接 → 查违规 + 预测播放表现。深色聊天窗口，底部下拉选平台（抖音可用，其余即将支持）。

## 目录
- `static/index.html` 前端（单文件聊天 UI）
- `app.py` 后端（FastAPI）：`/api/platforms`、`/api/audit`、`/api/extract`(占位)
- `engine.py` 通用引擎：违禁词匹配 + 防误杀 + 预测三段式
- `rules/douyin.json` 抖音规则包（**加平台 = 仿此再放一个 json**）
- 记录写到 `../records/records.jsonl`

## 本地运行
```bash
pip install fastapi "uvicorn[standard]"
cd "F:\Vibe Coding\抖音监察\webapp"
python app.py
# 打开 http://127.0.0.1:8900
```

## 路线
- v1（当前）：文字版，代码引擎，无需密钥即可跑。
- v2：接 DeepSeek V4 Flash 做语境/润色；`/api/extract` 接百炼ASR + Pixlix母版 douyin_parser（链接→文字）。
- v3：部署阿里云 8.218.32.133 + Pixlix-Hub 登录发码。

## 加新平台（如小红书）
1. 喂规则 → 仿 `rules/douyin.json` 写 `rules/xiaohongshu.json`（设 `enabled:true`）。
2. 前端下拉自动出现并可选，无需改代码。
