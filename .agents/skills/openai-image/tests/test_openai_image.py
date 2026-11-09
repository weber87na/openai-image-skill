# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""uv 執行的離線測試，不使用真實 API key，也不連線 OpenAI。"""

from __future__ import annotations

import base64
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from typing import Any, Iterator
from urllib import error

sys.dont_write_bytecode = True
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "openai_image.py"
SPEC = importlib.util.spec_from_file_location("openai_image", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
image = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(image)

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=")
# Windows 的 TLS 初始化需要系統路徑；隔離測試憑證時仍保留這些系統變數。
TEST_ENV = {name: os.environ[name] for name in ("SystemRoot", "WINDIR", "SYSTEMDRIVE") if name in os.environ}
TEST_ENV["NO_PROXY"] = "127.0.0.1,localhost"


def make_gif(frames: int = 9, delay_ms: int = 200, local_palette: bool = False) -> bytes:
    data = bytearray(b"GIF89a" + struct.pack("<HHBBB", 1, 1, 0x80, 0, 0))
    data.extend(b"\x00\x00\x00\xff\xff\xff")
    data.extend(b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00")
    # 註解中的影格分隔符不應被計算為影格。
    data.extend(b"\x21\xfe\x02\x2c\x2c\x00")
    for index in range(frames):
        data.extend(b"\x21\xf9\x04\x00" + struct.pack("<H", delay_ms // 10) + b"\x00\x00")
        data.extend(b"\x2c" + struct.pack("<HHHHB", 0, 0, 1, 1, 0x80 if local_palette else 0))
        if local_palette:
            data.extend(b"\x00\x00\x00\xff\xff\xff")
        data.extend(b"\x02\x02" + (b"\x44\x01" if index % 2 == 0 else b"\x4c\x01") + b"\x00")
    return bytes(data + b"\x3b")


def api_response(data: bytes) -> dict[str, Any]:
    return {"data": [{"b64_json": base64.b64encode(data).decode("ascii")}], "usage": {"total_tokens": 123}}


@contextmanager
def local_api(body: Any, status: int = 200, redirect: bool = False) -> Iterator[tuple[str, list[dict[str, Any]]]]:
    calls: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            raw = self.rfile.read(int(self.headers["Content-Length"]))
            calls.append({"method": "POST", "path": self.path, "authorization": self.headers.get("Authorization"), "body": json.loads(raw)})
            self.send_response(302 if redirect else status)
            if redirect:
                self.send_header("Location", "/redirected")
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body if isinstance(body, bytes) else json.dumps(body).encode("utf-8"))

        def do_GET(self):
            calls.append({"method": "GET", "path": self.path})
            self.send_response(200)
            self.end_headers()

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1/images/generations", calls
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


class PayloadTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, TEST_ENV, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def args(self, *extra: str, output: str = "sample.png"):
        return image.parser().parse_args(["--prompt", "原創小貓", "--output", output, *extra])

    def test_static_defaults(self):
        self.assertEqual(image.build_payload(self.args()), {
            "model": "gpt-image-2.6-sunburst", "prompt": "原創小貓", "n": 1, "output_format": "png",
        })

    def test_native_gif_defaults_and_no_unsupported_fields(self):
        payload = image.build_payload(self.args(output="sample.GIF"))
        self.assertEqual(payload["output_format"], "gif")
        self.assertEqual(payload["frame_count"], 9)
        self.assertEqual(payload["frame_duration_ms"], 200)
        for key in ("response_format", "stream", "partial_images", "output_compression", "size"):
            self.assertNotIn(key, payload)

    def test_native_gif_custom_options(self):
        payload = image.build_payload(self.args("--model", "gpt-image-2.6-flare", "--frames", "16", "--frame-duration-ms", "25", "--quality", "medium", "--complexity", "low", output="sample.gif"))
        self.assertEqual(payload["model"], "gpt-image-2.6-flare")
        self.assertEqual(payload["frame_count"], 16)
        self.assertEqual(payload["frame_duration_ms"], 25)
        self.assertEqual(payload["complexity"], "low")

    def test_model_precedence(self):
        with patch.dict(os.environ, {"OPENAI_IMAGE_MODEL": "gpt-image-2.6-flare"}):
            self.assertEqual(image.build_payload(self.args())["model"], "gpt-image-2.6-flare")
            self.assertEqual(image.build_payload(self.args("--model", "gpt-image-2.6-sunburst"))["model"], "gpt-image-2.6-sunburst")

    def test_supported_extensions(self):
        for suffix, expected in (("png", "png"), ("jpg", "jpeg"), ("jpeg", "jpeg"), ("webp", "webp")):
            with self.subTest(suffix=suffix):
                self.assertEqual(image.build_payload(self.args(output=f"x.{suffix}"))["output_format"], expected)

    def test_reject_bad_output_format(self):
        for args in (self.args("--format", "gif"), self.args(output="x.svg")):
            with self.assertRaises(image.ImageError):
                image.build_payload(args)

    def test_reject_gif_options_for_static(self):
        for option in (("--frames", "9"), ("--frame-duration-ms", "200")):
            with self.subTest(option=option), self.assertRaises(image.ImageError):
                image.build_payload(self.args(*option))

    def test_reject_bad_gif_limits(self):
        for option in (("--frames", "1"), ("--frames", "17"), ("--frame-duration-ms", "19"), ("--frame-duration-ms", "655351")):
            with self.subTest(option=option), self.assertRaises(image.ImageError):
                image.build_payload(self.args(*option, output="x.gif"))

    def test_reject_bad_size_or_timeout(self):
        for option in (("--size", "0x1024"), ("--size", "1025x1024"), ("--size", "4096x256"), ("--size", "bad"), ("--timeout", "0"), ("--timeout", "nan"), ("--timeout", "inf")):
            with self.subTest(option=option), self.assertRaises(image.ImageError):
                image.build_payload(self.args(*option))
        self.assertEqual(image.build_payload(self.args("--size", "1024x1024"))["size"], "1024x1024")
        self.assertEqual(image.build_payload(self.args("--size", "auto"))["size"], "auto")

    def test_background_constraints(self):
        self.assertEqual(image.build_payload(self.args("--background", "transparent"))["background"], "transparent")
        for output in ("x.gif", "x.jpg"):
            with self.subTest(output=output), self.assertRaises(image.ImageError):
                image.build_payload(self.args("--background", "transparent", output=output))

    def test_prompt_file_utf8_bom(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "prompt.txt"
            path.write_text("原創小貓\n揮手動畫", encoding="utf-8-sig")
            args = image.parser().parse_args(["--prompt-file", str(path), "--output", "x.gif"])
            self.assertEqual(image.build_payload(args)["prompt"], "原創小貓\n揮手動畫")

    def test_empty_long_and_missing_prompt_file(self):
        for text in (" ", "貓" * 32001):
            args = image.parser().parse_args(["--prompt", text, "--output", "x.png"])
            with self.assertRaises(image.ImageError):
                image.build_payload(args)
        with tempfile.TemporaryDirectory() as folder:
            args = image.parser().parse_args(["--prompt-file", str(Path(folder) / "missing.txt"), "--output", "x.png"])
            with self.assertRaises(image.ImageError):
                image.build_payload(args)


class FormatTests(unittest.TestCase):
    def test_png(self):
        data, info = image.decode_image(api_response(PNG), "png")
        self.assertEqual(data, PNG)
        self.assertEqual(info["format"], "png")

    def test_native_gif_frames_and_timing(self):
        data, info = image.decode_image(api_response(make_gif()), "gif")
        self.assertEqual(info, {"format": "gif", "bytes": len(data), "width": 1, "height": 1, "frames": 9, "duration_ms": 1800})

    def test_local_palette_and_delay(self):
        info = image.gif_info(make_gif(2, 250, local_palette=True))
        self.assertEqual(info["frames"], 2)
        self.assertEqual(info["duration_ms"], 500)

    def test_gif_without_global_palette(self):
        data = bytearray(make_gif(2, local_palette=True))
        data[10] = 0
        del data[13:19]
        self.assertEqual(image.gif_info(bytes(data))["frames"], 2)

    def test_reject_single_frame_and_truncated_gif(self):
        data = make_gif(2)
        for bad in (make_gif(1), data[:-1], data[:12], data[:-5], PNG):
            with self.subTest(size=len(bad)), self.assertRaises(image.ImageError):
                image.decode_image(api_response(bad), "gif")

    def test_reject_invalid_gif_canvas_and_block(self):
        for mutate in (lambda data: data.__setitem__(slice(6, 8), b"\x00\x00"), lambda data: data.__setitem__(19, 0)):
            data = bytearray(make_gif(2))
            mutate(data)
            with self.assertRaises(image.ImageError):
                image.gif_info(bytes(data))

    def test_reject_bad_response_or_base64(self):
        cases = ({}, {"data": []}, {"data": [None]}, {"data": [{"url": "https://example.invalid/image.png"}]}, {"data": [{"b64_json": "%%%"}]}, {"data": [{"b64_json": "你好"}]})
        for response in cases:
            with self.subTest(response=response), self.assertRaises(image.ImageError):
                image.decode_image(response, "png")

    def test_reject_gif_without_image_data(self):
        data = make_gif(2).replace(b"\x02\x02\x44\x01\x00", b"\x02\x00")
        with self.assertRaisesRegex(image.ImageError, "缺少影像資料"):
            image.gif_info(data)

    def test_reject_mismatched_format(self):
        for output_format in ("gif", "jpeg", "webp"):
            with self.subTest(output_format=output_format), self.assertRaises(image.ImageError):
                image.decode_image(api_response(PNG), output_format)
        with self.assertRaises(image.ImageError):
            image.decode_image(api_response(make_gif()), "png")


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {**TEST_ENV, "OPENAI_API_KEY": "offline-test-key"}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_http_png_and_persistent_output(self):
        with tempfile.TemporaryDirectory() as folder, local_api(api_response(PNG)) as (url, calls):
            output = Path(folder) / "圖片" / "image.png"
            args = image.parser().parse_args(["--prompt", "原創插畫", "--output", str(output)])
            with patch.object(image, "API_URL", url):
                result = image.run(args)
            self.assertEqual(output.read_bytes(), PNG)
            self.assertEqual(result["output"], str(output.resolve()))
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]["authorization"], "Bearer offline-test-key")
            self.assertEqual(calls[0]["path"], "/v1/images/generations")
            self.assertEqual(calls[0]["body"]["prompt"], "原創插畫")
            self.assertEqual(list(output.parent.glob(".openai-image-*")), [])

    def test_http_native_gif_single_request(self):
        gif = make_gif(9, 200)
        with tempfile.TemporaryDirectory() as folder, local_api(api_response(gif)) as (url, calls):
            output = Path(folder) / "animation.gif"
            args = image.parser().parse_args(["--prompt", "原創小貓揮手並循環", "--output", str(output)])
            with patch.object(image, "API_URL", url):
                result = image.run(args)
            self.assertEqual(output.read_bytes(), gif)
            self.assertEqual(result["frames"], 9)
            self.assertEqual(result["duration_ms"], 1800)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]["body"]["frame_count"], 9)
            self.assertNotIn("warning", result)

    def test_gif_frame_mismatch_warning(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(image, "call_api", return_value=api_response(make_gif(2))):
            output = Path(folder) / "animation.gif"
            result = image.run(image.parser().parse_args(["--prompt", "揮手", "--output", str(output)]))
            self.assertIn("warning", result)
            self.assertEqual(result["frames"], 2)

    def test_static_gif_response_never_written(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(image, "call_api", return_value=api_response(make_gif(1))):
            output = Path(folder) / "x.gif"
            with self.assertRaises(image.ImageError):
                image.run(image.parser().parse_args(["--prompt", "揮手", "--output", str(output)]))
            self.assertFalse(output.exists())

    def test_dry_run_without_key_network_or_files(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, TEST_ENV, clear=True), patch.object(image, "call_api") as api:
            output = Path(folder) / "missing" / "x.gif"
            args = image.parser().parse_args(["--prompt", "揮手", "--output", str(output), "--dry-run"])
            result = image.run(args)
            self.assertTrue(result["dry_run"])
            api.assert_not_called()
            self.assertFalse(output.parent.exists())

    def test_missing_key_before_network(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, TEST_ENV, clear=True), patch.object(image, "call_api") as api:
            args = image.parser().parse_args(["--prompt", "貓", "--output", str(Path(folder) / "x.png")])
            with self.assertRaisesRegex(image.ImageError, "OPENAI_API_KEY"):
                image.run(args)
            api.assert_not_called()

    def test_invalid_key_never_echoed_or_sent(self):
        for key in ("private\nkey", "private key", "private金鑰"):
            stderr = io.StringIO()
            with self.subTest(key=key), tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"OPENAI_API_KEY": key}), patch.object(image, "call_api") as api, redirect_stderr(stderr):
                status = image.main(["--prompt", "貓", "--output", str(Path(folder) / "x.png")])
                self.assertEqual(status, 1)
                self.assertNotIn(key, stderr.getvalue())
                self.assertIn("無效字元", stderr.getvalue())
                api.assert_not_called()

    def test_no_overwrite_or_paid_call_for_existing_file(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(image, "call_api") as api:
            output = Path(folder) / "x.png"
            output.write_bytes(b"original")
            with self.assertRaises(image.ImageError):
                image.run(image.parser().parse_args(["--prompt", "貓", "--output", str(output)]))
            self.assertEqual(output.read_bytes(), b"original")
            api.assert_not_called()

    def test_overwrite_and_no_temp_files(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "x.png"
            output.write_bytes(b"old")
            image.save_image(output, PNG, True)
            self.assertEqual(output.read_bytes(), PNG)
            self.assertEqual(list(Path(folder).glob(".openai-image-*")), [])

    def test_atomic_no_overwrite_race(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "x.png"
            original_link = os.link

            def competing_link(source, target):
                Path(target).write_bytes(b"created-while-waiting")
                return original_link(source, target)

            with patch.object(image.os, "link", side_effect=competing_link), self.assertRaises(FileExistsError):
                image.save_image(output, PNG, False)
            self.assertEqual(output.read_bytes(), b"created-while-waiting")
            self.assertEqual(list(Path(folder).glob(".openai-image-*")), [])

    def test_bad_parent_before_network(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(image, "call_api") as api:
            parent = Path(folder) / "file"
            parent.write_bytes(b"file")
            with self.assertRaises(image.ImageError):
                image.run(image.parser().parse_args(["--prompt", "貓", "--output", str(parent / "x.png")]))
            api.assert_not_called()

    def test_http_error_no_retry_and_key_redaction(self):
        for status in (400, 401, 403, 404, 429, 500):
            with self.subTest(status=status), local_api({"error": {"message": "failure offline-test-key"}}, status) as (url, calls), patch.object(image, "API_URL", url):
                with self.assertRaises(image.ImageError) as caught:
                    image.call_api({"prompt": "test"}, "offline-test-key", 5)
                self.assertIn(str(status), str(caught.exception))
                self.assertNotIn("offline-test-key", str(caught.exception))
                self.assertEqual(len(calls), 1)

    def test_http_error_non_json_or_unexpected_shape(self):
        for body in (b"not json", ["unexpected"], {"error": "unexpected"}):
            with self.subTest(body=body), local_api(body, 400) as (url, calls), patch.object(image, "API_URL", url):
                with self.assertRaises(image.ImageError):
                    image.call_api({}, "offline-test-key", 5)
                self.assertEqual(len(calls), 1)

    def test_invalid_success_json(self):
        for body in (b"not json", ["unexpected"]):
            with self.subTest(body=body), local_api(body) as (url, calls), patch.object(image, "API_URL", url):
                with self.assertRaises(image.ImageError):
                    image.call_api({}, "offline-test-key", 5)
                self.assertEqual(len(calls), 1)

    def test_redirect_never_followed(self):
        with local_api({}, redirect=True) as (url, calls), patch.object(image, "API_URL", url):
            with self.assertRaisesRegex(image.ImageError, "重新導向"):
                image.call_api({}, "offline-test-key", 5)
            self.assertEqual(len(calls), 1)

    def test_timeout_no_retry(self):
        for failure in (TimeoutError("test"), error.URLError("test")):
            with self.subTest(failure=failure), patch.object(image.request, "build_opener") as opener:
                opener.return_value.open.side_effect = failure
                with self.assertRaisesRegex(image.ImageError, "不自動重試"):
                    image.call_api({}, "offline-test-key", 0.1)
                self.assertEqual(opener.return_value.open.call_count, 1)

    def test_cli_main_outputs_clean_json_and_errors(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = image.main(["--prompt", "小貓", "--output", "x.gif", "--dry-run"])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(stdout.getvalue())["request"]["output_format"], "gif")
        self.assertNotIn("offline-test-key", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, TEST_ENV, clear=True), redirect_stderr(stderr):
            status = image.main(["--prompt", "小貓", "--output", str(Path(folder) / "x.png")])
        self.assertEqual(status, 1)
        self.assertIn("OPENAI_API_KEY", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())


class SkillTests(unittest.TestCase):
    def test_discoverable_frontmatter_and_bundled_script(self):
        skill = SCRIPT.parents[1] / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        frontmatter = text.split("---", 2)[1]
        self.assertIn(f"name: {skill.parent.name}\n", frontmatter)
        description = next(line.removeprefix("description: ") for line in frontmatter.splitlines() if line.startswith("description: "))
        self.assertTrue(description.startswith("'") and description.endswith("'"))
        self.assertLessEqual(len(description[1:-1]), 1024)
        self.assertIn("uv run --script", text)
        self.assertIn("./scripts/openai_image.py", text)
        self.assertIn("./tests/test_openai_image.py", text)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    unittest.main(verbosity=2)
