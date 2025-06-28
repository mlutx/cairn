import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/use-toast';
import { taskApi } from '@/lib/api/task';
import { TaskForm } from './TaskForm';

interface Task {
  id: string;
  title: string;
  description?: string;
  status: string;
  created_at: string;
  // Add other task properties as needed
}

export function TaskList() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const { toast } = useToast();

  // Fetch tasks on component mount
  useEffect(() => {
    fetchTasks();
  }, []);

  const fetchTasks = async () => {
    try {
      setIsLoading(true);
      const response = await taskApi.getTasks();
      setTasks(response.tasks);
    } catch (error) {
      console.error('Error fetching tasks:', error);
      toast({
        title: "Error",
        description: "Failed to fetch tasks",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteTasks = async (taskIds: string[]) => {
    try {
      setIsLoading(true);
      await taskApi.deleteTasks(taskIds);
      setTasks(tasks.filter(task => !taskIds.includes(task.id)));
      toast({
        title: "Success",
        description: "Tasks deleted successfully",
      });
    } catch (error) {
      console.error('Error deleting tasks:', error);
      toast({
        title: "Error",
        description: "Failed to delete tasks",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <TaskForm onTaskAdded={fetchTasks} />
      </div>

      <div className="space-y-2">
        {tasks.map((task) => (
          <div key={task.id} className="flex items-center justify-between p-4 border rounded">
            <div>
              <h3 className="font-semibold">{task.title}</h3>
              {task.description && <p className="text-sm text-gray-500">{task.description}</p>}
              <p className="text-sm text-gray-500">Status: {task.status}</p>
            </div>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => handleDeleteTasks([task.id])}
              disabled={isLoading}
            >
              Delete
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}
