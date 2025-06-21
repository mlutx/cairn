import { pgTable, text, serial, integer, timestamp, varchar } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod";

// Define status enum for task status
export const TaskStatusEnum = z.enum([
  'queued',
  'running',
  'done',
  'failed'
]);

export type TaskStatus = z.infer<typeof TaskStatusEnum>;

// Task table
export const tasks = pgTable("tasks", {
  id: serial("id").primaryKey(),
  title: text("title").notNull(),
  description: text("description"),
  status: text("status").notNull().$type<TaskStatus>().default('queued'),
  assignee: text("assignee"),
  dueDate: timestamp("due_date"),
  topic: text("topic"),
  createdAt: timestamp("created_at").notNull().defaultNow(),
  updatedAt: timestamp("updated_at").notNull().defaultNow(),
  completedAt: timestamp("completed_at"),
  project: text("project").default("Default Project"),
});

// User roles enum
export const UserRoleEnum = z.enum([
  'admin',
  'member',
  'viewer'
]);

export type UserRole = z.infer<typeof UserRoleEnum>;

// Users table
export const users = pgTable("users", {
  id: serial("id").primaryKey(),
  username: text("username").notNull().unique(),
  password: text("password").notNull(),
  name: text("name").notNull(),
  role: text("role").$type<UserRole>().default('member'),
  avatarUrl: text("avatar_url"),
});

// Insert schemas using drizzle-zod
export const insertTaskSchema = createInsertSchema(tasks)
  .omit({ id: true, updatedAt: true });

export const insertUserSchema = createInsertSchema(users)
  .omit({ id: true });

// Types for the insert schemas
export type InsertTask = z.infer<typeof insertTaskSchema>;
export type InsertUser = z.infer<typeof insertUserSchema>;

// Types for the tables
export type Task = typeof tasks.$inferSelect;
export type User = typeof users.$inferSelect;
