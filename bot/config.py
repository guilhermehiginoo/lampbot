import os
from datetime import datetime


def load_env(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

XMPP_JID = os.getenv("XMPP_JID", "bot@localhost")
XMPP_PASSWORD = os.getenv("XMPP_PASSWORD", "bot123")
XMPP_SERVER = os.getenv("XMPP_SERVER", "localhost")
XMPP_PORT = int(os.getenv("XMPP_PORT", "5222"))
DEFAULT_CONTACT = os.getenv("DEFAULT_CONTACT", "student@localhost")

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
TOPIC_MESSAGES = "iot/chat/messages"
TOPIC_COMMAND = "iot/lamp/command"
TOPIC_STATE = "iot/lamp/state"

LLM_URL = os.getenv("LLM_URL", "https://api.openai.com/v1/chat/completions")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")


def log(source, text):
    print(f"[{datetime.now():%H:%M:%S}] [{source}] {text}", flush=True)
