# Skills index

Each entry is a skill the agent can use. When a task matches, read the named
file with `read_file` to load the full instructions before acting.

| Skill | File | Use when |
|-------|------|----------|
| git-helper | `skills/git-helper/SKILL.md` | The user wants to stage, commit, branch, or inspect a git repository. |

## Adding a skill

1. Create `skills/<name>/SKILL.md` with the full instructions.
2. Add a row to the table above (name, file path, and when to use it).

The agent sees only this index by default and loads a skill's full file on
demand — so the skill set can grow without bloating every request.
