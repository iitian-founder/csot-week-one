# Terminal AI Agent

A command-line agent built on Claude. It holds a coherent multi-turn
conversation **and** can use tools: run CLI commands, read files, and call
remote MCP servers. The API key is loaded from the environment and never touches
the source.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp .env.example .env          # then edit .env and paste in your real key
```

Your key lives in `.env`, which is gitignored and never committed. `.env.example`
is the placeholder template that is safe to share.

## Run

```bash
.venv/bin/python chatbot.py
```

## Usage

- Type a message and press Enter.
- The agent remembers the whole conversation, so follow-ups work.
- `/reset` clears the conversation history.
- `/exit` (or `/quit`, or Ctrl-D) quits.

## Capabilities

### Tools

- **`run_command`** — runs a shell/CLI command. Every command is shown to you
  for **approval (`[y/N]`)** before it runs.
- **`read_file`** — reads a text file from disk.

The agent runs a tool-use loop: it calls a tool, you approve/return the result,
and it continues until the task is done.

### MCP servers — `mcp.config`

Connect the agent to remote MCP servers. Each entry:

```json
{
  "mcp_servers": [
    {
      "enabled": true,
      "name": "my-server",
      "url": "https://my-mcp-server.example.com/mcp",
      "authorization_token_env": "MY_MCP_TOKEN"
    }
  ]
}
```

Tokens are **never stored in the file** — `authorization_token_env` names an
environment variable (set it in `.env`), which is resolved at runtime. Set
`"enabled": false` to keep a server defined but inactive. The shipped config has
one disabled example.

### Persona — `agent.md`

`agent.md` is loaded as the system prompt. Edit it to change the agent's
behavior, rules, and working style.

### Skills — `skills.md` + `skills/`

- `skills.md` is an index (name → file → when to use) injected into context.
- Each skill is a folder: `skills/<name>/SKILL.md` with the full instructions.
- The agent sees only the index by default and loads a skill's full file **on
  demand** via `read_file` (progressive disclosure), so the skill set can grow
  without bloating every request.

To add a skill: create `skills/<name>/SKILL.md` and add a row to `skills.md`.
A `git-helper` skill ships as an example.

## How it works

The Messages API is stateless, so `chatbot.py` keeps the full message history in
memory and resends it each turn — including tool calls and results — which is
what makes the conversation coherent. Responses stream token-by-token. At
startup `load_dotenv()` reads `.env` into the environment, then
`anthropic.Anthropic()` picks up `ANTHROPIC_API_KEY` from there, keeping the
secret out of the codebase entirely.
