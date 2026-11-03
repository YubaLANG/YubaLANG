import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from lang.packages import (
    PackageError,
    _satisfies_requirement,
    check,
    install,
)


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
                "yubalang": "1.3",
                "dependencies": {},
            }
        ),
        encoding="utf-8",
    )
    (root / "main.yl").write_text(source, encoding="utf-8")


class PackageManagerTests(unittest.TestCase):
    def test_registry_lock_requirement_matches_semver_ranges(self):
        cases = (
            ("1.4.0", "^1.2.3", True),
            ("2.0.0", "^1.2.3", False),
            ("0.2.9", "^0.2.3", True),
            ("1.2.9", "~1.2.3", True),
            ("1.3.0", "~1.2.3", False),
            ("1.7.0", ">=1.2.0, <2.0.0", True),
            ("1.7.0", "1.x", True),
            ("1.2.3-beta", ">=1.2.3-beta <1.2.3", True),
            ("1.2.4-beta", ">=1.2.3-beta <2.0.0", False),
        )
        for version, requirement, expected in cases:
            with self.subTest(version=version, requirement=requirement):
                self.assertEqual(
                    _satisfies_requirement(version, requirement), expected
                )

    def test_init_creates_a_runnable_project(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "sample"
            result = run_cli("package", "init", project, cwd=directory)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((project / "yuba.json").is_file())
            self.assertTrue((project / "main.yl").is_file())
            parsed = json.loads((project / "yuba.json").read_text(encoding="utf-8"))
            self.assertEqual(parsed["entry"], "main.yl")
            self.assertEqual(parsed["yubalang"], "1.3")

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

    def test_bundled_standard_library_runs_without_install_or_lockfile(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "sample"
            write_package(
                project,
                "sample",
                "import std.process as process\n"
                "define var arguments: list = []\n"
                "func call process.args -> arguments\n"
                "text output arguments\n",
            )

            result = run_cli("run", project, "--", "first", "second", cwd=directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "['first', 'second']\n")
            self.assertFalse((project / "yuba.lock.json").exists())

            direct = run_cli(project / "main.yl", "direct", cwd=directory)
            self.assertEqual(direct.returncode, 0, direct.stderr)
            self.assertEqual(direct.stdout, "['direct']\n")

    def test_standard_library_exit_sets_process_status(self):
        with tempfile.TemporaryDirectory() as directory:
            program = Path(directory) / "exit.yl"
            program.write_text(
                "import std.process as process\n"
                "func call process.exit 7\n",
                encoding="utf-8",
            )
            result = run_cli(program, cwd=directory)

        self.assertEqual(result.returncode, 7)

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

    def test_imports_and_verifies_yubapkg_registry_lockfile_format_3(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            dependency = root / ".yuba" / "packages" / "mylib"
            write_package(
                dependency,
                "mylib",
                "func define answer\n    return 42\nendfunc\n",
            )
            dependency_manifest_path = dependency / "yuba.json"
            dependency_manifest = json.loads(
                dependency_manifest_path.read_text(encoding="utf-8")
            )
            dependency_manifest["version"] = "1.2.0"
            dependency_manifest_path.write_text(
                json.dumps(dependency_manifest), encoding="utf-8"
            )
            (dependency / "yuba.lock.json").write_text(
                json.dumps({"lock_version": 3, "dependencies": {}}),
                encoding="utf-8",
            )
            tree_hash = hashlib.sha256()
            package_files = sorted(
                path for path in dependency.rglob("*")
                if path.is_file() and path.name != "yuba.lock.json"
            )
            for path in package_files:
                relative = path.relative_to(dependency).as_posix().encode("utf-8")
                contents = path.read_bytes()
                tree_hash.update(len(relative).to_bytes(8, "big"))
                tree_hash.update(relative)
                tree_hash.update(contents)

            archive = b"cached verified package artifact"
            artifact_hash = hashlib.sha256(archive).hexdigest()
            artifact_path = root / ".yuba" / "artifacts" / f"{artifact_hash}.tar.gz"
            artifact_path.parent.mkdir(parents=True)
            artifact_path.write_bytes(archive)
            write_package(
                root,
                "app",
                "import mylib\n"
                "define var result: int = 0\n"
                "func call mylib.answer -> result\n"
                "text output result\n",
            )
            source = {"registry": "^1.0.0"}
            resolved = {
                "version": "1.2.0",
                "registry": "https://packages.example.invalid",
                "artifact": "artifacts/mylib-1.2.0.tar.gz",
                "sha256": artifact_hash,
                "tree_sha256": tree_hash.hexdigest(),
            }
            manifest_path = root / "yuba.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["dependencies"] = {"mylib": source}
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            package_manifest = json.loads(
                (dependency / "yuba.json").read_text(encoding="utf-8")
            )
            (root / "yuba.lock.json").write_text(
                json.dumps(
                    {
                        "lock_version": 3,
                        "dependencies": {
                            "mylib": {
                                "source": source,
                                "resolved": resolved,
                                "package": {
                                    field: package_manifest[field]
                                    for field in ("name", "version", "entry", "yubalang")
                                },
                                "dependencies": {},
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(PackageError, "must be installed with"):
                install(root)
            checked = run_cli("package", "check", cwd=root)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            executed = run_cli(root / "main.yl", cwd=root)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            self.assertEqual(executed.stdout, "42\n")

            artifact_path.write_bytes(b"modified")
            with self.assertRaisesRegex(PackageError, "SHA-256 verification"):
                check(root)

    def test_imports_yubapkg_v1_lockfile_and_upgrades_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            dependency = root / "library"
            write_package(
                dependency,
                "library",
                "func define answer\n    return 42\nendfunc\n",
            )
            write_package(
                project,
                "app",
                "import library\n"
                "define var result: int = 0\n"
                "func call library.answer -> result\n"
                "text output result\n",
            )

            for package_root in (project, dependency):
                manifest_path = package_root / "yuba.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["yubalang"] = "1.2"
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            manifest_path = project / "yuba.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["dependencies"] = {"library": {"path": "../library"}}
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            (project / "yuba.lock.json").write_text(
                json.dumps(
                    {
                        "lock_version": 1,
                        "dependencies": {
                            "library": {
                                "source": {"path": "../library"},
                                "resolved": {"path": "../library"},
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            checked = run_cli("package", "check", cwd=project)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            executed = run_cli(project / "main.yl", cwd=project)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            self.assertEqual(executed.stdout, "42\n")

            installed = run_cli("package", "install", cwd=project)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            upgraded_lock = json.loads(
                (project / "yuba.lock.json").read_text(encoding="utf-8")
            )
            self.assertEqual(upgraded_lock["lock_version"], 2)

    def test_reports_dependency_cycles_during_install(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            library = root / "library"
            write_package(project, "app", "")
            write_package(library, "library", "")
            project_manifest = json.loads(
                (project / "yuba.json").read_text(encoding="utf-8")
            )
            project_manifest["dependencies"] = {"library": {"path": "../library"}}
            (project / "yuba.json").write_text(
                json.dumps(project_manifest), encoding="utf-8"
            )
            library_manifest = json.loads(
                (library / "yuba.json").read_text(encoding="utf-8")
            )
            library_manifest["dependencies"] = {"app": {"path": "../project"}}
            (library / "yuba.json").write_text(
                json.dumps(library_manifest), encoding="utf-8"
            )

            installed = run_cli("package", "install", cwd=project)

        self.assertEqual(installed.returncode, 1)
        self.assertIn("Dependency cycle detected: app -> library -> app", installed.stderr)

    def test_installs_and_imports_transitive_path_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            first = root / "first"
            second = root / "second"
            write_package(
                second,
                "second",
                "func define answer\n    return 42\nendfunc\n",
            )
            write_package(
                first,
                "first",
                "import second\n"
                "func define answer\n"
                "    define var result: int = 0\n"
                "    func call second.answer -> result\n"
                "    return result\n"
                "endfunc\n",
            )
            manifest_path = first / "yuba.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["dependencies"] = {"second": {"path": "../second"}}
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            write_package(
                project,
                "app",
                "import first\n"
                "define var result: int = 0\n"
                "func call first.answer -> result\n"
                "text output result\n",
            )
            manifest_path = project / "yuba.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["dependencies"] = {"first": {"path": "../first"}}
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            (project / "first.yl").write_text(
                "func define answer\n    return 99\nendfunc\n",
                encoding="utf-8",
            )

            installed = run_cli("package", "install", cwd=project)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            self.assertTrue((first / "yuba.lock.json").is_file())
            self.assertTrue((project / "yuba.lock.json").is_file())
            lock = json.loads(
                (project / "yuba.lock.json").read_text(encoding="utf-8")
            )
            self.assertEqual(lock["lock_version"], 2)
            self.assertIn(
                "second",
                lock["dependencies"]["first"]["dependencies"],
            )

            checked = run_cli("package", "check", cwd=project)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            executed = run_cli(project / "main.yl", cwd=project)

        self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
        self.assertEqual(executed.stdout, "42\n")

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
            self.assertIn("this runtime supports 1.2 and 1.3", incompatible.stderr)

            manifest["yubalang"] = "1.2"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            compatible = run_cli("package", "install", cwd=project)
            self.assertEqual(compatible.returncode, 0, compatible.stderr)

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

    def test_check_reports_changed_package_version(self):
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

            dependency_manifest_path = dependency / "yuba.json"
            dependency_manifest = json.loads(
                dependency_manifest_path.read_text(encoding="utf-8")
            )
            dependency_manifest["version"] = "0.2.0"
            dependency_manifest_path.write_text(
                json.dumps(dependency_manifest), encoding="utf-8"
            )

            with self.assertRaisesRegex(PackageError, "metadata differs from the lockfile"):
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

            cached_entry = project / ".yuba" / "packages" / "gitlib" / "main.yl"
            original_entry = cached_entry.read_text(encoding="utf-8")
            cached_entry.write_text(original_entry + "\n", encoding="utf-8")
            modified = run_cli("package", "check", cwd=project)
            self.assertEqual(modified.returncode, 1)
            self.assertIn("modified files", modified.stderr)
            cached_entry.write_text(original_entry, encoding="utf-8")
            untracked_file = (
                project / ".yuba" / "packages" / "gitlib" / "injected.yl"
            )
            untracked_file.write_text("", encoding="utf-8")
            untracked = run_cli("package", "check", cwd=project)
            self.assertEqual(untracked.returncode, 1)
            self.assertIn("modified files", untracked.stderr)
            untracked_file.unlink()

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
