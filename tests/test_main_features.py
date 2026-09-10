import asyncio
import logging
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import main


class MainFeatureTests(unittest.TestCase):
    def test_color_protection_fields_are_opt_in_and_model_agnostic(self):
        request = main.OnlineImageRequest(prompt="test")
        self.assertEqual(request.color_preservation, "off")
        nano_fields = main.build_image_param_fields("api", {}, "gemini-3.1-flash-image-preview")
        alias_fields = main.build_image_param_fields("api", {}, "nano-banana-2")
        renamed_fields = main.build_image_param_fields("api", {}, "relay-custom-name")
        nano = {field["key"]: field for field in nano_fields}
        self.assertEqual(nano["color_preservation"]["default"], "off")
        self.assertEqual(nano["task_mode"]["default"], "outfit_swap")
        for fields in (alias_fields, renamed_fields):
            keys = {field["key"] for field in fields}
            self.assertIn("color_preservation", keys)
            self.assertIn("task_mode", keys)

    def test_relay_model_alias_can_run_color_protection(self):
        payload = main.OnlineImageRequest(
            prompt="test",
            provider_id="relay",
            model="nano-banana-2",
            reference_images=[main.AIReference(url="/assets/input/reference.png", role="source")],
            color_preservation="auto",
        )
        diagnostics = {"status": "corrected", "method": "test", "confidence": 1.0}
        with (
            patch.object(main, "get_api_provider", return_value={"id": "relay", "name": "Relay", "image_models": ["fallback"]}),
            patch.object(main, "generate_ai_image", new=AsyncMock(return_value=("generated", {"data": []}))),
            patch.object(main, "extract_images", return_value=["generated"]),
            patch.object(main, "save_ai_image_to_output", new=AsyncMock(return_value="/assets/output/online_result.png")),
            patch.object(main, "output_file_from_url", side_effect=lambda url: "C:/output/online_result.png" if "online_result" in url else "C:/input/reference.png"),
            patch.object(main, "preserve_image_colors", return_value=diagnostics) as preserve,
            patch.object(main.os.path, "isfile", return_value=True),
            patch.object(main, "output_url_for", return_value="/assets/output/online_result_colorfix.png"),
            patch.object(main, "image_output_meta", side_effect=lambda url, _item: {"url": url}),
            patch.object(main, "save_to_history"),
            patch.object(main, "GLOBAL_LOOP", None),
        ):
            result = asyncio.run(main.build_online_image_result(payload))

        preserve.assert_called_once()
        self.assertEqual(result["images"], ["/assets/output/online_result_colorfix.png"])
        self.assertTrue(result["color_preservation"]["supported_model"])

    def test_frontends_keep_color_protection_in_api_generation_nodes(self):
        repo_root = Path(__file__).resolve().parents[1]
        classic = (repo_root / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
        smart = (repo_root / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")
        self.assertIn('class="gen-settings-row color-preservation-row"', classic)
        self.assertNotIn('color-preservation-row" style="display:none"', classic)
        self.assertNotIn("colorPreservationRow.style.display", classic)
        self.assertIn("${renderTaskModeControl()}", smart)
        self.assertIn("${renderColorPreservationControl()}", smart)
        self.assertNotIn("isNanoBanana2Model", smart)

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
