#!/bin/bash

# Test availability dashboard endpoint
echo "Testing availability dashboard endpoint..."
echo "=========================================="

API_URL="http://localhost:8000"

echo ""
echo "Requesting /api/availability/dashboard..."
curl -v -X GET "$API_URL/api/availability/dashboard" 2>&1 | tee /tmp/availability-response.txt

echo ""
echo ""
echo "Response saved to /tmp/availability-response.txt"
echo ""
echo "Formatted response:"
curl -s -X GET "$API_URL/api/availability/dashboard" | python3 -m json.tool 2>/dev/null || echo "Failed to parse JSON"
