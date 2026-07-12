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

# How many recent turns of memory to keep once we cap unbounded history. Enough
# to preserve useful context; bounded so tokens/cost stop climbing.
MAX_HISTORY = 20

# Ceiling for the exponential backoff we inject into a no-backoff retry loop, so
# a struggling downstream is not hammered and the retries stop bleeding cost.
BACKOFF_CAP_SECONDS = 8

# How many documents to keep when a whole collection is stuffed into a prompt
# that overflows the model's window. Bounds the context so it fits, instead of
# letting the API silently truncate it.
MAX_CONTEXT_DOCS = 15


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


def guard_corrupt_output(location: CodeLocation, tool_name: str) -> Optional[str]:
    """
    Produce a unified diff that validates a tool's return value before the agent
    uses it, so an empty/degenerate payload is caught instead of silently
    propagating. Inserts, right after `<var> = <tool_name>(...)`:

        if not <var>:
            raise ValueError("<tool_name> returned an empty or invalid payload")

    Returns None if libcst is unavailable, the file can't be parsed, or the tool
    call isn't a simple assignment we can guard — the caller falls back to the LLM.
    """
    if not _HAS_LIBCST or not location.function_name or not tool_name:
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

    transformer = _GuardCorrupt(location.function_name, tool_name)
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


def cap_unbounded_memory(location: CodeLocation) -> Optional[str]:
    """
    Produce a unified diff that bounds an agent's unbounded memory so per-call
    tokens stop climbing. Inserts, right after the first `<mem>.append(...)` in
    the function:

        <mem>[:] = <mem>[-MAX_HISTORY:]

    which trims the history in place (works for a module-level list or self.x).
    Returns None if libcst is unavailable, the file can't be parsed, or there is
    no append to cap — the caller falls back to the LLM.
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

    transformer = _CapMemory(location.function_name)
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


def add_backoff(location: CodeLocation) -> Optional[str]:
    """
    Produce a unified diff that adds exponential backoff to a no-backoff retry
    loop, so transient failures are not retried in a tight, cost-bleeding storm.
    Inserts, at the end of the first `for <var> in ...:` loop body:

        time.sleep(min(2 ** <var>, BACKOFF_CAP_SECONDS))

    and adds `import time` if the module doesn't already import it. Returns None
    if libcst is unavailable, the file can't be parsed, or the function has no
    for-loop with a simple counter to back off on — the caller falls back to LLM.
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

    transformer = _AddBackoff(location.function_name)
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


def fix_binding_drop(location: CodeLocation) -> Optional[str]:
    """
    Produce a unified diff that stops a bound tool being silently dropped by a
    chained `.with_structured_output(...)`. It rewrites

        model.bind_tools([...]).with_structured_output(Schema)
    to
        model.bind_tools([...])

    so the bound tool is actually invoked again (the model no longer fabricates
    the structured object). Returns None if libcst is unavailable, the file
    can't be parsed, or the anti-pattern isn't present — the caller falls back
    to the LLM, which can also re-add structured parsing on top.
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

    transformer = _DropStructuredOutput(location.function_name)
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


def cap_context_window(location: CodeLocation) -> Optional[str]:
    """
    Produce a unified diff that bounds a context that overflows the model window.
    It finds the first `<sep>.join(<collection>)` in the function and slices the
    collection, so only the first MAX_CONTEXT_DOCS items are stuffed into the
    prompt:

        "\\n".join(KNOWLEDGE_BASE)   ->   "\\n".join(KNOWLEDGE_BASE[:MAX_CONTEXT_DOCS])

    Returns None if libcst is unavailable, the file can't be parsed, or there is
    no such join to bound — the caller falls back to the LLM (which can add
    relevance-ranked retrieval instead of a simple cap).
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

    transformer = _CapContext(location.function_name)
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


class _GuardCorrupt(cst.CSTTransformer):
    """
    Inside the target function, find the first `<var> = <tool_name>(...)`
    assignment and insert an emptiness guard immediately after it, turning a
    silently-consumed corrupt payload into a caught, actionable failure.
    """

    def __init__(self, func_name: str, tool_name: str):
        self.func_name = func_name
        self.tool_name = tool_name
        self.patched = False

    def leave_FunctionDef(
        self, original_node: "cst.FunctionDef", updated_node: "cst.FunctionDef"
    ) -> "cst.FunctionDef":
        if self.patched or original_node.name.value != self.func_name:
            return updated_node
        if not isinstance(updated_node.body, cst.IndentedBlock):
            return updated_node

        new_statements = []
        done = False
        for stmt in updated_node.body.body:
            new_statements.append(stmt)
            if not done:
                var = self._tool_assign_target(stmt)
                if var is not None:
                    new_statements.append(self._guard(var))
                    done = True

        if not done:
            return updated_node

        self.patched = True
        return updated_node.with_changes(
            body=updated_node.body.with_changes(body=new_statements)
        )

    def _tool_assign_target(self, stmt) -> Optional[str]:
        """Return the target var name if stmt is `<name> = <tool_name>(...)`."""
        if not isinstance(stmt, cst.SimpleStatementLine):
            return None
        for small in stmt.body:
            if not isinstance(small, cst.Assign) or not isinstance(small.value, cst.Call):
                continue
            func = small.value.func
            called = (
                func.value if isinstance(func, cst.Name)
                else func.attr.value if isinstance(func, cst.Attribute)
                else None
            )
            if (
                called == self.tool_name
                and len(small.targets) == 1
                and isinstance(small.targets[0].target, cst.Name)
            ):
                return small.targets[0].target.value
        return None

    def _guard(self, var: str) -> "cst.BaseStatement":
        return cst.parse_statement(
            f'if not {var}:\n'
            f'    raise ValueError("{self.tool_name} returned an empty or invalid payload")\n'
        )


class _CapMemory(cst.CSTTransformer):
    """
    Inside the target function, find the first `<mem>.append(...)` and insert an
    in-place trim right after it, so the agent's memory (and its per-call token
    count) stays bounded instead of growing every turn.
    """

    def __init__(self, func_name: str):
        self.func_name = func_name
        self.patched = False

    def leave_FunctionDef(
        self, original_node: "cst.FunctionDef", updated_node: "cst.FunctionDef"
    ) -> "cst.FunctionDef":
        if self.patched or original_node.name.value != self.func_name:
            return updated_node
        if not isinstance(updated_node.body, cst.IndentedBlock):
            return updated_node

        new_statements = []
        done = False
        for stmt in updated_node.body.body:
            new_statements.append(stmt)
            if not done:
                recv = self._append_receiver(stmt)
                if recv is not None:
                    new_statements.append(self._cap(recv))
                    done = True

        if not done:
            return updated_node

        self.patched = True
        return updated_node.with_changes(
            body=updated_node.body.with_changes(body=new_statements)
        )

    def _append_receiver(self, stmt) -> "Optional[cst.BaseExpression]":
        """Return the receiver of `<recv>.append(...)` if stmt is one, else None."""
        if not isinstance(stmt, cst.SimpleStatementLine):
            return None
        for small in stmt.body:
            if not isinstance(small, cst.Expr) or not isinstance(small.value, cst.Call):
                continue
            func = small.value.func
            if isinstance(func, cst.Attribute) and func.attr.value == "append":
                return func.value
        return None

    def _cap(self, receiver: "cst.BaseExpression") -> "cst.BaseStatement":
        recv = cst.Module([]).code_for_node(receiver)
        return cst.parse_statement(f"{recv}[:] = {recv}[-{MAX_HISTORY}:]\n")


class _AddBackoff(cst.CSTTransformer):
    """
    Inside the target function, add exponential backoff to the end of the first
    `for <var> in ...:` loop body, and ensure `import time` is present at module
    scope so the sleep resolves.
    """

    def __init__(self, func_name: str):
        self.func_name = func_name
        self.patched = False

    def leave_FunctionDef(
        self, original_node: "cst.FunctionDef", updated_node: "cst.FunctionDef"
    ) -> "cst.FunctionDef":
        if self.patched or original_node.name.value != self.func_name:
            return updated_node
        if not isinstance(updated_node.body, cst.IndentedBlock):
            return updated_node

        new_statements = []
        done = False
        for stmt in updated_node.body.body:
            if (
                not done
                and isinstance(stmt, cst.For)
                and isinstance(stmt.target, cst.Name)
                and isinstance(stmt.body, cst.IndentedBlock)
            ):
                new_statements.append(self._with_backoff(stmt))
                done = True
            else:
                new_statements.append(stmt)

        if not done:
            return updated_node

        self.patched = True
        return updated_node.with_changes(
            body=updated_node.body.with_changes(body=new_statements)
        )

    def _with_backoff(self, for_node: "cst.For") -> "cst.For":
        var = for_node.target.value
        sleep = cst.parse_statement(
            f"time.sleep(min(2 ** {var}, {BACKOFF_CAP_SECONDS}))\n"
        )
        new_body = for_node.body.with_changes(body=[*for_node.body.body, sleep])
        return for_node.with_changes(body=new_body)

    def leave_Module(
        self, original_node: "cst.Module", updated_node: "cst.Module"
    ) -> "cst.Module":
        if not self.patched or _imports_time(updated_node):
            return updated_node
        imp = cst.parse_statement("import time\n")
        body = list(updated_node.body)
        insert_at = 1 if body and _is_docstring(body[0]) else 0
        body.insert(insert_at, imp)
        return updated_node.with_changes(body=body)


def _imports_time(module: "cst.Module") -> bool:
    """True if the module already imports the time module (import or from-import)."""
    for stmt in module.body:
        if not isinstance(stmt, cst.SimpleStatementLine):
            continue
        for small in stmt.body:
            if isinstance(small, cst.Import):
                if any(isinstance(a.name, cst.Name) and a.name.value == "time" for a in small.names):
                    return True
            elif isinstance(small, cst.ImportFrom):
                mod = small.module
                if isinstance(mod, cst.Name) and mod.value == "time":
                    return True
    return False


def _is_docstring(stmt) -> bool:
    return (
        isinstance(stmt, cst.SimpleStatementLine)
        and len(stmt.body) == 1
        and isinstance(stmt.body[0], cst.Expr)
        and isinstance(stmt.body[0].value, (cst.SimpleString, cst.ConcatenatedString))
    )


class _DropStructuredOutput(cst.CSTTransformer):
    """
    Inside the target function, rewrite `<chain>.with_structured_output(...)` to
    `<chain>` when the chain binds tools, so the bound tool is invoked instead of
    being dropped. Rewrites the first such call only.
    """

    def __init__(self, func_name: str):
        self.func_name = func_name
        self.patched = False
        self._depth = 0  # >0 while inside the target function

    def visit_FunctionDef(self, node: "cst.FunctionDef") -> None:
        if node.name.value == self.func_name:
            self._depth += 1

    def leave_FunctionDef(
        self, original_node: "cst.FunctionDef", updated_node: "cst.FunctionDef"
    ) -> "cst.FunctionDef":
        if original_node.name.value == self.func_name and self._depth > 0:
            self._depth -= 1
        return updated_node

    def leave_Call(self, original_node: "cst.Call", updated_node: "cst.Call"):
        if self.patched or self._depth <= 0:
            return updated_node
        func = updated_node.func
        if (
            isinstance(func, cst.Attribute)
            and func.attr.value == "with_structured_output"
            and self._chain_binds_tools(func.value)
        ):
            self.patched = True
            return func.value  # drop the structured-output wrapper
        return updated_node

    def _chain_binds_tools(self, node) -> bool:
        """True if the receiver chain contains a .bind_tools(...) / .bind(...) call."""
        cur = node
        while isinstance(cur, cst.Call):
            fn = cur.func
            if isinstance(fn, cst.Attribute):
                if fn.attr.value in ("bind_tools", "bind"):
                    return True
                cur = fn.value
            else:
                break
        return False


class _CapContext(cst.CSTTransformer):
    """
    Inside the target function, slice the collection in the first
    `<sep>.join(<Name>)` to the first MAX_CONTEXT_DOCS items, so an over-window
    context is bounded instead of silently truncated.
    """

    def __init__(self, func_name: str):
        self.func_name = func_name
        self.patched = False
        self._depth = 0

    def visit_FunctionDef(self, node: "cst.FunctionDef") -> None:
        if node.name.value == self.func_name:
            self._depth += 1

    def leave_FunctionDef(
        self, original_node: "cst.FunctionDef", updated_node: "cst.FunctionDef"
    ) -> "cst.FunctionDef":
        if original_node.name.value == self.func_name and self._depth > 0:
            self._depth -= 1
        return updated_node

    def leave_Call(self, original_node: "cst.Call", updated_node: "cst.Call"):
        if self.patched or self._depth <= 0:
            return updated_node
        func = updated_node.func
        if (
            isinstance(func, cst.Attribute)
            and func.attr.value == "join"
            and len(updated_node.args) == 1
            and isinstance(updated_node.args[0].value, cst.Name)
        ):
            self.patched = True
            name = updated_node.args[0].value
            sliced = cst.Subscript(
                value=name,
                slice=[cst.SubscriptElement(
                    slice=cst.Slice(lower=None, upper=cst.Integer(str(MAX_CONTEXT_DOCS)))
                )],
            )
            new_arg = updated_node.args[0].with_changes(value=sliced)
            return updated_node.with_changes(args=[new_arg])
        return updated_node


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
