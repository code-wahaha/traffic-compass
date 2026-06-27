import os, json, tempfile, importlib.util

def load_mod():
    p = os.path.join(os.path.dirname(__file__), "log_record.py")
    spec = importlib.util.spec_from_file_location("log_record", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

def test_append_writes_one_jsonl_line():
    m = load_mod()
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "records.jsonl")
        m.append_record({"title": "测试作品", "predict": "500-3000"}, path)
        m.append_record({"title": "第二条"}, path)
        with open(path, encoding="utf-8") as f:
            lines = [l for l in f.read().splitlines() if l.strip()]
        assert len(lines) == 2, f"应有2行，实际{len(lines)}"
        first = json.loads(lines[0])
        assert first["title"] == "测试作品"
        assert "ts" in first   # 自动补时间戳
    print("OK test_append_writes_one_jsonl_line")

if __name__ == "__main__":
    test_append_writes_one_jsonl_line()
    print("ALL PASS")
