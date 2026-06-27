"""webapp 配置：API key + 模型。

key 读取优先级：环境变量 > _data/apikeys.json（后者不入 git，见 apikeys.example.json）。
"""
import os, json

BASE = os.path.dirname(os.path.abspath(__file__))


def _keys():
    p = os.path.join(BASE, "_data", "apikeys.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}


_K = _keys()

# 百炼（阿里云 DashScope）—— 链接提取的语音转写 ASR（可选）
BAILIAN_KEY = os.getenv("BAILIAN_KEY", _K.get("bailian", ""))
BAILIAN_ASR_MODEL = "paraformer-v2"

# DeepSeek —— 审核大脑：纠错 / 语境违规判断 / 流量潜力评分（核心，必填）
DEEPSEEK_KEY = os.getenv("DEEPSEEK_KEY", _K.get("deepseek", ""))
DEEPSEEK_HOST = "api.deepseek.com"
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")  # 非思考模式；deepseek-v4-pro 为思考模式

# 链接提取（可选）依赖：抖音登录态 cookie 的所在基目录，其下需有 chrome_data/douyin_cookies.json。
# 不配则默认 webapp/_data；没有 cookie 时链接提取不可用，但文字粘贴模式不受影响。
COOKIE_BASE_DIR = os.getenv("DOUYIN_COOKIE_BASE", os.path.join(BASE, "_data"))
