# Terminal Chatbot

A command-line chatbot that holds a coherent multi-turn conversation with
Claude. The API key is loaded from the environment and never touches the source.

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

- Type a message and press Enter to chat.
- The bot remembers the whole conversation, so follow-up questions work.
- `/reset` clears the conversation history.
- `/exit` (or `/quit`, or Ctrl-D) quits.

## How it works

The Anthropic Messages API is stateless, so `chatbot.py` keeps the full message
history in memory and resends it on every turn — that's what makes the
conversation coherent across turns. Responses are streamed token-by-token.
At startup `load_dotenv()` reads `.env` into the environment, then
`anthropic.Anthropic()` picks up `ANTHROPIC_API_KEY` from there — keeping the
secret out of the codebase entirely.
