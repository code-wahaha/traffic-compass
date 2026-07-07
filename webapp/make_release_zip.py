# -*- coding: utf-8 -*-
"""流量罗盘发行包压制:dist_release/流量罗盘 + 使用说明 → 桌面 zip。
剔除一切隐私(_data/钥匙/抖音登录/账本/日志),压完自检再报告。"""
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "dist_release", "流量罗盘")
DOC = os.path.join(HERE, "notice", "使用说明.txt")
OUT = os.path.join(os.path.expanduser("~"), "Desktop", "流量罗盘安装包.zip")

FORBID = {"_data", "__pycache__", "douyin_cookies.json", "apikeys.json",
          "compass.db", "app.log", "chrome_data", "records"}


def banned(rel):
    return any(p in FORBID for p in rel.replace("\\", "/").split("/"))


def main():
    assert os.path.isdir(SRC), "先跑 PyInstaller,没找到 " + SRC
    n = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.write(DOC, "使用说明.txt")
        for root, dirs, files in os.walk(SRC):
            dirs[:] = [d for d in dirs if d not in FORBID]
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.join("流量罗盘", os.path.relpath(full, SRC))
                if banned(rel):
                    continue
                z.write(full, rel)
                n += 1

    bad = []
    with zipfile.ZipFile(OUT) as z:
        for name in z.namelist():
            low = name.lower()
            if any(k in low for k in ("apikeys.json", "douyin_cookies", "compass.db",
                                      "app.log", "_data/", "chrome_data")):
                bad.append(name)
    print("打进文件数:", n)
    print("包大小MB:", round(os.path.getsize(OUT) / 1048576, 1))
    print("隐私自检:", "干净" if not bad else "发现问题:" + ";".join(bad[:5]))
    print("产物:", OUT)


if __name__ == "__main__":
    main()
