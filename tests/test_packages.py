import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from lang.packages import PackageError, check, install


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
ENTRY_POINT = REPOSITORY_ROOT / "YubaLANG.py"


def run_cli(*arguments, cwd):
    return subprocess.run(
        [sys.executable, str(ENTRY_POINT), *map(str, arguments)],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def write_package(root: Path, name: str, source: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "yuba.json").write_text(
        json.dumps(
            {
                "name": name,
                "version": "0.1.0",
                "entry": "main.yl",
                "yubalang": "1.2",
                "dependencies": {},
            }
        ),
        encoding="utf-8",
    )
    (root / "main.yl").write_text(source, encoding="utf-8")


class PackageManagerTests(unittest.TestCase):
    def test_init_creates_a_runnable_project(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "sample"
            result = run_cli("package", "init", project, cwd=directory)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((project / "yuba.json").is_file())
            self.assertTrue((project / "main.yl").is_file())
            parsed = json.loads((project / "yuba.json").read_text(encoding="utf-8"))
            self.assertEqual(parsed["entry"], "main.yl")

    def test_project_run_uses_manifest_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_package(root, "sample", 'text output "manifest entry"\n')
            (root / "wrong.yl").write_text('text output "wrong entry"\n', encoding="utf-8")
            manifest_path = root / "yuba.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["entry"] = "wrong.yl"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = run_cli("run", cwd=root)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "wrong entry\n")

    def test_add_path_dependency_lock_import_and_check(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            dependency = root / "mylib"
            project.mkdir()
            write_package(
                dependency,
                "mylib",
                "func define answer\n    return 42\nendfunc\n",
            )
            write_package(
                project,
                "app",
                "import mylib\n"
                "define var result: int = 0\n"
                "func call mylib.answer -> result\n"
                "text output result\n",
            )
            added = run_cli("package", "add", "mylib", "--path", "../mylib", cwd=project)
            self.assertEqual(added.returncode, 0, added.stderr)
            checked = run_cli("package", "check", cwd=project)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            listed = run_cli("package", "list", cwd=project)
            self.assertEqual(listed.returncode, 0, listed.stderr)
            self.assertIn("mylib: ../mylib", listed.stdout)
            executed = run_cli(project / "main.yl", cwd=project)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            self.assertEqual(executed.stdout, "42\n")

            lock = json.loads((project / "yuba.lock.json").read_text(encoding="utf-8"))
            self.assertEqual(
                lock["dependencies"]["mylib"]["resolved"]["path"], "../mylib"
            )
            removed = run_cli("package", "remove", "mylib", cwd=project)
            self.assertEqual(removed.returncode, 0, removed.stderr)
            updated_manifest = json.loads(
                (project / "yuba.json").read_text(encoding="utf-8")
            )
            self.assertEqual(updated_manifest["dependencies"], {})

    def test_reports_malformed_manifest_and_unavailable_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            (project / "yuba.json").write_text("{", encoding="utf-8")
            malformed = run_cli("package", "install", cwd=project)
            self.assertEqual(malformed.returncode, 1)
            self.assertIn("Invalid JSON", malformed.stderr)

            write_package(project, "app", "")
            manifest_path = project / "yuba.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["yubalang"] = "9.0"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            incompatible = run_cli("package", "install", cwd=project)
            self.assertEqual(incompatible.returncode, 1)
            self.assertIn("this runtime supports 1.2", incompatible.stderr)

            manifest["yubalang"] = "1.2"
            manifest["dependencies"] = {"missing": {"path": "../missing"}}
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            missing = run_cli("package", "install", cwd=project)
            self.assertEqual(missing.returncode, 1)
            self.assertIn("Path dependency 'missing' does not exist", missing.stderr)

    def test_check_reports_manifest_lockfile_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dependency = root / "library"
            write_package(dependency, "library", "")
            project = root / "project"
            write_package(project, "app", "")
            manifest_path = project / "yuba.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["dependencies"] = {"library": {"path": "../library"}}
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            install(project)
            manifest["dependencies"]["other"] = {"path": "../library"}
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(PackageError, "do not match the lockfile"):
                check(project)

    @unittest.skipUnless(shutil.which("git"), "Git is not installed")
    def test_add_git_dependency_records_and_installs_exact_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            write_package(
                work,
                "gitlib",
                "func define answer\n    return 42\nendfunc\n",
            )
            remote = root / "gitlib.git"
            subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
            subprocess.run(["git", "init", str(work)], check=True, capture_output=True)
            subprocess.run(
                ["git", "-C", str(work), "config", "user.name", "YubaLANG Tests"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(work), "config", "user.email", "tests@example.invalid"],
                check=True,
            )
            subprocess.run(["git", "-C", str(work), "add", "."], check=True)
            subprocess.run(
                ["git", "-C", str(work), "commit", "-m", "Initial library"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(work), "remote", "add", "origin", str(remote)],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(work), "push", "origin", "HEAD"],
                check=True,
                capture_output=True,
            )
            project = root / "project"
            write_package(
                project,
                "app",
                "import gitlib\n"
                "define var result: int = 0\n"
                "func call gitlib.answer -> result\n"
                "text output result\n",
            )

            added = run_cli("package", "add", "gitlib", "--git", remote, cwd=project)
            self.assertEqual(added.returncode, 0, added.stderr)
            lock = json.loads((project / "yuba.lock.json").read_text(encoding="utf-8"))
            revision = lock["dependencies"]["gitlib"]["resolved"]["rev"]
            self.assertEqual(len(revision), 40)
            self.assertTrue((project / ".yuba" / "packages" / "gitlib").is_dir())

            executed = run_cli(project / "main.yl", cwd=project)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            self.assertEqual(executed.stdout, "42\n")

            (work / "main.yl").write_text(
                "func define answer\n    return 43\nendfunc\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "-C", str(work), "add", "main.yl"], check=True)
            subprocess.run(
                ["git", "-C", str(work), "commit", "-m", "Update answer"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(work), "push", "origin", "HEAD"],
                check=True,
                capture_output=True,
            )

            installed = run_cli("package", "install", cwd=project)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            unchanged_lock = json.loads(
                (project / "yuba.lock.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                unchanged_lock["dependencies"]["gitlib"]["resolved"]["rev"], revision
            )
            updated = run_cli("package", "update", "gitlib", cwd=project)
            self.assertEqual(updated.returncode, 0, updated.stderr)
            new_lock = json.loads(
                (project / "yuba.lock.json").read_text(encoding="utf-8")
            )
            self.assertNotEqual(
                new_lock["dependencies"]["gitlib"]["resolved"]["rev"], revision
            )
            executed_after_update = run_cli(project / "main.yl", cwd=project)
            self.assertEqual(
                executed_after_update.returncode,
                0,
                executed_after_update.stdout + executed_after_update.stderr,
            )
            self.assertEqual(executed_after_update.stdout, "43\n")


if __name__ == "__main__":
    unittest.main()
