import os
from pathlib import Path
from typing import Optional

VAULT_ENV = "OBSIDIAN_VAULT_PATH"

class ObsidianFSAdapter:
    """
    Minimal filesystem adapter for Obsidian markdown files.
    Writes inside the configured vault root (env OBSIDIAN_VAULT_PATH).
    If the env var is missing, falls back to a local folder: ./_vault
    """

    def __init__(self, vault_root: Optional[str] = None):
        root = vault_root or os.environ.get(VAULT_ENV) or "./_vault"
        self.vault = Path(root).expanduser().resolve()
        self.vault.mkdir(parents=True, exist_ok=True)

    # -------- helpers --------
    def _safe_path(self, rel_path: str) -> Path:
        rel = Path(rel_path)
        if rel.is_absolute():
            # Disallow absolute paths; Obsidian expects vault-relative
            raise ValueError("path must be vault-relative, not absolute")
        # Normalize and ensure .md suffix
        if rel.suffix.lower() != ".md":
            raise ValueError("path must end with .md")
        full = (self.vault / rel).resolve()
        # Prevent path traversal outside the vault
        if not str(full).startswith(str(self.vault)):
            raise ValueError("path escapes vault root")
        full.parent.mkdir(parents=True, exist_ok=True)
        return full

    def _read_lines(self, file: Path) -> list[str]:
        if not file.exists():
            return []
        return file.read_text(encoding="utf-8").splitlines()

    def _write_lines(self, file: Path, lines: list[str]) -> None:
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    # -------- actions --------
    def note_create(self, path: str, title: str, body_md: str, vault: Optional[str] = None) -> str:
        file = self._safe_path(path)
        if file.exists():
            raise ValueError(f"note already exists: {path}")
        lines = []
        # If the file name doesn't already include a title in content, add one
        if title and not body_md.lstrip().startswith("#"):
            lines.append(f"# {title}")
            lines.append("")
        lines.extend(body_md.splitlines())
        self._write_lines(file, lines)
        return str(path)

    def note_update(self, path: str, body_md: str, vault: Optional[str] = None) -> str:
        file = self._safe_path(path)
        self._write_lines(file, body_md.splitlines())
        return str(path)

    def note_append(self, path: str, body_md: str, position: str = "bottom",
                    heading: Optional[str] = None, vault: Optional[str] = None) -> str:
        file = self._safe_path(path)
        lines = self._read_lines(file)
        if not lines:
            # Create an empty file with a heading if needed
            lines = []

        snippet = body_md.splitlines()

        if position == "top":
            new_lines = snippet + [""] + lines if lines else snippet + [""]
        elif position == "after_heading":
            if not heading:
                raise ValueError("heading is required when position=after_heading")
            idx = self._find_heading_index(lines, heading)
            if idx is None:
                # If heading doesn't exist, add it at the end then append
                if lines and lines[-1] != "":
                    lines.append("")
                lines.append(f"# {heading}")
                lines.append("")
                idx = len(lines) - 1  # index of the heading line
            insert_at = self._scan_to_section_end(lines, idx)
            new_lines = lines[:insert_at] + snippet + [""] + lines[insert_at:]
        else:  # bottom (default)
            if lines and lines[-1] != "":
                lines.append("")
            new_lines = lines + snippet + [""]

        self._write_lines(file, new_lines)
        return str(path)

    def task_create(self, path: str, task_text: str, due: Optional[str] = None,
                    tags: Optional[list[str]] = None, vault: Optional[str] = None) -> str:
        file = self._safe_path(path)
        lines = self._read_lines(file)
        task_line = f"- [ ] {task_text}"
        if due:
            task_line += f" ⏰ {due}"
        if tags:
            tag_str = " " + " ".join(f"#{t}" for t in tags)
            task_line += tag_str
        if lines and lines[-1] != "":
            lines.append("")
        lines.append(task_line)
        self._write_lines(file, lines)
        return f"{path}::task::{task_text}"

    def task_toggle(self, path: str, task_state: str, task_text: Optional[str] = None,
                    vault: Optional[str] = None) -> str:
        """
        Toggles the first matching task line by text. If task_text is not provided,
        raises an error (to avoid toggling the wrong line).
        """
        if not task_text:
            raise ValueError("task_text is required for task.toggle in filesystem adapter")

        file = self._safe_path(path)
        lines = self._read_lines(file)
        if not lines:
            raise ValueError("file not found or empty")

        target_open = f"- [ ] {task_text}"
        target_done = f"- [x] {task_text}"

        changed = False
        for i, line in enumerate(lines):
            if line.strip() == target_open and task_state == "done":
                lines[i] = target_done
                changed = True
                break
            if line.strip() == target_done and task_state == "open":
                lines[i] = target_open
                changed = True
                break
        if not changed:
            raise ValueError("matching task not found to toggle")

        self._write_lines(file, lines)
        return f"{path}::task::{task_text}::{task_state}"

    # -------- helpers for headings --------
    @staticmethod
    def _normalize_heading(h: str) -> str:
        return h.strip().lstrip("#").strip().lower()

    def _find_heading_index(self, lines: list[str], heading: str) -> Optional[int]:
        target = self._normalize_heading(heading)
        for i, line in enumerate(lines):
            if line.lstrip().startswith("#"):
                if self._normalize_heading(line) == target:
                    return i
        return None

    def _scan_to_section_end(self, lines: list[str], heading_idx: int) -> int:
        """Given the index of a heading line, find where that section ends (next heading or EOF)."""
        base_level = len(lines[heading_idx]) - len(lines[heading_idx].lstrip("#"))
        j = heading_idx + 1
        while j < len(lines):
            if lines[j].lstrip().startswith("#"):
                lvl = len(lines[j]) - len(lines[j].lstrip("#"))
                if lvl <= base_level:
                    break
            j += 1
        # Ensure there's a blank line after the heading before inserting
        if j == heading_idx + 1 or (j < len(lines) and lines[j-1].strip() != ""):
            lines.insert(j, "")
            j += 1
        return j