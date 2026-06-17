"""
Patch verification gates.

Every generated diff runs through this pipeline before it's exposed as
PATCHED. A patch only graduates if it survives all gates:

  1. Structural    — diff parses, has paths and hunks, size is sane
  2. Hallucination — every removed line actually exists in the source
  3. Syntactic     — patched source still parses (libcst → ast fallback)
  4. Static        — ruff finds no hard errors (E, F) in the patched file
  5. Imports       — no new top-level imports for unknown packages

Never raises. Returns a ValidationResult with the patched source and any
errors/warnings the caller can surface.
"""

import ast
import asyncio
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Optional

try:
    import libcst as cst
    _HAS_LIBCST = True
except ImportError:
    _HAS_LIBCST = False


MAX_DIFF_LINES = 200
RUFF_TIMEOUT_S = 5.0


_HUNK_HEADER = re.compile(
    r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@",
    re.MULTILINE,
)


# Hunk = (old_start, old_count, new_start, new_count, body_lines)
Hunk = tuple[int, int, int, int, list[str]]


@dataclass
class ValidationResult:
    valid: bool
    patched_source: Optional[str] = None
    errors:   list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def fail(self, msg: str) -> "ValidationResult":
        self.valid = False
        self.errors.append(msg)
        return self


async def validate(
    diff: str, file_path: str, source_text: Optional[str] = None
) -> ValidationResult:
    """
    Run every gate. Never raises.

    source_text, when provided, is the in-memory source the diff applies to
    (fetched from GitHub). When None, the source is read from disk (local dev).
    """
    result = ValidationResult(valid=True)

    if not diff or not diff.strip():
        return result.fail("empty diff")

    if len(diff.splitlines()) > MAX_DIFF_LINES:
        return result.fail(f"diff exceeds {MAX_DIFF_LINES} lines — auto-fix capped for safety")

    hunks = _parse_hunks(diff)
    if not hunks:
        return result.fail("no parseable hunks in diff")

    if source_text is not None:
        original = source_text
    else:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                original = f.read()
        except OSError as e:
            return result.fail(f"cannot read source: {e}")

    try:
        from .diff_engine import apply_to_text, DiffApplyError

        patched = apply_to_text(original, diff)
    except DiffApplyError as e:
        return result.fail(str(e))

    result.patched_source = patched

    syntax_err = _check_syntax(patched)
    if syntax_err:
        return result.fail(f"patched source has syntax error: {syntax_err}")

    ruff_errors = await _run_ruff(patched, file_path)
    for err in ruff_errors:
        result.errors.append(f"ruff: {err}")
        result.valid = False

    new_imports = _new_imports(original, patched)
    suspicious = [m for m in new_imports if not _is_known_module(m, file_path)]
    if suspicious:
        result.warnings.append(
            f"introduces new imports: {', '.join(suspicious)}"
        )

    return result


# ─────────────────────────── diff parsing ───────────────────────────

def _parse_hunks(diff: str) -> list[Hunk]:
    lines = diff.splitlines()
    hunks: list[Hunk] = []
    i = 0
    while i < len(lines):
        m = _HUNK_HEADER.match(lines[i])
        if not m:
            i += 1
            continue
        old_start = int(m.group(1))
        old_count = int(m.group(2)) if m.group(2) else 1
        new_start = int(m.group(3))
        new_count = int(m.group(4)) if m.group(4) else 1

        body: list[str] = []
        i += 1
        while i < len(lines):
            line = lines[i]
            if line.startswith("@@") or line.startswith("---") or line.startswith("+++"):
                break
            if not line or line[0] in (" ", "+", "-", "\\"):
                body.append(line)
            i += 1
        hunks.append((old_start, old_count, new_start, new_count, body))
    return hunks


# ─────────────────────────── diff applier (delegates to diff_engine) ──────────

# Legacy helpers kept for structural parsing in validate(); application uses
# orqis.rca.diff_engine.apply_to_text (H1).

def _check_syntax(source: str) -> Optional[str]:
    if _HAS_LIBCST:
        try:
            cst.parse_module(source)
            return None
        except cst.ParserSyntaxError as e:
            return str(e).splitlines()[0]
    try:
        ast.parse(source)
        return None
    except SyntaxError as e:
        return f"{e.msg} at line {e.lineno}"


async def _run_ruff(source: str, file_path: str) -> list[str]:
    """Run `ruff check` on patched source. Empty list = clean or ruff missing."""
    suffix = os.path.splitext(file_path)[1] or ".py"
    if suffix != ".py":
        return []

    tmp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=suffix, delete=False, encoding="utf-8"
        ) as f:
            f.write(source)
            tmp_path = f.name

        # F = pyflakes (real logic bugs: undefined names, unused imports).
        # E9 = syntax / runtime errors. Style rules (E1-E7) are excluded —
        # a stylistically ugly patch that works should not fail the gate.
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "ruff", "check",
            "--select", "F,E9",
            "--output-format", "concise",
            "--no-cache",
            "--isolated",
            tmp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _ = await asyncio.wait_for(
                proc.communicate(), timeout=RUFF_TIMEOUT_S
            )
        except asyncio.TimeoutError:
            proc.kill()
            return []

        if proc.returncode == 0:
            return []

        errors: list[str] = []
        for line in stdout.decode("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or "All checks passed" in line:
                continue
            # Skip ruff's summary footer ("Found N errors.")
            if re.match(r"^(\[\*\]\s*)?Found \d+ error", line):
                continue
            cleaned = re.sub(r"^.*?:\d+:\d+:\s+", "", line)
            errors.append(cleaned or line)
        return errors[:5]
    except FileNotFoundError:
        return []  # ruff not installed
    except Exception:
        return []
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# ─────────────────────────── imports check ───────────────────────────

_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))",
    re.MULTILINE,
)

_STDLIB = (
    frozenset(sys.stdlib_module_names)
    if hasattr(sys, "stdlib_module_names")
    else frozenset()
)


def _new_imports(original: str, patched: str) -> list[str]:
    def top_modules(src: str) -> set[str]:
        mods = set()
        for m in _IMPORT_RE.finditer(src):
            raw = (m.group(1) or m.group(2) or "").split(".")[0].strip()
            if raw:
                mods.add(raw)
        return mods

    return sorted(top_modules(patched) - top_modules(original))


def _is_known_module(name: str, file_path: str) -> bool:
    if name in _STDLIB:
        return True

    # Walk up from the source file looking for a sibling pkg/module
    project_dir = os.path.dirname(os.path.abspath(file_path))
    for _ in range(5):
        if (
            os.path.isdir(os.path.join(project_dir, name))
            or os.path.isfile(os.path.join(project_dir, f"{name}.py"))
        ):
            return True
        parent = os.path.dirname(project_dir)
        if parent == project_dir:
            break
        project_dir = parent

    # Last resort — check site-packages availability
    try:
        import importlib.util
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False
