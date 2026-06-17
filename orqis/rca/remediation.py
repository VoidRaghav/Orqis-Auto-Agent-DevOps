"""
Deterministic remediation for known failure classes.

Some failures have a structurally predictable fix. A runaway tool loop is one:
the remedy is always the same shape — bound the loop with a maximum attempt
count and return a safe fallback when it is reached. For these, Orqis applies a
verified code transform instead of asking an LLM, so the patch is correct by
construction and passes every verification gate. The LLM remains the fallback
for novel errors whose fix can't be templated.

The transform is a libcst rewrite, which round-trips the file losslessly, so
every unchanged line is preserved byte-for-byte and the resulting diff applies
cleanly. It handles the common pattern — a `while` loop directly inside the
failing function. Anything more exotic returns None and the caller falls back
to the LLM patch generator.
"""

import difflib
from typing import Optional

try:
    import libcst as cst
    _HAS_LIBCST = True
except ImportError:
    _HAS_LIBCST = False

from ..rca.file_reader import CodeLocation

# How many attempts before the guard gives up. Generous enough that a genuine
# transient ("processing" -> "shipped") resolves; tight enough to stop a loop.
MAX_ATTEMPTS = 5


def guard_runaway_loop(location: CodeLocation) -> Optional[str]:
    """
    Produce a unified diff that bounds the runaway loop in location's function.
    Returns None if libcst is unavailable, the file can't be parsed, or the
    function has no directly-nested while loop to guard.
    """
    if not _HAS_LIBCST or not location.function_name:
        return None

    if location.source_text is not None:
        original = location.source_text
    else:
        try:
            with open(location.file_path, "r", encoding="utf-8") as f:
                original = f.read()
        except OSError:
            return None

    try:
        module = cst.parse_module(original)
    except Exception:
        return None

    counter = _unique_name(original)
    transformer = _GuardLoop(location.function_name, counter)
    try:
        new_module = module.visit(transformer)
    except Exception:
        return None

    if not transformer.patched:
        return None

    patched = new_module.code
    if patched == original:
        return None

    header_path = location.repo_relative_path or location.file_path
    return _unified_diff(header_path, original, patched)


def _unique_name(source: str, base: str = "_attempts") -> str:
    """Pick a counter name that doesn't already appear in the source."""
    if base not in source:
        return base
    i = 2
    while f"{base}{i}" in source:
        i += 1
    return f"{base}{i}"


def _fallback_for(returns: "Optional[cst.Annotation]") -> str:
    """A type-appropriate fallback return value for the guard."""
    if returns is not None and isinstance(returns.annotation, cst.Name):
        name = returns.annotation.value
        if name == "str":
            return '"escalated to a human agent"'
        if name in ("int", "float"):
            return "0"
        if name == "bool":
            return "False"
    return "None"


class _GuardLoop(cst.CSTTransformer):
    """
    Inside the target function, wrap the first directly-nested while loop with:
      <counter> = 0                       # before the loop
      while ...:
          if <counter> >= MAX_ATTEMPTS:   # at the top of the body
              return <fallback>
          ... original body ...
          <counter> += 1                  # at the end of the body
    """

    def __init__(self, func_name: str, counter: str):
        self.func_name = func_name
        self.counter = counter
        self.patched = False

    def leave_FunctionDef(
        self, original_node: "cst.FunctionDef", updated_node: "cst.FunctionDef"
    ) -> "cst.FunctionDef":
        if self.patched or original_node.name.value != self.func_name:
            return updated_node
        if not isinstance(updated_node.body, cst.IndentedBlock):
            return updated_node

        fallback = _fallback_for(updated_node.returns)
        new_statements = []
        done = False
        for stmt in updated_node.body.body:
            if (
                not done
                and isinstance(stmt, cst.While)
                and isinstance(stmt.body, cst.IndentedBlock)
            ):
                new_statements.append(cst.parse_statement(f"{self.counter} = 0\n"))
                new_statements.append(self._guard(stmt, fallback))
                done = True
            else:
                new_statements.append(stmt)

        if not done:
            return updated_node

        self.patched = True
        return updated_node.with_changes(
            body=updated_node.body.with_changes(body=new_statements)
        )

    def _guard(self, while_node: "cst.While", fallback: str) -> "cst.While":
        guard = cst.parse_statement(
            f"if {self.counter} >= {MAX_ATTEMPTS}:\n    return {fallback}\n"
        )
        increment = cst.parse_statement(f"{self.counter} += 1\n")
        new_body = while_node.body.with_changes(
            body=[guard, *while_node.body.body, increment]
        )
        return while_node.with_changes(body=new_body)


def _unified_diff(file_path: str, original: str, patched: str) -> Optional[str]:
    diff_lines = list(
        difflib.unified_diff(
            original.splitlines(),
            patched.splitlines(),
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm="",
        )
    )
    if not diff_lines:
        return None
    return "\n".join(diff_lines) + "\n"
