# Name-collision check — "Sabot" — 2026-07-22

Queries run:
1. `"sabot" software testing tool`
2. `"sabot" github AI OR agent OR LLM`
3. `sabot benchmark OR framework site:github.com`
4. `"sabot score"`

(Plus targeted follow-ups to confirm/rule out specific hits surfaced by the above:
"Apache Arrow Sabot Java streaming library", `"sabot" pypi package`, django-sabot
maintenance status via libraries.io, tomitribe/sabot via GitHub, sabotchain.com
via web search, and "Sabot AI agent fault detection scoring 2026" to check the
project's actual field directly.)

## Findings (software-project hits only)

1. **django-sabot** — https://pypi.org/project/django-sabot/ (source on GitHub,
   Tomitribe unrelated author). A Django testing utility: "Provoke predictable
   errors in your Django projects" — raises `OperationalError`s to test failure
   tolerance / database-connection handling. This is the most collision-adjacent
   hit: it's literally a *testing* tool named "sabot," thematically close
   (fault-injection testing vs. this project's fault-detection scoring).
   However: single release, v0.1.0, dated 2015-07-20, no subsequent versions,
   0 forks, 1 contributor — dormant for roughly a decade, not an active project.

2. **tomitribe/sabot** — https://github.com/tomitribe/sabot — "Environment-aware
   CDI-based Configuration," a Java dependency-injection configuration extension
   maintained by the Tomitribe org (Apache TomEE contributors). Named after
   Antoine Sabot-Durand (CDI spec lead), i.e. a surname, not a chosen brand.
   Per the GitHub repo page: 6 stars, 6 forks, no visible recent commit
   activity — dormant/minimally maintained. Not in the testing/AI/agents space
   (it's a config-injection library).

3. **sabotchain.com** — https://www.sabotchain.com/ — "Sabot | Secure
   Peer-to-Peer Transactions." A consumer-facing crypto/blockchain P2P
   marketplace-safety product with "AI-powered fraud detection," identity
   verification, and a "Trust Score System." Appears active. Domain overlap is
   SEO-adjacent only (both use "AI" + "score" language) — it is a consumer
   marketplace-safety product, not a dev tool, testing framework, or
   AI-agent/LLM framework. No overlap with dev-tools distribution channels
   (not on PyPI/npm/GitHub as a library).

4. **julianueno/Sabot** — https://github.com/julianueno/Sabot — an app for gig-
   economy delivery drivers (labor-conditions data collection). Unrelated
   domain, coincidental name reuse.

5. **froscon/SaBoT** — https://github.com/froscon/SaBoT — "FrOSCon (S)ponsoring
   (a)nd (Bo)oth (T)oolkit," a conference sponsorship/booth management tool.
   Acronym-derived name, unrelated domain.

6. **ManonSabot** (GitHub user) — https://github.com/ManonSabot — repository is
   the author's surname; contains code for a vegetation-resilience research
   paper (Sabot et al. 2022). Not a product name, unrelated domain.

7. No active AI-agent evaluation, LLM-eval, or fault-detection/scoring tool
   named "Sabot" was found when searching the project's actual 2026 field
   directly (query: "Sabot AI agent fault detection scoring 2026" — returned
   Confident AI, Galileo, AgentOps, Langfuse, etc., no "Sabot").

8. Could not confirm an "Apache Arrow Sabot" Java library exists (searched
   directly; no evidence found in Apache Arrow's docs, GitHub orgs, or
   coverage). Noting this as unconfirmed rather than asserting it — earlier
   mention of it as a possible generic/archived precedent was not corroborated
   by search and should not be cited as fact going forward.

## Non-blocking generic uses (per rule)

- Sabot (footwear) — https://en.wikipedia.org/wiki/Sabot_(shoe)
- Sabot (firearms/ammunition, incl. muzzleloader forum threads) —
  https://en.wikipedia.org/wiki/Sabot_(firearms)
- Scrabble/dictionary word-lookup pages (anagrammer.com, Collins,
  Merriam-Webster, simplyscrabble.com)
- "The Saboteur" (2010 video game) — unrelated word root, not a collision

## Verdict

**GO**

## Rule applied

Collision = an active software project in testing/AI/agents named Sabot, or any
trademark in dev tools. Generic uses (ammunition, footwear, dictionary/Scrabble
entries) are noted but non-blocking. No active project in the testing, AI, or
agent-framework space was found using "Sabot" as its name. No evidence of a
registered trademark was found in web search; this was not checked against a
trademark registry (e.g., USPTO) directly, so absence of web hits is not
asserted as proof of absence of a registered mark. The two dev-tools-adjacent hits
(django-sabot, tomitribe/sabot) are both dormant (single release ~2015 /
minimal-activity Java lib named after a person's surname) and neither is in
this project's field (AI-agent fault-detection scoring). sabotchain.com is
SEO-muddle only — a consumer P2P-marketplace safety product with "AI" and
"score" language, not a dev tool or testing/agent framework — which per the
oracle-gate precedent (mild SEO overlap, no active dev-tools collision) is a
GO with a note, not a blocker.
