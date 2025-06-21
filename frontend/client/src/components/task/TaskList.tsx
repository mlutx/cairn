import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { format } from "date-fns";
import { Task, Priority, TeamUser } from "@/types";
import { getInitials } from "@/lib/utils/task-utils";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";

interface TaskListProps {
  tasks: { data: Task[] };
  onTaskClick: (task: Task) => void;
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

const getPriorityColor = (priority: Priority) => {
  switch (priority) {
    case "Urgent":
      return "bg-red-100 text-red-700 border-red-200";
    case "High":
      return "bg-orange-100 text-orange-700 border-orange-200";
    case "Medium":
      return "bg-yellow-100 text-yellow-700 border-yellow-200";
    case "Low":
      return "bg-green-100 text-green-700 border-green-200";
    case "No Priority":
      return "bg-gray-100 text-gray-700 border-gray-200";
    default:
      return "bg-gray-100 text-gray-700 border-gray-200";
  }
};

export default function TaskList({ tasks, onTaskClick }: TaskListProps) {
  if (!tasks?.data?.length) {
    return null;
  }

  // Get assignee details for a task
  const getAssigneeDetails = (task: Task) => {
    const assignee = mockTeamMembers.find((member: TeamUser) => {
      return task.assignees?.some(assigneeId =>
        member.uid === assigneeId || // Exact match
        member.uid?.toString() === assigneeId?.toString() || // String comparison
        member.account_email_address === assigneeId // Try email
      );
    });

    const assigneeName = assignee
      ? `${assignee.first_name} ${assignee.last_name}`
      : task.assignees?.[0] || "Unassigned";
    const assigneeInitials = assignee
      ? getInitials(`${assignee.first_name} ${assignee.last_name}`)
      : task.assignees?.[0]
        ? getInitials(task.assignees[0])
        : "U";

    return { assignee, assigneeName, assigneeInitials };
  };

  return (
    <div className="space-y-4">
      {tasks.data.map((task: Task) => {
        const { assignee, assigneeName, assigneeInitials } = getAssigneeDetails(task);
        return (
          <div
            key={task.id}
            className="p-4 bg-card rounded-lg shadow-sm border border-border hover:shadow-md transition-shadow cursor-pointer"
            onClick={() => onTaskClick(task)}
          >
            <div className="flex items-start justify-between">
              <div className="space-y-2">
                <h3 className="font-medium">{task.title}</h3>
                {task.description && (
                  <p className="text-sm text-muted-foreground line-clamp-2">
                    {task.description}
                  </p>
                )}
              </div>
              {task.priority && (
                <Badge variant="outline" className={`${getPriorityColor(task.priority)} font-medium`}>
                  {task.priority}
                </Badge>
              )}
            </div>
            <div className="mt-4 flex items-center justify-between text-sm text-muted-foreground">
              <div className="flex items-center gap-2">
                <Avatar className="h-6 w-6">
                  <AvatarImage src={assignee?.avatar} />
                  <AvatarFallback>{assigneeInitials}</AvatarFallback>
                </Avatar>
                <span>{assigneeName}</span>
              </div>
              {task.due_date && (
                <span>{format(new Date(task.due_date), "MMM d, yyyy")}</span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
