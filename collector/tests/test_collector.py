import contextlib
import hashlib
import importlib.util
import io
import json
import pathlib
import tempfile
import types
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location("collector", pathlib.Path(__file__).parents[1] / "run_collector.py")
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


class CollectorTests(unittest.TestCase):
    def test_classification_does_not_claim_empty_is_success(self):
        self.assertEqual(collector.classify([], "0.2s"), "empty_or_unparsed")
        self.assertEqual(collector.classify([], "打不开 HTTPError"), "fetch_error")
        self.assertEqual(collector.classify([], "解析失败 ValueError"), "parse_error")
        self.assertEqual(collector.classify([], "配置坏了 缺 url"), "config_error")
        self.assertEqual(collector.classify([("a", "b", "c")], "0.2s"), "items")

    def test_raw_time_and_fallback_provenance_are_kept(self):
        source = {"name": "fallback", "url": "https://example.com/feed", "fallback_for": "primary"}
        module = types.SimpleNamespace(
            pull=lambda s, n: (s, [("A title", "https://example.com/a", "2026-10-10T20:00:00Z")], "0.1s"),
            norm_time=lambda s: "10-10 20:00",
        )
        row = collector.collect_one(module, source)
        self.assertEqual(row["status"], "items")
        self.assertEqual(row["fallback_for"], "primary")
        self.assertEqual(row["source_url"], source["url"])
        self.assertEqual(row["items"][0]["raw_time"], "2026-10-10T20:00:00Z")

    def test_unexpected_source_error_is_accounted_for(self):
        module = types.SimpleNamespace(pull=mock.Mock(side_effect=ValueError("bad source")))
        row = collector.collect_one(module, {"name": "broken"})
        self.assertEqual(row["status"], "collector_error")
        self.assertEqual(row["items"], [])

    def test_partial_counts_include_every_source(self):
        rows = [
            {"source": "a", "status": "items", "items": [{}, {}], "note": "0.1s"},
            {"source": "b", "status": "fetch_error", "items": [], "note": "打不开 HTTPError"},
            {"source": "c", "status": "empty_or_unparsed", "items": [], "note": "0.2s"},
            {"source": "fallback", "status": "items", "items": [{}], "note": "0.1s"},
        ]
        meta = collector.summarize(rows, 5, 1)
        self.assertEqual(meta["status"], "partial")
        self.assertEqual(meta["configured_sources"], 5)
        self.assertEqual(meta["attempted_sources"], 4)
        self.assertEqual(meta["sources_with_items"], 2)
        self.assertEqual(meta["failed_sources"], 1)
        self.assertEqual(meta["sources_empty_or_unparsed"], 1)
        self.assertEqual(meta["item_count"], 3)
        self.assertFalse(meta["item_count_is_unique"])
        self.assertEqual(len(meta["source_results"]), 4)

    def test_no_items_is_failed_not_a_green_success(self):
        rows = [{"source": "a", "status": "empty_or_unparsed", "items": [], "note": "0.1s"}]
        self.assertEqual(collector.summarize(rows, 1, 0)["status"], "failed")
        self.assertEqual(collector.summarize([], 0, 0)["status"], "failed")

    def test_complete_results_are_ok(self):
        rows = [{"source": "a", "status": "items", "items": [{}], "note": "0.1s"}]
        self.assertEqual(collector.summarize(rows, 1, 0)["status"], "ok")

    def test_hash_mismatch_is_rejected_before_file_is_written(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder)
            with mock.patch.object(collector.urllib.request, "urlopen") as open_url:
                open_url.return_value.__enter__.return_value.read.return_value = b"changed code"
                with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                    collector.download_verified("hot_sources.py", "0" * 64, path)
            self.assertFalse((path / "hot_sources.py").exists())

    def test_verified_download_uses_immutable_commit(self):
        data = b"verified fixture\n"
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder)
            with mock.patch.object(collector.urllib.request, "urlopen") as open_url:
                open_url.return_value.__enter__.return_value.read.return_value = data
                collector.download_verified("sources.json", hashlib.sha256(data).hexdigest(), path)
                request = open_url.call_args.args[0]
                self.assertIn(collector.UPSTREAM_COMMIT, request.full_url)
                self.assertNotIn("v2.3.15", request.full_url)
            self.assertEqual((path / "sources.json").read_bytes(), data)

    def test_bootstrap_failure_saves_diagnostics_and_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as folder:
            output = pathlib.Path(folder) / "raw"
            with mock.patch.object(collector, "OUT", output), mock.patch.object(
                collector, "load_upstream", side_effect=ValueError("checksum failed")
            ), mock.patch.dict(collector.os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()):
                result = collector.main()
            self.assertEqual(result, 1)
            metadata = json.loads((output / "meta.json").read_text())
            self.assertEqual(metadata["status"], "failed")
            self.assertIn("checksum failed", metadata["fatal_error"])
            self.assertEqual(json.loads((output / "latest.json").read_text()), [])
            self.assertEqual(len(list(output.glob("*.json"))), 4)

    def test_main_does_not_run_selection_and_keeps_fallback_attempt(self):
        sources = [
            {"name": "primary", "url": "https://example.com/rss"},
            {"name": "fallback", "url": "https://example.com/api", "fallback_for": "primary"},
        ]
        module = types.SimpleNamespace(
            load_sources=lambda p: sources,
            pull=lambda s, n: (s, [(s["name"], s["url"], "raw")], "0.1s"),
            norm_time=lambda s: s,
        )
        # No main, clustering, keyword or subscription functions are supplied.
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            cache, output = root / "cache", root / "raw"
            cache.mkdir()
            (cache / "sources.json").write_text(json.dumps({"sources": sources}))
            with mock.patch.object(collector, "CACHE", cache), mock.patch.object(collector, "OUT", output), mock.patch.object(
                collector, "load_upstream", return_value=module
            ), mock.patch.dict(collector.os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()):
                result = collector.main()
            self.assertEqual(result, 0)
            rows = json.loads((output / "latest.json").read_text())
            metadata = json.loads((output / "meta.json").read_text())
            self.assertEqual(len(rows), 2)
            self.assertEqual(metadata["attempted_sources"], 2)
            self.assertEqual(metadata["item_count"], 2)


if __name__ == "__main__":
    unittest.main()
