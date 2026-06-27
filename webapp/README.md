# 流量罗盘 · Web 应用

FastAPI 后端 + 单文件聊天前端。发抖音前：粘贴文案 → 查违规 + 流量潜力评分 + 追问改写。
（完整说明见仓库根目录 [README](../README.md)。）

## 运行

```bash
pip install -r requirements.txt

# 配置 DeepSeek Key（二选一）
cp _data/apikeys.example.json _data/apikeys.json   # 编辑填入 deepseek key
# 或：export DEEPSEEK_KEY=你的密钥

python app.py
# → http://127.0.0.1:8900
```

## 接口

| 路由 | 说明 |
|---|---|
| `POST /api/audit` | 文案审核：纠错 + 违规清单 + 流量潜力评分（核心） |
| `POST /api/chat` | 带报告上下文追问 / 改写 |
| `POST /api/extract` | 可选：抖音链接 → 文字（需 cookie + 百炼 key；`DISABLE_EXTRACT=1` 可关闭） |
| `GET /api/platforms` | 平台列表（抖音可用，其余占位） |

## 文件

- `app.py` 路由 · `llm.py` DeepSeek 调用 · `engine.py` 规则引擎
- `audit_skill.md` ⭐审核大脑（改规则改这里）
- `rules/douyin.json` 抖音规则包 · `static/index.html` 前端
- 运行记录写到 `../records/records.jsonl`（回填真实播放量可校准评分）

## 部署提示

生产环境用 `uvicorn app:app --host 127.0.0.1 --port 8900` + 反向代理（DeepSeek 审核耗时 7~37s，反代 `proxy_read_timeout` 建议 ≥180s）。**上线务必加登录/限流**，否则任何人都能调用、消耗你的 API key。
