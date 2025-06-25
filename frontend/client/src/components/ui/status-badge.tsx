import { cn } from "@/lib/utils";
import { TaskStatus } from "@/types/task";

interface StatusBadgeProps {
  status: TaskStatus;
  className?: string;
  compact?: boolean;
}

export function StatusBadge({ status, className, compact = false }: StatusBadgeProps) {
  // Updated config for sleek dark mode design with five statuses
  const statusConfig: Record<string, {
    dotColor: string;
    label: string;
  }> = {
    'Queued': {
      dotColor: 'bg-red-400/90',
      label: 'Queued'
    },
    'Running': {
      dotColor: 'bg-amber-400/90',
      label: 'Running'
    },
    'Done': {
      dotColor: 'bg-emerald-400/90',
      label: 'Done'
    },
    'Failed': {
      dotColor: 'bg-rose-400/90',
      label: 'Failed'
    },
    'Waiting for Input': {
      dotColor: 'bg-blue-400/90',
      label: 'Waiting for Input'
    }
  };

  const config = statusConfig[status];

  if (!config) {
    console.warn(`Unknown status: ${status}`);
    return (
      <span className={cn(
        "inline-flex items-center gap-1.5",
        className
      )}>
        <span className="w-2 h-2 rounded-full bg-neutral-500 ring-1 ring-neutral-500/20"></span>
        {!compact && <span className="text-xs font-medium text-neutral-300">{status}</span>}
      </span>
    );
  }

  return (
    <span className={cn(
      "inline-flex items-center gap-1.5",
      className
    )}>
      <span className={cn(
        "w-2 h-2 rounded-full ring-1 ring-inset ring-white/10",
        config.dotColor
      )}></span>
      {!compact && <span className="text-xs font-medium text-neutral-300">{config.label}</span>}
    </span>
  );
}
