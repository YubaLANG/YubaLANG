import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from lang.formatter import FormatError, format_source
from lang.interpreter import execute_lines
from lang.runtime import Runtime


FIXTURES = Path(__file__).parent / "formatter"


class FormatterTests(unittest.TestCase):
    def test_formats_fixture_and_is_idempotent(self):
        source = (FIXTURES / "style.input.txt").read_text(encoding="utf-8")
        expected = (FIXTURES / "style.expected.hl").read_text(encoding="utf-8")

        formatted = format_source(source)

        self.assertEqual(formatted, expected)
        self.assertEqual(format_source(formatted), formatted)

    def test_formatting_preserves_program_output(self):
        source = (FIXTURES / "style.input.txt").read_text(encoding="utf-8")
        formatted = format_source(source)
        outputs = []

        for program in (source, formatted):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                execute_lines(program.splitlines(), Runtime())
            outputs.append(output.getvalue())

        self.assertEqual(outputs[0], outputs[1])

    def test_reports_unterminated_string(self):
        with self.assertRaisesRegex(FormatError, r"line 1: invalid command quoting"):
            format_source('text output "unfinished\n')

    def test_reports_unclosed_and_mismatched_blocks(self):
        with self.assertRaisesRegex(FormatError, r"line 1: missing endif"):
            format_source("if true\ntext output 'yes'\n")
        with self.assertRaisesRegex(FormatError, r"line 1: endif without a matching block"):
            format_source("endif\n")

    def test_check_accepts_windows_line_endings(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "sample.hl"
            with source.open("w", encoding="utf-8", newline="") as output_file:
                output_file.write("text output 'ok'\r\n")

            result = subprocess.run(
                [sys.executable, "YubaLANG.py", "fmt", "--check", str(source)],
                capture_output=True, text=True, check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("All files are formatted.", result.stdout)

    def test_cli_check_and_write_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "sample.hl"
            source.write_text("if true\ntext output 'ok'\nendif", encoding="utf-8")

            check = subprocess.run(
                [sys.executable, "YubaLANG.py", "fmt", "--check", str(source)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(check.returncode, 1)
            self.assertIn("Would reformat", check.stdout)
            self.assertEqual(source.read_text(encoding="utf-8"), "if true\ntext output 'ok'\nendif")

            write = subprocess.run(
                [sys.executable, "YubaLANG.py", "fmt", "--write", str(source)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(write.returncode, 0, write.stderr)
            self.assertEqual(
                source.read_text(encoding="utf-8"),
                "if true\n    text output 'ok'\nendif\n",
            )

            check_again = subprocess.run(
                [sys.executable, "YubaLANG.py", "fmt", "--check", str(source)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(check_again.returncode, 0, check_again.stderr)


if __name__ == "__main__":
    unittest.main()
