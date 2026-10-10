# Public source candidate lab

An isolated validation experiment, not part of the deployed collector. Standard library only. No schedules, credentials, cookies, login, source installation, redirect following, challenge solving, retries, publication, or data writeback.

## Run

```sh
python -m unittest discover -s collector_candidate_lab/tests -v
python collector_candidate_lab/validate_sources.py collector_candidate_lab/candidates.json --output candidate-results
# Only after the candidate batch is approved for public reads:
python collector_candidate_lab/validate_sources.py collector_candidate_lab/candidates.json --output candidate-results --live
```

The first command runs offline tests. The second validates the manifest without network. The third makes at most one GET per candidate, serially, to HTTPS port 443. Use a new output directory to avoid overwriting evidence. A completed laboratory run can report failed candidates and still exit zero; inspect `summary.json` rather than the workflow badge. This is intentional: an unavailable source is an observed result, not a reason to loop or retry.

Minimal standalone files (without optional upstream comparison): `validate_sources.py`, `candidates.json`, `tests/test_validate_sources.py`. Keep their directory layout. `README.md` can accompany them. No package installation is required. The local audited WorkBuddy parser is optional; if available under `vendor/hot_sources.py` inside this lab, its SHA-256 must match before an offline comparison is loaded. If absent, standalone validation still works and the comparison is explicitly unavailable. No upstream code is downloaded.

## Safety and scope

- Only explicit, researched JSON endpoints in the local manifest are fetched. Maximum five per run; current manifest has three.
- Endpoint URL rejects credentials, credential-like query parameters, local/private hosts, unusual ports, and non-HTTPS protocols.
- Resolve all DNS answers first and require all to be globally routable. Connect to one validated IP without re-resolving; TLS validates the original hostname with system trust. No proxies, custom CA relaxation, or alternate IP retries.
- No cookies or authorization headers are sent, saved, or reused. Response headers exclude `Set-Cookie`.
- Redirects are recorded but never followed. Responses stop at 2 MiB + 1 byte. Linked item pages are not fetched.
- Results preserve source identity (direct versus aggregator), source times separately from item times, the original JSON time value/type and its source field, and title/link quality.
- Templates explicitly labeled `documented_template` can form known human-readable story links. A syntactically valid link is not a successful visit or verified publication.
- Explicit item-list paths stop wrapper titles, missing arrays, parse failures, and error envelopes being reported as successful empty feeds.
- No full article body is fetched by the three selected candidates. Raw endpoint payloads are local audit evidence and should not be published as public repo data. Artifact retention should be short.
- A source or parser returning items does not prove accuracy, independence, freshness, copyright permission, or sustained availability. Same-platform alternate endpoints are not independent corroboration.

## Status meanings

- `items`: explicit list parsed to one or more usable titles; inspect quality warnings
- `empty_verified`: declared list exists and is empty, and declared API success checks passed
- `empty_body`: HTTP success without a body; cannot call this a verified empty feed
- `blocked`: HTTP 401/403/407/429/451 or an HTML challenge marker; stop
- `redirect_not_followed`, `http_error`, `unsupported_encoding`, `response_too_large`: observed transport/content issue
- `parser_error`: payload is not valid JSON
- `schema_error`: required list path missing or wrong type
- `upstream_error`: declared API success field missing or rejected
- `quality_error`: nonempty list produced no usable titles
- `dns_error`: local DNS failure before an HTTP request; says nothing about source availability
- `fetch_error`: transport exception; inspect the exact error
- `safety_blocked`: URL/DNS safety guard refused the action
- `lab_error`: unexpected local validation error

## Current local evidence

On 2026-10-10, offline tests pass. Local attempts, including the supported approved-network execution, stopped at DNS resolution for all three hosts; zero HTTP responses were observed. The original version 0.1 evidence labels this broad `fetch_error`, with exact `gaierror` messages; version 0.2 explicitly uses `dns_error`. These are environment failures, not blocked-source findings. Do not repeatedly retry locally. A separate authorized public-network runner is needed for actual endpoint evidence.

The deployed source files were hashed before and after; all unchanged. `evidence/baseline-link-quality.json` is an offline audit of the existing verified run: its eight Zhihu records link to an API endpoint; its eight NewsNow Douyin records have no item time. The proposed Zhihu reader-page mapping is diagnostic only and has not changed deployed data.
