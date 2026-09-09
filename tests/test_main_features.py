import logging
import time
import unittest

import main


class MainFeatureTests(unittest.TestCase):
    def test_nanobanana_fields_are_opt_in_and_model_scoped(self):
        request = main.OnlineImageRequest(prompt="test")
        self.assertEqual(request.color_preservation, "off")
        nano_fields = main.build_image_param_fields("api", {}, "gemini-3.1-flash-image-preview")
        regular_fields = main.build_image_param_fields("api", {}, "another-image-model")
        nano = {field["key"]: field for field in nano_fields}
        self.assertEqual(nano["color_preservation"]["default"], "off")
        self.assertEqual(nano["task_mode"]["default"], "outfit_swap")
        self.assertNotIn("color_preservation", {field["key"] for field in regular_fields})

    def test_access_filter_hides_only_successful_repetitive_requests(self):
        filter_ = main.QuietAccessLogFilter()
        message = '%s - "%s %s HTTP/%s" %s'
        success = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, message, (), None)
        success.args = ("127.0.0.1:1", "PUT", "/api/canvases/demo", "1.1", 200)
        failure = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, message, (), None)
        failure.args = ("127.0.0.1:1", "PUT", "/api/canvases/demo", "1.1", 500)
        self.assertFalse(filter_.filter(success))
        self.assertTrue(filter_.filter(failure))

    def test_in_memory_task_cache_is_bounded_but_keeps_running_tasks(self):
        original = dict(main.CANVAS_TASKS)
        try:
            main.CANVAS_TASKS.clear()
            now = time.time()
            main.CANVAS_TASKS["running"] = {"status": "running", "updated_at": now - 200000}
            for index in range(215):
                main.CANVAS_TASKS[f"done-{index}"] = {"status": "succeeded", "updated_at": now - index}
            main.prune_canvas_tasks_locked(now)
            self.assertIn("running", main.CANVAS_TASKS)
            self.assertLessEqual(sum(item.get("status") == "succeeded" for item in main.CANVAS_TASKS.values()), 200)
        finally:
            main.CANVAS_TASKS.clear()
            main.CANVAS_TASKS.update(original)

    def test_canvas_json_log_is_compact_and_traceable(self):
        compact = main.compact_canvas_log_entry({
            "id": "log-1", "createdAt": 1, "status": "success", "prompt": "P" * 5000,
            "request": {"trace_id": "trace-1", "api_key": "must-not-save", "color_preservation": {"status": "corrected"}},
            "refs": [{"data": "A" * 10000}],
            "outputs": [{"url": "/assets/output/a.png", "trace_id": "trace-1"}],
        })
        self.assertEqual(compact["request"]["trace_id"], "trace-1")
        self.assertNotIn("api_key", compact["request"])
        self.assertNotIn("refs", compact)
        self.assertEqual(len(compact["prompt"]), 600)


def tearDownModule():
    main.TASK_LOG_STORE.close()


if __name__ == "__main__":
    unittest.main()
