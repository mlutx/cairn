"""
A langgraph version of the ProjectManager class, similar to how langgraph_explorer.py is a langgraph version of the ExplorerAgent class.
"""

import asyncio
import os
import sys
import time
import json
from typing import Any, Dict, List

from dotenv import load_dotenv

# Try relative import first (for when module is imported as part of package)
try:
    from agent_classes import ManagerToolBox
    from llm_consts import ChatAnthropic
    from .agent_consts import AgentState, STRUCTURED_PM_PROMPT
    from .thought_logger import AgentLogger
    from .agent_consts import STRUCTURED_PM_PROMPT, AgentState

    # from ..supabase_utils import get_supabase_client, get_other_agents_from_subtask_id
    from .fullstack_planner import ExplorerAgent
    from .langgraph_utils import (
        create_agent_graph,
        create_run_config,
        format_other_agents_info,
        print_run_end,
        print_run_start,
    )
    from .swe import SoftwareEngineerAgent
    from .thought_logger import AgentLogger
    from supported_models import find_supported_model_given_model_name, SUPPORTED_MODELS
except (ImportError, ModuleNotFoundError):
    # Add parent directory to path for tools and supabase_utils
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from agent_classes import ManagerToolBox
    # from supabase_utils import get_supabase_client, get_other_agents_from_subtask_id

    # Add current directory to sys.path for agent_consts and other local modules
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))

    from agent_consts import STRUCTURED_PM_PROMPT, AgentState
    from thought_logger import AgentLogger

    # Add project root to path for cairn_utils imports
    parent_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)

    from cairn_utils.agents.swe import SoftwareEngineerAgent
    from langgraph_utils import (
        create_agent_graph,
        create_run_config,
        format_other_agents_info,
    )
    from llm_consts import ChatAnthropic
    from swe import SoftwareEngineerAgent
    from supported_models import find_supported_model_given_model_name, SUPPORTED_MODELS


class ProjectManagerAgent:
    """A LangGraph agent that manages projects using ManagerToolBox tools and delegates to SoftwareEngineer."""

    def __init__(self):
        """Initialize the ProjectManagerAgent with default values."""
        self.graph = None
        self.toolbox = None
        self.logger = None
        self.llm_client = None
        self.live_logging = False
        self.run_id = None
        self.swe = None
        self.branch = None
        self.subtask_id = None
        self.other_agents = None

    async def setup(
        self,
        owner: str,
        repos: list[str],
        installation_id: int,
        branch: str,
        model_provider: str,
        model_name: str,
        llm_client=None,
        live_logging=False,
        subtask_id=None,
        supabase_client=None,
        run_id=None,
        running_locally=False,
        other_agents=None,
        fake_calls_path: str = None
    ):
        """
        Set up the agent with necessary components.

        Args:
            owner (str): GitHub repository owner
            repos (list[str]): List of repositories
            installation_id (int): GitHub installation ID
            branch (str): Repository branch
            model_name (str): LLM model name
            llm_client: LLM client to use. If None, creates new one.
            live_logging (bool): Whether to print live logs
            subtask_id (str): Subtask ID for coordination
            supabase_client: Supabase client for logging
            run_id (str): Run ID for logging
            running_locally (bool): Whether running locally
            other_agents (list[dict]): list of other agents' info to use for coordination.
            -> dict should have keys of run_id, description, and repo (each keyed to a string)
            fake_calls_path (str): Path to JSON file containing fake LLM responses for testing

        Returns:
            ProjectManagerAgent: The configured agent instance
        """
        if not branch:
            raise ValueError("Branch is required for ProjectManagerAgent")

        # Set instance variables
        self.live_logging = live_logging
        self.run_id = run_id or str(int(time.time()))
        self.branch = branch
        self.running_locally = running_locally
        self.other_agents = other_agents
        self.subtask_id = None
        self.model_provider = model_provider
        self.model_name = model_name
        # Setup clients and dependencies
        await self._setup_clients()
        await self._setup_swe_agent(owner, repos, installation_id, branch, model_name, run_id)
        await self._setup_toolbox(owner, repos, installation_id, branch, model_name)
        self._setup_llm_and_logger(llm_client, model_name, fake_calls_path)
        await self._setup_graph(repos, branch)

        if self.live_logging:
            print(f"Project Manager agent ready on branch '{self.branch}'.")

        return self

    async def _setup_clients(self):
        """A method to setup clients for the agent. This is a placeholder for now."""
        pass



    async def _setup_swe_agent(self, owner, repos, installation_id, branch, model_name, run_id):
        """Initialize and setup the Software Engineer agent."""
        if self.live_logging:
            print(f"Initializing Software Engineer agent for branch '{branch}'...")

        swe = SoftwareEngineerAgent()
        await swe.setup(
            owner=owner,
            repos=repos,
            installation_id=installation_id,
            branch=branch,
            model_provider=self.model_provider,
            model_name=model_name,
            live_logging=self.live_logging,
            run_id=run_id+'_swe',
            subtask_id=self.subtask_id,
            other_agents=self.other_agents,
            running_locally=self.running_locally,
            running_from_pm=True,
        )
        self.swe = swe

        if self.live_logging:
            print("Software Engineer agent initialized.")

    async def _setup_toolbox(self, owner, repos, installation_id, branch, model_name):
        """Initialize and authenticate the toolbox."""
        self.toolbox = ManagerToolBox(
            owner,
            repos,
            installation_id,
            branch,
            model_name,
            self.subtask_id,
            self.other_agents,
            running_locally=self.running_locally,
            parent_run_id=self.run_id,
        )

        self.toolbox.set_swe(self.swe)
        await self.toolbox.authenticate()

    def _setup_llm_and_logger(self, llm_client, model_name, fake_calls_path=None):
        """Setup LLM client and logger."""
        if not self.logger:
            self.logger = AgentLogger(
                run_id=self.run_id,
            )

        # find the correct chat client
        chat_info = SUPPORTED_MODELS[self.model_provider]
        if not self.model_name in chat_info['models']:
            print('-'*50)
            print(f'[DEBUG] Model {self.model_name} not found in {self.model_provider} models. May not be supported!')
            print('-'*50)

        chat_client = chat_info['chat_class']
        self.llm_client = chat_client(model=model_name)

        # Load fake responses if path is provided
        if fake_calls_path and os.path.exists(fake_calls_path):
            try:
                with open(fake_calls_path, "r") as f:
                    fake_calls = json.load(f)
                for fake_call in fake_calls.get("fake_calls", []):
                    self.llm_client.add_fake_response(fake_call)
                if self.live_logging:
                    print(f"Loaded fake responses from {fake_calls_path}")
            except Exception as e:
                raise RuntimeError(f"Failed to load fake responses from {fake_calls_path}. This is a fatal error as test responses are required: {str(e)}")

    async def _setup_graph(self, repos, branch):
        """Create and configure the agent graph."""
        tools = self.toolbox.get_all_tools()
        tools_dict = {tool["name"]: tool for tool in tools}
        tool_names = list(tools_dict.keys())

        other_agents_info = format_other_agents_info(self.other_agents)

        prompt = STRUCTURED_PM_PROMPT.partial(
            tools="\n".join([f"{tool['name']}: {tool['description']}" for tool in tools]),
            tool_names=", ".join(tool_names),
            available_repos=", ".join(repos),
            branch=branch,
            other_agents_info=other_agents_info,
        )

        self.graph = create_agent_graph(
            tools=tools,
            prompt=prompt,
            llm_client=self.llm_client,
            logger=self.logger,
            toolbox=self.toolbox,
            state_type=AgentState,
        )

    async def run(self, project_description: str, run_id: str = None) -> Dict[str, Any]:
        """
        Run the agent with the given project description.

        Args:
            project_description (str): The project to implement
            run_id (str): Unique identifier for the run

        Returns:
            Dict: The final state after completion

        Raises:
            ValueError: If the agent has not been set up
        """
        if self.graph is None:
            raise ValueError("Agent not set up. Call setup() first.")

        # Update run_id if provided
        if run_id:
            self.run_id = run_id
            if self.logger:
                self.logger.run_id = run_id

        initial_state = AgentState(user_input=project_description)

        # print_run_start(
        #     f"PROJECT MANAGER AGENT RUN WITH PROJECT: {project_description}",
        #     self.live_logging,
        # )

        config = create_run_config(self.run_id)
        result = await self.graph.ainvoke(initial_state, config=config)

        # print_run_end(self.live_logging)

        return result


# Example usage
async def main(owner: str = "cairn-dev", repos: List[str] = ["test"]):
    """Example usage of ProjectManagerAgent"""

    load_dotenv()

    # Create a unique branch for this run
    timestamp = int(time.time())
    branch = f"pm-agent-test-{timestamp}"
    run_id = f"test_run_{timestamp}"

    project_description = "add an endpont that returns a random emoji"

    # Create and setup the agent
    agent = ProjectManagerAgent()
    await agent.setup(
        owner=owner,
        repos=repos,
        installation_id=65848345,
        branch=branch,
        live_logging=True,
        run_id=run_id,
        subtask_id="970f06f8-03de-4e76-9386-6feed924358c",
    )

    pm_result = await agent.run(project_description)
    print(pm_result)


if __name__ == "__main__":
    asyncio.run(main())
