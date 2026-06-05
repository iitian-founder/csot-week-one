#!/usr/bin/env python3
"""A terminal chatbot that holds a coherent multi-turn conversation with Claude.

The API key is read from the ANTHROPIC_API_KEY environment variable by the
Anthropic SDK — it never appears in this source file. Set it before running:

    export ANTHROPIC_API_KEY="sk-ant-..."
    python3 chatbot.py
"""

import os
import sys

import anthropic
from dotenv import load_dotenv

# Load ANTHROPIC_API_KEY from a local .env file into the environment, if present.
# The key still lives only in the environment / .env (which is gitignored) —
# never in this source file.
load_dotenv()

MODEL = "claude-opus-4-8"
MAX_TOKENS = 128000
SYSTEM_PROMPT = "You are a concise, helpful assistant chatting in a terminal."


def main() -> None:
    # The key comes from the environment, never from this source file. The SDK
    # reads ANTHROPIC_API_KEY itself, but it only errors at request time — check
    # up front so a missing key produces a clear message instead of a traceback.
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set.\n"
                 'Set it in your environment first:  export ANTHROPIC_API_KEY="sk-ant-..."')

    client = anthropic.Anthropic()

    # The Messages API is stateless, so we keep the full history ourselves and
    # resend it each turn. That's what makes the conversation coherent.
    messages: list[dict] = []

    print("Claude terminal chat. Type your message and press Enter.")
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

        # Stream the response so tokens appear as they're generated.
        print("Claude: ", end="", flush=True)
        try:
            with client.messages.stream(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    print(text, end="", flush=True)
                final = stream.get_final_message()
        except anthropic.APIError as exc:
            print(f"\n[API error: {exc}]\n")
            # Drop the user turn we couldn't answer so history stays valid.
            messages.pop()
            continue

        print("\n")

        # Append Claude's reply so the next turn has full context.
        assistant_text = "".join(
            block.text for block in final.content if block.type == "text"
        )
        messages.append({"role": "assistant", "content": assistant_text})


if __name__ == "__main__":
    main()
