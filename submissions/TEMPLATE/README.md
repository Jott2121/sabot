# Submission template

Copy this directory to `submissions/<your-slug>/` and fill it in. The full route,
end to end, is in **[SUBMITTING.md](../../SUBMITTING.md)** at the repository root —
read that first; this directory is only the skeleton it describes.

```
submissions/<your-slug>/
  manifest.json     version pins, config, model, replicate labels, spend, contact,
                    protocol, exclusions, and the row numbers you are claiming
  mapping.md        your proposed SPEC section 5 detection-act mapping, which goes
                    through the section 5 dispute process in the PR before the row lands
  traces/           the raw corpus, in trace schema v1
    <task>/<operator>/<replicate>/runresult.json
    <task>/baseline/<replicate>/baseline-runresult.json
```

`<task>` is `T1`–`T5`, `<operator>` is `O1`–`O6`, and `<replicate>` is one of the
labels you declare in `manifest.replicate_labels` — verbatim, at least five of them.

Check your work before you open the pull request:

```bash
cd harness
python scripts/validate_submission.py ../submissions/<your-slug>
```

The validator recomputes every claimed number from your raw traces using this
repository's committed scorers. It exits 0 only when the recompute matches your
claims to the digit. Running it on this template fails loudly by design — the
placeholder manifest claims a row that no corpus backs.

This directory is not validated by CI (it is skipped by name), so it is safe to
leave in place.
