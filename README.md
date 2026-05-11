# Skills Repository

A skills repository for collecting portable, self-contained skills in one place.

## Structure

```text
skills/
  <skill-name>/
    SKILL.md
    agents/openai.yaml
    scripts/
    references/
    assets/
tools/
  windows/
    sync-to-codex-skills.cmd
    sync-to-agents-skills.cmd
    sync-to-claude-code-skills.cmd
    validate-all.cmd
  macos-linux/
    sync-to-codex-skills.sh
    sync-to-agents-skills.sh
    sync-to-claude-code-skills.sh
    validate-all.sh
  validators/
    quick_validate.py
```

Each folder under `skills/` is self-contained and can be copied directly into any compatible skills directory.

Bundled sync targets for common skill locations:

- Codex: `~/.codex/skills`
- Global agents: `~/.agents/skills`
- Claude Code: `~/.claude/skills`

Validation uses the repository's bundled `tools/validators/quick_validate.py`.

## Included Skills

- `html-to-image-export`: export local HTML pages, DOM elements, SVG diagrams, charts, and app screens to PNG images.
- `roberta-mazzone-photography`: create slow-travel photography prompts, shot lists, moodboards, editorial direction, lifestyle campaign briefs, and caption copy.

## Usage

### Windows

- Codex: `tools\windows\sync-to-codex-skills.cmd`
- Global agents: `tools\windows\sync-to-agents-skills.cmd`
- Claude Code: `tools\windows\sync-to-claude-code-skills.cmd`
- Validate: `tools\windows\validate-all.cmd`

Pass a custom destination as the first argument when syncing. Use `--no-pause` or `--validator <path>` only when needed.

### macOS / Linux

- Codex: `sh ./tools/macos-linux/sync-to-codex-skills.sh`
- Global agents: `sh ./tools/macos-linux/sync-to-agents-skills.sh`
- Claude Code: `sh ./tools/macos-linux/sync-to-claude-code-skills.sh`
- Validate: `sh ./tools/macos-linux/validate-all.sh`

Pass a custom destination as the first argument when syncing. Use `--validator <path>` only when needed.
