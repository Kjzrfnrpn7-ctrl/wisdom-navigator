#!/usr/bin/env python3
"""Fetch public source items using a pinned, verified WorkBuddy parser.

Only load_sources, pull and norm_time are used. No clustering, keyword filters,
subscription matching, ranking, article generation or remote dispatch is run.
"""
from __future__ import annotations

import concurrent.futures
import datetime as dt
import hashlib
import importlib.util
import json
import os
import pathlib
import sys
import time
import urllib.request

UPSTREAM_REPO = "adsorgcn/WorkBuddy"
UPSTREAM_TAG = "v2.3.15"
UPSTREAM_COMMIT = "6efcffe70211080a18d4155c9f6739663b61a4b0"
BASE = (
    f"https://raw.githubusercontent.com/{UPSTREAM_REPO}/{UPSTREAM_COMMIT}/"
    "experts/ilang-wechat-awesome/skills/wechat-topic-hunter/scripts"
)
FILES = {
    "hot_sources.py": "f3c247ca2cb61f14d1df09216e61c214a2f6d0f8e8d5a6121277fae3eab47501",
    "sources.json": "8c9a2ed3196cc3708e427779fd99cdb0957423c970551ca13d9e4e25e2472af2",
}
ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = ROOT / ".collector"
OUT = ROOT / "data" / "raw"
PER_SOURCE_LIMIT = 8
WORKERS = 8


def download_verified(name: str, digest: str, cache: pathlib.Path) -> None:
    request = urllib.request.Request(
        f"{BASE}/{name}", headers={"User-Agent": "KJ-Information-Collector/0.2"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise ValueError(f"Upstream file exceeds size limit: {name}")
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError(f"Upstream SHA-256 mismatch: {name}")
    (cache / name).write_bytes(data)


def load_upstream(cache: pathlib.Path):
    cache.mkdir(parents=True, exist_ok=True)
    for name, digest in FILES.items():
        download_verified(name, digest, cache)
    spec = importlib.util.spec_from_file_location("kj_upstream_acquisition", cache / "hot_sources.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load verified acquisition module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def classify(items: list, note: str) -> str:
    if note.startswith("配置坏了"):
        return "config_error"
    if note.startswith("打不开"):
        return "fetch_error"
    if note.startswith("解析失败"):
        return "parse_error"
    # The upstream parser may swallow malformed payloads and return []. Do not
    # describe an empty list as a verified successful/empty upstream response.
    return "items" if items else "empty_or_unparsed"


def collect_one(module, source: dict) -> dict:
    start = time.monotonic()
    try:
        _, items, note = module.pull(source, PER_SOURCE_LIMIT)
        status = classify(items, note)
        rows = [
            {"title": title, "url": url, "time": module.norm_time(raw_time), "raw_time": raw_time}
            for title, url, raw_time in items
        ]
    except Exception as exc:
        rows, status, note = [], "collector_error", f"{type(exc).__name__}: {exc}"
    return {
        "source": source["name"],
        "source_url": source.get("url"),
        "source_type": source.get("type", "rss"),
        "group": source.get("group"),
        "platform": source.get("platform"),
        "lang": source.get("lang"),
        "fallback_for": source.get("fallback_for"),
        "status": status,
        "note": note,
        "elapsed_seconds": round(time.monotonic() - start, 3),
        "items": rows,
    }


def summarize(results: list[dict], configured: int, disabled: int) -> dict:
    counts = {key: 0 for key in (
        "items", "empty_or_unparsed", "fetch_error", "parse_error", "config_error", "collector_error"
    )}
    for row in results:
        counts[row["status"]] += 1
    item_count = sum(len(row["items"]) for row in results)
    failures = sum(counts[key] for key in ("fetch_error", "parse_error", "config_error", "collector_error"))
    status = "failed" if not item_count else "partial" if failures or counts["empty_or_unparsed"] else "ok"
    return {
        "status": status,
        "configured_sources": configured,
        "disabled_sources": disabled,
        "attempted_sources": len(results),
        "source_records": len(results),
        "sources_with_items": counts["items"],
        "sources_empty_or_unparsed": counts["empty_or_unparsed"],
        "failed_sources": failures,
        "source_status_counts": counts,
        "item_count": item_count,
        "item_count_is_unique": False,
        "source_results": [
            {"source": row["source"], "status": row["status"], "item_count": len(row["items"]), "note": row["note"]}
            for row in results
        ],
    }


def write_outputs(results: list[dict], metadata: dict, output: pathlib.Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.fromisoformat(metadata["collected_at_utc"]).strftime("%Y-%m-%dT%H-%M-%S-%fZ")
    payload = json.dumps(results, ensure_ascii=False, indent=1) + "\n"
    meta = json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    for name, content in (
        ("latest.json", payload), (f"{stamp}.json", payload),
        ("meta.json", meta), (f"{stamp}.meta.json", meta),
    ):
        temporary = output / f".{name}.tmp"
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(output / name)


def main() -> int:
    started = dt.datetime.now(dt.timezone.utc)
    metadata = {
        "schema_version": 1,
        "started_at_utc": started.isoformat(),
        "upstream_repo": UPSTREAM_REPO,
        "upstream_tag": UPSTREAM_TAG,
        "upstream_commit": UPSTREAM_COMMIT,
        "upstream_sha256": FILES,
        "per_source_limit": PER_SOURCE_LIMIT,
        "workers": WORKERS,
        "mode": "public source acquisition; no clustering, topic selection, writing or dispatch",
        "normalized_time_format": "MM-DD HH:MM in runner local timezone; raw_time retained",
        "runner_timezone": list(time.tzname),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "collector_commit": os.environ.get("GITHUB_SHA"),
    }
    results = []
    try:
        module = load_upstream(CACHE)
        catalogue = json.loads((CACHE / "sources.json").read_text(encoding="utf-8"))
        configured = catalogue["sources"]
        sources = module.load_sources(str(CACHE / "sources.json"))
        with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as executor:
            results = list(executor.map(lambda source: collect_one(module, source), sources))
        # Keep every attempt, including fallback endpoints, for honest accounting.
        # No upstream CLI, drop_fallbacks, cluster, load_words or match_group call.
        metadata.update(summarize(results, len(configured), len(configured) - len(sources)))
    except Exception as exc:
        metadata.update(summarize(results, 0, 0))
        metadata.update(status="failed", fatal_error=f"{type(exc).__name__}: {exc}")
    ended = dt.datetime.now(dt.timezone.utc)
    metadata["collected_at_utc"] = ended.isoformat()
    metadata["duration_seconds"] = round((ended - started).total_seconds(), 3)
    write_outputs(results, metadata, OUT)
    print(json.dumps(metadata, ensure_ascii=False))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(
                f"Collection status: {metadata['status']}\n\n"
                f"Sources attempted: {metadata['attempted_sources']}; with items: {metadata['sources_with_items']}; "
                f"failed: {metadata['failed_sources']}; empty or unparsed: {metadata['sources_empty_or_unparsed']}.\n\n"
                f"Item records: {metadata['item_count']} (not cross-source deduplicated).\n"
            )
    return 1 if metadata["status"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
