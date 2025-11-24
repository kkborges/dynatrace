# Dynatrace Metrics Guide

## Common Valid Metrics

### Host Metrics
- `builtin:host.cpu.usage` - CPU usage percentage
- `builtin:host.memory.usage` - Memory usage percentage
- `builtin:host.disk.usedSpace` - Disk space used
- `builtin:host.availability` - Host availability (recommended for dashboard)
- `builtin:host.network.io.read` - Network read operations
- `builtin:host.network.io.write` - Network write operations
- `builtin:host.processes.count` - Process count

### Application Metrics
- `builtin:app.web.httpRequests.overall` - HTTP requests count
- `builtin:app.web.httpRequests.successful` - Successful requests (good indicator of availability)
- `builtin:app.web.httpRequests.clientErrors` - Client errors (4xx)
- `builtin:app.web.httpRequests.serverErrors` - Server errors (5xx) (inverse indicator of availability)
- `builtin:app.web.requestResponseTime.overall` - Response time

### Service Metrics
- `builtin:service.requestCount.total` - Total service requests
- `builtin:service.errorCount.total` - Total service errors (inverse indicator of availability)
- `builtin:service.requestCount.server` - Server-side requests
- `builtin:service.requestCount.client` - Client-side requests
- `builtin:service.responseTime` - Service response time

### Database Metrics
- `builtin:databases.mysql.resultSetSize` - MySQL result set size
- `builtin:databases.mysql.queriesPerSecond` - MySQL queries per second
- `builtin:databases.postgresql.databaseSize` - PostgreSQL database size

### Custom Metrics
Any custom metrics you have created in your Dynatrace environment following the naming convention:
- `custom:<metric_name>`

## Testing Metrics

### Option 1: Using the provided shell script

```bash
# Linux/macOS
chmod +x test-api.sh
./test-api.sh

# This will:
# 1. Test connection to Dynatrace
# 2. List first 10 metrics
# 3. Test a sample metric query
```

### Option 2: Manual cURL testing

```bash
# Set your credentials
export TENANT_URL="https://your-tenant.live.dynatrace.com"
export API_TOKEN="your-api-token"

# List metrics
curl -H "Api-Token: $API_TOKEN" \
  "$TENANT_URL/api/v2/metrics?pageSize=10"

# Query specific metric
curl -H "Api-Token: $API_TOKEN" \
  "$TENANT_URL/api/v2/metrics/query?metricSelector=builtin:host.cpu.usage&resolution=5m&from=2025-11-24T12:00:00&to=2025-11-24T13:00:00"
```

### Option 3: Using the dashboard API

The application provides endpoints to validate metrics:

```bash
# Refresh metrics from Dynatrace
curl -X POST http://localhost:8000/api/metrics/refresh

# Validate a specific metric
curl http://localhost:8000/api/metrics/validate/builtin:host.cpu.usage

# Get all cached metrics
curl http://localhost:8000/api/metrics/list

# Query metric data
curl -X POST http://localhost:8000/api/metrics/data \
  -H "Content-Type: application/json" \
  -d '{
    "metric_key": "builtin:host.cpu.usage",
    "start_timestamp": 1732445400000,
    "end_timestamp": 1732449000000,
    "resolution": "5m"
  }'
```

## Important Notes

### Metric Name Format
- Always use the exact metric name as provided by Dynatrace
- Names are case-sensitive
- Use colons `:` to separate namespaces (e.g., `builtin:host.cpu.usage`)
- Do NOT use spaces in metric names

### Time Resolution
Valid resolution values:
- `1m` - 1 minute intervals
- `5m` - 5 minute intervals
- `15m` - 15 minute intervals
- `30m` - 30 minute intervals
- `1h` - 1 hour intervals
- `1d` - 1 day intervals

### Time Format
- Use ISO 8601 format: `YYYY-MM-DDTHH:MM:SS`
- Example: `2025-11-24T12:00:00`
- Always use UTC time
- The backend automatically converts millisecond timestamps to this format

### Pagination
When fetching metrics list, the API returns paginated results:
- Maximum items per page: 500
- Use `nextPageKey` parameter to fetch next page
- Continue until `nextPageKey` is null

Example:
```bash
# First page
curl -H "Api-Token: $API_TOKEN" \
  "$TENANT_URL/api/v2/metrics?pageSize=100"

# Next page (if nextPageKey is present in response)
curl -H "Api-Token: $API_TOKEN" \
  "$TENANT_URL/api/v2/metrics?pageSize=100&pageKey=<nextPageKey_value>"
```

## Availability Dashboard Configuration

The main dashboard displays three key availability metrics automatically calculated from Dynatrace data:

### Current Implementation
- **Host Availability**: `builtin:host.availability` - Direct percentage from Dynatrace
- **Application Availability**: Calculated as `(successful_requests / overall_requests) * 100`
  - Sources: `builtin:app.web.httpRequests.successful` and `builtin:app.web.httpRequests.overall`
  - Falls back to total request count if success metric unavailable
- **Service Availability**: Calculated as `((total_requests - error_count) / total_requests) * 100`
  - Sources: `builtin:service.requestCount.total` and `builtin:service.errorCount.total`
  - Falls back to total request count if error metric unavailable

### How Availability Metrics Work

**Application Success Rate:**
The dashboard automatically calculates application availability by comparing successful HTTP requests to total requests:
1. Fetches `builtin:app.web.httpRequests.successful` (successful requests)
2. Fetches `builtin:app.web.httpRequests.overall` (total requests)
3. Calculates: (successful / total) × 100 = percentage
4. If either metric is unavailable, displays total request count as fallback

**Service Success Rate:**
The dashboard calculates service availability by comparing total requests to errors:
1. Fetches `builtin:service.requestCount.total` (total requests)
2. Fetches `builtin:service.errorCount.total` (error count)
3. Calculates: ((total - errors) / total) × 100 = percentage
4. Clamps result to 0-100 range
5. If either metric is unavailable, displays total request count as fallback

### Customizing Availability Metrics

To modify the availability calculations, edit `backend/dynatrace_client.py`:

**For Applications**, modify the `get_application_availability()` method:
- Change which metrics are fetched in the `get_metric_data()` calls
- Modify the calculation logic in `_calculate_success_rate()`

**For Services**, modify the `get_service_availability()` method:
- Change which metrics are fetched in the `get_metric_data()` calls
- Modify the calculation logic in `_calculate_availability_from_errors()`

**To add different metrics entirely**, use these helper methods as patterns:
- `_extract_latest_value()` - Extracts the most recent value from any metric response
- `_calculate_success_rate()` - Template for calculating percentages from two metrics
- `_calculate_availability_from_errors()` - Template for calculating from count difference

## Troubleshooting

### Error: 404 Not Found
**Cause**: Metric name is incorrect or doesn't exist

**Solution**:
1. Run `./test-api.sh` to list available metrics
2. Verify exact metric name spelling
3. Refresh metrics in the application: click "Refresh Metrics" button

### Error: 400 Bad Request
**Cause**: Invalid timestamp format or time range

**Solution**:
1. Use ISO 8601 format: `YYYY-MM-DDTHH:MM:SS`
2. Ensure `from` timestamp is before `to` timestamp
3. Use UTC time zone

### Error: 403 Forbidden
**Cause**: API token lacks permissions

**Solution**:
1. Verify API token has "Read metrics" permission
2. Check token expiration date
3. Generate new token with correct scopes

### No Data Returned
**Cause**: No data available for the selected time range

**Solution**:
1. Try a longer time range
2. Verify the metric has data in that period
3. Check if data collection is enabled for that metric

## Entity IDs in Metrics

When querying metrics, results may include `entityId` values that represent:
- Host IDs: `HOST-xxx`
- Service IDs: `SERVICE-xxx`
- Application IDs: `APPLICATION-xxx`

The application automatically resolves these to display names and caches them in `entities.json`.

## Performance Tips

1. **Use appropriate resolution**: Larger time ranges should use lower resolution (e.g., `1h`)
2. **Cache metrics list**: The application caches metrics in `metrics.json` after first refresh
3. **Batch queries**: When possible, query multiple metrics in a single request
4. **Optimize time ranges**: Narrower time ranges return results faster

## API Rate Limits

Dynatrace API has rate limits:
- Check response headers: `X-RateLimit-Limit` and `X-RateLimit-Remaining`
- Default limit: 500 requests per minute
- If limit exceeded, wait before retrying

## Reference

- [Dynatrace API v2 Documentation](https://www.dynatrace.com/support/help/dynatrace-api/environment-api/metric-api)
- [Metrics Query Language](https://www.dynatrace.com/support/help/dynatrace-api/environment-api/metric-api/metric-selector-syntax)
- [Available Metrics](https://www.dynatrace.com/support/help/technology-support/supported-technologies)
