import argparse
from pathlib import Path
import subprocess
import tempfile


def _run(executable: Path, *arguments: str, cwd: Path) -> str:
    process = subprocess.run(
        [str(executable), *arguments],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if process.returncode:
        raise RuntimeError(
            f"{executable.name} {' '.join(arguments)} failed "
            f"({process.returncode}):\n{process.stdout}{process.stderr}"
        )
    return process.stdout


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Smoke-test an installed standalone YubaLANG executable."
    )
    parser.add_argument("executable", type=Path)
    executable = parser.parse_args().executable.resolve()

    with tempfile.TemporaryDirectory(prefix="yubalang-release-smoke-") as directory:
        workspace = Path(directory)
        project = workspace / "app"
        _run(executable, "package", "init", str(project), cwd=workspace)
        (project / "helper.yl").write_text(
            'func define greeting -> string\n'
            '    return "standalone install"\n'
            'endfunc\n',
            encoding="utf-8",
        )
        (project / "main.yl").write_text(
            "import helper\n"
            "define var message: string = \"\"\n"
            "func call helper.greeting -> message\n"
            "text output message\n",
            encoding="utf-8",
        )
        cases = project / "tests" / "cases"
        cases.mkdir(parents=True)
        (cases / "smoke.yl").write_text(
            'text output "test runner"\n', encoding="utf-8"
        )
        (cases / "smoke.expected.txt").write_text(
            "test runner\n", encoding="utf-8"
        )

        _run(executable, "package", "install", cwd=project)
        _run(executable, "package", "check", cwd=project)
        output = _run(executable, "run", str(project), cwd=workspace)
        if output != "standalone install\n":
            raise RuntimeError(f"Unexpected project output: {output!r}")
        test_output = _run(
            executable, "test", "tests/cases", cwd=project
        )
        if "1 passed, 0 failed, 0 errored" not in test_output:
            raise RuntimeError(f"Unexpected test-runner output: {test_output}")
        _run(executable, "fmt", "--check", str(project), cwd=workspace)
        print("Standalone initialization, restore, imports, run, test, and format passed.")


if __name__ == "__main__":
    main()
