"""Source loading and control-flow execution for YubaLANG."""

import shlex
import sys
from typing import Any

from .commands import evaluate_condition, execute_command
from .diagnostics import format_diagnostic
from .runtime import Runtime, TYPES, UserFunction
from .string_builtins import resolve


class ReturnException(Exception):
    def __init__(self, value: Any = None, has_value: bool = False) -> None:
        super().__init__()
        self.value = value
        self.has_value = has_value


class BreakException(Exception):
    pass


class ContinueException(Exception):
    pass


def _split(line: str) -> list[str]:
    try:
        return shlex.split(line, posix=False, comments=True)
    except ValueError as error:
        raise SyntaxError(f"Invalid command quoting: {error}") from error


def _type_of(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    for name in ("int", "float", "string", "list", "dict", "set", "tuple", "bytes", "bytearray"):
        if isinstance(value, TYPES[name]):
            return name
    if hasattr(value, "__next__"):
        return "iterator"
    return "string"


def interpret(
    line: str,
    runtime: Runtime | None = None,
    source_name: str = "<memory>",
) -> None:
    runtime = runtime or Runtime()
    parts = _split(line.strip())
    if parts:
        execute_command(
            parts,
            runtime,
            lambda name, args: _invoke_function(name, args, runtime),
            source_name,
        )


def _invoke_function(name: str, arguments: list[Any], runtime: Runtime) -> Any:
    function = runtime.functions.get(name)
    if function is None:
        raise ValueError(f"Function '{name}' is not defined.")
    if len(arguments) != len(function.parameters):
        raise TypeError(
            f"Function '{name}' expects {len(function.parameters)} argument(s), "
            f"but got {len(arguments)}."
        )

    local_scope = {
        parameter: {"type": _type_of(value), "value": value}
        for parameter, value in zip(function.parameters, arguments)
    }
    runtime.scopes.append(local_scope)
    try:
        execute_lines(
            function.body,
            runtime,
            function.source_name,
            function.line_numbers or None,
        )
    except ReturnException as result:
        return result.value if result.has_value else None
    finally:
        runtime.scopes.pop()
    return None


def _execute_function_call(parts: list[str], runtime: Runtime) -> None:
    if len(parts) < 3:
        raise SyntaxError("Usage: func call <name> [arguments] [-> destination]")
    name = parts[2]
    if name not in runtime.functions:
        raise ValueError(f"Function '{name}' is not defined.")
    call_parts = parts[3:]
    destination = None
    if "->" in call_parts:
        arrow = call_parts.index("->")
        if arrow != len(call_parts) - 2:
            raise SyntaxError("Return destination must follow '->'.")
        destination = call_parts[-1]
        call_parts = call_parts[:arrow]
    arguments = [resolve(argument, runtime) for argument in call_parts]
    result = _invoke_function(name, arguments, runtime)
    if destination is not None:
        if result is None:
            raise ValueError(f"Function '{name}' did not return a value.")
        target = runtime.require_var(destination)
        runtime.update_var(destination, target["type"], result)


def execute_lines(
    lines: list[str],
    runtime: Runtime | None = None,
    source_name: str = "<memory>",
    line_numbers: list[int] | None = None,
) -> None:
    runtime = runtime or Runtime()
    if line_numbers is None:
        line_numbers = list(range(1, len(lines) + 1))
    if len(line_numbers) != len(lines):
        raise ValueError("Source line mapping must match the number of program lines.")

    index = 0
    while index < len(lines):
        source_line = lines[index]
        raw_line = source_line.strip()
        statement_line = line_numbers[index]
        if not raw_line or raw_line.startswith("#"):
            index += 1
            continue

        try:
            parts = _split(raw_line)
            command = parts[0] if parts else ""
            if command == "return":
                value = resolve(" ".join(parts[1:]), runtime) if len(parts) > 1 else None
                raise ReturnException(value, has_value=len(parts) > 1)
            if command == "break":
                raise BreakException()
            if command == "continue":
                raise ContinueException()

            if command == "if":
                if len(parts) != 2:
                    raise SyntaxError("Usage: if <condition>")
                branches: list[tuple[str, list[str], list[int]]] = [
                    (parts[1], [], [])
                ]
                depth = 1
                index += 1
                while index < len(lines):
                    nested_source_line = lines[index]
                    nested_line = nested_source_line.strip()
                    try:
                        nested_parts = _split(nested_line) if nested_line else []
                    except SyntaxError as error:
                        print(format_diagnostic(
                            error, source_name, line_numbers[index], nested_source_line, runtime
                        ))
                        raise SystemExit(1) from error
                    nested_command = nested_parts[0] if nested_parts else ""
                    if nested_command == "if":
                        depth += 1
                        branches[-1][1].append(nested_source_line)
                        branches[-1][2].append(line_numbers[index])
                    elif nested_command == "endif":
                        depth -= 1
                        if depth == 0:
                            break
                        branches[-1][1].append(nested_source_line)
                        branches[-1][2].append(line_numbers[index])
                    elif depth == 1 and nested_command == "elseif":
                        if len(nested_parts) != 2:
                            error = SyntaxError("Usage: elseif <condition>")
                            print(format_diagnostic(
                                error, source_name, line_numbers[index],
                                nested_source_line, runtime,
                            ))
                            raise SystemExit(1) from error
                        branches.append((nested_parts[1], [], []))
                    elif depth == 1 and nested_command == "else":
                        branches.append(("true", [], []))
                    else:
                        branches[-1][1].append(nested_source_line)
                        branches[-1][2].append(line_numbers[index])
                    index += 1
                else:
                    raise SyntaxError("Missing endif for if block.")

                for condition, body, body_line_numbers in branches:
                    if evaluate_condition(condition, runtime):
                        execute_lines(body, runtime, source_name, body_line_numbers)
                        break

            elif command == "func" and len(parts) >= 3 and parts[1] == "define":
                function_name = parts[2]
                parameters = parts[3:]
                if len(set(parameters)) != len(parameters):
                    raise SyntaxError(f"Function '{function_name}' has duplicate parameters.")
                body = []
                body_line_numbers = []
                index += 1
                while index < len(lines) and lines[index].strip() != "endfunc":
                    body.append(lines[index])
                    body_line_numbers.append(line_numbers[index])
                    index += 1
                if index == len(lines):
                    raise SyntaxError(f"Missing endfunc for function '{function_name}'.")
                runtime.functions[function_name] = UserFunction(
                    parameters, body, source_name, body_line_numbers
                )

            elif command == "func" and len(parts) >= 3 and parts[1] == "call":
                _execute_function_call(parts, runtime)

            elif command == "loop" and len(parts) == 3 and parts[1] in ("for", "while"):
                loop_type, condition = parts[1], parts[2]
                body = []
                body_line_numbers = []
                index += 1
                while index < len(lines) and lines[index].strip() != "endloop":
                    body.append(lines[index])
                    body_line_numbers.append(line_numbers[index])
                    index += 1
                if index == len(lines):
                    raise SyntaxError("Missing endloop for loop.")
                if loop_type == "for":
                    value = runtime.get_var(condition)
                    count = value["value"] if value else int(condition)
                    for _ in range(count):
                        try:
                            execute_lines(body, runtime, source_name, body_line_numbers)
                        except ContinueException:
                            continue
                        except BreakException:
                            break
                else:
                    while evaluate_condition(condition, runtime):
                        try:
                            execute_lines(body, runtime, source_name, body_line_numbers)
                        except ContinueException:
                            continue
                        except BreakException:
                            break

            else:
                interpret(raw_line, runtime, source_name)
        except (
            SyntaxError, ValueError, TypeError, ZeroDivisionError, IndexError,
            KeyError, AttributeError, OverflowError, OSError, EOFError,
        ) as error:
            print(format_diagnostic(error, source_name, statement_line, source_line, runtime))
            raise SystemExit(1) from error
        index += 1


def run_file(filename: str) -> None:
    with open(filename, "r", encoding="utf-8") as source_file:
        lines = source_file.readlines()
    runtime = Runtime()
    try:
        execute_lines(lines, runtime, filename)
    except ReturnException:
        pass
    finally:
        for scope in runtime.scopes:
            for variable in scope.values():
                if variable["type"] == "file":
                    variable["value"].close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_file(sys.argv[1])
    else:
        print("Usage: py YubaLANG.py <path_to_file.hl>")
