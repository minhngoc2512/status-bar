"""Headless check of the event -> state machine and the i18n layer."""
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import indicator as I

st = I.Store()
A, B = "sess-A", "sess-B"
CWD = {A: "/home/minhngoc/Demo/sense_nova", B: "/home/minhngoc/Demo/api_firebase"}
EN, VI = I.Lang("en"), I.Lang("vi")


def ev(name, sid=A, **kw):
    d = {"hook_event_name": name, "session_id": sid, "cwd": CWD[sid]}
    d.update(kw)
    return d


def state(sid=A):
    s = st.sessions.get(sid)
    return None if s is None else (s.state, s.detail)


checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print(f"{'ok  ' if ok else 'FAIL'} {label}: {got!r}" + ("" if ok else f"  (want {want!r})"))


st.apply(ev("SessionStart"), 111)
check("SessionStart -> idle", state(), (I.IDLE, ("raw", "")))

st.apply(ev("UserPromptSubmit"), 111)
check("UserPromptSubmit -> working", state(), (I.WORKING, ("processing", None)))

st.apply(ev("PreToolUse", tool_name="Bash"), 111)
check("PreToolUse -> working:Bash", state(), (I.WORKING, ("raw", "Bash")))

st.apply(ev("PermissionRequest", tool_name="Bash"), 111)
check("PermissionRequest -> confirm", state(), (I.CONFIRM, ("raw", "Bash")))

st.apply(ev("PostToolUse", tool_name="Bash"), 111)
check("PostToolUse -> working", state(), (I.WORKING, ("processing", None)))

st.apply(ev("SubagentStart", agent_type="Explore"), 111)
check("SubagentStart counts", st.sessions[A].subagents, 1)
st.apply(ev("SubagentStop"), 111)
check("SubagentStop counts", st.sessions[A].subagents, 0)

st.apply(ev("Stop", background_tasks=[{"id": "1"}, {"id": "2"}]), 111)
check("Stop with tasks -> background", state(), (I.BACKGROUND, ("tasks", 2)))
check("detail renders EN", st.sessions[A].render_detail(EN), "2 task(s)")
check("detail renders VI", st.sessions[A].render_detail(VI), "2 task")

st.apply(ev("Stop", background_tasks=[]), 111)
check("Stop empty -> idle", state(), (I.IDLE, ("raw", "")))

st.apply(ev("Notification", notification_type="permission_prompt", title="Permission needed"), 111)
check("Notification/permission_prompt -> confirm", state(), (I.CONFIRM, ("raw", "Permission needed")))

st.apply(ev("Notification", notification_type="auth_success"), 111)
check("Notification/auth_success ignored", state(), (I.CONFIRM, ("raw", "Permission needed")))

st.apply(ev("Notification", notification_type="elicitation_dialog"), 111)
check("Notification/elicitation -> confirm mcp", state(), (I.CONFIRM, ("mcp", None)))

st.apply(ev("StopFailure"), 111)
check("StopFailure -> error", state(), (I.ERROR, ("api", None)))

# Second session, worst-state aggregation
st.apply(ev("SessionStart", sid=B), 222)
st.apply(ev("UserPromptSubmit", sid=B), 222)
check("worst() picks error over working", st.worst(), I.ERROR)

st.apply(ev("PermissionRequest", sid=B, tool_name="Write"), 222)
check("worst() picks confirm over error", st.worst(), I.CONFIRM)
check("count(confirm)", st.count(I.CONFIRM), 1)
check("project name from cwd", st.sessions[B].project, "api_firebase")

st.apply(ev("SessionEnd", sid=B, reason="other"), 222)
check("SessionEnd removes session", state(B), None)

check("unknown event ignored", st.apply(ev("PreCompact"), 111), None)
check("event without session_id ignored", st.apply({"hook_event_name": "Stop"}, 0), None)

# i18n coverage: every key used by one language exists in the other
en_keys, vi_keys = set(I.STRINGS["en"]), set(I.STRINGS["vi"])
check("EN/VI key sets match", en_keys ^ vi_keys, set())
check("bar label EN", EN("bar.working"), "working")
check("bar label VI", VI("bar.working"), "chạy")
check("unknown key falls back to itself", EN("nope.nope"), "nope.nope")

# every state has an icon (static) and animated states have all frames
missing = [s for s in I.PRIORITY if not (I.ICON_DIR / f"claude-{s}.svg").exists()]
check("static icons present", missing, [])
check("animated states are real states", set(I.ANIM) - set(I.PRIORITY), set())
check("every animation has frames + interval", all(f and ms > 0 for f, ms in I.ANIM.values()), True)

print()
print(f"{sum(checks)}/{len(checks)} passed")
sys.exit(0 if all(checks) else 1)
