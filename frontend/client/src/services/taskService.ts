import { Task } from "@/types";
import { TaskStatus } from "@/types/task";

// Map backend status to frontend status with intelligent fullstack handling
const mapAgentStatusToTaskStatus = (
  agentStatus: string,
  agentType: string,
  agentOutput: any,
  allTasks: any[],
  currentTaskId: string
): TaskStatus => {
  // For non-fullstack tasks, use simple mapping
  if (agentType !== 'Fullstack Planner') {
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
  }

  // Intelligent fullstack task status
  if (agentType === 'Fullstack Planner') {
    switch (agentStatus) {
      case "Running":
        return "Running";
      case "Queued":
        return "Queued";
      case "Failed":
        return "Failed";
      case "Completed":
        // Check if this fullstack task has virtual subtasks available
        const hasVirtualSubtasks =
          agentOutput?.list_of_subtasks &&
          Array.isArray(agentOutput.list_of_subtasks) &&
          agentOutput.list_of_subtasks.length > 0;

        if (hasVirtualSubtasks) {
          // Find child tasks for this specific fullstack task
          const childTasks = allTasks.filter(task =>
            task.payload?.parent_fullstack_id === currentTaskId
          );

          // Check if any child tasks are running
          const hasRunningSubtasks = childTasks.some(task =>
            task.payload.agent_status === "Running" ||
            task.payload.agent_status === "Queued" ||
            task.payload.agent_status === "Subtasks Running"
          );

          if (hasRunningSubtasks) {
            return "Running";
          }

          // Check if all virtual subtasks have been created as real tasks
          const virtualSubtasksCount = agentOutput.list_of_subtasks.length;
          const realSubtasksCount = childTasks.length;

          // If we have fewer real tasks than virtual tasks, we're waiting for input
          if (realSubtasksCount < virtualSubtasksCount) {
            return "Waiting for Input";
          }

          // Check if all real subtasks are done
          const allSubtasksDone = childTasks.length > 0 &&
            childTasks.every(task =>
              task.payload.agent_status === "Completed"
            );

          if (allSubtasksDone) {
            return "Done";
          }

          // Some tasks exist but not all are done - still running
          return "Running";
        }

        // No subtasks - just completed normally
        return "Done";
      default:
        return "Queued";
    }
  }

  // Fallback
  return "Queued";
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
        status: mapAgentStatusToTaskStatus(agent_status, agent_type, agent_output, data, run_id || item.task_id),
        due_date: undefined,
        repos: reposArray,
        agent_type: agent_type === 'Fullstack Planner' ? 'Fullstack' : (agent_type || 'Unknown'),
        parent_fullstack_id,
        parent_run_id,
        sibling_subtask_ids: Array.isArray(sibling_subtask_ids) ? sibling_subtask_ids : [],
        created_at: created_at || item.created_at,
        updated_at: updated_at || item.updated_at,
        created_by: 'system',
        team: 'default',
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

export async function deleteTask(taskId: string): Promise<boolean> {
  try {
    console.log(`Deleting task with ID: ${taskId}`);
    const response = await fetch(`/active-tasks/${taskId}`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Failed to delete task');
    }

    return true;
  } catch (error) {
    console.error(`Error deleting task ${taskId}:`, error);
    throw error;
  }
}
