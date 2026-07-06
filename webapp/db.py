"""流量罗盘 v2 —— SQLite 数据层（账号档案 / 作品闭环 / 校准日志）。
盲预测三原则：预测写入即锁定(触发器强制)、复盘只追加、校准调整必留痕。
"""
import os, json, sqlite3, hashlib, datetime

from config import DATA_DIR
DB_PATH = os.path.join(DATA_DIR, "compass.db")

# 比率桶：相对「账号基准播放(中位数×校准系数)」的倍数区间
BUCKETS = ["<0.3x", "0.3-1x", "1-3x", "3-10x", ">10x"]
BUCKET_BOUNDS = {  # (下界倍数, 上界倍数, 中枢倍数)
    "<0.3x":  (0.0, 0.3, 0.15),
    "0.3-1x": (0.3, 1.0, 0.6),
    "1-3x":   (1.0, 3.0, 1.7),
    "3-10x":  (3.0, 10.0, 5.5),
    ">10x":   (10.0, 10**9, 15.0),
}
DEADBAND = 0.20        # 偏差 ±20% 内算"命中中枢附近"，不计入连偏
STREAK_TRIGGER = 3     # 连续同向偏差 3 次触发校准
FACTOR_STEP = 0.15     # 每次校准系数调 ±15%


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c


def init():
    c = conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS accounts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      platform TEXT DEFAULT 'douyin',
      track TEXT DEFAULT '',
      baseline_median INTEGER NOT NULL,
      calib_factor REAL DEFAULT 1.0,
      calib_samples INTEGER DEFAULT 0,
      bias_streak INTEGER DEFAULT 0,
      created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS works (
      id TEXT PRIMARY KEY,
      account_id INTEGER REFERENCES accounts(id),
      text_snapshot TEXT NOT NULL,
      audit_json TEXT,
      status TEXT NOT NULL DEFAULT 'predicted',
      pred_bucket TEXT NOT NULL,
      pred_dist TEXT NOT NULL,
      pred_center INTEGER NOT NULL,
      basis_plays INTEGER NOT NULL,
      pred_reason TEXT,
      pred_confidence TEXT,
      rubric_version TEXT DEFAULT 'v1',
      predicted_at TEXT NOT NULL,
      published_at TEXT, video_url TEXT,
      actual_plays INTEGER, actual_likes INTEGER,
      actual_comments INTEGER, actual_shares INTEGER,
      retro_at TEXT, retro_source TEXT,
      deviation_pct REAL, hit_bucket INTEGER
    );
    CREATE TABLE IF NOT EXISTS calib_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      account_id INTEGER, ts TEXT,
      old_factor REAL, new_factor REAL, trigger_reason TEXT
    );
    CREATE TABLE IF NOT EXISTS chat_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      frame TEXT NOT NULL,
      role TEXT NOT NULL,
      html TEXT NOT NULL,
      ts TEXT
    );
    -- 盲预测锁：预测字段一旦写入禁止任何 UPDATE（复盘只写 actual_/retro_/status/published 字段）
    CREATE TRIGGER IF NOT EXISTS lock_prediction
    BEFORE UPDATE OF pred_bucket, pred_dist, pred_center, basis_plays,
                     pred_reason, predicted_at, text_snapshot ON works
    BEGIN
      SELECT RAISE(ABORT, 'prediction is immutable');
    END;
    """)
    c.commit(); c.close()


# ---------- accounts ----------

def create_account(name, platform, track, baseline_median):
    c = conn()
    cur = c.execute(
        "INSERT INTO accounts(name,platform,track,baseline_median,created_at) VALUES(?,?,?,?,?)",
        (name, platform, track, int(baseline_median), _now()))
    c.commit(); aid = cur.lastrowid; c.close()
    return aid


def list_accounts():
    c = conn()
    rows = [dict(r) for r in c.execute("SELECT * FROM accounts ORDER BY id")]
    c.close(); return rows


def get_account(aid):
    c = conn()
    r = c.execute("SELECT * FROM accounts WHERE id=?", (aid,)).fetchone()
    c.close(); return dict(r) if r else None


def confidence_label(samples: int) -> str:
    if samples >= 10: return "🟢 已校准"
    if samples >= 3:  return "🟡 校准中"
    return "🔴 冷启动"


# ---------- works ----------

def create_work(account_id, text, audit_json, bucket, dist: dict, reason):
    acc = get_account(account_id)
    if not acc:
        raise ValueError("账号不存在")
    if bucket not in BUCKETS:
        raise ValueError(f"非法 bucket: {bucket}")
    total = sum(dist.get(b, 0) for b in BUCKETS)
    if not (95 <= total <= 105):
        raise ValueError(f"概率分布加和={total}，必须≈100")
    wid = hashlib.sha256((text + _now()).encode("utf-8")).hexdigest()[:12]
    basis = int(acc["baseline_median"] * acc["calib_factor"])
    center = int(BUCKET_BOUNDS[bucket][2] * basis)
    c = conn()
    c.execute("""INSERT INTO works(id,account_id,text_snapshot,audit_json,status,
        pred_bucket,pred_dist,pred_center,basis_plays,pred_reason,pred_confidence,predicted_at)
        VALUES(?,?,?,?,'predicted',?,?,?,?,?,?,?)""",
        (wid, account_id, text, json.dumps(audit_json or {}, ensure_ascii=False),
         bucket, json.dumps(dist, ensure_ascii=False), center, basis, reason,
         confidence_label(acc["calib_samples"]), _now()))
    c.commit(); c.close()
    return get_work(wid)


def get_work(wid):
    c = conn()
    r = c.execute("SELECT * FROM works WHERE id=?", (wid,)).fetchone()
    c.close()
    if not r: return None
    d = dict(r)
    d["pred_dist"] = json.loads(d["pred_dist"])
    return d


def mark_published(wid, video_url=""):
    c = conn()
    n = c.execute("""UPDATE works SET status='published', published_at=?, video_url=?
                     WHERE id=? AND status='predicted'""", (_now(), video_url, wid)).rowcount
    c.commit(); c.close()
    if not n:
        raise ValueError("作品不存在或状态不允许（只能对未发布的预测登记发布）")
    return get_work(wid)


def list_works(account_id=None):
    c = conn()
    q = "SELECT * FROM works" + (" WHERE account_id=?" if account_id else "") + " ORDER BY predicted_at DESC"
    rows = [dict(r) for r in (c.execute(q, (account_id,)) if account_id else c.execute(q))]
    c.close()
    now = datetime.datetime.now()
    out = {"predicted": [], "retro_due": [], "published": [], "retroed": []}
    for d in rows:
        d["pred_dist"] = json.loads(d["pred_dist"])
        if d["status"] == "published" and d["published_at"]:
            due = datetime.datetime.strptime(d["published_at"], "%Y-%m-%d %H:%M:%S") + datetime.timedelta(days=3)
            d["retro_due_at"] = due.strftime("%Y-%m-%d %H:%M")
            out["retro_due" if now >= due else "published"].append(d)
        else:
            out[d["status"]].append(d)
    return out


# ---------- retro + 校准 ----------

def retro(wid, plays, likes=None, comments=None, shares=None, source="manual"):
    w = get_work(wid)
    if not w: raise ValueError("作品不存在")
    if w["status"] == "retroed": raise ValueError("该作品已复盘（复盘只能一次，只追加不修改）")
    if w["status"] == "predicted": raise ValueError("请先登记发布，再复盘")
    plays = int(plays)
    dev = (plays - w["pred_center"]) / max(w["pred_center"], 1)
    lo, hi, _ = BUCKET_BOUNDS[w["pred_bucket"]]
    ratio = plays / max(w["basis_plays"], 1)
    hit = 1 if lo <= ratio < hi else 0
    c = conn()
    c.execute("""UPDATE works SET status='retroed', actual_plays=?, actual_likes=?,
        actual_comments=?, actual_shares=?, retro_at=?, retro_source=?, deviation_pct=?, hit_bucket=?
        WHERE id=?""",
        (plays, likes, comments, shares, _now(), source, round(dev, 4), hit, wid))
    # 校准：偏差超出死区才计连偏
    acc = get_account(w["account_id"])
    streak = acc["bias_streak"]
    calib_event = None
    if abs(dev) <= DEADBAND:
        streak = 0
    else:
        step = 1 if dev > 0 else -1
        streak = streak + step if streak * step > 0 or streak == 0 else step
        if abs(streak) >= STREAK_TRIGGER:
            old = acc["calib_factor"]
            new = round(old * (1 + FACTOR_STEP * (1 if streak > 0 else -1)), 4)
            c.execute("INSERT INTO calib_log(account_id,ts,old_factor,new_factor,trigger_reason) VALUES(?,?,?,?,?)",
                      (acc["id"], _now(), old, new, f"连续{abs(streak)}次同向偏差({'偏低' if streak>0 else '偏高'})"))
            c.execute("UPDATE accounts SET calib_factor=? WHERE id=?", (new, acc["id"]))
            calib_event = {"old_factor": old, "new_factor": new,
                           "note": f"账号基准已{'上调' if streak>0 else '下调'} {int(FACTOR_STEP*100)}%（连续{abs(streak)}次预测{'偏低' if streak>0 else '偏高'}）"}
            streak = 0
    c.execute("UPDATE accounts SET bias_streak=?, calib_samples=calib_samples+1 WHERE id=?",
              (streak, w["account_id"]))
    c.commit(); c.close()
    out = get_work(wid)
    out["calib_event"] = calib_event
    return out


def report(wid):
    w = get_work(wid)
    if not w: return None
    acc = get_account(w["account_id"])
    c = conn()
    r = c.execute("""SELECT COUNT(*) n, SUM(hit_bucket) hits FROM works
                     WHERE account_id=? AND status='retroed'""", (w["account_id"],)).fetchone()
    c.close()
    w["account"] = {"name": acc["name"], "calib_factor": acc["calib_factor"],
                    "calib_samples": acc["calib_samples"],
                    "confidence": confidence_label(acc["calib_samples"]),
                    "hit_rate": f"{r['hits'] or 0}/{r['n'] or 0}"}
    return w


# ---------- 导出 ----------

def export_rows():
    c = conn()
    rows = [dict(r) for r in c.execute(
        "SELECT w.*, a.name account_name FROM works w LEFT JOIN accounts a ON a.id=w.account_id ORDER BY w.predicted_at")]
    c.close(); return rows


def export_full():
    c = conn()
    out = {t: [dict(r) for r in c.execute(f"SELECT * FROM {t}")]
           for t in ("accounts", "works", "calib_log")}
    c.close(); return out


# ---------- 对话记忆 ----------

def add_msg(frame, role, html):
    c = conn()
    c.execute("INSERT INTO chat_log(frame,role,html,ts) VALUES(?,?,?,?)",
              (frame, role, html[:200000], _now()))
    c.commit(); c.close()


def get_msgs(frame):
    c = conn()
    rows = [{"role": r["role"], "html": r["html"]} for r in
            c.execute("SELECT role,html FROM chat_log WHERE frame=? ORDER BY id", (frame,))]
    c.close(); return rows


def clear_msgs(frame):
    c = conn()
    c.execute("DELETE FROM chat_log WHERE frame=?", (frame,))
    c.commit(); c.close()


def reset_all():
    """清空全部记录：作品/账号/校准/对话。预测锁只防篡改，不防用户自己整体清零。"""
    c = conn()
    for t in ("works", "accounts", "calib_log", "chat_log"):
        c.execute(f"DELETE FROM {t}")
    c.commit(); c.close()


init()
