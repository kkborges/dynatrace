# Dynatrace Metrics Dashboard - Setup & Usage Guide

## Overview

The Dynatrace Metrics Dashboard is a full-stack application that displays real-time metrics from Dynatrace. It consists of:
- **Backend**: FastAPI server that fetches metrics from Dynatrace API
- **Frontend**: React dashboard with Vite for displaying metrics and building custom dashboards

## Current Status

✅ **Dashboard Working with Test Data**
- The dashboard can display metrics correctly with sample data
- Metrics data parsing is verified and working
- All UI components render properly

⚠️ **Requires Dynatrace Credentials for Real Data**
- Currently using `/api/test/availability/dashboard` endpoint with mock data
- To use real Dynatrace data, you need to configure credentials

## Setup Instructions

### 1. Create Configuration File

Create a `.env` file in the root directory with your Dynatrace credentials:

```bash
cat > .env << 'EOF'
# Dynatrace Configuration
TENANT_URL=https://your-tenant.dynatrace.com
API_TOKEN=your-api-token-here

# Application Configuration
BACKEND_PORT=8000
FRONTEND_PORT=3000
EOF
```

**To get your credentials:**
1. Go to your Dynatrace environment
2. Navigate to: Settings → Integration → Dynatrace API
3. Create an API token with "Metrics API" scope
4. Copy your tenant URL (e.g., `https://abc123.live.dynatrace.com`)

### 2. Install Dependencies

```bash
# Backend dependencies (if needed)
pip install -r backend/requirements.txt

# Frontend dependencies
cd frontend
npm install
```

### 3. Switch from Test to Real Data

Edit `frontend/src/services/api.ts` and change:

```typescript
// Change this line:
const response = await this.api.get('/test/availability/dashboard');

// Back to:
const response = await this.api.get('/availability/dashboard');
```

### 4. Run the Application

**Start the Backend:**
```bash
python backend/main.py
```
The backend will run on http://localhost:8000

**Start the Frontend (in another terminal):**
```bash
cd frontend
npm run dev
```
The frontend will run on http://localhost:3000

## Dashboard Metrics

The main dashboard displays 4 host metrics:

1. **Host Availability** (`builtin:host.availability`)
   - Percentage of hosts currently available
   - Status: Green (≥95%), Yellow (≥80%), Red (<80%)

2. **CPU Usage** (`builtin:host.cpu.usage`)
   - Average CPU usage across all hosts
   - Displayed as percentage

3. **Memory Usage** (`builtin:host.mem.usage`)
   - Average memory usage across all hosts
   - Displayed as percentage

4. **Network Connectivity** (`builtin:host.net.nic.connectivity`)
   - Network interface connectivity status
   - Displayed as percentage

## Features

### Main Dashboard
- Real-time metrics display
- Color-coded status badges
- Refresh button to update metrics
- Last refresh timestamp
- Error handling with retry mechanism

### Custom Dashboard Builder (4-step workflow)
1. **Select Metrics** - Choose metrics to display
2. **Configure Display** - Set chart type and title
3. **Set Time Range** - Choose time window (1m, 5m, 15m, 30m, 1h, today, yesterday, 30days, custom)
4. **Test Dashboard** - Verify configuration before saving

### Chart Types Supported
- Line Chart
- Bar Chart
- Area Chart
- Scatter Plot
- Pie Chart
- Gauge Chart
- Candlestick Chart
- Heatmap

## Troubleshooting

### Dashboard Shows "N/A"
This typically means:
1. `.env` file is not configured with Dynatrace credentials
2. Using test endpoint (current setup)
3. Configure `.env` with real credentials and switch from test endpoint

### Backend Connection Error
```
Invalid URL '/api/v2/metrics/query': No scheme supplied
```
This means `TENANT_URL` is not set in `.env`. Make sure to:
1. Create `.env` file with `TENANT_URL`
2. Ensure URL format: `https://your-tenant.dynatrace.com` (no trailing slash)

### Port Already in Use
If port 3000 or 8000 is already in use:
```bash
# Backend: Change BACKEND_PORT in .env
# Frontend: Vite will automatically use 3001, 3002, etc.
```

### CORS Errors
The backend is configured to accept requests from:
- `http://localhost:3000`
- `http://localhost:5173`
- `http://127.0.0.1:3000`
- `http://127.0.0.1:5173`

## Testing with Mock Data

To test the dashboard without Dynatrace credentials:

1. Keep the endpoint as `/test/availability/dashboard` in `api.ts`
2. Run both servers (backend and frontend)
3. Access http://localhost:3000
4. You'll see sample metrics: Availability 99.8%, CPU 45.2%, Memory 72.5%, Network 98.9%

The mock data demonstrates:
- Correct data structure from Dynatrace API
- Proper frontend parsing of metrics
- Complete dashboard rendering with all features

## API Endpoints

### Core Endpoints
- `GET /api/health` - Health check
- `GET /api/dynatrace/validate` - Validate Dynatrace connection
- `GET /api/test/availability/dashboard` - Get mock dashboard data
- `GET /api/availability/dashboard` - Get real dashboard metrics (requires .env)
- `POST /api/metrics/refresh` - Refresh all available metrics
- `GET /api/metrics/list` - List cached metrics

### Dashboard Building
- `POST /api/metrics/data` - Get specific metric data
- `GET /api/metrics/validate/{metric_key}` - Check if metric exists
- `POST /api/dashboard/test` - Test dashboard configuration
- `GET /api/time-range/calculate` - Calculate timestamps for time ranges
- `GET /api/chart-types` - Get available chart types

## File Structure

```
dynatrace/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration (reads from .env)
│   ├── dynatrace_client.py  # Dynatrace API client
│   ├── entity_manager.py    # Entity ID to name mapping
│   └── models.py            # Pydantic data models
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── MainDashboard.tsx      # Main metrics display
│   │   │   └── CreateDashboard.tsx    # Custom dashboard builder
│   │   ├── components/
│   │   │   ├── Chart.tsx              # ECharts wrapper
│   │   │   └── MetricsSelector.tsx    # Metrics selection
│   │   ├── services/
│   │   │   └── api.ts                 # API client
│   │   ├── types/
│   │   │   └── index.ts               # TypeScript interfaces
│   │   └── App.tsx                    # Main application
│   └── vite.config.ts                 # Vite configuration
├── .env                     # Configuration (create from .env.example)
├── .env.example            # Example configuration
└── SETUP_GUIDE.md          # This file
```

## Development Notes

### Console Logging
When debugging data parsing issues, check the browser console (F12) for logs from `getMetricValue()` function. It logs:
- `Processing metric data:` - Incoming data structure
- `Data keys:` - Top-level keys in response
- `Result item keys:` - Keys in result[0]
- `Data item keys:` - Keys in result[0].data[0]
- `Found values/points:` - Which data format was matched

### Backend Logging
The backend logs metric queries to the console, showing:
```
Querying metric builtin:host.availability from ... to ...
  Result count: 1
  Result[0] keys: ['metricId', 'dataPointCountRatio', 'dimensionCountRatio', 'data']
  Result[0].data type: <class 'list'>, length: 1
  Result[0].data[0] keys: ['dimensions', 'timestamps', 'values']
    values: list with 3 items
```

## Next Steps

1. Configure `.env` with your Dynatrace credentials
2. Switch from test endpoint to real endpoint
3. Access the dashboard and verify metrics load
4. Use the Custom Dashboard Builder to create additional dashboards
5. Deploy to production as needed

## Support

For issues or questions:
1. Check the console logs (browser and backend)
2. Verify `.env` configuration
3. Ensure Dynatrace API credentials are correct
4. Check that the API token has "Metrics API" scope
