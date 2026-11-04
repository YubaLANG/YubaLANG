import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ENTRY_POINT = REPOSITORY_ROOT / "YubaLANG.py"


def _package_archive(
    name: str, version: str, source: str, dependencies: dict[str, dict[str, str]]
) -> bytes:
    files = {
        "yuba.json": json.dumps(
            {
                "name": name,
                "version": version,
                "entry": "main.yl",
                "yubalang": "1.3",
                "dependencies": dependencies,
            }
        ).encode("utf-8"),
        "main.yl": source.encode("utf-8"),
    }
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for filename, contents in files.items():
            member = tarfile.TarInfo(filename)
            member.size = len(contents)
            archive.addfile(member, io.BytesIO(contents))
    return output.getvalue()


class _Registry:
    def __init__(self) -> None:
        self.artifacts: dict[str, bytes] = {}
        self.metadata: dict[str, bytes] = {}
        self.requests: list[str] = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                owner.requests.append(self.path)
                if self.path.startswith("/v1/packages/"):
                    name = self.path.rsplit("/", 1)[-1].removesuffix(".json")
                    body = owner.metadata[name]
                    content_type = "application/json"
                else:
                    filename = self.path.rsplit("/", 1)[-1]
                    body = owner.artifacts[filename]
                    content_type = "application/gzip"
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format: str, *_args: object) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def endpoint(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}"

    def add_package(
        self,
        name: str,
        version: str,
        source: str,
        dependencies: dict[str, dict[str, str]] | None = None,
    ) -> None:
        archive = _package_archive(name, version, source, dependencies or {})
        filename = f"{name}-{version}.tar.gz"
        self.artifacts[filename] = archive
        self.metadata[name] = json.dumps(
            {
                "schema_version": 1,
                "name": name,
                "versions": {
                    version: {
                        "yubalang": ["1.3"],
                        "artifact": f"artifacts/{filename}",
                        "sha256": hashlib.sha256(archive).hexdigest(),
                    }
                },
            }
        ).encode("utf-8")

    def __enter__(self) -> "_Registry":
        self.thread.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)


class YubaPKGIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.yubapkg = shutil.which("yubapkg")
        if self.yubapkg is None:
            self.fail(
                "YubaPKG must be installed before running this integration test."
            )

    def run_yubapkg(
        self, *arguments: str, cwd: Path, env: dict[str, str]
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self.yubapkg, *arguments],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

    def test_registry_graph_imports_online_and_offline(self) -> None:
        with _Registry() as registry, tempfile.TemporaryDirectory() as directory:
            registry.add_package(
                "leaf",
                "1.1.0",
                "func define answer -> int\n    return 42\nendfunc\n",
            )
            registry.add_package(
                "widget",
                "1.4.0",
                "import leaf\n"
                "define var leaf_answer: int = 0\n"
                "func call leaf.answer -> leaf_answer\n"
                "func define answer -> int\n"
                "    return leaf_answer\n"
                "endfunc\n",
                {"leaf": {"registry": "^1.0.0"}},
            )
            workspace = Path(directory)
            app = workspace / "app"
            environment = os.environ.copy()
            environment["YUBAPKG_REGISTRY_URL"] = registry.endpoint

            initialized = self.run_yubapkg(
                "package", "init", str(app), cwd=workspace, env=environment
            )
            self.assertEqual(
                initialized.returncode, 0, initialized.stdout + initialized.stderr
            )
            (app / "main.yl").write_text(
                "import widget\n"
                "define var answer: int = 0\n"
                "func call widget.answer -> answer\n"
                "text output answer\n",
                encoding="utf-8",
            )

            added = self.run_yubapkg(
                "package",
                "add",
                "widget",
                "--registry",
                "^1.2.0",
                cwd=app,
                env=environment,
            )
            self.assertEqual(added.returncode, 0, added.stdout + added.stderr)
            offline_environment = {
                key: value
                for key, value in environment.items()
                if key != "YUBAPKG_REGISTRY_URL"
            }
            installed = self.run_yubapkg(
                "package", "install", "--offline", cwd=app, env=offline_environment
            )
            self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
            checked = self.run_yubapkg(
                "package", "check", cwd=app, env=offline_environment
            )
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            frozen = self.run_yubapkg(
                "package", "install", "--frozen", cwd=app, env=offline_environment
            )
            self.assertEqual(frozen.returncode, 0, frozen.stdout + frozen.stderr)

            lock = json.loads((app / "yuba.lock.json").read_text(encoding="utf-8"))
            self.assertEqual(lock["lock_version"], 3)
            self.assertIn("leaf", lock["dependencies"]["widget"]["dependencies"])
            self.assertTrue((app / ".yuba" / "packages" / "widget" / ".yuba" / "packages" / "leaf").is_dir())

            request_count = len(registry.requests)
            for name, run_environment in (
                ("online", environment),
                (
                    "offline",
                    {
                        key: value
                        for key, value in environment.items()
                        if key != "YUBAPKG_REGISTRY_URL"
                    },
                ),
            ):
                with self.subTest(mode=name):
                    run = subprocess.run(
                        [sys.executable, str(ENTRY_POINT), "run", str(app)],
                        cwd=workspace,
                        env=run_environment,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        check=False,
                    )
                    self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                    self.assertEqual(run.stdout, "42\n")
            self.assertEqual(len(registry.requests), request_count)


if __name__ == "__main__":
    unittest.main()
