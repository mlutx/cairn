import { Comment as TaskComment } from "@/lib/api/comment";
import { AgentType, TaskStatus } from "./task";

export interface Subtask {
  id: string;
  title: string;
  status: string;
  task: string;
  llm_description?: string;
  assigned_to_agent?: boolean;
  run_ids?: string[];
  agent_output?: {
    branch: string;
    pr_url: string;
    recommendations: string[];
    issues_encountered: string[];
    pull_request_message: string;
  };
}

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
  subtasks?: Task[];
  comments?: TaskComment[];
  created_by: string;
  link?: string;
  explore_queued_at?: string;
  explore_done_at?: string;
  explore_result?: any;
  repos: string[];
  jobs?: string[];
  createdAt?: string;
  updatedAt?: string;
  dueDate?: string;
  topic?: string;
  priority?: string;
  assignees?: string[];
  model_provider?: string;
  model_name?: string;
  // Parent-child relationship fields:
  // For PM tasks: parent_fullstack_id refers to parent Fullstack task
  parent_fullstack_id?: string;
  // For SWE tasks: parent_run_id refers to parent PM task
  parent_run_id?: string;
  // For tasks that are related but not in parent-child relationship
  related_run_ids?: string[];
  // For parent tasks (Fullstack or PM): IDs of child tasks
  sibling_subtask_ids?: string[];
}

export interface User {
  id: string;
  email: string;
  first_name?: string;
  last_name?: string;
  profile_pic?: string;
  created_at?: string;
  updated_at?: string;
}

export interface TaskFormData {
  title: string;
  description?: string;
  status: TaskStatus;
  agent_type?: AgentType;
  dueDate?: Date | string;
  topic?: string;
  repos?: string[];
  model_provider?: string;
  model_name?: string;
}

export interface FilterOptions {
  status?: TaskStatus | 'all';
  agent_type?: AgentType | 'all';
  topic?: string | 'all';
  repo?: string | 'all';
  searchQuery?: string;
  sortBy?: 'created_at' | 'updated_at' | 'due_date' | 'title' | 'status' | 'agent_type';
  sortOrder?: 'asc' | 'desc';
}

export interface TeamUser {
  uid: string;
  first_name: string;
  last_name: string;
  account_email_address: string;
  team_ids: string[];
  role?: string;
  avatar?: string;
}
