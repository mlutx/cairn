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
import { useEffect, useRef, useState } from "react";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { format } from "date-fns";
import { ChevronDown, Github, Server } from "lucide-react";
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
import { fetchConnectedRepos } from "@/lib/api";
import { fetchModels, ModelsResponse } from "@/lib/api/models";

// Import logo images
import openaiLogo from "@/assets/openai.png";
import anthropicLogo from "@/assets/anthropic.png";
import geminiLogo from "@/assets/gemini.png";
import fullstackIcon from "@/assets/fullstack-icon.png";
import pmIcon from "@/assets/pm-icon.png";
import sweIcon from "@/assets/swe-icon.png";

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
  model_provider: z.string().optional(),
  model_name: z.string().optional(),
});

type TaskFormValues = z.infer<typeof taskFormSchema>;

interface TaskFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialData?: Task;
  mode?: "create" | "edit";
}

// Repository interface
interface Repository {
  owner: string;
  repo: string;
  installation_id?: number;
  rules?: string[];
}

export default function TaskForm({ open, onOpenChange, initialData, mode = "create" }: TaskFormProps) {
  const { toast } = useToast();
  const { addTask, updateTask } = useTasks();
  const { showProcessingToast } = useTaskProcessingToast();
  const [createdTaskId, setCreatedTaskId] = useState<string | null>(null);
  const [tagPopoverOpen, setTagPopoverOpen] = useState(false);
  const [customTag, setCustomTag] = useState("");
  const [allReposSelected, setAllReposSelected] = useState(mode === "create");
  const [repositories, setRepositories] = useState<Record<string, Repository>>({});
  const [isLoadingRepos, setIsLoadingRepos] = useState(false);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [modelProviders, setModelProviders] = useState<ModelsResponse["providers"]>({});
  const [selectedModels, setSelectedModels] = useState<string[]>([]);
  const titleInputRef = useRef<HTMLInputElement>(null);

  // Define agent types
  const agentTypes = ["Fullstack", "PM", "SWE"];

  // Helper function to get the logo for a model provider
  const getModelProviderLogo = (provider: string) => {
    switch (provider.toLowerCase()) {
      case "openai":
        return openaiLogo;
      case "anthropic":
        return anthropicLogo;
      case "gemini":
        return geminiLogo;
      default:
        return null;
    }
  };

  const getAgentTypeIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case "fullstack":
        return fullstackIcon;
      case "pm":
        return pmIcon;
      case "swe":
        return sweIcon;
      default:
        return null;
    }
  };

  // Get saved model provider and model from localStorage
  const savedModelProvider = localStorage.getItem('lastModelProvider');
  const savedModelName = localStorage.getItem('lastModelName');

  // Form definition
  const form = useForm<TaskFormValues>({
    resolver: zodResolver(taskFormSchema),
    defaultValues: {
      title: initialData?.title || "",
      description: initialData?.description || "",
      status: initialData?.status || "Queued",
      agent_type: initialData?.agent_type || "Fullstack",
      repositories: initialData?.repos || [],
      model_provider: initialData?.model_provider || savedModelProvider || "",
      model_name: initialData?.model_name || savedModelName || "",
      tags: initialData?.tags || [],
      due_date: initialData?.due_date ? new Date(initialData.due_date) : undefined,
      runOnCreate: true,
    },
  });

  // Watch agent type to control repository selection behavior
  const selectedModelProvider = form.watch("model_provider");
  const isFullstack = form.watch("agent_type") === "Fullstack";

  // Fetch repositories from the backend
  const fetchRepos = async () => {
    setIsLoadingRepos(true);
    try {
      const data = await fetchConnectedRepos();
      // Convert array of repos to a record with ids
      const reposRecord: Record<string, Repository> = {};
      data.repos.forEach((repo: Repository, index: number) => {
        const id = `repo-${index}`;
        reposRecord[id] = repo;
      });
      setRepositories(reposRecord);
    } catch (error) {
      console.error("Error fetching repositories:", error);
      toast({
        title: "Error",
        description: "Failed to fetch repositories",
        variant: "destructive",
      });
    } finally {
      setIsLoadingRepos(false);
    }
  };

  // Fetch model providers and models
  const fetchModelProviders = async () => {
    setIsLoadingModels(true);
    try {
      const data = await fetchModels();
      setModelProviders(data.providers);
    } catch (error) {
      console.error("Error fetching model providers:", error);
      toast({
        title: "Error",
        description: "Failed to fetch model providers",
        variant: "destructive",
      });
    } finally {
      setIsLoadingModels(false);
    }
  };

  // Reset loading state and initialize when form opens
  useEffect(() => {
    if (open) {
      // Initialize default state for create mode
      if (mode === "create") {
        setAllReposSelected(true);
      }
      // Fetch repositories when the form opens
      fetchRepos();
      // Fetch model providers when the form opens
      fetchModelProviders();
    }
  }, [open, mode]);

  // Update available models when model provider changes
  useEffect(() => {
    if (selectedModelProvider && modelProviders[selectedModelProvider]) {
      setSelectedModels(modelProviders[selectedModelProvider].models || []);
    } else {
      setSelectedModels([]);
    }
  }, [selectedModelProvider, modelProviders]);

  // Save selected model provider and model to localStorage when they change
  useEffect(() => {
    const currentProvider = form.getValues("model_provider");
    const currentModel = form.getValues("model_name");

    if (currentProvider) {
      localStorage.setItem('lastModelProvider', currentProvider);
    }

    if (currentModel) {
      localStorage.setItem('lastModelName', currentModel);
    }
  }, [form.watch("model_provider"), form.watch("model_name")]);

  // Auto-select all repositories when they are loaded
  useEffect(() => {
    // Only auto-select repositories if we're creating a new task (not editing)
    if (mode === "create" && Object.keys(repositories).length > 0) {
      if (isFullstack) {
        // For Fullstack, select all repositories
        const allRepoIds = Object.keys(repositories);
        if (allRepoIds.length > 0) {
          form.setValue("repositories", allRepoIds);
          setAllReposSelected(true);
        }
      } else {
        // For non-Fullstack, select only the first repository if available
        const repoKeys = Object.keys(repositories);
        if (repoKeys.length > 0) {
          form.setValue("repositories", [repoKeys[0]]);
          setAllReposSelected(false);
        } else {
          form.setValue("repositories", ["none"]);
        }
      }
    } else if (mode === "edit" && initialData?.repos?.length && Object.keys(repositories).length > 0) {
      // Check if all repos are selected in edit mode
      const allRepoIds = Object.keys(repositories);
      const selectedRepoIds = initialData.repos;
      setAllReposSelected(
        allRepoIds.length > 0 &&
        selectedRepoIds.length === allRepoIds.length &&
        allRepoIds.every(id => selectedRepoIds.includes(id))
      );
    }
  }, [form, mode, initialData, repositories, isFullstack]);

  // Update repositories when agent type changes
  useEffect(() => {
    if (!isFullstack) {
      // For non-Fullstack, limit to a single repository
      const currentRepos = form.getValues("repositories") || [];
      if (currentRepos.length > 1) {
        // Keep only the first selected repository
        form.setValue("repositories", [currentRepos[0]]);
        setAllReposSelected(false);
      }
    }
  }, [isFullstack, form]);

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
        if (!isFullstack) {
          // For non-Fullstack, replace the current selection with the new one
          newRepos = [repoId];
        } else {
          // For Fullstack, add to the current selection
          newRepos = [...filteredRepos, repoId];

          // Check if all repos are now selected
          const allRepoIds = Object.keys(repositories);
          setAllReposSelected(
            allRepoIds.length > 0 &&
            allRepoIds.every(id => newRepos.includes(id))
          );
        }
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
      const { runOnCreate, repositories, model_provider, model_name, ...taskDataValues } = values;
      const taskData = {
        ...taskDataValues,
        // Filter out "none" from the repositories array
        repos: repositories?.filter(repo => repo !== "none") || [],
        // Include model provider and model name if they exist
        model_provider,
        model_name,
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
        model_provider: values.model_provider,
        model_name: values.model_name,
      };

      // Add task to local state
      addTask(newTask);

      toast({
        title: "Success",
        description: "Task created successfully",
      });

      // Check if "Add more tasks" is selected
      const addMoreTasks = runOnCreate;

      if (addMoreTasks && mode === "create") {
        // Just reset the form fields but keep the dialog open
        form.reset({
          ...form.getValues(),
          title: "",
          description: "",
          runOnCreate: true, // Keep the "Add more tasks" option selected
          // Keep the model provider and model name
          model_provider: values.model_provider,
          model_name: values.model_name,
        });

        toast({
          title: "Task added",
          description: "Ready to create another task",
        });

        // Focus on the title input after a short delay to ensure the form is reset
        setTimeout(() => {
          titleInputRef.current?.focus();
        }, 50);
      } else {
        // Close the dialog if not adding more tasks
        onOpenChange(false);
        form.reset();
      }
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "Failed to save task",
        variant: "destructive",
      });
    }
  };

  // Add keyboard shortcuts for the form
  useEffect(() => {
    if (open) {
      const handleKeyDown = (e: KeyboardEvent) => {
        // Cmd+Enter to submit form
        if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
          e.preventDefault();
          form.handleSubmit(onSubmit)();
        }

        // Cmd+L to toggle "Add more tasks" checkbox
        if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'l') {
          e.preventDefault();
          const currentValue = form.getValues().runOnCreate;
          form.setValue('runOnCreate', !currentValue);
        }
      };

      document.addEventListener('keydown', handleKeyDown);
      return () => {
        document.removeEventListener('keydown', handleKeyDown);
      };
    }
  }, [open, form, onSubmit]);

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

  // Format repository display name
  const getRepoDisplayName = (id: string) => {
    const repo = repositories[id];
    if (repo) {
      return `${repo.owner}/${repo.repo}`;
    }
    return "Unknown Repository";
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
                      ref={titleInputRef}
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
                          {field.value && getAgentTypeIcon(field.value) ? (
                            <>
                              <img
                                src={getAgentTypeIcon(field.value)}
                                alt={`${field.value} icon`}
                                className="h-3.5 w-3.5 mr-1 object-contain"
                              />
                              <span>{field.value}</span>
                            </>
                          ) : (
                            <SelectValue placeholder="Agent Type" />
                          )}
                          <ChevronDown className="h-3 w-3 ml-auto select-chevron" />
                        </SelectTrigger>
                        <SelectContent>
                          {agentTypes.map((type) => (
                            <SelectItem key={type} value={type}>
                              {getAgentTypeIcon(type) ? (
                                <div className="flex items-center">
                                  <img
                                    src={getAgentTypeIcon(type)}
                                    alt={`${type} icon`}
                                    className="h-4 w-4 mr-2 object-contain"
                                  />
                                  {type}
                                </div>
                              ) : (
                                type
                              )}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </FormControl>
                  </FormItem>
                )}
              />

              {/* Model Provider and Model Selection - Side by side */}
              <div className="flex gap-2">
                {/* Model Provider Selection */}
                <FormField
                  control={form.control}
                  name="model_provider"
                  render={({ field }) => (
                    <FormItem className="flex-1">
                      <FormControl>
                        <Select
                          onValueChange={(value) => {
                            field.onChange(value);
                            // Reset model name when provider changes
                            form.setValue("model_name", "");
                          }}
                          value={field.value || ""}
                        >
                          <SelectTrigger className="linear-menu w-full justify-start">
                            {field.value && getModelProviderLogo(field.value) ? (
                              <>
                                <img
                                  src={getModelProviderLogo(field.value)}
                                  alt={`${field.value} logo`}
                                  className="h-3.5 w-3.5 mr-1 object-contain"
                                />
                                <span>{field.value}</span>
                              </>
                            ) : (
                              <>
                                <Server className="h-3.5 w-3.5 mr-1 opacity-70" />
                                <SelectValue placeholder="Select Model Provider" />
                              </>
                            )}
                            <ChevronDown className="h-3 w-3 ml-auto select-chevron" />
                          </SelectTrigger>
                          <SelectContent>
                            {isLoadingModels ? (
                              <SelectItem value="loading" disabled>
                                Loading providers...
                              </SelectItem>
                            ) : Object.keys(modelProviders).length === 0 ? (
                              <SelectItem value="none" disabled>
                                No providers available
                              </SelectItem>
                            ) : (
                              Object.keys(modelProviders).map((provider) => (
                                <SelectItem key={provider} value={provider}>
                                  {getModelProviderLogo(provider) ? (
                                    <div className="flex items-center">
                                      <img
                                        src={getModelProviderLogo(provider)}
                                        alt={`${provider} logo`}
                                        className="h-4 w-4 mr-2 object-contain"
                                      />
                                      {provider}
                                    </div>
                                  ) : (
                                    provider
                                  )}
                                </SelectItem>
                              ))
                            )}
                          </SelectContent>
                        </Select>
                      </FormControl>
                    </FormItem>
                  )}
                />

                {/* Model Selection */}
                <FormField
                  control={form.control}
                  name="model_name"
                  render={({ field }) => (
                    <FormItem className="flex-1">
                      <FormControl>
                        <Select
                          onValueChange={field.onChange}
                          value={field.value || ""}
                          disabled={!selectedModelProvider}
                        >
                          <SelectTrigger className="linear-menu w-full justify-start">
                            <SelectValue placeholder="Select Model" />
                            <ChevronDown className="h-3 w-3 ml-auto select-chevron" />
                          </SelectTrigger>
                          <SelectContent>
                            {!selectedModelProvider ? (
                              <SelectItem value="none" disabled>
                                Select a provider first
                              </SelectItem>
                            ) : selectedModels.length === 0 ? (
                              <SelectItem value="none" disabled>
                                No models available
                              </SelectItem>
                            ) : (
                              selectedModels.map((model) => (
                                <SelectItem key={model} value={model}>
                                  {model}
                                </SelectItem>
                              ))
                            )}
                          </SelectContent>
                        </Select>
                      </FormControl>
                    </FormItem>
                  )}
                />
              </div>
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
                                {isLoadingRepos ? "Loading repositories..." :
                                  field.value?.length === 0 || (field.value?.length === 1 && field.value[0] === "none")
                                  ? (mode === "create" ? "All repositories" : "Repositories")
                                  : field.value?.filter(r => r !== "none").length === 1
                                    ? getRepoDisplayName(field.value?.filter(r => r !== "none")[0])
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

                                  {form.getValues("agent_type") === "Fullstack" && Object.keys(repositories).length > 0 && (
                                    <CommandItem
                                      onSelect={() => {
                                        // Get all repository IDs
                                        const allRepoIds = Object.keys(repositories);
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
                                          Object.keys(repositories).every(id =>
                                            isRepositorySelected(id) && !isRepositorySelected("none")
                                          )
                                        }
                                        className="h-4 w-4 data-[state=checked]:bg-[#5e6ad2] data-[state=checked]:border-[#5e6ad2]"
                                      />
                                      <span className="font-medium">Select all repositories</span>
                                    </CommandItem>
                                  )}

                                  {Object.entries(repositories).map(([id, repo]) => (
                                    <CommandItem
                                      key={id}
                                      onSelect={() => handleRepositoryToggle(id)}
                                      className="flex items-center space-x-2"
                                    >
                                      <Checkbox
                                        checked={isRepositorySelected(id)}
                                        className="h-4 w-4 data-[state=checked]:bg-[#5e6ad2] data-[state=checked]:border-[#5e6ad2]"
                                      />
                                      <span>{`${repo.owner}/${repo.repo}`}</span>
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
                      Add more tasks <span className="ml-1 opacity-70 text-xs">⌘+L</span>
                    </label>
                  </div>
                )}
              />

              <Button
                type="submit"
                className="bg-[#5e6ad2] hover:bg-[#5e6ad2]/90 text-white h-9 px-4 rounded-md"
              >
                {mode === "create" ? (
                  <>
                    Create issue <span className="ml-1 opacity-70 text-xs">⌘+↵</span>
                  </>
                ) : "Update issue"}
              </Button>
            </div>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
