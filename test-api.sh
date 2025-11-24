#!/bin/bash

# Script para testar a API do Dynatrace e listar métricas válidas

if [ -z "$TENANT_URL" ] || [ -z "$API_TOKEN" ]; then
    # Tenta carregar do .env
    if [ -f ".env" ]; then
        export $(grep -v '^#' .env | xargs)
    fi
fi

if [ -z "$TENANT_URL" ] || [ -z "$API_TOKEN" ]; then
    echo "Error: TENANT_URL and API_TOKEN environment variables must be set"
    exit 1
fi

TENANT_URL="${TENANT_URL%/}"  # Remove trailing slash if present

echo "=========================================="
echo "Dynatrace API Testing Script"
echo "=========================================="
echo "Tenant URL: $TENANT_URL"
echo ""

# Test 1: Validate connection
echo "1. Testing connection to Dynatrace API..."
RESPONSE=$(curl -s -w "\n%{http_code}" \
  -H "Api-Token: $API_TOKEN" \
  "$TENANT_URL/api/v2/metrics?pageSize=1")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Connection successful!"
    TOTAL_COUNT=$(echo "$BODY" | grep -o '"totalCount":[0-9]*' | cut -d: -f2)
    echo "   Total metrics available: $TOTAL_COUNT"
else
    echo "❌ Connection failed (HTTP $HTTP_CODE)"
    echo "Response: $BODY"
    exit 1
fi

echo ""
echo "2. Fetching first 10 metrics..."
RESPONSE=$(curl -s -H "Api-Token: $API_TOKEN" \
  "$TENANT_URL/api/v2/metrics?pageSize=10")

echo "Metrics:"
echo "$RESPONSE" | grep -o '"metricId":"[^"]*"' | cut -d'"' -f4 | nl

echo ""
echo "3. Example of valid metrics to query:"
echo "   - builtin:host.cpu.usage"
echo "   - builtin:host.memory.usage"
echo "   - builtin:host.disk.usedSpace"
echo "   - builtin:host.availability"
echo "   - builtin:app.web.httpRequests.overall"
echo "   - builtin:service.requestCount.total"

echo ""
echo "4. Testing metric query..."
METRIC_SELECTOR="builtin:host.cpu.usage"
FROM=$(date -u -d "1 hour ago" +%Y-%m-%dT%H:%M:%S 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%S)
TO=$(date -u +%Y-%m-%dT%H:%M:%S)

echo "   Metric: $METRIC_SELECTOR"
echo "   From: $FROM"
echo "   To: $TO"
echo ""

RESPONSE=$(curl -s -w "\n%{http_code}" -H "Api-Token: $API_TOKEN" \
  "$TENANT_URL/api/v2/metrics/query?metricSelector=$METRIC_SELECTOR&resolution=5m&from=$FROM&to=$TO")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Query successful!"
    echo "Response:"
    echo "$BODY" | head -20
else
    echo "❌ Query failed (HTTP $HTTP_CODE)"
    echo "Response: $BODY"
fi

echo ""
echo "=========================================="
echo "Testing complete"
echo "=========================================="
