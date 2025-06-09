#!/usr/bin/env python3

import json
import os
import sys
import time
import logging
import asyncio
from dotenv import load_dotenv

# Add the cairn_utils directory to the Python path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(parent_dir, 'cairn_utils'))

# Import the wrapper function and task storage
from cairn_utils.agents.wrapper import wrapper
from cairn_utils.task_storage import TaskStorage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('worker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(os.path.join(parent_dir, '.env'))

async def run_agent_task(task_id: str):
    """Run a single agent task"""
    try:
        print(f"[DEBUG] Worker process {os.getpid()} starting for task {task_id}")

        # Initialize task storage
        task_storage = TaskStorage()

        print(f"[DEBUG] Worker {os.getpid()} initialized TaskStorage for task {task_id}")

        # Get the task payload from database
        persistent_payload = task_storage.get_active_task_persistent(task_id)
        logger.info(f"[DEBUG] Worker {os.getpid()} loaded task {task_id} with payload: {persistent_payload}, starting execution...")
        if not persistent_payload:
            logger.error(f"Task {task_id} not found in database")
            return

        print(f"[DEBUG] Worker {os.getpid()} loaded task {task_id}, starting execution...")
        logger.info(f"Worker starting task {task_id}")

        # Update status to running
        persistent_payload["agent_status"] = "Running"
        persistent_payload["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

        print(f"[DEBUG] Worker {os.getpid()} updated status to Running for task {task_id}")

        # Run the agent wrapper
        print(f"[DEBUG] Worker {os.getpid()} calling wrapper() for task {task_id}")
        result = await wrapper(persistent_payload)
        print(f"[DEBUG] Worker {os.getpid()} wrapper() completed for task {task_id}")

        # Update the task with results
        persistent_payload.update(result)
        persistent_payload["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

        print(f"[DEBUG] Worker {os.getpid()} completed task {task_id} with status: {result.get('agent_status', 'unknown')}")
        logger.info(f"Worker completed task {task_id} with status: {result.get('agent_status', 'unknown')}")

    except Exception as e:
        print(f"[DEBUG] Worker {os.getpid()} error in task {task_id}: {str(e)}")
        logger.error(f"Error in worker for task {task_id}: {str(e)}")
        # Update task status to failed
        try:
            task_storage = TaskStorage()
            persistent_payload = task_storage.get_active_task_persistent(task_id)
            if persistent_payload:
                persistent_payload["agent_status"] = "Failed"
                persistent_payload["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        except:
            pass
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

def main():
    """Main worker function"""
    if len(sys.argv) != 2:
        logger.error("Usage: python -m agent_worker <task_id>")
        sys.exit(1)

    task_id = sys.argv[1]
    print(f"[DEBUG] Worker process {os.getpid()} starting for task: {task_id}")
    logger.info(f"Starting worker for task: {task_id}")

    # Run the async task
    asyncio.run(run_agent_task(task_id))

if __name__ == "__main__":
    main()
