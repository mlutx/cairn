export type TaskStatus = "Queued" | "Running" | "Done" | "Failed" | "Waiting for Input";
export type AgentType = "Fullstack" | "PM" | "SWE" | "Unassigned";

export interface Task {
  id: string;
  title: string;
  description?: string;
  status: TaskStatus;
  due_date?: string;
  created_at: string;
  updated_at: string;
  agent_type?: AgentType;
  tags?: string[];
  projects?: string[];
  subtasks?: Task[];
  comments?: Comment[];
  created_by: string;
  team: string;
  link?: string;
  explore_queued_at?: string;
  explore_done_at?: string;
  explore_result?: any;
  repos?: string[];
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
