import contextlib
import ctypes
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from lang.interpreter import Runtime, execute_lines


class CAbiTests(unittest.TestCase):
    def test_calls_c_function_with_fixed_width_integer_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            library_path = folder / ("native.dll" if os.name == "nt" else "libnative.so")
            library_path.touch()
            source_path = folder / "program.hl"
            function = mock.Mock(return_value=42)
            library = mock.Mock()
            library.add_i32 = function
            runtime = Runtime()

            with mock.patch("lang.ffi.ctypes.CDLL", return_value=library) as load_library:
                execute_lines(
                    [
                        "define var left: int = 40",
                        "define var result: int = 0",
                        'ffi call "native.dll" add_i32 i32 i32 left i32 2 -> result'
                        if os.name == "nt"
                        else 'ffi call "libnative.so" add_i32 i32 i32 left i32 2 -> result',
                    ],
                    runtime,
                    str(source_path),
                )

            load_library.assert_called_once()
            loaded_path = Path(load_library.call_args.args[0])
            self.assertTrue(loaded_path.samefile(library_path))
            self.assertEqual(function.argtypes, [ctypes.c_int32, ctypes.c_int32])
            self.assertIs(function.restype, ctypes.c_int32)
            function.assert_called_once_with(40, 2)
            self.assertEqual(runtime.require_var("result")["value"], 42)
            self.assertEqual(len(runtime.native_libraries), 1)

    def test_calls_void_function_and_checks_bool_and_float_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            library_name = "native.dll" if os.name == "nt" else "libnative.so"
            (folder / library_name).touch()
            function = mock.Mock(return_value=None)
            library = mock.Mock()
            library.update_values = function
            runtime = Runtime()

            with mock.patch("lang.ffi.ctypes.CDLL", return_value=library):
                execute_lines(
                    [
                        "define var enabled: bool = true",
                        "define var ratio: float = 2.5",
                        f'ffi call "{library_name}" update_values void bool enabled f64 ratio',
                    ],
                    runtime,
                    str(folder / "program.hl"),
                )

            self.assertEqual(function.argtypes, [ctypes.c_bool, ctypes.c_double])
            self.assertIsNone(function.restype)
            function.assert_called_once_with(True, 2.5)

    def test_invalid_signature_fails_before_native_call(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            library_name = "native.dll" if os.name == "nt" else "libnative.so"
            (folder / library_name).touch()
            function = mock.Mock(return_value=1)
            library = mock.Mock()
            library.get_value = function

            with mock.patch("lang.ffi.ctypes.CDLL", return_value=library):
                with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
                    execute_lines(
                        [
                            "define var result: int = 0",
                            f'ffi call "{library_name}" get_value i32 i32 2147483648 -> result',
                        ],
                        Runtime(),
                        str(folder / "program.hl"),
                    )

            function.assert_not_called()

    def test_rejects_incompatible_result_variable_before_native_call(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            library_name = "native.dll" if os.name == "nt" else "libnative.so"
            (folder / library_name).touch()
            function = mock.Mock(return_value=1)
            library = mock.Mock()
            library.get_value = function
            output = io.StringIO()

            with mock.patch("lang.ffi.ctypes.CDLL", return_value=library):
                with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
                    execute_lines(
                        [
                            "define var result: float = 0.0",
                            f'ffi call "{library_name}" get_value i32 -> result',
                        ],
                        Runtime(),
                        str(folder / "program.hl"),
                    )

            self.assertIn("requires a YubaLANG int destination", output.getvalue())
            function.assert_not_called()

    def test_reports_missing_library_and_symbol(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source_path = str(folder / "program.hl")
            output = io.StringIO()
            with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
                execute_lines(
                    [
                        "define var result: int = 0",
                        'ffi call "missing.so" get_value i32 -> result',
                    ],
                    Runtime(),
                    source_path,
                )
            self.assertIn("C library file", output.getvalue())

            library_path = folder / ("native.dll" if os.name == "nt" else "libnative.so")
            library_path.touch()
            with mock.patch("lang.ffi.ctypes.CDLL", return_value=object()):
                output = io.StringIO()
                with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
                    execute_lines(
                        [
                            "define var result: int = 0",
                            f'ffi call "{library_path.name}" missing i32 -> result',
                        ],
                        Runtime(),
                        source_path,
                    )
            self.assertIn("was not found", output.getvalue())

    def test_loads_and_calls_compiled_c_function_when_compiler_is_available(self):
        compiler = shutil.which("cl" if os.name == "nt" else "cc")
        if compiler is None:
            self.skipTest("No native C compiler is available.")

        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = Path(__file__).parent.parent / "examples" / "ffi_add.c"
            if os.name == "nt":
                library_path = folder / "native_add.dll"
                command = [
                    compiler, "/nologo", "/LD", str(source),
                    f"/link", f"/OUT:{library_path}",
                ]
            else:
                extension = ".dylib" if sys.platform == "darwin" else ".so"
                library_path = folder / f"libnative_add{extension}"
                command = [
                    compiler, "-shared", "-fPIC", str(source), "-o", str(library_path),
                ]
            subprocess.run(command, cwd=folder, check=True, capture_output=True, text=True)

            runtime = Runtime()
            execute_lines(
                [
                    "define var result: int = 0",
                    f'ffi call "{library_path.name}" yubalang_add_i32 i32 i32 19 i32 23 -> result',
                ],
                runtime,
                str(folder / "program.hl"),
            )
            self.assertEqual(runtime.require_var("result")["value"], 42)


if __name__ == "__main__":
    unittest.main()
