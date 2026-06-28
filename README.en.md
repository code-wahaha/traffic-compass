# Traffic Compass · 流量罗盘

[中文](./README.md) | **English**

> An **AI compliance check + traffic-potential score** tool for Douyin (Chinese TikTok) videos — run it before you publish.
> Paste your voiceover script → instantly surface policy-violation risks, get minimal-edit fixes, and a niche-weighted "traffic potential" score.

Two things scare every Douyin creator: **getting throttled for a violation**, and **doing all the work but getting no views**. Traffic Compass checks your script before you hit "publish":

- 🛡 **Compliance check**: advertising-law superlatives, absolute claims, off-platform diversion, superstition, exaggerated / anxiety-driven AI claims, and qualification red lines (medical / financial / legal / education)… It judges by context — **it doesn't flag words blindly** (e.g. "my mom is the best person" won't be falsely flagged).
- ✍️ **Minimal-edit suggestions**: it only swaps the offending words and **keeps your spoken tone and rhythm** — it won't rewrite your script into "AI-speak".
- 📈 **Traffic-potential score**: out of 100, weighted for the AI-voiceover niche (**Save value 28% + Opening hook 20%** are the core), and it points out your weakest link.
- 💬 **Follow-up & rewrite**: after the report you can keep asking "why would this get throttled?" or "make my opening stronger".

> ⚠️ Compliance judgments are **reference, not legal advice**; the traffic score is a **script-level** estimate (excluding visuals / cover / delivery pacing / posting time / account weight) and **does not promise view counts**.

---

## Two ways to use

### A. Web app (`webapp/`)
A FastAPI backend + single-file chat frontend; runs locally or on a server. **A single DeepSeek API key is all you need for the core features.**

### B. Claude Code skill (`skill/`)
The review rules packaged as an installable agent skill — in Claude Code, just say "check this Douyin video for me". Rule data lives in `skill/references/`.

---

## Quick start (Web app)

```bash
cd webapp
pip install -r requirements.txt

# Configure your DeepSeek key (either option):
#  1) Copy _data/apikeys.example.json to _data/apikeys.json and fill it in
#  2) Or set the env var DEEPSEEK_KEY=your-key
cp _data/apikeys.example.json _data/apikeys.json   # then edit and add your key

python app.py
# Open http://127.0.0.1:8900
```

The default is **paste-text mode** (no cookies needed). Just paste your script and go.

---

## Configuration

| Variable | Required | Purpose |
|---|---|---|
| `DEEPSEEK_KEY` | ✅ | The review brain (correction + contextual compliance + traffic scoring) |
| `DEEPSEEK_MODEL` | No | Default `deepseek-v4-flash` (fast/cheap); `deepseek-v4-pro` is more accurate but slower |
| `BAILIAN_KEY` | No | Only for "link extraction" (Aliyun Bailian ASR speech-to-text) |
| `DISABLE_EXTRACT` | No | Set to `1` to disable link extraction and use text-only mode (recommended without cookies) |
| `DOUYIN_COOKIE_BASE` | No | Base dir of the Douyin login cookies used by link extraction |

> **Link extraction (Douyin link → text) is an optional advanced feature.** It needs your own Douyin login cookies (placed at `<base>/chrome_data/douyin_cookies.json`) + a Bailian key, plus `dashscope` and `playwright`. Leaving it off does not affect the core script self-check at all.

---

## Project structure

```
traffic-compass/
├── webapp/                  # Web app (FastAPI + single-file frontend)
│   ├── app.py               # Routes: /api/audit /api/chat /api/extract /api/platforms
│   ├── llm.py               # DeepSeek calls (review brain + follow-up/rewrite)
│   ├── audit_skill.md       # ⭐Core: the review system prompt fed to DeepSeek (edit rules here)
│   ├── engine.py            # Deterministic rule engine (banned-word recall + false-positive guard + scoring)
│   ├── extract.py           # Optional: Douyin link → text (playwright + Bailian ASR)
│   ├── config.py            # Key/model config (env first)
│   ├── rules/douyin.json    # Douyin rule pack (add a platform = drop in another json like this)
│   ├── static/index.html    # Dark chat UI (single file)
│   └── _data/apikeys.example.json
├── skill/                   # Claude Code skill version (same ruleset)
│   ├── SKILL.md
│   ├── references/          # Banned words / whitelist / AI-labeling & qualifications / prediction model
│   └── scripts/log_record.py
├── docs/                    # Rule-manual sources, design docs, test cases
├── .env.example
└── LICENSE                  # MIT
```

---

## How it works

```
Voiceover script
  → engine.py code pre-scan (deterministic "must-check list" recall net, so nothing is missed)
  → DeepSeek (with the audit_skill.md review brain): correction + contextual compliance re-check + traffic-potential scoring
  → structured report (corrected text / violation list / highlights / improvements / 7-dimension score)
  → optionally continue via /api/chat to ask follow-ups and rewrite
```

**Two layers of review**: the code engine does "rather over-list" recall (miss nothing), DeepSeek does "read the context" precision (no false kills).

---

## Adding other platforms (e.g. Xiaohongshu)

1. Mirror `webapp/rules/douyin.json` into a `rules/xiaohongshu.json` (set `"enabled": true`).
2. Add that platform's specific rules in `audit_skill.md`.
3. The frontend dropdown picks it up automatically — no code changes needed.

---

## Disclaimer

This project is only a **self-check helper for creators**. Compliance judgments are compiled from public platform rules and **do not constitute legal advice**; platform rules change at any time — always follow the latest official rules. The traffic potential is an **estimate** based on experience and the script dimension only; actual performance depends on many variables (visuals, cover, posting time, account weight, etc.), and **no guarantee is made about views or revenue**.

## License

[MIT](./LICENSE) © code-wahaha
