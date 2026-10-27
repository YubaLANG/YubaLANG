"""Parsing and shared representations for YubaLANG type annotations."""

from dataclasses import dataclass, field
import re


_TOKEN = re.compile(r"\s*(->|[A-Za-z_]\w*|[?\[\](),|])")


@dataclass(frozen=True)
class TypeSpec:
    name: str
    arguments: tuple["TypeSpec", ...] = ()


@dataclass(frozen=True)
class FunctionReference:
    name: str
    target: object | None = field(default=None, compare=False, repr=False)


class TypeSyntaxError(ValueError):
    pass


class _Parser:
    def __init__(self, source: str) -> None:
        self.tokens = []
        position = 0
        while position < len(source):
            if not source[position:].strip():
                break
            match = _TOKEN.match(source, position)
            if match is None:
                raise TypeSyntaxError(f"Invalid type syntax near '{source[position:]}'.")
            self.tokens.append(match.group(1))
            position = match.end()
        self.index = 0

    def peek(self) -> str | None:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def take(self, expected: str | None = None) -> str:
        token = self.peek()
        if token is None or (expected is not None and token != expected):
            wanted = f"'{expected}'" if expected is not None else "a type"
            raise TypeSyntaxError(f"Expected {wanted} in type annotation.")
        self.index += 1
        return token

    def parse(self) -> TypeSpec:
        result = self.parse_union()
        if self.peek() is not None:
            raise TypeSyntaxError(f"Unexpected '{self.peek()}' in type annotation.")
        return result

    def parse_union(self) -> TypeSpec:
        options = [self.parse_postfix()]
        while self.peek() == "|":
            self.take("|")
            options.append(self.parse_postfix())
        if len(options) == 1:
            return options[0]
        flattened = []
        for option in options:
            flattened.extend(option.arguments if option.name == "union" else (option,))
        unique = tuple(dict.fromkeys(flattened))
        return TypeSpec("union", unique)

    def parse_postfix(self) -> TypeSpec:
        result = self.parse_primary()
        while self.peek() == "?":
            if result.name == "union" and any(
                option.name == "none" for option in result.arguments
            ):
                raise TypeSyntaxError("An optional type cannot have repeated '?'.")
            self.take("?")
            result = self.parse_union_members((result, TypeSpec("none")))
        return result

    @staticmethod
    def parse_union_members(options: tuple[TypeSpec, ...]) -> TypeSpec:
        flattened = []
        for option in options:
            flattened.extend(option.arguments if option.name == "union" else (option,))
        return TypeSpec("union", tuple(dict.fromkeys(flattened)))

    def parse_primary(self) -> TypeSpec:
        if self.peek() == "(":
            self.take("(")
            arguments = []
            if self.peek() != ")":
                arguments.append(self.parse_union())
                while self.peek() == ",":
                    self.take(",")
                    arguments.append(self.parse_union())
            self.take(")")
            if self.peek() == "->":
                self.take("->")
                return TypeSpec("function", (*arguments, self.parse_union()))
            if len(arguments) != 1:
                raise TypeSyntaxError("Parenthesized types must contain exactly one type.")
            result = arguments[0]
        else:
            result = TypeSpec(self.take())

        if self.peek() == "[":
            self.take("[")
            arguments = [self.parse_union()]
            while self.peek() == ",":
                self.take(",")
                arguments.append(self.parse_union())
            self.take("]")
            result = TypeSpec(result.name, tuple(arguments))
        return result


def parse_type(source: str) -> TypeSpec:
    return _Parser(source).parse()


def format_type(spec: TypeSpec) -> str:
    if spec.name == "union":
        return " | ".join(format_type(option) for option in spec.arguments)
    if spec.name == "function":
        *parameters, result = spec.arguments
        return f"({', '.join(format_type(item) for item in parameters)}) -> {format_type(result)}"
    if spec.arguments:
        return f"{spec.name}[{', '.join(format_type(item) for item in spec.arguments)}]"
    return spec.name


def is_known_type(spec: TypeSpec, records: set[str]) -> bool:
    if spec.name == "union":
        return all(is_known_type(item, records) for item in spec.arguments)
    if spec.name == "function":
        return all(is_known_type(item, records) for item in spec.arguments)
    generic_arity = {"list": 1, "set": 1, "tuple": None, "dict": 2}
    if spec.name in generic_arity:
        if not spec.arguments:
            return True
        arity = generic_arity[spec.name]
        return (
            (arity is None or arity == len(spec.arguments))
            and all(is_known_type(item, records) for item in spec.arguments)
        )
    return not spec.arguments and (
        spec.name in {
            "int", "float", "string", "bool", "none", "list", "dict",
            "set", "tuple", "bytes", "bytearray", "iterator", "file",
        }
        or spec.name in records
    )
