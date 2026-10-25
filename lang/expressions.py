"""Evaluation of YubaLANG's expression grammar without Python eval."""

import ast
import operator
import re
from typing import Any, Callable

from .runtime import Runtime


_OPERATORS: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_COMPARISONS: dict[type[ast.cmpop], Callable[[Any, Any], bool]] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


def _normalize(source: str) -> str:
    result = []
    quote = None
    escaped = False
    index = 0
    replacements = {"true": "True", "false": "False", "none": "None"}
    while index < len(source):
        char = source[index]
        if quote is not None:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in ("'", '"'):
            quote = char
            result.append(char)
            index += 1
            continue
        match = re.match(r"[A-Za-z_]\w*", source[index:])
        if match is None:
            result.append(char)
            index += 1
            continue
        token = match.group()
        before = source[index - 1] if index else ""
        after_index = index + len(token)
        after = source[after_index] if after_index < len(source) else ""
        if (
            token.lower() in replacements
            and not (before.isalnum() or before == "_")
            and not (after.isalnum() or after == "_")
        ):
            token = replacements[token.lower()]
        result.append(token)
        index = after_index
    return "".join(result)


def parse_expression(source: str) -> ast.expr:
    try:
        expression = ast.parse(_normalize(source), mode="eval").body
    except SyntaxError as error:
        raise SyntaxError(f"Invalid expression: {error.msg}.") from error
    allowed = (
        ast.Constant, ast.Name, ast.List, ast.Tuple, ast.Set, ast.Dict,
        ast.UnaryOp, ast.UAdd, ast.USub, ast.Not, ast.BinOp,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
        ast.BoolOp, ast.And, ast.Or, ast.Compare, ast.Eq, ast.NotEq,
        ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Load,
    )
    for node in ast.walk(expression):
        if not isinstance(node, allowed):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "set"
                and not node.args and not node.keywords
            ):
                raise SyntaxError("Unsupported syntax in expression.")
    return expression


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def evaluate_expression(source: str, runtime: Runtime) -> Any:
    expression = parse_expression(source)

    def evaluate(node: ast.expr) -> Any:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (str, int, float, bool, type(None))):
                return node.value
            raise SyntaxError("Unsupported literal in expression.")
        if isinstance(node, ast.Name):
            variable = runtime.get_var(node.id)
            if variable is None:
                raise ValueError(f"Variable '{node.id}' is not defined.")
            return variable["value"]
        if isinstance(node, ast.List):
            return [evaluate(item) for item in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(evaluate(item) for item in node.elts)
        if isinstance(node, ast.Set):
            return {evaluate(item) for item in node.elts}
        if isinstance(node, ast.Dict):
            return {
                evaluate(key): evaluate(value)
                for key, value in zip(node.keys, node.values)
            }
        if (
            isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "set" and not node.args and not node.keywords
        ):
            return set()
        if isinstance(node, ast.UnaryOp):
            value = evaluate(node.operand)
            if isinstance(node.op, ast.UAdd) and _number(value):
                return value
            if isinstance(node.op, ast.USub) and _number(value):
                return -value
            if isinstance(node.op, ast.Not) and isinstance(value, bool):
                return not value
            raise TypeError("Unary operators require a number or boolean.")
        if isinstance(node, ast.BinOp):
            operation = _OPERATORS.get(type(node.op))
            left, right = evaluate(node.left), evaluate(node.right)
            if operation is None:
                raise SyntaxError("Unsupported operator in expression.")
            if not _number(left) or not _number(right):
                raise TypeError("Arithmetic operators require numeric operands.")
            result = operation(left, right)
            if not _number(result):
                raise TypeError("Arithmetic result is outside the supported numeric types.")
            return result
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                for item in node.values:
                    value = evaluate(item)
                    if not isinstance(value, bool):
                        raise TypeError("Boolean operators require boolean operands.")
                    if not value:
                        return False
                return True
            if isinstance(node.op, ast.Or):
                for item in node.values:
                    value = evaluate(item)
                    if not isinstance(value, bool):
                        raise TypeError("Boolean operators require boolean operands.")
                    if value:
                        return True
                return False
            raise SyntaxError("Unsupported boolean operator in expression.")
        if isinstance(node, ast.Compare):
            left = evaluate(node.left)
            for operation_node, comparator in zip(node.ops, node.comparators):
                right = evaluate(comparator)
                operation = _COMPARISONS.get(type(operation_node))
                if operation is None:
                    raise SyntaxError("Unsupported comparison in expression.")
                if not operation(left, right):
                    return False
                left = right
            return True
        raise SyntaxError("Unsupported value in expression.")

    return evaluate(expression)
