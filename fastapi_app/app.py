import asyncio
import json
import logging
import os
import sqlite3
import sys
import threading
import time
import traceback
import re
from contextlib import asynccontextmanager
from typing import Literal, Optional
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import httpx

# TODO: do this in a better way, this is hacky
# Add the parent directory to Python path so we can import cairn_utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from interactive_worker_manager import WorkerManager

# Load environment variables
load_dotenv('.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Add a handler to store logs in the database
class DatabaseLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self._is_handling = False  # Flag to prevent recursion

    def emit(self, record):
        if self._is_handling:  # Skip if we're already handling a log
            return

        try:
            self._is_handling = True
            conn = sqlite3.connect(DB_PATH, timeout=30)
            try:
                msg = self.format(record)
                conn.execute(
                    "INSERT INTO debug_messages (message, timestamp) VALUES (?, datetime('now'))",
                    (msg,)
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            self.handleError(record)
        finally:
            self._is_handling = False

# Add the database handler to the logger
db_handler = DatabaseLogHandler()
db_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
logger.addHandler(db_handler)

# Global variables for background event loop
background_loop = None
background_thread = None
worker_manager = None

def run_background_loop():
    """Run the background event loop for processing WorkerManager tasks"""
    global background_loop
    try:
        # Create a new event loop for this thread
        background_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(background_loop)
        worker_manager.loop = background_loop
        worker_manager.add_debug_message("Background event loop started for WorkerManager")
        logger.info("Background event loop started for WorkerManager")

        # Set up exception handler for the loop
        def exception_handler(loop, context):
            exception = context.get('exception')
            logger.error(f"Background loop exception: {exception}")
            worker_manager.add_debug_message(f"Background loop exception: {exception}")

        background_loop.set_exception_handler(exception_handler)

        # Run the event loop forever
        logger.info("Starting background event loop...")
        background_loop.run_forever()
        logger.info("Background event loop stopped")
    except Exception as e:
        logger.error(f"Error in background event loop: {e}")
        if worker_manager:
            worker_manager.add_debug_message(f"Background loop error: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle FastAPI app lifespan - startup and shutdown"""
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

    # Wait for background thread to finish
    if background_thread and background_thread.is_alive():
        background_thread.join(timeout=5)
        logger.info("Background thread finished")

app = FastAPI(title="Cairn Task Manager API", version="1.0.0", lifespan=lifespan)

# Get the absolute path to the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
STATIC_DIR = PROJECT_ROOT / "static"

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Use absolute path to ensure database is found regardless of working directory
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cairn_tasks.db")

def get_db_connection():
    """Get database connection with proper settings"""
    conn = sqlite3.connect(DB_PATH, timeout=30)
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
                    run_ids TEXT,
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

        # Add any missing columns to active_tasks
        cursor = conn.execute("PRAGMA table_info(active_tasks)")
        existing_columns = {row['name'] for row in cursor.fetchall()}

        # Add run_id column if it doesn't exist
        if 'run_id' not in existing_columns:
            logger.info("Adding run_id column to active_tasks")
            conn.execute("ALTER TABLE active_tasks ADD COLUMN run_id TEXT")

        # Add run_ids column if it doesn't exist
        if 'run_ids' not in existing_columns:
            logger.info("Adding run_ids column to active_tasks")
            conn.execute("ALTER TABLE active_tasks ADD COLUMN run_ids TEXT")

        # Add agent_type column if it doesn't exist
        if 'agent_type' not in existing_columns:
            logger.info("Adding agent_type column to active_tasks")
            conn.execute("ALTER TABLE active_tasks ADD COLUMN agent_type TEXT")

        # Add agent_status column if it doesn't exist
        if 'agent_status' not in existing_columns:
            logger.info("Adding agent_status column to active_tasks")
            conn.execute("ALTER TABLE active_tasks ADD COLUMN agent_status TEXT")

        # Add agent_output column if it doesn't exist
        if 'agent_output' not in existing_columns:
            logger.info("Adding agent_output column to active_tasks")
            conn.execute("ALTER TABLE active_tasks ADD COLUMN agent_output TEXT")

        # Add related_run_ids column if it doesn't exist
        if 'related_run_ids' not in existing_columns:
            logger.info("Adding related_run_ids column to active_tasks")
            conn.execute("ALTER TABLE active_tasks ADD COLUMN related_run_ids TEXT")

        # Add sibling_subtask_ids column if it doesn't exist
        if 'sibling_subtask_ids' not in existing_columns:
            logger.info("Adding sibling_subtask_ids column to active_tasks")
            conn.execute("ALTER TABLE active_tasks ADD COLUMN sibling_subtask_ids TEXT")

        # Add parent_fullstack_id column if it doesn't exist
        if 'parent_fullstack_id' not in existing_columns:
            logger.info("Adding parent_fullstack_id column to active_tasks")
            conn.execute("ALTER TABLE active_tasks ADD COLUMN parent_fullstack_id TEXT")

        # Add subtask_index column if it doesn't exist
        if 'subtask_index' not in existing_columns:
            logger.info("Adding subtask_index column to active_tasks")
            conn.execute("ALTER TABLE active_tasks ADD COLUMN subtask_index INTEGER")

        conn.commit()
        logger.info("Database schema initialization completed")
    except Exception as e:
        logger.error(f"Error initializing database schema: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

    return conn

def get_configuration():
    """Get configuration from WorkerManager instance"""
    if not worker_manager:
        return {
            "available_agent_types": ["Fullstack Planner", "PM", "SWE"],
            "connected_repos": []
        }
    return {
        "available_agent_types": ["Fullstack Planner", "PM", "SWE"],
        "connected_repos": [f"{owner}/{repo}" for owner, repo in worker_manager.connected_repos]
    }

# Pydantic models for request/response
class AgentPayload(BaseModel):
    """Payload model for agent tasks"""
    # Common fields
    description: str
    model_provider: Optional[str] = None
    model_name: Optional[str] = None

    # Fullstack Planner specific
    repos: Optional[list] = None

    # PM/SWE specific
    repo: Optional[str] = None
    branch: Optional[str] = None
    related_run_ids: Optional[list] = None

class KickoffAgentRequest(BaseModel):
    """Request model for kicking off an agent"""
    agent_type: Literal["Fullstack Planner", "PM", "SWE"]
    payload: AgentPayload

class KickoffAgentResponse(BaseModel):
    """Response model for agent kickoff"""
    run_id: str
    agent_type: str
    status: str
    message: str

class CreateSubtasksRequest(BaseModel):
    """Request model for creating subtasks from Fullstack Planner output"""
    fullstack_planner_run_id: str
    subtask_index: Optional[int] = None

class CreateSubtasksResponse(BaseModel):
    """Response model for subtask creation"""
    created_tasks: list
    message: str
    fullstack_planner_run_id: str

@app.get("/health")
async def root():
    return {"status": "ok"}

@app.get("/")
async def serve_ui():
    """Serve the main UI"""
    return FileResponse(str(STATIC_DIR / "index.html"))

@app.get("/repos")
async def serve_repos_ui():
    """Serve the repository management UI"""
    return FileResponse(str(STATIC_DIR / "repos.html"))

@app.get("/repos/{owner}/{repo}")
async def serve_repo_details_ui(owner: str, repo: str):
    """Serve the repository details UI"""
    return FileResponse(str(STATIC_DIR / "repo-details.html"))

@app.get("/api/repos")
async def get_repos():
    """Get list of connected repositories"""
    if not worker_manager:
        raise HTTPException(status_code=503, detail="WorkerManager not initialized")
    return {
        "repos": [{"owner": owner, "repo": repo} for owner, repo in worker_manager.connected_repos]
    }

@app.post("/api/repos")
async def add_repo(repo: dict):
    """Add a new repository"""
    if not worker_manager:
        raise HTTPException(status_code=503, detail="WorkerManager not initialized")
    
    owner = repo.get("owner")
    repo_name = repo.get("repo")
    
    if not owner or not repo_name:
        raise HTTPException(status_code=400, detail="Both owner and repo are required")
    
    # Add to connected repos
    if (owner, repo_name) not in worker_manager.connected_repos:
        worker_manager.connected_repos.append((owner, repo_name))
        
        # Update environment variable
        repos_str = ",".join([f"{o}/{r}" for o, r in worker_manager.connected_repos])
        os.environ["CONNECTED_REPOS"] = repos_str
        
        # Update .env file
        with open(".env", "r") as f:
            env_content = f.read()
        
        if "CONNECTED_REPOS=" in env_content:
            # Replace existing CONNECTED_REPOS line
            env_content = re.sub(
                r"CONNECTED_REPOS=.*",
                f"CONNECTED_REPOS={repos_str}",
                env_content
            )
        else:
            # Add new CONNECTED_REPOS line
            env_content += f"\nCONNECTED_REPOS={repos_str}\n"
        
        with open(".env", "w") as f:
            f.write(env_content)
    
    return {"message": f"Repository {owner}/{repo_name} added successfully"}

@app.delete("/api/repos/{owner}/{repo}")
async def delete_repo(owner: str, repo: str):
    """Remove a repository"""
    if not worker_manager:
        raise HTTPException(status_code=503, detail="WorkerManager not initialized")
    
    # Remove from connected repos
    if (owner, repo) in worker_manager.connected_repos:
        worker_manager.connected_repos.remove((owner, repo))
        
        # Update environment variable
        repos_str = ",".join([f"{o}/{r}" for o, r in worker_manager.connected_repos])
        os.environ["CONNECTED_REPOS"] = repos_str
        
        # Update .env file
        with open(".env", "r") as f:
            env_content = f.read()
        
        if "CONNECTED_REPOS=" in env_content:
            # Replace existing CONNECTED_REPOS line
            env_content = re.sub(
                r"CONNECTED_REPOS=.*",
                f"CONNECTED_REPOS={repos_str}",
                env_content
            )
        else:
            # Add new CONNECTED_REPOS line
            env_content += f"\nCONNECTED_REPOS={repos_str}\n"
        
        with open(".env", "w") as f:
            f.write(env_content)
    
    return {"message": f"Repository {owner}/{repo} removed successfully"}

@app.get("/config")
async def get_config():
    """Get configuration data for the UI"""
    return get_configuration()

@app.get("/active-tasks")
async def get_active_tasks():
    """Get all active tasks"""
    conn = get_db_connection()
    try:
        cursor = conn.execute("""
            SELECT task_id, payload, created_at, updated_at
            FROM active_tasks
            ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()

        # Convert to dicts and parse JSON payload if needed
        tasks = []
        for row in rows:
            task = dict(row)
            # Only parse payload if it's a JSON string
            try:
                task["payload"] = json.loads(task["payload"])
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse payload JSON for task_id {task.get('task_id')}: {e}")
                # Keep as-is if not valid JSON
                pass
            tasks.append(task)

        return tasks
    finally:
        conn.close()

@app.get("/debug-messages")
async def get_debug_messages(limit: int = 50):
    """Get recent debug messages"""
    conn = get_db_connection()
    try:
        cursor = conn.execute("""
            SELECT message_id, message, timestamp
            FROM debug_messages
            ORDER BY message_id DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()

        return [dict(row) for row in rows]
    finally:
        conn.close()

@app.get("/task-logs")
async def get_task_logs(limit: int = 100):
    """Get all task logs"""
    conn = get_db_connection()
    try:
        cursor = conn.execute("""
            SELECT log_id, run_id, agent_type, log_data, created_at, updated_at
            FROM task_logs
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()

        # Convert to dicts and parse JSON log_data if needed
        logs = []
        for row in rows:
            log = dict(row)
            # Only parse log_data if it's a JSON string
            try:
                log["log_data"] = json.loads(log["log_data"])
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse log_data JSON for log_id {log.get('log_id')}: {e}")
                # Keep as-is if not valid JSON
                pass
            logs.append(log)

        return logs
    finally:
        conn.close()

@app.get("/task-logs/{run_id}")
async def get_task_logs_by_run_id(run_id: str):
    """Get task logs for a specific run_id"""
    conn = get_db_connection()
    try:
        cursor = conn.execute("""
            SELECT log_id, run_id, agent_type, log_data, created_at, updated_at
            FROM task_logs
            WHERE run_id = ?
            ORDER BY created_at DESC
        """, (run_id,))
        rows = cursor.fetchall()

        # Convert to dicts and parse JSON log_data if needed
        logs = []
        for row in rows:
            log = dict(row)
            # Only parse log_data if it's a JSON string
            try:
                log["log_data"] = json.loads(log["log_data"])
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse log_data JSON for log_id {log.get('log_id')}: {e}")
                # Keep as-is if not valid JSON
                pass
            logs.append(log)

        return logs
    finally:
        conn.close()

@app.post("/kickoff-agent", response_model=KickoffAgentResponse)
async def kickoff_agent(request: KickoffAgentRequest):
    """Kick off an agent using the WorkerManager's task creation logic"""
    logger.info(f"Received request to kickoff {request.agent_type} agent")
    logger.info(f"Request payload: {json.dumps(request.payload.dict(), indent=2)}")

    if not worker_manager:
        logger.error("WorkerManager not initialized")
        raise HTTPException(status_code=503, detail="WorkerManager not initialized")

    # Validate payload based on agent type
    if request.agent_type == "Fullstack Planner":
        if not request.payload.repos:
            logger.error("No repositories provided for Fullstack Planner")
            raise HTTPException(status_code=400, detail="repos field is required for Fullstack Planner")
        # Extract just the repo names from full paths for WorkerManager
        repos = []
        for repo_path in request.payload.repos:
            if '/' in repo_path:
                _, repo_name = repo_path.split('/', 1)
                repos.append(repo_name)
            else:
                repos.append(repo_path)
        logger.info(f"Extracted repo names for Fullstack Planner: {repos}")
    else:  # PM or SWE
        if not request.payload.repo:
            logger.error("No repository provided for PM/SWE agent")
            raise HTTPException(status_code=400, detail="repo field is required for PM and SWE agents")
        # Extract just the repo name from full path for WorkerManager
        if '/' in request.payload.repo:
            _, repo_name = request.payload.repo.split('/', 1)
            repos = [repo_name]
        else:
            repos = [request.payload.repo]
        logger.info(f"Extracted repo name for PM/SWE agent: {repos}")

    try:
        logger.info(f"Attempting to create task using WorkerManager")
        # Ensure description is a string
        description = str(request.payload.description).strip()
        if not description:
            logger.error("Empty description provided")
            raise HTTPException(status_code=400, detail="Description cannot be empty")

        # Use WorkerManager's create_task_sync method
        # Get model info from request - don't add defaults as per user request
        model_provider = request.payload.model_provider
        model_name = request.payload.model_name

        task_id = worker_manager.create_task_sync(
            agent_type=request.agent_type,
            description=description,
            repos=repos,
            model_provider=model_provider,
            model_name=model_name
        )

        if not task_id:
            logger.error("WorkerManager.create_task_sync returned no task_id")
            raise HTTPException(status_code=500, detail="Failed to create task")

        logger.info(f"Successfully created task {task_id} using WorkerManager")

        return KickoffAgentResponse(
            run_id=task_id,
            agent_type=request.agent_type,
            status="queued",
            message=f"{request.agent_type} agent has been started with run ID {task_id}"
        )

    except Exception as e:
        logger.error(f"Failed to start agent: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to start agent: {str(e)}")

@app.post("/create-subtasks", response_model=CreateSubtasksResponse)
async def create_subtasks_from_fullstack_planner(request: CreateSubtasksRequest):
    """Create PM/SWE agent tasks from a completed Fullstack Planner output"""
    logger.info(f"Received request to create subtasks for Fullstack Planner task {request.fullstack_planner_run_id}")
    logger.info(f"Request details: subtask_index={request.subtask_index}")

    if not worker_manager:
        logger.error("WorkerManager not initialized")
        raise HTTPException(status_code=503, detail="WorkerManager not initialized")

    conn = get_db_connection()
    try:
        # Find the completed Fullstack Planner task
        cursor = conn.execute("""
            SELECT task_id, payload, created_at, updated_at
            FROM active_tasks
            WHERE task_id = ?
        """, (request.fullstack_planner_run_id,))
        row = cursor.fetchone()

        if not row:
            logger.error(f"Fullstack Planner task {request.fullstack_planner_run_id} not found in database")
            raise HTTPException(status_code=404, detail=f"Fullstack Planner task {request.fullstack_planner_run_id} not found")

        task = dict(row)
        try:
            payload = json.loads(task["payload"])
            logger.info(f"Successfully parsed task payload for task {request.fullstack_planner_run_id}")
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to parse task payload: {e}")
            raise HTTPException(status_code=400, detail="Invalid task payload format")

        # Verify it's a Fullstack Planner task
        if payload.get("agent_type") != "Fullstack Planner":
            logger.error(f"Task {request.fullstack_planner_run_id} is not a Fullstack Planner task, got type: {payload.get('agent_type')}")
            raise HTTPException(status_code=400, detail="Specified task is not a Fullstack Planner task")

        # Check if task is completed and has agent_output
        if payload.get("agent_status") != "Completed":
            logger.error(f"Fullstack Planner task {request.fullstack_planner_run_id} is not completed, status: {payload.get('agent_status')}")
            raise HTTPException(status_code=400, detail="Fullstack Planner task is not completed")

        agent_output = payload.get("agent_output", {})
        if not agent_output:
            logger.error(f"No agent output found in completed task {request.fullstack_planner_run_id}")
            raise HTTPException(status_code=400, detail="No agent output found in completed task")

        logger.info(f"Found agent output: {json.dumps(agent_output, indent=2)}")

        # Extract subtask information
        subtasks = agent_output.get("list_of_subtasks", [])
        subtask_titles = agent_output.get("list_of_subtask_titles", [])
        subtask_repos = agent_output.get("list_of_subtask_repos", [])
        subtask_assignments = agent_output.get("assessment_of_subtask_assignment", [])

        logger.info(f"Found {len(subtasks)} subtasks in Fullstack Planner output")
        logger.info(f"Subtask titles: {subtask_titles}")
        logger.info(f"Subtask repos: {subtask_repos}")
        logger.info(f"Subtask assignments: {subtask_assignments}")

        if not subtasks:
            logger.error("No subtasks found in agent output")
            return CreateSubtasksResponse(
                created_tasks=[],
                message="No subtasks found in the Fullstack Planner output",
                fullstack_planner_run_id=request.fullstack_planner_run_id
            )

        # Get pre-generated subtask IDs
        task_storage = worker_manager.task_storage
        all_subtask_ids = task_storage.get_subtask_ids(request.fullstack_planner_run_id)
        logger.info(f"Retrieved {len(all_subtask_ids) if all_subtask_ids else 0} pre-generated subtask IDs")

        # If no pre-generated IDs exist, generate them now
        if not all_subtask_ids and subtasks:
            logger.info(f"No pre-generated IDs found, generating {len(subtasks)} new IDs")
            try:
                all_subtask_ids = task_storage.pre_generate_subtask_ids(
                    fullstack_run_id=request.fullstack_planner_run_id,
                    num_subtasks=len(subtasks)
                )
                logger.info(f"Successfully generated {len(all_subtask_ids)} subtask IDs")
            except Exception as e:
                logger.error(f"Failed to generate subtask IDs: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                raise HTTPException(status_code=500, detail=f"Failed to generate subtask IDs: {str(e)}")

        # Extract the subtask IDs for easier access
        subtask_id_map = {item["subtask_index"]: item["subtask_id"] for item in all_subtask_ids}
        all_pm_subtask_ids = [item["subtask_id"] for item in all_subtask_ids]
        logger.info(f"Created subtask ID map with {len(subtask_id_map)} entries")

        # Check status of existing subtasks
        existing_tasks = {}
        for subtask_id in all_pm_subtask_ids:
            cursor = conn.execute("""
                SELECT task_id, payload FROM active_tasks
                WHERE task_id = ? OR payload LIKE ?
            """, (subtask_id, f'%"run_id": "{subtask_id}"%'))
            row = cursor.fetchone()
            if row:
                try:
                    task_payload = json.loads(row['payload'])
                    status = task_payload.get('agent_status', 'Unknown')
                    existing_tasks[subtask_id] = status
                except (json.JSONDecodeError, TypeError):
                    existing_tasks[subtask_id] = 'Unknown'

        created_tasks = []

        # Handle a single subtask or all subtasks
        subtask_indices = []
        if request.subtask_index is not None:
            # Handle a single subtask
            if request.subtask_index < 0 or request.subtask_index >= len(subtasks):
                logger.error(f"Invalid subtask index: {request.subtask_index}, total subtasks: {len(subtasks)}")
                raise HTTPException(status_code=400, detail=f"Invalid subtask index: {request.subtask_index}")

            # Check if this subtask has already been run
            subtask_id = subtask_id_map.get(request.subtask_index)
            if subtask_id and subtask_id in existing_tasks:
                status = existing_tasks[subtask_id]
                if status in ['Completed', 'Running', 'Queued']:
                    logger.info(f"Subtask {request.subtask_index} already has status: {status}")
                    return CreateSubtasksResponse(
                        created_tasks=[],
                        message=f"Subtask {request.subtask_index} has already been run (status: {status})",
                        fullstack_planner_run_id=request.fullstack_planner_run_id
                    )
            subtask_indices = [request.subtask_index]
            logger.info(f"Creating single subtask at index {request.subtask_index}")
        else:
            # Handle all subtasks - only create ones that haven't been run
            subtask_indices = []
            for i in range(len(subtasks)):
                subtask_id = subtask_id_map.get(i)
                if not subtask_id or subtask_id not in existing_tasks or existing_tasks[subtask_id] not in ['Completed', 'Running', 'Queued']:
                    subtask_indices.append(i)

            if not subtask_indices:
                logger.info("All subtasks have already been run")
                return CreateSubtasksResponse(
                    created_tasks=[],
                    message="All subtasks have already been run",
                    fullstack_planner_run_id=request.fullstack_planner_run_id
                )
            logger.info(f"Creating {len(subtask_indices)} remaining subtasks")

        if not subtask_indices:
            logger.warning("No subtasks found to process")
            return CreateSubtasksResponse(
                created_tasks=[],
                message="No subtasks found in the Fullstack Planner output",
                fullstack_planner_run_id=request.fullstack_planner_run_id
            )

        # Create PM tasks for each subtask
        for i in subtask_indices:
            subtask_desc = subtasks[i]
            title = subtask_titles[i]
            repo = subtask_repos[i]

            logger.info(f"Processing subtask {i}: {title} for repo {repo}")

            # Always use PM agent type
            agent_type = "PM"

            try:
                # Use pre-generated subtask ID if available, otherwise generate a new one
                pre_generated_id = subtask_id_map.get(i)
                logger.info(f"Using pre-generated ID: {pre_generated_id} for subtask {i}")

                # Prepare custom payload with related subtask IDs
                custom_payload = {
                    "description": f"{title}\n\n{subtask_desc}",
                    "repo": repo,
                    "related_run_ids": [request.fullstack_planner_run_id] + all_pm_subtask_ids,
                    "sibling_subtask_ids": all_pm_subtask_ids,
                    "parent_fullstack_id": request.fullstack_planner_run_id,
                    "subtask_index": i
                }

                if pre_generated_id:
                    logger.info(f"Creating task with pre-generated ID {pre_generated_id}")

                    # Create the task in the database with the pre-generated ID
                    # Get model info from parent task - don't add defaults as per user request
                    parent_task = task_storage.get_active_task(request.fullstack_planner_run_id)
                    model_provider = parent_task.get('model_provider')
                    model_name = parent_task.get('model_name')

                    worker_payload = {
                        "run_id": pre_generated_id,
                        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "repo": repo,
                        "owner": worker_manager.owner,
                        "description": f"{title}\n\n{subtask_desc}",
                        "agent_output": {},
                        "agent_status": "Queued",
                        "agent_type": agent_type,
                        "related_run_ids": [request.fullstack_planner_run_id] + all_pm_subtask_ids,
                        "sibling_subtask_ids": all_pm_subtask_ids,
                        "parent_fullstack_id": request.fullstack_planner_run_id,
                        "subtask_index": i,
                        "raw_logs_dump": {},
                        "branch": None,
                        "model_provider": model_provider,
                        "model_name": model_name
                    }

                    try:
                        # Create auto-persisting payload and store in database
                        persistent_payload = task_storage.create_active_task_persistent(pre_generated_id, worker_payload)
                        logger.info(f"Created persistent payload for task {pre_generated_id}")

                        # Start worker process
                        process = worker_manager.run_worker_process(pre_generated_id)
                        worker_manager.running_tasks[pre_generated_id] = process
                        worker_manager.active_tasks[pre_generated_id] = persistent_payload
                        task_id = pre_generated_id
                        logger.info(f"Started worker process for task {pre_generated_id}")
                    except Exception as e:
                        logger.error(f"Failed to create task with pre-generated ID {pre_generated_id}: {e}")
                        logger.error(f"Traceback: {traceback.format_exc()}")
                        continue
                else:
                    logger.info(f"No pre-generated ID found, creating new task using WorkerManager")
                    try:
                        # Create a new task using WorkerManager if no pre-generated ID
                        # Get model info from parent task - don't add defaults as per user request
                        parent_task = task_storage.get_active_task(request.fullstack_planner_run_id)
                        model_provider = parent_task.get('model_provider')
                        model_name = parent_task.get('model_name')

                        task_id = worker_manager.create_task_sync(
                            agent_type=agent_type,
                            description=f"{title}\n\n{subtask_desc}",
                            repos=[repo],
                            model_provider=model_provider,
                            model_name=model_name
                        )
                        logger.info(f"Created new task with ID: {task_id}")

                        # Update the payload with the additional fields
                        if task_id:
                            task_data = worker_manager.get_task(task_id)
                            if task_data:
                                task_data.update({
                                    "related_run_ids": [request.fullstack_planner_run_id] + all_pm_subtask_ids,
                                    "sibling_subtask_ids": all_pm_subtask_ids,
                                    "parent_fullstack_id": request.fullstack_planner_run_id,
                                    "subtask_index": i
                                })
                                logger.info(f"Updated task {task_id} with additional fields")
                    except Exception as e:
                        logger.error(f"Failed to create task using WorkerManager: {e}")
                        logger.error(f"Traceback: {traceback.format_exc()}")
                        continue

                if task_id:
                    created_tasks.append({
                        "run_id": task_id,
                        "agent_type": agent_type,
                        "title": title,
                        "repo": repo,
                        "status": "queued"
                    })
                    logger.info(f"Successfully created {agent_type} task {task_id} for subtask: {title}")
                else:
                    logger.error(f"Failed to create task for subtask: {title}")

            except Exception as e:
                logger.error(f"Error creating task for subtask '{title}': {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                continue

        if not created_tasks:
            logger.error("No tasks were successfully created")
            return CreateSubtasksResponse(
                created_tasks=[],
                message="Failed to create any subtasks. Please check the logs for more details.",
                fullstack_planner_run_id=request.fullstack_planner_run_id
            )

        logger.info(f"Successfully created {len(created_tasks)} PM tasks")
        return CreateSubtasksResponse(
            created_tasks=created_tasks,
            message=f"Successfully created {len(created_tasks)} PM tasks from Fullstack Planner output",
            fullstack_planner_run_id=request.fullstack_planner_run_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create subtasks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create subtasks: {str(e)}")
    finally:
        conn.close()

@app.delete("/active-tasks/{task_id}")
async def delete_active_task(task_id: str):
    """Delete an active task by ID (robustly by task_id or run_id)"""
    if not worker_manager:
        raise HTTPException(status_code=503, detail="WorkerManager not initialized")

    logger.info(f"Attempting to delete task {task_id}")

    conn = get_db_connection()
    try:
        # First check if the task exists by task_id
        cursor = conn.execute("""
            SELECT task_id, payload FROM active_tasks WHERE task_id = ?
        """, (task_id,))
        row = cursor.fetchone()

        if not row:
            # If not found by task_id, try to find by run_id in payload (robust LIKE)
            cursor = conn.execute("""
                SELECT task_id, payload FROM active_tasks
                WHERE payload LIKE ?
            """, (f'%"run_id": "{task_id}"%',))
            row = cursor.fetchone()

        # If still not found, iterate all and parse JSON to match run_id or task_id
        if not row:
            cursor = conn.execute("SELECT task_id, payload FROM active_tasks")
            all_rows = cursor.fetchall()
            found = False
            for r in all_rows:
                try:
                    payload = json.loads(r['payload'])
                    if payload.get('run_id') == task_id or r['task_id'] == task_id:
                        row = r
                        found = True
                        break
                except Exception:
                    continue
            if not found:
                logger.warning(f"Task {task_id} not found in database by task_id or run_id (even after full scan)")
                raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        # Get the run_id from the payload if it exists
        try:
            payload = json.loads(row['payload'])
            run_id = payload.get('run_id')
            if run_id and run_id != task_id:
                logger.info(f"Found run_id {run_id} in payload for task {task_id}")
                # Also delete by run_id
                conn.execute("""
                    DELETE FROM active_tasks
                    WHERE task_id = ?
                    OR payload LIKE ?
                """, (task_id, f'%"run_id": "{run_id}"%'))
                conn.execute("DELETE FROM task_logs WHERE run_id = ? OR run_id = ?",
                           (task_id, run_id))
            else:
                # Delete just by task_id
                conn.execute("DELETE FROM active_tasks WHERE task_id = ?", (task_id,))
                conn.execute("DELETE FROM task_logs WHERE run_id = ?", (task_id,))
        except json.JSONDecodeError:
            # If payload is not valid JSON, just delete by task_id
            conn.execute("DELETE FROM active_tasks WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM task_logs WHERE run_id = ?", (task_id,))

        conn.commit()
        logger.info(f"Deleted task {task_id} from database")

        # If the task is running, stop its worker process
        if task_id in worker_manager.running_tasks:
            process = worker_manager.running_tasks[task_id]
            if process and process.is_alive():
                process.terminate()
                logger.info(f"Terminated worker process for task {task_id}")
            del worker_manager.running_tasks[task_id]

        # Remove from active_tasks in WorkerManager
        if task_id in worker_manager.active_tasks:
            del worker_manager.active_tasks[task_id]
            logger.info(f"Removed task {task_id} from WorkerManager active_tasks")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete task: {str(e)}")
    finally:
        conn.close()

@app.get("/api/repos/{owner}/{repo}/stats")
async def get_repo_stats(owner: str, repo: str):
    """Get repository statistics including contributors and code ownership"""
    if not worker_manager:
        raise HTTPException(status_code=503, detail="WorkerManager not initialized")
    
    try:
        # Get GitHub token from environment
        github_token = os.getenv("GITHUB_TOKEN")
        if not github_token:
            raise HTTPException(
                status_code=500,
                detail="GitHub token not configured. Please set the GITHUB_TOKEN environment variable."
            )

        # Fetch repository data using GitHub API
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }

        async with httpx.AsyncClient() as client:
            # Get contributors
            contributors_response = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/contributors",
                headers=headers
            )
            if contributors_response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Repository {owner}/{repo} not found")
            contributors_response.raise_for_status()
            contributors = contributors_response.json()

            # Get languages
            languages_response = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/languages",
                headers=headers
            )
            languages_response.raise_for_status()
            languages = languages_response.json()

            # Get commit activity
            commits_response = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/commits",
                headers=headers,
                params={"per_page": 100}  # Get last 100 commits
            )
            commits_response.raise_for_status()
            commits = commits_response.json()

            # Process commit data to get file ownership and commit timing
            file_ownership = {}
            commit_times = {
                'hour_of_day': [0] * 24,
                'day_of_week': [0] * 7,
                'month': [0] * 12
            }
            commit_authors = {}

            for commit in commits:
                commit_sha = commit["sha"]
                commit_details = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo}/commits/{commit_sha}",
                    headers=headers
                )
                commit_details.raise_for_status()
                commit_data = commit_details.json()
                
                # Process file ownership
                for file in commit_data.get("files", []):
                    filename = file["filename"]
                    author = commit_data["commit"]["author"]["name"]
                    if filename not in file_ownership:
                        file_ownership[filename] = {"authors": {}, "last_modified": None}
                    
                    file_ownership[filename]["authors"][author] = file_ownership[filename]["authors"].get(author, 0) + 1
                    if not file_ownership[filename]["last_modified"]:
                        file_ownership[filename]["last_modified"] = commit_data["commit"]["author"]["date"]
                
                # Process commit timing
                if "commit" in commit_data and "author" in commit_data["commit"]:
                    commit_date = commit_data["commit"]["author"]["date"]
                    if commit_date:
                        try:
                            from datetime import datetime
                            dt = datetime.strptime(commit_date, "%Y-%m-%dT%H:%M:%SZ")
                            
                            # Hour of day (0-23)
                            hour = dt.hour
                            commit_times['hour_of_day'][hour] += 1
                            
                            # Day of week (0=Monday, 6=Sunday)
                            day = dt.weekday()
                            commit_times['day_of_week'][day] += 1
                            
                            # Month (0=January, 11=December)
                            month = dt.month - 1
                            commit_times['month'][month] += 1
                            
                            # Track author commits
                            author = commit_data["commit"]["author"]["name"]
                            if author not in commit_authors:
                                commit_authors[author] = {
                                    'total': 0,
                                    'hours': [0] * 24,
                                    'days': [0] * 7
                                }
                            commit_authors[author]['total'] += 1
                            commit_authors[author]['hours'][hour] += 1
                            commit_authors[author]['days'][day] += 1
                        except Exception as e:
                            logger.error(f"Error parsing commit date: {e}")

            # Calculate contributor statistics
            contributor_stats = []
            for contributor in contributors:
                contributor_stats.append({
                    "login": contributor["login"],
                    "avatar_url": contributor["avatar_url"],
                    "contributions": contributor["contributions"],
                    "html_url": contributor["html_url"]
                })

            # Calculate language statistics
            total_bytes = sum(languages.values())
            language_stats = [
                {
                    "name": lang,
                    "percentage": round((bytes / total_bytes) * 100, 2)
                }
                for lang, bytes in languages.items()
            ]

            return {
                "owner": owner,
                "repo": repo,
                "contributors": contributor_stats,
                "languages": language_stats,
                "file_ownership": file_ownership,
                "commit_times": commit_times,
                "commit_authors": commit_authors
            }

    except httpx.HTTPError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Repository {owner}/{repo} not found")
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
