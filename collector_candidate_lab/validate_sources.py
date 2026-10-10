#!/usr/bin/env python3
"""One-shot, public HTTPS candidate validation; Python standard library only.

No cookies, credentials, redirects, retries, proxy use, browser execution,
linked-page fetching, source installation, publishing, or production writes.
An explicit JSON item-list path is required: malformed data is never empty.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import http.client
import importlib.util
import ipaddress
import json
import pathlib
import re
import socket
import ssl
import sys
import time
import urllib.parse
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent
UPSTREAM = HERE / "vendor" / "hot_sources.py"
UPSTREAM_SHA256 = "f3c247ca2cb61f14d1df09216e61c214a2f6d0f8e8d5a6121277fae3eab47501"
MAX_BYTES = 2 * 1024 * 1024
TIMEOUT = 12
MAX_SOURCES = 5
SECRET_KEYS = re.compile(r"(^|[_-])(token|password|passwd|secret|cookie|authorization|api[_-]?key)($|[_-])", re.I)
BLOCK_MARKERS = re.compile(r"captcha|verify you are human|access denied|security check|安全验证|访问过于频繁|请完成验证|验证码", re.I)
MISSING = object()


class SafetyError(ValueError):
    pass


def load_upstream():
    """Use only an already-audited, hash-pinned local parser, never download code."""
    if not UPSTREAM.exists():
        return None
    if hashlib.sha256(UPSTREAM.read_bytes()).hexdigest() != UPSTREAM_SHA256:
        raise SafetyError("Audited local upstream parser SHA-256 mismatch")
    spec = importlib.util.spec_from_file_location("lab_pinned_upstream", UPSTREAM)
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def value_at(obj, path):
    value = obj
    for key in path.split(".") if path else []:
        if not isinstance(value, dict) or key not in value:
            return MISSING
        value = value[key]
    return value


def first_at(obj, paths):
    for path in paths:
        value = value_at(obj, path)
        if value is not MISSING and value is not None and value != "":
            return value, path
    return None, None


def safe_url(url, endpoint=False):
    """Syntax-only guard. Item links are inspected, never resolved or fetched."""
    try:
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in ({"https"} if endpoint else {"http", "https"}):
            raise SafetyError("Unsupported URL scheme")
        if not parts.hostname or parts.username or parts.password or parts.fragment:
            raise SafetyError("Missing host, userinfo, or fragment in URL")
        if parts.port not in (None, 443) and endpoint:
            raise SafetyError("Only HTTPS port 443 is allowed")
        if any(ord(char) < 32 or char == "\\" for char in url):
            raise SafetyError("Control character or backslash in URL")
        host = parts.hostname.rstrip(".").lower()
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            raise SafetyError("Local/private host is forbidden")
        try:
            addr = ipaddress.ip_address(host)
        except ValueError:
            if "." not in host:
                raise SafetyError("Unqualified host is forbidden")
        else:
            if not addr.is_global:
                raise SafetyError("Non-public IP is forbidden")
        if endpoint and any(SECRET_KEYS.search(k) for k, _ in urllib.parse.parse_qsl(parts.query)):
            raise SafetyError("Credential-like query parameter is forbidden")
        return parts
    except (TypeError, ValueError) as exc:
        raise SafetyError(str(exc)) from exc


def resolve_public(host):
    addresses = list(dict.fromkeys(row[4][0] for row in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)))
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise SafetyError("Endpoint DNS did not resolve exclusively to public IPs")
    return addresses


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Connect only to a validated public IP; TLS still verifies original host."""
    def __init__(self, host, ip):
        super().__init__(host, timeout=TIMEOUT, context=ssl.create_default_context())
        self.pinned_ip = ip

    def connect(self):
        sock = socket.create_connection((self.pinned_ip, 443), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


def fetch_public(url):
    parts = safe_url(url, endpoint=True)
    addresses = resolve_public(parts.hostname)
    connection = PinnedHTTPSConnection(parts.hostname, addresses[0])
    began = time.monotonic()
    try:
        path = urllib.parse.urlunsplit(("", "", parts.path or "/", parts.query, ""))
        connection.request("GET", path, headers={
            "User-Agent": "KJ-Candidate-Lab/0.1 (public-read-only validation)",
            "Accept": "application/json", "Accept-Encoding": "identity", "Connection": "close",
        })
        response = connection.getresponse()
        raw = response.read(MAX_BYTES + 1)
        metadata = {
            "http_status": response.status,
            "response_headers": {k.lower(): v for k, v in response.getheaders()
                if k.lower() in {"content-type", "content-encoding", "content-length", "date", "cache-control", "retry-after", "location"}},
            "resolved_public_addresses": addresses,
            "connected_public_address": addresses[0],
            "elapsed_seconds": round(time.monotonic() - began, 3),
            "response_bytes": len(raw),
        }
        return metadata, raw
    finally:
        connection.close()


def link_quality(url, allowed_hosts):
    if not url:
        return "missing"
    try:
        parts = safe_url(url)
    except SafetyError:
        return "unsafe_or_invalid"
    host = parts.hostname.lower()
    if allowed_hosts and not any(host == h or host.endswith("." + h) for h in allowed_hosts):
        return "off_platform"
    if host.startswith("api.") or "/api/" in parts.path:
        return "api_link_not_reader_page"
    return "syntactically_valid_platform_link"


def make_link(row, spec):
    url, field = first_at(row, spec.get("url_fields", ["url"]))
    if isinstance(url, str):
        return url.strip(), "payload:" + field
    template = spec.get("url_template")
    if template:
        values = {}
        for name, path in spec.get("url_template_fields", {}).items():
            v = value_at(row, path)
            if v is MISSING or not isinstance(v, (str, int)) or isinstance(v, bool) or str(v) == "":
                return "", "missing_template_field:" + path
            values[name] = urllib.parse.quote(str(v), safe="")
        return template.format(**values), "documented_template"
    return "", "missing"


def parse_response(source, metadata, raw, upstream):
    result = {"status": None, "note": "", "items": [], "schema": {}, "quality": {}}
    status = metadata["http_status"]
    headers = metadata.get("response_headers", {})
    content_type = headers.get("content-type", "")
    if status in (401, 403, 407, 429, 451):
        return dict(result, status="blocked", note=f"HTTP {status}; no retry or challenge handling")
    if 300 <= status < 400:
        return dict(result, status="redirect_not_followed", note="Location saved; redirect not followed")
    if not 200 <= status < 300:
        return dict(result, status="http_error", note=f"HTTP {status}")
    if len(raw) > MAX_BYTES:
        return dict(result, status="response_too_large", note="Response exceeded 2 MiB cap")
    if not raw.strip():
        return dict(result, status="empty_body", note="HTTP success with no body; not a verified empty feed")
    if headers.get("content-encoding", "identity").lower() not in ("identity", ""):
        return dict(result, status="unsupported_encoding", note="Unexpected content encoding; no decompression attempted")
    text = raw.decode("utf-8-sig", "replace")
    looks_html = "html" in content_type.lower() or text.lstrip().startswith(("<!DOCTYPE", "<!doctype", "<html"))
    if looks_html:
        blocked = bool(BLOCK_MARKERS.search(text[:200000]))
        return dict(result, status="blocked" if blocked else "unexpected_html", note="HTML challenge markers" if blocked else "JSON endpoint returned HTML")
    try:
        data = json.loads(text)
    except (ValueError, RecursionError) as exc:
        return dict(result, status="parser_error", note=f"JSON {type(exc).__name__}: {str(exc)[:180]}")
    result["schema"] = {"root_type": type(data).__name__, "top_level_keys": list(data)[:40] if isinstance(data, dict) else [], "items_path": source["items_path"]}
    for check in source.get("success_checks", []):
        v = value_at(data, check["path"])
        if v is MISSING or v not in check["accepted"]:
            return dict(result, status="upstream_error", note=f"API success field {check['path']} missing or rejected", api_status=None if v is MISSING else v)
    rows = value_at(data, source["items_path"])
    if not isinstance(rows, list):
        return dict(result, status="schema_error", note="Required item-list path is missing or is not an array")
    result["schema"]["raw_list_count"] = len(rows)
    result["source_times"] = {path: value_at(data, path) for path in source.get("source_time_fields", []) if value_at(data, path) is not MISSING}
    result["source_time_semantics"] = source.get("source_time_semantics", "unknown; not an item publication time")
    if not rows:
        return dict(result, status="empty_verified", note="Known item-list exists and is empty; API checks passed")
    title_rejections = Counter()
    quality = Counter()
    for rank, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            title_rejections["non_object_item"] += 1
            continue
        title, title_field = first_at(row, source.get("title_fields", ["title"]))
        if not isinstance(title, str):
            title_rejections["missing_or_nonstring_title"] += 1
            continue
        title = html.unescape(re.sub(r"<[^>]+>", "", title)).strip()
        date_only = bool(re.fullmatch(r"[\s\d\-/.:年月日号周星期一二三四五六日天期第]+", title))
        if not 2 <= len(title) <= 300 or date_only:
            title_rejections["empty_short_long_or_date_title"] += 1
            continue
        url, url_origin = make_link(row, source)
        lq = link_quality(url, source.get("item_hosts", []))
        quality[lq] += 1
        raw_time, time_field = first_at(row, source.get("item_time_fields", []))
        result["items"].append({
            "rank_in_response": rank, "title": title, "title_field": title_field,
            "url": url, "url_origin": url_origin, "link_quality": lq,
            "raw_time": raw_time, "raw_time_field": time_field,
            "raw_time_semantics": source.get("item_time_semantics", "unknown"),
        })
    quality["titles_rejected"] = sum(title_rejections.values())
    quality["items_missing_raw_time"] = sum(x["raw_time"] is None for x in result["items"])
    quality["duplicate_title_url_rows"] = len(result["items"]) - len({(x["title"], x["url"]) for x in result["items"]})
    result["quality"] = dict(quality)
    result["title_rejection_reasons"] = dict(title_rejections)
    result["schema"]["observed_item_keys"] = sorted({k for row in rows[:5] if isinstance(row, dict) for k in row})
    result["status"] = "items" if result["items"] else "quality_error"
    result["note"] = "Explicit item-list parsed; links not visited; no freshness or fact verification" if result["items"] else "Nonempty item-list but no usable titles"
    generic = upstream.parse_json(raw) if upstream else []
    result["existing_generic_parser_comparison"] = {
        "available": upstream is not None,
        "item_count_before_limit": len(generic),
        "missing_url_count": sum(not item[1] for item in generic),
        "missing_raw_time_count": sum(not item[2] for item in generic),
        "note": "Offline parser comparison only; existing production keeps up to eight items" if upstream else "Optional audited upstream absent; candidate parsing remains self-contained",
    }
    return result


def validate_manifest(sources):
    if not isinstance(sources, list) or not 1 <= len(sources) <= MAX_SOURCES:
        raise SafetyError("Manifest must contain one to five explicitly researched sources")
    seen_ids, seen_urls = set(), set()
    for source in sources:
        required = ("id", "name", "url", "platform", "source_identity", "items_path", "evidence_urls")
        if any(key not in source for key in required):
            raise SafetyError("Candidate lacks required schema/provenance fields")
        if not re.fullmatch(r"[a-z0-9_-]{1,64}", source["id"]) or source["id"] in seen_ids or source["url"] in seen_urls:
            raise SafetyError("Duplicate source/URL or unsafe source ID")
        if source["source_identity"].get("kind") not in ("direct", "aggregator"):
            raise SafetyError("Source identity must label direct or aggregator")
        if not source["evidence_urls"]:
            raise SafetyError("A source requires a researched evidence URL")
        safe_url(source["url"], endpoint=True)
        seen_ids.add(source["id"])
        seen_urls.add(source["url"])


def run_one(source, output, upstream):
    result = dict(source, attempted_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(), items=[])
    began = time.monotonic()
    try:
        metadata, raw = fetch_public(source["url"])
        raw_path = output / (source["id"] + ".response.bin")
        raw_path.write_bytes(raw)
        result.update(metadata, response_sha256=hashlib.sha256(raw).hexdigest(), response_file=raw_path.name)
        result.update(parse_response(source, metadata, raw, upstream))
    except SafetyError as exc:
        result.update(status="safety_blocked", note=str(exc))
    except socket.gaierror as exc:
        result.update(status="dns_error", failure_stage="dns_resolution", http_request_sent=False, note=f"{type(exc).__name__}: {exc}")
    except (OSError, http.client.HTTPException, ValueError) as exc:
        result.update(status="fetch_error", note=f"{type(exc).__name__}: {exc}")
    except Exception as exc:
        result.update(status="lab_error", note=f"{type(exc).__name__}: {exc}")
    result["total_elapsed_seconds"] = round(time.monotonic() - began, 3)
    (output / (source["id"] + ".json")).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=pathlib.Path)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--live", action="store_true", help="Explicitly authorize this one-shot public GET batch")
    args = parser.parse_args()
    sources = json.loads(args.manifest.read_text(encoding="utf-8"))
    validate_manifest(sources)
    if not args.live:
        print(json.dumps({"manifest_valid": True, "sources": len(sources), "requests_made": 0}))
        return 0
    # Refuse to overwrite previous evidence or accidentally repeat the same run.
    if args.output.exists() and any(args.output.iterdir()):
        raise SafetyError("Output directory must be new or empty; do not rerun blocked endpoints")
    args.output.mkdir(parents=True, exist_ok=True)
    upstream = load_upstream()
    rows = [run_one(source, args.output, upstream) for source in sources]
    summary = {
        "completed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "lab_version": "0.2", "sources_attempted": len(rows),
        "validator_sha256": hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
        "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "status_counts": dict(Counter(r["status"] for r in rows)),
        "item_records": sum(len(r["items"]) for r in rows), "item_count_is_unique": False,
        "offline_upstream_sha256": UPSTREAM_SHA256 if upstream else None,
        "network_policy": "one GET/source; public pinned IP; validated TLS; no redirect/retry/cookie/secret/proxy",
        "results": [{"id": r["id"], "status": r["status"], "http_status": r.get("http_status"), "items": len(r["items"]), "note": r["note"]} for r in rows],
    }
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
