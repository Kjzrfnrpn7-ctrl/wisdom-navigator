# wisdom-navigator

## KJ Information Collector

A small GitHub Actions collector for public RSS, JSON, JavaScript data and HTML
endpoints. Python 3.12 standard library only; no API keys or third-party Python
packages are needed.

The workflow runs at 00:17, 06:17, 12:17 and 18:17 UTC, on manual dispatch, and
on changes to `collector/**` or its workflow on `main`. GitHub may delay scheduled
runs. Data-only commits do not trigger another collection run.

### Scope and provenance

The acquisition parser and 84-source catalogue come from WorkBuddy `v2.3.15`,
pinned to commit `6efcffe70211080a18d4155c9f6739663b61a4b0` and verified by
SHA-256 before use. Public sources span AI, technology, trending lists, finance,
products, overseas news and search trends. Some sources are third-party
aggregators, including NewsNow; they are not all original publisher endpoints.

Only source loading, acquisition and time normalization are called. No topic
ranking, cross-source event clustering, subscription matching, article writing
or external content publishing is performed. Upstream parsing still strips
markup, filters date-only/junk titles, deduplicates some titles within a source,
and keeps at most eight items per endpoint. These are parsed item records, not
full response bodies or verified facts. See [the upstream notice](collector/NOTICE.md).

### Outputs

- `data/raw/latest.json`: one record per attempted endpoint, including errors
- `data/raw/meta.json`: provenance, run identifiers, counts and per-source status
- Timestamped `.json` and `.meta.json` pairs: item and metadata snapshots
- GitHub Actions artifact: collection outputs and diagnostics, retained 14 days

Each source row includes its endpoint, parser type, platform, language, optional
fallback relationship, status, diagnostic note, elapsed seconds and items.
Items include `title`, `url`, upstream-normalized `time` and unchanged `raw_time`.
Normalized times omit the year and timezone; the workflow uses UTC and keeps the
raw value for later interpretation. URLs or timestamps can be absent upstream.

All enabled endpoints are attempted, including fallback endpoints. Counts are
item records, not unique stories, and fallback/aggregator records may duplicate
other sources. Endpoint success is not independent-source corroboration.

### Status and failure semantics

- `items`: the parser produced one or more records
- `empty_or_unparsed`: no records; this can be a genuinely empty feed, filtering,
  an HTML block page, a changed schema, or a parsing failure swallowed upstream
- `fetch_error`, `parse_error`, `config_error`, `collector_error`: observed failure

The run is `ok` only when every attempted source produces items; `partial` when
some produce items and others fail or are empty/unparsed; and `failed` when no
items are collected or bootstrap fails. A green workflow can therefore contain
a `partial` collection: inspect `meta.json`, not just the Actions badge.

A failed collection exits nonzero and retains diagnostic artifacts, but does
not overwrite previously committed data. On partial/ok runs, a separate job
commits the JSON output. The collector has read-only repository permission and
no persisted checkout credential. Only the publishing job has `contents: write`;
it does not run the downloaded acquisition code.

### Local checks

Run `python -m unittest discover -s collector/tests -v` for offline tests.
Run `python collector/run_collector.py` for live acquisition from public sources.
Snapshots in Git history accumulate over time; no automatic deletion is enabled.

## Current P0 research project

A public-safe project charter for the active cross-media creative-systems research
program is tracked under
[`projects/creative-system-research/`](projects/creative-system-research/README.md).

The public repository contains research scope, maturity gates and evidence policy
only. Proprietary internal architecture, private runtime details and unpublished
system internals are intentionally excluded.
