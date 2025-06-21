import type { Express } from "express";
import { createServer, type Server } from "http";
import { WebSocketServer } from "ws";
import { storage } from "./storage";
import { TaskStatusEnum, insertTaskSchema } from "@shared/schema";
import { z } from "zod";

export async function registerRoutes(app: Express): Promise<Server> {
  // Create HTTP server
  const httpServer = createServer(app);

  // Create WebSocket server with a specific path to avoid conflicts with Vite
  const wss = new WebSocketServer({
    server: httpServer,
    path: '/ws'  // This ensures our WebSocket server only handles connections to /ws
  });

  wss.on('connection', (ws) => {
    console.log('New WebSocket connection');

    ws.on('message', (message) => {
      console.log('Received:', message);
    });

    ws.on('close', () => {
      console.log('Client disconnected');
    });
  });

  // Get all tasks
  app.get("/api/tasks", async (_req, res) => {
    try {
      const tasks = await storage.getAllTasks();
      res.json(tasks);
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch tasks" });
    }
  });

  // Get task by ID
  app.get("/api/tasks/:id", async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      if (isNaN(id)) {
        return res.status(400).json({ message: "Invalid task ID" });
      }

      const task = await storage.getTaskById(id);
      if (!task) {
        return res.status(404).json({ message: "Task not found" });
      }

      res.json(task);
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch task" });
    }
  });

  // Create new task
  app.post("/api/tasks", async (req, res) => {
    try {
      const result = insertTaskSchema.safeParse(req.body);

      if (!result.success) {
        return res.status(400).json({
          message: "Invalid task data",
          errors: result.error.format()
        });
      }

      const newTask = await storage.createTask(result.data);
      res.status(201).json(newTask);
    } catch (error) {
      res.status(500).json({ message: "Failed to create task" });
    }
  });

  // Update task
  app.patch("/api/tasks/:id", async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      if (isNaN(id)) {
        return res.status(400).json({ message: "Invalid task ID" });
      }

      // Validate the update fields
      const updateSchema = insertTaskSchema.partial().extend({
        status: z.enum(['queued', 'running', 'done', 'failed']).optional()
      });
      const result = updateSchema.safeParse(req.body);

      if (!result.success) {
        return res.status(400).json({
          message: "Invalid task update data",
          errors: result.error.format()
        });
      }

      const updatedTask = await storage.updateTask(id, result.data);
      if (!updatedTask) {
        return res.status(404).json({ message: "Task not found" });
      }

      res.json(updatedTask);
    } catch (error) {
      res.status(500).json({ message: "Failed to update task" });
    }
  });

  // Delete task
  app.delete("/api/tasks/:id", async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      if (isNaN(id)) {
        return res.status(400).json({ message: "Invalid task ID" });
      }

      const success = await storage.deleteTask(id);
      if (!success) {
        return res.status(404).json({ message: "Task not found" });
      }

      res.status(204).end();
    } catch (error) {
      res.status(500).json({ message: "Failed to delete task" });
    }
  });

  // Get tasks by status
  app.get("/api/tasks/status/:status", async (req, res) => {
    try {
      const statusParam = req.params.status;

      // Validate status
      const result = TaskStatusEnum.safeParse(statusParam);
      if (!result.success) {
        return res.status(400).json({ message: "Invalid status value" });
      }

      const tasks = await storage.getTasksByStatus(result.data);
      res.json(tasks);
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch tasks by status" });
    }
  });

  // Get tasks by assignee
  app.get("/api/tasks/assignee/:assignee", async (req, res) => {
    try {
      const assignee = req.params.assignee;
      const tasks = await storage.getTasksByAssignee(assignee);
      res.json(tasks);
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch tasks by assignee" });
    }
  });

  // Get tasks by project
  app.get("/api/tasks/project/:project", async (req, res) => {
    try {
      const project = req.params.project;
      const tasks = await storage.getTasksByProject(project);
      res.json(tasks);
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch tasks by project" });
    }
  });

  // Get tasks by topic
  app.get("/api/tasks/topic/:topic", async (req, res) => {
    try {
      const topic = req.params.topic;
      const tasks = await storage.getTasksByTopic(topic);
      res.json(tasks);
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch tasks by topic" });
    }
  });

  // Get metadata - all assignees
  app.get("/api/meta/assignees", async (_req, res) => {
    try {
      const assignees = await storage.getAssignees();
      res.json(assignees);
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch assignees" });
    }
  });

  // Get metadata - all topics
  app.get("/api/meta/topics", async (_req, res) => {
    try {
      const topics = await storage.getTopics();
      res.json(topics);
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch topics" });
    }
  });

  // Get metadata - all projects
  app.get("/api/meta/projects", async (_req, res) => {
    try {
      const projects = await storage.getProjects();
      res.json(projects);
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch projects" });
    }
  });

  return httpServer;
}
