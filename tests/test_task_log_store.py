import os
import tempfile
import unittest

from task_log_store import TaskLogStore, sanitize_log_value


class TaskLogStoreTests(unittest.TestCase):
    def test_sanitizer_redacts_credentials_and_omits_image_bytes(self):
        value = sanitize_log_value({
            "Authorization": "Bearer secret-token",
            "api_key": "secret-key",
            "url": "https://example.test/generate?token=secret&mode=image",
            "inlineData": {"data": "A" * 5000, "mimeType": "image/png"},
            "prompt": "保留完整提示词",
        })
        self.assertEqual(value["Authorization"], "[REDACTED]")
        self.assertEqual(value["api_key"], "[REDACTED]")
        self.assertNotIn("secret", value["url"])
        self.assertIn("OMITTED", value["inlineData"]["data"])
        self.assertEqual(value["prompt"], "保留完整提示词")

    def test_trace_lifecycle_is_persisted_and_cleanup_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = TaskLogStore(os.path.join(tmp, "task_logs.sqlite3"), queue_size=20)
            try:
                self.assertTrue(store.create(
                    "trace_1", task_id="task_1", canvas_id="canvas_1", node_id="node_1",
                    source="canvas", kind="image", provider_id="demo", model="model-a",
                    prompt="完整 prompt", request={"method": "POST", "api_key": "never-store"},
                ))
                store.event("trace_1", "provider_request", "request sent", data={"status": "waiting"}, status="running")
                store.finish(
                    "trace_1", status="succeeded", response={"images": ["/assets/output/result.png"]},
                    color={"status": "corrected", "method": "lab_chroma", "confidence": 0.9},
                    upstream_id="upstream_1", duration_ms=1234,
                )
                detail = store.get("trace_1")
                self.assertIsNotNone(detail)
                self.assertEqual(detail["status"], "succeeded")
                self.assertEqual(detail["prompt"], "完整 prompt")
                self.assertEqual(detail["request"]["api_key"], "[REDACTED]")
                self.assertEqual(detail["color"]["method"], "lab_chroma")
                self.assertGreaterEqual(len(detail["events"]), 3)
                page = store.list(canvas_id="canvas_1", limit=10)
                self.assertEqual(page["total"], 1)
                self.assertEqual(page["items"][0]["trace_id"], "trace_1")
                result = store.cleanup("all")
                self.assertEqual(result["deleted"], 1)
                self.assertEqual(store.list(limit=10)["total"], 0)
            finally:
                store.close()

    def test_disk_cap_prunes_oldest_rows_and_reclaims_file_space(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = TaskLogStore(
                os.path.join(tmp, "task_logs.sqlite3"),
                max_bytes=5 * 1024 * 1024,
                target_bytes=3 * 1024 * 1024,
                queue_size=700,
            )
            try:
                for index in range(500):
                    store.create(
                        f"trace_{index}",
                        task_id=f"task_{index}",
                        provider_id="demo",
                        model="model-a",
                        prompt=f"{index}:" + ("detailed request log content | " * 600),
                        request={"sequence": index},
                    )
                page = store.list(limit=200)
                info = store.storage_info()
                self.assertLess(page["total"], 500)
                self.assertLessEqual(info["bytes"], store.max_bytes)
                self.assertGreater(page["total"], 0)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
