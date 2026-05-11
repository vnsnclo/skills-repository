#!/usr/bin/env sh
set -eu

usage() {
  echo "Usage: $0 [--validator PATH] [--python COMMAND]"
}

script_dir=$(CDPATH= cd "$(dirname "$0")" && pwd)
repo_root=$(dirname "$(dirname "$script_dir")")
skills_dir="$repo_root/skills"
validator="$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py"
python_cmd=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --validator)
      if [ "$#" -lt 2 ]; then
        usage
        exit 1
      fi
      validator="$2"
      shift 2
      ;;
    --python)
      if [ "$#" -lt 2 ]; then
        usage
        exit 1
      fi
      python_cmd="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [ ! -f "$validator" ]; then
  echo "Validator not found: $validator" >&2
  exit 1
fi

if [ -z "$python_cmd" ]; then
  if command -v python3 >/dev/null 2>&1; then
    python_cmd="python3"
  elif command -v python >/dev/null 2>&1; then
    python_cmd="python"
  else
    echo "Python not found. Install Python or pass --python COMMAND." >&2
    exit 1
  fi
fi

for skill_dir in "$skills_dir"/*; do
  [ -d "$skill_dir" ] || continue

  printf 'Validating %s...\n' "$(basename "$skill_dir")"
  "$python_cmd" "$validator" "$skill_dir"
done
