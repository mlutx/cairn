import { Task, TeamUser } from "@/types";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { format } from "date-fns";
import { getInitials } from "@/lib/utils/task-utils";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { GridLoader } from "react-spinners";
import React from "react";

import sweAvatar from "@/assets/swe-icon.png";
import pmAvatar from "@/assets/pm-icon.png";
import fullstackAvatar from "@/assets/fullstack-icon.png";
import { GitBranch, Trash2 } from "lucide-react";

interface TaskCardProps {
  task: Task;
  onClick?: () => void;
  className?: string;
  expansionControl?: React.ReactNode;
  onViewLogs?: (task: Task) => void; // Add callback for logs
  onDeleteTask?: (task: Task) => void; // Add callback for deletion
  onRunAllChildTasks?: (task: Task) => void; // Add callback for running all child tasks
  isCreatingAllSubtasks?: boolean; // Add loading state for run all
  hasVirtualSubtasks?: boolean; // Whether there are virtual subtasks that can be created
}

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

function TaskCard({ task, onClick, className, expansionControl, onViewLogs, onDeleteTask, onRunAllChildTasks, isCreatingAllSubtasks, hasVirtualSubtasks }: TaskCardProps) {
  // Debug logging
  console.log(`[TaskCard-${task.id}] Render`);

  // Get assignee details with more robust matching
  const assignee = mockTeamMembers.find((member: TeamUser) => {
    // Since the Task type doesn't have assignees property, we'll skip this check
    return false;
  });

  // Get assignee name with fallback to agent type instead of "Unassigned"
  const assigneeName = assignee
    ? `${assignee.first_name} ${assignee.last_name}`
    : task.agent_type || "Unassigned";

  // Get initials for avatar
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

  // Handle dialog click to prevent it from triggering the card onClick
  const handleDialogClick = (e: React.MouseEvent) => {
    e.stopPropagation();
  };

  // Get repo count badge
  const repoCount = task.repos?.length || 0;
  const repoLabel = repoCount === 1 ? "1 repo" : `${repoCount} repos`;

  return (
    <div
      className={`p-2 bg-card rounded-lg shadow-sm border border-border hover:shadow-md hover:border-primary/50 transition-all cursor-pointer space-y-1 ${className || ''}`}
      onClick={onClick}
    >
      <div className="flex items-start justify-between">
        <h3 className="font-medium text-sm">{task.title}</h3>
        <div className="flex items-center gap-2">
          {task.status === "Running" && (
            <div className="flex items-center justify-center">
              <GridLoader
                size={4}
                margin={1}
                color="#5d70d5"
                loading={true}
                cssOverride={{}}
                speedMultiplier={1}
              />
            </div>
          )}
          {onViewLogs && (
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              title="View Logs"
              onClick={(e) => {
                e.stopPropagation();
                console.log(`[TaskCard-${task.id}] Requesting logs dialog`);
                onViewLogs(task);
              }}
            >
              <span className="text-xs">🪵</span>
            </Button>
          )}
          {onDeleteTask && (
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 text-destructive hover:bg-destructive/10"
              title="Delete Task"
              onClick={(e) => {
                e.stopPropagation();
                console.log(`[TaskCard-${task.id}] Requesting task deletion`);
                onDeleteTask(task);
              }}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
      <div className="flex items-start justify-between">
        {task.description && (
          <p className="text-xs text-muted-foreground line-clamp-2">
            {task.description}
          </p>
        )}
      </div>
      <div className="mt-1 flex items-center justify-between text-xs text-muted-foreground">
        <div className="flex items-center gap-2">
          <Avatar className="h-6 w-6">
            {agentAvatar ? (
              <div className="w-full h-full flex items-center justify-center">
                <AvatarImage
                  src={agentAvatar}
                  className="w-4 h-4 object-contain"
                />
              </div>
            ) : (
              <AvatarImage src={assignee?.avatar} />
            )}
            <AvatarFallback>{assigneeInitials}</AvatarFallback>
          </Avatar>
          <span>{assigneeName}</span>

          {/* Run All Child Tasks button for Fullstack tasks */}
          {task.agent_type === "Fullstack" &&
           (task.status === "Done" || task.status === "Waiting for Input") &&
           onRunAllChildTasks &&
           hasVirtualSubtasks && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground ml-4 border border-[#5d70d5] border-opacity-30 hover:border-opacity-50"
              onClick={(e) => {
                e.stopPropagation();
                onRunAllChildTasks(task);
              }}
              disabled={isCreatingAllSubtasks}
              title="Run All Child Tasks"
            >
              {isCreatingAllSubtasks ? (
                <>
                  <span className="animate-spin text-xs mr-1">⟳</span>
                  Creating...
                </>
              ) : (
                <>
                  <span className="mr-1">▶</span>
                  Run All
                </>
              )}
            </Button>
          )}
        </div>
        <div className="flex items-center gap-2">
          {expansionControl}
          {repoCount > 0 && (
            <Badge variant="outline" className="text-xs py-0 h-5 flex items-center gap-1 bg-muted text-muted-foreground text-[10px]">
              <GitBranch className="h-3 w-3" />
              {repoLabel}
            </Badge>
          )}
          {task.due_date && (
            <span>{format(new Date(task.due_date), "MMM d, yyyy")}</span>
          )}
        </div>
      </div>
    </div>
  );
}

export default React.memo(TaskCard);
