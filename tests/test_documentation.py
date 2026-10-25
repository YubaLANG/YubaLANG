import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
ENTRY_POINT = REPOSITORY_ROOT / "YubaLANG.py"
DOCUMENTED_EXAMPLES = (
    "getting-started.yl",
    "functions.yl",
    "collections.yl",
    "strings_and_iteration.yl",
    "file_io.yl",
    "error_handling.yl",
    Path("modules") / "main.yl",
    Path("testing") / "smoke.yl",
)


def run_cli(*arguments, cwd=REPOSITORY_ROOT):
    return subprocess.run(
        [sys.executable, str(ENTRY_POINT), *map(str, arguments)],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


class DocumentationTests(unittest.TestCase):
    def test_runnable_documented_examples_pass_the_output_runner(self):
        for relative_path in DOCUMENTED_EXAMPLES:
            example = REPOSITORY_ROOT / "examples" / relative_path
            with self.subTest(example=relative_path):
                result = run_cli("test", example)
                self.assertEqual(
                    result.returncode, 0, result.stdout + result.stderr
                )
                self.assertIn("1 passed, 0 failed, 0 errored", result.stdout)

    def test_project_tutorial_path_dependency_and_test_flow(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            library = root / "hello_library"
            app = root / "hello_app"
            library.mkdir()
            app.mkdir()

            for folder, name, source in (
                (
                    library,
                    "hello_library",
                    'func define greet name\n    text output "Hello"\n'
                    "    text output name\nendfunc\n",
                ),
                (
                    app,
                    "hello_app",
                    "import hello_library\n"
                    'func call hello_library.greet "Ada"\n',
                ),
            ):
                (folder / "yuba.json").write_text(
                    json.dumps({
                        "name": name,
                        "version": "0.1.0",
                        "entry": "main.yl",
                        "yubalang": "1.3",
                        "dependencies": {},
                    }),
                    encoding="utf-8",
                )
                (folder / "main.yl").write_text(source, encoding="utf-8")

            test_directory = app / "tests" / "cases"
            test_directory.mkdir(parents=True)
            (test_directory / "greeting.yl").write_text(
                'import hello_library\nfunc call hello_library.greet "Ada"\n',
                encoding="utf-8",
            )
            (test_directory / "greeting.expected.txt").write_text(
                "Hello\nAda\n", encoding="utf-8"
            )

            added = run_cli(
                "package", "add", "hello_library", "--path", "../hello_library",
                cwd=app,
            )
            self.assertEqual(added.returncode, 0, added.stdout + added.stderr)

            executed = run_cli("run", ".", cwd=app)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            self.assertEqual(executed.stdout, "Hello\nAda\n")

            tested = run_cli("test", "tests/cases", cwd=app)
            self.assertEqual(tested.returncode, 0, tested.stdout + tested.stderr)
            self.assertIn("1 passed, 0 failed, 0 errored", tested.stdout)


if __name__ == "__main__":
    unittest.main()
