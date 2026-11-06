import json
import queue
import sys
import time
from datetime import datetime

import paho.mqtt.client as mqtt
import xmpp

from config import (DEFAULT_CONTACT, MQTT_HOST, MQTT_PORT, TOPIC_COMMAND,
                    TOPIC_MESSAGES, TOPIC_STATE, XMPP_JID, XMPP_PASSWORD,
                    XMPP_PORT, XMPP_SERVER, log)
from llm import LLMAssistant

LAMP_NOTICES = {"ON": "💡 The lamp was turned ON.", "OFF": "🌑 The lamp was turned OFF."}


class LampBot:
    def __init__(self):
        self.jid = xmpp.JID(XMPP_JID)
        self.client = None
        self.llm = LLMAssistant()
        self.lamp_state = "unknown"
        self.last_contact = DEFAULT_CONTACT
        self.outbox = queue.Queue()
        self.mqtt = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="lampbot")

    def connect_xmpp(self):
        self.client = xmpp.Client(self.jid.getDomain(), debug=[])
        log("XMPP", f"connecting to {XMPP_SERVER}:{XMPP_PORT}")
        connection_type = self.client.connect(server=(XMPP_SERVER, XMPP_PORT))
        if not connection_type:
            sys.exit("Could not connect to the XMPP server.")

        if connection_type == "tls":
            tls_sock = self.client.Connection._sslObj
            log("TLS", f"{tls_sock.version()} / {tls_sock.cipher()[0]}")
        else:
            log("TLS", f"WARNING: connection without TLS ({connection_type})")

        if not self.client.auth(self.jid.getNode(), XMPP_PASSWORD, resource="lampbot"):
            sys.exit("SASL authentication failed: check XMPP_JID and XMPP_PASSWORD.")
        log("XMPP", f"authenticated as {self.jid}")

        self.client.RegisterHandler("message", self.on_message)
        self.client.RegisterHandler("presence", self.on_presence)
        self.client.sendInitPresence()

    def on_presence(self, _connection, presence):
        if presence.getType() == "subscribe":
            sender = presence.getFrom()
            self.client.send(xmpp.Presence(to=sender, typ="subscribed"))
            self.client.send(xmpp.Presence(to=sender, typ="subscribe"))
            log("XMPP", f"contact request accepted: {sender}")

    def on_message(self, _connection, message):
        text = message.getBody()
        if not text or message.getType() == "error":
            return
        sender = message.getFrom().getStripped()
        self.last_contact = sender
        log("XMPP <-", f"{sender}: {text}")

        self.publish(TOPIC_MESSAGES, json.dumps({
            "from": sender,
            "text": text,
            "time": datetime.now().isoformat(timespec="seconds"),
        }, ensure_ascii=False))

        if text.strip().lower() == "/state":
            self.send(sender, f"The lamp is {self.lamp_state}.")
            return

        reply, action = self.llm.reply(sender, text, self.lamp_state)
        log("LLM", f"action={action} reply={reply!r}")
        if action == "turn_on":
            self.publish(TOPIC_COMMAND, "ON", qos=1)
        elif action == "turn_off":
            self.publish(TOPIC_COMMAND, "OFF", qos=1)
        self.send(sender, reply)

    def send(self, to, text):
        self.client.send(xmpp.Message(to, text, typ="chat"))
        log("XMPP ->", f"{to}: {text}")

    def connect_mqtt(self):
        self.mqtt.on_connect = self.on_mqtt_connect
        self.mqtt.on_message = self.on_mqtt_message
        self.mqtt.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        self.mqtt.loop_start()

    def on_mqtt_connect(self, client, _userdata, _flags, reason_code, _props):
        log("MQTT", f"connected to {MQTT_HOST}:{MQTT_PORT} ({reason_code})")
        client.subscribe(TOPIC_STATE)

    def on_mqtt_message(self, _client, _userdata, msg):
        new_state = msg.payload.decode().upper()
        log("MQTT <-", f"{msg.topic} = {new_state}")
        if new_state == self.lamp_state:
            return
        first_reading = self.lamp_state == "unknown"
        self.lamp_state = new_state
        if not first_reading and new_state in LAMP_NOTICES:
            self.outbox.put((self.last_contact, LAMP_NOTICES[new_state]))

    def publish(self, topic, payload, qos=0):
        self.mqtt.publish(topic, payload, qos=qos)
        log("MQTT ->", f"{topic} = {payload}")

    def run(self):
        self.connect_mqtt()
        self.connect_xmpp()
        log("BOT", f"ready, chat with {self.jid}")
        try:
            while True:
                if self.client.Process(0.5) is None:
                    log("XMPP", "connection lost, reconnecting")
                    time.sleep(2)
                    self.connect_xmpp()
                while not self.outbox.empty():
                    self.send(*self.outbox.get())
        except KeyboardInterrupt:
            log("BOT", "shutting down")
        finally:
            self.mqtt.loop_stop()
            self.mqtt.disconnect()


if __name__ == "__main__":
    LampBot().run()
