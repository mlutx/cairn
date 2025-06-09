#!/usr/bin/env python3

import sys
import os
import asyncio

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the run_agent_task function from the worker module
from agent_worker.worker import run_agent_task, main

if __name__ == "__main__":
    main()
