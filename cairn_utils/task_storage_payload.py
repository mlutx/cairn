from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, Field
from enum import Enum


class AgentStatus(str, Enum):
    """Status of an agent task"""
    QUEUED = "Queued"
    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"
    SUBTASKS_GENERATED = "Subtasks Generated"
    SUBTASKS_RUNNING = "Subtasks Running"


class AgentType(str, Enum):
    """Type of agent"""
    FULLSTACK_PLANNER = "Fullstack Planner"
    PM = "PM"
    SWE = "SWE"


class BaseAgentOutput(BaseModel):
    """Base class for agent outputs"""
    end_task: bool = Field(default=False, description="Whether this output should end the task")


class SWEAgentOutput(BaseAgentOutput):
    """Output from the SWE agent"""
    summary_of_changes: str = Field(description="Summary of the changes made")
    files_modified: List[str] = Field(description="List of files that were modified")
    verification_status: bool = Field(description="Whether the changes were successfully verified")
    error_messages: List[str] = Field(default_factory=list, description="List of error messages encountered, if any")
    additional_notes: str = Field(default="", description="Any additional notes about the implementation")
    pr_url: Optional[str] = Field(default=None, description="URL of the created pull request, if any")


class PMAgentOutput(BaseAgentOutput):
    """Output from the PM agent"""
    recommendations: List[str] = Field(description="List of recommendations")
    issues_encountered: List[str] = Field(description="List of issues encountered")
    pull_request_message: str = Field(description="Pull request message")
    pr_url: Optional[str] = Field(default=None, description="URL of the created pull request")


class FullstackPlannerAgentOutput(BaseAgentOutput):
    """Output from the Fullstack Planner agent"""
    summary_of_the_problem: str = Field(description="Summary of the problem")
    response_to_the_question: Optional[str] = Field(
        default=None,
        description="Response to the question (if input was a question)"
    )
    most_relevant_code_file_paths: List[str] = Field(
        default_factory=list,
        description="Most relevant code file paths"
    )
    list_of_subtasks: List[str] = Field(
        default_factory=list,
        description="List of subtasks. Each subtask is a detailed description of what to do."
    )
    list_of_subtask_titles: List[str] = Field(
        default_factory=list,
        description="List of subtask titles. Each title is a short description of what to do."
    )
    list_of_subtask_repos: List[str] = Field(
        default_factory=list,
        description="List of the repository that each subtask should be done in"
    )
    assessment_of_difficulty: str = Field(
        default="unknown",
        description="Assessment of whether the problem can be solved easily (high, medium, or low difficulty)"
    )
    assessment_of_subtask_difficulty: List[str] = Field(
        default_factory=list,
        description="Assessment of the difficulty of each subtask"
    )
    assessment_of_subtask_assignment: List[str] = Field(
        default_factory=list,
        description="Assessment of the assignment of each subtask to 'agent' or 'human'"
    )
    recommended_approach: str = Field(
        default="",
        description="Any additional thoughts on the best approach to solve the problem"
    )


class BasePayload(BaseModel):
    """Base payload for all agent types"""
    run_id: str = Field(description="Unique identifier for the task run")
    created_at: str = Field(description="Timestamp when the task was created")
    updated_at: str = Field(description="Timestamp when the task was last updated")
    description: str = Field(description="Description of the task")
    title: Optional[str] = Field(default=None, description="Title of the task")
    owner: str = Field(description="Owner of the repository")
    agent_status: AgentStatus = Field(default=AgentStatus.QUEUED, description="Current status of the agent")
    agent_type: AgentType = Field(description="Type of agent")
    model_provider: Optional[str] = Field(default=None, description="Provider of the model (e.g., 'anthropic', 'openai')")
    model_name: Optional[str] = Field(default=None, description="Name of the model (e.g., 'claude-3-7-sonnet-latest')")
    raw_logs_dump: Dict[str, Any] = Field(default_factory=dict, description="Raw logs from the agent")
    agent_output: Dict[str, Any] = Field(default_factory=dict, description="Output from the agent")
    error: Optional[str] = Field(default=None, description="Error message if the agent failed")


class FullstackPlannerPayload(BasePayload):
    """Payload for Fullstack Planner agent"""
    repos: List[str] = Field(description="List of repositories to analyze")
    subtask_ids: List[str] = Field(default_factory=list, description="List of generated subtask IDs")
    agent_output: FullstackPlannerAgentOutput = Field(default_factory=FullstackPlannerAgentOutput)


class PMSWEBasePayload(BasePayload):
    """Base payload for PM and SWE agents"""
    repo: str = Field(description="Repository name")
    branch: Optional[str] = Field(default=None, description="Branch name")
    related_run_ids: List[str] = Field(default_factory=list, description="IDs of related task runs")
    parent_fullstack_id: Optional[str] = Field(default=None, description="ID of the parent Fullstack Planner task")
    subtask_index: Optional[int] = Field(default=None, description="Index of this subtask within the parent task")
    sibling_subtask_ids: List[str] = Field(default_factory=list, description="IDs of sibling subtasks")


class PMPayload(PMSWEBasePayload):
    """Payload for PM agent"""
    agent_type: AgentType = Field(default=AgentType.PM, description="Type of agent")
    agent_output: PMAgentOutput = Field(default_factory=PMAgentOutput)


class SWEPayload(PMSWEBasePayload):
    """Payload for SWE agent"""
    agent_type: AgentType = Field(default=AgentType.SWE, description="Type of agent")
    agent_output: SWEAgentOutput = Field(default_factory=SWEAgentOutput)


# Union type for all payload types
TaskPayload = Union[FullstackPlannerPayload, PMPayload, SWEPayload]


def create_payload_from_dict(payload_dict: Dict[str, Any]) -> TaskPayload:
    """Create a typed payload from a dictionary"""
    agent_type = payload_dict.get("agent_type")

    if agent_type == AgentType.FULLSTACK_PLANNER:
        return FullstackPlannerPayload(**payload_dict)
    elif agent_type == AgentType.PM:
        return PMPayload(**payload_dict)
    elif agent_type == AgentType.SWE:
        return SWEPayload(**payload_dict)
    else:
        raise ValueError(f"Unknown agent type: {agent_type}")


def payload_to_dict(payload: TaskPayload) -> Dict[str, Any]:
    """Convert a payload to a dictionary"""
    return payload.model_dump()
