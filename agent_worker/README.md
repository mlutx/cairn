# Agent Worker Module

This module provides a worker process implementation for running agent tasks in the Cairn system.

## Usage

The worker can be run in two ways:

1. As a module:
   ```
   python -m agent_worker <task_id>
   ```

2. Programmatically:
   ```python
   import asyncio
   from agent_worker import run_agent_task

   # Run a specific task
   asyncio.run(run_agent_task("task_12345"))
   ```

## Architecture

The agent worker:

1. Loads a task from the database using TaskStorage
2. Updates the task status to "Running"
3. Executes the task using the wrapper function
4. Updates the task with results when complete

This module is designed to be run as a separate process for true parallelism when handling multiple tasks.
