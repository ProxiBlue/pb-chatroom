#!/usr/bin/env bash
# pb-chatroom UserPromptSubmit hook.
#
# Polls the chatroom REST API for open threads addressed to this Claude
# Code session, and surfaces them as a context block prepended to the
# user's prompt. Claude sees the block and decides whether to act
# (read, reply, ack) before answering the user's actual question.
#
# Stays cheap: ~one HTTP GET per user message, throttled to one call
# every PB_CHATROOM_CHECK_INTERVAL_SECONDS (default 30).
#
# Identity resolves the same way the rest of the plugin does:
#   $PB_CHATROOM_PARTICIPANT_ID > container-${DDEV_PROJECT} > "host"
#
# REST URL resolves the same way the chat-threads-open slash does:
#   in container (DDEV_PROJECT or /.dockerenv): host.docker.internal:7476
#   otherwise:                                  127.0.0.1:7476
# Override either via env (PB_CHATROOM_REST_HOST / PB_CHATROOM_REST_URL).

set -euo pipefail

# --- Resolve identity ---------------------------------------------------
PARTICIPANT="${PB_CHATROOM_PARTICIPANT_ID:-${DDEV_PROJECT:+container-${DDEV_PROJECT}}}"
PARTICIPANT="${PARTICIPANT:-host}"

# --- Resolve URL --------------------------------------------------------
if [ -n "${PB_CHATROOM_REST_URL:-}" ]; then
    REST_URL="$PB_CHATROOM_REST_URL"
else
    if [ -n "${DDEV_PROJECT:-}" ] || [ -f /.dockerenv ]; then
        REST_HOST="${PB_CHATROOM_REST_HOST:-host.docker.internal}"
    else
        REST_HOST="${PB_CHATROOM_REST_HOST:-127.0.0.1}"
    fi
    REST_URL="http://${REST_HOST}:7476"
fi

# --- Throttle: skip if last check was very recent -----------------------
CHECK_INTERVAL="${PB_CHATROOM_CHECK_INTERVAL_SECONDS:-30}"

STATE_DIR="${PB_CHATROOM_HOOK_STATE_DIR:-$HOME/.pb-chatroom-hook-state}"
mkdir -p "$STATE_DIR" 2>/dev/null || true

# State file name encodes participant so multiple sessions on the same
# machine don't trample each other's cursors.
SAFE_PARTICIPANT="${PARTICIPANT//[^A-Za-z0-9._-]/_}"
LAST_CHECK_FILE="$STATE_DIR/last-check-${SAFE_PARTICIPANT}.epoch"

NOW_EPOCH=$(date +%s)
LAST_CHECK_EPOCH=$(cat "$LAST_CHECK_FILE" 2>/dev/null || echo 0)
ELAPSED=$((NOW_EPOCH - LAST_CHECK_EPOCH))

if [ "$ELAPSED" -lt "$CHECK_INTERVAL" ]; then
    # Still within the throttle window — emit nothing, don't fetch.
    exit 0
fi

# --- Fetch open threads addressed to me ---------------------------------
# Use a short timeout so a down server doesn't slow the prompt.
RESPONSE=$(curl -sS -m 3 \
    --get \
    --data-urlencode "to=${PARTICIPANT}" \
    --data-urlencode "status=open" \
    "${REST_URL}/api/threads" \
    -H "X-PB-Chatroom-Participant: ${PARTICIPANT}" 2>/dev/null || echo "[]")

# Update the cursor — successful or not, we throttle either way.
echo "$NOW_EPOCH" > "$LAST_CHECK_FILE" 2>/dev/null || true

# --- Parse + format -----------------------------------------------------
# Bail silently on unparseable response (server transient error).
THREAD_COUNT=$(python3 -c '
import sys, json
try:
    data = json.loads(sys.stdin.read())
    if isinstance(data, list):
        print(len(data))
    else:
        print(0)
except Exception:
    print(0)
' <<<"$RESPONSE" 2>/dev/null || echo 0)

if [ "$THREAD_COUNT" -eq 0 ]; then
    exit 0
fi

# Cap at 5 threads in the prompt to keep context tight when a queue builds up.
CAP="${PB_CHATROOM_HOOK_CAP:-5}"

FORMATTED=$(python3 -c "
import sys, json
data = json.loads(sys.stdin.read())
cap = $CAP
lines = []
for t in data[:cap]:
    tid = (t.get('id') or '')[:8]
    subj = (t.get('subject') or '(no subject)').replace('\n', ' ').strip()[:80]
    sender = t.get('created_by') or '?'
    last = t.get('last_message_at') or t.get('created_at') or ''
    lines.append(f'  - [{tid}] from={sender} subject={subj!r} last={last}')
overflow = len(data) - cap
if overflow > 0:
    lines.append(f'  ... +{overflow} more open thread(s)')
print('\n'.join(lines))
" <<<"$RESPONSE" 2>/dev/null)

if [ -z "$FORMATTED" ]; then
    exit 0
fi

# --- Emit context block --------------------------------------------------
# Output goes to stdout for the UserPromptSubmit hook and gets prepended
# to the user's prompt context — Claude sees this block before answering.
cat <<EOF
<pb-chatroom-inbox>
You have ${THREAD_COUNT} open chatroom thread(s) addressed to you (participant: ${PARTICIPANT}):
${FORMATTED}

To act on these:
  - mcp__chatroom__chat_read_thread(thread_id="<full-uuid>") — read full thread + messages
  - mcp__chatroom__chat_send(thread_id="<full-uuid>", body="<reply>") — post a reply
  - mcp__chatroom__chat_ack(thread_id="<full-uuid>", body="<closing>") — close the thread

Or via slash commands: /chat read <id>, /chat send <id> "msg", /chat ack <id> "summary".

Decide whether the user's current prompt requires you to act on these threads first,
or whether they can wait until after you answer the user. If you do read or respond,
do it at the start of your turn and continue with the user's actual question afterwards.
</pb-chatroom-inbox>
EOF
