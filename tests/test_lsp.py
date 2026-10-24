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
    def test_initialize_advertises_editor_features(self):
        server = LanguageServer()
        response, _ = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        capabilities = response["result"]["capabilities"]
        for feature in (
            "completionProvider", "signatureHelpProvider", "referencesProvider",
            "renameProvider", "documentSymbolProvider", "workspaceSymbolProvider",
            "codeActionProvider",
        ):
            self.assertIn(feature, capabilities)

    def test_completion_includes_commands_and_document_symbols(self):
        server = LanguageServer()
        uri = "file:///completion.yl"
        server.documents[uri] = "define var count: int = 1\nfunc define calculate value\nendfunc\n"
        response, _ = server.handle({
            "jsonrpc": "2.0", "id": 1, "method": "textDocument/completion",
            "params": {
                "textDocument": {"uri": uri},
                "position": {"line": 0, "character": 0},
            },
        })
        labels = {item["label"] for item in response["result"]["items"]}
        self.assertIn("compare", labels)
        self.assertIn("count", labels)
        self.assertIn("calculate", labels)

    def test_signature_help_for_user_function(self):
        server = LanguageServer()
        uri = "file:///signature.yl"
        server.documents[uri] = (
            "func define greet name greeting=hello\nendfunc\n"
            "func call greet Ada "
        )
        response, _ = server.handle({
            "jsonrpc": "2.0", "id": 1, "method": "textDocument/signatureHelp",
            "params": {
                "textDocument": {"uri": uri},
                "position": {"line": 2, "character": len("func call greet Ada ")},
            },
        })
        self.assertEqual(response["result"]["signatures"][0]["label"], "greet(name, greeting=hello)")
        self.assertEqual(response["result"]["activeParameter"], 1)

    def test_signature_help_and_parameter_symbols_support_types(self):
        server = LanguageServer()
        uri = "file:///typed-signature.yl"
        server.documents[uri] = (
            "func define increment value:int -> int\n"
            "    return value\n"
            "endfunc\n"
            "func call increment "
        )
        signature, _ = server.handle({
            "jsonrpc": "2.0", "id": 1, "method": "textDocument/signatureHelp",
            "params": {
                "textDocument": {"uri": uri},
                "position": {"line": 3, "character": len("func call increment ")},
            },
        })
        self.assertEqual(
            signature["result"]["signatures"][0]["label"],
            "increment(value:int) -> int",
        )
        references, _ = server.handle({
            "jsonrpc": "2.0", "id": 2, "method": "textDocument/references",
            "params": {
                "textDocument": {"uri": uri},
                "position": {"line": 1, "character": 12},
                "context": {"includeDeclaration": True},
            },
        })
        self.assertEqual(len(references["result"]), 2)

    def test_references_rename_and_document_symbols(self):
        server = LanguageServer()
        uri = "file:///symbols.yl"
        server.documents[uri] = (
            "define var count: int = 1\n"
            "func define read_count\n"
            "    return count\n"
            "endfunc\n"
            "text output count\n"
        )
        params = {
            "textDocument": {"uri": uri},
            "position": {"line": 0, "character": 13},
        }
        references, _ = server.handle({
            "jsonrpc": "2.0", "id": 1, "method": "textDocument/references",
            "params": {**params, "context": {"includeDeclaration": True}},
        })
        self.assertEqual(len(references["result"]), 3)
        rename, _ = server.handle({
            "jsonrpc": "2.0", "id": 2, "method": "textDocument/rename",
            "params": {**params, "newName": "total"},
        })
        self.assertEqual(len(rename["result"]["changes"][uri]), 3)
        symbols, _ = server.handle({
            "jsonrpc": "2.0", "id": 3, "method": "textDocument/documentSymbol",
            "params": {"textDocument": {"uri": uri}},
        })
        self.assertEqual({item["name"] for item in symbols["result"]}, {"count", "read_count"})

    def test_workspace_symbols_and_unknown_command_quick_fix(self):
        server = LanguageServer()
        uri = "file:///quickfix.yl"
        source = "func define calculate\nendfunc\ntex output count\n"
        server.documents[uri] = source
        workspace, _ = server.handle({
            "jsonrpc": "2.0", "id": 1, "method": "workspace/symbol",
            "params": {"query": "calcul"},
        })
        self.assertEqual(workspace["result"][0]["name"], "calculate")
        diagnostic = analyze_document(source)[0]
        actions, _ = server.handle({
            "jsonrpc": "2.0", "id": 2, "method": "textDocument/codeAction",
            "params": {
                "textDocument": {"uri": uri},
                "context": {"diagnostics": [diagnostic]},
            },
        })
        self.assertIn("Replace 'tex' with 'text'", actions["result"][0]["title"])
        edit = actions["result"][0]["edit"]["changes"][uri][0]
        self.assertEqual(edit["newText"], "text")
        self.assertEqual(edit["range"]["start"], {"line": 2, "character": 0})
        self.assertEqual(edit["range"]["end"], {"line": 2, "character": 3})

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

    def test_reports_definite_type_mismatches_without_executing_source(self):
        diagnostics = analyze_document(
            'define var label: string = ""\n'
            "define var values: list = [1, 2]\n"
            "list len values label\n"
        )
        mismatch = next(item for item in diagnostics if item["code"] == "type-mismatch")
        self.assertEqual(mismatch["range"]["start"], {"line": 2, "character": 0})
        self.assertIn("destination 'label' has type 'string'", mismatch["message"])

    def test_reports_invalid_assert_types_and_unknown_conversion_types(self):
        diagnostics = analyze_document(
            "assert 1\n"
            "convert value to integer\n"
        )
        self.assertEqual(
            [item["code"] for item in diagnostics],
            ["type-mismatch", "unknown-type"],
        )
        self.assertIn("assert condition has type 'int'", diagnostics[0]["message"])
        self.assertIn("Unknown type: integer", diagnostics[1]["message"])

    def test_record_types_are_recognized_and_field_mismatches_reported(self):
        diagnostics = analyze_document(
            "record define Point x:int y:string\n"
            "define var origin: Point = origin\n"
            "record create Point point 1 false\n"
        )
        self.assertTrue(any(item["code"] == "type-mismatch" for item in diagnostics))
        self.assertFalse(any(item["code"] == "unknown-type" for item in diagnostics))
        mismatch = next(item for item in diagnostics if item["code"] == "type-mismatch")
        self.assertIn("field 'y' requires 'string'", mismatch["message"])

    def test_function_parameter_defaults_are_validated(self):
        self.assertEqual(
            analyze_document(
                "func define greet name greeting=hello\n"
                "endfunc\n"
            ),
            [],
        )
        diagnostic = analyze_document(
            "func define greet greeting=hello name\n"
        )[0]
        self.assertIn("required parameters must come first", diagnostic["message"])
        self.assertEqual(
            analyze_document("func define collect first *rest\nendfunc\n"),
            [],
        )

    def test_exception_blocks_are_recognized_and_checked(self):
        self.assertEqual(
            analyze_document(
                'try\nthrow "problem"\ncatch error\nfinally\nendtry\n'
            ),
            [],
        )
        diagnostics = analyze_document("catch error\n")
        self.assertIn("without an open try block", diagnostics[0]["message"])

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

    def test_recognizes_assert_command_and_validates_arity(self):
        self.assertEqual(analyze_document('assert ready "not ready"\n'), [])
        diagnostics = analyze_document("assert\n")
        self.assertEqual(diagnostics[0]["message"], "Usage: assert <boolean> [message]")

    def test_recognizes_close_command_and_validates_arity(self):
        self.assertEqual(analyze_document("close handle\n"), [])
        diagnostics = analyze_document("close\n")
        self.assertEqual(diagnostics[0]["message"], "Usage: close <file_variable>")

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

    def test_stale_document_changes_do_not_replace_newer_text(self):
        server = LanguageServer()
        uri = "file:///versioned.yl"
        server.handle({
            "jsonrpc": "2.0", "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": uri, "version": 4, "text": "text output 4\n"}},
        })
        _, stale = server.handle({
            "jsonrpc": "2.0", "method": "textDocument/didChange",
            "params": {
                "textDocument": {"uri": uri, "version": 3},
                "contentChanges": [{"text": "unknown\n"}],
            },
        })
        self.assertEqual(stale, [])
        self.assertEqual(server.documents[uri], "text output 4\n")

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
