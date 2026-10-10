import copy
import hashlib
import importlib.util
import json
import pathlib
import socket
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("lab", ROOT / "validate_sources.py")
lab = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lab)
UPSTREAM = lab.load_upstream()
BASE = {"id": "fixture", "name": "Fixture", "url": "https://example.com/api", "platform": "zhihu", "source_identity": {"kind": "aggregator", "operator": "Fixture", "upstream_platform": "zhihu"}, "evidence_urls": ["https://example.com/documentation"], "items_path": "data", "title_fields": ["title"], "url_fields": ["url"], "item_hosts": ["zhihu.com"], "item_time_fields": ["created"], "source_time_fields": ["updated"]}


def parse(payload, source=None, status=200, ctype="application/json", raw=None):
    return lab.parse_response(source or BASE, {"http_status": status, "response_headers": {"content-type": ctype}}, raw if raw is not None else json.dumps(payload, ensure_ascii=False).encode(), UPSTREAM)


class SafetyTests(unittest.TestCase):
    def test_non_https_endpoint_rejected(self):
        for url in ("http://example.com/feed", "file:///etc/passwd", "ftp://example.com/feed"):
            with self.subTest(url=url), self.assertRaises(lab.SafetyError):
                lab.safe_url(url, endpoint=True)

    def test_private_and_credential_urls_rejected(self):
        for url in ("https://127.0.0.1/x", "https://[::1]/", "https://10.0.0.1/", "https://169.254.169.254/latest", "https://localhost/", "https://test.internal/", "https://user:password@example.com/", "https://example.com:8443/", "https://example.com/?access_token=abc", "https://example.com/?api_key=abc"):
            with self.subTest(url=url), self.assertRaises(lab.SafetyError):
                lab.safe_url(url, endpoint=True)

    def test_public_url_allowed(self):
        self.assertEqual(lab.safe_url("https://example.com/feed?q=hello", endpoint=True).hostname, "example.com")

    def test_dns_rejects_one_private_result(self):
        answers = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)), (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
        with mock.patch.object(lab.socket, "getaddrinfo", return_value=answers), self.assertRaises(lab.SafetyError):
            lab.resolve_public("example.com")

    def test_dns_global_result_recorded(self):
        with mock.patch.object(lab.socket, "getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]):
            self.assertEqual(lab.resolve_public("example.com"), ["93.184.216.34"])

    def test_manifest_duplicate_or_missing_provenance_rejected(self):
        for sources in ([BASE, BASE], [dict(BASE, evidence_urls=[])], [dict(BASE, id="../unsafe")], [dict(BASE, source_identity={"kind": "unknown"})], [BASE] * 6):
            with self.subTest(sources=sources), self.assertRaises(lab.SafetyError):
                lab.validate_manifest(sources)

    def test_manifest_batch_current_valid(self):
        sources = json.loads((ROOT / "candidates.json").read_text())
        lab.validate_manifest(sources)
        self.assertEqual(len(sources), 3)

    def test_pinned_upstream_hash_mismatch_blocks_import(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "upstream.py"
            path.write_text("raise AssertionError('must not execute')")
            with mock.patch.object(lab, "UPSTREAM", path), self.assertRaises(lab.SafetyError):
                lab.load_upstream()


class ResponseTests(unittest.TestCase):
    def test_empty_list_only_is_verified_empty(self):
        self.assertEqual(parse({"data": []})["status"], "empty_verified")
        for payload in ({}, {"data": None}, {"data": {}}, []):
            self.assertEqual(parse(payload)["status"], "schema_error")

    def test_empty_body_is_not_verified_empty(self):
        self.assertEqual(parse(None, raw=b"")["status"], "empty_body")

    def test_json_parse_error_not_empty(self):
        self.assertEqual(parse(None, raw=b"{broken")["status"], "parser_error")

    def test_block_and_unexpected_html_distinct(self):
        self.assertEqual(parse(None, raw=b"<html>CAPTCHA security check</html>", ctype="text/html")["status"], "blocked")
        self.assertEqual(parse(None, raw=b"<html>Home page</html>", ctype="text/html")["status"], "unexpected_html")

    def test_http_blocks_not_parser_errors(self):
        for status in (401, 403, 407, 429, 451):
            self.assertEqual(parse(None, status=status)["status"], "blocked")

    def test_redirect_and_server_error_not_followed(self):
        self.assertEqual(parse(None, status=302)["status"], "redirect_not_followed")
        self.assertEqual(parse(None, status=500)["status"], "http_error")

    def test_api_error_with_empty_list_not_empty(self):
        source = dict(BASE, success_checks=[{"path": "code", "accepted": [200]}])
        self.assertEqual(parse({"data": [], "code": 403}, source)["status"], "upstream_error")
        self.assertEqual(parse({"data": [], "code": 200}, source)["status"], "empty_verified")

    def test_raw_item_time_retained_source_time_not_inherited(self):
        result = parse({"updated": "2026-10-10T23:00:00Z", "data": [{"title": "示例条目", "url": "https://www.zhihu.com/question/123", "created": 1700000000}, {"title": "没有时间的条目", "url": "https://www.zhihu.com/question/456"}]})
        self.assertEqual(result["items"][0]["raw_time"], 1700000000)
        self.assertIsNone(result["items"][1]["raw_time"])
        self.assertEqual(result["source_times"]["updated"], "2026-10-10T23:00:00Z")

    def test_aggregator_wrapper_title_is_not_an_item(self):
        result = parse({"title": "知乎热门榜单", "updated": "today", "data": [{"title": "真实题目", "url": "https://www.zhihu.com/question/123"}]})
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["title"], "真实题目")

    def test_nonempty_unusable_list_is_quality_error(self):
        result = parse({"data": [{"not_title": "hello"}, {"title": "2026-10-10"}, "not object"]})
        self.assertEqual(result["status"], "quality_error")
        self.assertEqual(result["quality"]["titles_rejected"], 3)

    def test_link_quality_preserves_api_missing_off_platform_and_unsafe(self):
        urls = ["https://api.zhihu.com/questions/123", "", "https://example.com/123", "javascript:alert(1)", "https://127.0.0.1/x"]
        result = parse({"data": [{"title": "有效示例标题", "url": url} for url in urls]})
        self.assertEqual([x["link_quality"] for x in result["items"]], ["api_link_not_reader_page", "missing", "off_platform", "unsafe_or_invalid", "unsafe_or_invalid"])

    def test_documented_url_template_urlencodes_id(self):
        source = dict(BASE, url_template="https://www.zhihu.com/question/{id}", url_template_fields={"id": "id"})
        result = parse({"data": [{"title": "有效示例标题", "id": "12?foo=bar"}]}, source)
        self.assertEqual(result["items"][0]["url"], "https://www.zhihu.com/question/12%3Ffoo%3Dbar")
        self.assertEqual(result["items"][0]["url_origin"], "documented_template")

    def test_missing_template_field_no_fabricated_link(self):
        source = dict(BASE, url_template="https://www.zhihu.com/question/{id}", url_template_fields={"id": "id"})
        self.assertEqual(parse({"data": [{"title": "有效示例标题"}]}, source)["items"][0]["url"], "")

    def test_duplicate_rows_counted_not_silently_unique(self):
        row = {"title": "有效示例标题", "url": "https://www.zhihu.com/question/123"}
        result = parse({"data": [row, row]})
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["quality"]["duplicate_title_url_rows"], 1)

    def test_size_cap(self):
        self.assertEqual(parse(None, raw=b"a" * (lab.MAX_BYTES + 1))["status"], "response_too_large")

    def test_run_one_saves_identity_and_response_hash(self):
        raw = b'{"data": []}'
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(lab, "fetch_public", return_value=({"http_status": 200, "response_headers": {}}, raw)) as fetch:
            result = lab.run_one(BASE, pathlib.Path(folder), UPSTREAM)
            fetch.assert_called_once_with(BASE["url"])
            self.assertEqual(result["source_identity"]["kind"], "aggregator")
            self.assertEqual(result["response_sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual((pathlib.Path(folder) / "fixture.response.bin").read_bytes(), raw)

    def test_dns_failure_is_environment_evidence_not_target_response(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(lab, "fetch_public", side_effect=socket.gaierror(-3, "Temporary failure in name resolution")):
            result = lab.run_one(BASE, pathlib.Path(folder), UPSTREAM)
            self.assertEqual(result["status"], "dns_error")
            self.assertEqual(result["failure_stage"], "dns_resolution")
            self.assertFalse(result["http_request_sent"])
            self.assertNotIn("http_status", result)

    def test_fetch_error_gets_one_attempt(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(lab, "fetch_public", side_effect=TimeoutError("timed out")) as fetch:
            result = lab.run_one(BASE, pathlib.Path(folder), UPSTREAM)
            fetch.assert_called_once()
            self.assertEqual(result["status"], "fetch_error")


if __name__ == "__main__":
    unittest.main()
