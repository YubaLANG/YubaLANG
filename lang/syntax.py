"""Shared line tokenizer and source-located command syntax nodes."""

from dataclasses import dataclass
import shlex


@dataclass(frozen=True)
class SourceLocation:
    source_name: str
    line: int
    column: int = 1


@dataclass(frozen=True)
class CommandNode:
    tokens: tuple[str, ...]
    location: SourceLocation


def tokenize_line(line: str) -> tuple[str, ...]:
    try:
        return tuple(shlex.split(line, posix=False, comments=True))
    except ValueError as error:
        raise SyntaxError(f"Invalid command quoting: {error}") from error


def parse_line(
    line: str, source_name: str = "<memory>", line_number: int = 1
) -> CommandNode | None:
    tokens = tokenize_line(line)
    if not tokens:
        return None
    column = len(line) - len(line.lstrip()) + 1
    return CommandNode(tokens, SourceLocation(source_name, line_number, column))


def parse_program(
    lines: list[str],
    source_name: str = "<memory>",
    line_numbers: list[int] | None = None,
) -> tuple[CommandNode, ...]:
    if line_numbers is None:
        line_numbers = list(range(1, len(lines) + 1))
    if len(line_numbers) != len(lines):
        raise ValueError("Source line mapping must match the number of program lines.")
    nodes = []
    for line, line_number in zip(lines, line_numbers):
        node = parse_line(line, source_name, line_number)
        if node is not None:
            nodes.append(node)
    return tuple(nodes)
