"""抖音链接 → 文字（提取链路）
复刻 Pixlix 母版 douyin_parser + bailian_api 的核心逻辑，自包含：
  1) playwright 登录态浏览器抓 douyinvod CDN 直链（cookie 复用母版）
  2) 百炼 paraformer-v2 异步 ASR 把直链转文字
"""
import asyncio, json, os, re, time, urllib.request
import config
from config import BAILIAN_ASR_MODEL, PIXLIX_MUBAN_DIR

# 优先环境变量（服务器/异机部署用），否则用母版目录（本机）
CHROME_DATA = os.getenv("DOUYIN_CHROME_DATA") or os.path.join(PIXLIX_MUBAN_DIR, "chrome_data")
COOKIE_JSON = os.path.join(CHROME_DATA, "douyin_cookies.json")
MOBILE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
             "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
             "TikTok/26.2.0 TTWebView/TikTokWebView")
_PREFERRED = ("douyinvod.com", "/video/tos/")
_MEDIA = ("douyinvod.com", "/video/tos/", "/aweme/v1/play", "aweme.snssdk.com/aweme/v1/play")


def _extract_url(text):
    m = re.findall(r'https?://[^\s，。！？、…【】《》""'']+', text or "")
    return (m[-1].rstrip('.,;:!?)') if m else (text or "").strip())


def _video_id(url):
    m = re.search(r'/video/(\d+)', url or "")
    return m.group(1) if m else ""


def _is_logged_in():
    if not os.path.isfile(COOKIE_JSON):
        return False
    try:
        with open(COOKIE_JSON, encoding="utf-8") as f:
            d = {c["name"]: c["value"] for c in json.load(f)}
        return bool(d.get("uid_tt") or d.get("sessionid"))
    except Exception:
        return False


def _load_cookies(ctx):
    try:
        with open(COOKIE_JSON, encoding="utf-8") as f:
            ctx.add_cookies(json.load(f))
    except Exception:
        pass


def _pick_best(media):
    for u in media:
        if any(k in u for k in _PREFERRED):
            return u
    return media[0] if media else ""


def _resolve(short_url):
    """playwright 抓 CDN 直链，返回 media_url。"""
    media, found = [], []
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=CHROME_DATA, headless=True,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
                viewport={"width": 390, "height": 844}, user_agent=MOBILE_UA, locale="zh-CN")
            _load_cookies(ctx)
            page = ctx.new_page()

            def cap(u):
                if "/video/" in u and "douyin.com" in u:
                    vid = _video_id(u)
                    if vid and not found:
                        found.append(f"https://www.douyin.com/video/{vid}")
                if any(k in u for k in _MEDIA) and u not in media:
                    media.append(u)
            page.on("request", lambda r: cap(r.url))
            page.on("response", lambda r: cap(r.url))

            try:
                page.goto(short_url, timeout=25000, wait_until="domcontentloaded")
            except Exception:
                pass
            page.wait_for_timeout(6000)
            if not found:
                cap(page.url)
            if not found:
                try:
                    for vid in re.findall(r'/video/(\d{10,20})', page.content()):
                        found.append(f"https://www.douyin.com/video/{vid}"); break
                except Exception:
                    pass
            if found and not any(any(k in u for k in _PREFERRED) for u in media):
                try:
                    page.goto(found[0], timeout=20000, wait_until="domcontentloaded")
                    page.wait_for_timeout(4000)
                    for _ in range(3):
                        try:
                            page.evaluate("() => { const v=document.querySelector('video'); if(v){v.muted=true; v.play().catch(()=>{});} }")
                        except Exception:
                            pass
                        page.wait_for_timeout(2500)
                        if any(any(k in u for k in _PREFERRED) for u in media):
                            break
                except Exception:
                    pass
            if not any(any(k in u for k in _PREFERRED) for u in media):
                try:
                    for c in re.findall(r'https?:[\\/u002F]*[^"\']*?douyinvod\.com[^"\']*', page.content()):
                        clean = c.replace("\\u002F", "/").replace("\\/", "/").replace("\\u0026", "&")
                        if clean.startswith("http"):
                            media.insert(0, clean); break
                except Exception:
                    pass
            ctx.close()
    except Exception as e:
        print(f"[extract] playwright 异常: {e}", flush=True)
    return _pick_best(media)


def _fetch_text(url):
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        ts = data.get("transcripts", [])
        if ts:
            sents = ts[0].get("sentences", [])
            return "".join(s.get("text", "") for s in sents) if sents else ts[0].get("text", "")
    except Exception as e:
        print(f"[extract] 取转录文本失败: {e}", flush=True)
    return ""


def _transcribe(file_url):
    """百炼 paraformer 异步 ASR——直接走 REST（不用 dashscope SDK：其加密依赖在打包环境会崩）。"""
    key = config.get_key("bailian")  # 运行时取，界面里刚填的 key 立即生效
    if not key:
        print("[extract] 百炼 key 未配置", flush=True)
        return ""
    try:
        req = urllib.request.Request(
            "https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription",
            data=json.dumps({
                "model": BAILIAN_ASR_MODEL,
                "input": {"file_urls": [file_url]},
                "parameters": {"language_hints": ["zh"]},
            }).encode("utf-8"),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                     "X-DashScope-Async": "enable"})
        with urllib.request.urlopen(req, timeout=30) as r:
            task = json.loads(r.read().decode("utf-8"))
        tid = (task.get("output") or {}).get("task_id", "")
    except Exception as e:
        print(f"[extract] ASR 提交失败: {e}", flush=True)
        return ""
    if not tid:
        return ""
    for _ in range(90):
        time.sleep(2)
        try:
            q = urllib.request.Request(f"https://dashscope.aliyuncs.com/api/v1/tasks/{tid}",
                                       headers={"Authorization": f"Bearer {key}"})
            with urllib.request.urlopen(q, timeout=15) as r:
                res = json.loads(r.read().decode("utf-8"))
            st = (res.get("output") or {}).get("task_status", "")
            if st == "SUCCEEDED":
                results = (res.get("output") or {}).get("results", [])
                if results and results[0].get("transcription_url"):
                    return _fetch_text(results[0]["transcription_url"])
                return ""
            if st in ("FAILED", "CANCELED"):
                return ""
        except Exception:
            pass
    return ""


async def extract_from_link(share_url: str) -> dict:
    raw = _extract_url(share_url)
    if not raw.startswith(("http://", "https://")):
        return {"success": False, "message": "请输入有效的视频链接（http/https 开头）或含链接的分享文案"}
    if ("douyin.com" in raw or "v.douyin.com" in raw) and not _is_logged_in():
        return {"success": False, "message": "抖音 cookie 失效，需重新登录抖音更新登录态（母版 chrome_data）。"}
    loop = asyncio.get_running_loop()
    media = await loop.run_in_executor(None, _resolve, raw)
    if not media:
        return {"success": False, "message": "没抓到视频直链：该视频可能已被删除/下架/设为私密，或链接已失效。请换一条有效链接，或直接粘贴文案自查。"}
    text = await loop.run_in_executor(None, _transcribe, media)
    if not text:
        return {"success": False, "message": "ASR 转录为空（可能无人声/直链失效）。"}
    return {"success": True, "data": {"text": text}}
