import { useState, useMemo, useEffect, useRef } from "react";
import { Task } from "@/types";
import { TaskStatus } from "@/types/task";
import TaskCard from "./TaskCard";
import TaskForm from "./TaskForm";
import { Skeleton } from "@/components/ui/skeleton";
import { MoreHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import TaskDetailsSidebar from "./TaskDetailsSidebar";
import { useTasks } from "@/contexts/TaskContext";
import { useNavigate } from "react-router-dom";
import { useToast } from "@/components/ui/use-toast";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface KanbanBoardProps {
  project?: string;
}

// Mock logs data
const mockLogs = {
  columnId: "Running",
  tasks: [
    {
      taskId: "task-123",
      title: "Implement user authentication",
      events: [
        {
          timestamp: "2023-07-15T12:30:45Z",
          type: "status_change",
          data: { from: "Queued", to: "Running" }
        },
        {
          timestamp: "2023-07-15T12:45:22Z",
          type: "agent_assigned",
          data: { agent: "Fullstack" }
        }
      ]
    },
    {
      taskId: "task-124",
      title: "Create dashboard UI",
      events: [
        {
          timestamp: "2023-07-16T09:15:30Z",
          type: "status_change",
          data: { from: "Queued", to: "Running" }
        },
        {
          timestamp: "2023-07-16T10:20:45Z",
          type: "comment_added",
          data: { comment: "Working on implementing the feature" }
        }
      ]
    }
  ]
};

// Helper function to sort tasks by due date
const sortTasksByDueDate = (tasks: Task[]): Task[] => {
  return [...tasks].sort((a, b) => {
    if (!a.due_date) return 1;
    if (!b.due_date) return -1;
    return new Date(a.due_date).getTime() - new Date(b.due_date).getTime();
  });
};

export default function KanbanBoard({ project }: KanbanBoardProps) {
  const [selectedTask, setSelectedTask] = useState<Task | undefined>(undefined);
  const [isTaskFormOpen, setIsTaskFormOpen] = useState(false);
  const [isDetailsSidebarOpen, setIsDetailsSidebarOpen] = useState(false);
  const [logsDialogOpen, setLogsDialogOpen] = useState(false);
  const [selectedColumnId, setSelectedColumnId] = useState<string | null>(null);
  const { tasks, isLoading, error } = useTasks();
  const navigate = useNavigate();
  const { toast } = useToast();

  // Memoize filtered tasks to prevent unnecessary re-renders
  const { projectTasks, queuedTasks, runningTasks, doneTasks, failedTasks } = useMemo(() => {
    // Filter tasks by project if specified
    const filteredTasks = project
      ? tasks.filter(task => task.project === project)
      : tasks;

    // Filter tasks by status and sort by due date
    const queued = sortTasksByDueDate(
      filteredTasks.filter((task: Task) => task.status === "Queued")
    );
    const running = sortTasksByDueDate(
      filteredTasks.filter((task: Task) => task.status === "Running")
    );
    const done = sortTasksByDueDate(
      filteredTasks.filter((task: Task) => task.status === "Done")
    );
    const failed = sortTasksByDueDate(
      filteredTasks.filter((task: Task) => task.status === "Failed")
    );

    return {
      projectTasks: filteredTasks,
      queuedTasks: queued,
      runningTasks: running,
      doneTasks: done,
      failedTasks: failed,
    };
  }, [tasks, project]);

  // Handle task click to show details sidebar
  const handleTaskClick = (task: Task) => {
    // // Instead of navigating, show a toast notification
    // toast({
    //   title: "Task Selected",
    //   description: "Task details view has been removed from the application.",
    // });
  };

  // Handle task edit
  const handleTaskEdit = (task: Task) => {
    setSelectedTask(task);
    setIsTaskFormOpen(true);
  };

  // Handle view logs click
  const handleViewLogsClick = (columnId: string) => {
    setSelectedColumnId(columnId);
    setLogsDialogOpen(true);
  };

  // Kanban column component
  const KanbanColumn = ({
    title,
    tasks,
    color,
    status,
    columnId
  }: {
    title: string;
    tasks: Task[];
    color: string;
    status: TaskStatus;
    columnId: string;
  }) => (
    <div className="bg-card rounded-lg shadow border border-border flex flex-col h-full">
      <div className="px-4 py-1 border-b border-border">
        <div className="flex items-center justify-between">
          <h3 className="font-regular text-sm text-foreground flex items-center">
            <span className={`w-3 h-3 rounded-full ${color} mr-2`}></span>
            {title}
            <span className="ml-2 text-sm bg-muted px-2 py-0.5 rounded-full">{tasks.length}</span>
          </h3>
          <div className="flex items-center">
            <Button variant="ghost" size="icon" className="text-muted-foreground hover:text-foreground">
              <MoreHorizontal className="h-5 w-5" />
            </Button>
          </div>
        </div>
      </div>
      <div className="p-4 space-y-3 flex-grow overflow-y-auto border-b border-border/30">
        {isLoading ? (
          Array(3).fill(0).map((_, index) => (
            <div key={index} className="space-y-2">
              <Skeleton className="h-6 w-3/4" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-full" />
              <div className="flex justify-between items-center mt-3">
                <Skeleton className="h-6 w-24 rounded-full" />
                <Skeleton className="h-4 w-12" />
              </div>
            </div>
          ))
        ) : tasks.length === 0 ? (
          <div className="text-center text-muted-foreground h-full flex items-center justify-center min-h-[200px]">
            <p>No tasks</p>
          </div>
        ) : (
          tasks.map((task, index) => (
            <div key={task.id} className="transition-all duration-300 ease-in-out">
              <TaskCard
                task={task}
                onClick={() => handleTaskClick(task)}
              />
            </div>
          ))
        )}
      </div>
    </div>
  );

  if (error) {
    return <div className="text-center text-destructive py-4">Error loading tasks</div>;
  }

  return (
    <div className="h-full flex flex-col">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 h-full">
        <KanbanColumn
          title="Queued"
          tasks={queuedTasks}
          color="bg-gray-500"
          status="Queued"
          columnId="Queued"
        />
        <KanbanColumn
          title="Running"
          tasks={runningTasks}
          color="bg-yellow-500"
          status="Running"
          columnId="Running"
        />
        <KanbanColumn
          title="Done"
          tasks={doneTasks}
          color="bg-emerald-500"
          status="Done"
          columnId="Done"
        />
        <KanbanColumn
          title="Failed"
          tasks={failedTasks}
          color="bg-red-500"
          status="Failed"
          columnId="Failed"
        />
      </div>

      {/* Task Logs Dialog */}
      <Dialog open={logsDialogOpen} onOpenChange={setLogsDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              Watch your agent cook 🔥
            </DialogTitle>
          </DialogHeader>
          <div className="bg-slate-950 p-4 rounded-md overflow-auto max-h-96">
            <pre className="text-xs text-slate-100">{JSON.stringify(mockLogs, null, 2)}</pre>
          </div>
        </DialogContent>
      </Dialog>

      {/* Task Details Sidebar */}
      {selectedTask && (
        <TaskDetailsSidebar
          task={selectedTask}
          isOpen={isDetailsSidebarOpen}
          onClose={() => setIsDetailsSidebarOpen(false)}
        />
      )}

      {/* Task Edit Form Dialog */}
      <TaskForm
        open={isTaskFormOpen}
        onOpenChange={setIsTaskFormOpen}
        initialData={selectedTask}
        mode="edit"
      />
    </div>
  );
}
