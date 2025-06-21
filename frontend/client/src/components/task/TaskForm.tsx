import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormMessage,
} from "@/components/ui/form";
import {
  Dialog,
  DialogContent,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useQuery } from "@tanstack/react-query";
import { Task, TaskFormData, TeamUser } from "@/types";
import { AgentType, TaskStatus } from "@/types/task";
import { useToast } from "@/components/ui/use-toast";
import { taskApi } from "@/lib/api/task";
import { useEffect, useState } from "react";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { format } from "date-fns";
import { ChevronDown, Github } from "lucide-react";
import { cn } from "@/lib/utils";
import { Checkbox } from "@/components/ui/checkbox";
import { useTasks } from "@/contexts/TaskContext";
import { useTaskProcessingToast } from "@/components/ui/task-processing-toast";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Badge } from "@/components/ui/badge";

const customStyles = `
  /* Select item styles */
  [data-radix-select-item]:hover,
  [data-highlighted],
  [role="option"]:hover {
    background-color: rgba(94, 106, 210, 0.1) !important;
  }

  [data-radix-select-item][data-state="checked"],
  [role="option"][aria-selected="true"] {
    background-color: rgb(94, 106, 210) !important;
    color: white !important;
  }

  /* Select all option */
  .select-all-option {
    font-weight: 500;
    border-bottom: 1px solid rgba(0, 0, 0, 0.1);
    margin-bottom: 4px;
    padding-bottom: 4px;
  }

  /* Input and textarea styles */
  .linear-input {
    border: none;
    outline: none;
    box-shadow: none;
    padding: 0;
    height: auto;
    background: transparent;
    font-size: 1.125rem;
    font-weight: 500;
  }

  .linear-input:focus {
    outline: none;
    box-shadow: none;
    ring: none;
  }

  .linear-textarea {
    border: none;
    outline: none;
    box-shadow: none;
    padding: 0;
    background: transparent;
    resize: none;
    min-height: 80px;
  }

  .linear-textarea:focus {
    outline: none;
    box-shadow: none;
    ring: none;
  }

  /* Menu item styles */
  .linear-menu {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 5px 8px;
    border-radius: 4px;
    border: none;
    background: transparent;
    font-size: 14px;
    color: #888;
    height: 28px;
  }

  .linear-menu:hover {
    background-color: rgba(0, 0, 0, 0.05);
  }

  /* Status color dots */
  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 6px;
  }

  .queued-dot { background-color: #4673fa; }
  .running-dot { background-color: #f2c94c; }
  .done-dot { background-color: #27ae60; }
  .failed-dot { background-color: #eb5757; }

  /* Hide chevron icons in buttons */
  .linear-menu .select-chevron {
    opacity: 0;
    transition: opacity 0.2s;
  }

  .linear-menu:hover .select-chevron {
    opacity: 0.5;
  }

  /* Footer styling */
  .linear-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-top: 3px;
    margin-top: 3px;
    border-top: 1px solid rgba(0, 0, 0, 0.08);
  }

  /* Additional fields container */
  .additional-fields {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    padding-top: 3px;
    margin-top: 2px;
    margin-bottom: -8px;
  }

  /* Additional field style */
  .additional-field {
    flex: 1 1 calc(33.333% - 6px);
    min-width: 100px;
  }

  /* Date button styles */
  .date-button {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    border-radius: 4px;
    width: 100%;
    padding: 5px 8px;
    font-size: 14px;
    color: #888;
    height: 28px;
    border: none;
    background: transparent;
  }

  .date-button:hover {
    background-color: rgba(0, 0, 0, 0.05);
  }

  .date-button .calendar-icon {
    opacity: 0;
    margin-left: auto;
    transition: opacity 0.2s;
  }

  .date-button:hover .calendar-icon {
    opacity: 0.5;
  }

  /* Tag styles */
  .tag-badge {
    font-size: 11px;
    padding: 1px 8px;
    border-radius: 4px;
    font-weight: 500;
    display: inline-flex;
    align-items: center;
    margin-right: 4px;
    margin-bottom: 4px;
  }

  .tag-badge-bug {
    background-color: rgba(235, 87, 87, 0.12);
    color: #eb5757;
  }

  .tag-badge-feature {
    background-color: rgba(149, 128, 255, 0.12);
    color: #9580ff;
  }

  .tag-badge-improvement {
    background-color: rgba(71, 175, 255, 0.12);
    color: #47afff;
  }

  .tag-badge-custom {
    background-color: rgba(94, 106, 210, 0.12);
    color: #5e6ad2;
  }

  .tag-popover {
    width: 250px;
  }

  .tag-button {
    height: 28px;
    color: #888;
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 5px 8px;
    border-radius: 4px;
    border: none;
    background: transparent;
  }

  .tag-button:hover {
    background-color: rgba(0, 0, 0, 0.05);
  }

  .tag-button .tag-icon {
    opacity: 0.7;
  }

  .tag-container {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 2px;
    min-height: 0;
    padding: 0;
    margin-top: 1px;
  }
`;

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';



// Task form validation schema
const taskFormSchema = z.object({
  title: z.string().min(1, "Title is required"),
  description: z.string().optional(),
  status: z.enum(["Queued", "Running", "Done", "Failed"]),
  agent_type: z.enum(["Fullstack", "PM", "SWE", "Unassigned"]),
  dueDate: z.string().optional(),
  topic: z.string().optional(),
  project: z.string().optional(),
  repositories: z.array(z.string()).default([]),
  tags: z.array(z.string()).default([]),
  runOnCreate: z.boolean().default(true),
});

type TaskFormValues = z.infer<typeof taskFormSchema>;

interface TaskFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialData?: Task;
  mode?: "create" | "edit";
}

// Mock data for repositories
const mockRepositories = {
  "repo-1": { name: "Frontend App", url: "https://github.com/org/frontend" },
  "repo-2": { name: "Backend API", url: "https://github.com/org/backend" },
  "repo-3": { name: "Documentation", url: "https://github.com/org/docs" }
};

// Mock topics
const mockTopics = ["Frontend", "Backend", "Documentation", "DevOps", "Testing"];

export default function TaskForm({ open, onOpenChange, initialData, mode = "create" }: TaskFormProps) {
  const { toast } = useToast();
  const [createdTaskId, setCreatedTaskId] = useState<string | null>(null);
  const { addTask } = useTasks();
  const { showProcessingToast } = useTaskProcessingToast();
  const [tagPopoverOpen, setTagPopoverOpen] = useState(false);
  const [customTag, setCustomTag] = useState("");
  const [allReposSelected, setAllReposSelected] = useState(mode === "create");

  // Agent types
  const agentTypes = ["Fullstack", "PM", "SWE", "Unassigned"];

  // Reset loading state and initialize when form opens
  useEffect(() => {
    if (open) {
      // Initialize default state for create mode
      if (mode === "create") {
        setAllReposSelected(true);
      }
    }
  }, [open, mode]);

  // Initialize form with default values
  const form = useForm<TaskFormValues>({
    resolver: zodResolver(taskFormSchema),
    defaultValues: {
      title: initialData?.title || "",
      description: initialData?.description || "",
      status: (mode === "create") ? "Queued" : (initialData?.status as TaskFormValues['status']) || "Queued",
      agent_type: initialData?.agent_type || "Unassigned",
      dueDate: initialData?.due_date ? new Date(initialData.due_date).toISOString().split('T')[0] : "",
      topic: initialData?.topic || "",
      project: initialData?.project || "",
      repositories: initialData?.repos?.length
        ? initialData.repos
        : (mode === "create")
          ? Object.keys(mockRepositories)
          : ["none"],
      tags: initialData?.tags || [],
      runOnCreate: true,
    },
  });

  // Auto-select all repositories for new tasks
  useEffect(() => {
    // Only auto-select repositories if we're creating a new task (not editing)
    if (mode === "create") {
      // Get all repository IDs
      const allRepoIds = Object.keys(mockRepositories);
      if (allRepoIds.length > 0) {
        form.setValue("repositories", allRepoIds);
        setAllReposSelected(true);
      }
    } else if (mode === "edit" && initialData?.repos?.length) {
      // Check if all repos are selected in edit mode
      const allRepoIds = Object.keys(mockRepositories);
      const selectedRepoIds = initialData.repos;
      setAllReposSelected(
        allRepoIds.length > 0 &&
        selectedRepoIds.length === allRepoIds.length &&
        allRepoIds.every(id => selectedRepoIds.includes(id))
      );
    }
  }, [form, mode, initialData]);

  // Handle repository selection
  useEffect(() => {
    // Initialize selectedRepos when form or initialData changes
    const repos = form.getValues("repositories");
    if (repos.length === 0) {
      form.setValue("repositories", ["none"]);
    }
  }, [form, initialData]);

  const handleRepositoryToggle = (repoId: string) => {
    let newRepos: string[];

    if (repoId === "none") {
      // If "none" is selected, clear all selections
      newRepos = ["none"];
      setAllReposSelected(false);
    } else {
      // Get current repositories
      const currentRepos = form.getValues("repositories") || [];

      // Remove "none" if it exists
      const filteredRepos = currentRepos.filter(id => id !== "none");

      if (filteredRepos.includes(repoId)) {
        // Remove if already selected
        newRepos = filteredRepos.filter(id => id !== repoId);
        setAllReposSelected(false);
      } else {
        // Add if not selected
        newRepos = [...filteredRepos, repoId];

        // Check if all repos are now selected
        const allRepoIds = Object.keys(mockRepositories);
        setAllReposSelected(
          allRepoIds.length > 0 &&
          allRepoIds.every(id => newRepos.includes(id))
        );
      }

      // If no repos selected, add "none"
      if (newRepos.length === 0) {
        newRepos = ["none"];
        setAllReposSelected(false);
      }
    }

    // Update form value
    form.setValue("repositories", newRepos);
  };

  // Check if repository is selected
  const isRepositorySelected = (repoId: string) => {
    const repos = form.getValues("repositories") || [];
    return repos.includes(repoId);
  };

  const onSubmit = async (values: TaskFormValues) => {
    try {
      // Extract runOnCreate but don't include it in taskData
      const { runOnCreate, repositories, ...taskDataValues } = values;
      const taskData = {
        ...taskDataValues,
        // Filter out "none" from the repositories array
        repos: repositories?.filter(repo => repo !== "none") || [],
      };

      if (mode === "edit" && initialData) {
        // Update existing task
        const response = await taskApi.updateTask(initialData.id, taskData);
        toast({
          title: "Success",
          description: "Task updated successfully",
        });
        onOpenChange(false);
        return;
      }

      // Create task - always set status to Queued for new tasks
      const taskDataWithQueuedStatus = {
        ...taskData,
        status: "Queued" as TaskStatus
      };

      const response = await taskApi.createTask(taskDataWithQueuedStatus);
      const taskId = response.task?.id || `task-${Date.now()}`;
      setCreatedTaskId(taskId);

      // Create a local task object to add to state immediately
      const newTask: Task = {
        id: taskId,
        title: values.title,
        description: values.description || "",
        status: "Queued" as TaskStatus, // Always set to Queued for new tasks
        agent_type: values.agent_type,
        project: values.project || "",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        repos: repositories?.filter(repo => repo !== "none") || [],
        created_by: "user-1",
        team: "team-1",
      };

      // Add task to local state
      addTask(newTask);

      // Only run task with agent if runOnCreate is true
      if (runOnCreate) {
        const jobId = `task-${taskId}-${Date.now()}`;
        await taskApi.runTask({
          job_id: jobId,
          payload: { task_id: taskId }
        });

        // Show toast notification for task processing
        showProcessingToast(taskId);
      }

      toast({
        title: "Success",
        description: "Task created successfully",
      });

      // Always close the dialog after task creation
      onOpenChange(false);
      form.reset();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "Failed to save task",
        variant: "destructive",
      });
    }
  };

  // Get status dot color based on status value
  const getStatusDot = (status: string) => {
    switch (status) {
      case "Queued":
        return "queued-dot";
      case "Running":
        return "running-dot";
      case "Done":
        return "done-dot";
      case "Failed":
        return "failed-dot";
      default:
        return "queued-dot";
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <style dangerouslySetInnerHTML={{ __html: customStyles }} />
      <DialogContent className="sm:max-w-[550px] p-0 gap-0 overflow-hidden border rounded-lg shadow-lg">


        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="p-3 space-y-4">
            <FormField
              control={form.control}
              name="title"
              render={({ field }) => (
                <FormItem>
                  <FormControl>
                    <Input
                      placeholder="Issue title"
                      {...field}
                      className="linear-input focus-visible:ring-0 text-lg font-medium placeholder:text-gray-400/60"
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormControl>
                    <Textarea
                      placeholder="Add description..."
                      {...field}
                      value={field.value || ""}
                      className="linear-textarea focus-visible:ring-0 placeholder:text-gray-400/60"
                      rows={3}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="flex flex-col space-y-1">
              {mode === "edit" && (
                <FormField
                  control={form.control}
                  name="status"
                  render={({ field }) => (
                    <FormItem>
                      <FormControl>
                        <Select
                          onValueChange={field.onChange}
                          defaultValue={field.value}
                        >
                          <SelectTrigger className="linear-menu w-full justify-start">
                            <span className={`status-dot ${getStatusDot(field.value)}`}></span>
                            <SelectValue />
                            <ChevronDown className="h-3 w-3 ml-auto select-chevron" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="Queued">Queued</SelectItem>
                            <SelectItem value="Running">Running</SelectItem>
                            <SelectItem value="Done">Done</SelectItem>
                            <SelectItem value="Failed">Failed</SelectItem>
                          </SelectContent>
                        </Select>
                      </FormControl>
                    </FormItem>
                  )}
                />
              )}

              <FormField
                control={form.control}
                name="agent_type"
                render={({ field }) => (
                  <FormItem>
                    <FormControl>
                      <Select
                        onValueChange={field.onChange}
                        defaultValue={field.value}
                      >
                        <SelectTrigger className="linear-menu w-full justify-start">
                          <SelectValue placeholder="Agent Type" />
                          <ChevronDown className="h-3 w-3 ml-auto select-chevron" />
                        </SelectTrigger>
                        <SelectContent>
                          {agentTypes.map((type) => (
                            <SelectItem key={type} value={type}>
                              {type}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </FormControl>
                  </FormItem>
                )}
              />
            </div>

            <div className="additional-fields">
              <div className="additional-field">
                <FormField
                  control={form.control}
                  name="repositories"
                  render={({ field }) => (
                    <FormItem>
                      <FormControl>
                        <Popover>
                          <PopoverTrigger asChild>
                            <Button
                              variant="ghost"
                              className="linear-menu w-full justify-start"
                            >
                              <Github className="h-3.5 w-3.5 mr-0 opacity-70" />
                              <span className="text-sm">
                                {field.value?.length === 0 || (field.value?.length === 1 && field.value[0] === "none")
                                  ? (mode === "create" ? "All repositories" : "Repositories")
                                  : allReposSelected || (
                                    Object.keys(mockRepositories).length === field.value?.filter(r => r !== "none").length)
                                    ? "All repositories"
                                    : `${field.value?.filter(r => r !== "none").length} repo${field.value?.filter(r => r !== "none").length > 1 ? 's' : ''}`}
                              </span>
                              <ChevronDown className="h-3 w-3 ml-auto select-chevron" />
                            </Button>
                          </PopoverTrigger>
                          <PopoverContent className="w-[220px] p-0" align="start">
                            <Command>
                              <CommandInput placeholder="Search repositories..." />
                              <CommandList>
                                <CommandEmpty>No repositories found.</CommandEmpty>
                                <CommandGroup>
                                  <CommandItem
                                    onSelect={() => handleRepositoryToggle("none")}
                                    className="flex items-center space-x-2"
                                  >
                                    <Checkbox
                                      checked={isRepositorySelected("none")}
                                      className="h-4 w-4 data-[state=checked]:bg-[#5e6ad2] data-[state=checked]:border-[#5e6ad2]"
                                    />
                                    <span>No repository</span>
                                  </CommandItem>

                                  {Object.keys(mockRepositories).length > 0 && (
                                    <CommandItem
                                      onSelect={() => {
                                        // Get all repository IDs
                                        const allRepoIds = Object.keys(mockRepositories);
                                        const currentRepos = form.getValues("repositories") || [];

                                        // If all repos are already selected, deselect all and select "none"
                                        if (allRepoIds.every(id => currentRepos.includes(id)) && !currentRepos.includes("none")) {
                                          form.setValue("repositories", ["none"]);
                                          setAllReposSelected(false);
                                        } else {
                                          // Otherwise, select all repos
                                          form.setValue("repositories", allRepoIds);
                                          setAllReposSelected(true);
                                        }
                                      }}
                                      className="flex items-center space-x-2 select-all-option"
                                    >
                                      <Checkbox
                                        checked={
                                          Object.keys(mockRepositories).every(id =>
                                            isRepositorySelected(id) && !isRepositorySelected("none")
                                          )
                                        }
                                        className="h-4 w-4 data-[state=checked]:bg-[#5e6ad2] data-[state=checked]:border-[#5e6ad2]"
                                      />
                                      <span className="font-medium">Select all repositories</span>
                                    </CommandItem>
                                  )}

                                  {Object.entries(mockRepositories).map(([id, repo]: [string, any]) => (
                                    <CommandItem
                                      key={id}
                                      onSelect={() => handleRepositoryToggle(id)}
                                      className="flex items-center space-x-2"
                                    >
                                      <Checkbox
                                        checked={isRepositorySelected(id)}
                                        className="h-4 w-4 data-[state=checked]:bg-[#5e6ad2] data-[state=checked]:border-[#5e6ad2]"
                                      />
                                      <span>{`${repo.organization}/${repo.repository_name}`}</span>
                                    </CommandItem>
                                  ))}
                                </CommandGroup>
                              </CommandList>
                            </Command>
                          </PopoverContent>
                        </Popover>
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>


            </div>

            <div className="linear-footer">
              <FormField
                control={form.control}
                name="runOnCreate"
                render={({ field }) => (
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="run-ai"
                      checked={field.value}
                      onCheckedChange={field.onChange}
                      className="h-4 w-4 data-[state=checked]:bg-[#5e6ad2] data-[state=checked]:border-[#5e6ad2] border-gray-300"
                    />
                    <label htmlFor="run-ai" className="text-sm text-muted-foreground cursor-pointer">
                      Auto-generate subtasks with AI
                    </label>
                  </div>
                )}
              />

              <Button
                type="submit"
                className="bg-[#5e6ad2] hover:bg-[#5e6ad2]/90 text-white h-9 px-4 rounded-md"
              >
                {mode === "create" ? "Create issue" : "Update issue"}
              </Button>
            </div>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
