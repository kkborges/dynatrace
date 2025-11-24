#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Dynatrace Metrics Dashboard Starter${NC}"
echo -e "${GREEN}========================================${NC}"

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env file not found!${NC}"
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo -e "${YELLOW}Please edit .env with your Dynatrace credentials and run this script again.${NC}"
    exit 1
fi

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    exit 1
fi

# Check if Node is installed
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js is not installed${NC}"
    exit 1
fi

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo -e "${RED}❌ npm is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Python, Node.js, and npm are installed${NC}"

# Install backend dependencies if needed
if [ ! -d "backend/venv" ] && [ ! -f "backend/.venv" ]; then
    echo ""
    echo -e "${YELLOW}Installing backend dependencies...${NC}"
    cd backend
    pip install -q -r requirements.txt
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Backend dependencies installed${NC}"
    else
        echo -e "${RED}❌ Failed to install backend dependencies${NC}"
        exit 1
    fi
    cd ..
fi

# Install frontend dependencies if needed
if [ ! -d "frontend/node_modules" ]; then
    echo ""
    echo -e "${YELLOW}Installing frontend dependencies...${NC}"
    cd frontend
    npm install -q
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Frontend dependencies installed${NC}"
    else
        echo -e "${RED}❌ Failed to install frontend dependencies${NC}"
        exit 1
    fi
    cd ..
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Starting Application${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}Starting backend server...${NC}"
echo "URL: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo ""

# Start backend in background
cd backend
python main.py &
BACKEND_PID=$!
cd ..

sleep 2

# Check if backend started successfully
if ! ps -p $BACKEND_PID > /dev/null; then
    echo -e "${RED}❌ Failed to start backend${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Backend started (PID: $BACKEND_PID)${NC}"
echo ""
echo -e "${YELLOW}Starting frontend server...${NC}"
echo "URL: http://localhost:3000"
echo ""

# Start frontend
cd frontend
npm run dev

# Cleanup on exit
trap "kill $BACKEND_PID" EXIT
