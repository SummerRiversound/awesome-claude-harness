# Installing awesome-claude-harness (for AI agents)

You are an agent asked to install this setup for your user. Work through the steps in order. Run the commands yourself with your shell tool; the user only answers the questions in step 1 and restarts Claude Code at the end. Reply to the user in the language they wrote to you.

## 1. Ask what to install

Check that `claude --version` runs. Then ask the user, in one round (AskUserQuestion when you have it, multi-select), which of these to install. Recommend the first three plugins and the first two companions:

| Install name | What it gives |
|---|---|
| `harness-skills@awesome-claude-harness` | ready-review, session-retro, show-first, design-check skills |
| `goal-tree@awesome-claude-harness` | Goal tree and milestones before a big job |
| `human-readable-reports@awesome-claude-harness` | Reports and PR bodies a person can read on the first pass |
| `review-inbox@awesome-claude-harness` | A drawer with GitHub PRs and issues; needs GitHub settings afterwards |
| Companion: `mattpocock-skills@mattpocock` | `code-review`, `prototype`, `tdd`, `grilling`; ready-review and show-first call into it |
| Companion: `ponytail@ponytail` | Smallest-change discipline and short replies |
| Companion: `interfaces@interfaces` | UI reviews: accessibility, layout, typography, color |
| Companion: `fluent-korean@fluent-korean` | Natural Korean output |

In the same round ask whether they want the starter rules (step 3), and if so their name and GitHub account.

Done when you have the list of install names and a yes or no for the starter rules.

## 2. Install the plugins

Add each marketplace a chosen plugin needs, once, then install the plugin:

| Marketplace | Add command |
|---|---|
| `awesome-claude-harness` | `claude plugin marketplace add https://github.com/SummerRiversound/awesome-claude-harness.git` |
| `mattpocock` | `claude plugin marketplace add https://github.com/mattpocock/skills.git` |
| `ponytail` | `claude plugin marketplace add https://github.com/DietrichGebert/ponytail.git` |
| `interfaces` | `claude plugin marketplace add https://github.com/jakubkrehel/skills.git` |
| `fluent-korean` | `claude plugin marketplace add https://github.com/snflkd/fluent-korean.git` |

Install: `claude plugin install <install name>`. Use the HTTPS URLs above as written; the `owner/repo` short form clones over SSH and fails without an SSH key. A marketplace that is already added is fine; move on.

Done when `claude plugin list` shows every chosen plugin as enabled.

## 3. Starter rules (only if the user said yes)

Download `https://raw.githubusercontent.com/SummerRiversound/awesome-claude-harness/main/templates/CLAUDE.md`. Replace `<이름>` with the user's name and `<your-github-account>` with their GitHub account.

- No `~/.claude/CLAUDE.md` yet: write the result there.
- One exists: never overwrite it. Copy it to `~/.claude/CLAUDE.md.bak`, show the user the template's section headings, and append only the sections they pick.

The template's Language section makes Claude answer in Korean. If the user wrote to you in another language, ask whether to keep, translate or drop that section before writing it.

Done when `~/.claude/CLAUDE.md` holds the chosen rules and any earlier file is backed up.

## 4. Hand back

Tell the user, in a few lines:

- what was installed, and that Claude Code must be restarted (or `/reload-plugins` run) before the skills load;
- if review-inbox was installed: run `/plugin configure review-inbox@awesome-claude-harness` to fill in its GitHub settings;
- optional extras they can install later from their own repos: [korean-report-skills](https://github.com/JangHyun-bin/korean-report-skills) (sentence rules for Korean reports) and [superpowers](https://github.com/obra/superpowers) (`receiving-code-review`).
