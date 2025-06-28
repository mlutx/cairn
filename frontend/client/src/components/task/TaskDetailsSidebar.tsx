import { useState, useEffect, useRef } from "react";
import { format } from "date-fns";
import { ChevronRight, MessageSquare, Plus, CheckSquare, Bot, Play, User, ExternalLink, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { StatusBadge } from "@/components/ui/status-badge";
import { Textarea } from "@/components/ui/textarea";
import { Task, TeamUser } from "@/types";
import { getInitials } from "@/lib/utils/task-utils";
import { useToast } from "@/hooks/use-toast";
import { taskApi } from "@/lib/api/task";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAuth } from "@/contexts/AuthContext";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { useMutation } from "@tanstack/react-query";
import {
  SidebarProvider,
  SidebarHeader,
  SidebarContent,
} from "@/components/ui/sidebar";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { TaskStatus } from "@/types/task";
import sweAvatar from "@/assets/swe-icon.png";
import pmAvatar from "@/assets/pm-icon.png";
import fullstackAvatar from "@/assets/fullstack-icon.png";

interface TaskComment {
  id: string;
  content: string;
  author: string;
  created_at: string;
}

interface Subtask {
  id: string;
  task: string;
  status: string;
  assignee?: string;
  llm_description?: string;
  description?: string;
  assigned_to_agent?: boolean;
  tags?: string[];
  link?: string;
  repos?: string[];
  agent_output?: {
    pr_url?: string;
  };
}

interface SubtaskFormValues {
  status: string;
  assignee: string;
  description: string;
  assigned_to_agent: boolean;
  tags: string[];
  link?: string;
  repos?: string[];
}

interface SubtaskApiParams {
  subtask_ids: string[];
  filters?: Array<{
    field: string;
    operator: string;
    value: string | number | boolean;
  }>;
}

interface TaskDetailsSidebarProps {
  task: Task;
  isOpen: boolean;
  onClose: () => void;
}

export default function TaskDetailsSidebar({ task, isOpen, onClose }: TaskDetailsSidebarProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [newComment, setNewComment] = useState("");
  const [newSubtask, setNewSubtask] = useState("");
  const [showSubtaskForm, setShowSubtaskForm] = useState(false);
  const [tagInput, setTagInput] = useState('');
  const [subtaskForm, setSubtaskForm] = useState<SubtaskFormValues>({
    status: "Todo",
    assignee: "",
    description: "",
    assigned_to_agent: false,
    tags: [],
    link: "",
    repos: []
  });
  const sidebarRef = useRef<HTMLDivElement>(null);
  const [comments, setComments] = useState<TaskComment[]>([
    {
      id: "1",
      content: "Started working on the task",
      author: task.agent_type || "System",
      created_at: new Date().toISOString(),
    },
  ]);
  const [runningSubtasks, setRunningSubtasks] = useState<Set<string>>(new Set());

  // Handle click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (isOpen && sidebarRef.current && !sidebarRef.current.contains(event.target as Node)) {
        onClose();
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen, onClose]);

  // Fetch subtasks for the task
  const { data: subtasksData, isLoading: isLoadingSubtasks } = useQuery({
    queryKey: ["subtasks", task.id],
    queryFn: async () => {
      const params: SubtaskApiParams = {
        subtask_ids: [],
        filters: [
          {
            field: "task",
            operator: "eq",
            value: task.id
          }
        ]
      };

      const response = await taskApi.getSubtasks(params);
      return response;
    },
    enabled: !!task.id,
  });

  // Poll for running subtasks
  const { data: runningSubtasksData } = useQuery({
    queryKey: ["running-subtasks", Array.from(runningSubtasks)],
    queryFn: async () => {
      if (runningSubtasks.size === 0) return { subtasks: [] };
      const response = await taskApi.getSubtasks({
        subtask_ids: Array.from(runningSubtasks),
      });
      return response;
    },
    refetchInterval: 5000,
    enabled: runningSubtasks.size > 0,
  });

  useEffect(() => {
    if (runningSubtasksData?.subtasks) {
      // Check if any subtasks are done
      runningSubtasksData.subtasks.forEach((subtask: Subtask) => {
        if (subtask.status === 'Agent Done: Review') {
          console.log('Subtask completed:', subtask.id);
          console.log('PR URL:', subtask.agent_output?.pr_url);
          setRunningSubtasks((prev) => {
            const newSet = new Set(prev);
            newSet.delete(subtask.id);
            return newSet;
          });
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

  const addSubtaskMutation = useMutation({
    mutationFn: (description: string) => taskApi.addSubtask({
      task: task.id,
      status: "Todo",
      description,
      assignee: user?.id || "",
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subtasks", task.id] });
      setNewSubtask("");
      toast({
        title: "Success",
        description: "Subtask added successfully",
      });
    },
    onError: () => {
      toast({
        title: "Error",
        description: "Failed to add subtask",
        variant: "destructive",
      });
    },
  });

  const { user } = useAuth();
  const teamId = user?.team_id;

  // Fetch team members for assignee names
  const { data: teamMembers = [] } = useQuery<TeamUser[]>({
    queryKey: ["team-members", teamId],
    queryFn: () => taskApi.getTeamUsers(teamId!),
    enabled: !!teamId,
  });

  // Get assignee details with more robust matching
  const assignee = teamMembers.find((member: TeamUser) => {
    // Since the Task type doesn't have assignees property, we'll skip this check
    return false;
  });

  // Get assignee name with fallback
  const assigneeName = assignee
    ? `${assignee.first_name} ${assignee.last_name}`
    : task.agent_type || "Unassigned";
  const assigneeInitials = assignee
    ? getInitials(`${assignee.first_name} ${assignee.last_name}`)
    : task.agent_type
      ? task.agent_type.substring(0, 1)
      : "U";

  // Get the appropriate avatar based on agent type
  const getAgentAvatar = () => {
    switch (task.agent_type) {
      case "SWE":
        return sweAvatar;
      case "PM":
        return pmAvatar;
      case "Fullstack":
        return fullstackAvatar;
      default:
        return null;
    }
  };

  const agentAvatar = getAgentAvatar();

  // Initialize the form after user is available
  useEffect(() => {
    if (user) {
      setSubtaskForm({
        status: "Todo",
        assignee: user.id || "",
        description: "",
        assigned_to_agent: false,
        tags: [],
        link: "",
        repos: task.repos || []
      });
    }
  }, [user, task]);

  const handleAddComment = () => {
    if (!newComment.trim()) return;

    const comment: TaskComment = {
      id: Date.now().toString(),
      content: newComment,
      author: user?.id || "System",
      created_at: new Date().toISOString(),
    };

    setComments([comment, ...comments]);
    setNewComment("");
  };

  const handleStatusChange = async (newStatus: TaskStatus) => {
    try {
      await taskApi.updateTask(task.id, { ...task, status: newStatus });
      toast({
        title: "Status updated",
        description: `Task status has been updated to ${newStatus}.`,
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to update task status. Please try again.",
        variant: "destructive",
      });
    }
  };

  const handleAddSubtask = () => {
    if (!newSubtask.trim()) return;
    addSubtaskMutation.mutate(newSubtask.trim());
  };

  const handleAddTag = () => {
    if (!tagInput.trim()) return;

    setSubtaskForm(prev => ({
      ...prev,
      tags: [...prev.tags, tagInput.trim()]
    }));

    setTagInput('');
  };

  const handleRemoveTag = (tagToRemove: string) => {
    setSubtaskForm(prev => ({
      ...prev,
      tags: prev.tags.filter(tag => tag !== tagToRemove)
    }));
  };

  const createSubtaskMutation = useMutation({
    mutationFn: (data: Partial<Subtask>) => {
      return taskApi.addSubtask({
        task: task.id,
        status: data.status || "Todo",
        assignee: data.assignee || user?.id || "",
        description: data.description,
        assigned_to_agent: !!data.assigned_to_agent,
        tags: data.tags,
        link: data.link,
        repos: data.repos || task.repos
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subtasks", task.id] });
      setShowSubtaskForm(false);
      // Reset form
      setSubtaskForm({
        status: "Todo",
        assignee: user?.id || "",
        description: "",
        assigned_to_agent: false,
        tags: [],
        link: "",
        repos: task.repos || []
      });
      toast({
        title: "Success",
        description: "Subtask created successfully",
      });
    },
    onError: (error: any) => {
      toast({
        title: "Error",
        description: error.message || "Failed to create subtask",
        variant: "destructive",
      });
    },
  });

  const handleSubtaskFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const subtaskData = {
      ...subtaskForm,
      task: task.id
    };

    createSubtaskMutation.mutate(subtaskData);
  };

  return (
    <SidebarProvider
      defaultOpen={isOpen}
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      style={{
        "--sidebar-width": "380px",
        "--sidebar-width-icon": "0px"
      } as React.CSSProperties}
    >
      <div
        ref={sidebarRef}
        className={`fixed right-0 top-0 h-screen w-[380px] bg-background border-l border-border shadow-xl z-50 transition-all duration-300 ease-in-out ${
          isOpen ? "translate-x-0 opacity-100" : "translate-x-full opacity-0"
        }`}
      >
        <div className="h-full flex flex-col">
          {/* <SidebarHeader className="px-5 py-4 border-b border-border bg-background sticky top-0 z-10 flex items-center justify-between">
            {/* <div className="flex items-center">
              <h3 className="text-xl font-medium">{task.title}</h3>
            </div> */}
          {/* </SidebarHeader> */}

          <SidebarContent className="flex-1 overflow-y-auto hide-scrollbar">
            <div className="p-5 space-y-6">
              {/* Task Info */}
              <div className="space-y-5">

                <Button
                  variant="ghost"
                  size="icon"
                  onClick={onClose}
                  className="hover:bg-muted rounded-full h-8 w-8 flex justify-right"
                  aria-label="Close sidebar"
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
                <div className="flex items-start justify-between">
                  <h2 className="text-xl font-semibold">{task.title}</h2>
                </div>

                <div className="flex items-center space-x-3">
                  <Avatar className="h-9 w-9">
                    {agentAvatar ? (
                      <div className="w-full h-full flex items-center justify-center">
                        <AvatarImage
                          src={agentAvatar}
                          className="w-6 h-6 object-contain"
                        />
                      </div>
                    ) : (
                      <AvatarImage src={assignee?.avatar} />
                    )}
                    <AvatarFallback>{assigneeInitials}</AvatarFallback>
                  </Avatar>
                  <div>
                    <p className="text-sm font-medium">{assigneeName}</p>
                    <p className="text-xs text-muted-foreground">Assignee</p>
                  </div>
                </div>

                <div className="flex items-center gap-2 flex-wrap">
                  <StatusBadge status={task.status} />
                  <Select defaultValue={task.status} onValueChange={handleStatusChange}>
                    <SelectTrigger className="w-[140px] h-8">
                      <SelectValue placeholder="Change status" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Queued">Queued</SelectItem>
                      <SelectItem value="Running">Running</SelectItem>
                      <SelectItem value="Done">Done</SelectItem>
                      <SelectItem value="Failed">Failed</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-muted-foreground">Created</p>
                    <p>{format(new Date(task.created_at), "MMM d, yyyy")}</p>
                  </div>
                  {task.due_date && (
                    <div>
                      <p className="text-muted-foreground">Due Date</p>
                      <p>{format(new Date(task.due_date), "MMM d, yyyy")}</p>
                    </div>
                  )}
                </div>
                {task.description && (
                  <div>
                    <p className="text-muted-foreground mb-1">Description</p>
                    <p className="text-sm">{task.description}</p>
                  </div>
                )}
              </div>

              {/* Subtasks Section */}
              <div className="space-y-4 pt-2 border-t border-border">
                <div className="flex items-center justify-between pt-4">
                  <h3 className="text-base font-semibold flex items-center text-muted-foreground">
                    <CheckSquare className="h-4 w-4 mr-2" />
                    Subtasks
                  </h3>
                  <Dialog open={showSubtaskForm} onOpenChange={setShowSubtaskForm}>
                    <DialogTrigger asChild>
                      <Button variant="outline" size="sm">
                        <Plus className="h-4 w-4 mr-1" /> Advanced
                      </Button>
                    </DialogTrigger>
                    <DialogContent className="sm:max-w-[500px]">
                      <DialogHeader>
                        <DialogTitle>Create subtask</DialogTitle>
                        <DialogDescription>
                          Add a new subtask to this task
                        </DialogDescription>
                      </DialogHeader>
                      <form onSubmit={handleSubtaskFormSubmit}>
                        <div className="grid gap-4 py-4">
                          <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                              <Label htmlFor="status">Status</Label>
                              <Select
                                value={subtaskForm.status}
                                onValueChange={(value) => setSubtaskForm(prev => ({ ...prev, status: value }))}
                              >
                                <SelectTrigger id="status">
                                  <SelectValue placeholder="Select status" />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="Queued">Queued</SelectItem>
                                  <SelectItem value="Running">Running</SelectItem>
                                  <SelectItem value="Done">Done</SelectItem>
                                  <SelectItem value="Failed">Failed</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                          </div>

                          <div className="space-y-2">
                            <Label htmlFor="assignee">Assignee</Label>
                            <Select
                              value={subtaskForm.assignee}
                              onValueChange={(value) => setSubtaskForm(prev => ({ ...prev, assignee: value }))}
                            >
                              <SelectTrigger id="assignee">
                                <SelectValue placeholder="Select assignee" />
                              </SelectTrigger>
                              <SelectContent>
                                {teamMembers.map((member: TeamUser) => (
                                  <SelectItem key={member.uid} value={member.uid}>
                                    {member.first_name} {member.last_name}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>

                          <div className="space-y-2">
                            <Label htmlFor="description">Description</Label>
                            <Textarea
                              id="description"
                              placeholder="Provide a detailed description for this subtask"
                              value={subtaskForm.description}
                              onChange={(e) => setSubtaskForm(prev => ({ ...prev, description: e.target.value }))}
                              className="min-h-[100px]"
                            />
                          </div>

                          <div className="space-y-2">
                            <Label htmlFor="link">External Link</Label>
                            <Input
                              id="link"
                              placeholder="Add an external link"
                              value={subtaskForm.link || ''}
                              onChange={(e) => setSubtaskForm(prev => ({ ...prev, link: e.target.value }))}
                            />
                          </div>

                          <div className="space-y-2">
                            <Label>Tags</Label>
                            <div className="flex flex-wrap gap-2 mb-2">
                              {subtaskForm.tags.map(tag => (
                                <Badge key={tag} className="flex items-center gap-1 px-3">
                                  {tag}
                                  <button
                                    type="button"
                                    onClick={() => handleRemoveTag(tag)}
                                    className="hover:bg-muted rounded-full p-0.5"
                                  >
                                    <X className="h-3 w-3" />
                                  </button>
                                </Badge>
                              ))}
                            </div>
                            <div className="flex gap-2">
                              <Input
                                placeholder="Add a tag"
                                value={tagInput}
                                onChange={(e) => setTagInput(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") {
                                    e.preventDefault();
                                    handleAddTag();
                                  }
                                }}
                              />
                              <Button
                                type="button"
                                onClick={handleAddTag}
                                variant="outline"
                                disabled={!tagInput.trim()}
                              >
                                <Plus className="h-4 w-4" />
                              </Button>
                            </div>
                          </div>

                          <div className="flex items-center space-x-2">
                            <Switch
                              id="ai-agent"
                              checked={subtaskForm.assigned_to_agent}
                              onCheckedChange={(checked) => setSubtaskForm(prev => ({ ...prev, assigned_to_agent: checked }))}
                            />
                            <Label htmlFor="ai-agent" className="flex items-center gap-2">
                              <Bot className="h-4 w-4" />
                              Assign to AI Agent
                            </Label>
                          </div>
                        </div>
                        <DialogFooter>
                          <Button variant="outline" type="button" onClick={() => setShowSubtaskForm(false)}>
                            Cancel
                          </Button>
                          <Button
                            type="submit"
                            disabled={createSubtaskMutation.isPending}
                          >
                            {createSubtaskMutation.isPending ? 'Creating...' : 'Create Subtask'}
                          </Button>
                        </DialogFooter>
                      </form>
                    </DialogContent>
                  </Dialog>
                </div>

                {/* Quick Add Subtask Form */}
                <div className="flex gap-2">
                  <Input
                    placeholder="Add a subtask description..."
                    value={newSubtask}
                    onChange={(e) => setNewSubtask(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && newSubtask.trim()) {
                        handleAddSubtask();
                      }
                    }}
                    className="h-9 bg-muted/30"
                  />
                  <Button
                    onClick={handleAddSubtask}
                    disabled={!newSubtask.trim() || addSubtaskMutation.isPending}
                    size="sm"
                    className="bg-muted/50 text-foreground hover:bg-muted"
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>

                {isLoadingSubtasks ? (
                  <div className="space-y-2">
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-full" />
                  </div>
                ) : subtasksData?.subtasks && subtasksData.subtasks.length > 0 ? (
                  <div className="space-y-2">
                    {subtasksData.subtasks.map((subtask: Subtask) => {
                      const isRunning = runningSubtasks.has(subtask.id);
                      const runningSubtaskData = runningSubtasksData?.subtasks.find((s: Subtask) => s.id === subtask.id);

                      return (
                        <div key={subtask.id} className="p-4 border rounded-lg">
                          <div className="flex items-start justify-between">
                            <div className="space-y-1">
                              {subtask.llm_description ? (
                                <h3 className="font-medium">{subtask.llm_description}</h3>
                              ) : subtask.description ? (
                                <h3 className="font-medium">{subtask.description}</h3>
                              ) : (
                                <h3 className="font-medium text-muted-foreground">Subtask</h3>
                              )}
                              {subtask.llm_description && subtask.description && (
                                <p className="text-sm text-muted-foreground">{subtask.description}</p>
                              )}
                              {isRunning && (
                                <div className="mt-2">
                                  <p className="text-sm text-muted-foreground">
                                    Status: {runningSubtaskData?.status || 'Processing...'}
                                  </p>
                                </div>
                              )}
                              {runningSubtaskData?.agent_output?.pr_url && (
                                <div className="mt-2">
                                  <a
                                    href={runningSubtaskData.agent_output.pr_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-sm text-primary hover:underline flex items-center gap-1"
                                  >
                                    View Pull Request <ExternalLink className="h-3 w-3" />
                                  </a>
                                </div>
                              )}
                            </div>
                            <div className="flex items-center gap-2">
                              {subtask.assigned_to_agent ? (
                                <>
                                  <Bot className="h-5 w-5 text-primary" />
                                  {runningSubtaskData?.agent_output?.pr_url ? (
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      onClick={() => window.open(runningSubtaskData.agent_output?.pr_url || '', '_blank')}
                                    >
                                      <ExternalLink className="h-4 w-4 mr-2" />
                                      View PR
                                    </Button>
                                  ) : (
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      onClick={() => handleRunSubtask(subtask.id)}
                                      disabled={isRunning}
                                    >
                                      <Play className="h-4 w-4 mr-2" />
                                      {isRunning ? 'Running...' : 'Run'}
                                    </Button>
                                  )}
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
                ) : (
                  <p className="text-sm text-muted-foreground">No subtasks found</p>
                )}
              </div>

              {/* Comments Section */}
              <div className="space-y-4 pt-2 border-t border-border">
                <div className="flex items-center justify-between pt-4">
                  <h3 className="text-base font-semibold flex items-center text-muted-foreground">
                    <MessageSquare className="h-4 w-4 mr-2" />
                    Comments
                  </h3>
                </div>

                {/* Add Comment */}
                <div className="space-y-2">
                  <Textarea
                    placeholder="Add a comment..."
                    value={newComment}
                    onChange={(e) => setNewComment(e.target.value)}
                    className="min-h-[100px] resize-none bg-muted/30"
                  />
                  <Button
                    onClick={handleAddComment}
                    className="w-full bg-primary/90 hover:bg-primary"
                    disabled={!newComment.trim()}
                  >
                    Add Comment
                  </Button>
                </div>

                {/* Comments List */}
                <div className="space-y-4 pt-2">
                  {comments.map((comment) => (
                    <Card key={comment.id} className="shadow-none border-none bg-muted/20">
                      <CardHeader className="p-3 pb-1">
                        <div className="flex items-center">
                          <div className="flex items-center space-x-2">
                            <Avatar className="h-6 w-6">
                              <AvatarImage src={`https://api.dicebear.com/7.x/initials/svg?seed=${comment.author}`} />
                              <AvatarFallback>{getInitials(comment.author)}</AvatarFallback>
                            </Avatar>
                            <div>
                              <p className="text-sm font-medium">{comment.author}</p>
                              <p className="text-xs text-muted-foreground">
                                {format(new Date(comment.created_at), "MMM d, yyyy 'at' h:mm a")}
                              </p>
                            </div>
                          </div>
                        </div>
                      </CardHeader>
                      <CardContent className="p-3 pt-0">
                        <p className="text-sm">{comment.content}</p>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            </div>
          </SidebarContent>
        </div>
      </div>
    </SidebarProvider>
  );
}
