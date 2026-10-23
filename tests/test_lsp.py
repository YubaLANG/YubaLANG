import io
import json
import subprocess
import sys
import unittest

from lang.lsp import LanguageServer, _read_message, analyze_document, serve


def _frame(message):
    content = json.dumps(message).encode("utf-8")
    return f"Content-Length: {len(content)}\r\n\r\n".encode("ascii") + content


def _read_frames(stream):
    stream.seek(0)
    messages = []
    while stream.tell() < len(stream.getvalue()):
        messages.append(_read_message(stream))
    return messages


class LanguageServerTests(unittest.TestCase):
    def test_reports_syntax_diagnostics_with_source_ranges(self):
        diagnostics = analyze_document(
            'define var value: mystery = 1\n'
            'unknown command\n'
            'text output "unterminated\n'
            'if true\n'
        )

        self.assertEqual(
            [item["code"] for item in diagnostics],
            ["unknown-type", "unknown-command", "invalid-quoting", "unclosed-block"],
        )
        self.assertEqual(diagnostics[1]["range"]["start"], {"line": 1, "character": 0})
        self.assertEqual(diagnostics[1]["range"]["end"], {"line": 1, "character": 15})

    def test_recognizes_ffi_command_and_provides_hover(self):
        source = 'ffi call "./libnative.so" add i32 i32 1 -> result\n'
        self.assertEqual(analyze_document(source), [])

        server = LanguageServer()
        uri = "file:///ffi.yl"
        server.documents[uri] = source
        hover, _ = server.handle({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "textDocument/hover",
            "params": {
                "textDocument": {"uri": uri},
                "position": {"line": 0, "character": 1},
            },
        })
        self.assertIn("C ABI function", hover["result"]["contents"]["value"])

    def test_recognizes_import_syntax_and_provides_hover(self):
        self.assertEqual(analyze_document("import helpers as tools\n"), [])
        self.assertEqual(
            analyze_document("import helpers from somewhere\n")[0]["message"],
            "Usage: import <module> [as <namespace>]",
        )

        server = LanguageServer()
        uri = "file:///imports.yl"
        server.documents[uri] = "import helpers\n"
        hover, _ = server.handle({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "textDocument/hover",
            "params": {
                "textDocument": {"uri": uri},
                "position": {"line": 0, "character": 1},
            },
        })
        self.assertIn("loads a local or installed module", hover["result"]["contents"]["value"])

    def test_definition_and_hover_for_variable_function_and_builtin(self):
        server = LanguageServer()
        uri = "file:///sample.yl"
        source = (
            "define var number: int = 1\n"
            "func define identity value\n"
            "    return value\n"
            "endfunc\n"
            "func call identity number\n"
            "text output number\n"
        )
        server.documents[uri] = source

        definition, _ = server.handle({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "textDocument/definition",
            "params": {"textDocument": {"uri": uri}, "position": {"line": 5, "character": 13}},
        })
        self.assertEqual(definition["result"][0]["range"]["start"]["line"], 0)

        function_definition, _ = server.handle({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "textDocument/definition",
            "params": {"textDocument": {"uri": uri}, "position": {"line": 4, "character": 11}},
        })
        self.assertEqual(function_definition["result"][0]["range"]["start"]["line"], 1)

        hover, _ = server.handle({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "textDocument/hover",
            "params": {"textDocument": {"uri": uri}, "position": {"line": 5, "character": 2}},
        })
        self.assertIn("prints a value", hover["result"]["contents"]["value"])

    def test_document_sync_publishes_and_clears_diagnostics(self):
        server = LanguageServer()
        uri = "file:///sample.yl"
        _, published = server.handle({
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": uri, "text": "not_a_command\n"}},
        })
        self.assertEqual(published[0]["params"]["diagnostics"][0]["code"], "unknown-command")

        _, changed = server.handle({
            "jsonrpc": "2.0",
            "method": "textDocument/didChange",
            "params": {
                "textDocument": {"uri": uri, "version": 2},
                "contentChanges": [{"text": "text output \"ok\"\n"}],
            },
        })
        self.assertEqual(changed[0]["params"]["diagnostics"], [])

        _, closed = server.handle({
            "jsonrpc": "2.0",
            "method": "textDocument/didClose",
            "params": {"textDocument": {"uri": uri}},
        })
        self.assertEqual(closed[0]["params"]["diagnostics"], [])
        self.assertNotIn(uri, server.documents)

    def test_stdio_protocol_initializes_and_exits(self):
        incoming = io.BytesIO(
            _frame({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
            + _frame({"jsonrpc": "2.0", "method": "exit"})
        )
        outgoing = io.BytesIO()

        serve(incoming, outgoing)

        responses = _read_frames(outgoing)
        self.assertEqual(responses[0]["result"]["capabilities"]["textDocumentSync"]["change"], 1)
        self.assertTrue(responses[0]["result"]["capabilities"]["definitionProvider"])

    def test_cli_starts_stdio_server(self):
        incoming = (
            _frame({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
            + _frame({"jsonrpc": "2.0", "method": "exit"})
        )
        process = subprocess.run(
            [sys.executable, "YubaLANG.py", "--lsp"],
            input=incoming,
            capture_output=True,
            check=False,
        )

        self.assertEqual(process.returncode, 0, process.stderr.decode("utf-8"))
        self.assertTrue(process.stdout.startswith(b"Content-Length: "))


if __name__ == "__main__":
    unittest.main()
