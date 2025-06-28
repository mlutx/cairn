import { apiRequest } from "@/utils/api";
import { Task, TeamUser } from "@/types";

interface SubtaskApiParams {
  subtask_ids: string[];
  filters?: Array<{
    field: string;
    operator: string;
    value: string | number | boolean;
  }>;
}

interface Subtask {
  id: string;
  task: string;
  status: string;
  assignee?: string;
  llm_description?: string;
  description?: string;
  assigned_to_agent?: boolean;
  tags?: string[];
  link?: string;
  repos?: string[];
  agent_output?: {
    pr_url?: string;
  };
}

interface AddSubtaskPayload {
  task_id: string;
  description: string;
  status?: string;
  assignee?: string;
  assigned_to_agent?: boolean;
  tags?: string[];
  link?: string;
  repos?: string[];
}

interface RunSubtaskPayload {
  job_id: string;
  payload: {
    subtask_id: string;
  };
}

// Active Task interfaces (from backend)
interface ActiveTask {
  task_id: string;
  payload: any;
  created_at: string;
  updated_at: string;
}

// Task Log interfaces (from backend)
interface TaskLog {
  log_id: string;
  run_id: string;
  agent_type: string;
  log_data: any;
  created_at: string;
  updated_at: string;
}

// Debug Message interfaces
interface DebugMessage {
  message_id: string;
  message: string;
  timestamp: string;
}

// Agent kickoff interfaces (from backend)
interface AgentPayload {
  description: string;
  title?: string;
  model_provider?: string;
  model_name?: string;
  repos?: string[];
  repo?: string;
  branch?: string;
  related_run_ids?: string[];
}

interface KickoffAgentRequest {
  agent_type: "Fullstack Planner" | "PM" | "SWE";
  payload: AgentPayload;
}

interface KickoffAgentResponse {
  run_id: string;
  agent_type: string;
  status: string;
  message: string;
}

interface CreateSubtasksRequest {
  fullstack_planner_run_id: string;
  subtask_index?: number;
}

interface CreateSubtasksResponse {
  created_tasks: any[];
  message: string;
  fullstack_planner_run_id: string;
}

export const taskApi = {
  // ======== ACTIVE TASKS ========
  // Get all active tasks
  async getActiveTasks(): Promise<ActiveTask[]> {
    return await apiRequest<ActiveTask[]>('/active-tasks', {
      method: 'GET',
    });
  },

  // Delete an active task
  async deleteActiveTask(taskId: string): Promise<void> {
    return await apiRequest<void>(`/active-tasks/${taskId}`, {
      method: 'DELETE',
    });
  },

  // ======== AGENT MANAGEMENT ========
  // Kickoff an agent
  async kickoffAgent(request: KickoffAgentRequest): Promise<KickoffAgentResponse> {
    return await apiRequest<KickoffAgentResponse>('/kickoff-agent', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  // Create subtasks from Fullstack Planner
  async createSubtasks(request: CreateSubtasksRequest): Promise<CreateSubtasksResponse> {
    return await apiRequest<CreateSubtasksResponse>('/create-subtasks', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  // ======== TASK LOGS ========
  // Get all task logs
  async getTaskLogs(limit: number = 100): Promise<TaskLog[]> {
    return await apiRequest<TaskLog[]>(`/task-logs?limit=${limit}`, {
      method: 'GET',
    });
  },

  // Get task logs for a specific run ID
  async getTaskLogsByRunId(runId: string): Promise<TaskLog[]> {
    return await apiRequest<TaskLog[]>(`/task-logs/${runId}`, {
      method: 'GET',
    });
  },

  // ======== DEBUG MESSAGES ========
  // Get debug messages
  async getDebugMessages(limit: number = 50): Promise<DebugMessage[]> {
    return await apiRequest<DebugMessage[]>(`/debug-messages?limit=${limit}`, {
      method: 'GET',
    });
  },

  // ======== SUBTASKS (Legacy - from original code) ========
  // Get subtasks for a task
  async getSubtasks(params: SubtaskApiParams) {
    return apiRequest<{ subtasks: Subtask[] }>('/subtasks', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },

  // Run a subtask
  async runSubtask(payload: RunSubtaskPayload) {
    return apiRequest<{ success: boolean; job_id: string }>('/run-subtask', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  // Add a new subtask
  async addSubtask(payload: AddSubtaskPayload) {
    return apiRequest<{ subtask: Subtask }>('/subtasks', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  // Update a task
  async updateTask(taskId: string, updates: Partial<Task>) {
    return apiRequest<{ task: Task }>(`/tasks/${taskId}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    });
  },

  // Get team users for assignment
  async getTeamUsers(teamId: string) {
    return apiRequest<{ users: TeamUser[] }>(`/teams/${teamId}/users`, {
      method: 'GET',
    });
  },
};
