"""Normalized trace: the only currency between adapters, scorer, and judge."""
from __future__ import annotations
import json
from dataclasses import dataclass, field

SCHEMA_VERSION = 1
EVENT_KINDS = ("agent-msg", "tool-call", "guardrail-event", "verdict")

@dataclass(frozen=True)
class Event:
    kind: str
    agent: str
    payload: dict
    seq: int

    def __post_init__(self):
        if self.kind not in EVENT_KINDS:
            raise ValueError(f"unknown event kind: {self.kind}")

    def to_dict(self) -> dict:
        return {"kind": self.kind, "agent": self.agent,
                "payload": self.payload, "seq": self.seq}

    @classmethod
    def from_dict(cls, d: dict) -> "Event":
        return cls(kind=d["kind"], agent=d["agent"],
                   payload=d["payload"], seq=d["seq"])

@dataclass
class Trace:
    run_id: str
    framework: str
    task: str
    config: str
    operator: str | None
    seed: int
    events: list[Event] = field(default_factory=list)

    def add(self, event: Event) -> None:
        if self.events and event.seq <= self.events[-1].seq:
            raise ValueError(
                f"seq {event.seq} not after {self.events[-1].seq}")
        self.events.append(event)

    def to_json(self) -> str:
        return json.dumps({
            "schema_version": SCHEMA_VERSION, "run_id": self.run_id,
            "framework": self.framework, "task": self.task,
            "config": self.config, "operator": self.operator,
            "seed": self.seed,
            "events": [e.to_dict() for e in self.events],
        }, sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> "Trace":
        d = json.loads(s)
        t = cls(run_id=d["run_id"], framework=d["framework"], task=d["task"],
                config=d["config"], operator=d["operator"], seed=d["seed"])
        for ed in d["events"]:
            t.add(Event.from_dict(ed))
        return t
