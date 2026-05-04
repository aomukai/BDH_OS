# Worker: gpt-5.4-mini (via codex)

## When to use

**This is the primary worker.** Use it for all tasks — I/O and reasoning alike.

The user has a flat-rate $20 OpenAI subscription, so every codex call is already paid for. DeepSeek costs real money per token via OpenRouter. Always prefer codex unless the OpenAI rate limit is active.

Only fall back to DeepSeek when codex returns a rate limit error.

## Invocation

```bash
codex exec \
  -m "gpt-5.4-mini" \
  --dangerously-bypass-approvals-and-sandbox \
  -s danger-full-access \
  "EXECUTOR_PROMPT_HERE"
```

For long prompts, use heredoc:

```bash
codex exec \
  -m "gpt-5.4-mini" \
  --dangerously-bypass-approvals-and-sandbox \
  -s danger-full-access \
  "$(cat <<'EOF'
...executor prompt...
EOF
)"
```

Run from repo root (`-C /home/aomukai/Ninereeds` if needed).

## Rate limits

**Important:** The user's OpenAI subscription rate limit resets on **May 5, 2026 at 9:11 PM JST**.

Before using codex, check whether the limit has reset. If unsure, use DeepSeek as the fallback.

If a run fails with a 429 or quota error, switch to DeepSeek for that task and note in todo.md that the codex version should be run after the reset.

## Model name note

Confirmed model ID: `gpt-5.4-mini`. Default variant is `medium`. The codex CLI header shows `gpt-5.4-mini medium` at launch.

## Strengths
- Better language quality for generated training content
- Good at following stylistic constraints (format rules, voice consistency)
- More reliable for judgment-alongside-execution tasks

## Limits
- Rate-limited on the user's subscription — don't burn quota on pure I/O tasks
- Slower than DeepSeek for bulk operations
