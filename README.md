# Dixi Tower

**English** · [Español](README.es.md)

## Purpose

Dixi Tower is a local control tower for coding agents. It launches Claude Code and Codex sessions on your own machine, each in its own git worktree and branch, and lets you watch and steer all of them from one web panel at `http://localhost:4310/`.

It runs on the subscription you already have: no API keys, no cloud service, nothing leaves your machine except what the agents themselves do.

> **Status: alpha, private.** macOS only for now. Codex support has not been validated with a real session yet. See the [roadmap](ROADMAP.md).

## What you get

- **One panel for every agent**: search, filter by state, sort by who is waiting for you.
- **Live console** of each agent, with clickable links and keyboard control (arrows, Enter, Esc, 1–3).
- **Slash-command autocomplete**: the engine's commands, your own, and the ones installed in the project (for example the `/dixi.*` commands of [dixi-spec-kit](https://github.com/dixi-project/dixi-spec-kit)).
- **Full session lifecycle**: launch, stop, turn back on (resuming the conversation) and delete.
- **Per-agent settings**: engine (Claude Code or Codex), autonomy level, subagents allowed and how many, and account-usage limits.
- **Guardrails**: an agent never merges, deploys, pushes to the base branch or reads secrets. It ends in a pull request.

## Requirements

- macOS, `bash`, Python 3.9 or later (standard library only)
- `tmux` and `git`
- At least one engine, signed in with your subscription: [Claude Code](https://claude.com/claude-code) or [Codex CLI](https://github.com/openai/codex)
- Optional: `gh` (pull requests), `terminal-notifier` (clickable notifications)

## Quickstart

From a clone of this repository:

```sh
./dixi-tower servicio instalar    # panel always on at http://localhost:4310/
```

Open the panel and click **＋ New agent**. Pick a repository from your projects folder (`~/projects` by default, change it with `DIXI_PROYECTOS_DIR`), a task or a free-form instruction, and launch.

The command line is in Spanish for now (`lanzar`, `estado`, `detener`…); run `./dixi-tower` with no arguments to list it. The panel is available in English and Spanish.

## How it works

Each agent is an interactive session of the engine inside a window of the `agentes` tmux session. Dixi Tower injects permissions, hooks and rules from outside, so the project repository is never modified. Hooks report each agent's state to `~/.agentes/`, and the panel reads those files, git and tmux.

The full guide (commands, settings, internals, security of the panel) is in [docs/uso.md](docs/uso.md), in Spanish.

## Security

The panel listens on `127.0.0.1` only, rejects requests whose `Host` header is not local, and requires a token for every action that writes. Anyone who can open the panel can give instructions to your agents: do not expose it through a tunnel or proxy.

## Links

- [Roadmap](ROADMAP.md)
- [Changelog](CHANGELOG.md)
- [Usage guide](docs/uso.md) (Spanish)
