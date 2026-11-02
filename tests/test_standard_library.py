import contextlib
import http.server
import io
import json
import random
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from lang.interpreter import Runtime, execute_lines


class StandardLibraryTests(unittest.TestCase):
    def execute(self, source: str, runtime: Runtime | None = None) -> Runtime:
        runtime = runtime or Runtime()
        execute_lines(source.strip().splitlines(), runtime)
        return runtime

    def test_imports_path_math_json_and_encoding_modules(self):
        runtime = self.execute(
            r'''
            import std.path as path
            import std.math as math
            import std.json as json
            import std.encoding as encoding
            define var joined: string = ""
            define var root: float = 0.0
            define var decoded: dict = {}
            define var encoded: bytes = ""
            define var round_trip: string = ""
            define var is_callable: bool = false
            func call path.join "folder" "item.txt" -> joined
            callable path.join is_callable
            func call math.sqrt 81 -> root
            func call json.loads '{"answer": 42}' -> decoded
            func call encoding.utf8_encode "Yuba" -> encoded
            func call encoding.utf8_decode encoded -> round_trip
            '''
        )

        self.assertEqual(runtime.require_var("joined")["value"], str(Path("folder") / "item.txt"))
        self.assertEqual(runtime.require_var("root")["value"], 9.0)
        self.assertEqual(runtime.require_var("decoded")["value"], {"answer": 42})
        self.assertEqual(runtime.require_var("encoded")["value"], b"Yuba")
        self.assertEqual(runtime.require_var("round_trip")["value"], "Yuba")
        self.assertTrue(runtime.require_var("is_callable")["value"])

    def test_json_rejects_nonstandard_numeric_constants(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            self.execute(
                """
                import std.json as json
                define var value: float = 0.0
                func call json.loads "NaN" -> value
                """,
                Runtime(),
            )
        self.assertIn("Invalid JSON numeric constant 'NaN'", output.getvalue())

    def test_time_and_random_are_injectable_for_deterministic_tests(self):
        runtime = Runtime(
            clock=lambda: 1_700_000_000.0,
            random_source=random.Random(),
        )
        self.execute(
            """
            import std.time
            import std.random
            define var timestamp: float = 0.0
            define var iso: string = ""
            define var first: int = 0
            define var second: int = 0
            func call time.now -> timestamp
            func call time.utc_iso timestamp -> iso
            func call random.seed 12345
            func call random.integer 1 100 -> first
            func call random.seed 12345
            func call random.integer 1 100 -> second
            """,
            runtime,
        )

        self.assertEqual(runtime.require_var("timestamp")["value"], 1_700_000_000.0)
        self.assertEqual(runtime.require_var("iso")["value"], "2023-11-14T22:13:20Z")
        self.assertEqual(
            runtime.require_var("first")["value"],
            runtime.require_var("second")["value"],
        )

    def test_filesystem_write_is_no_clobber_by_default_and_utf8(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "message.txt"
            runtime = Runtime()
            self.execute(
                f"""
                import std.fs as fs
                func call fs.write_text {json.dumps(str(target))} "snowman ☃"
                """,
                runtime,
            )
            self.assertEqual(target.read_bytes(), "snowman ☃".encode("utf-8"))

            output = io.StringIO()
            with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
                self.execute(
                    f"""
                    import std.fs as fs
                    func call fs.write_text {json.dumps(str(target))} "replacement"
                    """,
                    Runtime(),
                )
            self.assertIn("File exists", output.getvalue())
            self.assertEqual(target.read_text(encoding="utf-8"), "snowman ☃")

            self.execute(
                f"""
                import std.fs as fs
                func call fs.write_text {json.dumps(str(target))} "replacement" overwrite=true
                """,
                Runtime(),
            )
            self.assertEqual(target.read_text(encoding="utf-8"), "replacement")

            binary_target = Path(directory) / "payload.bin"
            self.execute(
                f"""
                import std.fs as fs
                define var payload: bytes = "payload"
                func call fs.write_bytes {json.dumps(str(binary_target))} payload
                func call fs.read_bytes {json.dumps(str(binary_target))} -> payload
                """,
                Runtime(),
            )
            self.assertEqual(binary_target.read_bytes(), b"payload")

    def test_process_arguments_environment_and_bounded_subprocess_output(self):
        runtime = Runtime(program_args=["first", "second"])
        with patch.dict("os.environ", {"YUBALANG_TEST_VALUE": "present"}):
            self.execute(
                """
                import std.process as process
                define var arguments: list = []
                define var environment: string? = none
                func call process.args -> arguments
                func call process.env "YUBALANG_TEST_VALUE" -> environment
                """,
                runtime,
            )

        self.assertEqual(runtime.require_var("arguments")["value"], ["first", "second"])
        self.assertEqual(runtime.require_var("environment")["value"], "present")

        command = [
            sys.executable,
            "-c",
            "import sys; sys.stdout.buffer.write(b'out'); sys.stderr.buffer.write(b'err')",
        ]
        runtime = Runtime()
        self.execute(
            f"""
            import std.process as process
            define var command: list = {json.dumps(command)}
            define var result: dict = {{}}
            func call process.run command -> result
            """,
            runtime,
        )
        result = runtime.require_var("result")["value"]
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["stdout"], b"out")
        self.assertEqual(result["stderr"], b"err")

        output = io.StringIO()
        oversized_command = [
            sys.executable,
            "-c",
            "print('x' * 128)",
        ]
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            self.execute(
                f"""
                import std.process as process
                define var command: list = {json.dumps(oversized_command)}
                define var result: dict = {{}}
                func call process.run command max_output_bytes=4 -> result
                """,
                Runtime(),
            )
        self.assertIn("output exceeded the 4-byte limit", output.getvalue())

        output = io.StringIO()
        sleeping_command = [
            sys.executable,
            "-c",
            "import time; time.sleep(2)",
        ]
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            self.execute(
                f"""
                import std.process as process
                define var command: list = {json.dumps(sleeping_command)}
                define var result: dict = {{}}
                func call process.run command timeout=0.1 -> result
                """,
                Runtime(),
            )
        self.assertIn("exceeded its 0.1-second timeout", output.getvalue())

    def test_http_response_limit_and_cross_origin_credential_stripping(self):
        observed_headers = []

        class DestinationHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                observed_headers.append(
                    (self.headers.get("Authorization"), self.headers.get("Cookie"))
                )
                body = b"ok"
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):
                pass

        destination = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), DestinationHandler
        )

        class SourceHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/redirect":
                    location = (
                        f"http://127.0.0.1:{destination.server_port}/target"
                    )
                    self.send_response(302)
                    self.send_header("Location", location)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                if self.path == "/userinfo":
                    location = (
                        f"http://user:password@127.0.0.1:"
                        f"{destination.server_port}/target"
                    )
                    self.send_response(302)
                    self.send_header("Location", location)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                body = b"response-too-large"
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):
                pass

        source = http.server.ThreadingHTTPServer(("127.0.0.1", 0), SourceHandler)
        threads = [
            threading.Thread(target=server.serve_forever, daemon=True)
            for server in (source, destination)
        ]
        for thread in threads:
            thread.start()
        try:
            request_headers = json.dumps(
                {"Authorization": "Bearer secret", "Cookie": "session=secret"}
            )
            runtime = Runtime()
            self.execute(
                f"""
                import std.http as http
                define var response: dict = {{}}
                define var request_headers: dict = {request_headers}
                func call http.request "http://127.0.0.1:{source.server_port}/redirect" headers=request_headers -> response
                """,
                runtime,
            )
            self.assertEqual(runtime.require_var("response")["value"]["status"], 200)
            self.assertEqual(observed_headers, [(None, None)])

            output = io.StringIO()
            with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
                self.execute(
                    f"""
                    import std.http as http
                    define var response: dict = {{}}
                    func call http.request "http://127.0.0.1:{source.server_port}/userinfo" -> response
                    """,
                    Runtime(),
                )
            self.assertIn("without user info", output.getvalue())

            output = io.StringIO()
            with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
                self.execute(
                    f"""
                    import std.http as http
                    define var response: dict = {{}}
                    func call http.request "http://127.0.0.1:{source.server_port}/large" max_bytes=4 -> response
                    """,
                    Runtime(),
                )
            self.assertIn("response exceeded the 4-byte limit", output.getvalue())
        finally:
            for server in (source, destination):
                server.shutdown()
                server.server_close()
            for thread in threads:
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
