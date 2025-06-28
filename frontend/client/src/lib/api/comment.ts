import { apiRequest } from "@/utils/api";

export interface Comment {
  id: string;
  content: string;
  author: string;
  created_at: string;
  task_id?: string;
}

export interface AddCommentPayload {
  task_id: string;
  content: string;
  author: string;
}

export const commentApi = {
  // Add a new comment to a task
  async addComment(payload: AddCommentPayload): Promise<Comment> {
    const response = await apiRequest<{ comment: Comment }>('/api/comments', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return response.comment;
  },

  // Get comments for a task
  async getComments(taskId: string): Promise<Comment[]> {
    const response = await apiRequest<{ comments: Comment[] }>(`/api/tasks/${taskId}/comments`, {
      method: 'GET',
    });
    return response.comments;
  },

  // Delete a comment
  async deleteComment(commentId: string): Promise<void> {
    return await apiRequest<void>(`/api/comments/${commentId}`, {
      method: 'DELETE',
    });
  },
};
