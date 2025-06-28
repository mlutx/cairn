import { useState, useEffect, useCallback, useRef } from "react";
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

  // Use refs to maintain stable references across re-renders
  const taskIdRef = useRef<string | undefined>();
  const intervalRef = useRef<number | undefined>();
  const isDialogOpenRef = useRef(open);
  const componentIdRef = useRef(`TaskLogsDialog-${Math.random().toString(36).substr(2, 9)}`);

  // Get stable task ID for useEffect dependencies
  const taskId = task?.id;

  console.log(`[${componentIdRef.current}] TaskLogsDialog render - open:`, open, 'taskId:', taskId, 'task object changed:', task !== taskIdRef.current);

  // Update refs when values change
  useEffect(() => {
    console.log(`[${componentIdRef.current}] Refs update effect - taskId:`, taskId, 'open:', open);
    taskIdRef.current = taskId;
    isDialogOpenRef.current = open;
  }, [taskId, open]);

  // Stable onOpenChange callback that prevents unwanted closures
  const handleOpenChange = useCallback((newOpen: boolean) => {
    console.log(`[${componentIdRef.current}] handleOpenChange called - newOpen:`, newOpen, 'current state:', isDialogOpenRef.current);
    console.log(`[${componentIdRef.current}] Call stack:`, new Error().stack);

    // Only allow closing if the dialog is actually open and we're not in the middle of a re-render
    if (!newOpen && !isDialogOpenRef.current) {
      console.log(`[${componentIdRef.current}] PREVENTED CLOSE - dialog wasn't actually open`);
      return; // Prevent closing if dialog wasn't actually open
    }

    console.log(`[${componentIdRef.current}] ALLOWING state change to:`, newOpen);
    onOpenChange(newOpen);
  }, [onOpenChange]);

  // Fetch logs when dialog opens or task changes
  useEffect(() => {
    console.log(`[${componentIdRef.current}] Main effect triggered - open:`, open, 'taskId:', taskId, 'activeTab:', activeTab);

    const fetchLogs = async () => {
      if (!isDialogOpenRef.current || !taskIdRef.current) {
        console.log(`[${componentIdRef.current}] fetchLogs skipped - open:`, isDialogOpenRef.current, 'taskId:', taskIdRef.current);
        return;
      }

      console.log(`[${componentIdRef.current}] Fetching logs for task:`, taskIdRef.current);
      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(`http://localhost:8000/task-logs/${taskIdRef.current}`);

        if (!response.ok) {
          throw new Error(`Failed to fetch logs: ${response.status} ${response.statusText}`);
        }

        const data = await response.json();
        console.log(`[${componentIdRef.current}] Logs fetched successfully - count:`, data.length);
        setLogs(data);
        setLastUpdated(new Date());
      } catch (err) {
        console.error(`[${componentIdRef.current}] Error fetching logs:`, err);
        setError(err instanceof Error ? err.message : "Failed to fetch logs");
      } finally {
        setIsLoading(false);
      }
    };

    // Clear any existing interval
    if (intervalRef.current) {
      console.log(`[${componentIdRef.current}] Clearing existing interval:`, intervalRef.current);
      window.clearInterval(intervalRef.current);
      intervalRef.current = undefined;
    }

    // Initial fetch and set up interval if dialog is open
    if (open && taskId && activeTab === "logs") {
      console.log(`[${componentIdRef.current}] Starting log fetching and interval`);
      fetchLogs();

      // Set up auto-refresh every 2 seconds
      intervalRef.current = window.setInterval(() => {
        console.log(`[${componentIdRef.current}] Interval tick - fetching logs`);
        fetchLogs();
      }, 2000);
      console.log(`[${componentIdRef.current}] Interval set with ID:`, intervalRef.current);
    }

    // Clean up interval when dependencies change
    return () => {
      console.log(`[${componentIdRef.current}] Main effect cleanup`);
      if (intervalRef.current) {
        console.log(`[${componentIdRef.current}] Cleanup: clearing interval:`, intervalRef.current);
        window.clearInterval(intervalRef.current);
        intervalRef.current = undefined;
      }
    };
  }, [open, taskId, activeTab]);

  // Reset to logs tab when opening a new task
  useEffect(() => {
    console.log(`[${componentIdRef.current}] Tab reset effect - open:`, open, 'taskId:', taskId);
    if (open) {
      console.log(`[${componentIdRef.current}] Resetting to logs tab`);
      setActiveTab("logs");
    }
  }, [open, taskId]);

  // Log when component unmounts
  useEffect(() => {
    return () => {
      console.log(`[${componentIdRef.current}] Component unmounting`);
    };
  }, []);

  console.log(`[${componentIdRef.current}] About to render Dialog with open:`, open);

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
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

        <Tabs value={activeTab} onValueChange={(value) => {
          console.log(`[${componentIdRef.current}] Tab changed to:`, value);
          setActiveTab(value);
        }} className="w-full">
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
