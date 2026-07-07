"""抖音自查网页产品 —— 后端 (FastAPI)
v1 文字版：/api/audit 走代码引擎(确定性，无需密钥即可跑)。
后续接：/api/extract 抖音链接→文字(复用 Pixlix 母版 douyin_parser + 百炼ASR)；DeepSeek 语境润色。
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
    # DeepSeek 带审核Skill：纠错 + 语境违规 + 流量潜力，一次出（skill 按平台选）
    try:
        import llm
        r = await llm.audit_full(text, cand, platform)
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
        relay = os.getenv("EXTRACT_RELAY", "")
        body0 = await req.json()
        url0 = (body0.get("share_url") or body0.get("url") or "").strip()
        if relay and url0:
            import httpx
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=10.0)) as c:
                    r = await c.post(relay, json={"share_url": url0})
                    return JSONResponse(r.json())
            except Exception as e:
                return JSONResponse({"success": False, "message": f"云端提取服务暂不可用（{str(e)[:60]}），请先把视频文案直接粘进来自查。"})
        return JSONResponse({"success": False, "message": "网页版不做链接提取（那需要你的抖音登录，放服务器上不安全）。贴链接请用桌面版流量罗盘；或者把视频文案直接粘进来，一样自查。"})
    import extract as _ext
    body = await req.json()
    url = (body.get("share_url") or body.get("url") or "").strip()
    if not url:
        return JSONResponse({"success": False, "message": "链接不能为空"})
    try:
        return JSONResponse(await _ext.extract_from_link(url))
    except Exception as e:
        return JSONResponse({"success": False, "message": f"提取异常: {str(e)[:150]}"})


@app.get("/api/douyin_status")
async def douyin_status():
    """抖音登录态：给前端右下角小按钮显示用。"""
    import extract as _ext
    return JSONResponse({"success": True, "logged_in": _ext._is_logged_in()})


@app.post("/api/douyin_login")
async def douyin_login_api():
    """弹本机浏览器窗口，用户扫码登录自己的抖音（桌面版专用）。"""
    if os.getenv("DISABLE_EXTRACT"):
        return JSONResponse({"success": False, "message": "网页版不支持，请用桌面版。"})
    import asyncio
    import extract as _ext
    loop = asyncio.get_running_loop()
    ok = await loop.run_in_executor(None, _ext.douyin_login)
    if ok:
        return JSONResponse({"success": True, "message": "抖音登录成功！现在贴链接就能自动提取文案了。"})
    return JSONResponse({"success": False, "message": "没等到登录成功（超时或窗口被关了），再点一次试试。"})


@app.post("/api/chat")
async def chat_api(req: Request):
    """DeepSeek 追问/改写/解释：带上一份自查报告做上下文。"""
    import llm
    body = await req.json()
    msgs = body.get("messages") or [{"role": "user", "content": (body.get("message") or "").strip()}]
    if not msgs or not msgs[-1].get("content"):
        return JSONResponse({"success": False, "message": "内容不能为空"})
    try:
        reply = await llm.chat(msgs, body.get("report_context", ""), body.get("platform") or "douyin")
        return {"success": True, "data": {"reply": reply}}
    except Exception as e:
        return JSONResponse({"success": False, "message": f"DeepSeek 调用失败: {str(e)[:160]}"})


# ==================== v2 预测校准闭环 ====================
import db


@app.get("/api/accounts")
def accounts_list():
    return {"success": True, "data": db.list_accounts()}


@app.post("/api/accounts")
async def accounts_create(req: Request):
    b = await req.json()
    name = (b.get("name") or "").strip()
    try:
        baseline = int(b.get("baseline_median") or 0)
    except (TypeError, ValueError):
        baseline = 0
    if not name or baseline <= 0:
        return JSONResponse({"success": False, "message": "账号昵称和近期播放中位数必填（中位数>0）"})
    aid = db.create_account(name, b.get("platform") or "douyin", b.get("track") or "", baseline)
    return {"success": True, "data": db.get_account(aid)}


@app.post("/api/predict")
async def predict(req: Request):
    """盲预测：写入即锁定。必须在发布前调用（发布后补预测=作弊，直接拒绝）。"""
    b = await req.json()
    text = (b.get("text") or "").strip()
    account_id = b.get("account_id")
    if not text or not account_id:
        return JSONResponse({"success": False, "message": "text 和 account_id 必填"})
    if b.get("already_published"):
        return JSONResponse({"success": False, "message": "该作品已发布，不能补预测（盲预测原则：预测必须在看到数据之前）"})
    acc = db.get_account(account_id)
    if not acc:
        return JSONResponse({"success": False, "message": "账号不存在，请先创建账号档案"})
    import llm
    try:
        p = await llm.predict_blind(text, acc)
        w = db.create_work(account_id, text, b.get("audit"), p["bucket"], p["dist"], p.get("reason", ""))
    except Exception as e:
        return JSONResponse({"success": False, "message": f"预测失败: {str(e)[:160]}"})
    return {"success": True, "data": w}


@app.post("/api/publish")
async def publish(req: Request):
    b = await req.json()
    try:
        w = db.mark_published(b.get("work_id") or "", (b.get("video_url") or "").strip())
        return {"success": True, "data": w}
    except ValueError as e:
        return JSONResponse({"success": False, "message": str(e)})


@app.get("/api/works")
def works(account_id: int | None = None):
    return {"success": True, "data": db.list_works(account_id)}


@app.post("/api/retro/{work_id}")
async def retro_api(work_id: str, req: Request):
    b = await req.json()
    try:
        plays = int(b.get("plays"))
    except (TypeError, ValueError):
        return JSONResponse({"success": False, "message": "实际播放数必填"})
    def _i(k):
        try: return int(b.get(k))
        except (TypeError, ValueError): return None
    try:
        w = db.retro(work_id, plays, _i("likes"), _i("comments"), _i("shares"))
        return {"success": True, "data": w}
    except ValueError as e:
        return JSONResponse({"success": False, "message": str(e)})


@app.get("/api/report/{work_id}")
def report_api(work_id: str):
    w = db.report(work_id)
    if not w:
        return JSONResponse({"success": False, "message": "作品不存在"})
    return {"success": True, "data": w}


@app.get("/api/chatlog")
def chatlog_get(frame: str = "pre"):
    return {"success": True, "data": db.get_msgs(frame)}


@app.post("/api/chatlog")
async def chatlog_add(req: Request):
    b = await req.json()
    if not b.get("html"):
        return JSONResponse({"success": False, "message": "html 必填"})
    db.add_msg(b.get("frame") or "pre", b.get("role") or "bot", b["html"])
    return {"success": True}


@app.delete("/api/chatlog")
def chatlog_clear(frame: str = "pre"):
    db.clear_msgs(frame)
    return {"success": True}


@app.get("/api/settings")
def settings_get():
    import config
    return {"success": True, "data": {"deepseek": bool(config.get_key("deepseek")),
                                      "bailian": bool(config.get_key("bailian"))}}


@app.post("/api/settings")
async def settings_set(req: Request):
    import config
    b = await req.json()
    saved = []
    for k in ("deepseek", "bailian"):
        if (b.get(k) or "").strip():
            config.save_key(k, b[k]); saved.append(k)
    if not saved:
        return JSONResponse({"success": False, "message": "没有可保存的 key"})
    return {"success": True, "data": saved}


@app.get("/api/export")
def export_api(format: str = "csv"):
    from fastapi.responses import Response
    import io, csv
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    if format == "json":
        data = json.dumps(db.export_full(), ensure_ascii=False, indent=1)
        return Response(content=data, media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="luopan_backup_{ts}.json"'})
    rows = db.export_rows()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["预测时间", "账号", "内容摘要", "预测桶", "预计播放", "状态", "发布时间",
                "实际播放", "点赞", "评论", "转发", "偏差%", "命中", "复盘时间", "预测理由"])
    STATUS = {"predicted": "待发布", "published": "已发布", "retroed": "已复盘"}
    for r in rows:
        dev = "" if r["deviation_pct"] is None else round(r["deviation_pct"] * 100)
        hit = "" if r["hit_bucket"] is None else ("命中" if r["hit_bucket"] else "未中")
        w.writerow([r["predicted_at"], r.get("account_name") or "",
                    (r["text_snapshot"] or "")[:60].replace("\n", " "),
                    r["pred_bucket"], r["pred_center"], STATUS.get(r["status"], r["status"]),
                    r["published_at"] or "",
                    r["actual_plays"] if r["actual_plays"] is not None else "",
                    r["actual_likes"] or "", r["actual_comments"] or "", r["actual_shares"] or "",
                    dev, hit, r["retro_at"] or "", (r["pred_reason"] or "").replace("\n", " ")])
    return Response(content="﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="luopan_ledger_{ts}.csv"'})


@app.post("/api/reset")
async def reset_all(req: Request):
    b = await req.json()
    if b.get("confirm") != "重置":
        return JSONResponse({"success": False, "message": "需要 confirm='重置' 确认"})
    db.reset_all()
    return {"success": True}


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


if os.path.isdir(STATIC):
    app.mount("/static", StaticFiles(directory=STATIC), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8900)
