#!/usr/bin/env bash
# beforeShellExecution guard. Reads {"command": "...", "cwd": "..."} on stdin.
# Denies irreversible / publishing commands; asks on network fetches. Fails closed (hooks.json failClosed: true).
# The matcher includes `git pull`, so `git pull --rebase` reaches the rebase deny arm. See AGENTS.md.
set -euo pipefail
input="$(cat)"
cmd="$(printf '%s' "$input" | python3 -c 'import sys,json
data=json.load(sys.stdin)
cmd=data.get("command") if isinstance(data, dict) else None
sys.stdout.write(cmd if isinstance(cmd, str) else "")')"
deny() { printf '{"permission":"deny","user_message":"%s","agent_message":"%s Open a PR instead; a human will do this step."}\n' "$1" "$1"; exit 0; }
ask()  { printf '{"permission":"ask","user_message":"%s"}\n' "$1"; exit 0; }
if [ -z "${cmd//[[:space:]]/}" ]; then
  deny "Shell guard blocked a missing command."
fi
# Match rewrite flags as their own arguments anywhere, not only beside the
# subcommand. `git push origin --force`, `git push origin -f`, and
# `git reset HEAD --hard` are denied. A plain `git push` still asks below.
set -f
push=0
reset=0
force=0
hard=0
for token in $cmd; do
  token="${token#\'}"
  token="${token%\'}"
  token="${token#\"}"
  token="${token%\"}"
  case "$token" in
    push) push=1 ;;
    reset) reset=1 ;;
    --force|--force=*|--force-with-lease|--force-with-lease=*|-f) force=1 ;;
    --hard|--hard=*) hard=1 ;;
  esac
done
set +f
if [ "$push" -eq 1 ] && [ "$force" -eq 1 ]; then
  deny "Force-push blocked by repo policy."
fi
if [ "$reset" -eq 1 ] && [ "$hard" -eq 1 ]; then
  deny "History rewrite blocked by repo policy."
fi
case "$cmd" in
  *"rebase"*) deny "History rewrite blocked by repo policy." ;;
  *"git tag"*|*"twine upload"*|*"uv publish"*|*"gh release"*) deny "Releases/publishing are human-only." ;;
  *"rm -rf /"*|*"rm -rf ~"*|*'rm -rf $HOME'*)         deny "Destructive delete blocked." ;;
  *"curl"*"| sh"*|*"curl"*"| bash"*|*"wget"*"| sh"*)   deny "Pipe-to-shell blocked." ;;
  *"git push"*)                                       ask  "Agent wants to push a branch. Allow?" ;;
  *"curl"*|*"wget"*)                                  ask  "Agent wants network access: $cmd" ;;
esac
printf '{"permission":"allow"}\n'
