from contextlib import contextmanager
from dataclasses import dataclass, field
from io import IOBase
from pathlib import Path
from typing import Any, Iterator
from weakref import WeakValueDictionary

from .type_system import FunctionReference, TypeSpec, format_type, is_known_type, parse_type


TYPES = {
    "int": int,
    "float": float,
    "string": str,
    "bool": bool,
    "list": list,
    "dict": dict,
    "set": set,
    "tuple": tuple,
    "bytes": bytes,
    "bytearray": bytearray,
    "iterator": object,
    "file": object,
    "none": type(None),
}

MAX_FUNCTION_CALL_DEPTH = 128


class LanguageException(ValueError):
    def __init__(self, value: Any) -> None:
        super().__init__(f"Uncaught language exception: {value}")
        self.value = value


@dataclass
class RecordDefinition:
    fields: dict[str, str]


@dataclass
class RecordValue:
    record_type: str
    fields: dict[str, Any]


@dataclass
class UserFunction:
    parameters: list[str]
    body: list[str]
    source_name: str = "<memory>"
    line_numbers: list[int] = field(default_factory=list)
    namespace: str = ""
    defaults: dict[str, Any] = field(default_factory=dict)
    variadic_parameter: str | None = None
    parameter_types: dict[str, str] = field(default_factory=dict)
    return_type: str | None = None
    closure_scopes: tuple[dict[str, dict[str, Any]], ...] = ()


@dataclass
class Runtime:
    scopes: list[dict[str, dict[str, Any]]] = field(default_factory=lambda: [{}])
    functions: dict[str, UserFunction] = field(default_factory=dict)
    private_functions: set[str] = field(default_factory=set)
    closure_functions: WeakValueDictionary[str, UserFunction] = field(
        default_factory=WeakValueDictionary
    )
    closure_counter: int = 0
    records: dict[str, RecordDefinition] = field(default_factory=dict)
    native_libraries: dict[str, Any] = field(default_factory=dict)
    project_root: Path | None = None
    module_aliases: dict[str, str] = field(default_factory=dict)
    module_alias_paths: dict[str, str] = field(default_factory=dict)
    loaded_modules: dict[str, str] = field(default_factory=dict)
    import_stack: list[str] = field(default_factory=list)
    current_namespaces: list[str] = field(default_factory=list)
    function_scope_starts: list[int] = field(default_factory=list)
    function_call_depth: int = 0
    open_files: list[IOBase] = field(default_factory=list)
    exception_capture_depth: int = 0
    call_stack: list[tuple[str, str, int]] = field(default_factory=list)
    current_location: tuple[str, int] = ("<memory>", 1)

    def resolve_function(self, name: str) -> str | None:
        if "." in name:
            alias, function_name = name.split(".", 1)
            namespace = self.module_aliases.get(alias, alias)
            key = f"{namespace}.{function_name}"
            if key not in self.functions:
                return None
            if (
                key in self.private_functions
                and (
                    not self.current_namespaces
                    or self.current_namespaces[-1] != namespace
                )
            ):
                return None
            return key
        variable = self.get_var(name)
        if variable is not None and isinstance(
            variable["value"], FunctionReference
        ):
            return variable["value"].name
        if self.current_namespaces:
            key = f"{self.current_namespaces[-1]}.{name}"
            if key in self.functions:
                return key
        return name if name in self.functions else None

    def get_function(self, name: str) -> UserFunction | None:
        return self.functions.get(name) or self.closure_functions.get(name)

    def get_var(self, name: str) -> dict[str, Any] | None:
        start = self.function_scope_starts[-1] if self.function_scope_starts else 0
        for scope in reversed(self.scopes[start:]):
            if name in scope:
                return scope[name]
        if start:
            return self.scopes[0].get(name)
        return None

    def define_var(self, name: str, var_type: str, value: Any) -> None:
        self.scopes[-1][name] = {"type": var_type, "value": value}

    @contextmanager
    def scope(self) -> Iterator[None]:
        self.scopes.append({})
        try:
            yield
        finally:
            self.scopes.pop()

    @contextmanager
    def global_scope(self) -> Iterator[None]:
        scopes = self.scopes
        function_scope_starts = self.function_scope_starts
        self.scopes = [scopes[0]]
        self.function_scope_starts = []
        try:
            yield
        finally:
            self.scopes = scopes
            self.function_scope_starts = function_scope_starts

    def register_file(self, file_obj: IOBase) -> None:
        self.open_files.append(file_obj)

    def close_file(self, file_obj: IOBase) -> None:
        file_obj.close()
        self.open_files = [opened for opened in self.open_files if opened is not file_obj]

    def close_files(self) -> None:
        files = list(self.open_files)
        self.open_files.clear()
        files.extend(
            variable["value"]
            for scope in self.scopes
            for variable in scope.values()
            if variable["type"] == "file" and isinstance(variable["value"], IOBase)
        )
        closed_ids: set[int] = set()
        first_error: OSError | None = None
        for file_obj in files:
            if id(file_obj) in closed_ids:
                continue
            closed_ids.add(id(file_obj))
            try:
                if not file_obj.closed:
                    file_obj.close()
            except OSError as error:
                if first_error is None:
                    first_error = error
        if first_error is not None:
            raise first_error

    def update_var(self, name: str, var_type: str, value: Any) -> None:
        start = self.function_scope_starts[-1] if self.function_scope_starts else 0
        target_scope = next(
            (scope for scope in reversed(self.scopes[start:]) if name in scope),
            None,
        )
        if target_scope is None and start and name in self.scopes[0]:
            target_scope = self.scopes[0]
        if target_scope is None:
            raise ValueError(f"Variable '{name}' is not defined.")
        target_scope[name] = {"type": var_type, "value": value}

    def assign_var(self, name: str, value: Any) -> None:
        variable = self.require_var(name)
        var_type = variable["type"]
        matches = self.value_matches_type(var_type, value)
        if var_type == "float" and matches:
            value = float(value)
        if not matches:
            actual_type = self.type_name(value)
            raise TypeError(
                f"Cannot assign a {actual_type} value to variable '{name}' "
                f"of type '{var_type}'."
            )
        self.update_var(name, var_type, value)

    def value_matches_type(self, var_type: str, value: Any) -> bool:
        return self._matches_type(parse_type(var_type), value, allow_widening=True)

    def _matches_type(
        self, spec: TypeSpec, value: Any, allow_widening: bool
    ) -> bool:
        if spec.name == "union":
            return any(
                self._matches_type(option, value, allow_widening)
                for option in spec.arguments
            )
        if spec.name == "function":
            if not isinstance(value, FunctionReference):
                return False
            function = value.target or self.get_function(value.name)
            if function is None or function.return_type is None:
                return False
            if function.variadic_parameter is not None:
                return False
            if len(function.parameters) != len(spec.arguments) - 1:
                return False
            actual_parameters = []
            for parameter in function.parameters:
                parameter_type = function.parameter_types.get(parameter)
                if parameter_type is None:
                    return False
                actual_parameters.append(parse_type(parameter_type))
            return TypeSpec(
                "function",
                (*actual_parameters, parse_type(function.return_type)),
            ) == spec
        if spec.name in self.records:
            return isinstance(value, RecordValue) and value.record_type == spec.name
        if spec.name == "iterator":
            return hasattr(value, "__next__")
        if spec.name == "file":
            return isinstance(value, IOBase)
        if spec.name == "int":
            return isinstance(value, int) and not isinstance(value, bool)
        if spec.name == "float":
            return isinstance(value, float) or (
                allow_widening and isinstance(value, int) and not isinstance(value, bool)
            )
        if spec.name in ("list", "tuple", "set", "dict"):
            if not isinstance(value, TYPES[spec.name]):
                return False
            if not spec.arguments:
                return True
            if spec.name == "dict":
                key_type, value_type = spec.arguments
                return all(
                    self._matches_type(key_type, key, allow_widening=False)
                    and self._matches_type(value_type, item, allow_widening=False)
                    for key, item in value.items()
                )
            if spec.name == "tuple" and len(spec.arguments) > 1:
                return len(value) == len(spec.arguments) and all(
                    self._matches_type(item_type, item, allow_widening=False)
                    for item_type, item in zip(spec.arguments, value)
                )
            item_type = spec.arguments[0]
            return all(
                self._matches_type(item_type, item, allow_widening=False)
                for item in value
            )
        return (
            spec.name in TYPES and not spec.arguments
            and isinstance(value, TYPES[spec.name])
        )

    def type_is_known(self, type_name: str) -> bool:
        return is_known_type(parse_type(type_name), set(self.records))

    @staticmethod
    def type_name(value: Any) -> str:
        if isinstance(value, FunctionReference):
            return "function"
        if isinstance(value, RecordValue):
            return value.record_type
        if value is None:
            return "none"
        if isinstance(value, bool):
            return "bool"
        for name, python_type in TYPES.items():
            if name not in ("iterator", "file", "none") and isinstance(value, python_type):
                return name
        if hasattr(value, "__next__"):
            return "iterator"
        return type(value).__name__

    def validate_container_mutation(self, container: Any, candidate: Any) -> None:
        visited: set[tuple[int, TypeSpec]] = set()

        def check(value: Any, spec: TypeSpec) -> bool:
            pair = (id(value), spec)
            if pair in visited:
                return True
            visited.add(pair)
            if value is container:
                return self.value_matches_type(format_type(spec), candidate)
            if spec.name == "union":
                return all(
                    check(value, option)
                    for option in spec.arguments
                    if self.value_matches_type(format_type(option), value)
                )
            if spec.name == "list" and spec.arguments and isinstance(value, list):
                return all(check(item, spec.arguments[0]) for item in value)
            if spec.name == "set" and spec.arguments and isinstance(value, set):
                return all(check(item, spec.arguments[0]) for item in value)
            if spec.name == "tuple" and spec.arguments and isinstance(value, tuple):
                if len(spec.arguments) == 1:
                    return all(check(item, spec.arguments[0]) for item in value)
                return all(
                    check(item, item_spec)
                    for item, item_spec in zip(value, spec.arguments)
                )
            if spec.name == "dict" and len(spec.arguments) == 2 and isinstance(value, dict):
                return all(
                    check(key, spec.arguments[0]) and check(item, spec.arguments[1])
                    for key, item in value.items()
                )
            if (
                spec.name in self.records and isinstance(value, RecordValue)
                and value.record_type == spec.name
            ):
                return all(
                    check(value.fields[field_name], parse_type(field_type))
                    for field_name, field_type in self.records[spec.name].fields.items()
                )
            return True

        for scope in self.scopes:
            for variable in scope.values():
                try:
                    spec = parse_type(variable["type"])
                except ValueError:
                    continue
                if not check(variable["value"], spec):
                    raise TypeError(
                        f"Mutation would violate collection type '{format_type(spec)}'."
                    )

    def require_var(self, name: str) -> dict[str, Any]:
        result = self.get_var(name)
        if result is None:
            raise ValueError(f"Variable '{name}' is not defined.")
        return result
