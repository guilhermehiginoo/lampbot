import unittest

from llm import LLMAssistant


class ParseTest(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(
            LLMAssistant._parse('{"reply": "Done!", "action": "turn_on"}'),
            ("Done!", "turn_on"),
        )

    def test_json_inside_markdown_fence(self):
        content = '```json\n{"reply": "Off now.", "action": "turn_off"}\n```'
        self.assertEqual(LLMAssistant._parse(content), ("Off now.", "turn_off"))

    def test_unknown_action_becomes_none(self):
        self.assertEqual(
            LLMAssistant._parse('{"reply": "Hi", "action": "explode"}'),
            ("Hi", "none"),
        )

    def test_non_json_answer_is_used_as_reply(self):
        self.assertEqual(LLMAssistant._parse("just text"), ("just text", "none"))


class FallbackTest(unittest.TestCase):
    def test_keywords(self):
        self.assertEqual(LLMAssistant._without_llm("turn it on", "x")[1], "turn_on")
        self.assertEqual(LLMAssistant._without_llm("switch off please", "x")[1], "turn_off")
        self.assertEqual(LLMAssistant._without_llm("hello", "x")[1], "none")


if __name__ == "__main__":
    unittest.main()
