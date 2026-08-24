#!/bin/bash
# Joidy API — comprehensive endpoint tests.
# Tests all major API endpoints with JWT auth.
# Usage: bash e2e/api-tests.sh

set -euo pipefail

API="http://localhost:8000"
PASS=0
FAIL=0
ERRORS=()

# Get JWT token
TOKEN=$(curl -s -X POST "$API/auth/login?password=root" | jq -r .access_token)
if [ "$TOKEN" = "null" ] || [ -z "$TOKEN" ]; then
  echo "FATAL: Could not obtain JWT token"
  exit 1
fi
AUTH="Authorization: Bearer $TOKEN"

# Helper: test an endpoint and check status
test_endpoint() {
  local method="$1"
  local path="$2"
  local expected_status="${3:-200}"
  local body="${4:-}"
  local label="${5:-$method $path}"

  local response
  local status
  if [ -n "$body" ]; then
    response=$(curl -s -w "\n%{http_code}" -X "$method" "$API$path" -H "$AUTH" -H "Content-Type: application/json" -d "$body" 2>&1)
  else
    response=$(curl -s -w "\n%{http_code}" -X "$method" "$API$path" -H "$AUTH" -H "Content-Type: application/json" 2>&1)
  fi
  status=$(echo "$response" | tail -1)
  local body_response=$(echo "$response" | head -n -1)

  if [ "$status" = "$expected_status" ]; then
    echo "  ✓ $label → $status"
    PASS=$((PASS + 1))
  else
    echo "  ✗ $label → $status (expected $expected_status)"
    echo "    Response: $(echo "$body_response" | head -c 200)"
    FAIL=$((FAIL + 1))
    ERRORS+=("$label: got $status, expected $expected_status")
  fi
}

echo "=========================================="
echo " Joidy API Tests"
echo "=========================================="
echo ""

echo "── Health & Auth ──"
test_endpoint GET "/health" 200 "" "Health check"
test_endpoint GET "/health/ready" 200 "" "Health ready"
test_endpoint GET "/auth/status" 200 "" "Auth status"
test_endpoint GET "/" 200 "" "API root"

echo ""
echo "── Notes ──"
test_endpoint GET "/notes/?limit=5" 200 "" "List notes (limit=5)"
test_endpoint GET "/notes/?limit=5&skip=0" 200 "" "List notes with skip"
test_endpoint GET "/notes/?source=joidy" 200 "" "List notes by source"

# Get a note ID for further tests
NOTE_ID=$(curl -s -H "$AUTH" "$API/notes/?limit=1" | jq -r '.[0].id // empty')
if [ -n "$NOTE_ID" ]; then
  test_endpoint GET "/notes/$NOTE_ID" 200 "" "Get note by ID"
  test_endpoint GET "/notes/$NOTE_ID/backlinks" 200 "" "Get note backlinks"
  test_endpoint GET "/notes/$NOTE_ID/similar" 200 "" "Get similar notes"
fi

# Create a test note
CREATE_RESPONSE=$(curl -s -X POST "$API/notes/" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"title":"E2E API Test Note","content":"Test content from API tests","tags":["e2e-test","api-test"]}')
CREATED_ID=$(echo "$CREATE_RESPONSE" | jq -r '.id // empty')
if [ -n "$CREATED_ID" ]; then
  echo "  ✓ Created test note ID=$CREATED_ID"
  PASS=$((PASS + 1))

  # Update the note
  test_endpoint PUT "/notes/$CREATED_ID" 200 '{"title":"Updated E2E Note","content":"Updated content"}' "Update note"

  # Delete the note (204 is valid for DELETE — No Content)
  test_endpoint DELETE "/notes/$CREATED_ID" 204 "" "Delete note"
else
  echo "  ✗ Failed to create test note"
  FAIL=$((FAIL + 1))
fi

echo ""
echo "── Tags ──"
test_endpoint GET "/tags/" 200 "" "List tags"
test_endpoint GET "/tags/graph" 200 "" "Tags graph"

echo ""
echo "── Goals ──"
test_endpoint GET "/goals/?limit=5" 200 "" "List goals"
test_endpoint GET "/goals/streak" 200 "" "Goal streak info"

# Get a goal ID for further tests
GOAL_ID=$(curl -s -H "$AUTH" "$API/goals/?limit=1" | jq -r '.[0].id // empty')
if [ -n "$GOAL_ID" ]; then
  test_endpoint GET "/goals/$GOAL_ID" 200 "" "Get goal by ID"
  test_endpoint GET "/goals/$GOAL_ID/content" 200 "" "Get goal content"
fi

# Create a test goal
GOAL_CREATE=$(curl -s -X POST "$API/goals/" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"title":"E2E Test Goal","description":"Test goal from API","temporality":"DAILY","measurement_type":"COUNT","target_value":1.0,"state":"ACTIVE","fail_config":"STATIC","color":"#c8a96e","theme":"solid"}')
GOAL_CREATED=$(echo "$GOAL_CREATE" | jq -r '.id // empty')
if [ -n "$GOAL_CREATED" ]; then
  echo "  ✓ Created test goal ID=$GOAL_CREATED"
  PASS=$((PASS + 1))
  # Delete it (204 is valid for DELETE)
  test_endpoint DELETE "/goals/$GOAL_CREATED" 204 "" "Delete test goal"
else
  echo "  ✗ Failed to create test goal"
  FAIL=$((FAIL + 1))
fi

echo ""
echo "── Skills ──"
test_endpoint GET "/skills/" 200 "" "List skills"
test_endpoint GET "/skills/tree" 200 "" "Skills tree"
test_endpoint POST "/skills/sync" 200 "" "Sync skills"

echo ""
echo "── Gamification ──"
test_endpoint GET "/gamification/stats" 200 "" "Gamification stats"
test_endpoint GET "/gamification/streak-history" 200 "" "Streak history"
test_endpoint GET "/gamification/recent-events" 200 "" "Recent XP events"

echo ""
echo "── Personal Streaks ──"
test_endpoint GET "/personal-streaks/" 200 "" "List streaks"
test_endpoint GET "/personal-streaks/categories" 200 "" "Streak categories"
test_endpoint GET "/personal-streaks/stats" 200 "" "Streak stats"

# Get a streak ID for further tests
STREAK_ID=$(curl -s -H "$AUTH" "$API/personal-streaks/?include_archived=false" | jq -r '.[0].id // empty')
if [ -n "$STREAK_ID" ]; then
  test_endpoint GET "/personal-streaks/$STREAK_ID/history" 200 "" "Streak history by ID"
fi

echo ""
echo "── Mood ──"
test_endpoint GET "/mood/today" 200 "" "Get today's mood"
test_endpoint GET "/mood/history" 200 "" "Mood history"
test_endpoint GET "/mood/stats" 200 "" "Mood stats"
test_endpoint POST "/mood/" 200 '{"score":4,"note":"E2E test mood"}' "Create mood entry"

echo ""
echo "── AI ──"
test_endpoint GET "/ai/usage" 200 "" "AI usage stats"

echo ""
echo "── Sync ──"
test_endpoint GET "/sync/conflicts" 200 "" "Sync conflicts"
test_endpoint GET "/sync/status" 200 "" "Sync status"

echo ""
echo "── Export ──"
test_endpoint GET "/export/notes/markdown" 200 "" "Export markdown"
test_endpoint GET "/export/notes/html" 200 "" "Export HTML"

echo ""
echo "── Analytics ──"
test_endpoint GET "/analytics/dashboard" 200 "" "Analytics dashboard"
test_endpoint GET "/analytics/usage" 200 "" "Analytics usage"

echo ""
echo "── Config ──"
test_endpoint GET "/config" 200 "" "Get config"
test_endpoint GET "/config/keys" 200 "" "Config keys"
test_endpoint GET "/config/gamification" 200 "" "Gamification config"
test_endpoint GET "/config/setup-status" 200 "" "Setup status"

echo ""
echo "── Stats ──"
test_endpoint GET "/stats/system" 200 "" "System stats"
test_endpoint GET "/stats/activity" 200 "" "Activity stats"

echo ""
echo "── Planning ──"
TODAY=$(date +%Y-%m-%d)
test_endpoint GET "/planning/assignments?date=$TODAY" 200 "" "Planning assignments (today)"

echo ""
echo "── Integrations ──"
test_endpoint GET "/integrations/github/status" 200 "" "GitHub status"

echo ""
echo "── Push ──"
test_endpoint GET "/push/vapid-public-key" 200 "" "VAPID public key"

echo ""
echo "── Metrics ──"
test_endpoint GET "/metrics" 200 "" "Prometheus metrics"

echo ""
echo "=========================================="
echo " Results: $PASS passed, $FAIL failed"
echo "=========================================="

if [ ${#ERRORS[@]} -gt 0 ]; then
  echo ""
  echo "Failures:"
  for err in "${ERRORS[@]}"; do
    echo "  - $err"
  done
fi

exit $FAIL
