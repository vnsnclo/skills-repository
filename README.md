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
  validate-all.ps1
  sync-to-codex-skills.ps1
```

Each folder under `skills/` is self-contained and can be copied directly into a Codex skills directory.

## Included Skills

- `html-to-image-export`: export local HTML pages, DOM elements, SVG diagrams, charts, and app screens to PNG images.

## Usage

Sync all skills to the local Codex directory:

```powershell
.\tools\sync-to-codex-skills.ps1
```

Validate all skills:

```powershell
.\tools\validate-all.ps1
```
