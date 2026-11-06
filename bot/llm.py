import json
import re
import urllib.error
import urllib.request

from config import LLM_API_KEY, LLM_MODEL, LLM_URL, log

SYSTEM_PROMPT = """
You are "lampbot", an assistant that chats over XMPP and controls a smart lamp.

## Lamp
- Current state: {state}
- The action you return is executed IMMEDIATELY, before the user reads your reply.

## Choosing the action
1. Check the current state FIRST. If the lamp is already in the requested state,
   the action is "none" (asking to turn on a lamp that is ON -> "none").
2. "turn_on" / "turn_off": only when the user asks for a change, directly or
   indirectly (e.g. "it's dark in here" with the lamp OFF -> "turn_on").
3. "none": for any other conversation.

## Writing the reply
- English only, short and friendly, 3 sentences at most. Vary the wording.
- Action "turn_on" / "turn_off": confirm it is already DONE, in the past tense.
  Never offer, ask or promise to do it ("I can turn it on" is wrong).
- Already in the requested state: tell the user it was already on/off.
- Action "none": never claim you changed the lamp.

## Output
Return ONLY valid JSON, with no text outside it:
{{"reply": "<text for the user>", "action": "turn_on" | "turn_off" | "none"}}
""".strip()


class LLMAssistant:
    def __init__(self):
        self.histories = {}

    def reply(self, user, text, lamp_state):
        if not LLM_API_KEY and "localhost:11434" not in LLM_URL:
            return self._without_llm(text, "the LLM is not configured (set LLM_API_KEY in .env)")

        history = self.histories.setdefault(user, [])
        history.append({"role": "user", "content": text})
        del history[:-10]

        messages = [{"role": "system",
                     "content": SYSTEM_PROMPT.format(state=lamp_state)}]
        messages += history
        messages.append({"role": "system",
                         "content": f"Reminder: the lamp is {lamp_state} right now. Reply in English."})

        body = json.dumps({
            "model": LLM_MODEL,
            "messages": messages,
            "temperature": 0.4,
        }).encode("utf-8")
        request = urllib.request.Request(
            LLM_URL,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {LLM_API_KEY}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.load(response)
            content = data["choices"][0]["message"]["content"]
        except (urllib.error.URLError, KeyError, IndexError, TimeoutError) as error:
            log("LLM", f"failed to query the LLM: {error}")
            history.pop()
            return self._without_llm(text, "I couldn't reach the LLM right now")

        history.append({"role": "assistant", "content": content})
        return self._parse(content)

    @staticmethod
    def _parse(content):
        snippet = re.search(r"\{.*\}", content, re.DOTALL)
        try:
            data = json.loads(snippet.group(0)) if snippet else {}
        except json.JSONDecodeError:
            data = {}
        reply = data.get("reply") or content.strip()
        action = data.get("action", "none")
        if action not in ("turn_on", "turn_off"):
            action = "none"
        return reply, action

    @staticmethod
    def _without_llm(text, reason):
        text = text.lower()
        if re.search(r"\b(off|disable)\b", text):
            return "Ok, turning the lamp off. (no-LLM mode)", "turn_off"
        if re.search(r"\b(on|enable)\b", text):
            return "Ok, turning the lamp on. (no-LLM mode)", "turn_on"
        return f"I got your message, but {reason}.", "none"
