#!/bin/bash
# Three isolated framework venvs. CrewAI/LangGraph/AutoGen dependency trees conflict;
# isolation is the defensible reproducibility story (pins published with results).
set -euo pipefail
cd "$(dirname "$0")/.."

make_venv () {
  local name="$1"; shift
  python3.11 -m venv ".venv-${name}" 2>/dev/null || python3 -m venv ".venv-${name}"
  ".venv-${name}/bin/python" -m pip install -q --upgrade pip
  ".venv-${name}/bin/python" -m pip install -q -e .
  ".venv-${name}/bin/python" -m pip install -q "$@"
}

make_venv langgraph "langgraph==1.2.9" "langchain-openai==1.4.0"
make_venv crewai    "crewai==1.15.5"
make_venv autogen   "autogen-agentchat==0.7.5" "autogen-core==0.7.5" "autogen-ext[openai]==0.7.5"
echo "OK: all three venvs built"
