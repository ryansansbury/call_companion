"""How an agent reaches a model. Every backend answers the same call, model(system, user) -> (text, meta):

- ClaudeCLI calls Claude through the Claude Code CLI (claude -p). It records the Claude runs.
- OpenAICompatible calls the Chat Completions protocol that OpenAI speaks, and that Google's Gemini and a local Ollama
  server accept at their own addresses. The local model runs through it with no key and with its thinking off, since
  reasoning_effort "none" tells Ollama not to think before answering.
- AnthropicAPI calls the Anthropic Messages API with an API key, as an alternative to the CLI.
- WithFallback tries the models of a route in turn and answers with the first one whose call succeeds.

Adapted from the Policy Reconciler's model layer, without its embeddings. They all sit behind the same prompts,
validation and single repair request in owner/record_ai_runs.py, so a model from any vendor faces the same checks.
The caller hands each API key in, since keys live in the macOS Keychain and never in the repo. The build calls none
of them. It replays what they recorded and validates each run again.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
API_MODELS = {"opus": "claude-opus-5-5", "sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-5-5"}
RETRY_STATUS = (429, 500, 502, 503, 504, 529)
MAX_TOKENS = 16000          # room for a long reply
TIMEOUT = 300
REASONING_MAX_TOKENS = 32000    # reasoning models count their hidden reasoning against the output budget
REASONING_TIMEOUT = 600         # and take longer
FLAGS = ("--model", "--output-format", "--system-prompt", "--max-turns", "--tools", "--disallowedTools",
         "--strict-mcp-config", "--no-session-persistence")
NO_TOOLS = "Bash Edit Write Read Glob Grep WebFetch WebSearch NotebookEdit Task TodoWrite"


# ---------------------------------------------------------------------- the Anthropic API
def urllib_transport(url, headers, body, timeout):
    """POST body to url. Returns (status, response bytes), with an HTTP error's status and body returned too."""
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def cost(tokens_in, tokens_out, price_in, price_out):
    """Dollars from token counts and list prices per million tokens, or None when a price or a count is missing."""
    if None in (tokens_in, tokens_out, price_in, price_out):
        return None
    return round(tokens_in * price_in / 1e6 + tokens_out * price_out / 1e6, 6)


class AnthropicAPI:
    """model(system, user) through the Messages API, with two retries on rate limits and server errors."""

    def __init__(self, key, model="opus", max_tokens=MAX_TOKENS, timeout=TIMEOUT, retries=2, transport=None,
                 sleep=time.sleep, price_in=None, price_out=None):
        if not key:
            raise ValueError("Live mode needs an Anthropic API key.")
        self.key, self.model = key, API_MODELS.get(model, model)
        self.max_tokens, self.timeout, self.retries = max_tokens, timeout, retries
        self.transport, self.sleep = transport or urllib_transport, sleep
        self.price_in, self.price_out = price_in, price_out

    def request(self, system, user):
        headers = {"x-api-key": self.key, "anthropic-version": API_VERSION, "content-type": "application/json"}
        body = {"model": self.model, "max_tokens": self.max_tokens, "system": system,
                "messages": [{"role": "user", "content": user}]}
        return headers, json.dumps(body).encode()

    def __call__(self, system, user):
        headers, body = self.request(system, user)
        t0 = time.time()
        for attempt in range(self.retries + 1):
            status, raw = self.transport(API_URL, headers, body, self.timeout)
            if status == 200:
                text, meta = parse_api(raw, (time.time() - t0) * 1000)
                meta["cost_usd"] = cost(meta["input_tokens"], meta["output_tokens"], self.price_in, self.price_out)
                return text, meta
            if status == 401:
                raise RuntimeError("The Anthropic API refused the key (401). Save it in the Keychain again with security "
                                   "add-generic-password -U -a \"$USER\" -s policy-reconciler-anthropic -w \"$(pbpaste)\" after copying the key")
            if status in RETRY_STATUS and attempt < self.retries:
                self.sleep(2 * 3 ** attempt)        # 2 seconds, then 6
                continue
            raise RuntimeError(f"The Anthropic API answered {status}: {error_text(raw)}")

    def described(self):
        return {"backend": "anthropic-api", "model": self.model}


def parse_api(raw, ms):
    """The reply's text and what the API reported about the call. The API doesn't report a price, so the caller works
    out the cost from the list prices it was given."""
    data = json.loads(raw)
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    usage = data.get("usage") or {}
    return text, {"ms": round(ms), "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
                  "cost_usd": None, "models": [data["model"]] if data.get("model") else [],
                  "stop_reason": data.get("stop_reason")}


# ---------------------------------------------------------------------- the OpenAI-compatible protocol
class OpenAICompatible:
    """model(system, user) through Chat Completions at any vendor's endpoint that speaks it. A reasoning model counts
    its hidden reasoning against the output budget, so the budget leaves room for the reply after it, and the wait
    is longer. A new key's rate limit gets four retries that back off up to 45 seconds. reasoning_effort goes out only
    when the config sets it, and each reply's meta repeats it."""

    def __init__(self, key, model, base_url, vendor="", label="", keychain="", token_param="max_tokens",
                 max_tokens=REASONING_MAX_TOKENS, timeout=REASONING_TIMEOUT, retries=4, transport=None, sleep=time.sleep,
                 price_in=None, price_out=None, notify=None, reasoning_effort=None):
        if not key:
            raise ValueError(f"{vendor or 'This vendor'} needs an API key in the Keychain under {keychain or 'its service'}.")
        if not model or not base_url:
            raise ValueError("An OpenAI-compatible model needs its model name and its endpoint.")
        self.key, self.model, self.url = key, model, base_url.rstrip("/") + "/chat/completions"
        self.vendor, self.label, self.keychain, self.token_param = vendor, label, keychain, token_param
        self.max_tokens, self.timeout, self.retries = max_tokens, timeout, retries
        self.transport, self.sleep = transport or urllib_transport, sleep
        self.price_in, self.price_out = price_in, price_out
        self.reasoning_effort = reasoning_effort
        self.notify = notify or (lambda line: print(line, file=sys.stderr, flush=True))

    def request(self, system, user):
        headers = {"authorization": f"Bearer {self.key}", "content-type": "application/json"}
        body = {"model": self.model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                self.token_param: self.max_tokens}
        if self.reasoning_effort:
            body["reasoning_effort"] = self.reasoning_effort
        return headers, json.dumps(body).encode()

    def __call__(self, system, user):
        headers, body = self.request(system, user)
        t0 = time.time()
        for attempt in range(self.retries + 1):
            status, raw = self.transport(self.url, headers, body, self.timeout)
            if status == 200:
                text, meta = parse_openai(raw, (time.time() - t0) * 1000, self.price_in, self.price_out)
                if self.reasoning_effort:
                    meta["reasoning_effort"] = self.reasoning_effort
                return text, meta
            if status in (401, 403):
                raise RuntimeError(f"{self.vendor or 'The vendor'} refused the key ({status}). Save it again with "
                                   f"security add-generic-password -U -a \"$USER\" -s {self.keychain} -w \"$(pbpaste)\" after copying the key")
            if status in RETRY_STATUS and attempt < self.retries:
                wait = min(2 * 3 ** attempt, 45)        # 2, 6, 18, then 45 seconds
                self.notify(f"    {self.label or self.model}: {self.vendor or 'the vendor'} answered {status} "
                            f"({error_text(raw)[:160]}). Trying again in {wait} s.")
                self.sleep(wait)
                continue
            raise RuntimeError(f"{self.vendor or 'The vendor'} answered {status}: {error_text(raw)}")

    def described(self):
        out = {"backend": "openai-compatible", "vendor": self.vendor, "model": self.model, "label": self.label}
        return dict(out, reasoning_effort=self.reasoning_effort) if self.reasoning_effort else out


def billed(usage):
    """(input, output) tokens the way the vendor bills them. OpenAI counts reasoning inside completion_tokens. Google's
    OpenAI-compatible endpoint leaves the model's thinking out of completion_tokens but counts it in total_tokens, and
    bills thinking as output, so the billed output is everything in the total beyond the prompt."""
    tokens_in, tokens_out, total = usage.get("prompt_tokens"), usage.get("completion_tokens"), usage.get("total_tokens")
    if None not in (tokens_in, tokens_out, total) and total > tokens_in + tokens_out:
        tokens_out = total - tokens_in
    return tokens_in, tokens_out


def parse_openai(raw, ms, price_in=None, price_out=None):
    """The reply's text, its tokens, and its cost at the given list prices. A model that thinks before it answers
    sends its thinking apart from the reply when the server separates them, as Ollama does, and reasoning_chars
    counts it. The thinking itself isn't kept."""
    data = json.loads(raw)
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = message.get("content") or ""
    thought = message.get("reasoning") or message.get("reasoning_content") or ""
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    usage = data.get("usage") or {}
    tokens_in, tokens_out = billed(usage)
    # The vendor's whole usage report is kept, so a cost can be audited where reasoning is counted apart from output.
    return content, {"ms": round(ms), "input_tokens": tokens_in, "output_tokens": tokens_out,
                     "cost_usd": cost(tokens_in, tokens_out, price_in, price_out), "usage": usage,
                     "models": [data["model"]] if data.get("model") else [], "stop_reason": choice.get("finish_reason"),
                     "reasoning_chars": len(thought) if isinstance(thought, str) else 0}


# ---------------------------------------------------------------------- one backend from config, and a route's fallback
def backend_for(entry, key_for):
    """The backend a config/models.json entry describes. key_for(service) returns that service's key from the
    Keychain. It's owner code, so this module never reads a key itself."""
    via = entry.get("via")
    prices = {"price_in": entry.get("price_in"), "price_out": entry.get("price_out")}
    if via == "claude-cli":
        return ClaudeCLI(entry["model"])
    if via == "anthropic":
        return AnthropicAPI(key_for(entry["keychain"]), entry["model"], **prices)
    if via == "openai":
        limits = {k: entry[k] for k in ("max_tokens", "timeout", "reasoning_effort") if entry.get(k)}
        key = key_for(entry["keychain"]) if entry.get("keychain") else "local"
        return OpenAICompatible(key, entry["model"], entry["base_url"], vendor=entry.get("vendor", ""),
                                label=entry.get("label", ""), keychain=entry.get("keychain", ""),
                                token_param=entry.get("token_param", "max_tokens"), **prices, **limits)
    raise ValueError(f"{entry.get('id')} names an unknown way to reach its model: {via}")


class WithFallback:
    """A route's models in order. The first whose call succeeds answers, and its meta says which one it was and which
    failed before it. A reply that fails validation isn't a failed call. It gets the usual repair request instead."""

    def __init__(self, backends):
        if not backends:
            raise ValueError("A route needs at least one model.")
        self.backends = backends

    def __call__(self, system, user):
        failed = []
        for b in self.backends:
            try:
                text, meta = b(system, user)
            except Exception as e:  # noqa: BLE001 - the next model in the route gets the call
                failed.append({"model": b.described().get("model"), "error": str(e)[:200]})
                continue
            return text, dict(meta, answered_by=b.described().get("model"), fell_back_from=failed)
        raise RuntimeError("Every model in the route failed: " + "; ".join(f"{f['model']} ({f['error']})" for f in failed))

    def described(self):
        first = self.backends[0].described()
        return dict(first, route=[b.described().get("model") for b in self.backends])


def error_text(raw):
    try:
        e = json.loads(raw).get("error") or {}
        return f"{e.get('type', '')} {e.get('message', '')}".strip()[:300]
    except (ValueError, AttributeError):
        return (raw.decode(errors="replace") if isinstance(raw, bytes) else str(raw))[:300]


# ---------------------------------------------------------------------- the Claude Code CLI
def parse_cli(stdout, ms):
    """The reply text and what the CLI reported about the call. Anything it didn't report stays None."""
    try:
        data = json.loads(stdout)
    except ValueError:
        return stdout, {"ms": round(ms), "models": []}
    if isinstance(data, list):
        data = next((d for d in reversed(data) if isinstance(d, dict) and d.get("type") == "result"), {})
    if data.get("is_error"):
        raise RuntimeError(f"the CLI reported an error: {str(data.get('result'))[:300]}")
    usage = data.get("usage") or {}
    parts = [usage.get(k) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")]
    tokens_in = sum(p for p in parts if p) if any(p is not None for p in parts) else None
    return str(data.get("result", "")), {
        "ms": round(float(data.get("duration_ms") or ms)), "api_ms": data.get("duration_api_ms"),
        "input_tokens": tokens_in, "output_tokens": usage.get("output_tokens"), "usage": usage,
        "cost_usd": data.get("total_cost_usd"), "models": sorted((data.get("modelUsage") or {}).keys())}


class ClaudeCLI:
    """model(system, user) through claude -p, with only the flags this CLI offers. Each call runs in a fresh empty
    folder in the system's temporary space, outside any project folder, so no project's instructions reach the
    prompt."""

    def __init__(self, model):
        if not shutil.which("claude"):
            raise SystemExit("The claude command isn't on your PATH. Open Claude Code once, then run this again.")
        help_text = subprocess.run(["claude", "--help"], capture_output=True, text=True, timeout=60).stdout
        self.flags = {f: f in help_text for f in FLAGS}
        self.model = model
        self.tools_flag = "--tools" if self.flags["--tools"] else "--disallowedTools" if self.flags["--disallowedTools"] \
            else None

    def args(self, system, user):
        a = ["claude", "-p"]
        if self.flags["--model"]:
            a += ["--model", self.model]
        if self.flags["--output-format"]:
            a += ["--output-format", "json"]
        if self.flags["--max-turns"]:
            a += ["--max-turns", "1"]
        if self.tools_flag == "--tools":
            a += ["--tools", ""]
        elif self.tools_flag == "--disallowedTools":
            a += ["--disallowedTools", NO_TOOLS]
        if self.flags["--strict-mcp-config"]:
            a.append("--strict-mcp-config")
        if self.flags["--no-session-persistence"]:
            a.append("--no-session-persistence")
        if self.flags["--system-prompt"]:
            return a + ["--system-prompt", system, user]
        return a + [system + "\n\n" + user]

    def __call__(self, system, user):
        workdir = tempfile.mkdtemp(prefix="call-companion-")
        try:
            t0 = time.time()
            r = subprocess.run(self.args(system, user), cwd=workdir, capture_output=True, text=True, timeout=TIMEOUT)
            if r.returncode != 0 and self.tools_flag == "--tools" and "tools" in (r.stderr or "").lower():
                self.tools_flag = "--disallowedTools" if self.flags["--disallowedTools"] else None
                r = subprocess.run(self.args(system, user), cwd=workdir, capture_output=True, text=True, timeout=TIMEOUT)
            if r.returncode != 0:
                raise RuntimeError(f"claude -p exited with {r.returncode}: {(r.stderr or r.stdout).strip()[:300]}")
            return parse_cli(r.stdout, (time.time() - t0) * 1000)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def described(self):
        return {"backend": "claude-cli", "model": self.model, "flags": [f for f, on in self.flags.items() if on],
                "tools_off": self.tools_flag}
