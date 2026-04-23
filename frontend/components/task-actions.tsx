"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { API_BASE_URL } from "@/lib/api";
import { TaskStatus } from "@/lib/types";

interface TaskActionsProps {
  taskId: string;
  status: TaskStatus;
  mode?: "review" | "console";
}

async function postAction(path: string) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || "操作失败");
  }
}

export function TaskActions({ taskId, status, mode = "console" }: TaskActionsProps) {
  const router = useRouter();
  const [message, setMessage] = useState("");
  const [pending, startTransition] = useTransition();

  const runAction = (path: string, successText: string) => {
    startTransition(() => {
      void (async () => {
        try {
          await postAction(path);
          setMessage(successText);
          router.refresh();
        } catch (error) {
          setMessage(error instanceof Error ? error.message : "操作失败");
        }
      })();
    });
  };

  const canReviewRollback = ["ready", "failed", "published"].includes(status);

  return (
    <div className="action-row">
      <Link href={`/tasks/${taskId}`} className="button secondary">
        查看详情
      </Link>

      {mode === "review" && (status === "draft" || status === "pending_review") ? (
        <button className="button" disabled={pending} onClick={() => runAction(`/api/tasks/${taskId}/approve`, "任务已审核通过。")}>
          审核通过
        </button>
      ) : null}

      {mode === "review" && canReviewRollback ? (
        <button className="button" disabled={pending} onClick={() => runAction(`/api/tasks/${taskId}/review-rollback`, "任务已回退到待审核状态。")}>
          审核回退
        </button>
      ) : null}

      {mode === "review" && status === "publishing" ? <span className="inline-message">发布中，暂不能审核回退。</span> : null}

      {mode === "console" && status === "ready" ? (
        <button className="button highlight" disabled={pending} onClick={() => runAction(`/api/tasks/${taskId}/publish`, "发布任务已提交。")}>
          开始发布
        </button>
      ) : null}

      {mode === "console" && status === "failed" ? (
        <button className="button" disabled={pending} onClick={() => runAction(`/api/tasks/${taskId}/retry`, "任务已恢复为待重试。")}>
          重试
        </button>
      ) : null}

      {mode === "console" && status === "published" ? (
        <button className="button" disabled={pending} onClick={() => runAction(`/api/tasks/${taskId}/rollback`, "任务已回退到待发布状态。")}>
          回退
        </button>
      ) : null}

      {mode === "review" && status === "ready" ? <span className="inline-message">已审核，可在任务控制台发布。</span> : null}

      {message ? <span className="inline-message">{message}</span> : null}
    </div>
  );
}
