"""Wave-2 anomaly-first probe adapter — AutoGen. Probe scope is the guardrail config
(MagenticOne) only: it has NO reviewer stage to re-prompt, so the anomaly-first seam is
the task text handed to the orchestrator — the final artifact message must BEGIN with a
FLAGS line. The probe then strips that line off the draft before the frozen artifact
parser runs, so the wave-1 output contract (raw JSON / code / answer shapes) is
untouched. The FLAGS text stays in the trace via the existing agent-msg events and is
adjudicated post-hoc by sabot.probe.scan_trace_flags. The default config is dispatched
unchanged (wave-1 behavior) and is outside the probe scope."""
from __future__ import annotations
from sabot.adapters.autogen_adapter import AutoGenAdapter
from sabot.probe import add_flags_instruction, strip_flags


class ProbeAutoGenAdapter(AutoGenAdapter):
    def _dispatch(self, cell, rec, inj, **kwargs):
        if cell.config == "guardrail":
            orig_build = kwargs["build_worker_desc"]
            orig_parse = kwargs["parse_fn"]
            kwargs["build_worker_desc"] = (
                lambda document, reason: add_flags_instruction(orig_build(document, reason)))
            kwargs["parse_fn"] = lambda draft: orig_parse(strip_flags(draft))
        return super()._dispatch(cell, rec, inj, **kwargs)
