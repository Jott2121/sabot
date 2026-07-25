# Wave-2 build notes (2026-07-23) — carry into the wave-2 paper

Internally independent adversarial review of the v0.2 build (commits 1207640, 66eacd3,
4850d2d) — a separate reviewing agent working from the spec, same project and
authorship, not third-party external review —
CLEARED the paid run: no frozen-behavior violation, ANCHORS_V2
character-exact vs SPEC 10.4, money path sound. Three non-blocking items to
carry forward honestly:

1. **O4 pairing caveat (methods/limitations).** The O4 landing probe can
   newly exclude wave-2 O4 cells that wave 1 counted, so O4-row side-by-side
   rates are not strictly paired; the scoreboard now carries this note and a
   strict paired recompute must filter both waves to wave-2-valid cells
   (wave2-rows.json retains per-cell wave1_hard/wave1_excluded).
2. **None-form regex divergence (disclose, conservative).** The implemented
   non-flag forms (`probe.py _NONE_RE`) also match "no anomaly(,/ies)
   noticed" variants beyond SPEC 10.2's literal list. Every extra match
   scores a line as a NON-flag — bias against the hypothesis, never for it.
   Character-level spec-vs-code divergence, disclosed rather than re-tagged.
3. **Breaker calibration (ops).** Real-vs-margined factor confirmed 1.171
   (dashboard $60 / margined ledger $51.25); worst-case breaker trip at $38
   margined ~ $44.5 real, inside the $47 wallet. Residual amplifiers (retry
   past a trip, concurrent writers racing the cap check) are bounded well
   under $1; drivers run with at most two concurrent writers.

Thin test spots noted by review (non-blocking): langgraph one-shot model-id
stamp not tested against a non-adjacent interposed agent-msg; none-form list
not pinned character-for-character.
