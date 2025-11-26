# Quick Start - Test the Dashboard in 2 Minutes

## Option 1: Test with Mock Data (No Credentials Needed)

The dashboard is pre-configured to work with mock data out of the box.

### Start the Backend:
```bash
python backend/main.py
```

### Start the Frontend (in another terminal):
```bash
cd frontend
npm run dev
```

### View the Dashboard:
Open your browser to `http://localhost:3000`

You'll see a dashboard with:
- **Host Availability**: 99.80%
- **CPU Usage**: 45.20%
- **Memory Usage**: 72.50%
- **Network Connectivity**: 98.90%

All metrics are clickable, have status badges, and the refresh button works!

---

## Option 2: Use Your Dynatrace Instance

### 1. Create `.env` file:
```bash
cat > .env << 'EOF'
TENANT_URL=https://your-tenant.dynatrace.com
API_TOKEN=your-api-token-here
BACKEND_PORT=8000
FRONTEND_PORT=3000
EOF
```

### 2. Edit frontend API client:
Open `frontend/src/services/api.ts` and change line 88 from:
```typescript
const response = await this.api.get('/test/availability/dashboard');
```
to:
```typescript
const response = await this.api.get('/availability/dashboard');
```

### 3. Run the application:
```bash
# Terminal 1
python backend/main.py

# Terminal 2
cd frontend
npm run dev
```

### 4. Open the dashboard:
`http://localhost:3000`

---

## What's Working

✅ **Dashboard Display**
- Metrics load from backend
- Values parse correctly
- Status badges show color-coded health

✅ **Data Parsing**
- Frontend correctly extracts values from Dynatrace API response
- Supports multiple response formats
- Fallback handling for edge cases

✅ **Error Handling**
- Graceful error display with retry button
- Loading state while fetching
- Detailed backend logging for debugging

✅ **Features**
- Refresh button updates all metrics
- Shows last refresh time
- Status-based color coding
- Responsive layout

---

## Debugging

### Check Backend Logs
When metrics are loaded, you'll see logs like:
```
Querying metric builtin:host.availability from ... to ...
  Result count: 1
  Result[0] keys: ['metricId', 'dataPointCountRatio', 'dimensionCountRatio', 'data']
  Result[0].data type: <class 'list'>, length: 1
```

### Check Frontend Console (F12)
The dashboard logs detailed parsing information:
```
Processing metric data: {totalCount: 1, resolution: "1m", result: Array(1)}
Data keys: ['totalCount', 'resolution', 'result']
Result item keys: ['metricId', 'dataPointCountRatio', 'dimensionCountRatio', 'data']
Data item keys: ['dimensions', 'timestamps', 'values']
Found values, last value: [99.8]
```

### Common Issues

**"N/A" displayed for metrics:**
- Currently using test endpoint (expected with mock data)
- Configure `.env` with real credentials to see actual values

**Connection refused:**
- Backend not running on port 8000
- Check if `python backend/main.py` is still running

**Port already in use:**
- Change port in `.env`: `BACKEND_PORT=8001`
- Frontend will automatically use 3001, 3002, etc. if 3000 is taken

---

## Next: Custom Dashboards

Once the main dashboard is working, click "Create Dashboard" to:
1. Select specific metrics
2. Choose chart type (line, bar, area, pie, gauge, etc.)
3. Set time range (1m, 5m, 1h, today, custom range)
4. Test before saving

Enjoy your Dynatrace metrics dashboard! 📊
