# submissions/

Third-party scoreboard rows. One directory per row.

A row is one framework, at one config, on one pipeline model, over the five tasks and
six operators in this repository, with at least five replicates and the clean
baselines they share. The route from a fork to a merged row — what a submission must
contain, the honesty bar, the mapping dispute process — is in
**[SUBMITTING.md](../SUBMITTING.md)**.

- `TEMPLATE/` — the worked skeleton to copy. Skipped by CI; never a scoreboard row.
- `<slug>/` — one submitted row each.

## The provenance rule

**Submitted rows are labelled third-party and are published in a separate table.
They are never pooled into the author-run medians, and they never enter the
headline.**

This is not a comment on submission quality. The author-run rows were produced by one
person, on one harness, at one set of pins, with a pre-registered spec and a
published spend ledger; mixing rows produced under different hands into a single
median would quietly change what the median means, and no footnote makes that
recoverable. So the two populations stay separate, in the data and in the prose, and
every submitted row carries `"provenance": "third-party"` in its manifest — the
validator fails the submission if it does not.

Comparisons across the two tables are legitimate and encouraged. Silent pooling is
not.

## What is in scope

Deterministic surfaces only:

- the hard-tier detection-act mapping surface (SPEC §5), and
- the wave-2 anchored-FLAGS union surface (SPEC §10.3–§10.5).

The soft-tier LLM judge (SPEC §6) is **out of scope for submissions**. It cannot be
replicated by a third party — a judge run depends on a model, a prompt variant, and a
sandbox that a reader of this repository cannot reproduce from the committed
artifacts — and every number in a submitted row must be recomputable offline, to the
digit, by the scorers committed here. A submission that quotes a judge number is
quoting something the validator cannot check, so it is not part of the row.

## Checking a submission

```bash
cd harness
python scripts/validate_submission.py ../submissions/<slug>          # human-readable
python scripts/validate_submission.py ../submissions/<slug> --json   # for tooling
```

Stdlib-only, Python 3.9+, no API key, no network. CI runs it over every directory
here except `TEMPLATE/` on every pull request and push.
