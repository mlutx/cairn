#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Cairn Development Environment...${NC}"

# Function to cleanup background processes
cleanup() {
    echo -e "\n${YELLOW}Shutting down servers...${NC}"

    # Kill the FastAPI server
    if [ ! -z "$FASTAPI_PID" ]; then
        kill $FASTAPI_PID 2>/dev/null
        echo -e "${GREEN}FastAPI server stopped${NC}"
    fi

    # Kill any remaining node processes for this project
    pkill -f "vite" 2>/dev/null

    echo -e "${GREEN}Cleanup complete${NC}"
    exit 0
}

# Set up trap to call cleanup function on script exit
trap cleanup EXIT INT TERM

# Start FastAPI backend in background
echo -e "${GREEN}Starting FastAPI backend...${NC}"
python fastapi_app/app.py &
FASTAPI_PID=$!

# Wait a moment for FastAPI to start
sleep 2

# Check if FastAPI is running
if kill -0 $FASTAPI_PID 2>/dev/null; then
    echo -e "${GREEN}FastAPI backend started successfully (PID: $FASTAPI_PID)${NC}"
else
    echo -e "${RED}Failed to start FastAPI backend${NC}"
    exit 1
fi

# Start frontend development server
echo -e "${GREEN}Starting frontend development server...${NC}"
cd frontend

# Wait a bit more for backend to be fully ready
sleep 3

# Open browser (works on macOS, Linux, and Windows)
echo -e "${GREEN}Opening browser at http://localhost:5173/${NC}"
if command -v open >/dev/null 2>&1; then
    # macOS
    open http://localhost:5173/ &
elif command -v xdg-open >/dev/null 2>&1; then
    # Linux
    xdg-open http://localhost:5173/ &
elif command -v start >/dev/null 2>&1; then
    # Windows
    start http://localhost:5173/ &
fi

# Start the frontend (this will run in foreground)
echo -e "${GREEN}Frontend starting...${NC}"
npm run dev

# Note: The script will end here when npm run dev is terminated (Ctrl+C)
# The cleanup function will automatically run due to the trap
