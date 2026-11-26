# Dixi Tower

**English** · [Español](README.es.md)

## Purpose

Dixi Tower is a local control tower for coding agents. It launches coding-agent sessions on your own machine (Claude Code, Codex, or any agent you run from a terminal), each in its own git worktree and branch, and lets you watch and steer all of them from one web panel at `http://localhost:4310/`.

It runs on the subscription you already have: no API keys, no cloud service, nothing leaves your machine except what the agents themselves do.

> **Status: alpha, private.** macOS only for now. Codex support has not been validated with a real session yet. See the [roadmap](ROADMAP.md).

## What you get

- **One panel for every agent**: search, filter by state, sort by who is waiting for you.
- **Live console** of each agent, with clickable links and keyboard control (arrows, Enter, Esc, 1–3).
- **Slash-command autocomplete**: the engine's commands, your own, and the ones installed in the project (for example the `/dixi.*` commands of [dixi-spec-kit](https://github.com/dixi-project/dixi-spec-kit)).
- **Full session lifecycle**: launch, stop, turn back on (resuming the conversation) and delete.
- **Bring your own agent**: besides Claude Code and Codex, define any terminal agent as an engine.
- **Files and paths in the prompt**: drag or paste files and images, or pick a folder, and its path is inserted for the agent.
- **Dictation**: hold the space bar to speak instead of typing (uses your browser's speech recognition).
- **Per-agent settings**: engine, autonomy level, subagents allowed and how many, and account-usage limits.
- **Guardrails**: an agent never merges, deploys, pushes to the base branch or reads secrets. It ends in a pull request.

## Requirements

- macOS, `bash`, Python 3.9 or later (standard library only)
- `tmux` and `git`
- At least one engine: [Claude Code](https://claude.com/claude-code) or [Codex CLI](https://github.com/openai/codex) signed in with your subscription, or your own
- Optional: `gh` (pull requests), `terminal-notifier` (clickable notifications)

## Quickstart

From a clone of this repository:

```sh
./dixi-tower doctor               # check requirements
./dixi-tower service install      # panel always on at http://localhost:4310/ (macOS)
./dixi-tower panel                # or: run the panel inside tmux (any system)
```

Open the panel and click **＋ New agent**. Pick a repository from your projects folder (`~/projects` by default, change it with `DIXI_TOWER_PROJECTS`), type an instruction and launch.

Run `./dixi-tower` with no arguments to list every command. The panel and the help are available in English and Spanish; messages from the launcher are still in Spanish.

## How it works

Each agent is an interactive session of the engine inside a window of the `dixi-tower` tmux session. Dixi Tower injects permissions, hooks and rules from outside, so the project repository is never modified. Hooks report each agent's state to `~/.dixi-tower/`, and the panel reads those files, git and tmux.

The full guide (commands, settings, internals, security of the panel) is in [docs/uso.md](docs/uso.md), in Spanish.

## Security

The panel listens on `127.0.0.1` only, rejects requests whose `Host` header is not local, and requires a token for every action that writes. Anyone who can open the panel can give instructions to your agents: do not expose it through a tunnel or proxy.

## License

[MIT](LICENSE) © 2026 Dixi Project.

## Links

- [Roadmap](ROADMAP.md)
- [Changelog](CHANGELOG.md)
- [Usage guide](docs/uso.md) (Spanish)
