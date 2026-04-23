export type TaskStatus =
  | "draft"
  | "pending_review"
  | "ready"
  | "publishing"
  | "published"
  | "failed";

export type DeviceStatus = "idle" | "busy" | "offline" | "error";

export interface MaterialBatch {
  id: number;
  batch_id: string;
  sku_code: string;
  image_1?: string | null;
  image_2?: string | null;
  image_3?: string | null;
  image_4?: string | null;
  cover_image?: string | null;
  tags?: string | null;
  created_at: string;
}

export interface AccountDevice {
  id: number;
  account_id: string;
  account_name: string;
  platform: string;
  device_id: string;
  device_name?: string | null;
  adb_serial?: string | null;
  appium_url?: string | null;
  status: DeviceStatus;
  last_heartbeat?: string | null;
  remark?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PublishLog {
  id: number;
  task_id: string;
  step_name: string;
  result: string;
  detail?: string | null;
  screenshot?: string | null;
  created_at: string;
}

export interface PublishTask {
  id: number;
  task_id: string;
  platform: string;
  sku_code: string;
  account_id?: string | null;
  device_id?: string | null;
  material_batch_id?: string | null;
  title: string;
  content?: string | null;
  topics?: string | null;
  status: TaskStatus;
  current_step?: string | null;
  plan_publish_time?: string | null;
  actual_publish_time?: string | null;
  execution_started_at?: string | null;
  execution_finished_at?: string | null;
  retry_count: number;
  error_message?: string | null;
  publish_url?: string | null;
  result_screenshot?: string | null;
  created_at: string;
  updated_at: string;
  account_device?: AccountDevice | null;
}

export interface PublishTaskDetail extends PublishTask {
  material_batch?: MaterialBatch | null;
  account_device?: AccountDevice | null;
  logs: PublishLog[];
}
