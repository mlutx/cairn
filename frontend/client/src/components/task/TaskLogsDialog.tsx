import { useState, useEffect } from "react";
import { Task } from "@/types";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface TaskLogsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  task?: Task | null;
  title?: string;
}

export default function TaskLogsDialog({
  open,
  onOpenChange,
  task,
  title = "Watch your agent cook 🔥"
}: TaskLogsDialogProps) {
  const [logs, setLogs] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [activeTab, setActiveTab] = useState<string>("logs");

  // Fetch logs when dialog opens or task changes
  useEffect(() => {
    let intervalId: number | undefined;

    const fetchLogs = async () => {
      if (!open || !task?.id) return;

      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(`http://localhost:8000/task-logs/${task.id}`);

        if (!response.ok) {
          throw new Error(`Failed to fetch logs: ${response.status} ${response.statusText}`);
        }

        const data = await response.json();
        setLogs(data);
        setLastUpdated(new Date());
      } catch (err) {
        console.error("Error fetching logs:", err);
        setError(err instanceof Error ? err.message : "Failed to fetch logs");
      } finally {
        setIsLoading(false);
      }
    };

    // Initial fetch
    if (open && task?.id && activeTab === "logs") {
      fetchLogs();

      // Set up auto-refresh every 2 seconds
      intervalId = window.setInterval(fetchLogs, 2000);
    }

    // Clean up interval when dialog closes or component unmounts
    return () => {
      if (intervalId) {
        window.clearInterval(intervalId);
      }
    };
  }, [open, task?.id, activeTab]);

  // Reset to logs tab when opening a new task
  useEffect(() => {
    if (open) {
      setActiveTab("logs");
    }
  }, [open, task?.id]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex justify-between items-center">
            <span>{title}</span>
            {lastUpdated && activeTab === "logs" && (
              <span className="text-xs text-muted-foreground">
                Last updated: {lastUpdated.toLocaleTimeString()}
              </span>
            )}
          </DialogTitle>
        </DialogHeader>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid grid-cols-2 mb-4">
            <TabsTrigger value="logs">Logs</TabsTrigger>
            <TabsTrigger value="details">Task Details</TabsTrigger>
          </TabsList>

          <TabsContent value="logs" className="mt-0">
            <div className="bg-slate-950 p-4 rounded-md overflow-auto max-h-96">
              {isLoading && logs.length === 0 ? (
                <div className="space-y-2">
                  <Skeleton className="h-4 w-3/4 bg-slate-800" />
                  <Skeleton className="h-4 w-full bg-slate-800" />
                  <Skeleton className="h-4 w-1/2 bg-slate-800" />
                </div>
              ) : error ? (
                <div className="text-red-400 text-sm">
                  {error}
                </div>
              ) : logs.length === 0 ? (
                <div className="text-slate-400 text-sm">
                  No logs found for this task yet.
                </div>
              ) : (
                <pre className="text-xs text-slate-100 whitespace-pre-wrap">
                  {logs.map((log, index) => (
                    <div key={index} className="mb-2">
                      <strong className="text-blue-300">
                        [{new Date(log.created_at).toLocaleString()}] {log.agent_type}:
                      </strong>
                      <div className="pl-2 mt-1">
                        {typeof log.log_data === 'object'
                          ? JSON.stringify(log.log_data, null, 2)
                          : String(log.log_data)}
                      </div>
                    </div>
                  ))}
                </pre>
              )}
            </div>
          </TabsContent>

          <TabsContent value="details" className="mt-0">
            <div className="bg-slate-950 p-4 rounded-md overflow-auto max-h-96">
              {task ? (
                <pre className="text-xs text-slate-100 whitespace-pre-wrap">
                  {JSON.stringify(task, null, 2)}
                </pre>
              ) : (
                <div className="text-slate-400 text-sm">
                  No task details available.
                </div>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
