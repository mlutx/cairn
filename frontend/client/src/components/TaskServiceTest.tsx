import { useEffect, useState } from "react";
import { fetchTasks } from "@/services/taskService";
import { Task } from "@/types";

export default function TaskServiceTest() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadTasks() {
      try {
        setLoading(true);
        const fetchedTasks = await fetchTasks();
        setTasks(fetchedTasks);
        setError(null);
      } catch (err) {
        console.error("Error loading tasks:", err);
        setError("Failed to load tasks");
      } finally {
        setLoading(false);
      }
    }

    loadTasks();
  }, []);

  return (
    <div className="p-4">
      <h1 className="text-xl font-bold mb-4">Task Service Test</h1>

      {loading && <p>Loading tasks...</p>}

      {error && <p className="text-red-500">{error}</p>}

      {!loading && !error && (
        <div>
          <p>Loaded {tasks.length} tasks</p>
          <button
            className="bg-blue-500 text-white px-4 py-2 rounded mt-2"
            onClick={() => console.log("Current tasks:", tasks)}
          >
            Log Tasks to Console
          </button>

          <div className="mt-4">
            <h2 className="text-lg font-semibold mb-2">Task Preview:</h2>
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-gray-100">
                  <th className="p-2 text-left">ID</th>
                  <th className="p-2 text-left">Title</th>
                  <th className="p-2 text-left">Status</th>
                  <th className="p-2 text-left">Agent Type</th>
                  <th className="p-2 text-left">Repos</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map(task => (
                  <tr key={task.id} className="border-t">
                    <td className="p-2">{task.id}</td>
                    <td className="p-2">{task.title}</td>
                    <td className="p-2">{task.status}</td>
                    <td className="p-2">{task.agent_type}</td>
                    <td className="p-2">
                      {task.repos && task.repos.length > 0 ? (
                        <ul className="list-disc pl-4">
                          {task.repos.map((repo, idx) => (
                            <li key={idx}>{repo}</li>
                          ))}
                        </ul>
                      ) : (
                        "No repos"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div className="mt-8">
              <h3 className="text-md font-semibold mb-2">Raw Task Data:</h3>
              <pre className="bg-gray-100 p-4 rounded overflow-auto max-h-96">
                {JSON.stringify(tasks, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
