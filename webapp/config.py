"""webapp 配置：API key + 模型。key 从 _data/apikeys.json 读取（不入 git）。"""
import os, sys, json

BASE = os.path.dirname(os.path.abspath(__file__))
# 打包成 exe 后，可写数据放在 exe 旁边（用户看得见、好备份）；开发模式放 webapp/_data
APP_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else BASE
DATA_DIR = os.path.join(APP_DIR, "_data")


def _keys():
    p = os.path.join(DATA_DIR, "apikeys.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_key(name: str) -> str:
    env = {"deepseek": "DEEPSEEK_KEY", "bailian": "BAILIAN_KEY"}.get(name, "")
    return (os.getenv(env) or _keys().get(name, "")).strip()


def save_key(name: str, value: str):
    os.makedirs(DATA_DIR, exist_ok=True)
    k = _keys(); k[name] = value.strip()
    with open(os.path.join(DATA_DIR, "apikeys.json"), "w", encoding="utf-8") as f:
        json.dump(k, f, ensure_ascii=False, indent=1)


_K = _keys()

# 百炼（阿里云 DashScope）—— ASR
BAILIAN_KEY = os.getenv("BAILIAN_KEY", _K.get("bailian", ""))
BAILIAN_ASR_MODEL = "paraformer-v2"

# DeepSeek —— 语境判断 / 改写建议 / 报告润色
DEEPSEEK_KEY = os.getenv("DEEPSEEK_KEY", _K.get("deepseek", ""))
DEEPSEEK_HOST = "api.deepseek.com"
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")  # 非思考模式；deepseek-v4-pro 为思考模式

# 复用 Pixlix 母版的抖音解析（playwright + cookie）
PIXLIX_MUBAN_DIR = r"F:\协作区\Pixlix_母版"
