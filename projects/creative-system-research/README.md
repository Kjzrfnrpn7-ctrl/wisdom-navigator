# Creative Systems Research Program

**Priority:** P0 / Key Project  
**Status:** Active research  
**Scope:** cross-media creative mechanism research for video, graphic design,
language/copy, advertising, narrative, character, service and experience projects.

## Latest recorded progress

<!-- R1_STATUS:START -->
<!-- Generated from the latest complete MILESTONES.md entry; do not edit by hand. -->
**Research evidence as of:** 2026-10-16 — 150-case milestone

**Research gate:** R1 — Foundation taxonomy / closure in progress; not complete

- Independent professional cases: **153 / 200 (76.5%)**
- R1 remaining: **47**
- Longitudinal creator cluster: **89 / 89**, tracked separately; excluded from the 200-case target
- Executable primitives: **34**
- Canon promotions: **0**
- Visible-map batches: **B04–B12** (9 batches; **36** contract-standard maps)
- Latest completed Coverage Map: **150-case**
- Latest completed Mechanism Tree Delta: **~150-case**

Candidate status recorded at this milestone:

- **E-P04 Incentive Rewire — Strong Candidate**
- **E-P03 Alternative Evidence → Formal Access — Strong Candidate**
- **B-P05 Distributed Evidence Mosaic — Priority Candidate**
- **E-P05 Infrastructure / Asset → Operational Function — Strong Candidate**
- **H-P01 Language Form Embodies Function — Priority Candidate**

Source: [MILESTONES.md](MILESTONES.md). This is the latest recorded research
checkpoint, not a claim of new research on the date a status page is edited.
<!-- R1_STATUS:END -->

## Objective

Build a high-quality, evidence-grounded creative mechanism library that can:

- identify reusable mechanisms rather than copy styles;
- distinguish observed case facts from abstraction and new derivation;
- support cross-media transfer only after domain-specific revalidation;
- include strong cases, weak cases, counterexamples and failure modes;
- convert research into executable creative directions rather than a case archive.

## Core research loop

```text
SEARCH
→ DECONSTRUCT
→ PRIOR ART
→ SYMBOLIZE
→ DERIVE
→ PRESSURE TEST
→ ACTUAL OUTPUT
→ REVIEW / PROMOTE / PATCH / REJECT
```

The working rule is: **search once, deconstruct once, symbolize once**.
A batch is not complete when cases are only collected.

## Active batch contract

Default round:

```text
10 independent professional cases
→ 10 deconstructions
→ prior-art positioning
→ MAP-01 Batch Overview
→ MAP-02 Deep Distillation
→ MAP-03 Prior Art / Contrast
→ MAP-04 Derivation / Cross-domain
```

Every +30 independent cases adds a **Mechanism Tree Delta**.
Every +50 independent cases adds a **Coverage Map**.

See [VISUAL_RESEARCH_CONTRACT.md](VISUAL_RESEARCH_CONTRACT.md).

## R1 maturity gate

Target:

- **200 independent professional cases**
- plus **one 89-work longitudinal creator cluster**

The 89-work creator cluster is one longitudinal sample and does not fill the
200 independent-case target.

R1 is used to establish:

- first stable mechanism taxonomy;
- executable primitive library;
- prior-art distance and novelty discipline;
- failure / counterexample corpus;
- visible symbol-map research interface;
- cross-domain transfer boundaries.

## Evidence rules

- External cases are **reference evidence**, not proof of our own capability.
- Keep **Observed / Abstracted / Derived** separate.
- Prior art is checked before calling a mechanism novel.
- One case cannot promote a general rule.
- Negative evidence is required.
- AI usage and AI necessity are evaluated separately.
- Actual output, regression and human review outrank document completeness.

## R1 closure steering

At the recorded checkpoint, the project is in R1 closure mode. Priority gaps:

1. Latin America and South / Southeast Asia coverage;
2. non-English long-form copy, titles and dialogue;
3. non-award B2B / manufacturing / software evidence;
4. ordinary low-gain and mechanism-valid-but-execution-failed examples;
5. normalize the original 18 anchors plus early negative set to the same prior-art scale;
6. begin 2–3 representative Actual Take pressure tests.

## Public-repository boundary

This repository records only public-safe research status, maturity targets,
visual-research rules and milestone summaries.

Proprietary internal architecture, private runtime structures, unpublished
framework internals and sensitive implementation details are intentionally not
published here.

## Periodic-map follow-up

The latest completed periodic maps are listed in the generated summary above.
The ~90-case Tree Delta was recovered from a historical ledger snapshot; it was
not backdated. The 100-case Coverage Map and ~120-case Tree Delta are also complete.

Under the visual research contract, the next Tree Delta is due around 180 cases,
then the final Coverage Map at 200 cases and 3–5 R1 synthesis maps. These remain
future work, not newly completed outputs.

## Milestones

See [MILESTONES.md](MILESTONES.md).

## Status maintenance

`MILESTONES.md` is the dated source for the current R1 summary. Older milestones
and batch notes remain historical snapshots. Do not replace their totals with
today's count or treat their old task lists as current instructions.

For an evidence-backed change, append a complete cumulative milestone with its
actual research date and supporting records. Preserve the separate 89-work
creator sample, candidate grades and Canon evidence boundary. Then run:

```sh
python scripts/check_creative_research_status.py --write
python scripts/check_creative_research_status.py
python -m unittest discover -s scripts/tests -v
```

The first command refreshes only the marked blocks in STATUS, README and ROADMAP.
Review the remaining prose and open checklists too: the checker catches summary
drift, arithmetic errors, batch/map inconsistencies and common conflicting counts
or candidate grades outside the blocks. It does not certify case quality, test
completion, all prose claims or Canon eligibility. If a later batch uses an
exception to the default ten-case contract, record that evidence and adapt the
batch-accounting check before accepting a new total.

The read-only GitHub Actions check runs on pushes and pull requests affecting
this project, the checker/tests, root README or its workflow. It also runs offline
without third-party packages. A documentation reconciliation date must never
replace the research evidence date.
