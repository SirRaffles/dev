# Global Graphify Qwen Default

## Goal

Make local Qwen extraction the default for `graphify extract` on this machine while preserving explicit access to every other Graphify backend.

## Design

Add a `graphify` shell function to `~/.zshrc`. For `graphify extract` calls that do not already specify `--backend` or `--backend=...`, the function delegates to the real executable with these defaults:

- `--backend ollama`
- `--model qwen2.5-coder:7b`
- `--token-budget 4000`
- `--api-timeout 600`
- `OLLAMA_API_KEY=local`
- `GRAPHIFY_OLLAMA_NUM_CTX=32768`

All non-extract commands pass through unchanged. Any extract command with an explicit backend also passes through unchanged, so Gemini, OpenAI, or another backend can still be selected per invocation.

The function uses `command graphify` to avoid recursion. It does not modify the installed Graphify package, project files, API keys, or Ollama configuration.

## Verification

Start a fresh interactive Zsh shell and verify:

1. `type graphify` resolves to the shell function.
2. A dry argument trace confirms defaults are injected for `graphify extract`.
3. An explicit `--backend gemini` is not modified.
4. `graphify --help` remains a direct pass-through.
