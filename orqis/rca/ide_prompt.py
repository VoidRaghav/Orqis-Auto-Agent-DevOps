"""
IDE-agnostic fix prompts — plain text any AI coding assistant can act on.

Works when pasted into VS Code Copilot Chat, Cursor, Claude Code, Windsurf,
JetBrains AI, Zed, or any terminal-based coding agent. No vendor-specific APIs.
"""

from ..backend.models import Incident


def build_fix_prompt(incident: Incident) -> str:
    """Return a self-contained prompt for any AI assistant in any IDE."""
    path = incident.repo_relative_path or incident.file_path
    if path:
        path = path.replace("\\", "/")

    lines = [
        "Orqis detected a production error. Help the developer fix it in their editor.",
        "",
        "This prompt works in any IDE or AI assistant (VS Code, Cursor, Claude Code,",
        "Windsurf, JetBrains, Zed, terminal agents, etc.) — paste it into the chat.",
        "",
        f"Error: {incident.error_message}",
    ]

    if incident.interpretation:
        lines.append(f"What happened: {incident.interpretation}")

    if path:
        loc = f"{path}"
        if incident.error_line:
            loc += f":{incident.error_line}"
        lines.append(f"Location: {loc}")

    if incident.function_name:
        lines.append(f"Function: {incident.function_name}()")

    if incident.repo_full_name:
        lines.append(f"Repository: {incident.repo_full_name}")
        if incident.pr_url:
            lines.append(
                f"A fix PR may already exist: {incident.pr_url} — review/merge on GitHub "
                "instead of editing locally if appropriate."
            )

    if incident.code_context:
        lines.append("")
        lines.append(f"Code context (around line {incident.context_start_line}):")
        lines.append(f"```python\n{incident.code_context}\n```")

    if incident.diff:
        lines.append("")
        lines.append("Suggested fix (unified diff):")
        lines.append(f"```diff\n{incident.diff}\n```")
        lines.append("")
        lines.append("Instructions:")
        if path:
            lines.append(f"1. Open `{path}` in the workspace.")
        else:
            lines.append("1. Open the file shown in the diff.")
        lines.append(
            "2. Apply the diff exactly (or implement the same logic if your tool "
            "cannot apply patches)."
        )
        lines.append("3. Keep style consistent with the surrounding code.")
        lines.append("4. Briefly explain what you changed.")
        if not incident.repo_full_name:
            lines.append(
                "5. Orqis can also apply this fix via the dashboard "
                "\"Apply Fix\" button if you prefer not to edit manually."
            )
    else:
        lines.append("")
        lines.append(
            "No automated patch was generated. Investigate the error and propose a minimal fix."
        )

    return "\n".join(lines)
