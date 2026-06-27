"""DeepSeek V4 Flash —— 审核大脑(纠错+语境违规+流量潜力) + 报告后对话(追问/改写)。"""
import os
import json as _json
import httpx
from config import DEEPSEEK_KEY, DEEPSEEK_HOST, DEEPSEEK_MODEL

_SKILL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit_skill.md")


def _load_skill() -> str:
    with open(_SKILL_PATH, encoding="utf-8") as f:
        return f.read()


async def audit_full(text: str, candidates=None) -> dict:
    """一次 DeepSeek 调用：纠错 + 语境违规审核 + 流量潜力评分。返回结构化 dict。"""
    user = "口播文案：\n" + (text or "")
    if candidates:
        user += "\n\n【代码预扫到的疑似违禁词，请逐一在语境中复核，可推翻也可补充】：" + "、".join(candidates)
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [{"role": "system", "content": _load_skill()},
                     {"role": "user", "content": user}],
        "temperature": 0.3, "stream": False,
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=15.0)) as c:
        r = await c.post(f"https://{DEEPSEEK_HOST}/chat/completions",
                         headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
                         json=payload)
        r.raise_for_status()
        return _json.loads(r.json()["choices"][0]["message"]["content"])

SYSTEM = """你是「抖音作品合规与运营助手」。用户发抖音视频前用你做自查与优化。已知抖音规则要点：

【违禁词】广告法极限词（最/全网第一/100%有效/绝对/国家级/央视推荐/秒杀等，营销语境违规）；虚假宣传（神器/黑科技/躺赚/月入过万/零成本）；封建迷信（改运/招财/算命/风水/转运）；引流（微信/vx/二维码/加群/私信，非企业蓝V一律违规）；功效承诺（包过/7天速成/学不会退款）；AI夸大（100%替代某职业/取代人工/让所有人失业）。
【防误杀】"钱/便宜/万/千元/直播间"是正常词；"最"在非营销语境正常（如"最伟大的人"）。不要把正常表达当违规吓唬用户。
【AI标注】用了AI（写文案/配音/画面/数字人/剪辑）必须双标注：发布端勾选官方AI标签 + 画面前5秒字幕"含AI生成内容"停留≥3秒，缺一限流。
【资质红线】无资质禁止：医疗诊断/治疗、金融荐股/保本、法律咨询、教育押题。
【表现/算法】权重：收藏率>复访>铁粉互动>5秒完播>整体完播>评论>点赞>转发。知识类主攻收藏率+前3秒钩子+信息密度。

你的任务：基于系统给你的"本条作品自查报告"，回答用户追问——
1) 解释为什么会违规/限流/预测低；
2) 【改写=最小改动】只替换或删掉违规的那几个词，**其余原文一字不动**。务必保留原作者的口语腔、口头禅、节奏和语气（像"OK兄弟们""咱就别""是吧"这种照留）。绝对不要整段重写、不要书面化、不要加华丽辞藻、不要变成AI腔。目标是让作者觉得"这还是我说的话，只是把违规词换掉了"。改写时优先用"列出：哪个词→换成什么"的方式，能不动就不动；
3) 给具体涨播放建议（钩子、收藏点、结构）；
4) 用户改完想重测时，提醒他重新发文案自查。
简洁、口语、直接给可用结果，别绕、别废话、别复述报告原文。"""


ASSESS_SYS = """你是抖音内容评估助手。读这段视频口播文案，只判断下面4项，严格只输出 JSON，不要任何解释：
{"real_person": true/false,  // 听起来像真人口播(有口头禅、自然语气、个人表达)=true；像机器朗读/AI生成腔=false；拿不准填 null
 "hook_strong": true/false,  // 开头前两三句是否抓人(提问/冲突/利益点/反常识)
 "collect": true/false,      // 是否有可收藏的干货(步骤/清单/方法/可复用的东西)
 "density": "高"/"中"/"低"}  // 单位时间有效信息密度
只输出上述 JSON 对象。"""


async def assess_content(text: str) -> dict:
    """DeepSeek 读文案，判断预测用的软指标（真人感/钩子/干货/信息密度）。失败返回空 {}。"""
    import json as _json
    msgs = [{"role": "system", "content": ASSESS_SYS},
            {"role": "user", "content": "文案：\n" + (text or "")[:3000]}]
    payload = {"model": DEEPSEEK_MODEL, "messages": msgs, "temperature": 0.2, "stream": False,
               "response_format": {"type": "json_object"}}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=15.0)) as c:
            r = await c.post(f"https://{DEEPSEEK_HOST}/chat/completions",
                             headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
                             json=payload)
            r.raise_for_status()
            d = _json.loads(r.json()["choices"][0]["message"]["content"])
        return {
            "real_person": d.get("real_person"),
            "hook_strong": d.get("hook_strong"),
            "collect": d.get("collect"),
            "density": d.get("density") if d.get("density") in ("高", "中", "低") else None,
        }
    except Exception as e:
        print(f"[assess] 失败: {e}", flush=True)
        return {}


async def chat(messages: list, report_context: str = "") -> str:
    msgs = [{"role": "system", "content": SYSTEM}]
    if report_context:
        msgs.append({"role": "system", "content": "【本条作品的自查报告（你的回答要基于它）】\n" + report_context})
    msgs += messages
    payload = {"model": DEEPSEEK_MODEL, "messages": msgs, "temperature": 0.6, "stream": False}
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=15.0)) as c:
        r = await c.post(f"https://{DEEPSEEK_HOST}/chat/completions",
                         headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
                         json=payload)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
