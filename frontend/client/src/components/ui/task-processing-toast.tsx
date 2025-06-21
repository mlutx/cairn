import { Loader2 } from "lucide-react";
import { Toast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/use-toast";
import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";

interface TaskProcessingToastProps {
  taskId: string;
  onComplete?: () => void;
}

export function TaskProcessingToast({ taskId, onComplete }: TaskProcessingToastProps) {
  const { toast } = useToast();
  const [isProcessing, setIsProcessing] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    if (!isProcessing && onComplete) {
      onComplete();
    }
  }, [isProcessing, onComplete]);

  return (
    <div className="flex items-center gap-2">
      {isProcessing ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : (
        <span className="h-4 w-4 bg-green-500 rounded-full" />
      )}
      <div className="flex-1">
        <div className="font-medium">
          {isProcessing ? "Processing task..." : "Task processing complete"}
        </div>
        <div className="text-xs text-muted-foreground">
          {isProcessing
            ? "AI is breaking down your task into subtasks"
            : "Subtasks have been generated"
          }
        </div>
      </div>
      <Button
        variant={isProcessing ? "outline" : "default"}
        size="sm"
        className="ml-auto"
        onClick={() => setIsProcessing(false)}
      >
        {isProcessing ? "Dismiss" : "Close"}
      </Button>
    </div>
  );
}

export function useTaskProcessingToast() {
  const { toast } = useToast();

  const showProcessingToast = (taskId: string) => {
    const toastInstance = toast({
      title: "Processing Task",
      description: "AI is breaking down your task into subtasks",
      duration: Infinity,
      action: (
        <Button
          variant="outline"
          size="sm"
          className="ml-auto"
        >
          Dismiss
        </Button>
      ),
    });

    return toastInstance;
  };

  return { showProcessingToast };
}
