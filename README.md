# Skills Repository

Reusable Codex skills collected in one place.

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
    sync-to-codex-skills.ps1
    sync-to-agents-skills.ps1
    validate-all.ps1
  macos-linux/
    sync-to-codex-skills.sh
    sync-to-agents-skills.sh
    validate-all.sh
```

Each folder under `skills/` is self-contained and can be copied directly into a Codex or global agents skills directory.

Default sync destinations:

- Codex skills: `~/.codex/skills`
- Global agents skills: `~/.agents/skills`

## Included Skills

- `html-to-image-export`: export local HTML pages, DOM elements, SVG diagrams, charts, and app screens to PNG images.

## Usage

### Windows

Sync all skills to the local Codex directory:

```powershell
.\tools\windows\sync-to-codex-skills.ps1
```

Sync all skills to the global agents directory:

```powershell
.\tools\windows\sync-to-agents-skills.ps1
```

Pass `-Destination <path>` to sync to a custom directory.

Validate all skills:

```powershell
.\tools\windows\validate-all.ps1
```

### macOS / Linux

Sync all skills to the local Codex directory:

```sh
sh ./tools/macos-linux/sync-to-codex-skills.sh
```

Sync all skills to the global agents directory:

```sh
sh ./tools/macos-linux/sync-to-agents-skills.sh
```

Pass a path as the first argument to sync to a custom directory.

Validate all skills:

```sh
sh ./tools/macos-linux/validate-all.sh
```
