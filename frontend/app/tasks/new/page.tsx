"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { API_BASE_URL } from "@/lib/api";

export default function NewTaskPage() {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setMessage("");

    const formData = new FormData(event.currentTarget);
    const payload = {
      sku_code: String(formData.get("sku_code") || ""),
      title: String(formData.get("title") || ""),
      content: String(formData.get("content") || ""),
      topics: String(formData.get("topics") || ""),
      account_id: String(formData.get("account_id") || "") || null,
      device_id: String(formData.get("device_id") || "") || null,
      material_batch_id: String(formData.get("material_batch_id") || "") || null,
      plan_publish_time: String(formData.get("plan_publish_time") || "") || null,
    };

    try {
      const response = await fetch(`${API_BASE_URL}/api/tasks`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorPayload = await response.json().catch(() => ({}));
        throw new Error(errorPayload.detail || "创建任务失败");
      }

      const created = await response.json();
      router.push(`/tasks/${created.task_id}`);
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "创建任务失败");
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <section className="page-head">
        <div>
          <h2>新建任务</h2>
          <p>第一版先把任务创建入口做轻一点，重点是让任务、素材、账号设备能串起来。</p>
        </div>
      </section>

      <section className="panel">
        <form onSubmit={handleSubmit} className="form-grid">
          <div className="field">
            <label htmlFor="sku_code">款号</label>
            <input id="sku_code" name="sku_code" required />
          </div>

          <div className="field">
            <label htmlFor="title">标题</label>
            <input id="title" name="title" required />
          </div>

          <div className="field">
            <label htmlFor="account_id">账号ID</label>
            <input id="account_id" name="account_id" placeholder="例如 ACC-001" />
          </div>

          <div className="field">
            <label htmlFor="device_id">设备ID</label>
            <input id="device_id" name="device_id" placeholder="例如 DEV-001" />
          </div>

          <div className="field">
            <label htmlFor="material_batch_id">素材批次ID</label>
            <input id="material_batch_id" name="material_batch_id" placeholder="例如 MAT-20260420-ABC123" />
          </div>

          <div className="field">
            <label htmlFor="plan_publish_time">计划发布时间</label>
            <input id="plan_publish_time" name="plan_publish_time" type="datetime-local" />
          </div>

          <div className="field full">
            <label htmlFor="topics">话题</label>
            <input id="topics" name="topics" placeholder="例如 #潮流穿搭 #今日上新" />
          </div>

          <div className="field full">
            <label htmlFor="content">正文</label>
            <textarea id="content" name="content" placeholder="输入这次发布的正文内容" />
          </div>

          <div className="field full">
            <div className="action-row">
              <button type="submit" className="button highlight" disabled={pending}>
                {pending ? "创建中..." : "创建任务"}
              </button>
              {message ? <span className="inline-message">{message}</span> : null}
            </div>
          </div>
        </form>
      </section>
    </>
  );
}
