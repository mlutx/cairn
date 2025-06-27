import { useState, useMemo, useEffect, Fragment } from "react";
import { useQuery } from "@tanstack/react-query";
import { Task, FilterOptions, TeamUser } from "@/types";
import { AgentType } from "@/types/task";
import { StatusBadge } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardFooter,
  CardTitle
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { useToast } from "@/hooks/use-toast";
import { format } from "date-fns";
import TaskForm from "./TaskForm";
import { ArrowUpDown, ChevronDown, ChevronUp, Download, Pencil, Trash2, ChevronRight } from "lucide-react";
import { getInitials } from "@/lib/utils/task-utils";
import { Skeleton } from "@/components/ui/skeleton";
import TaskDetailsSidebar from "./TaskDetailsSidebar";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import TaskLogsDialog from "./TaskLogsDialog";
import { taskApi } from "@/lib/api/task";
import { useAuth } from "@/contexts/AuthContext";
import { useTasks } from "@/contexts/TaskContext";
import { useNavigate, useSearchParams, useLocation } from "react-router-dom";
import sweAvatar from "@/assets/swe-icon.png";
import pmAvatar from "@/assets/pm-icon.png";
import fullstackAvatar from "@/assets/fullstack-icon.png";

// Mock team members data
const mockTeamMembers: TeamUser[] = [
  {
    uid: "user-1",
    first_name: "John",
    last_name: "Doe",
    account_email_address: "john.doe@example.com",
    team_ids: ["team-1"]
  },
  {
    uid: "user-2",
    first_name: "Jane",
    last_name: "Smith",
    account_email_address: "jane.smith@example.com",
    team_ids: ["team-1"]
  },
  {
    uid: "user-3",
    first_name: "Bob",
    last_name: "Johnson",
    account_email_address: "bob.johnson@example.com",
    team_ids: ["team-1"]
  }
];

// Mock logs data
const mockLogs = {
  taskId: "task-123",
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
    },
    {
      timestamp: "2023-07-15T13:15:10Z",
      type: "comment_added",
      data: { comment: "Working on implementing the feature" }
    }
  ]
};

// Define agent types
const agentTypes = ["Fullstack", "PM", "SWE"];

// Define column configuration for sorting
const columns = [
  { id: 'title', label: 'Title', sortable: true },
  { id: 'status', label: 'Status', sortable: true },
  { id: 'agent_type', label: 'Agent Type', sortable: true },
  { id: 'repos', label: 'Repositories', sortable: false },
  { id: 'created_at', label: 'Created', sortable: true },
  { id: 'due_date', label: 'Due Date', sortable: true },
  { id: 'actions', label: 'Actions', sortable: false },
];

// Helper function to check if a task is a child task
const isChildTask = (task: Task): boolean => {
  return !!task.parent_run_id || !!task.parent_fullstack_id;
};

interface ListViewProps {
  project?: string;
}

export default function ListView({ project = "" }: ListViewProps) {
  const { toast } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();

  // Initialize filter options from URL parameters or defaults
  const initialSortBy = searchParams.get('sort') || 'created_at';
  const initialSortOrder = searchParams.get('order') || 'desc';
  const initialStatus = searchParams.get('status') || 'all';
  const initialAgentType = searchParams.get('agent_type') || 'all';
  const initialTopic = searchParams.get('topic') || 'all';

  const [filterOptions, setFilterOptions] = useState<FilterOptions>({
    status: initialStatus as any,
    agent_type: initialAgentType as 'all' | AgentType,
    topic: initialTopic,
    sortBy: initialSortBy as keyof FilterOptions['sortBy'],
    sortOrder: initialSortOrder as 'asc' | 'desc'
  });

  const [selectedTask, setSelectedTask] = useState<Task | undefined>(undefined);
  const [isEditFormOpen, setIsEditFormOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [taskToDelete, setTaskToDelete] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [isDetailsSidebarOpen, setIsDetailsSidebarOpen] = useState(false);
  const [logsDialogOpen, setLogsDialogOpen] = useState(false);
  const [selectedTaskForLogs, setSelectedTaskForLogs] = useState<Task | null>(null);
  const [expandedTasks, setExpandedTasks] = useState<Set<string>>(new Set());
  const pageSize = 10;
  const { user } = useAuth();
  const teamId = user?.team_id;
  const { tasks, isLoading, error, deleteTask } = useTasks();

  // Use mock team members data instead of API call
  const teamMembers = mockTeamMembers;

  // Toggle task expansion
  const toggleTaskExpansion = (taskId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const newExpandedTasks = new Set(expandedTasks);
    if (newExpandedTasks.has(taskId)) {
      newExpandedTasks.delete(taskId);
    } else {
      newExpandedTasks.add(taskId);
    }
    setExpandedTasks(newExpandedTasks);
  };

  // Update URL when filter options change
  useEffect(() => {
    const newParams = new URLSearchParams(searchParams);
    // Set sorting and filtering parameters
    if (filterOptions.sortBy) newParams.set('sort', filterOptions.sortBy);
    if (filterOptions.sortOrder) newParams.set('order', filterOptions.sortOrder);
    if (filterOptions.status !== 'all') newParams.set('status', filterOptions.status as string);
    if (filterOptions.agent_type !== 'all') newParams.set('agent_type', filterOptions.agent_type as string);
    if (filterOptions.topic !== 'all') newParams.set('topic', filterOptions.topic as string);

    // Ensure view parameter is preserved
    if (!newParams.has('view')) {
      newParams.set('view', 'list');
    }

    // Only update if params have changed to avoid unnecessary history entries
    if (newParams.toString() !== searchParams.toString()) {
      setSearchParams(newParams);
    }
  }, [filterOptions, setSearchParams, searchParams]);

  // Handle task click to show details
  const handleTaskClick = (task: Task) => {
    // Instead of navigating, show a toast notification
    // toast({
    //   title: "Task Selected",
    //   description: "Task details view has been removed from the application.",
    // });
  };

  // Handle edit button click
  const handleEditClick = (task: Task) => {
    setSelectedTask(task);
    setIsEditFormOpen(true);
  };

  // Handle delete button click
  const handleDeleteClick = (taskId: string) => {
    setTaskToDelete(taskId);
    setIsDeleteDialogOpen(true);
  };

  // Handle confirm delete
  const handleConfirmDelete = async () => {
    if (taskToDelete) {
      try {
        await taskApi.deleteTasks([taskToDelete]);
        deleteTask(taskToDelete);
        toast({
          title: "Task deleted",
          description: "The task has been deleted successfully.",
        });
      } catch (error) {
        toast({
          title: "Error",
          description: "Failed to delete task. Please try again.",
          variant: "destructive",
        });
      }
    }
    setIsDeleteDialogOpen(false);
  };

  // Handle filter changes
  const handleFilterChange = (field: keyof FilterOptions, value: string) => {
    setFilterOptions(prev => ({ ...prev, [field]: value }));
    setCurrentPage(1); // Reset to first page when filters change
  };

  // Handle export
  const handleExport = () => {
    if (!tasks?.length) return;

    const dataStr = JSON.stringify(tasks, null, 2);
    const dataUri = "data:application/json;charset=utf-8," + encodeURIComponent(dataStr);

    const exportFileDefaultName = `tasks-export-${new Date().toISOString().slice(0, 10)}.json`;

    const linkElement = document.createElement("a");
    linkElement.setAttribute("href", dataUri);
    linkElement.setAttribute("download", exportFileDefaultName);
    linkElement.click();
  };

  // Enhanced handleSort function to handle column header clicks
  const handleSort = (field: string) => {
    if (!field || !columns.find(col => col.id === field)?.sortable) return;

    setFilterOptions(prev => ({
      ...prev,
      sortBy: field as keyof FilterOptions['sortBy'],
      sortOrder: prev.sortBy === field && prev.sortOrder === "asc" ? "desc" : "asc",
    }));
  };

  // Get sort icon based on current sort state
  const getSortIcon = (columnId: string) => {
    if (filterOptions.sortBy !== columnId) {
      return <ArrowUpDown className="ml-1 h-3 w-3 opacity-50" />;
    }

    return filterOptions.sortOrder === 'asc'
      ? <ChevronUp className="ml-1 h-3 w-3" />
      : <ChevronDown className="ml-1 h-3 w-3" />;
  };

  // Generate shareable URL with current sorting settings
  const getShareableUrl = () => {
    const baseUrl = window.location.origin + location.pathname;
    // Ensure we keep the view parameter in the URL
    const newParams = new URLSearchParams(searchParams);
    if (!newParams.has('view')) {
      newParams.set('view', 'list');
    }
    return `${baseUrl}?${newParams.toString()}`;
  };

  // Copy shareable URL to clipboard
  const copyShareableUrl = () => {
    const url = getShareableUrl();
    navigator.clipboard.writeText(url).then(() => {
      toast({
        title: "URL copied to clipboard",
        description: "You can now share this URL with others.",
      });
    }).catch(err => {
      toast({
        title: "Failed to copy URL",
        description: "Please try again or copy the URL manually.",
        variant: "destructive",
      });
    });
  };

  // Handle view logs click
  const handleViewLogsClick = (task: Task) => {
    setSelectedTaskForLogs(task);
    setLogsDialogOpen(true);
  };

  // Get agent avatar based on agent type
  const getAgentAvatar = (agentType: string | undefined): string | undefined => {
    switch (agentType) {
      case "SWE":
        return sweAvatar;
      case "PM":
        return pmAvatar;
      case "Fullstack":
        return fullstackAvatar;
      default:
        return undefined;
    }
  };

  // Helper function to render child tasks recursively
  const renderChildTasks = (parentTask: Task, childTaskMap: Map<string, Task[]>, level: number) => {
    const childTasks = childTaskMap.get(parentTask.id) || [];
    if (childTasks.length === 0) return null;

    return childTasks.map((childTask: Task) => (
      <Fragment key={childTask.id}>
        <TableRow
          className="cursor-pointer hover:bg-muted/50 bg-muted/20 border-l-2 border-blue-500"
          onClick={() => handleTaskClick(childTask)}
        >
          <TableCell className="font-regular text-sm">
            <div className="flex items-center" style={{ paddingLeft: `${level * 20 + 6}px` }}>
              {/* First, always render the return arrow for consistent alignment */}
              <span className="text-xs text-muted-foreground mr-2 w-4 inline-block text-center">↳</span>

              {/* Then, create a container for the expansion button and title */}
              <div className="flex items-center gap-2">
                {/* Conditionally render expansion button */}
                {((childTask.sibling_subtask_ids && childTask.sibling_subtask_ids.length > 0) ||
                  (childTaskMap.get(childTask.id) && childTaskMap.get(childTask.id)!.length > 0)) && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-5 w-5 p-0"
                    onClick={(e) => toggleTaskExpansion(childTask.id, e)}
                  >
                    {expandedTasks.has(childTask.id) ? (
                      <ChevronDown className="h-3 w-3" />
                    ) : (
                      <ChevronRight className="h-3 w-3" />
                    )}
                  </Button>
                )}
                {/* Always render the title */}
                {childTask.title}
              </div>
            </div>
          </TableCell>
          <TableCell>
            <StatusBadge status={childTask.status} />
          </TableCell>
          <TableCell>
            <div className="flex items-center gap-2">
              {childTask.agent_type && getAgentAvatar(childTask.agent_type) && (
                <div className="w-5 h-5 flex items-center justify-center">
                  <img
                    src={getAgentAvatar(childTask.agent_type)}
                    alt={childTask.agent_type}
                    className="w-4 h-4 object-contain"
                  />
                </div>
              )}
              <Badge variant="outline" className="text-xs">
                {childTask.agent_type || 'Unknown'}
              </Badge>
            </div>
          </TableCell>
          <TableCell className="text-xs">
            {childTask.repos && childTask.repos.length > 0 ? (
              <div className="flex flex-wrap gap-1">
                {childTask.repos.map((repo, idx) => (
                  <Badge key={idx} variant="secondary" className="text-xs">
                    {repo}
                  </Badge>
                ))}
              </div>
            ) : (
              <span className="text-muted-foreground">No repos</span>
            )}
          </TableCell>
          <TableCell className="text-sm">{format(new Date(childTask.created_at), "MMM d, yyyy")}</TableCell>
          <TableCell className="text-sm pr-6">
            {childTask.due_date ? format(new Date(childTask.due_date), "MMM d, yyyy") : "-"}
          </TableCell>
          <TableCell className="text-right">
            <div className="flex justify-end space-x-1">
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={(e) => {
                  e.stopPropagation();
                  handleViewLogsClick(childTask);
                }}
                title="View Logs"
              >
                <span className="text-xs">🪵</span>
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={(e) => {
                  e.stopPropagation();
                  handleEditClick(childTask);
                }}
              >
                <Pencil className="h-3 w-3" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={(e) => {
                  e.stopPropagation();
                  handleDeleteClick(childTask.id);
                }}
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            </div>
          </TableCell>
        </TableRow>

        {/* Recursively render this child's children if expanded */}
        {expandedTasks.has(childTask.id) && renderChildTasks(childTask, childTaskMap, level + 1)}
      </Fragment>
    ));
  };

  // Memoize filtered and sorted tasks to prevent unnecessary re-renders
  const { filteredTasks, paginatedTasks, totalPages, childTaskMap } = useMemo(() => {
    // Start with all tasks
    let filtered = tasks;

    // Apply project filter if specified
    if (project) {
      filtered = filtered.filter((task: Task) => task.project === project);
    }

    // Apply status filter
    if (filterOptions.status !== 'all') {
      filtered = filtered.filter((task: Task) => task.status === filterOptions.status);
    }

    // Apply agent type filter
    if (filterOptions.agent_type !== 'all') {
      filtered = filtered.filter((task: Task) => task.agent_type === filterOptions.agent_type);
    }

    // Apply topic filter
    if (filterOptions.topic !== 'all') {
      filtered = filtered.filter((task: Task) =>
        task.tags?.includes(filterOptions.topic!) ?? false
      );
    }

    // Create a map of child tasks by their parent IDs
    const childTaskMap = new Map<string, Task[]>();
    filtered.forEach(task => {
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

    // Filter out child tasks from main list (we'll show them nested under parents)
    const parentTasks = filtered.filter(task => !isChildTask(task));

    // Sort tasks
    parentTasks.sort((a: Task, b: Task) => {
      const aValue = a[filterOptions.sortBy as keyof Task];
      const bValue = b[filterOptions.sortBy as keyof Task];

      if (typeof aValue === 'string' && typeof bValue === 'string') {
        return filterOptions.sortOrder === 'asc'
          ? aValue.localeCompare(bValue)
          : bValue.localeCompare(aValue);
      } else if (aValue instanceof Date && bValue instanceof Date) {
        return filterOptions.sortOrder === 'asc'
          ? aValue.getTime() - bValue.getTime()
          : bValue.getTime() - aValue.getTime();
      } else if (aValue === undefined && bValue !== undefined) {
        return filterOptions.sortOrder === 'asc' ? -1 : 1;
      } else if (aValue !== undefined && bValue === undefined) {
        return filterOptions.sortOrder === 'asc' ? 1 : -1;
      }

      return 0;
    });

    // Calculate pagination
    const total = Math.ceil(parentTasks.length / pageSize);
    const paginated = parentTasks.slice(
      (currentPage - 1) * pageSize,
      currentPage * pageSize
    );

    return {
      filteredTasks: filtered,
      paginatedTasks: paginated,
      totalPages: total,
      childTaskMap
    };
  }, [tasks, project, filterOptions, currentPage, pageSize]);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-[200px]" />
        <Skeleton className="h-[400px] w-full" />
      </div>
    );
  }

  if (error) {
    console.error("Error loading tasks:", error);
    return (
      <div className="p-4 text-center">
        <div className="text-red-500 font-medium">Error loading tasks</div>
        <div className="text-sm text-muted-foreground mt-2">
          {error instanceof Error ? error.message : 'An unexpected error occurred'}
        </div>
      </div>
    );
  }

  if (!tasks?.length) {
    console.log("No tasks found for team:", teamId);
    return (
      <div className="p-4 text-center">
        <div className="text-muted-foreground">No tasks found</div>
        <div className="text-sm text-muted-foreground mt-2">
          Create a new task to get started
        </div>
      </div>
    );
  }

  return (
    <>
      <Card className="shadow-sm flex flex-col h-full">
        <CardHeader className="p-4 pb-3 border-b">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between space-y-2 md:space-y-0">
            <div className="flex flex-col md:flex-row md:items-center space-y-2 md:space-y-0 md:space-x-4">
              <div className="relative">
                <Select
                  value={filterOptions.status}
                  onValueChange={(value) => handleFilterChange('status', value)}
                >
                  <SelectTrigger className="w-[180px] h-8">
                    <SelectValue placeholder="All Statuses" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Statuses</SelectItem>
                    <SelectItem value="Queued">Queued</SelectItem>
                    <SelectItem value="Running">Running</SelectItem>
                    <SelectItem value="Done">Done</SelectItem>
                    <SelectItem value="Failed">Failed</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="relative">
                <Select
                  value={filterOptions.agent_type || 'all'}
                  onValueChange={(value) => handleFilterChange('agent_type', value as 'all' | AgentType)}
                >
                  <SelectTrigger className="w-[180px] h-8">
                    <SelectValue placeholder="All Agent Types" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Agent Types</SelectItem>
                    <SelectItem value="Fullstack">Fullstack</SelectItem>
                    <SelectItem value="PM">PM</SelectItem>
                    <SelectItem value="SWE">SWE</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="relative">
                <Select
                  value={filterOptions.sortBy}
                  onValueChange={(value) => handleSort(value)}
                >
                  <SelectTrigger className="w-[180px] h-8">
                    <SelectValue placeholder="Sort by" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="created_at">Created Date</SelectItem>
                    <SelectItem value="due_date">Due Date</SelectItem>
                    <SelectItem value="title">Title</SelectItem>
                    <SelectItem value="status">Status</SelectItem>
                    <SelectItem value="agent_type">Agent Type</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={copyShareableUrl}>
                Share View
              </Button>
              <Button variant="outline" size="sm" onClick={handleExport}>
                <Download className="h-4 w-4 mr-2" />
                Export
              </Button>
            </div>
          </div>
        </CardHeader>

        <CardContent className="p-0 flex-grow overflow-auto">
          <div className="overflow-x-auto h-full">
            <div className="px-6 h-full">
              <Table className="h-full">
                <TableHeader>
                  <TableRow>
                    <TableHead
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => handleSort('title')}
                    >
                      <div className="flex items-center">
                        Title
                        {getSortIcon('title')}
                      </div>
                    </TableHead>
                    <TableHead
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => handleSort('status')}
                    >
                      <div className="flex items-center">
                        Status
                        {getSortIcon('status')}
                      </div>
                    </TableHead>
                    <TableHead
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => handleSort('agent_type')}
                    >
                      <div className="flex items-center">
                        Agent Type
                        {getSortIcon('agent_type')}
                      </div>
                    </TableHead>
                    <TableHead
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => handleSort('repos')}
                    >
                      <div className="flex items-center">
                        Repositories
                        {getSortIcon('repos')}
                      </div>
                    </TableHead>
                    <TableHead
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => handleSort('created_at')}
                    >
                      <div className="flex items-center">
                        Created
                        {getSortIcon('created_at')}
                      </div>
                    </TableHead>
                    <TableHead
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => handleSort('due_date')}
                    >
                      <div className="flex items-center">
                        Due Date
                        {getSortIcon('due_date')}
                      </div>
                    </TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {paginatedTasks.map((task: Task) => (
                    <Fragment key={task.id}>
                      <TableRow
                        className="cursor-pointer hover:bg-muted/50"
                        onClick={() => handleTaskClick(task)}
                      >
                        <TableCell className="font-regular text-sm">
                          <div className="flex items-center">
                            {/* Container for expansion button and title */}
                            <div className="flex items-center gap-2">
                              {((task.sibling_subtask_ids && task.sibling_subtask_ids.length > 0) || (childTaskMap.get(task.id) && childTaskMap.get(task.id)!.length > 0)) && (
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-5 w-5 p-0"
                                  onClick={(e) => toggleTaskExpansion(task.id, e)}
                                >
                                  {expandedTasks.has(task.id) ? (
                                    <ChevronDown className="h-3 w-3" />
                                  ) : (
                                    <ChevronRight className="h-3 w-3" />
                                  )}
                                </Button>
                              )}
                              {task.title}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={task.status} />
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            {task.agent_type && getAgentAvatar(task.agent_type) && (
                              <div className="w-5 h-5 flex items-center justify-center">
                                <img
                                  src={getAgentAvatar(task.agent_type)}
                                  alt={task.agent_type}
                                  className="w-4 h-4 object-contain"
                                />
                              </div>
                            )}
                            <Badge variant="outline" className="text-xs">
                              {task.agent_type || 'Unknown'}
                            </Badge>
                          </div>
                        </TableCell>
                        <TableCell className="text-xs">
                          {task.repos && task.repos.length > 0 ? (
                            <div className="flex flex-wrap gap-1">
                              {task.repos.map((repo, idx) => (
                                <Badge key={idx} variant="secondary" className="text-xs">
                                  {repo}
                                </Badge>
                              ))}
                            </div>
                          ) : (
                            <span className="text-muted-foreground">No repos</span>
                          )}
                        </TableCell>
                        <TableCell className="text-sm">{format(new Date(task.created_at), "MMM d, yyyy")}</TableCell>
                        <TableCell className="text-sm pr-6">
                          {task.due_date ? format(new Date(task.due_date), "MMM d, yyyy") : "-"}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end space-x-1">
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleViewLogsClick(task);
                              }}
                              title="View Logs"
                            >
                              <span className="text-xs">🪵</span>
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleEditClick(task);
                              }}
                            >
                              <Pencil className="h-3 w-3" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDeleteClick(task.id);
                              }}
                            >
                              <Trash2 className="h-3 w-3" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>

                      {/* Render child tasks recursively when parent is expanded */}
                      {expandedTasks.has(task.id) && renderChildTasks(task, childTaskMap, 1)}
                    </Fragment>
                  ))}
                </TableBody>
              </Table>
              {paginatedTasks.length === 0 && (
                <div className="py-20 text-center text-muted-foreground border-b border-border/30 h-full flex items-center justify-center min-h-[400px]">
                  <p>No tasks match your current filters</p>
                </div>
              )}
            </div>
          </div>
        </CardContent>

        <CardFooter className="p-3 border-t border-border">
          <div className="flex items-center justify-between w-full">
            <div className="text-xs text-muted-foreground">
              Showing {paginatedTasks.length} of {filteredTasks.length} tasks
            </div>
            <div className="flex items-center space-x-2">
              <Button
                variant="outline"
                size="sm"
                className="h-7"
                onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                disabled={currentPage === 1}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-7"
                onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                disabled={currentPage === totalPages}
              >
                Next
              </Button>
            </div>
          </div>
        </CardFooter>
      </Card>

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
        open={isEditFormOpen}
        onOpenChange={setIsEditFormOpen}
        initialData={selectedTask}
        mode="edit"
      />

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Are you sure?</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. This will permanently delete the task.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmDelete}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Task Logs Dialog */}
            <TaskLogsDialog
        open={logsDialogOpen}
        onOpenChange={setLogsDialogOpen}
        task={selectedTaskForLogs}
      />
    </>
  );
}
