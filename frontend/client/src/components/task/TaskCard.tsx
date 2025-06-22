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
import { useState } from "react";
import sweAvatar from "@/assets/swe-icon.png";
import pmAvatar from "@/assets/pm-icon.png";
import fullstackAvatar from "@/assets/fullstack-icon.png";

interface TaskCardProps {
  task: Task;
  onClick?: () => void;
  className?: string;
  expansionControl?: React.ReactNode;
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

export default function TaskCard({ task, onClick, className, expansionControl }: TaskCardProps) {
  const [isDialogOpen, setIsDialogOpen] = useState(false);

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

  return (
    <div
      className={`p-2 bg-card rounded-lg shadow-sm border border-border hover:shadow-md transition-shadow cursor-pointer space-y-1 ${className || ''}`}
      onClick={onClick}
    >
      <div className="flex items-start justify-between">
        <h3 className="font-medium text-sm">{task.title}</h3>
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogTrigger asChild onClick={handleDialogClick}>
            <Button variant="ghost" size="sm" className="h-6 px-2 text-xs">
              🪵 View Logs
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Watch your agent cook 🔥</DialogTitle>
            </DialogHeader>
            <div className="bg-slate-950 p-4 rounded-md overflow-auto max-h-96">
              <pre className="text-xs text-slate-100">{JSON.stringify(mockLogs, null, 2)}</pre>
            </div>
          </DialogContent>
        </Dialog>
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
        </div>
        <div className="flex items-center gap-2">
          {expansionControl}
          {task.due_date && (
            <span>{format(new Date(task.due_date), "MMM d, yyyy")}</span>
          )}
        </div>
      </div>
    </div>
  );
}
