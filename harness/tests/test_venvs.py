import subprocess, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
CASES = [
    ("langgraph", "import langgraph, langchain_openai; from langgraph.graph import StateGraph; "
                  "from langgraph.prebuilt import ToolNode; from langgraph.types import interrupt, Command"),
    ("crewai",    "from crewai import Agent, Crew, Task, LLM; from crewai.tools import BaseTool; "
                  "from crewai.events import BaseEventListener"),
    ("autogen",   "from autogen_agentchat.teams import RoundRobinGroupChat, MagenticOneGroupChat; "
                  "from autogen_agentchat.conditions import TextMentionTermination; "
                  "from autogen_core.tools import FunctionTool; "
                  "from autogen_ext.models.openai import OpenAIChatCompletionClient"),
]

def test_framework_venvs_import():
    for name, imports in CASES:
        py = ROOT / f".venv-{name}" / "bin" / "python"
        assert py.exists(), f"venv missing: run scripts/setup_venvs.sh ({name})"
        proc = subprocess.run([str(py), "-c", imports], capture_output=True, text=True)
        assert proc.returncode == 0, f"{name} imports failed:\n{proc.stderr}"


# append to tests/test_venvs.py
PINS = {
    "langgraph": {"langgraph": "1.2.9", "langchain-openai": "1.4.0"},
    "crewai": {"crewai": "1.15.5"},
    "autogen": {"autogen-agentchat": "0.7.5", "autogen-core": "0.7.5",
                "autogen-ext": "0.7.5"},
}


def test_framework_venvs_exact_pins():
    for name, pins in PINS.items():
        py = ROOT / f".venv-{name}" / "bin" / "python"
        assert py.exists(), f"venv missing: run scripts/setup_venvs.sh ({name})"
        for dist, want in pins.items():
            proc = subprocess.run(
                [str(py), "-c",
                 f"import importlib.metadata as m; print(m.version('{dist}'))"],
                capture_output=True, text=True)
            assert proc.returncode == 0, f"{name}: {dist} not installed:\n{proc.stderr}"
            got = proc.stdout.strip()
            assert got == want, f"{name}: {dist}=={got}, pinned {want} (SPEC section 8)"
