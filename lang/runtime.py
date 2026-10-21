from dataclasses import dataclass, field
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

    def update_var(self, name: str, var_type: str, value: Any) -> None:
        if name in self.scopes[-1]:
            target_scope = self.scopes[-1]
        elif name in self.scopes[0]:
            target_scope = self.scopes[0]
        else:
            raise ValueError(f"Variable '{name}' is not defined.")
        target_scope[name] = {"type": var_type, "value": value}

    def require_var(self, name: str) -> dict[str, Any]:
        result = self.get_var(name)
        if result is None:
            raise ValueError(f"Variable '{name}' is not defined.")
        return result
