"""抖音自查网页产品 —— 后端 (FastAPI)
v1 文字版：/api/audit 走代码引擎(确定性，无需密钥即可跑)。
/api/extract 抖音链接→文字(playwright 抓直链 + 百炼ASR，可选)；DeepSeek 语境审核。
"""
import os, json, datetime
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

import engine

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "static")
RECORDS = os.path.join(os.path.dirname(BASE), "records", "records.jsonl")

app = FastAPI(title="流量罗盘")


def _log(rec: dict):
    rec = dict(rec)
    rec["ts"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rec.setdefault("real_views", None)
    os.makedirs(os.path.dirname(RECORDS), exist_ok=True)
    with open(RECORDS, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


@app.get("/api/platforms")
def platforms():
    # 固定展示顺序：抖音可用，其余占位「即将支持」
    packs = {p["id"]: p for p in engine.list_packs()}
    order = [
        {"id": "douyin", "name": "抖音"},
        {"id": "xiaohongshu", "name": "小红书"},
        {"id": "kuaishou", "name": "快手"},
        {"id": "shipinhao", "name": "视频号"},
    ]
    out = []
    for o in order:
        p = packs.get(o["id"])
        out.append({"id": o["id"], "name": o["name"], "enabled": bool(p and p.get("enabled"))})
    return {"success": True, "data": out}


def _verdict(violations):
    highs = [v for v in violations if v.get("severity") == "high"]
    mids = [v for v in violations if v.get("severity") == "mid"]
    if len(highs) >= 2:
        return "⛔ 高风险勿发：先改掉下面的🔴项"
    if highs:
        return "🛠 改完可发：处理🔴项"
    if mids:
        return "🛠 建议优化后发：有🟠项"
    return "✅ 可发"


@app.post("/api/audit")
async def audit(req: Request):
    body = await req.json()
    text = (body.get("text") or "").strip()
    platform = body.get("platform") or "douyin"
    if not text:
        return JSONResponse({"success": False, "message": "文案内容不能为空"})
    # 代码预扫做"必查名单"召回网，递给 DeepSeek 防漏看
    try:
        cand = [h["word"] for h in engine.scan_text(text, engine.load_pack(platform))["hits"]]
        pname = engine.load_pack(platform)["name"]
    except Exception:
        cand, pname = [], "抖音"
    # DeepSeek 带审核Skill：纠错 + 语境违规 + 流量潜力，一次出
    try:
        import llm
        r = await llm.audit_full(text, cand)
    except Exception as e:
        return JSONResponse({"success": False, "message": f"DeepSeek 审核失败: {str(e)[:160]}"})
    r["platform"] = pname
    r["verdict"] = _verdict(r.get("violations", []))
    sc = r.get("score", {}) or {}
    _log({
        "platform": pname, "summary": text[:40],
        "violations": [v.get("text") for v in r.get("violations", [])],
        "verdict": r["verdict"],
        "score": sc.get("total"), "level": sc.get("level"),
    })
    return {"success": True, "data": r}


@app.post("/api/extract")
async def extract_api(req: Request):
    """抖音链接 → 文字：playwright 抓直链 + 百炼 paraformer-v2 ASR。"""
    if os.getenv("DISABLE_EXTRACT"):
        return JSONResponse({"success": False, "message": "链接提取暂未开放，请直接粘贴视频文案自查（提取功能即将上线）。"})
    import extract as _ext
    body = await req.json()
    url = (body.get("share_url") or body.get("url") or "").strip()
    if not url:
        return JSONResponse({"success": False, "message": "链接不能为空"})
    try:
        return JSONResponse(await _ext.extract_from_link(url))
    except Exception as e:
        return JSONResponse({"success": False, "message": f"提取异常: {str(e)[:150]}"})


@app.post("/api/chat")
async def chat_api(req: Request):
    """DeepSeek 追问/改写/解释：带上一份自查报告做上下文。"""
    import llm
    body = await req.json()
    msgs = body.get("messages") or [{"role": "user", "content": (body.get("message") or "").strip()}]
    if not msgs or not msgs[-1].get("content"):
        return JSONResponse({"success": False, "message": "内容不能为空"})
    try:
        reply = await llm.chat(msgs, body.get("report_context", ""))
        return {"success": True, "data": {"reply": reply}}
    except Exception as e:
        return JSONResponse({"success": False, "message": f"DeepSeek 调用失败: {str(e)[:160]}"})


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


if os.path.isdir(STATIC):
    app.mount("/static", StaticFiles(directory=STATIC), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8900)
