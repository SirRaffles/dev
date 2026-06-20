# Global Graphify Qwen Default Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Qwen 2.5 Coder 7B through local Ollama the machine-wide default for `graphify extract` while preserving explicit backend overrides.

**Architecture:** Define a Zsh wrapper function in `~/.zshrc` that delegates to the installed executable with `command graphify`. The wrapper injects local extraction defaults only when the subcommand is `extract` and no explicit backend is present; all other calls pass through unchanged.

**Tech Stack:** Zsh, Graphify CLI, Ollama

---

### Task 1: Add And Verify The Global Graphify Wrapper

**Files:**
- Modify: `~/.zshrc`

- [ ] **Step 1: Record the current command resolution**

Run:

```bash
zsh -ic 'type graphify'
```

Expected: `graphify` resolves to `/Users/davidmarchesseau/.local/bin/graphify` before the change.

- [ ] **Step 2: Add the wrapper function after API-key loading**

Append this block to `~/.zshrc` after the secrets source line so existing API-key configuration remains available:

```zsh
# Graphify local semantic extraction defaults.
graphify() {
  if [[ "$1" == "extract" && "$#" -ge 2 ]]; then
    local arg
    local has_backend=0

    for arg in "$@"; do
      if [[ "$arg" == "--backend" || "$arg" == --backend=* ]]; then
        has_backend=1
        break
      fi
    done

    if (( ! has_backend )); then
      local target="$2"
      shift 2
      OLLAMA_API_KEY="${OLLAMA_API_KEY:-local}" \
      GRAPHIFY_OLLAMA_NUM_CTX="${GRAPHIFY_OLLAMA_NUM_CTX:-32768}" \
        command graphify extract "$target" \
          --backend ollama \
          --model qwen2.5-coder:7b \
          --token-budget 4000 \
          --api-timeout 600 \
          "$@"
      return
    fi
  fi

  command graphify "$@"
}
```

Defaults are inserted before remaining user arguments, so an explicit `--model`, `--token-budget`, or `--api-timeout` still wins under Graphify's last-value parsing.

- [ ] **Step 3: Verify Zsh loads the function without syntax errors**

Run:

```bash
zsh -n ~/.zshrc
zsh -ic 'type graphify'
```

Expected: syntax check exits zero and `graphify is a shell function` is reported.

- [ ] **Step 4: Verify non-extract commands pass through**

Run:

```bash
zsh -ic 'graphify --help' | head -3
```

Expected: output starts with `Usage: graphify <command>`.

- [ ] **Step 5: Verify the wrapper body contains every approved default and override guard**

Run:

```bash
zsh -ic 'functions graphify' | rg 'has_backend|backend ollama|qwen2.5-coder:7b|token-budget 4000|api-timeout 600|GRAPHIFY_OLLAMA_NUM_CTX'
```

Expected: every pattern appears in the loaded function definition.

- [ ] **Step 6: Verify explicit cloud backends bypass injection**

Run:

```bash
zsh -ic 'functions graphify' | rg 'has_backend|command graphify "\$@"'
```

Expected: the backend guard and final direct delegation are both present. No external API call is made during verification.

- [ ] **Step 7: Record the global configuration change**

No repository commit is created for `~/.zshrc`, because it is machine-local and outside the repository. The committed design and this implementation plan provide the durable project record.
