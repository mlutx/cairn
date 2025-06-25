export type TaskStatus = "Queued" | "Running" | "Done" | "Failed" | "Waiting for Input";
export type AgentType = "Fullstack" | "PM" | "SWE";

export interface Task {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  agent_type: AgentType;
  project?: string;
  created_at: string;
  updated_at: string;
  due_date?: string;
  repos: string[];
  tags?: string[];
  topic?: string;
  created_by: string;
  team: string;
  model_provider?: string;
  model_name?: string;
  link?: string;
  explore_queued_at?: string;
  explore_done_at?: string;
  explore_result?: any;
  jobs?: string[];
  createdAt?: string;
  updatedAt?: string;
}

export interface Subtask {
  id: string;
  task: string;
  status: TaskStatus;
  assignee?: string;
  title?: string;
  llm_description?: string;
  description?: string;
  assigned_to_agent?: boolean;
  priority?: string;
  tags?: string[];
  link?: string;
  repos?: string[];
  run_ids?: string[];
  agent_output?: {
    pr_url?: string;
    branch?: string;
    recommendations?: string[];
    issues_encountered?: string[];
  };
  agent_queued_at?: string | null;
  agent_done_at?: string | null;
  explore_queued_at?: string | null;
  explore_done_at?: string | null;
  explore_result?: Record<string, any> | null;
}
