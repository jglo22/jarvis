from pydantic import ValidationError
from core.types import ObsidianCommand

ok = ObsidianCommand(
    action="note.append",
    payload={
        "path":"Daily/2025-08-21.md",
        "position":"after_heading",
        "heading":"Standup",
        "body_md":"- [ ] Review PR #214",
        "meta":{"idempotency_key":"day-2025-08-21-standup-pr214"}
    }
)
print("Valid ✓", ok.dict()["action"])

try:
    bad = ObsidianCommand(action="task.toggle", payload={"path":"Projects/Alpha.md"})
except ValidationError as e:
    print("Expected error →", e.errors()[0]["msg"])