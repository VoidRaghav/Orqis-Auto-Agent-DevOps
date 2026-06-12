"""
Traceback parser and code context extractor.

Given an error message or a multi-line traceback string, this module:
  1. Extracts the file path and line number of the failing frame.
  2. Reads the source file and returns the minimal code context the LLM
     needs to generate an accurate patch — the containing function body
     plus a few lines of surrounding context.

Design rules:
  - Never reads outside the project root (path traversal guard).
  - Returns None on any failure — the caller falls back to interpretation-only.
  - Only reads .py files for now (safe, well-understood AST).
  - Caps context at MAX_CONTEXT_LINES to bound LLM token cost.
"""

import ast
import os
import re
from typing import Optional

# Cap how many lines of source we send to the LLM.
# ~60 lines * ~8 tokens/line = ~480 tokens — well within Haiku's budget.
MAX_CONTEXT_LINES = 60

# Regex for a Python traceback frame line:
#   File "/path/to/file.py", line 42, in function_name
_FRAME_RE = re.compile(
    r'File "(?P<path>[^"]+\.py)",\s+line (?P<line>\d+)',
)


class CodeLocation:
    __slots__ = ("file_path", "line", "function_name", "context", "context_start_line")

    def __init__(
        self,
        file_path: str,
        line: int,
        function_name: Optional[str],
        context: str,
        context_start_line: int,
    ):
        self.file_path = file_path
        self.line = line
        self.function_name = function_name
        self.context = context          # source text sent to the LLM
        self.context_start_line = context_start_line  # line number of context[0]


def extract(error_text: str, project_root: Optional[str] = None) -> Optional[CodeLocation]:
    """
    Parse an error message / traceback and return the CodeLocation of the
    innermost (most recent) frame that belongs to the project.

    project_root: if given, only frames inside this directory are considered.
    Falls back to any readable .py file if no project frame is found.
    """
    frames = _parse_frames(error_text)
    if not frames:
        return None

    # Prefer the innermost frame that is inside the project root
    target = None
    for path, line in reversed(frames):
        abs_path = os.path.abspath(path)
        if not os.path.isfile(abs_path):
            continue
        if project_root:
            if not abs_path.startswith(os.path.abspath(project_root)):
                continue
        target = (abs_path, line)
        break

    # If nothing matched the project root, take the innermost readable frame
    if target is None:
        for path, line in reversed(frames):
            abs_path = os.path.abspath(path)
            if os.path.isfile(abs_path):
                target = (abs_path, line)
                break

    if target is None:
        return None

    file_path, line = target
    return _read_context(file_path, line)


def read_at(file_path: str, line: int, project_root: Optional[str] = None) -> Optional[CodeLocation]:
    """
    Resolve a CodeLocation directly from a known file and line — used by the
    anomaly detector, which already knows where the looping call lives and has
    no traceback to parse.

    Honours the same project-root path-traversal guard as extract().
    """
    abs_path = os.path.abspath(file_path)
    if not os.path.isfile(abs_path):
        return None
    if project_root and not abs_path.startswith(os.path.abspath(project_root)):
        return None
    return _read_context(abs_path, line)


def _parse_frames(text: str) -> list[tuple[str, int]]:
    """Return all (file_path, line_number) pairs from a traceback string."""
    return [
        (m.group("path"), int(m.group("line")))
        for m in _FRAME_RE.finditer(text)
    ]


def _read_context(file_path: str, error_line: int) -> Optional[CodeLocation]:
    """
    Read the source file and extract the function that contains error_line.
    Falls back to a fixed window around the line if AST parsing fails.
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
            all_lines = source.splitlines()
    except OSError:
        return None

    function_name, start, end = _find_function_bounds(source, error_line)

    # Clamp to MAX_CONTEXT_LINES centred on the error line
    if (end - start) > MAX_CONTEXT_LINES:
        half = MAX_CONTEXT_LINES // 2
        start = max(0, error_line - half - 1)
        end = min(len(all_lines), error_line + half)

    context_lines = all_lines[start:end]
    context = "\n".join(context_lines)

    return CodeLocation(
        file_path=file_path,
        line=error_line,
        function_name=function_name,
        context=context,
        context_start_line=start + 1,  # 1-indexed
    )


def _find_function_bounds(source: str, error_line: int) -> tuple[Optional[str], int, int]:
    """
    Use the AST to find the function/method that contains error_line.
    Returns (function_name, start_line, end_line) — all 0-indexed for slicing.
    Falls back to a ±30 line window on AST parse failure.
    """
    all_lines = source.splitlines()
    total = len(all_lines)

    try:
        tree = ast.parse(source)
    except SyntaxError:
        # File has a syntax error — still useful to show the window around the error
        half = MAX_CONTEXT_LINES // 2
        start = max(0, error_line - half - 1)
        end = min(total, error_line + half)
        return None, start, end

    best: Optional[ast.FunctionDef] = None

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        # ast line numbers are 1-indexed
        func_start = node.lineno
        func_end = node.end_lineno or func_start
        if func_start <= error_line <= func_end:
            # Prefer the innermost (tightest) function
            if best is None or (func_end - func_start) < (best.end_lineno - best.lineno):
                best = node

    if best is not None:
        # Include one line of padding before the def for decorators
        start = max(0, best.lineno - 2)
        end = min(total, best.end_lineno + 1)
        return best.name, start, end

    # No function found (module-level code) — use a fixed window
    half = MAX_CONTEXT_LINES // 2
    start = max(0, error_line - half - 1)
    end = min(total, error_line + half)
    return None, start, end
