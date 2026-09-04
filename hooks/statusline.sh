#!/bin/bash
# Claude Code statusLine command.
#
# Claude Code pipes a JSON context object to this script on stdin. That object
# is the only place plan usage limits are exposed locally -- they arrive as
# `anthropic-ratelimit-unified-*` response headers and are never written to
# disk, so no amount of reading ~/.claude will find them.
#
#   "rate_limits": {          // only for subscribers, after the first API response
#     "five_hour": { "used_percentage": number, "resets_at": number },
#     "seven_day": { "used_percentage": number, "resets_at": number }
#   }
#
# So this drops the payload into the same spool the hooks use, and the indicator
# picks it up from there.
#
# SPEED: this runs on every status line render, far more often than a hook. It
# therefore spawns no subprocesses at all -- no jq, no python -- and pulls the
# two percentages out with parameter expansion.
#
# STDOUT IS THE STATUS LINE. Whatever is printed here appears inside Claude
# Code, so it prints the same summary the tray shows, and nothing at all when
# the payload carries no limits.

spool="${CLAUDE_STATUS_DIR:-$HOME/.cache/claude-status}/events"
[[ -d $spool ]] || mkdir -p "$spool"

input=$(cat)

ts=${EPOCHREALTIME/[.,]/}
part="$spool/.part.$ts.$$"
printf '%s' "$input" >"$part" 2>/dev/null
# .status.json rather than .json: the indicator applies hook events and status
# payloads through different paths.
mv -f "$part" "$spool/$ts.$PPID.status.json" 2>/dev/null

# --- render, without forking ------------------------------------------------
pct() { # $1 = window key; echoes a rounded percentage, or nothing
	local rest=${input#*\"$1\"}
	[[ $rest == "$input" ]] && return
	rest=${rest#*\"used_percentage\":}
	# Two steps, not one bracket expression: a "}" inside ${var%%[,}]*} ends the
	# parameter expansion early in bash, and the rest of the pattern leaks into
	# the output as literal text.
	rest=${rest%%,*}
	rest=${rest%%\}*}
	rest=${rest// /}
	[[ $rest =~ ^[0-9]+ ]] || return
	printf '%s' "${rest%%.*}"
}

five=$(pct five_hour)
week=$(pct seven_day)

out=""
[[ -n $five ]] && out="5h ${five}%"
[[ -n $week ]] && out="${out:+$out · }7d ${week}%"
[[ -n $out ]] && printf '%s' "$out"

exit 0
