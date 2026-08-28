#!/bin/bash
# Claude Code status hook.
#
# Dumps the event payload into the spool directory and exits. Deliberately
# minimal: this runs synchronously on every tool call, so it must stay cheap.
#
# SAFETY: this script must never write to stdout. It is wired into
# PermissionRequest, where stdout is parsed as a decision object — anything
# printed here could auto-allow or auto-deny a tool call. The block below
# redirects stdout to /dev/null and the script always exits 0.
{
	spool="${CLAUDE_STATUS_DIR:-$HOME/.cache/claude-status}/events"
	[[ -d $spool ]] || mkdir -p "$spool"

	# Microseconds since epoch. Locale may use ',' as the decimal separator.
	ts=${EPOCHREALTIME/[.,]/}
	part="$spool/.part.$ts.$$"

	# Write to a temp name, then rename: the reader only ever sees whole files.
	cat >"$part"
	mv -f "$part" "$spool/$ts.$PPID.json"
} >/dev/null 2>&1

exit 0
