#!/usr/bin/env sh
set -eu

script_dir=$(CDPATH= cd "$(dirname "$0")" && pwd)
repo_root=$(dirname "$(dirname "$script_dir")")
skills_dir="$repo_root/skills"
destination="${1:-$HOME/.claude/skills}"

mkdir -p "$destination"

for skill_dir in "$skills_dir"/*; do
  [ -d "$skill_dir" ] || continue

  name=$(basename "$skill_dir")
  target="$destination/$name"

  if [ -e "$target" ]; then
    rm -rf "$target"
  fi

  cp -R "$skill_dir" "$target"
  printf 'Synced %s -> %s\n' "$name" "$target"
done
