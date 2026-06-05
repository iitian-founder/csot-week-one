# Skill: git-helper

Help the user with common git tasks safely.

## Workflow

1. Start by understanding the current state — run `git status` and, when
   relevant, `git log --oneline -10` and `git branch --show-current`.
2. Summarize what you see in one or two lines before changing anything.
3. For commits:
   - Stage intentionally (`git add <paths>`), not blindly with `git add -A`,
     unless the user asked for everything.
   - Write a clear, conventional commit message (a short imperative subject,
     optionally a body explaining why).
4. Never run destructive or history-rewriting commands — `git reset --hard`,
   `git push --force`, `git clean -fd`, branch deletion — without first
   explaining exactly what will be lost and getting the user's confirmation.

## Notes

- Prefer read-only inspection commands when exploring.
- If the working tree is dirty in a way the user didn't expect, stop and point
  it out instead of proceeding.
