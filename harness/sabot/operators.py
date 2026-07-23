"""Fault operators O1-O6 (SPEC section 4). Pure: input payload is never mutated.

An operator that cannot land its corruption returns verified=False — the runner
excludes that cell as INJECTION_UNVERIFIED. This is the blind-oracle lesson:
verify the channel, never assume the fault arrived."""
from __future__ import annotations
import copy
from collections import namedtuple
from dataclasses import dataclass

Operator = namedtuple("Operator", "id kind fn")


@dataclass(frozen=True)
class OperatorResult:
    payload: dict
    verified: bool


def _substring_swap(payload: dict, spec: dict) -> OperatorResult:
    field, find, replace = spec["field"], spec["find"], spec["replace"]
    text = payload.get(field, "")
    if not isinstance(text, str) or find not in text:
        return OperatorResult(payload=payload, verified=False)
    new = copy.deepcopy(payload)
    new[field] = text.replace(find, replace, 1)
    return OperatorResult(payload=new, verified=True)


def _o5_stale_context(payload: dict, spec: dict) -> OperatorResult:
    field = spec["field"]
    if field not in payload or not isinstance(payload[field], str):
        return OperatorResult(payload=payload, verified=False)
    new = copy.deepcopy(payload)
    new[field] = new[field] + "\n" + spec["stale_content"]
    return OperatorResult(payload=new, verified=True)


def _field_replace(payload: dict, spec: dict, value_key: str,
                   extra: dict | None = None) -> OperatorResult:
    field = spec["field"]
    if field not in payload:
        return OperatorResult(payload=payload, verified=False)
    new = copy.deepcopy(payload)
    new[field] = spec[value_key]
    if extra:
        new.update(extra)
    return OperatorResult(payload=new, verified=True)


def _o2_false_success(payload: dict, spec: dict) -> OperatorResult:
    return _field_replace(payload, spec, "fake_report")


def _o6_silent_noop(payload: dict, spec: dict) -> OperatorResult:
    return _field_replace(payload, spec, "success_response",
                          extra={"__sabot_suppress_side_effect__": True})


def _o4_model_downgrade(payload: dict, spec: dict) -> OperatorResult:
    return OperatorResult(payload={"model_override": spec["downgrade_to"]}, verified=True)


OPERATORS: dict[str, Operator] = {
    "O1": Operator("O1", "payload", _substring_swap),
    "O2": Operator("O2", "payload", _o2_false_success),
    "O3": Operator("O3", "payload", _substring_swap),
    "O4": Operator("O4", "config", _o4_model_downgrade),
    "O5": Operator("O5", "payload", _o5_stale_context),
    "O6": Operator("O6", "payload", _o6_silent_noop),
}


def apply(operator_id: str, payload: dict, spec: dict) -> OperatorResult:
    return OPERATORS[operator_id].fn(payload, spec)
