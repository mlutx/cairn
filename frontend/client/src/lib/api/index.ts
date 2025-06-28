import { apiRequest } from "@/utils/api";

export interface Repository {
  owner: string;
  repo: string;
  installation_id?: number;
  rules?: string[];
}

export interface RepoResponse {
  repos: Repository[];
  general_rules: string[];
}

export interface RepoStats {
  owner: string;
  repo: string;
  contributors: Array<{
    login: string;
    avatar_url: string;
    contributions: number;
    html_url: string;
  }>;
  languages: Array<{
    name: string;
    percentage: number;
  }>;
  file_ownership: Record<string, {
    authors: Record<string, {
      commits: number;
      lines_changed: number;
      additions: number;
      deletions: number;
    }>;
    last_modified: string | null;
  }>;
  commit_times: {
    hour_of_day: number[];
    day_of_week: number[];
    month: number[];
  };
  commit_authors: Record<string, {
    total: number;
    hours: number[];
    days: number[];
  }>;
}

// Fetch connected repositories
export async function fetchConnectedRepos(): Promise<RepoResponse> {
  return await apiRequest<RepoResponse>('/api/repos', {
    method: 'GET',
  });
}

// Add a new repository
export async function addRepository(repo: Repository): Promise<Repository> {
  return await apiRequest<Repository>('/api/repos', {
    method: 'POST',
    body: JSON.stringify(repo),
  });
}

// Delete a repository
export async function deleteRepository(owner: string, repo: string): Promise<void> {
  return await apiRequest<void>(`/api/repos/${owner}/${repo}`, {
    method: 'DELETE',
  });
}

// Get repository statistics
export async function getRepoStats(owner: string, repo: string): Promise<RepoStats> {
  return await apiRequest<RepoStats>(`/api/repos/${owner}/${repo}/stats`, {
    method: 'GET',
  });
}

// Refresh repository cache
export async function refreshReposCache(): Promise<{ message: string; timestamp: string }> {
  return await apiRequest<{ message: string; timestamp: string }>('/api/repos/refresh-cache', {
    method: 'POST',
  });
}

// Get app configuration
export async function getConfig(): Promise<any> {
  return await apiRequest<any>('/config', {
    method: 'GET',
  });
}

// Health check
export async function healthCheck(): Promise<{ status: string }> {
  return await apiRequest<{ status: string }>('/health', {
    method: 'GET',
  });
}
