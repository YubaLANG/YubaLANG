"""A lightweight stdio Language Server Protocol implementation for YubaLANG."""

import json
import re
import sys
from typing import Any, BinaryIO

from .interpreter import _split
from .runtime import TYPES


_IDENTIFIER = re.compile(r"[A-Za-z_]\w*")
_LEXEME = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|#[^\r\n]*|[A-Za-z_]\w*')
_COMMANDS = {
    "all", "any", "arith", "ascii", "bool", "break", "bytearray", "bytes",
    "callable", "chr", "compare", "continue", "convert", "define", "dict",
    "enumerate", "ffi", "filter", "format", "func", "getattr", "hasattr", "if",
    "id", "import", "iter", "len", "list", "loop", "map", "next", "open", "ord",
    "range", "repr",
    "return", "reversed", "set", "setattr", "slice", "sorted", "text",
    "tuple", "type", "vars", "wait", "zip",
}
_ARITY: dict[str, tuple[int, ...]] = {
    "all": (3,), "any": (3,), "ascii": (3,), "bool": (3,),
    "bytearray": (3,), "bytes": (3,), "callable": (3,), "chr": (3,),
    "compare": (5,), "convert": (3, 4), "enumerate": (3, 4),
    "filter": (4,), "format": (3, 4), "getattr": (4,), "hasattr": (4,),
    "id": (3,), "import": (2, 4),
    "iter": (3,), "len": (3,), "map": (4,), "next": (3, 4),
    "ord": (3,), "range": (3, 4, 5), "repr": (3,), "reversed": (3,),
    "setattr": (4,), "slice": (5, 6), "sorted": (3, 4), "type": (3,),
    "vars": (1,), "wait": (2,),
}
_HOVER: dict[str, str] = {
    "define": "**`define var <name>: <type> = <value>`** declares a variable.",
    "convert": "**`convert <variable> to <type>`** changes a variable's value and type.",
    "arith": "**`arith <operation> <value> [value]`** performs arithmetic and prints the result.",
    "compare": "**`compare <left> <operator> <right> <bool_variable>`** stores a comparison.",
    "dict": (
        "**`dict set <variable> <key> <value>`** or "
        "**`dict get <variable> <key> <destination>`** accesses a dictionary."
    ),
    "list": (
        "**`list append <variable> <value>`**, "
        "**`list get <variable> <index> <destination>`**, and "
        "**`list len <variable> <destination>`** operate on lists."
    ),
    "set": (
        "**`set add <variable> <value>`** and "
        "**`set remove <variable> <value>`** modify a set."
    ),
    "tuple": "**`tuple get <variable> <index> <destination>`** reads a tuple value.",
    "text": (
        "**`text output <value>`** prints a value; "
        "**`text input <string_variable>`** reads a line."
    ),
    "input": "**`text input <string_variable>`** reads a line into a string variable.",
    "output": "**`text output <value>`** prints a value.",
    "func": (
        "**`func define <name> [parameters] ... endfunc`** defines a function; "
        "use `func call` to call it."
    ),
    "import": (
        "**`import <module> [as <namespace>]`** loads a local or installed "
        "module; call its functions with `func call namespace.function`."
    ),
    "if": "**`if <condition>`** starts a conditional block. Close it with `endif`.",
    "elseif": "**`elseif <condition>`** adds a conditional branch.",
    "else": "**`else`** adds the fallback branch to an `if` block.",
    "endif": "**`endif`** closes an `if` block.",
    "loop": (
        "**`loop for <count>`** or **`loop while <condition>`** starts a loop. "
        "Close it with `endloop`."
    ),
    "endloop": "**`endloop`** closes a loop.",
    "return": "**`return [value]`** exits the current function.",
    "break": "**`break`** exits the current loop.",
    "continue": "**`continue`** advances to the next loop iteration.",
    "endfunc": "**`endfunc`** closes a function definition.",
    "append": "**`list append <variable> <value>`** adds a value to the end of a list.",
    "get": "**`list get <variable> <index> <destination>`** reads a collection value.",
    "add": "**`set add <variable> <value>`** adds a value to a set.",
    "remove": "**`set remove <variable> <value>`** removes a value from a set.",
    "all": (
        "**`all <collection> <bool_destination>`** tests whether every "
        "collection value is truthy."
    ),
    "any": (
        "**`any <collection> <bool_destination>`** tests whether any "
        "collection value is truthy."
    ),
    "bool": "**`bool <value> <bool_destination>`** converts a value to boolean.",
    "bytearray": (
        "**`bytearray <value> <destination>`** converts a value to bytes in "
        "a mutable byte array."
    ),
    "bytes": "**`bytes <value> <destination>`** converts a value to bytes.",
    "callable": "**`callable <name> <bool_destination>`** checks whether a function exists.",
    "chr": "**`chr <integer> <string_destination>`** converts a code point to a character.",
    "enumerate": (
        "**`enumerate <iterable> <list_destination> [start]`** creates "
        "index/value pairs."
    ),
    "filter": (
        "**`filter <function> <iterable> <list_destination>`** keeps values "
        "accepted by a function."
    ),
    "format": "**`format <value> <format_spec> <string_destination>`** formats a value.",
    "ffi": (
        "**`ffi call <library> <symbol> <return-type> [<argument-type> <value> ...] "
        "[-> <destination>]`** calls a local C ABI function using fixed-width "
        "integer, double, and boolean values."
    ),
    "getattr": "**`getattr <variable> <attribute> <destination>`** reads an attribute.",
    "hasattr": "**`hasattr <variable> <attribute> <bool_destination>`** checks an attribute.",
    "id": "**`id <variable> <integer_destination>`** returns the identity of a value.",
    "iter": "**`iter <iterable> <iterator_destination>`** creates an iterator.",
    "len": "**`len <variable> <integer_destination>`** stores the length of a value.",
    "map": "**`map <function> <iterable> <list_destination>`** applies a function to each value.",
    "next": "**`next <iterator> <destination> [default]`** gets the next iterator value.",
    "open": "**`open <path> <mode> <file_variable>`** opens a file and stores its handle.",
    "ord": "**`ord <character> <integer_destination>`** converts a character to its code point.",
    "range": "**`range <stop> <list_destination>`** creates a list of integers.",
    "repr": "**`repr <value> <string_destination>`** stores the representation of a value.",
    "reversed": "**`reversed <iterable> <list_destination>`** stores values in reverse order.",
    "slice": (
        "**`slice <sequence> <start> <stop> <destination> [step]`** selects "
        "a sequence slice."
    ),
    "sorted": "**`sorted <iterable> <list_destination> [reverse]`** sorts an iterable.",
    "type": "**`type <variable> <string_destination>`** stores the declared type.",
    "vars": "**`vars`** prints active variables and functions.",
    "wait": "**`wait <seconds>`** pauses execution.",
    "zip": "**`zip <iterable1> <iterable2> [...] <list_destination>`** combines iterables.",
    "abs": "**`arith abs <value>`** returns the absolute value.",
    "bin": "**`arith bin <integer>`** prints the binary representation.",
    "divmod": "**`arith divmod <left> <right>`** returns the quotient and remainder.",
    "hex": "**`arith hex <integer>`** prints the hexadecimal representation.",
    "max": "**`arith max <collection>`** returns the largest value.",
    "min": "**`arith min <collection>`** returns the smallest value.",
    "oct": "**`arith oct <integer>`** prints the octal representation.",
    "pow": "**`arith pow <base> <exponent>`** raises a value to a power.",
    "round": "**`arith round <value>`** rounds a number.",
    "sum": "**`arith sum <collection>`** totals a collection.",
}
for _type_name in TYPES:
    _HOVER[_type_name] = (
        _HOVER.get(_type_name, "")
        + f"\n\nYubaLANG **`{_type_name}`** type."
    ).strip()


def _utf16_length(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _character_offset(text: str, utf16_column: int) -> int:
    units = 0
    for offset, character in enumerate(text):
        next_units = units + (2 if ord(character) > 0xFFFF else 1)
        if next_units > utf16_column:
            return offset
        units = next_units
    return len(text)


def _position(line: int, column: int) -> dict[str, int]:
    return {"line": line, "character": column}


def _diagnostic(line_number: int, line: str, message: str, code: str) -> dict[str, Any]:
    return {
        "range": {
            "start": _position(line_number, 0),
            "end": _position(line_number, _utf16_length(line)),
        },
        "severity": 1,
        "code": code,
        "source": "YubaLANG",
        "message": message,
    }


def analyze_document(source: str) -> list[dict[str, Any]]:
    """Return static syntax diagnostics without executing the document."""
    lines = source.splitlines()
    diagnostics: list[dict[str, Any]] = []
    blocks: list[tuple[str, int]] = []

    for line_number, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            parts = _split(line)
        except SyntaxError as error:
            diagnostics.append(_diagnostic(line_number, raw_line, str(error), "invalid-quoting"))
            continue
        if not parts:
            continue

        command = parts[0]
        error: str | None = None
        code = "invalid-syntax"
        if command == "if":
            if len(parts) != 2:
                error = "Usage: if <condition>"
            else:
                blocks.append(("if", line_number))
        elif command == "func":
            if len(parts) >= 3 and parts[1] == "define":
                if not all(_IDENTIFIER.fullmatch(name) for name in parts[2:]):
                    error = "Function name and parameters must be identifiers."
                else:
                    blocks.append(("func", line_number))
            elif len(parts) < 3 or parts[1] != "call":
                error = "Usage: func define <name> [parameters] or func call <name> [arguments]"
        elif command == "loop":
            if len(parts) != 3 or parts[1] not in ("for", "while"):
                error = "Usage: loop for <count> or loop while <condition>"
            else:
                blocks.append(("loop", line_number))
        elif command in ("elseif", "else", "endif", "endfunc", "endloop"):
            expected = {"elseif": "if", "else": "if", "endif": "if",
                        "endfunc": "func", "endloop": "loop"}[command]
            if len(parts) != 1 and command != "elseif":
                error = f"'{command}' does not take arguments."
            elif command == "elseif" and len(parts) != 2:
                error = "Usage: elseif <condition>"
            elif not blocks or blocks[-1][0] != expected:
                error = f"Unexpected '{command}' without an open {expected} block."
            elif command in ("endif", "endfunc", "endloop"):
                blocks.pop()
        elif command not in _COMMANDS:
            code = "unknown-command"
            error = f"Unknown command: {command}"
        elif command == "define":
            if (
                len(parts) < 6 or parts[1] != "var"
                or not parts[2].endswith(":") or parts[4] != "="
            ):
                error = "Usage: define var <name>: <type> = <value>"
            elif parts[3] not in TYPES:
                code = "unknown-type"
                error = f"Unknown type: {parts[3]}"
        elif command in _ARITY and len(parts) not in _ARITY[command]:
            error = f"Invalid {command} command or arguments."
        elif command == "import" and len(parts) == 4 and parts[2] != "as":
            error = "Usage: import <module> [as <namespace>]"
        elif command == "convert" and len(parts) == 4 and parts[2] != "to":
            error = "Usage: convert <variable> to <type>"
        elif command == "arith" and len(parts) not in (3, 4):
            error = "Usage: arith <operation> <value> [value]"
        elif command == "text":
            if len(parts) < 3 or parts[1] not in ("input", "output"):
                error = "Usage: text output <value> or text input <string_variable>"
            elif parts[1] == "input" and len(parts) != 3:
                error = "Usage: text input <string_variable>"
        elif command == "open" and len(parts) != 4:
            error = "Usage: open <path> <mode> <file_variable>"
        elif command in ("list", "dict", "set", "tuple"):
            operation_lengths = {
                "list": {"append": (4,), "get": (5,), "len": (4,)},
                "dict": {"get": (5,), "set": (5,)},
                "set": {"add": (4,), "remove": (4,)},
                "tuple": {"get": (5,)},
            }
            if len(parts) < 2 or len(parts) not in operation_lengths[command].get(parts[1], ()):
                error = f"Invalid {command} operation or arguments."

        if error is not None:
            diagnostics.append(_diagnostic(line_number, raw_line, error, code))

    for block, line_number in blocks:
        diagnostics.append(
            _diagnostic(
                line_number, lines[line_number],
                f"Missing closing command for {block} block.", "unclosed-block",
            )
        )
    return diagnostics


def _identifier_positions(line: str) -> list[tuple[str, int]]:
    result = []
    for match in _LEXEME.finditer(line):
        value = match.group()
        if value.startswith("#") or value.startswith(("'", '"')):
            continue
        result.append((value, _utf16_length(line[:match.start()])))
    return result


def _symbols(source: str) -> dict[str, dict[str, int]]:
    definitions: dict[str, dict[str, int]] = {}
    for line_number, line in enumerate(source.splitlines()):
        try:
            parts = _split(line.strip())
        except SyntaxError:
            continue
        identifiers = _identifier_positions(line)
        name: str | None = None
        if len(parts) >= 3 and parts[:2] == ["define", "var"]:
            name = parts[2].removesuffix(":")
        elif len(parts) >= 3 and parts[:2] == ["func", "define"]:
            name = parts[2]
        if name:
            location = next(((word, column) for word, column in identifiers if word == name), None)
            if location:
                definitions.setdefault(name, {"line": line_number, "character": location[1]})
        if len(parts) >= 4 and parts[:2] == ["func", "define"]:
            for parameter in parts[3:]:
                location = next(
                    ((word, column) for word, column in identifiers if word == parameter), None
                )
                if location:
                    definitions.setdefault(
                        parameter, {"line": line_number, "character": location[1]}
                    )
    return definitions


def _word_at(source: str, line_number: int, utf16_column: int) -> tuple[str, int, int] | None:
    lines = source.splitlines()
    if line_number < 0 or line_number >= len(lines):
        return None
    line = lines[line_number]
    column = _character_offset(line, utf16_column)
    for word, start in _identifier_positions(line):
        start_character = _character_offset(line, start)
        end = start + _utf16_length(word)
        if start_character <= column <= _character_offset(line, end):
            return word, start, end
    return None


def _range(line: int, start: int, end: int) -> dict[str, dict[str, int]]:
    return {"start": _position(line, start), "end": _position(line, end)}


def _apply_change(source: str, change: dict[str, Any]) -> str:
    if "range" not in change:
        return change["text"]
    lines = source.splitlines(keepends=True)
    start = change["range"]["start"]
    end = change["range"]["end"]
    if (
        start["line"] < 0 or end["line"] < 0
        or start["line"] >= len(lines) or end["line"] >= len(lines)
        or (start["line"], start["character"]) > (end["line"], end["character"])
    ):
        raise ValueError("Text document change range is outside the document.")

    def offset(position: dict[str, int]) -> int:
        return sum(len(part) for part in lines[:position["line"]]) + _character_offset(
            lines[position["line"]].rstrip("\r\n"), position["character"]
        )

    start_offset, end_offset = offset(start), offset(end)
    return source[:start_offset] + change["text"] + source[end_offset:]


class LanguageServer:
    def __init__(self) -> None:
        self.documents: dict[str, str] = {}
        self.shutdown_requested = False
        self.exit_requested = False

    def handle(
        self, message: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        method = message.get("method")
        request_id = message.get("id")
        params = message.get("params", {})
        notifications: list[dict[str, Any]] = []

        if method == "initialize":
            result: Any = {
                "capabilities": {
                    "textDocumentSync": {"openClose": True, "change": 1},
                    "definitionProvider": True,
                    "hoverProvider": True,
                },
                "serverInfo": {"name": "YubaLANG"},
            }
        elif method == "shutdown":
            self.shutdown_requested = True
            result = None
        elif method == "exit":
            self.exit_requested = True
            result = None
        elif method == "textDocument/didOpen":
            document = params["textDocument"]
            uri, text = document["uri"], document["text"]
            self.documents[uri] = text
            notifications.append(self._publish(uri, text))
            result = None
        elif method == "textDocument/didChange":
            document = params["textDocument"]
            uri = document["uri"]
            text = self.documents[uri]
            for change in params["contentChanges"]:
                text = _apply_change(text, change)
            self.documents[uri] = text
            notifications.append(self._publish(uri, text))
            result = None
        elif method == "textDocument/didClose":
            uri = params["textDocument"]["uri"]
            self.documents.pop(uri, None)
            notifications.append({
                "jsonrpc": "2.0",
                "method": "textDocument/publishDiagnostics",
                "params": {"uri": uri, "diagnostics": []},
            })
            result = None
        elif method == "textDocument/definition":
            uri = params["textDocument"]["uri"]
            source = self.documents.get(uri)
            word = (
                _word_at(source, params["position"]["line"], params["position"]["character"])
                if source is not None else None
            )
            definition = _symbols(source).get(word[0]) if source is not None and word else None
            result = None
            if definition is not None:
                definition_line = definition["line"]
                start = definition["character"]
                result = [{
                    "uri": uri,
                    "range": _range(
                        definition_line, start,
                        start + _utf16_length(word[0]),
                    ),
                }]
        elif method == "textDocument/hover":
            uri = params["textDocument"]["uri"]
            source = self.documents.get(uri)
            word = (
                _word_at(source, params["position"]["line"], params["position"]["character"])
                if source is not None else None
            )
            result = None
            if word:
                hover_text = _HOVER.get(word[0])
                if hover_text is None:
                    definition = _symbols(source).get(word[0]) if source is not None else None
                    if definition is not None:
                        hover_text = f"YubaLANG symbol **`{word[0]}`**."
                if hover_text:
                    result = {
                        "contents": {"kind": "markdown", "value": hover_text},
                        "range": _range(params["position"]["line"], word[1], word[2]),
                    }
        else:
            result = None
            if "id" in message and method is not None:
                return ({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }, [])
            return None, []

        response = (
            {"jsonrpc": "2.0", "id": request_id, "result": result}
            if "id" in message else None
        )
        return response, notifications

    @staticmethod
    def _publish(uri: str, text: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {"uri": uri, "diagnostics": analyze_document(text)},
        }


def _write_message(stream: BinaryIO, message: dict[str, Any]) -> None:
    content = json.dumps(message, separators=(",", ":")).encode("utf-8")
    stream.write(f"Content-Length: {len(content)}\r\n\r\n".encode("ascii"))
    stream.write(content)
    stream.flush()


def _read_message(stream: BinaryIO) -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    while True:
        line = stream.readline()
        if not line:
            if headers:
                raise ValueError("Unexpected end of stream in LSP headers.")
            return None
        if line in (b"\r\n", b"\n"):
            break
        try:
            key, value = line.decode("ascii").split(":", 1)
        except (UnicodeDecodeError, ValueError) as error:
            raise ValueError("Malformed LSP header.") from error
        headers[key.lower().strip()] = value.strip()
    try:
        content_length = int(headers["content-length"])
    except (KeyError, ValueError) as error:
        raise ValueError("LSP message is missing a valid Content-Length header.") from error
    if content_length < 0:
        raise ValueError("LSP Content-Length cannot be negative.")
    content = stream.read(content_length)
    if len(content) != content_length:
        raise ValueError("Unexpected end of stream in LSP message body.")
    try:
        message = json.loads(content.decode("utf-8"))
    except UnicodeDecodeError as error:
        raise ValueError("LSP message body is not valid UTF-8.") from error
    if not isinstance(message, dict):
        raise ValueError("LSP message must be a JSON object.")
    return message


def serve(input_stream: BinaryIO | None = None, output_stream: BinaryIO | None = None) -> None:
    input_stream = input_stream or sys.stdin.buffer
    output_stream = output_stream or sys.stdout.buffer
    server = LanguageServer()
    while not server.shutdown_requested and not server.exit_requested:
        try:
            message = _read_message(input_stream)
        except (ValueError, json.JSONDecodeError) as error:
            print(f"YubaLANG LSP protocol error: {error}", file=sys.stderr)
            return
        if message is None:
            return
        response, notifications = server.handle(message)
        for notification in notifications:
            _write_message(output_stream, notification)
        if response is not None:
            _write_message(output_stream, response)
