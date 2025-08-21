from __future__ import annotations
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, root_validator, validator
import re

MD_PATH_RE = re.compile(r"\.md$", re.IGNORECASE)

class Action(str, Enum):
    note_create = "note.create"
    note_append = "note.append"
    note_update = "note.update"
    task_create = "task.create"
    task_toggle = "task.toggle"

class Position(str, Enum):
    top = "top"
    bottom = "bottom"
    after_heading = "after_heading"

class TaskState(str, Enum):
    open = "open"
    done = "done"

class Meta(BaseModel):
    idempotency_key: Optional[str] = Field(None, min_length=8, max_length=200)
    trace_id: Optional[str] = Field(None, min_length=8, max_length=200)

class Payload(BaseModel):
    vault: Optional[str]
    path: Optional[str]
    heading: Optional[str]
    position: Optional[Position] = Position.bottom
    title: Optional[str]
    body_md: Optional[str]
    task_text: Optional[str]
    task_state: Optional[TaskState]
    due: Optional[str]  # ISO 8601; normalization handled later
    tags: Optional[List[str]] = None
    meta: Optional[Meta] = None

    @validator("path")
    def path_must_be_md(cls, v):
        if v and not MD_PATH_RE.search(v):
            raise ValueError("path must end with .md")
        return v

    @validator("tags")
    def tags_unique_nonempty(cls, v):
        if v is None:
            return v
        if len(v) != len(set(v)):
            raise ValueError("tags must be unique")
        if any(not t or not t.strip() for t in v):
            raise ValueError("tags cannot contain empty strings")
        return [t.strip() for t in v]

class ObsidianCommand(BaseModel):
    type: str = Field("obsidian.command", const=True)
    action: Action
    payload: Payload

    @root_validator
    def enforce_action_requirements(cls, values):
        action: Action = values.get("action")
        p: Payload = values.get("payload")
        missing = []

        def require(field: str):
            if getattr(p, field) in (None, "", []):
                missing.append(field)

        # Common: all actions require a target file path
        if action in {
            Action.note_create, Action.note_append,
            Action.note_update, Action.task_create, Action.task_toggle
        }:
            require("path")

        # Per-action requirements
        if action == Action.note_create:
            require("title"); require("body_md")
        elif action == Action.note_append:
            require("body_md")
            if p.position == Position.after_heading:
                require("heading")
        elif action == Action.note_update:
            require("body_md")
        elif action == Action.task_create:
            require("task_text")
        elif action == Action.task_toggle:
            require("task_state")

        if missing:
            raise ValueError(f"missing required fields for {action}: {', '.join(missing)}")
        return values