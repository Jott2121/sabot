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
# Match rewrite flags as their own arguments anywhere in that command, not
# only beside the subcommand. `git push origin --force`, `git push origin -f`,
# `git push -fu`, and `git reset HEAD --hard` are denied. A newline, `;`,
# `&&`, or `|` starts a new command, so `git push` then `curl -fsSL` is not a
# force-push. A backslash-newline is a continuation and stays one command.
# A plain `git push` still asks below.
rewrite=$(printf '%s' "$cmd" | python3 -c '
import re, sys
text = sys.stdin.read()
segs = []
buf = []
i = 0
quote = None
while i < len(text):
    c = text[i]
    if quote:
        buf.append(c)
        if c == quote:
            quote = None
        i += 1
        continue
    if c in ("'\''", "\""):
        quote = c
        buf.append(c)
        i += 1
        continue
    if c == "\\" and i + 1 < len(text) and text[i + 1] == "\n":
        buf.append(" ")
        i += 2
        continue
    if c == "\n" or c == ";" or c == "|":
        segs.append("".join(buf))
        buf = []
        i += 1
        continue
    if text.startswith("&&", i) or text.startswith("||", i):
        segs.append("".join(buf))
        buf = []
        i += 2
        continue
    if c == "&":
        segs.append("".join(buf))
        buf = []
        i += 1
        continue
    buf.append(c)
    i += 1
segs.append("".join(buf))
short_force = re.compile(r"^-[A-Za-z]*f[A-Za-z]*$")
saw_force = saw_hard = False
for seg in segs:
    verb = None
    for raw in seg.split():
        token = raw[1:-1] if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'\''", "\"") else raw
        if token == "push":
            verb = "push"
        elif token == "reset":
            verb = "reset"
        elif verb == "push" and (
            token in ("-f", "--force", "--force-with-lease")
            or token.startswith("--force=")
            or token.startswith("--force-with-lease=")
            or short_force.match(token)
        ):
            saw_force = True
        elif verb == "reset" and (token == "--hard" or token.startswith("--hard=")):
            saw_hard = True
if saw_force:
    sys.stdout.write("force")
elif saw_hard:
    sys.stdout.write("hard")
')
case "$rewrite" in
  force) deny "Force-push blocked by repo policy." ;;
  hard) deny "History rewrite blocked by repo policy." ;;
esac
case "$cmd" in
  *"rebase"*) deny "History rewrite blocked by repo policy." ;;
  *"git tag"*|*"twine upload"*|*"uv publish"*|*"gh release"*) deny "Releases/publishing are human-only." ;;
  *"rm -rf /"*|*"rm -rf ~"*|*'rm -rf $HOME'*)         deny "Destructive delete blocked." ;;
  *"curl"*"| sh"*|*"curl"*"| bash"*|*"wget"*"| sh"*)   deny "Pipe-to-shell blocked." ;;
  *"git push"*)                                       ask  "Agent wants to push a branch. Allow?" ;;
  *"curl"*|*"wget"*)                                  ask  "Agent wants network access: $cmd" ;;
esac
printf '{"permission":"allow"}\n'
