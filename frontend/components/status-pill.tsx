import { DeviceStatus, TaskStatus } from "@/lib/types";

const LABELS: Record<string, string> = {
  draft: "草稿",
  pending_review: "待审核",
  ready: "待发布",
  publishing: "发布中",
  published: "已发布",
  failed: "失败",
  idle: "空闲",
  busy: "忙碌",
  offline: "离线",
  error: "异常",
  success: "成功",
  running: "执行中",
};

export function StatusPill({ status }: { status: TaskStatus | DeviceStatus | string }) {
  return <span className={`status-pill status-${status}`}>{LABELS[status] ?? status}</span>;
}
