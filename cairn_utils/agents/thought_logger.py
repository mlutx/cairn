"""
Defines a simple class that updates agent logs with auto-persistence.

The log document can be used to track the progress of an agent, by keeping running tabs on the messages generated thus far.
All changes are automatically persisted to the database with debouncing for performance.
"""

import time
import logging
import os

from task_storage import TaskStorage


# Configure global file logger
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "langgraph.log")

file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

logger = logging.getLogger("langgraph")
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)


class AgentLogger:

    def __init__(self, run_id: str, task_id: str = None):
        self.run_id = run_id
        self.task_id = task_id or run_id  # Default to run_id if task_id not provided
        self.verbose = False

        self.task_storage = TaskStorage()

        self._setup_log_document()

    def load_log_document(self) -> dict:
        """
        Load the log document - returns the auto-persisting log dict.
        """
        return dict(self.log_document)  # Return a regular dict copy for compatibility

    def log_message(self, message: dict):
        """
        Update the log document with a new message - auto-saves to database!
        """
        self.log_document["progress"].append(message)
        self.log_document["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")

        # Also log to file
        log_entry = f"Task: {self.task_id} | Run: {self.run_id} | Message: {message}"
        logger.info(log_entry)

    def _setup_log_document(self):
        """
        Setup the auto-persisting log document.
        """
        # Try to load existing log from database
        existing_log = self.task_storage.load_log(self.run_id, "agent_logger")

        if existing_log:
            # Create auto-persisting log from existing data
            self.log_document = self.task_storage.create_log_persistent(
                self.task_id, self.run_id, "agent_logger", existing_log
            )
        else:
            # Create new auto-persisting log document
            initial_log_data = {
                "task_id": self.task_id,
                "run_id": self.run_id,
                "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
                "progress": []
            }
            self.log_document = self.task_storage.create_log_persistent(
                self.task_id, self.run_id, "agent_logger", initial_log_data
            )

            # Register this run_id with the task
            self.task_storage.add_run_id_to_task(self.task_id, self.run_id)

            # Log initialization to file
            logger.info(f"Initialized logger for Task: {self.task_id} | Run: {self.run_id}")
