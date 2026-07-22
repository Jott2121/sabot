# Normalization rule (shared by T2 and T5 string checks)

Every substring / verbatim-quote comparison in the task suite is performed on
**normalized** text so that trivial whitespace differences never decide a PASS/FAIL.
The algorithm is pinned here once; T2 and T5 reference it rather than restating it.

## Whitespace normalization (`normalize`)
Given a string `s`:
1. Replace every maximal run of whitespace with a single ASCII space (`U+0020`).
   "Whitespace" is the Python regex `\s` class on `str` patterns, which matches ASCII
   space, tab, newline, carriage return, form feed, vertical tab, **and** Unicode
   whitespace including the non-breaking space `U+00A0`.
2. Strip leading and trailing spaces.

Reference implementation (the definition, not merely an example):

```python
import re
def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()
```

## Case handling
A check described as **case-insensitive** additionally applies `str.lower()` to both
sides after `normalize`; a check described as **verbatim** does not (case must match).

## Containment
"`x` appears in `y`" / "`x` is a substring of `y`" means
`normalize(x) in normalize(y)` (with `.lower()` on both sides when the check is
case-insensitive). No other transformation (punctuation folding, unicode NFC, quote
straightening) is applied — callers must supply strings already in the corpus's exact
punctuation.
