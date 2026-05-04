# Worker: DeepSeek v4 flash (via opencode)

## When to use

**This is the fallback worker.** Use it only when gpt-5.4-mini (codex) is rate-limited.

DeepSeek is billed per token via OpenRouter — it costs real money. The primary worker (codex) runs on a flat-rate OpenAI subscription. Do not use DeepSeek when codex is available.

Appropriate when: codex returns a 429/rate-limit error, or the OpenAI daily limit is known to be active (check `skills/worker_codex.md` for reset time).

## Invocation

```bash
~/.opencode/bin/opencode run \
  -m "openrouter/deepseek/deepseek-v4-flash" \
  --dangerously-skip-permissions \
  "EXECUTOR_PROMPT_HERE"
```

For long prompts, use heredoc:

```bash
~/.opencode/bin/opencode run \
  -m "openrouter/deepseek/deepseek-v4-flash" \
  --dangerously-skip-permissions \
  "$(cat <<'EOF'
...executor prompt...
EOF
)"
```

Run from repo root. The `--dangerously-skip-permissions` flag enables headless operation (auto-accepts all tool calls).

## Strengths
- Fast and cheap for bulk file work
- Reliable for structured JSON manipulation
- Good at following explicit step-by-step instructions

## Limits
- Less reliable for tasks requiring nuanced judgment about training data quality
- Occasionally needs re-runs for complex graph operations — always verify the receipt

## Rate limits
- Available via OpenRouter — generally no hard daily limits at this tier
- If a run fails with a rate error, wait 60 seconds and retry

## Notes
- opencode operates in the repo directory by default — no need to specify `--dir` when running from repo root
- The model ID `openrouter/deepseek/deepseek-v4-flash` is confirmed working as of 2026-05-04
