#!/usr/bin/env python
"""Validate one third-party scoreboard submission (see SUBMITTING.md).

A submission is ONE scoreboard row: one framework, at one config, on one pipeline
model, over the repo's five tasks x six operators x at least five replicates, plus
the per-(task, replicate) clean baselines, shipped as raw traces in trace schema v1.

    python scripts/validate_submission.py ../submissions/<slug> [--json]

Exit 0 when every check passes, non-zero with findings otherwise.

Two rules govern this script.

**It never forks scoring logic.** Every number it reports is produced by the
committed scorers, imported:

  * exclusion + `wave1_mapping` + `recovered` -> `sabot.runner.run_cell`, which is
    the frozen `sabot.score.score` path (SPEC sections 2-3), so exclusion precedence
    (`RUN_ERROR > BASELINE_FAIL > INJECTION_UNVERIFIED`) is checked by recomputing
    it rather than by re-stating it;
  * trace schema v1 -> `sabot.serde.run_result_from_json` / `sabot.trace.Trace`,
    which is the same parse the harness itself writes and reads;
  * the anchored-FLAGS surface -> `sabot.wave2.scan_trace_flags_v2` (SPEC 10.3-10.4);
  * the strict injection-evidence floor -> `sabot.strict.strict_detected` (v0.2.1);
  * group totals -> `scripts/score_wave2.aggregate`, loaded by path, so a submitted
    row is counted by the same function that counts the author-run scoreboard.

**Everything it checks is deterministic.** The soft-tier LLM judge (SPEC section 6)
is out of scope for submissions and this script has no judge path: a third party
cannot replicate a judge run, so no judge-derived number can be recomputed offline
from a submitted corpus. Every claimed number in a submitted row must be
reproducible by this repo's committed scorers on the shipped traces, to the digit.

v0.2.1 rules apply to submissions, prospectively (SPEC amendment log, v0.2.1):
O4 is scored on the mapping surface only -- the generic anchored-FLAGS surface is
excluded for O4 -- and the strict floor plus the clean-baseline false-anchor base
rate are published alongside the headline, never on their own.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import re
import sys

HARNESS = pathlib.Path(__file__).resolve().parents[1]
REPO = HARNESS.parent
sys.path.insert(0, str(HARNESS))

from sabot.runner import Cell, run_cell                             # noqa: E402
from sabot.score import EXCLUSION_CODES                             # noqa: E402
from sabot.serde import run_result_from_json                        # noqa: E402
from sabot.strict import injection_only_anchors, strict_detected    # noqa: E402
from sabot.trace import SCHEMA_VERSION                              # noqa: E402
from sabot.wave2 import scan_trace_flags_v2                         # noqa: E402

TASKS = ("T1", "T2", "T3", "T4", "T5")
OPERATORS = ("O1", "O2", "O3", "O4", "O5", "O6")
MIN_REPLICATES = 5
MANIFEST_SCHEMA = "sabot-submission/1"
PROTOCOLS = ("wave1-mapping", "wave2-union")

# SPEC v0.2.1 section 10.3: the O4 symptom-value anchors fire on clean baselines at
# the faulted rate, so from v0.2.1 onward O4 detection is mapping-surface only.
FLAGS_SURFACE_EXCLUDED_OPERATORS = frozenset({"O4"})

# Claimed counters every submission must publish, whatever its protocol.
BASE_CLAIMS = ("wave1_mapping", "reacted", "recovered", "strict_floor",
               "clean_baseline_false_anchor")
# Claimed counters a wave-2 (anchored-FLAGS) submission must publish as well.
UNION_CLAIMS = ("flags_anchored", "union")

_EXACT_PIN = re.compile(r"^[0-9][0-9A-Za-z.\-+!]*$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_URL = re.compile(r"^https://\S+$")


# --------------------------------------------------------------------------------
# findings
# --------------------------------------------------------------------------------

class Report:
    """An ordered list of finding lines. FAIL is the only level that fails the run."""

    def __init__(self) -> None:
        self.findings = []

    def _add(self, level, code, message):
        self.findings.append({"level": level, "code": code, "message": message})

    def fail(self, code, message):
        self._add("FAIL", code, message)

    def warn(self, code, message):
        self._add("WARN", code, message)

    def info(self, code, message):
        self._add("INFO", code, message)

    @property
    def failed(self):
        return any(f["level"] == "FAIL" for f in self.findings)

    def render(self):
        width = max([len(f["code"]) for f in self.findings] + [4])
        return "\n".join("{:<4}  {:<{w}}  {}".format(f["level"], f["code"],
                                                     f["message"], w=width)
                         for f in self.findings)


# --------------------------------------------------------------------------------
# committed-scorer reuse
# --------------------------------------------------------------------------------

def load_score_wave2():
    """The committed wave-2 scorer, loaded by path so its `aggregate` counts a
    submitted row exactly as it counts the author-run scoreboard."""
    path = HARNESS / "scripts" / "score_wave2.py"
    spec = importlib.util.spec_from_file_location("sabot_score_wave2", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------------
# manifest
# --------------------------------------------------------------------------------

def _spec_version_in_repo():
    """The SPEC revision this checkout publishes, or None if SPEC.md is absent."""
    spec_md = REPO / "SPEC.md"
    if not spec_md.is_file():
        return None
    m = re.search(r"Specification\s+(v\d+\.\d+\.\d+)", spec_md.read_text())
    return m.group(1) if m else None


def _is_str(value):
    return isinstance(value, str) and bool(value.strip())


def _counter(value):
    """A claimed counter is {"hits": int, "n": int} with 0 <= hits <= n."""
    return (isinstance(value, dict)
            and isinstance(value.get("hits"), int)
            and isinstance(value.get("n"), int)
            and not isinstance(value.get("hits"), bool)
            and not isinstance(value.get("n"), bool)
            and 0 <= value["hits"] <= value["n"])


def check_manifest(manifest, report):
    """Schema, version pins, provenance, replicate honesty. Returns True if the
    manifest is structurally usable enough to keep going."""
    if manifest.get("schema") != MANIFEST_SCHEMA:
        report.fail("MANIFEST_SCHEMA",
                    "manifest 'schema' must be {!r}, got {!r}".format(
                        MANIFEST_SCHEMA, manifest.get("schema")))
        return False

    usable = True

    for key in ("slug", "submitted", "sabot_commit"):
        if not _is_str(manifest.get(key)):
            report.fail("MANIFEST_FIELD", "missing or empty manifest field: " + key)

    # Provenance separation is not negotiable: a submitted row is labelled
    # third-party and is rendered in its own table, never pooled into the
    # author-run medians or the headline.
    if manifest.get("provenance") != "third-party":
        report.fail("PROVENANCE",
                    "manifest 'provenance' must be the literal string 'third-party' "
                    "(submitted rows are never pooled into the author-run medians)")
    else:
        report.info("PROVENANCE",
                    "row labelled third-party; it publishes in the separate "
                    "third-party table, never in the author-run medians or headline")

    repo_spec = _spec_version_in_repo()
    declared_spec = manifest.get("spec_version")
    if not _is_str(declared_spec):
        report.fail("SPEC_VERSION", "missing manifest field: spec_version")
    elif repo_spec is None:
        report.warn("SPEC_VERSION",
                    "SPEC.md not found next to harness/; cannot check that "
                    "{!r} is a tagged revision".format(declared_spec))
    elif declared_spec != repo_spec:
        report.fail("SPEC_VERSION",
                    "spec_version {!r} is not this checkout's SPEC revision {!r}; a "
                    "row may only cite a tagged revision".format(declared_spec, repo_spec))
    else:
        report.info("SPEC_VERSION", "scored against SPEC " + declared_spec)

    protocol = manifest.get("protocol")
    if protocol not in PROTOCOLS:
        report.fail("PROTOCOL",
                    "manifest 'protocol' must be one of {}, got {!r}".format(
                        list(PROTOCOLS), protocol))
        usable = False

    framework = manifest.get("framework")
    if not isinstance(framework, dict):
        report.fail("PINS", "manifest 'framework' must be an object")
        usable = False
    else:
        for key in ("id", "name", "version"):
            if not _is_str(framework.get(key)):
                report.fail("PINS", "missing or empty framework." + key)
                if key == "id":
                    usable = False
        version = framework.get("version")
        if _is_str(version) and not _EXACT_PIN.match(version.strip()):
            report.fail("PINS",
                        "framework.version {!r} is not an exact pin (no ranges, "
                        "no ^ or >=)".format(version))

    pins = manifest.get("dependency_pins")
    if not isinstance(pins, dict) or not pins:
        report.fail("PINS", "manifest 'dependency_pins' must be a non-empty object "
                            "mapping package name -> exact version")
    else:
        for name, version in sorted(pins.items()):
            if not _is_str(version) or not _EXACT_PIN.match(version.strip()):
                report.fail("PINS", "dependency_pins[{!r}] = {!r} is not an exact "
                                    "pin".format(name, version))
        report.info("PINS", "{} dependency pins declared".format(len(pins)))

    config = manifest.get("config")
    if not isinstance(config, dict) or not _is_str(config.get("name")) \
            or not _is_str(config.get("description")):
        report.fail("CONFIG", "manifest 'config' needs a name and a description "
                              "(what the review/guardrail machinery actually is)")
        usable = usable and isinstance(config, dict) and _is_str(config.get("name"))

    model = manifest.get("pipeline_model")
    if not isinstance(model, dict) or not _is_str(model.get("id")):
        report.fail("MODEL", "manifest 'pipeline_model' needs an exact model id")

    contact = manifest.get("contact")
    if not isinstance(contact, dict) or not any(_is_str(contact.get(k))
                                                for k in ("email", "github")):
        report.fail("CONTACT", "manifest 'contact' needs an email or a github handle")

    spend = manifest.get("spend_usd")
    if not isinstance(spend, (int, float)) or isinstance(spend, bool) or spend < 0:
        report.fail("SPEND", "manifest 'spend_usd' must be a non-negative number "
                             "(what the row cost to produce)")

    # Replicate honesty (v0.2.1): these are replicate labels, not random seeds.
    labels = manifest.get("replicate_labels")
    if not isinstance(labels, list) or not all(_is_str(x) for x in labels):
        report.fail("REPLICATES", "manifest 'replicate_labels' must be a list of "
                                  "non-empty strings")
        usable = False
    elif len(labels) != len(set(labels)):
        report.fail("REPLICATES", "replicate_labels contains duplicates")
        usable = False
    elif len(labels) < MIN_REPLICATES:
        report.fail("REPLICATES", "{} replicate labels declared; at least {} are "
                                  "required".format(len(labels), MIN_REPLICATES))
    else:
        report.info("REPLICATES",
                    "{} replicate labels: {}. These are labels, not random seeds -- "
                    "quote them as replicates.".format(len(labels), ", ".join(labels)))

    if "seeds" in manifest:
        report.fail("REPLICATES",
                    "manifest uses 'seeds'; v0.2.1 calls these replicate labels. "
                    "Rename the field to 'replicate_labels'.")

    claimed = manifest.get("claimed")
    if not isinstance(claimed, dict):
        report.fail("CLAIMED", "manifest 'claimed' must be an object of counters")
        usable = False
    else:
        if not isinstance(claimed.get("valid_cells"), int) \
                or isinstance(claimed.get("valid_cells"), bool):
            report.fail("CLAIMED", "claimed.valid_cells must be an integer")
        required = list(BASE_CLAIMS)
        if protocol == "wave2-union":
            required += list(UNION_CLAIMS)
        for key in required:
            if key not in claimed:
                report.fail("CLAIMED", "claimed." + key + " is required for protocol "
                                       + str(protocol))
            elif not _counter(claimed[key]):
                report.fail("CLAIMED", "claimed.{} must be {{'hits': int, 'n': int}} "
                                       "with 0 <= hits <= n".format(key))
        if protocol == "wave1-mapping":
            for key in UNION_CLAIMS:
                if key in claimed:
                    report.fail("CLAIMED",
                                "claimed.{} is not scoreable under protocol "
                                "wave1-mapping".format(key))

    for key, kind in (("exclusions", list), ("carve_outs", list)):
        if key in manifest and not isinstance(manifest[key], kind):
            report.fail("MANIFEST_FIELD", "manifest '" + key + "' must be a list")
            usable = False

    return usable


def check_mapping_doc(subdir, report):
    """mapping.md carries the proposed SPEC section 5 detection-act mapping. It is
    adjudicated by the section-5 dispute process in the PR, not by this script; all
    that is checked here is that a reviewable mapping table exists."""
    path = subdir / "mapping.md"
    if not path.is_file():
        report.fail("MAPPING_DOC", "mapping.md is missing; a submitted row needs a "
                                   "proposed SPEC section 5 detection-act mapping")
        return
    text = path.read_text()
    if not re.search(r"\|\s*act\s*\|\s*mechanism\s*\|", text, re.IGNORECASE):
        report.fail("MAPPING_DOC", "mapping.md has no `| act | mechanism |` table; "
                                   "mirror the SPEC section 5 per-act mapping")
        return
    if "<" in text and re.search(r"<[a-z_ ]+>", text):
        report.fail("MAPPING_DOC", "mapping.md still contains <placeholder> text")
        return
    report.info("MAPPING_DOC", "mapping table present; it goes through the SPEC "
                               "section 5 dispute process in the PR before the row lands")


def check_traces_declaration(manifest, subdir, report):
    """Returns True when an in-repo corpus is expected, False when the manifest
    points at an external release asset. CI validates only what is in-repo."""
    traces = manifest.get("traces")
    have_dir = ((subdir / "traces").is_dir()
                and any((subdir / "traces").rglob("*.json")))
    if isinstance(traces, dict) and traces.get("in_repo") is True:
        if not have_dir:
            report.fail("TRACES", "manifest declares an in-repo corpus but "
                                  "traces/ is missing or empty")
            return False
        return True
    if isinstance(traces, dict) and "tarball_url" in traces:
        url, digest = traces.get("tarball_url"), traces.get("sha256")
        ok = True
        if not _is_str(url) or not _URL.match(url.strip()):
            report.fail("TRACES", "traces.tarball_url must be an https URL")
            ok = False
        if not _is_str(digest) or not _SHA256.match(digest.strip()):
            report.fail("TRACES", "traces.sha256 must be a 64-character hex digest")
            ok = False
        if have_dir:
            report.warn("TRACES", "both an external tarball and an in-repo traces/ "
                                  "are present; the in-repo corpus is what CI scores")
            return True
        if ok:
            report.info("EXTERNAL",
                        "corpus is an external release asset ({}, sha256 {}). CI "
                        "validates only what is in-repo, so this row is UNVERIFIED "
                        "here; the maintainer downloads it, verifies the digest, and "
                        "runs this validator locally before the row "
                        "lands.".format(url, digest))
        return False
    report.fail("TRACES", "manifest 'traces' must declare either {\"in_repo\": true} "
                          "or {\"tarball_url\": ..., \"sha256\": ...}")
    return False


# --------------------------------------------------------------------------------
# corpus
# --------------------------------------------------------------------------------

def _read_run_result(path, report, code, where):
    """Parse one runresult.json through the committed serde/trace path."""
    try:
        raw = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        report.fail(code, "{}: unreadable JSON ({})".format(where, exc))
        return None, None
    version = raw.get("trace", {}).get("schema_version") if isinstance(raw, dict) else None
    if version != SCHEMA_VERSION:
        report.fail(code, "{}: trace schema_version is {!r}, expected {}".format(
            where, version, SCHEMA_VERSION))
        return None, None
    try:
        result = run_result_from_json(json.dumps(raw))
    except (KeyError, TypeError, ValueError) as exc:
        report.fail(code, "{}: does not parse as trace schema v1 ({}: {})".format(
            where, type(exc).__name__, exc))
        return None, None
    return result, raw


def _check_trace_identity(raw, report, where, framework, config, task, operator, label):
    trace = raw["trace"]
    for field, want in (("framework", framework), ("config", config),
                        ("task", task), ("operator", operator)):
        got = trace.get(field)
        if got != want:
            report.fail("TRACE_IDENTITY", "{}: trace {} is {!r}, expected {!r}".format(
                where, field, got, want))
    if str(trace.get("seed")) != str(label):
        report.fail("TRACE_IDENTITY", "{}: trace seed field is {!r}, expected the "
                                      "replicate label {!r}".format(
                                          where, trace.get("seed"), label))


def load_baselines(subdir, framework, config, labels, report):
    """The per-(task, replicate) clean baselines. A cell cannot be scored without
    the baseline it shares (SPEC section 3)."""
    baselines = {}
    for task in TASKS:
        for label in labels:
            path = (subdir / "traces" / task / "baseline" / label
                    / "baseline-runresult.json")
            where = "{}/baseline/{}".format(task, label)
            if not path.is_file():
                report.fail("BASELINE_MISSING", where + ": baseline-runresult.json "
                                                        "is missing")
                continue
            result, raw = _read_run_result(path, report, "BASELINE_TRACE", where)
            if result is None:
                continue
            _check_trace_identity(raw, report, where, framework, config, task,
                                  None, label)
            baselines[(task, label)] = (result, raw)
    if baselines:
        passed = sum(1 for r, _ in baselines.values() if r.task_passed)
        report.info("BASELINES", "{}/{} baselines present, {} passing their task "
                                 "(a failing baseline excludes every cell that "
                                 "shares it, BASELINE_FAIL)".format(
                                     len(baselines), len(TASKS) * len(labels), passed))
    return baselines


def carved_out(manifest):
    """Structural carve-outs (the SPEC 10.6 pattern): operators that cannot land in
    view of any component of this framework's pipeline. Not exclusions -- these
    cells are never run and are not part of the matrix."""
    out = {}
    for entry in manifest.get("carve_outs", []) or []:
        if isinstance(entry, dict) and _is_str(entry.get("operator")):
            out[entry["operator"]] = entry
    return out


def check_carve_outs(manifest, report):
    declared = manifest.get("carve_outs", []) or []
    for entry in declared:
        if not isinstance(entry, dict):
            report.fail("CARVE_OUT", "carve_outs entries must be objects")
            continue
        if entry.get("operator") not in OPERATORS:
            report.fail("CARVE_OUT", "carve_outs operator {!r} is not one of "
                                     "{}".format(entry.get("operator"), list(OPERATORS)))
        if not _is_str(entry.get("reason")) or not _is_str(entry.get("spec_ref")):
            report.fail("CARVE_OUT", "each carve-out needs a 'reason' and a "
                                     "'spec_ref' (why no component sees the fault)")
    if declared:
        report.info("CARVE_OUT",
                    "{} structural carve-out(s) declared; those cells leave the "
                    "matrix entirely rather than counting as zeros, and the row "
                    "publishes with the carve-out named".format(len(declared)))


def index_exclusions(manifest, labels, report):
    """{(task, operator, label): code} from the itemized exclusion list."""
    index = {}
    for entry in manifest.get("exclusions", []) or []:
        if not isinstance(entry, dict):
            report.fail("EXCLUSION_CLASS", "exclusions entries must be objects")
            continue
        task, operator = entry.get("task"), entry.get("operator")
        label, code = entry.get("replicate"), entry.get("code")
        where = "{}/{}/{}".format(task, operator, label)
        if task not in TASKS or operator not in OPERATORS or label not in labels:
            report.fail("EXCLUSION_CLASS",
                        where + ": exclusion does not name a cell in this matrix")
            continue
        if code not in EXCLUSION_CODES:
            report.fail("EXCLUSION_CLASS",
                        "{}: exclusion code {!r} is not one of {} (SPEC section "
                        "3)".format(where, code, list(EXCLUSION_CODES)))
            continue
        if not _is_str(entry.get("note")):
            report.fail("EXCLUSION_CLASS",
                        where + ": every exclusion needs a 'note' saying what happened")
        index[(task, operator, label)] = code
    return index


def score_corpus(subdir, manifest, labels, baselines, declared, carve, report,
                 score_wave2):
    """Recompute every cell through the committed scorers. Returns the row list in
    the shape scripts/score_wave2.py produces."""
    framework = manifest["framework"]["id"]
    config = manifest["config"]["name"]
    rows = []
    seen = set()

    for task in TASKS:
        for operator in OPERATORS:
            if operator in carve:
                continue
            for position, label in enumerate(labels):
                key = (task, operator, label)
                where = "{}/{}/{}".format(task, operator, label)
                path = subdir / "traces" / task / operator / label / "runresult.json"
                declared_code = declared.get(key)

                if not path.is_file():
                    if declared_code is None:
                        report.fail("CELL_MISSING",
                                    where + ": runresult.json is missing and the cell "
                                            "is not itemized as an exclusion")
                    elif declared_code in ("RUN_ERROR", "INJECTION_UNVERIFIED"):
                        report.fail("EXCLUSION_EVIDENCE",
                                    "{}: declared {} but ships no runresult.json. A "
                                    "quarantined run still ships its trace -- that is "
                                    "what makes the exclusion "
                                    "auditable.".format(where, declared_code))
                    elif (task, label) not in baselines:
                        report.fail("EXCLUSION_EVIDENCE",
                                    where + ": declared BASELINE_FAIL but the baseline "
                                            "it names is not in the corpus")
                    elif baselines[(task, label)][0].task_passed:
                        report.fail("EXCLUSION_PRECEDENCE",
                                    where + ": declared BASELINE_FAIL but the shared "
                                            "baseline passed its task")
                    else:
                        seen.add(key)
                    continue

                seen.add(key)
                faulted, raw = _read_run_result(path, report, "CELL_TRACE", where)
                if faulted is None:
                    continue
                _check_trace_identity(raw, report, where, framework, config, task,
                                      operator, label)
                if (task, label) not in baselines:
                    report.fail("BASELINE_MISSING",
                                where + ": no baseline for this (task, replicate), so "
                                        "the cell cannot be scored")
                    continue
                baseline = baselines[(task, label)][0]

                cell = Cell(framework=framework, task=task, config=config,
                            operator=operator, operator_spec=None, seed=position)
                verdict = run_cell(None, cell, faulted, baseline)

                if verdict.excluded is not None and declared_code is None:
                    report.fail("EXCLUSION_UNDECLARED",
                                "{}: recomputes as {} but is not itemized in the "
                                "manifest. Exclusions are itemized, never silently "
                                "dropped.".format(where, verdict.excluded))
                elif verdict.excluded is None and declared_code is not None:
                    report.fail("EXCLUSION_PRECEDENCE",
                                "{}: itemized as {} but recomputes as a valid scored "
                                "cell".format(where, declared_code))
                elif verdict.excluded is not None and verdict.excluded != declared_code:
                    report.fail("EXCLUSION_PRECEDENCE",
                                "{}: itemized as {} but the committed scorer resolves "
                                "it to {} (precedence RUN_ERROR > BASELINE_FAIL > "
                                "INJECTION_UNVERIFIED, SPEC section 3)".format(
                                    where, declared_code, verdict.excluded))

                scan = {"noticed": False, "anchored": False, "flags": []}
                if verdict.excluded is None:
                    scan = scan_trace_flags_v2(raw["trace"], task, operator,
                                               faulted.injection_seq or 0)
                anchored = scan["anchored"]
                if operator in FLAGS_SURFACE_EXCLUDED_OPERATORS:
                    anchored = False

                row = {"framework": framework, "config": config, "task": task,
                       "operator": operator, "seed": label,
                       "excluded": verdict.excluded,
                       "wave1_mapping": verdict.detected_hard,
                       "reacted": verdict.detected_hard,
                       "recovered": verdict.recovered,
                       "flags_noticed": scan["noticed"],
                       "flags_anchored": anchored,
                       "flags": scan["flags"],
                       "wave1_hard": None, "wave1_excluded": None}
                # Identical to scripts/score_wave2.py: union is either surface.
                row["union"] = bool(row["wave1_mapping"] or row["flags_anchored"])
                rows.append(row)

    stale = sorted(set(declared) - seen)
    for key in stale:
        report.fail("EXCLUSION_CLASS",
                    "{}/{}/{}: itemized as an exclusion but is not a cell of this "
                    "matrix (carved out?)".format(*key))

    # The exclusion appendix (SPEC section 3): per-code counts, always published,
    # even when it is empty.
    counts = {}
    for code in declared.values():
        counts[code] = counts.get(code, 0) + 1
    report.info("EXCLUSIONS",
                "exclusion appendix: " + (", ".join(
                    "{} {}".format(code, counts[code]) for code in sorted(counts))
                    if counts else "none") + " (publish this with the row)")

    groups = score_wave2.aggregate(rows, lambda r: "row")
    totals = groups.get("row", {"valid": 0, "wave1_mapping": 0, "flags_anchored": 0,
                                "union": 0, "flags_noticed": 0, "reacted": 0,
                                "recovered": 0})
    totals = dict(totals)
    totals["strict_floor"] = sum(strict_detected(r) for r in rows
                                 if r["excluded"] is None)
    return rows, totals


def clean_baseline_false_anchor(baselines, report):
    """The clean-baseline false-anchor base rate, computed by the committed anchor
    rule against runs where no fault exists (SPEC 10.3; the review's R9/R11).

    Every hit is a false positive. Any anchored-text detection metric owes its
    readers this table, so a submitted row publishes it next to its headline."""
    per_operator = {}
    hits = total = 0
    for (task, _label), (_result, raw) in sorted(baselines.items()):
        for operator in OPERATORS:
            scan = scan_trace_flags_v2(raw["trace"], task, operator, 0)
            bucket = per_operator.setdefault(operator, {"hits": 0, "n": 0})
            bucket["n"] += 1
            total += 1
            if scan["anchored"]:
                bucket["hits"] += 1
                hits += 1
    rate = (100.0 * hits / total) if total else 0.0
    report.info("BASE_RATE",
                "clean-baseline false-anchor base rate {:.1f}% ({}/{}) -- publish "
                "this with the row: {}".format(
                    rate, hits, total,
                    ", ".join("{} {:.1f}%".format(
                        op, 100.0 * per_operator[op]["hits"] / per_operator[op]["n"]
                        if per_operator[op]["n"] else 0.0)
                        for op in OPERATORS if op in per_operator)))
    if "O4" in per_operator:
        report.info("BASE_RATE",
                    "O4's base rate is diagnostic only: under SPEC v0.2.1 O4 is "
                    "scored on the mapping surface and is off the anchored-FLAGS "
                    "surface entirely")
    return {"hits": hits, "n": total, "per_operator": per_operator}


def report_instrument_coverage(rows, report):
    """The review's R3: a cell whose registered anchors cannot separate injected
    from true text scores zero because the instrument is blind, not because the
    pipeline was silent. Publish the coverage rather than discovering it later."""
    scored = [r for r in rows if r["excluded"] is None]
    if not scored:
        return {"covered": 0, "n": 0}
    covered = sum(1 for r in scored
                  if injection_only_anchors(r["task"], r["operator"]))
    report.info("COVERAGE",
                "{}/{} scored cells have an injection-only anchor surface "
                "({:.1f}%); the rest are instrument-blind at the strict floor and a "
                "zero there means blindness, not silence".format(
                    covered, len(scored), 100.0 * covered / len(scored)))
    return {"covered": covered, "n": len(scored)}


def check_claims(manifest, totals, base_rate, report):
    """Claimed row numbers must match the recompute to the digit."""
    claimed = manifest.get("claimed")
    if not isinstance(claimed, dict):
        return
    protocol = manifest.get("protocol")
    valid = totals.get("valid", 0)

    if isinstance(claimed.get("valid_cells"), int) \
            and not isinstance(claimed.get("valid_cells"), bool) \
            and claimed["valid_cells"] != valid:
        report.fail("RECOMPUTE", "claimed valid_cells {} != recomputed {}".format(
            claimed["valid_cells"], valid))

    keys = list(BASE_CLAIMS)
    if protocol == "wave2-union":
        keys += list(UNION_CLAIMS)
    for key in keys:
        entry = claimed.get(key)
        if not _counter(entry):
            continue
        if key == "clean_baseline_false_anchor":
            got_hits, got_n = base_rate["hits"], base_rate["n"]
        else:
            got_hits, got_n = totals.get(key, 0), valid
        if (entry["hits"], entry["n"]) != (got_hits, got_n):
            report.fail("RECOMPUTE",
                        "claimed {} = {}/{} but the committed scorers recompute "
                        "{}/{}".format(key, entry["hits"], entry["n"], got_hits, got_n))
        else:
            rate = (100.0 * got_hits / got_n) if got_n else 0.0
            report.info("RECOMPUTE", "{} verified: {:.1f}% ({}/{})".format(
                key, rate, got_hits, got_n))

    if protocol == "wave2-union":
        report.info("PAIR", "quote this row as the pair (strict floor, union) -- the "
                            "floor deliberately under-counts and the truth lies "
                            "between them")


# --------------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------------

def validate(subdir, report):
    """Run every check over one submission directory. Returns the JSON payload."""
    payload = {"submission": subdir.name, "verified": False, "recomputed": None,
               "clean_baseline_false_anchor": None, "coverage": None}

    manifest_path = subdir / "manifest.json"
    if not manifest_path.is_file():
        report.fail("MANIFEST_PARSE", "manifest.json is missing")
        return payload
    try:
        manifest = json.loads(manifest_path.read_text())
    except ValueError as exc:
        report.fail("MANIFEST_PARSE", "manifest.json is not valid JSON: " + str(exc))
        return payload
    if not isinstance(manifest, dict):
        report.fail("MANIFEST_PARSE", "manifest.json must be a JSON object")
        return payload

    usable = check_manifest(manifest, report)
    check_mapping_doc(subdir, report)
    check_carve_outs(manifest, report)
    if not usable:
        report.fail("ABORT", "manifest is not structurally usable; fix the findings "
                             "above before the corpus can be scored")
        return payload

    in_repo = check_traces_declaration(manifest, subdir, report)
    if not in_repo:
        return payload

    labels = manifest["replicate_labels"]
    framework = manifest["framework"]["id"]
    config = manifest["config"]["name"]

    baselines = load_baselines(subdir, framework, config, labels, report)
    declared = index_exclusions(manifest, labels, report)
    carve = carved_out(manifest)

    score_wave2 = load_score_wave2()
    rows, totals = score_corpus(subdir, manifest, labels, baselines, declared, carve,
                                report, score_wave2)
    base_rate = clean_baseline_false_anchor(baselines, report)
    coverage = report_instrument_coverage(rows, report)
    check_claims(manifest, totals, base_rate, report)

    payload["recomputed"] = totals
    payload["clean_baseline_false_anchor"] = base_rate
    payload["coverage"] = coverage
    payload["verified"] = not report.failed
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Validate one third-party Sabot scoreboard submission.")
    parser.add_argument("submission", help="path to submissions/<slug>")
    parser.add_argument("--json", action="store_true",
                        help="emit machine-readable findings for CI annotation")
    args = parser.parse_args(argv)

    subdir = pathlib.Path(args.submission)
    report = Report()
    if not subdir.is_dir():
        report.fail("SUBMISSION", "not a directory: " + str(subdir))
        payload = {"submission": subdir.name, "verified": False, "recomputed": None,
                   "clean_baseline_false_anchor": None, "coverage": None}
    else:
        payload = validate(subdir, report)

    status = 1 if report.failed else 0
    payload["exit"] = status
    payload["findings"] = report.findings

    if args.json:
        print(json.dumps(payload, indent=1, sort_keys=True))
    else:
        print("== sabot submission validator: {} ==".format(subdir))
        print(report.render())
        fails = sum(1 for f in report.findings if f["level"] == "FAIL")
        print("{}: {} finding(s), {} FAIL".format(
            "REJECTED" if fails else "OK", len(report.findings), fails))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
