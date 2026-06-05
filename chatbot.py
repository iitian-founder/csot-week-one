#!/usr/bin/env python3
"""A terminal AI agent built on Claude.

Capabilities:
  - Multi-turn conversation (full history kept and resent each turn).
  - Tools: run shell/CLI commands and read files (executed locally).
  - MCP: connect to remote MCP servers listed in mcp.config.
  - Persona/instructions loaded from agent.md.
  - Skills: an index from skills.md, with full skill files loaded on demand.

The API key is read from the environment (via .env). It never appears in this
source file. See .env.example.
"""

import json
import os
import subprocess
import sys

import anthropic
from dotenv import load_dotenv

# Load ANTHROPIC_API_KEY (and any MCP token vars) from .env into the environment.
# The secret still lives only in the environment / .env (gitignored).
load_dotenv()

MODEL = "claude-opus-4-8"
MAX_TOKENS = 128000
MCP_BETA = "mcp-client-2025-11-20"

HERE = os.path.dirname(os.path.abspath(__file__))


# --------------------------------------------------------------------------- #
# Configuration loading: agent.md, skills.md, mcp.config
# --------------------------------------------------------------------------- #

def _read_if_exists(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def build_system_prompt() -> str:
    """System prompt = agent.md persona + the skills index from skills.md."""
    parts = []
    agent = _read_if_exists(os.path.join(HERE, "agent.md")).strip()
    parts.append(agent or "You are a helpful terminal agent.")

    skills = _read_if_exists(os.path.join(HERE, "skills.md")).strip()
    if skills:
        parts.append(
            "# Available skills\n"
            "Each skill below names a file. When a task matches a skill, read "
            "that file with the read_file tool before proceeding.\n\n" + skills
        )
    return "\n\n".join(parts)


def load_mcp_servers() -> list[dict]:
    """Read mcp.config and return API-ready MCP server entries.

    Auth tokens are never stored in the file — each server may name an env var
    via "authorization_token_env", which is resolved here at runtime.
    """
    raw = _read_if_exists(os.path.join(HERE, "mcp.config"))
    if not raw.strip():
        return []
    try:
        config = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"[mcp.config is not valid JSON: {exc}]", file=sys.stderr)
        return []

    servers = []
    for entry in config.get("mcp_servers", []):
        if not entry.get("enabled", True):
            continue
        server = {"type": "url", "name": entry["name"], "url": entry["url"]}
        token_env = entry.get("authorization_token_env")
        if token_env:
            token = os.environ.get(token_env)
            if token:
                server["authorization_token"] = token
            else:
                print(f"[MCP server '{entry['name']}': {token_env} not set, "
                      "connecting without auth]", file=sys.stderr)
        servers.append(server)
    return servers


# --------------------------------------------------------------------------- #
# Local tools
# --------------------------------------------------------------------------- #

TOOLS = [
    {
        "name": "run_command",
        "description": (
            "Run a shell/CLI command on the user's machine and return its "
            "stdout and stderr. Use for git, ls, building, running scripts, "
            "etc. The user is asked to approve each command before it runs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The command to run"}
            },
            "required": ["command"],
        },
    },
    {
        "name": "read_file",
        "description": (
            "Read a UTF-8 text file from disk and return its contents. Use this "
            "to load source files, skill files (skills/<name>/SKILL.md), or any "
            "other text the task needs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file"}
            },
            "required": ["path"],
        },
    },
]

MAX_FILE_BYTES = 100_000
COMMAND_TIMEOUT = 60


def tool_run_command(command: str) -> tuple[str, bool]:
    """Execute a command after asking the user to approve it."""
    print(f"\n  ┌─ Claude wants to run:\n  │   {command}\n  └─ Approve? [y/N] ",
          end="", flush=True)
    try:
        answer = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = "n"
    if answer not in ("y", "yes"):
        return "Command was declined by the user.", True

    try:
        proc = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=COMMAND_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return f"Command timed out after {COMMAND_TIMEOUT}s.", True

    out = (proc.stdout or "") + (proc.stderr or "")
    out = out.strip() or "(no output)"
    return f"exit code: {proc.returncode}\n{out}", proc.returncode != 0


def tool_read_file(path: str) -> tuple[str, bool]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = f.read(MAX_FILE_BYTES + 1)
    except FileNotFoundError:
        return f"File not found: {path}", True
    except (IsADirectoryError, PermissionError, UnicodeDecodeError) as exc:
        return f"Could not read {path}: {exc}", True
    if len(data) > MAX_FILE_BYTES:
        data = data[:MAX_FILE_BYTES] + "\n... [truncated]"
    return data, False


def execute_tool(name: str, tool_input: dict) -> tuple[str, bool]:
    """Dispatch a tool call. Returns (result_text, is_error)."""
    if name == "run_command":
        return tool_run_command(tool_input.get("command", ""))
    if name == "read_file":
        return tool_read_file(tool_input.get("path", ""))
    return f"Unknown tool: {name}", True


# --------------------------------------------------------------------------- #
# Agentic loop
# --------------------------------------------------------------------------- #

def respond(client, messages, system, mcp_servers) -> None:
    """Run one user turn to completion, handling tool use and MCP pauses."""
    use_beta = bool(mcp_servers)

    while True:
        kwargs = dict(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            tools=TOOLS,
            messages=messages,
        )
        if use_beta:
            kwargs["betas"] = [MCP_BETA]
            kwargs["mcp_servers"] = mcp_servers
            stream_ctx = client.beta.messages.stream(**kwargs)
        else:
            stream_ctx = client.messages.stream(**kwargs)

        print("Claude: ", end="", flush=True)
        with stream_ctx as stream:
            for text in stream.text_stream:
                print(text, end="", flush=True)
            final = stream.get_final_message()
        print()

        # Preserve the full assistant turn (text + tool_use blocks) in history.
        messages.append({"role": "assistant", "content": final.content})

        if final.stop_reason == "pause_turn":
            # Server-side tool (e.g. MCP) hit its iteration cap — resume.
            continue

        if final.stop_reason != "tool_use":
            return  # end_turn / max_tokens / etc.

        # Execute each local tool call and feed the results back.
        tool_results = []
        for block in final.content:
            if block.type == "tool_use":
                result, is_error = execute_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                    "is_error": is_error,
                })
        messages.append({"role": "user", "content": tool_results})


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit('ANTHROPIC_API_KEY is not set.\n'
                 'Set it in .env:  cp .env.example .env  then edit .env')

    client = anthropic.Anthropic()
    system = build_system_prompt()
    mcp_servers = load_mcp_servers()
    messages: list[dict] = []

    print("Claude terminal agent.  Tools: run_command, read_file.")
    if mcp_servers:
        print("MCP servers: " + ", ".join(s["name"] for s in mcp_servers))
    print("Commands: /reset clears the conversation, /exit quits.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input in ("/exit", "/quit"):
            print("Goodbye!")
            break
        if user_input == "/reset":
            messages.clear()
            print("(conversation cleared)\n")
            continue

        messages.append({"role": "user", "content": user_input})
        try:
            respond(client, messages, system, mcp_servers)
        except anthropic.APIError as exc:
            print(f"\n[API error: {exc}]\n")
            # Roll back to the last clean user turn so history stays valid.
            while messages and messages[-1]["role"] != "user":
                messages.pop()
            if messages:
                messages.pop()
            continue
        print()


if __name__ == "__main__":
    main()
