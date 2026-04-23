"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { API_BASE_URL } from "@/lib/api";

export function FeishuSyncButton() {
  const router = useRouter();
  const [message, setMessage] = useState("");
  const [pending, startTransition] = useTransition();

  const handleSync = () => {
    startTransition(() => {
      void (async () => {
        setMessage("");
        try {
          const response = await fetch(`${API_BASE_URL}/api/feishu/sync`, {
            method: "POST",
          });

          if (!response.ok) {
            const payload = await response.json().catch(() => ({}));
            throw new Error(payload.detail || "飞书同步失败");
          }

          const payload = await response.json();
          setMessage(`已同步 ${payload.synced} 条，跳过 ${payload.skipped} 条，失败 ${payload.failed} 条。`);
          router.refresh();
        } catch (error) {
          setMessage(error instanceof Error ? error.message : "飞书同步失败");
        }
      })();
    });
  };

  return (
    <div className="action-row">
      <button className="button secondary" disabled={pending} onClick={handleSync}>
        {pending ? "同步中..." : "同步飞书"}
      </button>
      {message ? <span className="inline-message">{message}</span> : null}
    </div>
  );
}
