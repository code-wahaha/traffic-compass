"""流量罗盘 · 桌面客户端入口：后台起 FastAPI，前台开原生窗口（pywebview / WebView2）。
打包：pyinstaller 见 打包.md。数据存 exe 旁 _data/。
"""
import os
import socket
import sys
import threading
import time

# 链接提取：playwright 已打进包，直接本地提取。
# 本机/有抖音登录态的机器开箱即用；没有浏览器组件或登录态的机器会收到清晰的降级提示。

if getattr(sys, "frozen", False):
    # 打包后的 playwright 会到包内部找浏览器——指回系统的 ms-playwright 目录
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH",
                          os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright"))
    # windowed 模式下 stdout/stderr 是空句柄：playwright 起子进程会失败，print 也全丢。
    # 重定向到日志文件，一并解决（日志在 exe 旁 _data\app.log，排障就看它）。
    _logdir = os.path.join(os.path.dirname(sys.executable), "_data")
    os.makedirs(_logdir, exist_ok=True)
    _logf = open(os.path.join(_logdir, "app.log"), "a", buffering=1, encoding="utf-8")
    sys.stdout = _logf
    sys.stderr = _logf


def find_port(start=8900):
    for p in range(start, start + 50):
        try:
            with socket.socket() as s:
                s.bind(("127.0.0.1", p))
                return p
        except OSError:
            continue
    raise RuntimeError("找不到可用端口")


PORT = find_port()


def run_server():
    import uvicorn
    from app import app
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")


def wait_ready(timeout=20.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", PORT), 0.2):
                return True
        except OSError:
            time.sleep(0.1)
    return False


if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    if not wait_ready():
        sys.exit("服务启动失败")
    import webview
    webview.create_window("流量罗盘 · 发布前体检 + 发布后对账",
                          f"http://127.0.0.1:{PORT}",
                          width=1000, height=780, min_size=(780, 620))
    webview.start()
