import { apiRequest } from "@/utils/api";

export interface ModelProvider {
  models: string[];
  has_valid_key: boolean;
}

export interface ModelsResponse {
  providers: Record<string, ModelProvider>;
  last_updated: string;
}

export async function fetchModels(): Promise<ModelsResponse> {
  return await apiRequest<ModelsResponse>('/api/models', {
    method: 'GET',
  });
}
