import React, { createContext, useContext, useState, useCallback, useEffect } from "react";
import { Task } from "@/types";
import { fetchTasks as apiFetchTasks } from "@/services/taskService";

interface TaskContextType {
  tasks: Task[];
  addTask: (task: Task) => void;
  updateTask: (taskId: string, updates: Partial<Task>) => void;
  updateTaskStatus: (taskId: string, status: Task['status']) => void;
  deleteTask: (taskId: string) => void;
  isLoading: boolean;
  error: Error | null;
  refreshTasks: () => Promise<void>;
  autoRefreshEnabled: boolean;
  setAutoRefreshEnabled: (enabled: boolean) => void;
}

const TaskContext = createContext<TaskContextType | undefined>(undefined);

export const TaskProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(true);

  // Fetch tasks from API
  const fetchTasks = useCallback(async (isManualRefresh: boolean = false) => {
    if (isManualRefresh) {
      setIsLoading(true);
    }

    try {
      // Use our task service to get tasks from the API
      const fetchedTasks = await apiFetchTasks();
      setError(null);
      // Only update if changed (shallow compare by id and status)
      setTasks(prevTasks => {
        if (
          prevTasks.length === fetchedTasks.length &&
          prevTasks.every((t, i) => t.id === fetchedTasks[i].id && t.status === fetchedTasks[i].status)
        ) {
          return prevTasks;
        }
        return fetchedTasks;
      });
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to fetch tasks'));
      console.error('Error fetching tasks:', err);
    } finally {
      if (isManualRefresh) {
        setIsLoading(false);
      }
    }
  }, []);

  // Refresh tasks manually
  const refreshTasks = useCallback(async () => {
    await fetchTasks(true);
  }, [fetchTasks]);

  // Add a new task
  const addTask = useCallback((task: Task) => {
    setTasks(prevTasks => [task, ...prevTasks]);
  }, []);

  // Update a task
  const updateTask = useCallback((taskId: string, updates: Partial<Task>) => {
    setTasks(prevTasks =>
      prevTasks.map(task =>
        task.id === taskId ? { ...task, ...updates } : task
      )
    );
  }, []);

  // Update a task's status
  const updateTaskStatus = useCallback((taskId: string, status: Task['status']) => {
    setTasks(prevTasks =>
      prevTasks.map(task =>
        task.id === taskId ? { ...task, status } : task
      )
    );
  }, []);

  // Delete a task
  const deleteTask = useCallback((taskId: string) => {
    setTasks(prevTasks => prevTasks.filter(task => task.id !== taskId));
  }, []);

  // Initial fetch
  useEffect(() => {
    fetchTasks(true);
  }, [fetchTasks]);

  // Auto-refresh every 10 seconds if enabled
  useEffect(() => {
    let intervalId: number | undefined;

    if (autoRefreshEnabled) {
      intervalId = window.setInterval(() => {
        fetchTasks(false);
      }, 10000);
    }

    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [autoRefreshEnabled, fetchTasks]);

  return (
    <TaskContext.Provider
      value={{
        tasks,
        addTask,
        updateTask,
        updateTaskStatus,
        deleteTask,
        isLoading,
        error,
        refreshTasks,
        autoRefreshEnabled,
        setAutoRefreshEnabled,
      }}
    >
      {children}
    </TaskContext.Provider>
  );
};

export const useTasks = () => {
  const context = useContext(TaskContext);
  if (context === undefined) {
    throw new Error("useTasks must be used within a TaskProvider");
  }
  return context;
};
