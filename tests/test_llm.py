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


class CachedInput(unittest.TestCase):
    """OpenAI bills cached input at its own price (11/20), and a recorded call is priced again from its usage report."""
    USAGE = {"prompt_tokens": 2000, "completion_tokens": 500, "total_tokens": 2500,
             "prompt_tokens_details": {"cached_tokens": 1500}}

    def test_cached_input_costs_its_multiple(self):
        full = llm.openai_cost(self.USAGE, 0.1, 0.5)
        cheap = llm.openai_cost(self.USAGE, 0.1, 0.5, 0.1)
        self.assertAlmostEqual(full, (2000 * 0.1 + 500 * 0.5) / 1e6)
        self.assertAlmostEqual(cheap, (500 * 0.1 + 1500 * 0.01 + 500 * 0.5) / 1e6)

    def test_a_recorded_call_is_priced_again_and_a_claude_call_keeps_its_cost(self):
        meta = {"cost_usd": 1.0, "usage": self.USAGE}
        luna = {"via": "openai", "price_in": 0.1, "price_out": 0.5, "cached_mult": 0.1}
        self.assertAlmostEqual(llm.repriced(meta, luna)["cost_usd"], llm.openai_cost(self.USAGE, 0.1, 0.5, 0.1))
        self.assertEqual(meta["cost_usd"], 1.0, "the recording itself stays as it was")
        cli = {"cost_usd": 0.05, "usage": {"input_tokens": 3, "output_tokens": 9}}
        self.assertEqual(llm.repriced(cli, {"via": "claude-cli"})["cost_usd"], 0.05)
