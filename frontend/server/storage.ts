import {
  tasks,
  users,
  type Task,
  type InsertTask,
  type User,
  type InsertUser,
  TaskStatus
} from "@shared/schema";

// Interface for storage operations
export interface IStorage {
  // User operations
  getUser(id: number): Promise<User | undefined>;
  getUserByUsername(username: string): Promise<User | undefined>;
  createUser(user: InsertUser): Promise<User>;

  // Task operations
  getAllTasks(): Promise<Task[]>;
  getTaskById(id: number): Promise<Task | undefined>;
  getTasksByStatus(status: TaskStatus): Promise<Task[]>;
  getTasksByAssignee(assignee: string): Promise<Task[]>;
  getTasksByProject(project: string): Promise<Task[]>;
  getTasksByTopic(topic: string): Promise<Task[]>;
  createTask(task: InsertTask): Promise<Task>;
  updateTask(id: number, task: Partial<Task>): Promise<Task | undefined>;
  deleteTask(id: number): Promise<boolean>;

  // Meta operations
  getAssignees(): Promise<string[]>;
  getTopics(): Promise<string[]>;
  getProjects(): Promise<string[]>;
}

// In-memory storage implementation
export class MemStorage implements IStorage {
  private users: Map<number, User>;
  private tasks: Map<number, Task>;
  private userIdCounter: number;
  private taskIdCounter: number;

  constructor() {
    this.users = new Map();
    this.tasks = new Map();
    this.userIdCounter = 1;
    this.taskIdCounter = 1;

    // Add default user
    this.createUser({
      username: "demo",
      password: "password",
      name: "Alex Johnson",
      role: "admin",
      avatarUrl: "https://eminyrxftyqxwrazqukk.supabase.co/storage/v1/object/public/public-cairn//Screenshot%202025-05-05%20at%2010.35.37%20PM.png"
    });

    // Seed some initial data
    this.seedInitialData();
  }

  // User operations
  async getUser(id: number): Promise<User | undefined> {
    return this.users.get(id);
  }

  async getUserByUsername(username: string): Promise<User | undefined> {
    return Array.from(this.users.values()).find(
      (user) => user.username === username,
    );
  }

  async createUser(insertUser: InsertUser): Promise<User> {
    const id = this.userIdCounter++;
    const user: User = { ...insertUser, id };
    this.users.set(id, user);
    return user;
  }

  // Task operations
  async getAllTasks(): Promise<Task[]> {
    return Array.from(this.tasks.values());
  }

  async getTaskById(id: number): Promise<Task | undefined> {
    return this.tasks.get(id);
  }

  async getTasksByStatus(status: TaskStatus): Promise<Task[]> {
    return Array.from(this.tasks.values()).filter(
      (task) => task.status === status
    );
  }

  async getTasksByAssignee(assignee: string): Promise<Task[]> {
    return Array.from(this.tasks.values()).filter(
      (task) => task.assignee === assignee
    );
  }

  async getTasksByProject(project: string): Promise<Task[]> {
    return Array.from(this.tasks.values()).filter(
      (task) => task.project === project
    );
  }

  async getTasksByTopic(topic: string): Promise<Task[]> {
    return Array.from(this.tasks.values()).filter(
      (task) => task.topic === topic
    );
  }

  async createTask(insertTask: InsertTask): Promise<Task> {
    const id = this.taskIdCounter++;
    const now = new Date();

    const task: Task = {
      ...insertTask,
      id,
      createdAt: insertTask.createdAt || now,
      updatedAt: now,
      // Set completedAt if the status is completed
      completedAt: insertTask.status === 'completed' ? now : insertTask.completedAt
    };

    this.tasks.set(id, task);
    return task;
  }

  async updateTask(id: number, taskUpdate: Partial<Task>): Promise<Task | undefined> {
    const task = this.tasks.get(id);
    if (!task) return undefined;

    const updatedTask: Task = {
      ...task,
      ...taskUpdate,
      updatedAt: new Date(),
      // Set completedAt if status is being changed to completed
      completedAt: taskUpdate.status === 'completed' ? new Date() :
                  (task.status === 'completed' && taskUpdate.status && taskUpdate.status !== 'completed') ?
                    undefined : task.completedAt
    };

    this.tasks.set(id, updatedTask);
    return updatedTask;
  }

  async deleteTask(id: number): Promise<boolean> {
    return this.tasks.delete(id);
  }

  // Meta operations - get unique values
  async getAssignees(): Promise<string[]> {
    const assignees = new Set<string>();
    for (const task of this.tasks.values()) {
      if (task.assignee) assignees.add(task.assignee);
    }
    return Array.from(assignees);
  }

  async getTopics(): Promise<string[]> {
    const topics = new Set<string>();
    for (const task of this.tasks.values()) {
      if (task.topic) topics.add(task.topic);
    }
    return Array.from(topics);
  }

  async getProjects(): Promise<string[]> {
    const projects = new Set<string>();
    for (const task of this.tasks.values()) {
      if (task.project) projects.add(task.project);
    }
    return Array.from(projects);
  }

  // Helper method to seed initial data
  private seedInitialData() {
    const sampleTasks: InsertTask[] = [
      {
        title: "Design homepage wireframes",
        description: "Create wireframes for the new homepage design based on the approved mockups",
        status: "queued",
        assignee: "Sarah Chen",
        dueDate: new Date(2025, 5, 17), // June 17, 2025
        topic: "Design",
        project: "Website Redesign Project",
        createdAt: new Date(2025, 5, 10) // June 10, 2025
      },
      {
        title: "Research competitor sites",
        description: "Analyze competitor websites and create a report of findings",
        status: "queued",
        assignee: "Michael Torres",
        dueDate: new Date(2025, 5, 19), // June 19, 2025
        topic: "Research",
        project: "Website Redesign Project",
        createdAt: new Date(2025, 5, 12) // June 12, 2025
      },
      {
        title: "Create content plan",
        description: "Draft a content strategy for the blog section",
        status: "queued",
        assignee: "Jessica Wu",
        dueDate: new Date(2025, 5, 22), // June 22, 2025
        topic: "Content",
        project: "Website Redesign Project",
        createdAt: new Date(2025, 5, 15) // June 15, 2025
      },
      {
        title: "Develop navigation menu",
        description: "Create responsive navigation menu with dropdown functionality",
        status: "running",
        assignee: "David Kim",
        dueDate: new Date(2025, 5, 15), // June 15, 2025
        topic: "Development",
        project: "Website Redesign Project",
        createdAt: new Date(2025, 5, 8) // June 8, 2025
      },
      {
        title: "Design product cards",
        description: "Create reusable product card components with hover states",
        status: "running",
        assignee: "Sarah Chen",
        dueDate: new Date(2025, 5, 16), // June 16, 2025
        topic: "Design",
        project: "Website Redesign Project",
        createdAt: new Date(2025, 5, 9) // June 9, 2025
      },
      {
        title: "Test contact form",
        description: "Verify form validation and submission are working correctly",
        status: "running",
        assignee: "James Rodriguez",
        dueDate: new Date(2025, 5, 12), // June 12, 2025
        topic: "QA",
        project: "Website Redesign Project",
        createdAt: new Date(2025, 5, 5) // June 5, 2025
      },
      {
        title: "Cross-browser testing",
        description: "Test site functionality across Chrome, Firefox, Safari, and Edge",
        status: "failed",
        assignee: "Michael Torres",
        dueDate: new Date(2025, 5, 14), // June 14, 2025
        topic: "QA",
        project: "Website Redesign Project",
        createdAt: new Date(2025, 5, 7) // June 7, 2025
      },
      {
        title: "Set up project repository",
        description: "Initialize Git repository and set up folder structure",
        status: "done",
        assignee: "David Kim",
        dueDate: new Date(2025, 5, 4), // June 4, 2025
        topic: "DevOps",
        project: "Website Redesign Project",
        createdAt: new Date(2025, 5, 2), // June 2, 2025
        completedAt: new Date(2025, 5, 4) // June 4, 2025
      },
      {
        title: "Define project requirements",
        description: "Document functional and technical requirements for the website redesign",
        status: "done",
        assignee: "Jessica Wu",
        dueDate: new Date(2025, 5, 3), // June 3, 2025
        topic: "Planning",
        project: "Website Redesign Project",
        createdAt: new Date(2025, 5, 1), // June 1, 2025
        completedAt: new Date(2025, 5, 3) // June 3, 2025
      },
      {
        title: "Create project timeline",
        description: "Develop a detailed project schedule with milestones and deadlines",
        status: "done",
        assignee: "Alex Johnson",
        dueDate: new Date(2025, 4, 31), // May 31, 2025
        topic: "Planning",
        project: "Website Redesign Project",
        createdAt: new Date(2025, 4, 29), // May 29, 2025
        completedAt: new Date(2025, 4, 31) // May 31, 2025
      }
    ];

    // Add all sample tasks to the storage
    for (const task of sampleTasks) {
      this.createTask(task);
    }
  }
}

export const storage = new MemStorage();
