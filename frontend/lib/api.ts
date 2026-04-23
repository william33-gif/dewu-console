import { AccountDevice, MaterialBatch, PublishLog, PublishTask, PublishTaskDetail } from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function safeRequest<T>(path: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return fallback;
    }

    return (await response.json()) as T;
  } catch {
    return fallback;
  }
}

export async function getTasks(): Promise<PublishTask[]> {
  return safeRequest("/api/tasks", []);
}

export async function getTask(taskId: string): Promise<PublishTaskDetail | null> {
  return safeRequest(`/api/tasks/${taskId}`, null);
}

export async function getMaterialBatches(): Promise<MaterialBatch[]> {
  return safeRequest("/api/material-batches", []);
}

export async function getAccountDevices(): Promise<AccountDevice[]> {
  return safeRequest("/api/account-devices", []);
}

export async function getLogs(taskId?: string): Promise<PublishLog[]> {
  const suffix = taskId ? `?task_id=${encodeURIComponent(taskId)}` : "";
  return safeRequest(`/api/publish-logs${suffix}`, []);
}

export { API_BASE_URL };
