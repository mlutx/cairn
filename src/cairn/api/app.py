"""
Simplified FastAPI application for Cairn.

This module provides a FastAPI application factory that serves both the API
endpoints and the frontend, properly integrated with the Cairn package structure.
"""

import asyncio
import json
import logging
import os
import sqlite3
import sys
import threading
import time
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Import from the package structure
from cairn.worker_manager import WorkerManager
from cairn_utils.supported_models import SUPPORTED_MODELS

# Load environment variables
load_dotenv('.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Global state
worker_manager: Optional[WorkerManager] = None
background_loop: Optional[asyncio.AbstractEventLoop] = None
background_thread: Optional[threading.Thread] = None

def get_project_root() -> Path:
    """Get the project root directory."""
    # From src/cairn/api/app.py, go up to project root
    return Path(__file__).parent.parent.parent.parent.absolute()

def get_db_path() -> Path:
    """Get the database path."""
    return get_project_root() / "cairn_tasks.db"

def get_static_dir() -> Path:
    """Get the static directory."""
    return get_project_root() / "static"

def get_frontend_dist_dir() -> Path:
    """Get the frontend dist directory."""
    return Path(__file__).parent.parent / "frontend" / "dist"

def get_db_connection():
    """Get database connection with proper settings."""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")

    # Initialize database schema if needed
    try:
        # Check if active_tasks table exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='active_tasks'")
        if not cursor.fetchone():
            logger.info("Creating active_tasks table")
            conn.execute("""
                CREATE TABLE active_tasks (
                    task_id TEXT PRIMARY KEY,
                    payload TEXT,
                    run_id TEXT,
                    agent_type TEXT,
                    agent_status TEXT,
                    agent_output TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

        # Check if task_logs table exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='task_logs'")
        if not cursor.fetchone():
            logger.info("Creating task_logs table")
            conn.execute("""
                CREATE TABLE task_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    agent_type TEXT,
                    log_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

        # Check if debug_messages table exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='debug_messages'")
        if not cursor.fetchone():
            logger.info("Creating debug_messages table")
            conn.execute("""
                CREATE TABLE debug_messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

        conn.commit()
        logger.info("Database schema initialization completed")
    except Exception as e:
        logger.error(f"Error initializing database schema: {e}")
        raise

    return conn

def run_background_loop():
    """Run the background event loop for processing WorkerManager tasks."""
    global background_loop
    try:
        background_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(background_loop)
        worker_manager.loop = background_loop
        logger.info("Background event loop started for WorkerManager")

        def exception_handler(loop, context):
            exception = context.get('exception')
            logger.error(f"Background loop exception: {exception}")

        background_loop.set_exception_handler(exception_handler)
        background_loop.run_forever()
        logger.info("Background event loop stopped")
    except Exception as e:
        logger.error(f"Error in background event loop: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle FastAPI app lifespan - startup and shutdown."""
    global worker_manager, background_thread, background_loop

    # Startup
    logger.info("Starting up FastAPI app with WorkerManager")

    # Create WorkerManager instance
    worker_manager = WorkerManager()

    # Start the background event loop in a separate thread
    background_thread = threading.Thread(target=run_background_loop, daemon=True)
    background_thread.start()
    logger.info("Started background thread for WorkerManager event loop")

    # Wait a moment for the background loop to initialize
    await asyncio.sleep(0.1)

    yield

    # Shutdown
    logger.info("Shutting down FastAPI app")

    # Clean up WorkerManager
    if worker_manager:
        worker_manager.cleanup()

    # Stop the background event loop
    if background_loop and not background_loop.is_closed():
        background_loop.call_soon_threadsafe(background_loop.stop)
        logger.info("Stopped background event loop")

# Pydantic models
class AgentPayload(BaseModel):
    """Payload model for agent tasks."""
    description: str
    title: Optional[str] = None
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    repos: Optional[list] = None
    repo: Optional[str] = None
    branch: Optional[str] = None

class KickoffAgentRequest(BaseModel):
    """Request model for kicking off an agent."""
    agent_type: Literal["Fullstack Planner", "PM", "SWE"]
    payload: AgentPayload

class KickoffAgentResponse(BaseModel):
    """Response model for agent kickoff."""
    run_id: str
    agent_type: str
    status: str
    message: str

def create_app() -> FastAPI:
    """Factory function to create FastAPI app."""
    app = FastAPI(title="Cairn Task Manager API", version="1.0.0", lifespan=lifespan)

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Get directory paths
    static_dir = get_static_dir()
    frontend_dist_dir = get_frontend_dist_dir()

    # Serve static files from frontend dist if available, otherwise from static
    if frontend_dist_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(frontend_dist_dir / "assets")), name="assets")
        logger.info(f"Serving frontend assets from: {frontend_dist_dir / 'assets'}")
    elif static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        logger.info(f"Serving static files from: {static_dir}")

    # Routes
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "ok", "timestamp": time.time()}

    @app.get("/")
    async def serve_ui():
        """Serve the main UI."""
        # Try frontend dist first, fallback to static
        if frontend_dist_dir.exists() and (frontend_dist_dir / "index.html").exists():
            return FileResponse(str(frontend_dist_dir / "index.html"))
        elif static_dir.exists() and (static_dir / "index.html").exists():
            return FileResponse(str(static_dir / "index.html"))
        else:
            raise HTTPException(status_code=404, detail="Frontend not built. Run 'cairn setup' first.")

    @app.get("/api/config")
    async def get_config():
        """Get configuration data for the UI."""
        if not worker_manager:
            return {
                "available_agent_types": ["Fullstack Planner", "PM", "SWE"],
                "connected_repos": []
            }
        return {
            "available_agent_types": ["Fullstack Planner", "PM", "SWE"],
            "connected_repos": [f"{owner}/{repo}" for owner, repo in worker_manager.connected_repos]
        }

    @app.get("/api/repos")
    async def get_repos():
        """Get list of connected repositories."""
        if not worker_manager:
            raise HTTPException(status_code=503, detail="WorkerManager not initialized")

        repos = []
        for owner, repo in worker_manager.connected_repos:
            repos.append({
                "owner": owner,
                "repo": repo
            })

        return {"repos": repos}

    @app.get("/api/active-tasks")
    async def get_active_tasks():
        """Get all active tasks."""
        conn = get_db_connection()
        try:
            cursor = conn.execute("""
                SELECT task_id, payload, agent_type, agent_status, created_at, updated_at
                FROM active_tasks
                ORDER BY created_at DESC
            """)
            rows = cursor.fetchall()

            tasks = []
            for row in rows:
                task = dict(row)
                # Parse JSON payload if possible
                try:
                    task["payload"] = json.loads(task["payload"])
                except (json.JSONDecodeError, TypeError):
                    pass
                tasks.append(task)

            return {"tasks": tasks}
        finally:
            conn.close()

    @app.get("/api/debug-messages")
    async def get_debug_messages(limit: int = 50):
        """Get recent debug messages."""
        conn = get_db_connection()
        try:
            cursor = conn.execute("""
                SELECT message_id, message, timestamp
                FROM debug_messages
                ORDER BY message_id DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()

            return {"messages": [dict(row) for row in rows]}
        finally:
            conn.close()

    @app.post("/api/kickoff-agent", response_model=KickoffAgentResponse)
    async def kickoff_agent(request: KickoffAgentRequest):
        """Kickoff a new agent task."""
        if not worker_manager:
            raise HTTPException(status_code=503, detail="WorkerManager not initialized")

        try:
            # Generate a simple run ID
            run_id = f"{request.agent_type.lower().replace(' ', '_')}_{int(time.time())}"

            # Store task in database
            conn = get_db_connection()
            try:
                conn.execute("""
                    INSERT INTO active_tasks (task_id, payload, agent_type, agent_status, run_id)
                    VALUES (?, ?, ?, ?, ?)
                """, (run_id, json.dumps(request.payload.dict()), request.agent_type, "started", run_id))
                conn.commit()
            finally:
                conn.close()

            logger.info(f"Started {request.agent_type} task with run_id: {run_id}")

            return KickoffAgentResponse(
                run_id=run_id,
                agent_type=request.agent_type,
                status="started",
                message=f"{request.agent_type} task started successfully"
            )
        except Exception as e:
            logger.error(f"Error starting agent task: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/models")
    async def get_models():
        """Get available model providers and models."""
        valid_providers = {}

        # Check each provider's API key
        for provider, info in SUPPORTED_MODELS.items():
            env_key_name = info.get('env_api_key_name')

            # If the provider has an API key requirement and it's set
            if env_key_name and os.getenv(env_key_name):
                valid_providers[provider] = {
                    "models": info["models"],
                    "has_valid_key": True
                }
            elif not env_key_name:
                # If no API key is required, include the provider
                valid_providers[provider] = {
                    "models": info["models"],
                    "has_valid_key": True
                }

        return {
            "providers": valid_providers,
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    return app

# For backwards compatibility
if __name__ == "__main__":
    import uvicorn
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)
