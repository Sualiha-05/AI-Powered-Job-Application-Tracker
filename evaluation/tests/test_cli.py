import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "data" / "example"
CLEAN_ENV = {k: v for k, v in os.environ.items() if k not in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY", "LLM_PROVIDER", "LLM_MODEL", "GEMINI_BASE_URL")}


def run(script, *args, stdin="", env=None):
    return subprocess.run([sys.executable, str(ROOT / script), *args], input=stdin, capture_output=True, text=True, env=env or CLEAN_ENV, timeout=120)


def test_run_eval_writes_markdown_and_json(tmp_path):
    r = run("run_eval.py", "--data", str(EXAMPLE), "--split", "all", "--tfidf-thresholds", "0.4,0.6", "--out", str(tmp_path), "--name", "t")
    assert r.returncode == 0 and "Requirement-level agreement" in r.stdout
    data = json.loads((tmp_path / "t.json").read_text())
    assert [x["label"] for x in data["runs"]] == ["keyword", "tfidf@0.4", "tfidf@0.6"] and (tmp_path / "t.md").exists()


def test_test_split_prints_the_honesty_reminder(tmp_path):
    r = run("run_eval.py", "--data", str(EXAMPLE), "--out", str(tmp_path))
    assert r.returncode == 0 and "TEST split" in r.stdout


def test_missing_or_broken_data_gives_a_clear_error(tmp_path):
    r = run("run_eval.py", "--data", str(tmp_path / "nope"))
    assert r.returncode == 1 and "label.py init" in r.stdout
    (tmp_path / "labels.json").write_text(json.dumps({"postings": {}, "resumes": {}, "pairs": []}))
    assert "No labeled pairs" in run("run_eval.py", "--data", str(tmp_path)).stdout


def test_ai_matcher_needs_a_key_and_an_explicit_yes(tmp_path):
    no_key = run("run_eval.py", "--data", str(EXAMPLE), "--llm", "--yes", "--out", str(tmp_path))
    assert no_key.returncode == 2 and "No AI provider is configured" in no_key.stdout
    env = dict(CLEAN_ENV, GEMINI_API_KEY="fake", GEMINI_BASE_URL="http://127.0.0.1:9")      # nothing listens there
    not_confirmed = run("run_eval.py", "--data", str(EXAMPLE), "--llm", "--out", str(tmp_path), env=env)
    assert not_confirmed.returncode == 2 and "add --yes" in not_confirmed.stdout and "may use what you send" in not_confirmed.stdout


def test_ai_failures_are_reported_and_the_run_stops_early(tmp_path):
    env = dict(CLEAN_ENV, GEMINI_API_KEY="fake", GEMINI_BASE_URL="http://127.0.0.1:9", LLM_MAX_RETRIES="0", LLM_TIMEOUT_SECONDS="2")
    r = run("run_eval.py", "--data", str(EXAMPLE), "--split", "all", "--llm", "--llm-runs", "1", "--yes", "--sleep", "0", "--out", str(tmp_path), env=env)
    assert r.returncode == 0 and "stopping llm" in r.stdout and "Incomplete runs" in r.stdout


def test_bias_audit_runs_and_reports(tmp_path):
    r = run("bias_audit.py", "--data", str(EXAMPLE), "--max-pairs", "3", "--names-per-group", "1", "--out", str(tmp_path), "--name", "b")
    assert r.returncode == 0 and "Name-swap bias audit" in r.stdout and "labels fingerprint" in r.stdout and json.loads((tmp_path / "b.json").read_text())["meta"]["labels_hash"]


def test_scripted_session_from_empty_folder_to_scores(tmp_path):
    d = tmp_path / "mine"
    assert run("label.py", "--data", str(d), "init").returncode == 0
    (d / "postings" / "job-a.txt").write_text("Role\nRequirements:\n- Python\n- Docker\nNice to have: Terraform\n")
    for name, body in {"r1": "Alex Test\nBuilt APIs in Python\nShipped with Docker\n", "r2": "Blair Test\nWrote docs\n", "r3": "Casey Test\nLearning Python\n"}.items():
        (d / "resumes" / f"{name}.txt").write_text(body)
    assert "job-a" in run("label.py", "--data", str(d), "sync").stdout
    run("label.py", "--data", str(d), "requirements", "job-a", stdin="Python | python\nDocker | docker\nTerraform | terraform | preferred\n\n")
    run("label.py", "--data", str(d), "tags", "r1", "strong")
    out = run("label.py", "--data", str(d), "pairs", "job-a", stdin="y\n2\ny\n3\nn\n" + "n\n" * 6)   # r1: python y (line 2), docker y (line 3), terraform n; r2 and r3: three n each
    assert out.returncode == 0, out.stdout + out.stderr
    assert "OK: no errors" in run("label.py", "--data", str(d), "check").stdout
    scored = run("run_eval.py", "--data", str(d), "--split", "all", "--out", str(tmp_path / "res"), "--name", "mine")
    assert scored.returncode == 0 and "3 resume/posting pairs" in scored.stdout
