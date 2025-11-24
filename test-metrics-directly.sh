#!/bin/bash

# Test specific metrics directly
# This tests the exact metrics used in the availability dashboard

TENANT_URL=${TENANT_URL:-""}
API_TOKEN=${API_TOKEN:-""}

if [ -z "$TENANT_URL" ] || [ -z "$API_TOKEN" ]; then
    echo "Error: TENANT_URL and API_TOKEN environment variables must be set"
    exit 1
fi

# Get current time in milliseconds
NOW_MS=$(date +%s)000
ONE_HOUR_AGO_MS=$((NOW_MS - 3600000))

echo "Testing availability metrics directly from Dynatrace API"
echo "========================================================"
echo ""
echo "Time range: $ONE_HOUR_AGO_MS to $NOW_MS"
echo ""

# Test host availability metric
echo "1. Testing builtin:host.availability"
echo "======================================"
curl -s -X GET \
  "$TENANT_URL/api/v2/metrics/query" \
  -H "Authorization: Api-Token $API_TOKEN" \
  -H "Content-Type: application/json" \
  --data-urlencode "metricSelector=builtin:host.availability" \
  --data-urlencode "from=$ONE_HOUR_AGO_MS" \
  --data-urlencode "to=$NOW_MS" \
  --data-urlencode "resolution=1m" | python3 -m json.tool

echo ""
echo ""

# Test application metrics
echo "2. Testing builtin:app.web.httpRequests.overall"
echo "================================================"
curl -s -X GET \
  "$TENANT_URL/api/v2/metrics/query" \
  -H "Authorization: Api-Token $API_TOKEN" \
  -H "Content-Type: application/json" \
  --data-urlencode "metricSelector=builtin:app.web.httpRequests.overall" \
  --data-urlencode "from=$ONE_HOUR_AGO_MS" \
  --data-urlencode "to=$NOW_MS" \
  --data-urlencode "resolution=1m" | python3 -m json.tool

echo ""
echo ""

# Test service metrics
echo "3. Testing builtin:service.requestCount.total"
echo "=============================================="
curl -s -X GET \
  "$TENANT_URL/api/v2/metrics/query" \
  -H "Authorization: Api-Token $API_TOKEN" \
  -H "Content-Type: application/json" \
  --data-urlencode "metricSelector=builtin:service.requestCount.total" \
  --data-urlencode "from=$ONE_HOUR_AGO_MS" \
  --data-urlencode "to=$NOW_MS" \
  --data-urlencode "resolution=1m" | python3 -m json.tool
