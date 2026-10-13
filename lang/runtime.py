from dataclasses import dataclass, field
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


@dataclass
class Runtime:
    scopes: list[dict[str, dict[str, Any]]] = field(default_factory=lambda: [{}])
    functions: dict[str, UserFunction] = field(default_factory=dict)

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
