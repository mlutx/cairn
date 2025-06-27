import { useState, useMemo, useEffect, useRef } from "react";
import { Task } from "@/types";
import { TaskStatus } from "@/types/task";
import TaskCard from "./TaskCard";
import TaskForm from "./TaskForm";
import { Skeleton } from "@/components/ui/skeleton";
import { MoreHorizontal, ChevronDown, ChevronRight } from "lucide-react";
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

// Helper function to check if a task is a child task
const isChildTask = (task: Task): boolean => {
  return !!task.parent_run_id || !!task.parent_fullstack_id;
};

// Helper function to check if a task has subtasks in its agent_output
const hasSubtasksInOutput = (task: Task): boolean => {
  return (
    task.agent_type === "Fullstack" &&
    task.status === "Done" &&
    !!task.agent_output &&
    !!task.agent_output.list_of_subtasks &&
    Array.isArray(task.agent_output.list_of_subtasks) &&
    task.agent_output.list_of_subtasks.length > 0
  );
};

// Interface for virtual subtasks created from agent output
interface VirtualSubtask {
  id: string;
  title: string;
  description: string;
  repo: string;
  difficulty: string;
  assignment: string;
  index: number;
  parentTaskId: string;
}

export default function KanbanBoard({ project }: KanbanBoardProps) {
  const [selectedTask, setSelectedTask] = useState<Task | undefined>(undefined);
  const [isTaskFormOpen, setIsTaskFormOpen] = useState(false);
  const [isDetailsSidebarOpen, setIsDetailsSidebarOpen] = useState(false);
  const [logsDialogOpen, setLogsDialogOpen] = useState(false);
  const [selectedColumnId, setSelectedColumnId] = useState<string | null>(null);
  const [expandedTasks, setExpandedTasks] = useState<Set<string>>(new Set());
  const [isCreatingSubtask, setIsCreatingSubtask] = useState(false);
  const [currentSubtaskIndex, setCurrentSubtaskIndex] = useState<number | null>(null);
  const [currentParentTaskId, setCurrentParentTaskId] = useState<string | null>(null);
  const { tasks, isLoading, error, refreshTasks } = useTasks();
  const navigate = useNavigate();
  const { toast } = useToast();

  // Toggle task expansion
  const toggleTaskExpansion = (taskId: string) => {
    const newExpandedTasks = new Set(expandedTasks);
    if (newExpandedTasks.has(taskId)) {
      newExpandedTasks.delete(taskId);
    } else {
      newExpandedTasks.add(taskId);
    }
    setExpandedTasks(newExpandedTasks);
  };

  // Create a subtask from fullstack planner output
  const createSubtask = async (parentTaskId: string, subtaskIndex: number) => {
    setIsCreatingSubtask(true);
    setCurrentSubtaskIndex(subtaskIndex);
    setCurrentParentTaskId(parentTaskId);

    try {
      const response = await fetch('http://localhost:8000/create-subtasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          fullstack_planner_run_id: parentTaskId,
          subtask_index: subtaskIndex
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create subtask');
      }

      const result = await response.json();

      if (result.created_tasks.length > 0) {
        toast({
          title: "Success",
          description: `Created subtask successfully`,
        });
        // Refresh tasks to show the newly created subtask
        refreshTasks();
      } else {
        toast({
          title: "Note",
          description: result.message,
          variant: "default",
        });
      }
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to create subtask",
        variant: "destructive",
      });
    } finally {
      setIsCreatingSubtask(false);
      setCurrentSubtaskIndex(null);
      setCurrentParentTaskId(null);
    }
  };

  // Run a subtask that's already been created
  const runSubtask = async (taskId: string) => {
    try {
      const response = await fetch(`http://localhost:8000/run-task/${taskId}`, {
        method: 'POST'
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to run task');
      }

      const result = await response.json();

      toast({
        title: "Success",
        description: "Task started successfully",
      });

      // Refresh tasks to show updated status
      refreshTasks();
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to run task",
        variant: "destructive",
      });
    }
  };

  // Memoize filtered tasks to prevent unnecessary re-renders
  const { projectTasks, queuedTasks, runningTasks, doneTasks, failedTasks, waitingForInputTasks, taskMap, childTaskMap, virtualSubtaskMap } = useMemo(() => {
    // Filter tasks by project if specified
    const filteredTasks = project
      ? tasks.filter(task => task.repos?.includes(project))
      : tasks;

    // Create a map of tasks by their IDs for quick lookup
    const taskMap = new Map<string, Task>();
    filteredTasks.forEach(task => {
      taskMap.set(task.id, task);
    });

    // Create a map of child tasks by their parent IDs
    const childTaskMap = new Map<string, Task[]>();
    filteredTasks.forEach(task => {
      // Check for parent relationship
      if (task.parent_run_id || task.parent_fullstack_id) {
        const parentId = task.parent_run_id || task.parent_fullstack_id;
        if (parentId) {
          const children = childTaskMap.get(parentId) || [];
          children.push(task);
          childTaskMap.set(parentId, children);
        }
      }
    });

    // Create virtual subtasks from fullstack planner output
    const virtualSubtaskMap = new Map<string, VirtualSubtask[]>();

    filteredTasks.forEach(task => {
      if (hasSubtasksInOutput(task)) {
        const subtasks = task.agent_output?.list_of_subtasks || [];
        const subtaskTitles = task.agent_output?.list_of_subtask_titles || [];
        const subtaskRepos = task.agent_output?.list_of_subtask_repos || [];
        const subtaskDifficulties = task.agent_output?.assessment_of_subtask_difficulty || [];
        const subtaskAssignments = task.agent_output?.assessment_of_subtask_assignment || [];

        // Check if there are already child tasks for this parent
        const existingChildTasks = childTaskMap.get(task.id) || [];

        // Track which subtask indices already have tasks created
        const existingSubtaskIndices = new Set();

        // Check both by subtask_index and by matching titles/descriptions
        existingChildTasks.forEach(childTask => {
          // Check by subtask_index if available
          if (childTask.agent_output && typeof childTask.agent_output.subtask_index !== 'undefined') {
            existingSubtaskIndices.add(childTask.agent_output.subtask_index);
          }

          // Also check by title/description match
          subtasks.forEach((subtaskDesc, idx) => {
            const subtaskTitle = subtaskTitles[idx] || `Subtask ${idx + 1}`;

            // If title or description matches, consider this subtask already created
            if (
              (childTask.title && subtaskTitle && childTask.title.includes(subtaskTitle)) ||
              (childTask.description && subtaskDesc && childTask.description.includes(subtaskDesc))
            ) {
              existingSubtaskIndices.add(idx);
            }
          });
        });

        // Only create virtual subtasks for those that don't have real tasks yet
        const virtualSubtasks: VirtualSubtask[] = [];

        subtasks.forEach((subtask, index) => {
          // Skip if this subtask index already has a real task
          if (existingSubtaskIndices.has(index)) {
            return;
          }

          virtualSubtasks.push({
            id: `virtual-${task.id}-${index}`,
            title: subtaskTitles[index] || `Subtask ${index + 1}`,
            description: subtask,
            repo: subtaskRepos[index] || '',
            difficulty: subtaskDifficulties[index] || 'Not specified',
            assignment: subtaskAssignments[index] || 'agent',
            index,
            parentTaskId: task.id
          });
        });

        if (virtualSubtasks.length > 0) {
          virtualSubtaskMap.set(task.id, virtualSubtasks);
        }
      }
    });

    // Get only parent tasks (tasks without parent_run_id or parent_fullstack_id)
    const getParentTasks = (tasks: Task[]): Task[] => {
      return tasks.filter(task => !isChildTask(task));
    };

    // Filter tasks by status and get only parent tasks
    const queued = sortTasksByDueDate(
      getParentTasks(filteredTasks.filter((task: Task) => task.status === "Queued"))
    );
    const running = sortTasksByDueDate(
      getParentTasks(filteredTasks.filter((task: Task) => task.status === "Running"))
    );
    const done = sortTasksByDueDate(
      getParentTasks(filteredTasks.filter((task: Task) => task.status === "Done"))
    );
    const failed = sortTasksByDueDate(
      getParentTasks(filteredTasks.filter((task: Task) => task.status === "Failed"))
    );
    const waitingForInput = sortTasksByDueDate(
      getParentTasks(filteredTasks.filter((task: Task) => task.status === "Waiting for Input"))
    );

    return {
      projectTasks: filteredTasks,
      queuedTasks: queued,
      runningTasks: running,
      doneTasks: done,
      failedTasks: failed,
      waitingForInputTasks: waitingForInput,
      taskMap,
      childTaskMap,
      virtualSubtaskMap
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

  // Render a virtual subtask card
  const renderVirtualSubtaskCard = (subtask: VirtualSubtask) => {
    const isCurrentlyCreating = isCreatingSubtask &&
                               currentSubtaskIndex === subtask.index &&
                               currentParentTaskId === subtask.parentTaskId;

    return (
      <div key={subtask.id} className="pl-4 mt-2 border-l-2 border-slate-600 bg-slate-800/30 p-3 rounded-md">
        <div className="flex justify-between items-start">
          <div>
            <h4 className="text-sm font-medium">{subtask.title}</h4>
            <p className="text-xs text-muted-foreground mt-1">{subtask.description}</p>
            <div className="flex gap-2 mt-2">
              <span className="text-xs px-2 py-1 bg-slate-700 rounded-full">{subtask.difficulty}</span>
              <span className="text-xs px-2 py-1 bg-slate-700 rounded-full">{subtask.assignment}</span>
              <span className="text-xs px-2 py-1 bg-slate-700 rounded-full">{subtask.repo}</span>
            </div>
          </div>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => createSubtask(subtask.parentTaskId, subtask.index)}
            disabled={isCurrentlyCreating}
          >
            {isCurrentlyCreating ? "Creating..." : "Create Task"}
          </Button>
        </div>
      </div>
    );
  };

  // Render a task card with expansion controls if needed
  const renderTaskCard = (task: Task, nestingLevel: number = 0) => {
    const hasChildren = task.sibling_subtask_ids && task.sibling_subtask_ids.length > 0;
    const isExpanded = expandedTasks.has(task.id);
    const childTasks = childTaskMap.get(task.id) || [];
    const virtualSubtasks = virtualSubtaskMap.get(task.id) || [];
    const hasChildTasks = childTasks.length > 0;
    const hasVirtualSubtasks = virtualSubtasks.length > 0;
    const shouldShowExpansionControl = hasChildren || hasChildTasks || hasVirtualSubtasks || hasSubtasksInOutput(task);

    // Create expansion control if task has children or subtasks
    const expansionControl = shouldShowExpansionControl ? (
      <Button
        variant="ghost"
        size="icon"
        className="h-5 w-5 p-0"
        onClick={(e) => {
          e.stopPropagation();
          toggleTaskExpansion(task.id);
        }}
      >
        {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
      </Button>
    ) : null;

    return (
      <div key={task.id} className="transition-all duration-300 ease-in-out">
        <TaskCard
          task={task}
          onClick={() => handleTaskClick(task)}
          expansionControl={expansionControl}
        />

        {/* Show child tasks and virtual subtasks when expanded */}
        {isExpanded && (
          <div className="pl-4 mt-2 border-l-2 border-slate-600 space-y-2">
            {/* Render real child tasks */}
            {childTasks.map((childTask: Task) => {
              // For child tasks that were created from subtasks, add a "Run" button if they're not running/completed
              const isSubtask = childTask.parent_fullstack_id === task.id;
              const canRun = isSubtask && childTask.status !== "Running" && childTask.status !== "Done";

              return (
                <div key={childTask.id} className="relative">
                  <TaskCard
                    task={childTask}
                    onClick={() => handleTaskClick(childTask)}
                    expansionControl={null}
                  />
                  {canRun && (
                    <div className="absolute top-2 right-2">
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={(e) => {
                          e.stopPropagation();
                          runSubtask(childTask.id);
                        }}
                      >
                        Run Task
                      </Button>
                    </div>
                  )}
                </div>
              );
            })}

            {/* Render virtual subtasks from agent output */}
            {hasVirtualSubtasks && virtualSubtasks.map(renderVirtualSubtaskCard)}
          </div>
        )}
      </div>
    );
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
          tasks.map(task => renderTaskCard(task))
        )}
      </div>
    </div>
  );

  if (error) {
    return <div className="text-center text-destructive py-4">Error loading tasks</div>;
  }

  return (
    <div className="h-full flex flex-col">
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4 h-full">
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
          title="Waiting for Input"
          tasks={waitingForInputTasks}
          color="bg-blue-500"
          status="Waiting for Input"
          columnId="Waiting for Input"
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
