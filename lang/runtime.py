from dataclasses import dataclass, field
from io import IOBase
from pathlib import Path
from typing import Any


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
}

MAX_FUNCTION_CALL_DEPTH = 128


@dataclass
class UserFunction:
    parameters: list[str]
    body: list[str]
    source_name: str = "<memory>"
    line_numbers: list[int] = field(default_factory=list)
    namespace: str = ""


@dataclass
class Runtime:
    scopes: list[dict[str, dict[str, Any]]] = field(default_factory=lambda: [{}])
    functions: dict[str, UserFunction] = field(default_factory=dict)
    native_libraries: dict[str, Any] = field(default_factory=dict)
    project_root: Path | None = None
    module_aliases: dict[str, str] = field(default_factory=dict)
    module_alias_paths: dict[str, str] = field(default_factory=dict)
    loaded_modules: dict[str, str] = field(default_factory=dict)
    import_stack: list[str] = field(default_factory=list)
    current_namespaces: list[str] = field(default_factory=list)
    function_call_depth: int = 0
    open_files: list[IOBase] = field(default_factory=list)

    def resolve_function(self, name: str) -> str | None:
        if "." in name:
            alias, function_name = name.split(".", 1)
            namespace = self.module_aliases.get(alias, alias)
            key = f"{namespace}.{function_name}"
            return key if key in self.functions else None
        if self.current_namespaces:
            key = f"{self.current_namespaces[-1]}.{name}"
            if key in self.functions:
                return key
        return name if name in self.functions else None

    def get_var(self, name: str) -> dict[str, Any] | None:
        if name in self.scopes[-1]:
            return self.scopes[-1][name]
        return self.scopes[0].get(name)

    def define_var(self, name: str, var_type: str, value: Any) -> None:
        self.scopes[-1][name] = {"type": var_type, "value": value}

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
        if name in self.scopes[-1]:
            target_scope = self.scopes[-1]
        elif name in self.scopes[0]:
            target_scope = self.scopes[0]
        else:
            raise ValueError(f"Variable '{name}' is not defined.")
        target_scope[name] = {"type": var_type, "value": value}

    def assign_var(self, name: str, value: Any) -> None:
        variable = self.require_var(name)
        var_type = variable["type"]
        expected_type = TYPES[var_type]
        if var_type == "iterator":
            matches = hasattr(value, "__next__")
        elif var_type == "file":
            matches = isinstance(value, IOBase)
        elif var_type == "int":
            matches = isinstance(value, int) and not isinstance(value, bool)
        elif var_type == "float":
            matches = isinstance(value, (int, float)) and not isinstance(value, bool)
            if matches:
                value = float(value)
        else:
            matches = isinstance(value, expected_type)
        if not matches:
            actual_type = type(value).__name__
            raise TypeError(
                f"Cannot assign a {actual_type} value to variable '{name}' "
                f"of type '{var_type}'."
            )
        self.update_var(name, var_type, value)

    def require_var(self, name: str) -> dict[str, Any]:
        result = self.get_var(name)
        if result is None:
            raise ValueError(f"Variable '{name}' is not defined.")
        return result
