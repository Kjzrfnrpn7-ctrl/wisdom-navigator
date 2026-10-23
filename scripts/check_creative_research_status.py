#!/usr/bin/env python3
"""Check public R1 summaries against the latest complete milestone (stdlib only).

Use --write to refresh marked blocks. Historical checkpoints are not rewritten.
This checks documented consistency, not source-case validity or Canon eligibility.
"""

import argparse
from datetime import date
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path("projects/creative-system-research")
BEGIN = "<!-- R1_STATUS:START -->"
END = "<!-- R1_STATUS:END -->"
CURRENT = ("STATUS.md", "README.md", "ROADMAP.md")


def one(pattern, text, label):
    matches = list(re.finditer(pattern, text, re.MULTILINE))
    if len(matches) != 1:
        raise ValueError(f"{label}: expected one match, found {len(matches)}")
    return matches[0]


def latest_snapshot(root):
    text = (root / PROJECT / "MILESTONES.md").read_text(encoding="utf-8")
    headings = list(re.finditer(r"^## (\d{4}-\d{2}-\d{2}) — (.+)$", text, re.M))
    if not headings:
        raise ValueError("MILESTONES.md: no dated milestone")
    dates = [date.fromisoformat(h[1]) for h in headings]
    if dates != sorted(dates):
        raise ValueError("Milestones must remain chronological; same-day checkpoints use file order")
    last = headings[-1]
    body = text[last.end():]
    if not re.search(r"^Status: \*\*Complete\*\*$", body, re.M):
        raise ValueError("Latest milestone is not complete; do not silently fall back to an older one")
    cases = one(r"^- Independent professional cases: \*\*(\d+) / (\d+) \(([\d.]+)%\)\*\*$", body, "cases")
    count, target, percent = int(cases[1]), int(cases[2]), float(cases[3])
    remaining = int(one(r"^- R1 remaining: \*\*(\d+)\*\*$", body, "remaining")[1])
    cluster = one(r"^- Longitudinal creator cluster: \*\*(\d+) / (\d+)\*\*, tracked separately$", body, "separate cluster")
    if target != 200 or not 0 <= count <= target or count + remaining != target:
        raise ValueError("R1 count + remaining must equal the independent 200-case target")
    if abs(percent - round(100 * count / target, 1)) > 0.0001:
        raise ValueError("R1 percentage does not match its independent-case count")
    if (int(cluster[1]), int(cluster[2])) != (89, 89):
        raise ValueError("The separate 89-work creator sample must not be merged into R1")
    primitives = int(one(r"^- Executable primitives: \*\*(\d+)\*\*$", body, "primitives")[1])
    canon = int(one(r"^- Canon promotions: \*\*(\d+)\*\*$", body, "Canon")[1])
    batches = one(r"^- Contract-standard visible maps from B(\d+)–B(\d+): \*\*(\d+)\*\*$", body, "batch maps")
    first, last_batch, maps = map(int, batches.groups())
    if first != 4 or last_batch < first or maps != (last_batch - first + 1) * 4:
        raise ValueError("B04 onward: completed batch range must agree with four visible maps per batch")
    # B03 is a historical subtotal, not a stale current count. Later default
    # batches add ten cases each; the creator sample is deliberately excluded.
    b03 = (root / PROJECT / "R1_BATCH_03.md").read_text(encoding="utf-8")
    subtotal = int(one(r"^\*\*R1 total after batch:\*\* (\d+) / 200 independent professional cases", b03, "B03 subtotal")[1])
    if count != subtotal + (last_batch - first + 1) * 10:
        raise ValueError("Latest count disagrees with B03 subtotal + completed default batches")
    coverage = int(one(r"^- (\d+)-case Coverage Map$", body, "completed Coverage Map")[1])
    delta = int(one(r"^- ~(\d+)-case Mechanism Tree Delta$", body, "completed Tree Delta")[1])
    if coverage > count or delta > count:
        raise ValueError("Completed periodic maps cannot exceed the recorded case count")
    candidate_section = one(r"^### Candidate changes\n([\s\S]*?)(?=^### |\Z)", body, "candidate changes")[1]
    candidates = re.findall(r"^- \*\*([A-H]-P\d+ .+?) → (Priority Candidate|Strong Candidate|Candidate)\*\*$", candidate_section, re.M)
    if not candidates or len({name.split()[0] for name, _ in candidates}) != len(candidates):
        raise ValueError("Candidate list is empty or contains duplicate primitive IDs")
    return dict(date=last[1], heading=last[2], count=count, target=target,
                percent=percent, remaining=remaining, primitives=primitives,
                canon=canon, first=first, last=last_batch, maps=maps,
                coverage=coverage, delta=delta, candidates=candidates)


def render(s):
    stage = "closure in progress; not complete" if s["remaining"] else "case target reached; closure review pending"
    lines = [BEGIN,
             "<!-- Generated from the latest complete MILESTONES.md entry; do not edit by hand. -->",
             f"**Research evidence as of:** {s['date']} — {s['heading']}", "",
             f"**Research gate:** R1 — Foundation taxonomy / {stage}", "",
             f"- Independent professional cases: **{s['count']} / {s['target']} ({s['percent']:.1f}%)**",
             f"- R1 remaining: **{s['remaining']}**",
             "- Longitudinal creator cluster: **89 / 89**, tracked separately; excluded from the 200-case target",
             f"- Executable primitives: **{s['primitives']}**",
             f"- Canon promotions: **{s['canon']}**",
             f"- Visible-map batches: **B{s['first']:02d}–B{s['last']:02d}** ({s['last'] - s['first'] + 1} batches; **{s['maps']}** contract-standard maps)",
             f"- Latest completed Coverage Map: **{s['coverage']}-case**",
             f"- Latest completed Mechanism Tree Delta: **~{s['delta']}-case**", "",
             "Candidate status recorded at this milestone:", ""]
    lines.extend(f"- **{name} — {status}**" for name, status in s["candidates"])
    lines += ["", "Source: [MILESTONES.md](MILESTONES.md). This is the latest recorded research",
              "checkpoint, not a claim of new research on the date a status page is edited.", END]
    return "\n".join(lines)


def check(root, write=False):
    snapshot = latest_snapshot(root)
    expected = render(snapshot)
    errors = []
    for name in CURRENT:
        path = root / PROJECT / name
        text = path.read_text(encoding="utf-8")
        if text.count(BEGIN) != 1 or text.count(END) != 1:
            errors.append(f"{name}: missing or duplicate R1 status markers")
            continue
        start, end = text.index(BEGIN), text.index(END) + len(END)
        if start >= end:
            errors.append(f"{name}: reversed R1 status markers")
            continue
        if text[start:end] != expected:
            if write:
                text = text[:start] + expected + text[end:]
                path.write_text(text, encoding="utf-8")
                print(f"Updated {name}")
            else:
                errors.append(f"{name}: status block differs from the latest milestone; run with --write")
        # Catch common stale claims outside the generated block too. Historical
        # batch notes and older MILESTONES entries intentionally keep old totals.
        outside = text.split(BEGIN)[0] + text.split(END)[1]
        for count, target in re.findall(r"\b(\d+)\s*/\s*(200|89)\b", outside):
            wanted = snapshot["count"] if target == "200" else 89
            if int(count) != wanted:
                errors.append(f"{name}: stale count {count}/{target} outside generated block")
        patterns = [
            (r"(?i)remaining\s+\*{0,2}(\d+)", "remaining"),
            (r"(?i)\b(\d+)\*{0,2}\s+independent professional cases remain", "remaining"),
            (r"(?i)\b(\d+)\*{0,2}\s+(?:executable\s+)?primitives\b", "primitives"),
            (r"(?i)(?:primitive library|executable primitives|Canon promotions):\s*\*{0,2}(\d+)", None),
        ]
        for pattern, field in patterns:
            for match in re.finditer(pattern, outside):
                key = field or ("canon" if match[0].lower().startswith("canon") else "primitives")
                if int(match[1]) != snapshot[key]:
                    errors.append(f"{name}: conflicting {key}: {match[0]}")
        candidates = {name: status for name, status in snapshot["candidates"]}
        for name_status in re.findall(r"\*\*([A-H]-P\d+ .+?) (?:→|—) (Priority Candidate|Strong Candidate|Candidate|Canon)\*\*", outside):
            candidate, status = name_status
            if candidates.get(candidate) != status:
                errors.append(f"{name}: candidate differs from milestone: {candidate} / {status}")
    if errors:
        raise ValueError("\n".join(errors))
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="refresh marked blocks, preserving all historical records")
    args = parser.parse_args()
    try:
        s = check(ROOT, args.write)
    except (ValueError, OSError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"PASS: R1 {s['count']}/{s['target']}; remaining {s['remaining']}; "
          f"{s['primitives']} primitives; Canon {s['canon']}; evidence {s['date']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
