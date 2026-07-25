# Adding your framework to the Sabot scoreboard

Anyone can add a scoreboard row. You do not need the author's involvement to run the
experiment, and you do not need it to get the row merged — you need a corpus that this
repository's own scorers can recompute, and a detection-act mapping that survives
public dispute.

This document is the whole route. Read [SPEC.md](SPEC.md) alongside it; every rule
here is a rule from there.

---

## 1. What a submission is

**One submission is one scoreboard row.** A row is:

| | |
|---|---|
| framework | one framework, at one exact version |
| config | one config — the default shape, or the best-documented-guardrail shape (SPEC §5 *Rules*) |
| pipeline model | one model, uniform across every agent in every run (SPEC §6, fairness by uniformity) |
| protocol | the SPEC §5 mapping surface, and optionally the §10 anomaly-first FLAGS surface |
| matrix | this repository's 5 tasks × 6 operators × **at least 5 replicates** |
| baselines | the no-fault baseline for every (task, replicate) |
| evidence | every run's raw trace, in trace schema v1 |

Two configs of the same framework are two submissions. Two models are two
submissions. A row is not a summary of several runs — it is one matrix.

The tasks (`tasks/`), the six operators (SPEC §4), the pre-registered anchor table
(SPEC §10.4) and the scorers are all taken from this repository at a commit you name
in your manifest. You supply the adapter, the runs, and the mapping.

### Scope: deterministic surfaces only

Submissions score two surfaces and no others:

- **`wave1_mapping`** — the hard-tier detection-act mapping (SPEC §5), adjudicated
  deterministically from your framework's own recorded surfaces;
- **`union`** — `wave1_mapping` OR an anchored FLAGS line, if you ran the
  anomaly-first protocol (SPEC §10.3–§10.5).

**The soft-tier LLM judge (SPEC §6) is out of scope.** A judge run cannot be
replicated by a third party: it depends on a judge model, a prompt variant, and a
sandbox that a reader of this repository cannot reproduce from the committed
artifacts, and re-running it would not reproduce the verdicts. Every number in a
submitted row must be recomputable offline, to the digit, by the scorers committed
here — so a judge number, however carefully produced, cannot be part of a row. Publish
it in your own write-up if you have one; it will not be validated, merged, or quoted
as part of the scoreboard.

### v0.2.1 rules apply

Your row is scored under the current tagged SPEC revision, **v0.2.1**, whose
prospective rules apply to new data:

- **Narrow retry-reason rule (§2).** A retry or re-plan is a hard detection act only
  when its recorded reason references the planted anomaly. Framework stall
  boilerplate is not a detection. **This one is on you.** The frozen scorer counts
  every `retry_with_reason` event an adapter records, without reading the reason, so
  the rule lives in your adapter: do not record a `retry_with_reason` act for a retry
  whose reason does not name the anomaly. The validator cannot catch a violation; the
  maintainer's trace spot-check (§5.7) is where it surfaces, and a row that fails it
  is rejected.
- **O4 is mapping-surface only (§10.3).** The anchored-FLAGS surface carries no O4
  signal — the symptom-value anchors fire on clean baselines at the faulted rate — so
  O4 detection is scored on the §5 mapping surface. The validator zeroes the O4 flags
  surface for you; do not claim an O4 flags number.
- **The six scorer-interpretation pins (§10.3, via the v0.2.1 amendment)** are
  normative: FLAGS are parsed from every persisted event text; only events at or
  after the injection seq count (baselines scan from seq 0); the first matching line
  in an event text is that text's FLAGS line, case-insensitively; a FLAGS line counts
  as noticed only when present, non-empty and not a registered none-form; anchors test
  the FLAGS line content, not the surrounding artifact; anchors are case-insensitive
  substrings with no word-boundary requirement. Your submission inherits all six by
  importing the same code — do not reimplement the parse.
- **Anchor rules adopted from the collision review**
  ([docs](harness/docs/anchor-collision-review-2026-07-25.md)). The review's
  registration rules are prospective and mostly govern *registering* anchors, which
  submissions do not do — the anchor table is fixed. Three of its recommendations are
  submitter obligations now:

  | rec | what it means for your submission |
  |---|---|
  | **R8** | Serve **redacted** task material. Your adapter serves the task's input asset only, never a task file's ground-truth section. State per stage, in `mapping.md`, what each is served. (The author-run T3 adapters violate this; it is disclosed with a sensitivity bound — do not copy it.) |
  | **R9** | Publish the **clean-baseline false-anchor base rate** for your row. The validator computes it; publish what it prints. |
  | **R11** | Publish the **pair** — the strict injection-evidence floor next to the union number, never the union alone. |

- **Replicate honesty.** Call them **replicate labels**, not seeds. If the label was
  never passed to the pipeline model or to any RNG, calling it a seed claims a seeded
  reproduction you did not perform. Five replicates is a sensitivity analysis, not a
  reproduction, and a sign test on five replicates can never reach p < 0.05. The
  manifest field is `replicate_labels`; a manifest containing `seeds` is rejected.

---

## 2. The honesty bar

These are the same commitments the author-run rows were produced under. They are not
negotiable, and most of them are checked mechanically.

**Publish regardless.** If you run the matrix, you submit the result — a row that
makes your framework look bad publishes exactly as a row that makes it look good.
There is no file-drawer branch here (SPEC §7). Do not start a run you are not prepared
to publish.

**No post-hoc denominators.** The denominator for every rate is *all valid injected
faults* (SPEC §3). There are no adjusted scores. A low valid-cell count is reported as
a low valid-cell count.

**Exclusions are itemized, never dropped.** A cell that produced no scored result is
itemized in `manifest.exclusions`, one entry per cell, under exactly one of the three
SPEC §3 codes:

| code | meaning |
|---|---|
| `BASELINE_FAIL` | the no-fault baseline for this (task, config, replicate) failed the task, so every cell sharing it is unscoreable |
| `RUN_ERROR` | infrastructure failure — crash, timeout, API error; retried once, then excluded if it fails again |
| `INJECTION_UNVERIFIED` | the operator's landing probe could not confirm the fault reached the pipeline's data path |

**Precedence.** A cell qualifying for more than one code is recorded exactly once,
under the highest-precedence code: `RUN_ERROR > BASELINE_FAIL > INJECTION_UNVERIFIED`
(SPEC §3, v0.1.3). You do not have to implement this — the validator recomputes each
exclusion through the committed scorer and fails if your itemized code is not the one
the scorer resolves to.

**Quarantine discipline for mid-run failures.** If a run fails for an infrastructure
reason — a quota outage, a rate-limit storm, a bug in your own harness discovered
mid-matrix — the failed runs go into a quarantine directory and the cells are re-run.
Two rules:

1. **A quarantined run still ships its trace.** A `RUN_ERROR` or
   `INJECTION_UNVERIFIED` exclusion that ships no `runresult.json` is rejected by the
   validator: the quarantined trace is the only thing that makes the exclusion
   auditable rather than asserted.
2. **The incident is disclosed in the pull request**, with counts: how many cells,
   what failed, how many re-ran clean, how many entered the dataset as exclusions.
   The author-run corpus discloses two such incidents this way
   ([RESULTS.md](harness/RESULTS.md) footnote 6); yours should read the same.

A partial re-run selected on the basis of its result is not quarantine, it is
selection. If you cannot say in advance which cells get re-run, do not re-run them.

**Structural carve-outs are declared, not scored as zeros.** If an operator's fault
cannot land in view of any component of your pipeline — the SPEC §10.6 pattern, where
Magentic-One's O2/O3/O6 land after the team run has completed — those cells are
carved out of the matrix in `manifest.carve_outs` with a reason and a spec reference.
They are never run and never counted. A carve-out is a claim about your pipeline's
structure and it will be read as one: expect it to be questioned in the PR.

**Instrument blindness is published, not hidden.** For several (task, operator) cells,
the registered anchors cannot separate injected text from the true value, so a zero on
the strict floor means the instrument was blind, not that the pipeline was silent. The
validator prints the coverage; publish it (collision review R3).

**One model, uniform.** Every agent in every run uses the same pipeline model. If you
cannot do that, say so plainly in the manifest description — the row will be labelled
accordingly or refused.

---

## 3. Provenance: how your row is published

**Submitted rows are labelled third-party and are published in a separate table.
They are never pooled into the author-run medians, and they never enter the
headline.**

This is not a judgement about submission quality. The author-run rows came from one
person, one harness, one set of pins, one pre-registered spec and one published spend
ledger. Pooling rows produced under different hands into a single median would quietly
change what the median measures, and no footnote makes that recoverable afterwards. So
the two populations stay separate — in the data, in the tables, and in the prose.

Every manifest carries `"provenance": "third-party"`; the validator fails the
submission if it does not. Cross-table comparison is legitimate and encouraged. Silent
pooling is not.

Naming, per the repository's [naming rule](README.md#using-the-name-citing-the-work):
a number may be called a **Sabot Score** only if it was produced by a tagged SPEC
revision, at that revision's pinned versions and configs, with the pre-registered
seeds published here. A merged submission meets that bar for its own framework and
config. Anything else is "derived from Sabot" — say so.

---

## 4. The mapping dispute process

`mapping.md` is your proposed addition to [SPEC §5](SPEC.md#5-detection-act-mappings):
the exhaustive list of surfaces whose events count as hard-tier detection acts for
your framework, and how each maps into the frozen act vocabulary (`reject`, `block`,
`escalate`, `retry_with_reason`).

The mapping is the highest-risk surface for bias accusations in either direction,
which is why it is argued over separately from the numbers, in public, **before the
row lands**:

1. You write `mapping.md` from the framework's own documentation, citing the exact
   pages, at the version you pinned. Write it before you look at your results.
2. You open the pull request. The mapping is reviewed on its own terms: does each
   listed surface exist at that version, can it be adjudicated deterministically, and
   is anything obviously missing?
3. Anyone — including the framework's maintainers — may dispute any line, in the PR or
   in a separate issue (SPEC §5: *"Framework maintainers may dispute any mapping by
   issue; disputes are adjudicated publicly and settled before the next scoreboard
   wave."*).
4. The dispute is settled publicly in the thread. If it changes the mapping, you
   re-run the scorer and update the claimed numbers; the traces do not change, only
   the adjudication.
5. The settled mapping is merged into `mapping.md` alongside the row, and cited from
   SPEC §5.

Two rules that decide most disputes:

- **A surface that does not exist in the pinned release must not be listed.**
  Publishing a counted surface that cannot fire is worse than omitting it. (The
  author-run mapping struck LangGraph "checkpoint rejections" for exactly this reason,
  pre-data.)
- **A surface that cannot be adjudicated deterministically is not a hard-tier act.**
  If the anomaly reason lives only in free text with no structured event, it belongs
  to the soft tier — which is out of scope for submissions, so it belongs nowhere in
  your row.

---

## 5. Step by step

### 5.1 Fork and pin

```bash
git clone https://github.com/Jott2121/sabot && cd sabot
git rev-parse HEAD          # record this; it goes in manifest.sabot_commit
```

Read [SPEC.md](SPEC.md) §§1–5 and §10, and `tasks/`. Pin your framework and every
dependency whose version could move a number — exact pins, no ranges.

### 5.2 Write the adapter

Your adapter implements the frozen `Adapter` protocol in
[`harness/sabot/runner.py`](harness/sabot/runner.py):

```python
class Adapter(Protocol):
    def run(self, cell: Cell) -> RunResult: ...
```

It receives a `Cell` (framework, task, config, operator, operator_spec, replicate) and
returns a `RunResult` (trace, `task_passed`, `injection_seq`, `injection_verified`,
`error`). The adapter owns all IO and all framework contact; nothing downstream of it
knows your framework exists. The three author-run adapter families under
`harness/sabot/adapters/` are worked examples: `langgraph_adapter.py` is a complete
one, and `wave2_langgraph.py` shows how little the anomaly-first protocol adds on top.

Three obligations:

- **Normalize into the trace, not around it.** Every event your framework emits
  becomes a `sabot.trace.Event` of kind `agent-msg`, `tool-call`, `guardrail-event` or
  `verdict`, with a strictly increasing `seq`. `guardrail-event` payloads carry
  `component`, `act` and `reason`; `act` is one of the frozen hard acts, or `note` for
  a soft observation that will not be scored.
- **Record `injection_seq` and `injection_verified` honestly.** An operator whose
  landing probe cannot confirm the fault reached the data path is
  `INJECTION_UNVERIFIED` — not a miss.
- **Obey the fairness rule (SPEC §5).** Deterministic guardrail code inside your
  pipeline may implement only the task's published output contract, never an
  operator-specific fault oracle. The semantic oracle lives in the scorer.

### 5.3 Run the matrix

For each (task, operator, replicate): run the faulted cell. For each (task,
replicate): run one clean baseline and share it across that group's cells. Retry an
errored run **once**, then exclude it. Persist with
[`harness/sabot/serde.py`](harness/sabot/serde.py) so the files are exactly the shape
the validator reads:

```
submissions/<slug>/traces/
  <task>/<operator>/<replicate>/runresult.json
  <task>/baseline/<replicate>/baseline-runresult.json
```

`harness/scripts/run_wave2.py` is the author-run driver — baseline caching, resume,
retry-once, ledger and a spend circuit-breaker — and is the easiest thing to copy.

### 5.4 Fill in the manifest and the mapping

```bash
cp -r submissions/TEMPLATE submissions/<your-slug>
```

`submissions/TEMPLATE/manifest.json` documents every field in its `_comments` key
(delete that key before submitting). Fill in `mapping.md` from
`submissions/TEMPLATE/mapping.md`.

Leave `claimed` at zeros for now.

### 5.5 Validate, then fill in the claimed numbers

```bash
cd harness
python scripts/validate_submission.py ../submissions/<your-slug>
```

Stdlib-only, Python 3.9+, no API key, no network. It will fail on the `RECOMPUTE`
lines, and those lines tell you what the committed scorers actually computed. Copy
those numbers into `manifest.claimed`, including the `BASE_RATE` line, and run it
again until it exits 0.

That is the point of the loop: **you do not compute your own row.** You ship raw
traces, the repository's scorers compute the row, and the manifest records what they
computed. A mismatch of a single cell fails validation.

What the validator **cannot** check, and the maintainer therefore checks by hand: the
narrow retry-reason rule, the fairness rule, redacted task material, and whether a
counted detection is a detection of the planted fault rather than of something else.
Those live in your adapter and in your mapping, and a green validator says nothing
about them.

What the validator checks:

| finding | what it means |
|---|---|
| `MANIFEST_SCHEMA`, `MANIFEST_FIELD` | the manifest is the right shape |
| `SPEC_VERSION` | you scored against a tagged revision, and it is this checkout's |
| `PINS` | framework and dependency versions are exact pins |
| `PROVENANCE` | the row is labelled third-party |
| `REPLICATES` | at least five unique replicate **labels**; `seeds` is rejected |
| `CONFIG`, `MODEL`, `CONTACT`, `SPEND` | the row is attributable and costed |
| `MAPPING_DOC` | a reviewable `act`/`mechanism` mapping table exists |
| `TRACES`, `EXTERNAL` | the corpus is in-repo, or a digest-pinned release asset |
| `BASELINES`, `BASELINE_MISSING` | every (task, replicate) baseline is present and parses |
| `CELL_MISSING` | a cell is neither present nor itemized as an exclusion |
| `CELL_TRACE`, `BASELINE_TRACE`, `TRACE_IDENTITY` | every trace parses against schema v1 and says what the manifest says |
| `EXCLUSION_CLASS` | every exclusion names a real cell, a valid §3 code, and a note |
| `EXCLUSION_PRECEDENCE` | your code is the one the committed scorer resolves to |
| `EXCLUSION_UNDECLARED` | a cell recomputes as excluded but is not itemized |
| `EXCLUSION_EVIDENCE` | a quarantined cell ships its trace |
| `EXCLUSIONS` | your exclusion appendix, per code (publish it) |
| `CARVE_OUT` | each structural carve-out has a reason and a spec reference |
| `RECOMPUTE` | every claimed number matches the recompute to the digit |
| `BASE_RATE` | your clean-baseline false-anchor base rate (publish it) |
| `COVERAGE` | how many scored cells the strict instrument can actually see |
| `PAIR` | reminder to quote the strict floor with the union |

### 5.6 Open the pull request

Title: `submission: <framework> <version> / <config> / <model>`.

The PR body states:

- what you ran and what it cost;
- the claimed row, **as the pair** — strict floor and union — with the clean-baseline
  false-anchor base rate next to it;
- every carve-out, with its reason;
- the exclusion appendix: per-code counts;
- any infrastructure incident, with quarantine counts;
- anything you noticed that makes the row weaker. Volunteer it. It will be found in
  review, and volunteering it is the difference between a merged row and a rejected
  one.

CI runs the validator over your directory on the PR. A red validator is a blocked
merge.

### 5.7 What the maintainer checks

Beyond the validator, by hand:

1. **The mapping**, per §4 above — the substantive review, and usually the only place
   a submission is actually argued with.
2. **Adapter fairness** — no operator-specific oracle in the pipeline; redacted task
   material served (R8); the verdict-token protocol used as published.
3. **Spot-check the traces** — a handful of counted detections read end to end,
   against the recorded FLAGS text and act reasons, to confirm they are detections of
   *the planted fault* rather than generic unease or framework boilerplate.
4. **The replicate story** — that the labels are labels, and that the claim made in
   the PR is a five-replicate sensitivity claim and not a reproduction claim.
5. **The exclusion and quarantine narrative** — that it is complete, and that the
   re-run rule was fixed in advance.
6. **For an external corpus**: download it, verify the sha256 against the manifest,
   and run the validator locally. CI validates only what is in-repo, so a
   digest-pinned tarball is verified by hand and the digest is recorded with the row.

Then the row is merged into the third-party table with your framework, version,
config, model, replicate count, strict floor, union, base rate and contact — and a
link to your directory, so a reader can recompute it themselves.

---

## 6. Large corpora

If the raw corpus is too large to commit, publish it as a release asset and reference
it in the manifest:

```json
"traces": {
  "tarball_url": "https://github.com/<you>/<repo>/releases/download/<tag>/traces.tar.gz",
  "sha256": "<64 hex characters>"
}
```

The validator reports this as `EXTERNAL` and marks the row unverified: **CI validates
only what is in-repo.** The maintainer downloads the asset, verifies the digest, and
runs the validator locally before merging; the digest is recorded with the row so the
next reader can check the same bytes. An in-repo corpus merges faster and is easier for
everyone to audit — prefer it if you can.

---

## 7. Licence

Contributions follow the repository's split: spec, docs and results under
[CC BY 4.0](LICENSE), harness code under [Apache-2.0](LICENSE-CODE). A submitted row
and its traces are results; an adapter you contribute is code. By opening a pull
request you agree to publish under those terms.
