"""The OpenAI-compatible backend sends the thinking setting only when the config asks for it."""
import json
import unittest

from agents import llm


def reply(content, reasoning=None, completion=3):
    message = {"role": "assistant", "content": content}
    if reasoning is not None:
        message["reasoning"] = reasoning
    return json.dumps({"model": "m", "choices": [{"message": message, "finish_reason": "stop"}],
                       "usage": {"prompt_tokens": 10, "completion_tokens": completion, "total_tokens": 10 + completion}
                       }).encode()


class Local(unittest.TestCase):
    def test_thinking_off_goes_out_and_comes_back_in_meta(self):
        sent = []

        def transport(url, headers, body, timeout):
            sent.append((json.loads(body), timeout))
            return 200, reply("yes")

        entry = {"id": "local", "via": "openai", "base_url": "http://localhost:11434/v1", "model": "q",
                 "reasoning_effort": "none", "max_tokens": 12000, "timeout": 1800}
        b = llm.backend_for(entry, lambda s: "")
        b.transport = transport
        text, meta = b("system", "user")
        body, timeout = sent[0]
        self.assertEqual((body["reasoning_effort"], body["max_tokens"], timeout), ("none", 12000, 1800))
        self.assertEqual((text, meta["reasoning_effort"], meta["reasoning_chars"]), ("yes", "none", 0))

    def test_no_setting_sends_nothing(self):
        b = llm.OpenAICompatible("k", "m", "https://example.invalid/v1")
        body = json.loads(b.request("s", "u")[1])
        self.assertNotIn("reasoning_effort", body)

    def test_thinking_kept_apart_is_counted(self):
        text, meta = llm.parse_openai(reply("yes", reasoning="Let me think.", completion=9), 5)
        self.assertEqual((text, meta["reasoning_chars"]), ("yes", 13))


if __name__ == "__main__":
    unittest.main()
