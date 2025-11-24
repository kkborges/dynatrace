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

## Host Metrics Dashboard

The main dashboard displays four key host metrics from your Dynatrace environment:

### Displayed Metrics
- **Host Availability**: `builtin:host.availability` - Percentage of hosts currently available
- **CPU Usage**: `builtin:host.cpu.usage` - Average CPU usage percentage across all hosts
- **Memory Usage**: `builtin:host.mem.usage` - Average memory usage percentage across all hosts
- **Network Connectivity**: `builtin:host.net.nic.connectivity` - Network interface connectivity status

All metrics are displayed as percentages (0-100%) with status indicators:
- **Healthy** (≥95%): Green badge
- **Warning** (≥80%): Yellow badge
- **Critical** (<80%): Red badge
- **Unknown** (no data): Gray badge

### API Response Structure

The `/api/availability/dashboard` endpoint returns:
```json
{
  "availability": { "result": [...] },
  "cpu_usage": { "result": [...] },
  "memory_usage": { "result": [...] },
  "network_connectivity": { "result": [...] }
}
```

Each metric follows the Dynatrace API v2 metrics/query response structure.

### Customizing Dashboard Metrics

To change which metrics are displayed, edit `backend/dynatrace_client.py`:

**To change a specific metric**, modify the corresponding method:
- `get_host_availability()` - Metric key: `builtin:host.availability`
- `get_host_cpu_usage()` - Metric key: `builtin:host.cpu.usage`
- `get_host_memory_usage()` - Metric key: `builtin:host.mem.usage`
- `get_host_network_connectivity()` - Metric key: `builtin:host.net.nic.connectivity`

Simply change the metric key string to any available Dynatrace metric.

**To add or remove dashboard cards**, update:
1. `backend/dynatrace_client.py` - Add/remove getter method
2. `backend/main.py` - Update `/api/availability/dashboard` endpoint to call new method
3. `frontend/src/pages/MainDashboard.tsx` - Add/remove metric card in the JSX

### Example: Replace Network Connectivity with Disk Space

1. Rename the method in `dynatrace_client.py`:
```python
def get_host_disk_usage(self, start_timestamp=None, end_timestamp=None):
    if start_timestamp is None or end_timestamp is None:
        import time
        now = int(time.time() * 1000)
        start_timestamp = now - (60 * 60 * 1000)
        end_timestamp = now

    return self.get_metric_data(
        "builtin:host.disk.usedSpace",  # Changed from builtin:host.net.nic.connectivity
        start_timestamp,
        end_timestamp,
        "1m"
    )
```

2. Update `main.py` endpoint:
```python
disk_data = dynatrace_client.get_host_disk_usage()  # Changed from network
return {
    "availability": availability_data,
    "cpu_usage": cpu_data,
    "memory_usage": memory_data,
    "disk_usage": disk_data,  # Changed from network_connectivity
}
```

3. Update the frontend component accordingly

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
