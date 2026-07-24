"""Offline checks that the probe adapters change EXACTLY the anomaly-first seam and
nothing else: CrewAI reviewer prompts gain the addendum (T4 untouched); Magentic task
text gains the addendum and the artifact parser sees a FLAGS-stripped draft. Framework
imports are venv-gated like the wave-1 adapter suites."""
import pytest

from sabot.probe import CREWAI_ADDENDUM, MAGENTIC_ADDENDUM
from sabot.runner import Cell


class TestProbeCrewAI:
    @pytest.fixture(autouse=True)
    def _requires_crewai(self):
        pytest.importorskip("crewai")

    def test_reviewer_sys_gains_addendum_in_scope(self):
        from sabot.adapters.crewai_adapter import CrewAIAdapter
        from sabot.adapters.probe_crewai import ProbeCrewAIAdapter
        for t in ("T1", "T2", "T3", "T5"):
            probe = getattr(ProbeCrewAIAdapter, f"_{t}_REVIEWER_SYS")
            frozen = getattr(CrewAIAdapter, f"_{t}_REVIEWER_SYS")
            assert probe == frozen + CREWAI_ADDENDUM
        assert ProbeCrewAIAdapter._T4_REVIEWER_SYS == CrewAIAdapter._T4_REVIEWER_SYS

    def test_reviewer_desc_builder_carries_addendum(self):
        # the desc builders resolve the prompt via cls/self, so the subclass override
        # must propagate into the composed reviewer task description
        from sabot.adapters.probe_crewai import ProbeCrewAIAdapter
        desc = ProbeCrewAIAdapter._t1_reviewer_desc("SRC", "DRAFT", "NOTE")
        assert CREWAI_ADDENDUM in desc

    def test_worker_prompts_untouched(self):
        from sabot.adapters.crewai_adapter import CrewAIAdapter
        from sabot.adapters.probe_crewai import ProbeCrewAIAdapter
        assert ProbeCrewAIAdapter._T1_EXTRACTOR_SYS == CrewAIAdapter._T1_EXTRACTOR_SYS


class TestProbeAutoGen:
    @pytest.fixture(autouse=True)
    def _requires_autogen(self):
        pytest.importorskip("autogen_agentchat")

    def _capture_dispatch(self, config):
        from sabot.adapters.probe_autogen import ProbeAutoGenAdapter
        captured = {}

        class Capturing(ProbeAutoGenAdapter):
            def _run_guardrail(self, cell, rec, inj, **kwargs):   # stub, sync on purpose
                captured.update(kwargs)
                return "guardrail-ran"

            def _run_default(self, cell, rec, inj, **kwargs):
                captured.update(kwargs)
                return "default-ran"

        adapter = Capturing(tasks_dir=None)
        cell = Cell(framework="autogen", task="T1", config=config,
                    operator=None, operator_spec=None, seed=11)
        ret = adapter._dispatch(
            cell, rec=None, inj=None,
            build_worker_desc=lambda document, reason: f"TASK({document},{reason})",
            build_reviewer_desc=lambda *a: "rdesc", reviewer_sys="rsys",
            parse_fn=lambda draft: ("parsed", draft),
            task_id="T1", agent_name="extractor", source_text="src", worker_sys="wsys",
            precheck_fn=lambda d: "ok", empty_default=None, write_tool="write")
        return ret, captured

    def test_guardrail_task_text_gains_addendum(self):
        ret, captured = self._capture_dispatch("guardrail")
        assert ret == "guardrail-ran"
        built = captured["build_worker_desc"]("DOC", None)
        assert built == "TASK(DOC,None)" + MAGENTIC_ADDENDUM

    def test_guardrail_parser_sees_flags_stripped_draft(self):
        _, captured = self._capture_dispatch("guardrail")
        parsed, seen = captured["parse_fn"]('FLAGS: 74.1 mismatch\n{"unit_id": "X"}')
        assert parsed == "parsed"
        assert seen == '\n{"unit_id": "X"}'

    def test_default_config_is_untouched(self):
        ret, captured = self._capture_dispatch("default")
        assert ret == "default-ran"
        assert captured["build_worker_desc"]("DOC", None) == "TASK(DOC,None)"
        _, seen = captured["parse_fn"]("FLAGS: x\nbody")
        assert seen == "FLAGS: x\nbody"
