"""Deterministic pass criteria (SPEC section 8, tasks/*.md). Pure string/JSON logic plus
two sandboxed delegations: T3 shells out to the bundled pytest suite; T4 imports the
bundled constraint checker. The public tasks/ dir is the single source of truth —
nothing is vendored, so the assets cannot drift from what is pre-registered."""
from __future__ import annotations
import importlib.util, json, re, subprocess, sys, tempfile
from pathlib import Path

_WS = re.compile(r"\s+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def normalize(s: str) -> str:
    return _WS.sub(" ", s).strip()


def check_t1(output: dict, tasks_dir: Path) -> bool:
    golden = json.loads((tasks_dir / "assets" / "T1-golden.json").read_text())
    return output == golden


def check_t2(summary: str, tasks_dir: Path) -> bool:
    claims = json.loads((tasks_dir / "assets" / "T2-claims.json").read_text())
    text = normalize(summary).lower()
    if any(normalize(req).lower() not in text for req in claims["required_substrings"]):
        return False
    exemptions = [w.lower() for w in claims["forbidden_context_exemption_keywords"]]
    for sentence in _SENTENCE_SPLIT.split(normalize(summary)):
        low = sentence.lower()
        for forb in claims["forbidden_substrings"]:
            if normalize(forb).lower() in low and not any(w in low for w in exemptions):
                return False
    return True


def check_t3(solution_code: str, tasks_dir: Path) -> bool:
    suite = tasks_dir / "assets" / "T3_test_suite.py"
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "solution.py").write_text(solution_code)
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", str(suite), "-q", "--no-header", "-p", "no:cacheprovider"],
            cwd=d, capture_output=True, text=True, timeout=120)
    return proc.returncode == 0


def check_t4(plan_tokens: list, tasks_dir: Path) -> bool:
    spec = importlib.util.spec_from_file_location(
        "t4_check", tasks_dir / "assets" / "T4_constraints_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.check_plan(plan_tokens) == []


def check_t5(answer_obj: dict, tasks_dir: Path) -> bool:
    corpus = normalize((tasks_dir / "assets" / "T5-corpus.md").read_text())
    key = json.loads((tasks_dir / "assets" / "T5-answerkey.json").read_text())
    citations = answer_obj.get("citations")
    answer = answer_obj.get("answer")
    if not isinstance(citations, list) or not citations or not isinstance(answer, str):
        return False
    if any(normalize(q) not in corpus for q in citations):        # verbatim: case-sensitive
        return False
    low = normalize(answer).lower()
    return all(normalize(req).lower() in low
               for req in key["required_answer_substrings"])


_CHECKS = {"T1": check_t1, "T2": check_t2, "T3": check_t3, "T4": check_t4, "T5": check_t5}


def check(task_id: str, output, tasks_dir: Path) -> bool:
    return _CHECKS[task_id](output, tasks_dir)
