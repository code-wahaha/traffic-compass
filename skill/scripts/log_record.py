"""把一次自查记录追加成 jsonl 的一行（UTF-8）。无第三方依赖。

用法（命令行）：
    python log_record.py '<json字符串>'
被 SKILL.md 调用时，传入本次作品的元数据 + 自查命中摘要 + 预测区间。
真实播放量列留空，待事后回填，用于 v2/v3 校准。
"""
import os, json, sys
from datetime import datetime

# 默认写到仓库根目录 records/records.jsonl（本脚本在 skill/scripts/ 下，往上三级是仓库根）
DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "records", "records.jsonl")


def append_record(record: dict, path: str = DEFAULT_PATH) -> None:
    """把一条记录追加成 jsonl 的一行；自动补时间戳 ts。"""
    rec = dict(record)
    rec.setdefault("ts", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    # 预留回填列
    rec.setdefault("real_views", None)
    rec.setdefault("real_completion", None)
    rec.setdefault("real_collect", None)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    data = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    append_record(data)
    print("recorded")
