"""通用审核+预测引擎（平台无关）。加载某平台规则包 JSON，对文案做：
  - 违规自查（L2 违禁词 + L3 白名单防误杀 + AI标注 + 资质红线）
  - 表现预测（基准区间 × 质量系数 × 合规系数）
代码侧确定性计算；DeepSeek 语境/润色在 app.py 里可选叠加。"""
import json, os

RULES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules")

# 营销语境关键词：用于判断「最/顶级」等极限词是不是在带货推广语境（防误杀核心）
MARKETING_HINTS = ["买", "购", "下单", "优惠", "价", "抢", "秒杀", "折", "促销", "店", "货",
                   "链接", "领", "券", "包邮", "限时", "到手", "原价", "现价", "拍下", "成交"]
# 看语境的极限词：只在「自己周围」有营销词时才算违规，否则是正常口语（防误杀）
SOFT_SAFE_WORDS = {"最", "唯一", "顶级", "最佳", "最优"}
_WIN = 12  # 判断营销语境的左右窗口字数


def list_packs() -> list:
    out = []
    for fn in sorted(os.listdir(RULES_DIR)):
        if fn.endswith(".json"):
            try:
                with open(os.path.join(RULES_DIR, fn), encoding="utf-8") as f:
                    p = json.load(f)
                out.append({"id": p["id"], "name": p["name"], "enabled": p.get("enabled", False)})
            except Exception:
                pass
    return out


def load_pack(platform_id: str) -> dict:
    path = os.path.join(RULES_DIR, f"{platform_id}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"无此平台规则包: {platform_id}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _is_marketing(text: str) -> bool:
    return any(h in text for h in MARKETING_HINTS)


def scan_text(text: str, pack: dict) -> dict:
    """返回 {hits, whitelist_notes, redlines}。"""
    text = text or ""
    marketing = _is_marketing(text)
    whitelist_words = set()
    for w in pack.get("l3_whitelist", []):
        whitelist_words.update(w["words"])

    hits, whitelist_notes, seen = [], [], set()

    for entry in pack.get("l2", []):
        for word in entry["words"]:
            if word not in text or word in seen:
                continue
            # L3 白名单：精确命中白名单词 → 不报
            if word in whitelist_words:
                whitelist_notes.append(f"「{word}」价格/正常用语，此处安全")
                seen.add(word)
                continue
            # 看语境的极限词（最/唯一/顶级…）：一律列出（碰规范必列），但语境决定严重度——
            # 周围无营销词 = 降为 🟡 提示并注明"疑似正常，自行确认"；有营销词 = 按原严重度。
            if word in SOFT_SAFE_WORDS:
                i = text.find(word)
                win = text[max(0, i - _WIN): i + len(word) + _WIN]
                if not any(h in win for h in MARKETING_HINTS):
                    hits.append({
                        "word": word, "category": entry["category"], "severity": "low",
                        "replace": entry["replace"],
                        "note": "疑似正常语境（周围无营销词），但属敏感词，请自行确认"
                    })
                    seen.add(word)
                    continue
            hits.append({
                "word": word, "category": entry["category"], "severity": entry["severity"],
                "replace": entry["replace"], "note": ""
            })
            seen.add(word)

    # 去重：若某命中词是另一命中词的子串（如 100% ⊂ 100%有效），丢掉短的
    words_now = [h["word"] for h in hits]
    hits = [h for h in hits if not any(h["word"] != o and h["word"] in o for o in words_now)]

    # 资质红线
    redlines = []
    for r in pack.get("qual_redlines", []):
        for t in r["trigger"]:
            if t in text:
                redlines.append({"field": r["field"], "trigger": t, "note": r["note"], "severity": "high"})
                break
    return {"hits": hits, "whitelist_notes": whitelist_notes, "redlines": redlines, "marketing": marketing}


def ai_check(meta: dict, pack: dict) -> dict:
    has_ai = meta.get("has_ai")
    labeled = meta.get("ai_labeled")
    if not has_ai:
        return {"need": False, "ok": True, "msg": "未标明含AI内容（如有AI参与请补标注）"}
    if labeled:
        return {"need": True, "ok": True, "msg": "含AI且已双标注 ✅（合规AI内容还可进专属流量池）"}
    return {"need": True, "ok": False, "severity": "high",
            "msg": "🔴 含AI但未达标双标注。要求：" + pack.get("ai_rule", {}).get("double_label_desc", "")}


def verdict(scan: dict, ai: dict) -> str:
    high = [h for h in scan["hits"] if h["severity"] == "high"]
    if scan["redlines"]:
        return "⛔ 高风险勿发：触碰资质红线"
    if any(h["category"].startswith("引流") for h in high) or len(high) >= 3:
        return "⛔ 高风险勿发：违规较重，改完再发"
    if high or (ai and not ai.get("ok", True)):
        return "🛠 改完可发：处理下面🔴项"
    if [h for h in scan["hits"] if h["severity"] == "mid"]:
        return "🛠 建议优化后发：有🟠项"
    return "✅ 可发"


def _fans_tier(fans: int) -> str:
    if fans < 1000:
        return "0-1000"
    if fans < 10000:
        return "1000-10000"
    return "10000-100000"


def predict(meta: dict, pack: dict, has_high_risk: bool) -> dict:
    pr = pack["predict"]
    if has_high_risk:
        return {"blocked": True, "msg": "命中🔴高风险（违禁词/资质红线），先改违规再谈预测。"}

    fans = int(meta.get("fans") or 0)
    track = meta.get("track") or pr["default_track"]
    tier = _fans_tier(fans)
    bm = pr["benchmarks"].get(tier, {}).get(track) or pr["benchmarks"]["0-1000"]["AI知识科普"]

    # 质量系数
    qf = pr["quality_factors"]
    q = 1.0
    notes_weak = []
    dur = meta.get("duration")
    if dur:
        if (15 <= dur <= 75) or (180 <= dur <= 600):
            q += qf["duration_fit"]
        else:
            q -= qf["duration_fit"]; notes_weak.append("时长不在知识类高完播区间(短30-45s/长3-8min)")
    if meta.get("ratio") == "9:16":
        q += qf["ratio_916"]
    elif meta.get("ratio") == "16:9":
        q -= 0.15; notes_weak.append("横屏发主feed完播偏低")
    # 三态：True=加分 / False=减分+列短板 / None(未知)=中性，不猜不编
    rp = meta.get("real_person")
    if rp is True:
        q += qf["real_person"]
    elif rp is False:
        q -= qf["real_person"]; notes_weak.append("非真人出镜，原创权重偏低")
    dens = meta.get("info_density")
    if dens == "高":
        q += qf["info_density_high"]
    elif dens == "低":
        q += qf["info_density_low"]; notes_weak.append("信息密度低，拉低收藏/复访")
    if meta.get("full_subtitle") is True:
        q += qf["full_subtitle"]
    hk = meta.get("strong_hook")
    if hk is True:
        q += qf["strong_hook"]
    elif hk is False:
        notes_weak.append("前3秒钩子偏弱，影响3秒留存")
    cp = meta.get("collect_potential")
    if cp is True:
        q += qf["collect_potential"]
    elif cp is False:
        notes_weak.append("缺可收藏的干货点，收藏率上不去（知识类核心指标）")
    lo, hi = pr["quality_clamp"]
    q = max(lo, min(hi, round(q, 2)))

    # 合规系数
    c = 1.0
    if meta.get("has_ai") and not meta.get("ai_labeled"):
        c *= 0.4
        notes_weak.append("AI未双标注，播放上限被压（×0.4）")
    health = meta.get("health")
    if health is not None:
        if health < 50:
            c *= 0.3
        elif health < 70:
            c *= 0.6

    normal = [round(bm["normal"][0] * q * c), round(bm["normal"][1] * q * c)]
    good_top = round(bm["good"][1] * q * c)

    # 流量池预判（按 normal 上限分档）
    top = normal[1]
    if top < 1000:
        pool = "冷启动种子池"
    elif top < 5000:
        pool = "初级流量池"
    elif top < 30000:
        pool = "中级流量池"
    elif top < 500000:
        pool = "高级流量池"
    else:
        pool = "全站热门池"

    return {
        "blocked": False, "tier": tier, "track": track,
        "quality_coeff": q, "compliance_coeff": round(c, 2),
        "normal_range": normal, "good_top": good_top,
        "pool": pool, "weakness": notes_weak[:3],
        "disclaimer": "此为基于规则与行业基准的估算，浮动大（±30%+），靠回填真实播放量逐步校准。"
    }


def audit(text: str, meta: dict, platform_id: str) -> dict:
    pack = load_pack(platform_id)
    scan = scan_text(text, pack)
    ai = ai_check(meta, pack)
    has_high = bool(scan["redlines"]) or any(h["severity"] == "high" for h in scan["hits"]) or (ai.get("need") and not ai.get("ok"))
    pred = predict(meta, pack, has_high_risk=bool(scan["redlines"]) or any(h["severity"] == "high" for h in scan["hits"]))
    return {
        "platform": pack["name"],
        "scan": scan,
        "ai_check": ai,
        "verdict": verdict(scan, ai),
        "predict": pred,
    }
