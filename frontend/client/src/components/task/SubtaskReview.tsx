import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Bot, User, Play, ExternalLink } from "lucide-react";
import { taskApi } from "@/lib/api/task";
import { Subtask, TaskStatus } from "@/types";
import { useToast } from "@/components/ui/use-toast";

interface SubtaskReviewProps {
  taskId: string;
  onApprove: () => void;
  onManualGenerate: () => void;
}

export function SubtaskReview({ taskId, onApprove, onManualGenerate }: SubtaskReviewProps) {
  const [status, setStatus] = useState<'loading' | 'failed' | 'done'>('loading');
  const [runningSubtasks, setRunningSubtasks] = useState<Set<string>>(new Set());
  const [completedSubtasks, setCompletedSubtasks] = useState<Set<string>>(new Set());
  const [completedSubtasksData, setCompletedSubtasksData] = useState<Record<string, Subtask>>({});
  const { toast } = useToast();

  // Poll for task status every 5 seconds
  const { data: taskData } = useQuery({
    queryKey: ['task-status', taskId],
    queryFn: async () => {
      const response = await taskApi.getTasks({ task_ids: [taskId] });
      return response.tasks[0];
    },
    refetchInterval: 5000,
    enabled: status === 'loading',
  });

  // Fetch subtasks when task is done
  const { data: subtasksData } = useQuery({
    queryKey: ['subtasks', taskId],
    queryFn: async () => {
      if (!taskData?.subtasks) return { subtasks: [] };
      const response = await taskApi.getSubtasks({ subtask_ids: taskData.subtasks as unknown as string[] });
      return response;
    },
    enabled: status === 'done' && !!taskData?.subtasks,
  });

  // Poll for running subtasks
  const { data: runningSubtasksData } = useQuery({
    queryKey: ['running-subtasks', Array.from(runningSubtasks)],
    queryFn: async () => {
      if (runningSubtasks.size === 0) return { subtasks: [] };
      const response = await taskApi.getSubtasks({ subtask_ids: Array.from(runningSubtasks) });
      return response;
    },
    refetchInterval: 5000,
    enabled: runningSubtasks.size > 0,
  });

  useEffect(() => {
    if (taskData) {
      if (taskData.status === 'Agent Failed') {
        setStatus('failed');
      } else if (taskData.status === 'Agent Done: Review') {
        setStatus('done');
      }
    }
  }, [taskData]);

  useEffect(() => {
    if (runningSubtasksData?.subtasks) {
      // Check if any subtasks are done
      runningSubtasksData.subtasks.forEach((subtask) => {
        console.log('Checking subtask:', subtask.id);
        console.log('Status:', subtask.status);
        console.log('PR URL:', subtask.agent_output?.pr_url);
        if (subtask.status === 'Agent Done: Review') {
          console.log('Subtask completed:', subtask.id);
          console.log('PR URL:', subtask.agent_output?.pr_url);
          setRunningSubtasks((prev) => {
            const newSet = new Set(prev);
            newSet.delete(subtask.id);
            return newSet;
          });
          setCompletedSubtasks((prev) => new Set(prev).add(subtask.id));
          setCompletedSubtasksData((prev) => ({
            ...prev,
            [subtask.id]: subtask
          }));
        }
      });
    }
  }, [runningSubtasksData]);

  const handleRunSubtask = async (subtaskId: string) => {
    try {
      const jobId = `subtask-${subtaskId}-${Date.now()}`;
      await taskApi.runSubtask({
        job_id: jobId,
        payload: { subtask_id: subtaskId }
      });
      setRunningSubtasks((prev) => new Set(prev).add(subtaskId));
      toast({
        title: "Success",
        description: "Subtask has been queued for processing",
      });
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "Failed to run subtask",
        variant: "destructive",
      });
    }
  };

  if (status === 'loading') {
    return (
      <div className="flex flex-col items-center justify-center p-8 space-y-4">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
        <p className="text-lg font-medium">Generating and assigning subtasks...</p>
      </div>
    );
  }

  if (status === 'failed') {
    return (
      <div className="flex flex-col items-center justify-center p-8 space-y-4">
        <p className="text-lg font-medium text-red-500">Auto-generation of subtasks failed</p>
        <Button onClick={onManualGenerate}>Generate subtasks manually</Button>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <div className="space-y-4">
        {subtasksData?.subtasks.map((subtask: Subtask) => {
          const isRunning = runningSubtasks.has(subtask.id);
          const isCompleted = completedSubtasks.has(subtask.id);
          const runningSubtaskData = runningSubtasksData?.subtasks.find(s => s.id === subtask.id);
          const completedSubtaskData = completedSubtasksData[subtask.id];
          const subtaskData = isCompleted ? completedSubtaskData : runningSubtaskData;

          return (
            <div key={subtask.id} className="p-4 border rounded-lg">
              <div className="flex items-start justify-between">
                <div className="space-y-1">
                  <h3 className="font-medium">{subtask.title}</h3>
                  <p className="text-sm text-muted-foreground">{subtask.llm_description}</p>
                  {(isRunning || isCompleted) && (
                    <div className="mt-2 flex items-center gap-2">
                      <p className="text-sm font-medium text-primary">
                        Status: {isCompleted ? 'Completed' : (subtaskData?.status || 'Processing...')}
                      </p>
                      {!isCompleted && subtaskData?.status !== 'Agent Done: Review' && (
                        <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-primary"></div>
                      )}
                    </div>
                  )}
                  {isCompleted && subtaskData?.agent_output?.pr_url && (
                    <div className="mt-2">
                      <Button
                        variant="default"
                        size="sm"
                        onClick={() => window.open(subtaskData.agent_output?.pr_url, '_blank')}
                        className="w-full bg-green-500 hover:bg-green-600"
                      >
                        <ExternalLink className="h-4 w-4 mr-2" />
                        View Pull Request
                      </Button>
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {subtask.assigned_to_agent ? (
                    <>
                      <Bot className="h-5 w-5 text-primary" />
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleRunSubtask(subtask.id)}
                        disabled={isRunning || isCompleted}
                      >
                        <Play className="h-4 w-4 mr-2" />
                        {isRunning ? 'Running...' : isCompleted ? 'Completed' : 'Run'}
                      </Button>
                    </>
                  ) : (
                    <User className="h-5 w-5 text-primary" />
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <div className="flex justify-end">
        <Button onClick={onApprove}>Approve subtasks</Button>
      </div>
    </div>
  );
}
