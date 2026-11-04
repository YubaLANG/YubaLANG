from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Callable, Mapping

from .runtime import Runtime


@dataclass(frozen=True)
class DebugFrame:
    function: str
    source_name: str
    line_number: int


@dataclass(frozen=True)
class DebugEvent:
    reason: str
    source_name: str
    line_number: int
    function_depth: int
    stack: tuple[DebugFrame, ...]
    variables: Mapping[str, Any]


class Debugger:
    def __init__(self, on_stop: Callable[[DebugEvent], None]) -> None:
        self._on_stop = on_stop
        self._breakpoints: set[tuple[str | None, int]] = set()
        self._mode = "continue"
        self._target_depth = 0
        self._last_depth = 0

    def add_breakpoint(
        self, line_number: int, source_name: str | None = None
    ) -> None:
        if line_number < 1:
            raise ValueError("Breakpoint line numbers must be positive.")
        self._breakpoints.add((source_name, line_number))

    def remove_breakpoint(
        self, line_number: int, source_name: str | None = None
    ) -> bool:
        breakpoint = (source_name, line_number)
        if breakpoint not in self._breakpoints:
            return False
        self._breakpoints.remove(breakpoint)
        return True

    def continue_execution(self) -> None:
        self._mode = "continue"

    def step_into(self) -> None:
        self._mode = "step_into"

    def step_over(self) -> None:
        self._target_depth = self._last_depth
        self._mode = "step_over"

    def step_out(self) -> None:
        if self._last_depth == 0:
            self.continue_execution()
            return
        self._target_depth = self._last_depth
        self._mode = "step_out"

    def on_line(
        self, runtime: Runtime, source_name: str, line_number: int
    ) -> None:
        depth = runtime.function_call_depth
        breakpoint_hit = (
            (source_name, line_number) in self._breakpoints
            or (None, line_number) in self._breakpoints
        )
        step_hit = (
            self._mode == "step_into"
            or (
                self._mode == "step_over"
                and depth <= self._target_depth
            )
            or (
                self._mode == "step_out"
                and depth < self._target_depth
            )
        )
        if not breakpoint_hit and not step_hit:
            return

        self._mode = "continue"
        self._last_depth = depth
        visible_variables: dict[str, Any] = {}
        start = runtime.function_scope_starts[-1] if runtime.function_scope_starts else 0
        if start:
            visible_variables.update(
                {
                    name: variable["value"]
                    for name, variable in runtime.scopes[0].items()
                }
            )
        for scope in runtime.scopes[start:]:
            visible_variables.update(
                {
                    name: variable["value"]
                    for name, variable in scope.items()
                }
            )
        event = DebugEvent(
            reason="breakpoint" if breakpoint_hit else "step",
            source_name=source_name,
            line_number=line_number,
            function_depth=depth,
            stack=tuple(
                DebugFrame(function, call_source, call_line)
                for function, call_source, call_line in runtime.call_stack
            ),
            variables=MappingProxyType(visible_variables),
        )
        self._on_stop(event)
