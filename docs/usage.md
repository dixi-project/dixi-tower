# Dixi Tower usage guide

**English** · [Español](uso.md)

## Purpose

How to use Dixi Tower day to day: commands, settings, internals and rules.

## Quick use

Every command has an English and a Spanish name (`launch`/`lanzar`, `status`/`estado`, `stop`/`detener`…). `dixi-tower doctor` checks requirements and installation.

```bash
dixi-tower service install      # panel always on at http://localhost:4310/ (macOS)
dixi-tower service restart      # after changing panel.py or the catalogs
dixi-tower service status       # installed? responding?
dixi-tower service uninstall
dixi-tower panel                # without the service: runs the panel inside tmux
```

The service is a LaunchAgent (`~/Library/LaunchAgents/com.dixi-project.dixi-tower.plist`): it starts when you log in and launchd restarts it if it crashes, independently of tmux. Its output goes to `~/.dixi-tower/panel.log`. It stores the `PATH` from the moment it was installed; if `tmux`, `git`, `gh` or your engine move, reinstall it.

On Linux and on Windows (WSL2) there is no service: start the panel with `dixi-tower panel`. For Windows setup, see [the manual](manual.md#on-windows-wsl2).

Everything else is done from the panel: launch an agent (**＋ New agent**), watch its console, type to it, send keys and stop it.

From the terminal:

```bash
dixi-tower next <project>                          # pending board tasks
dixi-tower launch <project> <task-id> [--force]    # with a board task
dixi-tower launch <project> free --instruction <file> [--engine E] [--autonomy A]
dixi-tower status
dixi-tower show <agent> | say <agent> "<msg>" | stop <agent>
dixi-tower resume <agent>                          # turn a stopped agent back on, resuming its conversation
dixi-tower delete <agent>                          # remove a stopped agent and its worktree
tmux attach -t dixi-tower                          # live consoles
```

## Settings

Changed from the panel: **Settings** in the sidebar (values every new agent starts with, stored in `~/.dixi-tower/config.json`) and **Settings** on each agent's card (its own copy, stored in its state file).

| Setting | Options | When it applies |
|---|---|---|
| Engine | `claude` (Claude Code), `codex` (Codex CLI) or one of your own | When the agent is turned on |
| Autonomy | `supervisada` (supervised), `equilibrada` (balanced), `autonoma` (autonomous) | When the agent is turned on |
| Subagents | allowed or not, and maximum open at a time (1 to 20) | Claude: immediately. Codex: when turned on |
| Weekly and 5-hour session usage limit | percentage of the account; 0 = no limit | Claude: immediately. Codex: shown, not enforced |

How autonomy maps to each engine:

| Level | Claude Code | Codex |
|---|---|---|
| Supervised | `--permission-mode manual` | `--sandbox read-only --ask-for-approval on-request` |
| Balanced | `--permission-mode acceptEdits` | `--sandbox workspace-write --ask-for-approval on-request` |
| Autonomous | `--permission-mode auto` | `--approve-for-me` (an automatic reviewer approves) |

At every level the agent still cannot merge, deploy or read secrets.

### Engine differences

| | Claude Code | Codex |
|---|---|---|
| Agent rules | `--append-system-prompt` | `-c developer_instructions=…` |
| State in the panel | Hooks on every event: exact | Read from its screen: approval prompts and the state in its footer |
| Own guard (`guardia.py`) | Yes | No: the guard is Codex's sandbox |
| Usage limits | Shown and enforced | Shown (read from its footer), not enforced |
| Commits | No friction | Its sandbox protects `.git`: each commit needs approval, except in autonomous |

Codex support was validated with a real session (Codex 0.167): startup, end-of-turn notice, commit approval, state in the panel and resuming the session.

What to expect with Codex:

- **The first time in each repository it asks you to trust the folder.** Answer from the panel with Enter. Codex stores that decision in its own settings.
- **Each commit asks for approval** in supervised and balanced, because its sandbox protects `.git`. The panel shows the agent as “Needs you”.
- **Its footer shows “1 warning”**: Codex says that, when it receives options on the command line, it does not use its shared background server. It is harmless.
- Dixi Tower turns off Codex's “update available” prompt, which would leave an unattended agent waiting.

## How it works

| Piece | What it does |
|---|---|
| `dixi-tower` | Creates the worktree and the branch, builds the prompt and opens the agent in a window of the `dixi-tower` tmux session |
| `~/.dixi-tower/proyectos.json` | Project registry (repository, base branch and workflow command). A repository in the projects folder is registered the first time it is launched (`registro.py`) |
| `worker-settings.json` | Permissions and hooks injected into the agent with `--settings`, without touching the project repository |
| `worker-prompt.md` | Agent rules: one task, ends in a pull request, never merges or deploys |
| `hooks/estado-hook.py` | Writes `~/.dixi-tower/estado/<agent>.json` on every event and notifies you when the agent stops |
| `config.py` | Global and per-agent settings, and limit checks |
| `arranque.py` | Writes the script that opens or resumes a session for the agent's engine and autonomy |
| `hooks/barra.py` | The agent's status line: stores account usage in `~/.dixi-tower/uso/` and shows your own status line |
| `hooks/control.py` | Before each tool call: enforces usage limits and the subagent cap |
| `hooks/avisos.py` | Desktop notifications: terminal-notifier or osascript on macOS, notify-send on Linux, Windows notifications through PowerShell on WSL |
| `hooks/codex-notify.py` | End of a Codex turn: updates its state and notifies you |
| `comandos.json` | Each engine's own commands, for autocomplete |
| `hooks/guardia.py` | Blocks merge, pushing to the base branch, force push, deploys, writes to AWS and reading secrets |
| `panel.py` | Web panel: reads the state files, git and tmux; texts in `locales/` |
| `mensajes.py` | Messages of the launcher in English and Spanish |
| `tareas.py`, `estado.py`, `ocupado.py` | Reading `tasks/TASKS.md`, the status table and in-use worktree checks |

## Your own engines

Besides Claude Code and Codex, you can use any agent that runs in a terminal: another CLI, a local model, a script of yours. Define them under the `motores` key of the settings (`config.json` in the data folder):

```json
{
  "motores": {
    "aider": {
      "comando": "aider --message {instruccion}",
      "reanudar": "aider --restore-chat-history"
    }
  }
}
```

- `comando` opens the session. `{instruccion}` is replaced with the task and `{reglas}` with the agent rules; both are optional.
- `reanudar` is optional: what runs when a stopped agent is turned back on. If missing, `comando` runs with the task “Continue with the previous task”.
- The engine shows up in the panel's selectors and in `--engine <name>`.

With your own engine, Dixi Tower gives you everything that does not depend on the engine: its own worktree and branch, live console, keyboard, lifecycle and an approximate state (from changes on its screen). Autonomy, subagents, usage limits and the own guard do not apply: that depends on what your engine offers.

## Files and paths in the prompt

To tell the agent which file or folder you mean:

- **Drag or paste** files and images onto the text box. For security, a browser never reveals to a page the real path of what is dropped on it, so the panel saves a **copy** in `adjuntos/<agent>/` inside the data folder and inserts the path of that copy. Limit: 25 MB per file. Copies are deleted when the agent is deleted.
- **“Path” button**: opens a browser of your folders and inserts the **real path** of the file or folder you pick, without copying anything. This is how you point to a folder or a large file. It only shows what is inside your home folder and hides files that start with a dot.

Paths with spaces are inserted in quotes.

## Dictation

In the panel you can dictate instead of typing: hold the **space bar** with the box empty, or the **Dictate** button, and release to finish. The text stays in the box for you to review; it is not sent on its own.

It uses the browser's speech recognition, which is **not local**: in Chrome the audio is transcribed on Google's servers, and in Safari Apple processes it. If that is not acceptable for your work, do not use it.

## Agent rules

Every agent gets the rules in `worker-prompt.md`: one task, one branch, ends in a pull request, never merges, deploys or reads secrets.

To add your own, create `~/.dixi-tower/reglas.md`. Its content is appended to every agent's rules the next time it is turned on. Use it for your team's conventions: language of commits, maximum size of a pull request, files that must not be touched.

## Task integration (optional)

Dixi Tower works without any task manager: each agent starts with a free-form instruction and a branch `agente/<summary>-<date>`.

If a project has a `tasks/TASKS.md` in the [sys_task](https://task.dixi-project.com/) format (lines like `- [ ] **Title** <!-- st:id -->`), an integration turns on by itself:

- The **New agent** form offers the pending tasks, by priority.
- The branch is named `st/<id>-<summary>`, the convention sys_task uses to move the card.
- You can set an **in-review task limit** per project in Settings: with more tasks in `[r]` than the limit, no new agent is launched unless forced. It is 0 (off) by default.
- To keep your board one click away, add its address to `config.json` in the data folder: `"tablero": "https://tasks.example.com/"`. The panel then shows an “Open the task board” link; without that key there is no link.

## Slash commands in the panel

Typing `/` in the text box shows autocomplete with the commands that agent understands:

| Source | Where they come from |
|---|---|
| Project | `.claude/commands/**/*.md` and `.claude/skills/*/SKILL.md` in the agent's worktree. Whatever a kit installs in the project, such as the `/dixi.*` commands of dixi-spec-kit, shows up here with no setup |
| Yours | `~/.claude/commands` and `~/.claude/skills` |
| Engine | `comandos.json`: a curated list of Claude Code's and Codex's own commands. No engine exposes this list to a script, so it may not match your installed version exactly |

With Codex only the engine's commands are offered. ↑ ↓ pick, Tab or Enter complete, Esc closes; the command is sent with a second Enter.

## Rules

- **Agent name**: the first agent of a project is named after the project; the next ones, `<project>@2`, `<project>@3`… There are never two agents on the same task.
- **Branches**: with a board task, `st/<id>-<slug>` (moves the card in sys_task); with a free-form instruction, `agente/<slug>-<date>` (moves nothing).
- **Agent lifecycle**: launch → (stop ⇄ resume) → delete. Deleting requires the agent to be stopped and to have no uncommitted files; it removes its worktree and state, and **keeps the branch** with its commits.
- **In-review limit** (only with the task integration): see “Task integration”.
- **Working data** lives in `~/.dixi-tower/` (`estado/`, `run/`, `worktrees/`), outside any repository.

## Environment variables

The former names (`DIXI_AGENTES_*`, `DIXI_PROYECTOS_DIR`) are still accepted.

| Variable | Default | Purpose |
|---|---|---|
| `DIXI_TOWER_PROJECTS` | `~/projects` | Folder whose repositories can be launched |
| `DIXI_TOWER_HOME` | `~/.dixi-tower` | Data folder: state, settings, startup scripts and worktrees. If only `~/.agentes` exists (earlier installations), that one is used |
| `DIXI_TOWER_PORT` | `4310` | Panel port |
| `DIXI_TOWER_NOTIFY` | `1` | `0` turns notifications off |
| `DIXI_TOWER_LANG` | system language | `en` or `es`: language of messages and help |
| `DIXI_TOWER_SESSION` | `dixi-tower` | Name of the agents' tmux session |

## Panel security

The panel listens on `127.0.0.1` only, rejects requests whose `Host` header is not local, and requires a token for every action that writes (sending text or keys, stopping, launching, saving attachments). The token is stored in the data folder, readable only by you. Anyone who can open the panel can give instructions to your agents: do not expose it through a tunnel or proxy.

## Links

- [README](../README.md)
- [Operations manual](manual.md): step by step, with screenshots
- [Roadmap](../ROADMAP.md)
