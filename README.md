# opendawn

Agent skills and custom agents for AI coding tools — OpenCode, Claude Code, and the `npx skills` ecosystem.

## Quick Install

Install into your current project (default):

```bash
bash <(curl -sSL https://raw.githubusercontent.com/Tomorrowdawn/opendawn/main/scripts/install.sh)
```

Install globally (`~/.config/opencode`, `~/.claude`):

```bash
bash <(curl -sSL https://raw.githubusercontent.com/Tomorrowdawn/opendawn/main/scripts/install.sh) -g
```

Non-interactive (overwrite all without asking):

```bash
bash <(curl -sSL https://raw.githubusercontent.com/Tomorrowdawn/opendawn/main/scripts/install.sh) -y
```

Or clone manually:

```bash
git clone https://github.com/Tomorrowdawn/opendawn.git
cd your-project
bash ../opendawn/scripts/install.sh      # local, interactive
bash ../opendawn/scripts/install.sh -g   # global
bash ../opendawn/scripts/install.sh -y   # non-interactive
```

`npx skills` CLI users:

```bash
npx skills add Tomorrowdawn/opendawn
```

## Architecture

Two agents; pick by mode, not by phase.

```text
Human <-> YuuDev (primary)
  ↪ Mode A — Direct (default): implement in current/assigned worktree, commit, done.
              Gradient is small; git diff is the audit.
  ↪ Mode B — Batch Launcher (explicit): user points at a folder of *-instructions.md;
              YuuDev dispatches parallel YuuCoder runs, collects reports, verifies.

YuuDev also writes instruction.md files for large tasks (opt-in to the
coding-instruction skill format). It does NOT auto-spawn subagents.

YuuDev ←detects symptoms→ suggests loading `probe-and-plan` for deep-dive.

YuuCoder (subagent)
  ↪ Reads one *-instructions.md, works inside its scope + test boundary,
     runs red-green, commits, self-reviews, appends to PR doc, reports.
```

What belongs where (the design principle):

> **System prompt is the strongest constraint.** Per the LLM training, content written directly in the agent's prompt outweighs the same content loaded via "read this file." Skills are a workaround for content too large or too situational to live in the prompt. So:
> - Habits every agent needs → system prompt (scenarios, git recon, commit discipline, lazy ladder)
> - Method the user opts into → skill (deep-dive, coding-instruction spec)
> - Cross-project reference material → skill (language standards, case studies)

## What's Inside

### Custom Agents (`.opencode/agents/`)

OpenCode primary and subagent definitions. Their system prompts embed git discipline, scenario communication, commit hygiene, and the lazy-reflection ladder directly.

| Agent | Role |
|-------|------|
| `YuuDev` | Primary. Direct mode (implement in worktree + commit) is the default. For large tasks, writes `*-instructions.md` files and stops — user reviews/edits, clears session, then re-launches YuuDev to trigger Batch Launcher mode. Suggests `probe-and-plan` when symptoms recur. |
| `YuuCoder` | Subagent. Executes one `*-instructions.md` in an assigned clean worktree: red-green test-first, scope-locked implementation, self-review, PR doc. Only invoked for large-task workflow. |

### Skills (`skills/`)

Platform-independent skills distributed via the `npx skills` CLI and installed by `install.sh`.

| Skill | Description |
|-------|-------------|
| `probe-and-plan` | Opt-in deep-dive. Take-a-step-back methodology, ought-to-be analysis, design format. Loads only when the user signals recurring symptoms or suspected architecture mismatch. NOT a default phase. |
| `coding-instruction` | Specification for the large-task workflow. Defines `*-instructions.md` format, Change Scope semantics, Test Boundary requirements, blocker protocol, worktree lifecycle, task sizing. Loaded manually when producing or executing instruction artifacts. |
| `yuutest` | Red-green test subworkflow used during the test-first phase of a coding instruction. Catches invalid red failures and bad-test anti-patterns. |
| `python-purist` | Opinionated Python coding standards — type safety, composition over inheritance, coroutines over threads. Includes 31 case studies, cookbook recipes, and an automated anti-pattern scanner. |
| `what-should-i-do` | Human-invoked morning orientation — summarize recent progress, roadmap position, and important next todos. |
| `ponytail` *(dependency, MIT)* | Lazy reflection ladder. Forces the simplest, shortest, most minimal solution. Both agents' system prompts inline the ladder core and reference this skill for the full methodology with intensity levels and worked examples. Source: [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail), MIT — installed automatically by `install.sh`. |

## Development

```bash
pnpm install
pnpm check          # TypeScript type checking
```

## Structure

```
opendawn/
├── skills/                        # Platform-independent agent skills
│   ├── probe-and-plan/SKILL.md    # Opt-in deep-dive
│   ├── coding-instruction/SKILL.md # Spec for large-task workflow
│   ├── yuutest/SKILL.md           # Red-green test subworkflow
│   ├── python-purist/             # Python standards + case studies + scanner
│   ├── what-should-i-do/SKILL.md # Morning orientation
│   └── (ponytail is installed by install.sh, not committed here)
├── roadmap/                       # Git-tracked long-term project plans
│   └── index.md
├── .opencode/
│   ├── agents/                    # OpenCode agent definitions
│   │   ├── yuudev.md              #   Primary system prompt (direct + launcher modes)
│   │   └── yuucoder.md            #   Subagent system prompt (large-task executor)
│   └── commands/                  # (empty — no slash commands by design)
├── scripts/
│   └── install.sh                 # One-liner install + ponytail dependency
├── external-wiki/                 # Reference docs for OpenCode plugin system
├── opencode.json
└── package.json
```

## Third-Party Notice

This project includes the `ponytail` skill (MIT) from
[DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail).
It is fetched automatically by `scripts/install.sh` and stored at
`skills/ponytail/`. Both `YuuDev` and `YuuCoder` system prompts reference it;
the lazy-reflection ladder inlined in those prompts is adapted from ponytail.

To install ponytail manually (without `install.sh`):

```bash
npx skills add DietrichGebert/ponytail
```

## License

MIT — see [LICENSE](./LICENSE)
