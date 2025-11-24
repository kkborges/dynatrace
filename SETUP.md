# Setup Guide - Dynatrace Metrics Dashboard

## Quick Start Guide

### Prerequisites
- Python 3.8+
- Node.js 16+
- Dynatrace Tenant URL and API Token

### Step 1: Configure Environment Variables

Create a `.env` file in the root directory:

```bash
cp .env.example .env
```

Edit `.env` with your Dynatrace credentials:

```
TENANT_URL=https://your-tenant.live.dynatrace.com
API_TOKEN=your-api-token-here
BACKEND_PORT=8000
FRONTEND_PORT=3000
```

**Important**: Make sure your `TENANT_URL` is correct:
- Example: `https://abc12345.live.dynatrace.com` (note: no trailing slash)
- Should include the protocol (`https://`)

### Step 2: Install Backend Dependencies

```bash
cd backend
pip install -r requirements.txt
cd ..
```

### Step 3: Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

## Running the Application

### Terminal 1 - Start Backend

```bash
cd backend
python main.py
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

API documentation will be available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Terminal 2 - Start Frontend

```bash
cd frontend
npm run dev
```

You should see:
```
  VITE v5.0.8  ready in 123 ms

  ➜  Local:   http://localhost:3000/
  ➜  press h to show help
```

Open http://localhost:3000 in your browser.

## Accessing from Another Machine

If you want to access the application from another machine on your network:

### Update Frontend Proxy (if backend is on different machine)

Edit `frontend/vite.config.ts`:

```typescript
proxy: {
  '/api': {
    target: 'http://your-backend-ip:8000',  // Change to backend machine IP
    changeOrigin: true,
    rewrite: (path) => path,
  }
}
```

Then restart the frontend.

### Or Use Production Build

Build frontend for production:
```bash
cd frontend
npm run build
cd ..
```

This creates a `frontend/dist` folder with static files.

## Troubleshooting

### Issue: Connection Error (400 Bad Request)

**Symptoms:**
```
GET http://192.168.0.20:3000/api/dynatrace/validate 400 (Bad Request)
```

**Solution:**
1. Ensure backend is running: `python backend/main.py`
2. Check TENANT_URL in `.env` is correct (should start with `https://`)
3. Check API_TOKEN is valid
4. Verify backend can reach Dynatrace:
   ```bash
   curl -H "Api-Token: YOUR_TOKEN" https://your-tenant.live.dynatrace.com/api/v2/metrics
   ```

### Issue: Port Already in Use

**Error:**
```
ERROR: Address already in use
```

**Solution:**
```bash
# Find process using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or change port in .env
BACKEND_PORT=8001
FRONTEND_PORT=3001
```

### Issue: CORS Error

**Symptoms:**
```
Access to XMLHttpRequest at 'http://localhost:8000/api/dynatrace/validate'
from origin 'http://localhost:3000' has been blocked by CORS policy
```

**Solution:**
- This shouldn't happen if using Vite proxy
- Restart frontend dev server
- Make sure vite.config.ts has correct proxy configuration

### Issue: No Metrics Displayed

**Solutions:**
1. Click "Refresh Metrics" button in Create Dashboard page
2. Check backend logs for API errors
3. Verify API token has "Read metrics" permission in Dynatrace
4. Try manually testing API endpoint:
   ```bash
   curl -H "Api-Token: YOUR_TOKEN" \
     "https://your-tenant.live.dynatrace.com/api/v2/metrics"
   ```

### Issue: Module Not Found Error

**Example:**
```
ModuleNotFoundError: No module named 'requests'
```

**Solution:**
```bash
cd backend
pip install -r requirements.txt
python main.py
```

### Issue: npm Command Not Found

**Solution:**
Make sure Node.js is installed:
```bash
node --version  # Should be v16+
npm --version   # Should be 8+
```

If not installed, download from https://nodejs.org/

## Development

### Frontend Development Mode

Frontend runs in hot-reload mode:
- Changes to `.tsx` or `.css` files reload automatically
- No need to restart server

### Backend Development Mode

Backend runs with auto-reload:
- Changes to `.py` files reload automatically
- If not working, restart with `python main.py`

### Backend API Documentation

While backend is running, visit:
- http://localhost:8000/docs (interactive Swagger UI)
- http://localhost:8000/redoc (ReDoc)

### Debug Logging

#### Backend Logs

Backend prints debug info to console. For more details:

```bash
cd backend
# Edit main.py to change log level
```

#### Frontend Logs

Browser console (F12):
- Network tab: See all API requests
- Console tab: See JavaScript errors

## Performance Notes

- Metrics are cached in `backend/data/metrics.json`
- Entities are cached in `backend/data/entities.json`
- First metrics refresh may take 10-30 seconds (1000+ metrics)
- Subsequent requests are much faster due to caching

## Production Deployment

### Build Frontend

```bash
cd frontend
npm run build
```

Creates optimized build in `frontend/dist/`

### Deploy Options

1. **Backend + Frontend on same server:**
   - Serve `frontend/dist` files with Nginx
   - Backend runs on port 8000
   - Proxy `/api` requests to backend

2. **Backend and Frontend on different servers:**
   - Deploy frontend to web server
   - Update `VITE_API_URL` in frontend `.env`
   - Deploy backend to separate server

3. **Docker:**
   - Create Dockerfile for backend (Python FastAPI)
   - Create Dockerfile for frontend (Node.js build)
   - Use docker-compose for orchestration

## Getting Help

### Check Logs

1. **Backend logs**: Console output when running `python main.py`
2. **Frontend logs**: Browser DevTools → Console
3. **API errors**: Check HTTP response in Network tab

### Test API Directly

```bash
# Test connection
curl -v -H "Api-Token: YOUR_TOKEN" \
  https://your-tenant.live.dynatrace.com/api/v2/metrics | head -20

# Should see:
# {"totalCount": 239, "nextPageKey": "...", "metrics": [...]}
```

### Common Dynatrace API Issues

1. **401 Unauthorized**: API token is invalid or expired
2. **403 Forbidden**: API token lacks required permissions
3. **404 Not Found**: Entity ID or metric doesn't exist
4. **429 Too Many Requests**: Rate limit exceeded

## File Structure

```
dynatrace/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration management
│   ├── dynatrace_client.py  # Dynatrace API client
│   ├── entity_manager.py    # Entity mapping cache
│   ├── models.py            # Pydantic models
│   ├── requirements.txt     # Python dependencies
│   └── data/
│       ├── metrics.json     # Cached metrics
│       └── entities.json    # Entity ID mapping
│
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── pages/          # Page components
│   │   ├── services/       # API client
│   │   ├── config/         # Configuration
│   │   ├── types/          # TypeScript types
│   │   ├── styles/         # Global styles
│   │   ├── App.tsx         # Main app component
│   │   └── main.tsx        # Entry point
│   ├── vite.config.ts      # Vite configuration
│   ├── tsconfig.json       # TypeScript configuration
│   ├── package.json        # Node dependencies
│   ├── .env.example        # Frontend env template
│   └── index.html          # HTML template
│
├── .env.example            # Backend env template
├── .env                    # (create this file) Backend config
├── SETUP.md               # This file
└── README.md              # Project documentation
```

## Next Steps

1. ✅ Configure `.env` file with Dynatrace credentials
2. ✅ Install dependencies (backend + frontend)
3. ✅ Run backend: `python backend/main.py`
4. ✅ Run frontend: `npm run dev` (from frontend folder)
5. ✅ Open http://localhost:3000
6. ✅ Create your first custom dashboard!
