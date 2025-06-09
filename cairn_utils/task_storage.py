import json
import logging
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskStorage:
    """SQLite-based storage for task states, replacing in-memory dictionaries"""

    def __init__(self, db_path: str = "cairn_tasks.db"):
        self.db_path = db_path
        self._init_db()
        logger.info(f"TaskStorage initialized with database: {db_path}")

    def _init_db(self):
        """Initialize the SQLite database with required tables"""
        with self.get_connection() as conn:
            # Table for active tasks (replaces active_tasks dict)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS active_tasks (
                    task_id TEXT PRIMARY KEY,
                    payload JSON NOT NULL,
                    run_ids JSON DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Table for task logs (replaces JSON files)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    agent_type TEXT NOT NULL,
                    log_data JSON NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(run_id, agent_type)
                )
            """)

            # Table for debug messages (replaces debug_messages list)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS debug_messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Table for pre-generated subtask IDs from fullstack planner runs
            conn.execute("""
                CREATE TABLE IF NOT EXISTS subtask_ids (
                    fullstack_run_id TEXT NOT NULL,
                    subtask_index INTEGER NOT NULL,
                    subtask_id TEXT NOT NULL,
                    agent_type TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (fullstack_run_id, subtask_index)
                )
            """)

    @contextmanager
    def get_connection(self):
        """Get database connection with proper settings"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # Active Tasks Methods (replaces active_tasks dict)
    def add_active_task(self, task_id: str, payload: Dict[str, Any]):
        """Add a task to active tasks"""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO active_tasks (task_id, payload, run_ids, updated_at)
                VALUES (?, ?, '[]', CURRENT_TIMESTAMP)
            """,
                (task_id, json.dumps(payload)),
            )
        logger.debug(f"Added active task: {task_id}")

    def get_active_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific active task"""
        with self.get_connection() as conn:
            row = conn.execute(
                """
                SELECT payload FROM active_tasks WHERE task_id = ?
            """,
                (task_id,),
            ).fetchone()
            return json.loads(row["payload"]) if row else None

    def get_all_active_tasks(self) -> Dict[str, Any]:
        """Get all active tasks (mimics the active_tasks dict interface)"""
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT task_id, payload FROM active_tasks
            """).fetchall()
            return {row["task_id"]: json.loads(row["payload"]) for row in rows}

    def update_active_task(self, task_id: str, payload: Dict[str, Any]):
        """Update an active task"""
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE active_tasks
                SET payload = ?, updated_at = CURRENT_TIMESTAMP
                WHERE task_id = ?
            """,
                (json.dumps(payload), task_id),
            )
        logger.debug(f"Updated active task: {task_id}")

    def add_run_id_to_task(self, task_id: str, run_id: str):
        """Add a new run_id to the task's run_ids list"""
        with self.get_connection() as conn:
            # Get current run_ids
            row = conn.execute(
                "SELECT run_ids FROM active_tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()

            if row:
                current_run_ids = json.loads(row["run_ids"])
                current_run_ids.append(run_id)

                conn.execute(
                    """
                    UPDATE active_tasks
                    SET run_ids = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE task_id = ?
                """,
                    (json.dumps(current_run_ids), task_id),
                )
                logger.debug(f"Added run_id {run_id} to task {task_id}")
            else:
                logger.warning(f"Task {task_id} not found when trying to add run_id {run_id}")

    def get_task_run_ids(self, task_id: str) -> List[str]:
        """Get all run_ids for a specific task"""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT run_ids FROM active_tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            return json.loads(row["run_ids"]) if row else []

    def remove_active_task(self, task_id: str):
        """Remove a task from active tasks"""
        with self.get_connection() as conn:
            conn.execute(
                "DELETE FROM active_tasks WHERE task_id = ?",
                (task_id,),
            )
        logger.debug(f"Removed active task: {task_id}")

    # Task Logs Methods (replaces JSON files)
    def save_log(self, task_id: str, run_id: str, agent_type: str, log_data: Dict[str, Any]):
        """Save task log data (replaces file-based logging) - properly replaces existing entries"""
        with self.get_connection() as conn:
            # Simple INSERT OR REPLACE that respects UNIQUE constraint
            conn.execute(
                """
                INSERT OR REPLACE INTO task_logs (task_id, run_id, agent_type, log_data, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (task_id, run_id, agent_type, json.dumps(log_data)),
            )
        logger.debug(f"Saved log for task_id: {task_id}, run_id: {run_id}, agent_type: {agent_type}")

    def load_log(self, run_id: str, agent_type: str) -> Dict[str, Any]:
        """Load task log data (replaces file-based loading) - returns most recent entry"""
        with self.get_connection() as conn:
            row = conn.execute(
                """
                SELECT log_data FROM task_logs
                WHERE run_id = ? AND agent_type = ?
                ORDER BY updated_at DESC LIMIT 1
            """,
                (run_id, agent_type),
            ).fetchone()
            return json.loads(row["log_data"]) if row else {}

    def get_all_logs_for_task(self, task_id: str) -> List[Dict[str, Any]]:
        """Get all logs for a specific task (task_id) from the database"""
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT run_id, agent_type, log_data, created_at, updated_at
                FROM task_logs
                WHERE task_id = ?
                ORDER BY created_at DESC
            """,
                (task_id,),
            ).fetchall()
            logs = []
            for row in rows:
                log_entry = {
                    "run_id": row["run_id"],
                    "agent_type": row["agent_type"],
                    "log_data": json.loads(row["log_data"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"]
                }
                logs.append(log_entry)
            return logs

    def get_all_logs_for_run(self, run_id: str) -> List[Dict[str, Any]]:
        """Get all logs for a specific run (run_id) from the database"""
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT task_id, agent_type, log_data, created_at, updated_at
                FROM task_logs
                WHERE run_id = ?
                ORDER BY created_at DESC
            """,
                (run_id,),
            ).fetchall()
            logs = []
            for row in rows:
                log_entry = {
                    "task_id": row["task_id"],
                    "agent_type": row["agent_type"],
                    "log_data": json.loads(row["log_data"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"]
                }
                logs.append(log_entry)
            return logs

    # Debug Messages Methods (replaces debug_messages list)
    def add_debug_message(self, message: str):
        """Add a debug message"""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO debug_messages (message) VALUES (?)
            """,
                (message,),
            )
        logger.debug(f"Added debug message: {message}")

    def get_debug_messages(self, limit: int = 10) -> List[str]:
        """Get recent debug messages"""
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT message FROM debug_messages
                ORDER BY message_id DESC LIMIT ?
            """,
                (limit,),
            ).fetchall()
            return [
                row["message"] for row in reversed(rows)
            ]  # Return in chronological order

    # Auto-persistence methods with unified PersistentDict
    def get_active_task_persistent(self, task_id: str) -> Optional["PersistentDict"]:
        """Get a specific active task as a PersistentDict that auto-saves on modification"""
        existing_data = self.get_active_task(task_id)
        if existing_data is None:
            return None
        # Create save callback for active tasks
        save_callback = lambda data: self.update_active_task(task_id, data)
        return PersistentDict(save_callback, existing_data)

    def create_active_task_persistent(self, task_id: str, payload: Dict[str, Any]) -> "PersistentDict":
        """Create a new active task and return it as a PersistentDict that auto-saves on modification"""
        self.add_active_task(task_id, payload)
        # Create save callback for active tasks
        save_callback = lambda data: self.update_active_task(task_id, data)
        return PersistentDict(save_callback, payload.copy())

    def create_log_persistent(self, task_id: str, run_id: str, agent_type: str, log_data: Dict[str, Any]) -> "PersistentDict":
        """Create a new log entry and return it as a PersistentDict that auto-saves on modification"""
        self.save_log(task_id, run_id, agent_type, log_data)
        # Create save callback for logs
        save_callback = lambda data: self.save_log(task_id, run_id, agent_type, data)
        return PersistentDict(save_callback, log_data.copy())

    def pre_generate_subtask_ids(self, fullstack_run_id: str, num_subtasks: int) -> List[Dict[str, Any]]:
        """
        Generate and store IDs for all possible subtasks from a Fullstack Planner run.
        Returns a list of dictionaries with subtask_id, subtask_index, and agent_type.
        """
        generated_ids = []
        timestamp = int(time.time())

        with self.get_connection() as conn:
            for idx in range(num_subtasks):
                # Generate a unique subtask ID with timestamp and index
                subtask_id = f"pm_subtask_{timestamp}_{idx}"

                # Default to PM agent type for now
                agent_type = "PM"

                # Store in database
                conn.execute("""
                    INSERT OR REPLACE INTO subtask_ids
                    (fullstack_run_id, subtask_index, subtask_id, agent_type)
                    VALUES (?, ?, ?, ?)
                """, (fullstack_run_id, idx, subtask_id, agent_type))

                generated_ids.append({
                    "subtask_id": subtask_id,
                    "subtask_index": idx,
                    "agent_type": agent_type
                })

        return generated_ids

    def get_subtask_ids(self, fullstack_run_id: str) -> List[Dict[str, Any]]:
        """
        Get all pre-generated subtask IDs for a specific Fullstack Planner run.
        Returns a list of dictionaries with subtask_id, subtask_index, and agent_type.
        """
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT subtask_id, subtask_index, agent_type
                FROM subtask_ids
                WHERE fullstack_run_id = ?
                ORDER BY subtask_index
            """, (fullstack_run_id,)).fetchall()

            return [{
                "subtask_id": row["subtask_id"],
                "subtask_index": row["subtask_index"],
                "agent_type": row["agent_type"]
            } for row in rows]

    def get_subtask_id(self, fullstack_run_id: str, subtask_index: int) -> Optional[str]:
        """
        Get a specific pre-generated subtask ID by its index.
        Returns the subtask_id or None if not found.
        """
        with self.get_connection() as conn:
            row = conn.execute("""
                SELECT subtask_id
                FROM subtask_ids
                WHERE fullstack_run_id = ? AND subtask_index = ?
            """, (fullstack_run_id, subtask_index)).fetchone()

            return row["subtask_id"] if row else None


class PersistentDict(dict):
    """
    A unified dictionary that automatically persists changes to the database.

    Features:
    - Auto-saves on any modification (__setitem__, __delitem__, update, etc.)
    - Debouncing to prevent excessive DB writes during rapid updates
    - Thread-safe operations
    - Supports all standard dict operations
    - Configurable save behavior via callback (eliminates code duplication)
    """

    def __init__(self, save_callback, initial_data: Dict[str, Any] = None, debounce_interval: float = 0.1):
        """
        Initialize PersistentDict with a save callback.

        Args:
            save_callback: Function to call when saving (should accept dict data)
            initial_data: Initial dictionary data
            debounce_interval: Debounce interval in seconds (default 100ms)
        """
        super().__init__(initial_data or {})
        self._save_callback = save_callback
        self._lock = threading.RLock()
        self._last_save_time = 0
        self._pending_save = False
        self._debounce_interval = debounce_interval

    def _schedule_save(self):
        """Schedule a save operation with debouncing to prevent excessive DB writes"""
        with self._lock:
            current_time = time.time()
            time_since_last_save = current_time - self._last_save_time

            if time_since_last_save >= self._debounce_interval:
                # Enough time has passed, save immediately
                self._save_to_db()
            elif not self._pending_save:
                # Schedule a delayed save
                self._pending_save = True
                threading.Timer(self._debounce_interval, self._delayed_save).start()

    def _delayed_save(self):
        """Execute a delayed save operation"""
        with self._lock:
            if self._pending_save:
                self._save_to_db()
                self._pending_save = False

    def _save_to_db(self):
        """Actually save the current state to the database via callback"""
        try:
            self._save_callback(dict(self))
            self._last_save_time = time.time()
            logger.debug("Auto-saved data to database via callback")
        except Exception as e:
            logger.error(f"Failed to auto-save data via callback: {e}")

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._schedule_save()

    def __delitem__(self, key):
        super().__delitem__(key)
        self._schedule_save()

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        self._schedule_save()  # Single save operation for batch updates!

    def pop(self, *args, **kwargs):
        result = super().pop(*args, **kwargs)
        self._schedule_save()
        return result

    def popitem(self):
        result = super().popitem()
        self._schedule_save()
        return result

    def clear(self):
        super().clear()
        self._schedule_save()

    def setdefault(self, key, default=None):
        result = super().setdefault(key, default)
        # Only save if we actually added a new key
        if key not in self or self[key] != default:
            self._schedule_save()
        return result

    def force_save(self):
        """Force an immediate save to the database, bypassing debouncing"""
        with self._lock:
            self._save_to_db()
            self._pending_save = False
