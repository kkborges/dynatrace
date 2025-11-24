# Dynatrace Metrics Dashboard

A comprehensive dashboard application for monitoring Dynatrace metrics with custom visualization options and real-time data collection.

## Features

- **Main Dashboard**: View real-time availability metrics for:
  - Host availability
  - Application availability
  - Service availability

- **Custom Dashboard Creator**:
  - Select from all available Dynatrace metrics
  - Search and filter metrics with autocomplete
  - Choose from multiple chart types (common and modern)
  - Define custom time ranges
  - Test metrics before finalizing

- **Chart Types Available**:
  - Common: Line, Bar, Area, Scatter, Pie
  - Modern: Gauge, Candlestick, Heatmap

- **Time Range Options**:
  - Preset ranges: 1m, 5m, 15m, 30m, 1h
  - Quick ranges: Today, Yesterday, Last 30 Days
  - Custom date/time ranges

## Prerequisites

- Python 3.8+
- Node.js 16+
- npm or yarn
- Dynatrace API Token and Tenant URL

## Installation

### 1. Clone the Repository

```bash
cd dynatrace
```

### 2. Set Up Environment Variables

Create a `.env` file in the root directory:

```bash
cp .env.example .env
```

Edit `.env` with your Dynatrace credentials:

```
TENANT_URL=https://your-tenant.dynatrace.com
API_TOKEN=your-api-token-here
BACKEND_PORT=8000
FRONTEND_PORT=3000
```

### 3. Install Backend Dependencies

```bash
cd backend
pip install -r requirements.txt
cd ..
```

### 4. Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

## Running the Application

### Start the Backend

```bash
cd backend
python main.py
```

The backend will run on `http://localhost:8000`

API Documentation will be available at `http://localhost:8000/docs`

### Start the Frontend (in a new terminal)

```bash
cd frontend
npm run dev
```

The frontend will run on `http://localhost:3000`

## Usage

### Main Dashboard

1. Open `http://localhost:3000` in your browser
2. The main dashboard automatically displays:
   - Current host availability percentage
   - Current application availability percentage
   - Current service availability percentage
3. Click the "Refresh" button to update metrics

### Create Custom Dashboard

1. Click "Create Dashboard" in the navigation menu
2. **Step 1**: Select one or more metrics to visualize
   - Use the search box to find metrics quickly
   - Check the checkbox to select each metric
3. **Step 2**: Choose chart types for each metric
   - Browse common and modern chart options
   - Select the most appropriate visualization
4. **Step 3**: Select the time range
   - Use preset ranges for quick selection
   - Or select "Custom Date Range" for specific dates/times
5. **Step 4**: Review and test
   - See test results for each metric
   - View chart previews with actual data
   - Verify everything looks correct

## API Endpoints

### Health & Connection

- `GET /api/health` - Health check
- `GET /api/dynatrace/validate` - Validate Dynatrace connection

### Metrics

- `POST /api/metrics/refresh` - Refresh all metrics from Dynatrace
- `GET /api/metrics/list` - Get available metrics list
- `POST /api/metrics/data` - Get metric data for a specific metric

### Dashboard

- `GET /api/availability/dashboard` - Get availability metrics
- `POST /api/dashboard/test` - Test dashboard configuration

### Utilities

- `GET /api/time-range/calculate` - Calculate time range timestamps
- `GET /api/chart-types` - Get available chart types

## Project Structure

```
dynatrace/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration management
│   ├── dynatrace_client.py  # Dynatrace API client
│   ├── models.py            # Pydantic models
│   ├── requirements.txt     # Python dependencies
│   └── data/
│       └── metrics.json     # Cached metrics (auto-generated)
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── pages/          # Page components
│   │   ├── services/       # API services
│   │   ├── types/          # TypeScript types
│   │   ├── styles/         # Global styles
│   │   ├── App.tsx         # Main app component
│   │   └── main.tsx        # Entry point
│   ├── vite.config.ts      # Vite configuration
│   ├── tsconfig.json       # TypeScript configuration
│   ├── package.json        # Node dependencies
│   └── index.html          # HTML template
├── .env.example            # Environment variables template
└── README.md              # This file
```

## Troubleshooting

### Connection Error
- Verify TENANT_URL and API_TOKEN in `.env`
- Ensure Dynatrace API is accessible
- Check network connectivity

### No Metrics Found
- Ensure the API token has appropriate permissions
- Try clicking "Refresh Metrics" in the dashboard
- Check backend logs for API errors

### Chart Not Displaying
- Verify metric data is available in the selected time range
- Some metrics may not have data for the selected period
- Try a longer time range

### Port Already in Use
- Change BACKEND_PORT or FRONTEND_PORT in `.env`
- Or kill the process using the port:
  ```bash
  # For Linux/Mac
  lsof -ti:8000 | xargs kill -9
  lsof -ti:3000 | xargs kill -9

  # For Windows
  netstat -ano | findstr :8000
  taskkill /PID <PID> /F
  ```

## Development

### Backend Development

The backend uses FastAPI with automatic API documentation:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Frontend Development

The frontend uses React with Vite for fast development:
- Hot Module Replacement (HMR) enabled
- TypeScript for type safety
- ESLint for code quality

## Performance Notes

- Metrics are cached in `backend/data/metrics.json` after the first refresh
- Chart rendering uses ECharts for optimal performance
- Time range calculations are done client-side to reduce API calls

## License

This project is licensed under the MIT License.

## Support

For issues or questions, please contact your Dynatrace administrator or support team.
