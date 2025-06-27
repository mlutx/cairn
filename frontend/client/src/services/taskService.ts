import { Task } from "@/types";
import { TaskStatus } from "@/types/task";

// Map backend status to frontend status
const mapAgentStatusToTaskStatus = (agentStatus: string): TaskStatus => {
  switch (agentStatus) {
    case "Completed":
      return "Done";
    case "Running":
      return "Running";
    case "Queued":
      return "Queued";
    case "Failed":
      return "Failed";
    case "Subtasks Generated":
    case "Subtasks Running":
      return "Running";
    case "Waiting for Input":
      return "Waiting for Input";
    default:
      return "Queued";
  }
};

export async function fetchTasks(): Promise<Task[]> {
  try {
    console.log("Fetching tasks from API...");
    const response = await fetch('/active-tasks');
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    console.log("Raw API response:", data);

    // Map backend tasks to frontend Task format
    const convertedTasks = data.map((item: any) => {
      const payload = item.payload || {};
      console.log("Processing task item:", item);
      console.log("Task payload:", payload);

      // Extract relevant fields from payload
      const {
        run_id,
        title,
        description,
        agent_status,
        agent_type,
        repo,
        repos = [],
        parent_fullstack_id,
        parent_run_id,
        sibling_subtask_ids = [],
        created_at,
        updated_at,
        agent_output = {},
        team = 'default'
      } = payload;

      // Handle repos field - it could be a single repo string or an array of repos
      let reposArray: string[] = [];
      if (Array.isArray(repos) && repos.length > 0) {
        reposArray = repos;
      } else if (repo && typeof repo === 'string') {
        reposArray = [repo];
      }

      // Create a Task object with the required fields
      const task: Task = {
        id: run_id || item.task_id,
        title: title || (description ? description.split('\n')[0].substring(0, 50) : 'Untitled Task'),
        description: description || '',
        status: mapAgentStatusToTaskStatus(agent_status),
        due_date: undefined,
        repos: reposArray,
        agent_type: agent_type === 'Fullstack Planner' ? 'Fullstack' : (agent_type || 'Unknown'),
        parent_fullstack_id,
        parent_run_id,
        sibling_subtask_ids: Array.isArray(sibling_subtask_ids) ? sibling_subtask_ids : [],
        created_at: created_at || item.created_at,
        updated_at: updated_at || item.updated_at,
        created_by: 'system',
        team: team,
        agent_output: agent_output
      };

      console.log("Converted task:", task);
      return task;
    });

    console.log("All converted tasks:", convertedTasks);
    return convertedTasks;
  } catch (error) {
    console.error("Failed to fetch tasks:", error);
    return [];
  }
}
