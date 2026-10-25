"""Source loading and control-flow execution for YubaLANG."""

import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from .commands import evaluate_condition, execute_command
from .diagnostics import format_diagnostic
from .expressions import evaluate_expression
from .packages import (
    PackageError,
    find_project_root,
    read_manifest,
    resolve_dependency,
    resolve_entry,
)
from .runtime import (
    MAX_FUNCTION_CALL_DEPTH,
    LanguageException,
    RecordValue,
    Runtime,
    TYPES,
    UserFunction,
)
from .string_builtins import resolve
from .syntax import parse_line, tokenize_line
from .type_system import FunctionReference, format_type, parse_type


class ReturnException(Exception):
    def __init__(self, value: Any = None, has_value: bool = False) -> None:
        super().__init__()
        self.value = value
        self.has_value = has_value


class BreakException(Exception):
    pass


class ContinueException(Exception):
    pass


class RuntimeErrorSignal(Exception):
    def __init__(
        self,
        error: Exception,
        source_name: str,
        line_number: int,
        source_line: str,
    ) -> None:
        super().__init__(str(error))
        self.error = error
        self.source_name = source_name
        self.line_number = line_number
        self.source_line = source_line


@lru_cache(maxsize=4096)
def _split_cached(line: str) -> tuple[str, ...]:
    return tokenize_line(line)


def _split(line: str) -> list[str]:
    return list(_split_cached(line))


def _type_of(value: Any) -> str:
    return Runtime.type_name(value)


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


def _invoke_function(
    name: str,
    arguments: list[Any],
    runtime: Runtime,
    keyword_arguments: dict[str, Any] | None = None,
) -> Any:
    resolved_name = runtime.resolve_function(name)
    if resolved_name is None:
        raise ValueError(f"Function '{name}' is not defined.")
    if runtime.function_call_depth >= MAX_FUNCTION_CALL_DEPTH:
        raise RecursionError(
            f"Maximum function call depth ({MAX_FUNCTION_CALL_DEPTH}) exceeded."
        )
    function = runtime.functions[resolved_name]
    keyword_arguments = keyword_arguments or {}
    if function.variadic_parameter is None and len(arguments) > len(function.parameters):
        raise TypeError(
            f"Function '{name}' expects {len(function.parameters)} argument(s), "
            f"but got at least {len(arguments)}."
        )

    positional_count = min(len(arguments), len(function.parameters))
    bound_arguments = dict(zip(function.parameters, arguments[:positional_count]))
    extra_arguments = arguments[positional_count:]
    for parameter, value in keyword_arguments.items():
        if parameter not in function.parameters:
            raise TypeError(f"Function '{name}' has no parameter named '{parameter}'.")
        if parameter in bound_arguments:
            raise TypeError(f"Function '{name}' got multiple values for '{parameter}'.")
        bound_arguments[parameter] = value
    missing = [
        parameter for parameter in function.parameters
        if parameter not in bound_arguments and parameter not in function.defaults
    ]
    if missing:
        if not function.defaults and not keyword_arguments:
            raise TypeError(
                f"Function '{name}' expects {len(function.parameters)} argument(s), "
                f"but got {len(arguments)}."
            )
        raise TypeError(
            f"Function '{name}' is missing required argument(s): {', '.join(missing)}."
        )
    bound_arguments.update({
        parameter: value for parameter, value in function.defaults.items()
        if parameter not in bound_arguments
    })
    for parameter, expected_type in function.parameter_types.items():
        if parameter in bound_arguments and not runtime.value_matches_type(
            expected_type, bound_arguments[parameter]
        ):
            actual_type = _type_of(bound_arguments[parameter])
            raise TypeError(
                f"Function '{name}' parameter '{parameter}' requires "
                f"type '{expected_type}', got '{actual_type}'."
            )
        if (
            parameter in bound_arguments
            and expected_type == "float"
            and isinstance(bound_arguments[parameter], int)
            and not isinstance(bound_arguments[parameter], bool)
        ):
            bound_arguments[parameter] = float(bound_arguments[parameter])
    local_scope = {
        parameter: {
            "type": function.parameter_types.get(
                parameter, _type_of(bound_arguments[parameter])
            ),
            "value": bound_arguments[parameter],
        }
        for parameter in function.parameters
    }
    if function.variadic_parameter is not None:
        variadic_type = function.parameter_types.get(function.variadic_parameter)
        if variadic_type is not None:
            for value in extra_arguments:
                if not runtime.value_matches_type(variadic_type, value):
                    raise TypeError(
                        f"Function '{name}' variadic parameter "
                        f"'{function.variadic_parameter}' requires type "
                        f"'{variadic_type}'."
                    )
        local_scope[function.variadic_parameter] = {
            "type": f"tuple[{variadic_type}]" if variadic_type else "tuple",
            "value": tuple(extra_arguments),
        }
    runtime.scopes.append(local_scope)
    runtime.current_namespaces.append(function.namespace)
    runtime.function_call_depth += 1
    call_source, call_line = runtime.current_location
    runtime.call_stack.append((name, call_source, call_line))
    try:
        execute_lines(
            function.body,
            runtime,
            function.source_name,
            function.line_numbers or None,
            function.namespace or None,
        )
    except ReturnException as result:
        if function.return_type is not None and not runtime.value_matches_type(
            function.return_type, result.value
        ):
            actual_type = _type_of(result.value)
            raise TypeError(
                f"Function '{name}' must return '{function.return_type}', "
                f"got '{actual_type}'."
            )
        if (
            function.return_type == "float"
            and isinstance(result.value, int)
            and not isinstance(result.value, bool)
        ):
            result.value = float(result.value)
        return result.value if result.has_value else None
    finally:
        runtime.call_stack.pop()
        runtime.function_call_depth -= 1
        runtime.current_namespaces.pop()
        runtime.scopes.pop()
    if function.return_type is not None and not runtime.value_matches_type(
        function.return_type, None
    ):
        raise TypeError(
            f"Function '{name}' must return '{function.return_type}', got 'none'."
        )
    return None


def _execute_function_call(parts: list[str], runtime: Runtime) -> None:
    if len(parts) < 3:
        raise SyntaxError("Usage: func call <name> [arguments] [-> destination]")
    name = parts[2]
    if runtime.resolve_function(name) is None:
        variable = runtime.get_var(name)
        if variable is not None and isinstance(variable["value"], FunctionReference):
            name = variable["value"].name
    if runtime.resolve_function(name) is None:
        raise ValueError(f"Function '{name}' is not defined.")
    call_parts = parts[3:]
    destination = None
    if "->" in call_parts:
        arrow = call_parts.index("->")
        if arrow != len(call_parts) - 2:
            raise SyntaxError("Return destination must follow '->'.")
        destination = call_parts[-1]
        call_parts = call_parts[:arrow]
    arguments = []
    keyword_arguments: dict[str, Any] = {}
    saw_keyword = False
    for argument in call_parts:
        parameter, separator, value = argument.partition("=")
        if separator and parameter.isidentifier():
            if not value:
                raise SyntaxError(f"Missing value for named argument '{parameter}'.")
            saw_keyword = True
            if parameter in keyword_arguments:
                raise TypeError(f"Named argument '{parameter}' was supplied more than once.")
            keyword_arguments[parameter] = resolve(value, runtime)
        else:
            if saw_keyword:
                raise SyntaxError("Positional arguments must come before named arguments.")
            arguments.append(resolve(argument, runtime))
    result = _invoke_function(name, arguments, runtime, keyword_arguments)
    if destination is not None:
        if result is None:
            raise ValueError(f"Function '{name}' did not return a value.")
        runtime.assign_var(destination, result)


def _module_file(module_name: str, runtime: Runtime, source_name: str) -> Path:
    parts = module_name.split(".")
    if (
        runtime.project_root is not None
        and parts[0] in read_manifest(runtime.project_root)["dependencies"]
    ):
        dependency_root = resolve_dependency(runtime.project_root, parts[0])
        if dependency_root is None:
            raise PackageError(f"Dependency '{parts[0]}' could not be resolved.")
        if len(parts) == 1:
            manifest = read_manifest(dependency_root)
            return resolve_entry(dependency_root, manifest)
        base = dependency_root.joinpath(*parts[1:])
    else:
        if source_name == "<memory>":
            base_directory = Path.cwd()
        else:
            source_path = Path(source_name).resolve()
            base_directory = source_path.parent
            if runtime.project_root is None:
                runtime.project_root = find_project_root(source_path)
        base = base_directory.joinpath(*parts)

    candidates = (base.with_suffix(".yl"), base / "main.yl")
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    searched = " or ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(
        f"Module '{module_name}' was not found; tried {searched}."
    )


def _execute_import(parts: list[str], runtime: Runtime, source_name: str) -> None:
    if len(parts) not in (2, 4) or (len(parts) == 4 and parts[2] != "as"):
        raise SyntaxError("Usage: import <module> [as <namespace>]")
    module_name = parts[1]
    if not all(part.isidentifier() for part in module_name.split(".")):
        raise SyntaxError(f"Invalid module name '{module_name}'.")
    alias = parts[3] if len(parts) == 4 else module_name.split(".")[-1]
    if not alias.isidentifier():
        raise SyntaxError(f"Invalid module namespace '{alias}'.")

    module_path = _module_file(module_name, runtime, source_name)
    key = str(module_path.resolve())
    if key in runtime.import_stack:
        cycle = " -> ".join((*runtime.import_stack, key))
        raise ValueError(f"Import cycle detected: {cycle}")
    if alias in runtime.module_aliases:
        if runtime.module_alias_paths[alias] != key:
            raise ValueError(
                f"Namespace '{alias}' is already bound to a different module."
            )
        namespace = runtime.module_aliases[alias]
    else:
        namespace = runtime.loaded_modules.get(key, alias)
        runtime.module_aliases[alias] = namespace
        runtime.module_alias_paths[alias] = key

    if key in runtime.loaded_modules:
        return
    runtime.import_stack.append(key)
    try:
        try:
            lines = module_path.read_text(encoding="utf-8-sig").splitlines()
        except (OSError, UnicodeError) as error:
            raise ValueError(f"Cannot read module '{module_path}': {error}") from error
        runtime.current_namespaces.append(namespace)
        try:
            execute_lines(lines, runtime, str(module_path), namespace=namespace)
        finally:
            runtime.current_namespaces.pop()
        runtime.loaded_modules[key] = namespace
    finally:
        runtime.import_stack.pop()


def _execute_try_block(
    lines: list[str],
    runtime: Runtime,
    source_name: str,
    line_numbers: list[int],
    namespace: str | None,
    start: int,
) -> int:
    sections: dict[str, tuple[list[str], list[int]]] = {
        "try": ([], []), "catch": ([], []), "finally": ([], [])
    }
    catch_name: str | None = None
    has_catch = False
    section = "try"
    depth = 1
    index = start + 1
    while index < len(lines):
        source_line = lines[index]
        try:
            parts = _split(source_line.strip()) if source_line.strip() else []
        except SyntaxError:
            parts = []
        command = parts[0] if parts else ""
        if command == "try":
            depth += 1
        elif command == "endtry":
            depth -= 1
            if depth == 0:
                break
        elif depth == 1 and command == "catch":
            if section != "try" or len(parts) not in (1, 2):
                raise SyntaxError("Usage: catch [exception_variable], before finally.")
            if len(parts) == 2 and not parts[1].isidentifier():
                raise SyntaxError("Catch variable must be an identifier.")
            catch_name = parts[1] if len(parts) == 2 else None
            has_catch = True
            section = "catch"
            index += 1
            continue
        elif depth == 1 and command == "finally":
            if section == "finally" or len(parts) != 1:
                raise SyntaxError("Usage: finally, after catch.")
            section = "finally"
            index += 1
            continue
        if section != "try" or command != "catch":
            sections[section][0].append(source_line)
            sections[section][1].append(line_numbers[index])
        index += 1
    if index == len(lines):
        raise SyntaxError("Missing endtry for try block.")

    try:
        signal: RuntimeErrorSignal | None = None
        runtime.exception_capture_depth += 1
        try:
            try_lines, try_numbers = sections["try"]
            execute_lines(
                try_lines, runtime, source_name, try_numbers, namespace
            )
        except RuntimeErrorSignal as error_signal:
            signal = error_signal
        finally:
            runtime.exception_capture_depth -= 1

        if signal is not None:
            if not has_catch:
                if runtime.exception_capture_depth == 0:
                    print(format_diagnostic(
                        signal.error, signal.source_name, signal.line_number,
                        signal.source_line, runtime,
                    ))
                    raise SystemExit(1) from signal.error
                raise signal
            caught_value = (
                signal.error.value
                if isinstance(signal.error, LanguageException)
                else str(signal.error)
            )
            if catch_name is not None:
                runtime.scopes.append({})
                runtime.define_var(catch_name, _type_of(caught_value), caught_value)
            try:
                execute_lines(
                    sections["catch"][0], runtime, source_name,
                    sections["catch"][1], namespace,
                )
            finally:
                if catch_name is not None:
                    runtime.scopes.pop()
    finally:
        runtime.exception_capture_depth -= 1
        finally_lines, finally_numbers = sections["finally"]
        if finally_lines:
            execute_lines(
                finally_lines, runtime, source_name, finally_numbers, namespace
            )
    return index


def execute_lines(
    lines: list[str],
    runtime: Runtime | None = None,
    source_name: str = "<memory>",
    line_numbers: list[int] | None = None,
    namespace: str | None = None,
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
            node = parse_line(source_line, source_name, statement_line)
            parts = list(node.tokens) if node is not None else []
            runtime.current_location = (source_name, statement_line)
            command = parts[0] if parts else ""
            if command == "return":
                value = (
                    evaluate_expression(" ".join(parts[1:]), runtime)
                    if len(parts) > 1 else None
                )
                raise ReturnException(value, has_value=len(parts) > 1)
            if command == "break":
                raise BreakException()
            if command == "continue":
                raise ContinueException()
            if command == "throw":
                if len(parts) != 2:
                    raise SyntaxError("Usage: throw <value>")
                raise LanguageException(resolve(parts[1], runtime))

            if command == "try":
                if len(parts) != 1:
                    raise SyntaxError("Usage: try")
                index = _execute_try_block(
                    lines, runtime, source_name, line_numbers, namespace, index
                )
                index += 1
                continue

            if command == "if":
                if len(parts) < 2:
                    raise SyntaxError("Usage: if <condition>")
                branches: list[tuple[str, list[str], list[int]]] = [
                    (" ".join(parts[1:]), [], [])
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
                        if len(nested_parts) < 2:
                            error = SyntaxError("Usage: elseif <condition>")
                            print(format_diagnostic(
                                error, source_name, line_numbers[index],
                                nested_source_line, runtime,
                            ))
                            raise SystemExit(1) from error
                        branches.append((" ".join(nested_parts[1:]), [], []))
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
                        execute_lines(
                            body, runtime, source_name, body_line_numbers, namespace
                        )
                        break

            elif command == "func" and len(parts) >= 3 and parts[1] == "define":
                function_name = parts[2]
                parameters = []
                defaults = {}
                variadic_parameter = None
                parameter_types = {}
                optional_seen = False
                declarations = parts[3:]
                return_type = None
                if "->" in declarations:
                    return_index = declarations.index("->")
                    if return_index == len(declarations) - 1:
                        raise SyntaxError("A function return type must follow '->'.")
                    return_type = format_type(
                        parse_type(" ".join(declarations[return_index + 1:]))
                    )
                    if not runtime.type_is_known(return_type):
                        raise ValueError(f"Unknown type: {return_type}")
                    declarations = declarations[:return_index]
                for declaration_index, declaration in enumerate(declarations):
                    if declaration.startswith("*"):
                        parameter_declaration = declaration[1:]
                        parameter, type_separator, parameter_type = parameter_declaration.partition(":")
                        if (
                            not parameter.isidentifier()
                            or declaration_index != len(declarations) - 1
                            or variadic_parameter is not None
                        ):
                            raise SyntaxError(
                                "A variadic parameter must be a final '*name' parameter."
                            )
                        variadic_parameter = parameter
                        if type_separator:
                            parameter_type = format_type(parse_type(parameter_type))
                            if not runtime.type_is_known(parameter_type):
                                raise ValueError(f"Unknown type: {parameter_type}")
                            parameter_types[parameter] = parameter_type
                        continue
                    parameter, separator, default_value = declaration.partition("=")
                    parameter, type_separator, parameter_type = parameter.partition(":")
                    if not parameter.isidentifier() or (separator and not default_value):
                        raise SyntaxError(
                            "Function parameters must be name[:type] or name[:type]=value."
                        )
                    if type_separator:
                        parameter_type = format_type(parse_type(parameter_type))
                        if not runtime.type_is_known(parameter_type):
                            raise ValueError(f"Unknown type: {parameter_type}")
                        parameter_types[parameter] = parameter_type
                    if separator:
                        optional_seen = True
                        defaults[parameter] = (
                            parse_value(default_value, parameter_type, runtime)
                            if type_separator else resolve(default_value, runtime)
                        )
                        if type_separator and not runtime.value_matches_type(
                            parameter_type, defaults[parameter]
                        ):
                            raise TypeError(
                                f"Default for parameter '{parameter}' must match "
                                f"type '{parameter_type}'."
                            )
                    elif optional_seen:
                        raise SyntaxError(
                            "Required function parameters must precede default parameters."
                        )
                    parameters.append(parameter)
                if (
                    len(set(parameters)) != len(parameters)
                    or variadic_parameter in parameters
                ):
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
                qualified_name = (
                    f"{namespace}.{function_name}" if namespace else function_name
                )
                runtime.functions[qualified_name] = UserFunction(
                    parameters, body, source_name, body_line_numbers,
                    namespace or "", defaults, variadic_parameter,
                    parameter_types, return_type,
                )

            elif command == "func" and len(parts) >= 3 and parts[1] == "call":
                _execute_function_call(parts, runtime)

            elif command == "import":
                _execute_import(parts, runtime, source_name)

            elif command == "loop" and len(parts) >= 3 and parts[1] in ("for", "while"):
                loop_type, condition = parts[1], " ".join(parts[2:])
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
                    count = evaluate_expression(condition, runtime)
                    if not isinstance(count, int) or isinstance(count, bool):
                        raise TypeError("loop for count must evaluate to an integer.")
                    for _ in range(count):
                        try:
                            execute_lines(
                                body, runtime, source_name, body_line_numbers, namespace
                            )
                        except ContinueException:
                            continue
                        except BreakException:
                            break
                else:
                    while evaluate_condition(condition, runtime):
                        try:
                            execute_lines(
                                body, runtime, source_name, body_line_numbers, namespace
                            )
                        except ContinueException:
                            continue
                        except BreakException:
                            break

            else:
                interpret(raw_line, runtime, source_name)
        except (
            SyntaxError, ValueError, TypeError, ZeroDivisionError, IndexError,
            KeyError, AttributeError, OverflowError, OSError, EOFError, RecursionError,
            AssertionError, MemoryError, LanguageException,
        ) as error:
            if runtime.exception_capture_depth:
                raise RuntimeErrorSignal(
                    error, source_name, statement_line, source_line
                ) from error
            print(format_diagnostic(error, source_name, statement_line, source_line, runtime))
            raise SystemExit(1) from error
        index += 1


def run_file(filename: str) -> None:
    with open(filename, "r", encoding="utf-8-sig") as source_file:
        lines = source_file.readlines()
    runtime = Runtime()
    runtime.project_root = find_project_root(Path(filename))
    try:
        execute_lines(lines, runtime, filename)
    except ReturnException:
        pass
    finally:
        runtime.close_files()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_file(sys.argv[1])
    else:
        print("Usage: py YubaLANG.py <path_to_file.yl>")
