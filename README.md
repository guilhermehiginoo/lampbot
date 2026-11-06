# lampbot

Chat with an LLM agent that controls a smart lamp. You talk to the bot over **XMPP**, the **LLM** decides what to do, and the action reaches the device over **MQTT**.

```
 browser :8080 ── chat (XMPP/WebSocket) ──► Ejabberd ◄── XMPP + TLS ──┐
        ▲                                                             bot ── HTTPS ──► LLM
        └────── lamp (MQTT/WebSocket) ──► Mosquitto ◄──── MQTT ───────┘
```

## Run it

Requires only Docker.

```bash
cp .env.example .env
docker compose up --build
```

Open **http://localhost:8080** and say something like *"it's way too dark in here"*.

Put an API key in `.env` to use a real LLM. Without one the bot still runs, using keyword rules.

## How it works

1. A message arrives at the bot over XMPP.
2. The bot sends the conversation and the **current lamp state** to the LLM.
3. The LLM answers with JSON: `{"reply": "...", "action": "turn_on" | "turn_off" | "none"}`.
4. The bot publishes the action on MQTT and replies in the chat.
5. The lamp publishes its new state. If someone flips it on the panel, the bot tells the user.

Implementation notes:

- **Structured output, defensively parsed.** The answer is extracted even when wrapped in a markdown fence, and any unknown action becomes `none`, so the model can never trigger something unexpected.
- **State-aware prompt.** The model sees the lamp state, so "turn it on" with the lamp already on gets a "it's already on" instead of a redundant command. The state is repeated at the end of the context because smaller models tend to ignore it at the top.
- **Graceful degradation.** If the LLM is unreachable or unconfigured, a keyword fallback keeps the device controllable.
- **Per-user memory.** Each contact keeps its last 10 messages.
- **Provider-agnostic.** Any OpenAI-compatible `chat/completions` endpoint works (see below), with no SDK, only the standard library.

## LLM providers

| Provider | `LLM_URL` | `LLM_MODEL` |
|---|---|---|
| OpenAI | `https://api.openai.com/v1/chat/completions` | `gpt-4o-mini` |
| Google Gemini (free tier) | `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions` | `gemini-2.5-flash` |
| Groq | `https://api.groq.com/openai/v1/chat/completions` | `llama-3.3-70b-versatile` |
| Ollama (local, no key) | `http://host.docker.internal:11434/v1/chat/completions` | `llama3.2` |

## Services

| Service | Port | Role |
|---|---|---|
| `panel` | 8080 | Web UI: XMPP chat + MQTT lamp |
| `ejabberd` | 5222, 5280 | XMPP server. STARTTLS required on 5222 (TLS ≥ 1.2, SCRAM). WebSocket and admin on 5280 |
| `mosquitto` | 1883, 9001 | MQTT broker (TCP and WebSocket) |
| `bot` | – | Python agent (xmpppy + paho-mqtt) |
| `certs` | – | Generates the self-signed TLS certificate on first run |

Accounts are created automatically:

| Account | Password |
|---|---|
| `student@localhost` | `student123` |
| `bot@localhost` | `bot123` |
| `admin@localhost` | `admin123` (http://localhost:5280/admin) |

## MQTT topics

| Topic | Published by | Payload |
|---|---|---|
| `iot/chat/messages` | bot | `{"from", "text", "time"}` for every message |
| `iot/lamp/command` | bot | `ON` / `OFF` |
| `iot/lamp/state` | lamp | `ON` / `OFF` (retained) |

```bash
docker compose exec mosquitto mosquitto_sub -v -t "iot/#"
```

## TLS

The bot and native clients connect on port 5222, where the server refuses anything that is not encrypted. The bot logs the negotiated protocol on startup (`[TLS] TLSv1.3 / TLS_AES_256_GCM_SHA384`). To check from outside:

```bash
openssl s_client -connect localhost:5222 -starttls xmpp -xmpphost localhost </dev/null | grep -E "Protocol|Cipher"
```

The browser chat uses plain WebSocket on port 5280 to avoid certificate warnings on localhost.

## Using Pidgin

Add an XMPP account with username `student`, domain `localhost`, password `student123`, and set *Connection security* to *Require encryption*. Accept the self-signed certificate. The bot is already in the contact list.

## Development

```bash
cd bot
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest
```

To run the bot outside Docker, stop its container (`docker compose stop bot`) and run `.venv/bin/python main.py`.

## License

[GPL-3.0](LICENSE) © Guilherme Higino. You may use, modify and share this project, as long as you credit the author and release derived works under the same license.
