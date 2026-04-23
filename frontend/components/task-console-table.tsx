"use client";

import Link from "next/link";
import { useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { FeishuSyncButton } from "@/components/feishu-sync-button";
import { StatusPill } from "@/components/status-pill";
import { TaskActions } from "@/components/task-actions";
import { API_BASE_URL } from "@/lib/api";
import { getMaterialPreviewUrl } from "@/lib/media";
import { MaterialBatch, PublishTask } from "@/lib/types";

function TaskPreview({ path, alt }: { path?: string | null; alt: string }) {
  const previewUrl = getMaterialPreviewUrl(path);

  if (!previewUrl) {
    return <span className="muted">-</span>;
  }

  return (
    <a href={previewUrl} target="_blank" rel="noreferrer" className="task-preview" title="查看大图">
      <img src={previewUrl} alt={alt} />
    </a>
  );
}

async function postBatchPublish(taskIds: string[]) {
  const response = await fetch(`${API_BASE_URL}/api/tasks/batch/publish`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ task_ids: taskIds }),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || "批量发布失败");
  }

  return (await response.json()) as { message?: string };
}

interface TaskConsoleTableProps {
  tasks: PublishTask[];
  materialBatches: MaterialBatch[];
}

export function TaskConsoleTable({ tasks, materialBatches }: TaskConsoleTableProps) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [message, setMessage] = useState("");
  const [selectedTaskIds, setSelectedTaskIds] = useState<string[]>([]);
  const [showPublished, setShowPublished] = useState(false);

  const materialByBatchId = useMemo(() => new Map(materialBatches.map((batch) => [batch.batch_id, batch])), [materialBatches]);
  const publishedCount = tasks.filter((task) => task.status === "published").length;
  const runningCount = tasks.filter((task) => task.status === "publishing").length;
  const failedCount = tasks.filter((task) => task.status === "failed").length;
  const visibleTasks = useMemo(
    () => tasks.filter((task) => (showPublished ? task.status === "published" : task.status !== "published")),
    [showPublished, tasks],
  );
  const readyTaskIds = useMemo(() => visibleTasks.filter((task) => task.status === "ready").map((task) => task.task_id), [visibleTasks]);

  const allReadySelected = readyTaskIds.length > 0 && readyTaskIds.every((taskId) => selectedTaskIds.includes(taskId));
  const selectedReadyTaskIds = selectedTaskIds.filter((taskId) => readyTaskIds.includes(taskId));

  const toggleTask = (taskId: string) => {
    setSelectedTaskIds((current) => (current.includes(taskId) ? current.filter((value) => value !== taskId) : [...current, taskId]));
  };

  const toggleAllReady = () => {
    setSelectedTaskIds((current) => (allReadySelected ? current.filter((taskId) => !readyTaskIds.includes(taskId)) : [...new Set([...current, ...readyTaskIds])]));
  };

  const runBatchPublish = () => {
    if (selectedReadyTaskIds.length === 0) {
      setMessage("请先选择待发布任务。");
      return;
    }

    startTransition(() => {
      void (async () => {
        try {
          const payload = await postBatchPublish(selectedReadyTaskIds);
          setMessage(payload.message || `已加入批量发布队列：${selectedReadyTaskIds.length} 条任务。`);
          setSelectedTaskIds([]);
          router.refresh();
        } catch (error) {
          setMessage(error instanceof Error ? error.message : "批量发布失败");
        }
      })();
    });
  };

  return (
    <>
      <section className="page-head">
        <div>
          <h2>任务列表</h2>
          <p>默认只显示未发布任务。已发布任务放在单独视图里，需要回退时再切进去处理。</p>
        </div>
        <div className="action-row">
          <button className={showPublished ? "button secondary" : "button highlight"} disabled={pending} onClick={() => setShowPublished(false)}>
            未发布任务
          </button>
          <button className={showPublished ? "button highlight" : "button secondary"} disabled={pending} onClick={() => setShowPublished(true)}>
            已发布任务 ({publishedCount})
          </button>
          <FeishuSyncButton />
          <button className="button" disabled={pending || showPublished || selectedReadyTaskIds.length === 0} onClick={runBatchPublish}>
            批量发布{selectedReadyTaskIds.length > 0 ? ` (${selectedReadyTaskIds.length})` : ""}
          </button>
          <Link href="/tasks/new" className="button highlight">
            新建任务
          </Link>
        </div>
      </section>

      <section className="hero-grid">
        <div className="stat-card">
          <span className="muted">任务总数</span>
          <strong>{tasks.length}</strong>
        </div>
        <div className="stat-card">
          <span className="muted">发布中</span>
          <strong>{runningCount}</strong>
        </div>
        <div className="stat-card">
          <span className="muted">已发布 / 失败</span>
          <strong>
            {publishedCount} / {failedCount}
          </strong>
        </div>
      </section>

      {message ? <p className="toolbar-message">{message}</p> : null}

      <section className="panel">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th className="selection-cell">
                  <input
                    type="checkbox"
                    checked={allReadySelected}
                    onChange={toggleAllReady}
                    disabled={showPublished || readyTaskIds.length === 0 || pending}
                    aria-label="全选待发布任务"
                  />
                </th>
                <th>任务ID</th>
                <th>款号</th>
                <th>预览</th>
                <th>标题</th>
                <th>账号</th>
                <th>设备</th>
                <th>状态</th>
                <th>计划发布时间</th>
                <th>实际发布时间</th>
                <th>错误信息</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {visibleTasks.map((task) => {
                const material = task.material_batch_id ? materialByBatchId.get(task.material_batch_id) : null;
                const selectable = task.status === "ready";

                return (
                  <tr key={task.task_id}>
                    <td className="selection-cell">
                      <input
                        type="checkbox"
                        checked={selectedTaskIds.includes(task.task_id)}
                        onChange={() => toggleTask(task.task_id)}
                        disabled={showPublished || !selectable || pending}
                        aria-label={`选择任务 ${task.task_id}`}
                      />
                    </td>
                    <td>
                      <code>{task.task_id}</code>
                    </td>
                    <td>{task.sku_code}</td>
                    <td>
                      <TaskPreview path={material?.cover_image ?? material?.image_1} alt={`${task.task_id} 预览图`} />
                    </td>
                    <td>{task.title}</td>
                    <td>{task.account_device?.account_name ?? task.account_id ?? "-"}</td>
                    <td>{task.account_device?.device_name ?? task.device_id ?? "-"}</td>
                    <td>
                      <StatusPill status={task.status} />
                    </td>
                    <td>{task.plan_publish_time ? new Date(task.plan_publish_time).toLocaleString("zh-CN") : "-"}</td>
                    <td>{task.actual_publish_time ? new Date(task.actual_publish_time).toLocaleString("zh-CN") : "-"}</td>
                    <td>{task.error_message ?? "-"}</td>
                    <td>
                      <TaskActions taskId={task.task_id} status={task.status} mode="console" />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {visibleTasks.length === 0 ? (
            <div className="empty-state">{showPublished ? "当前没有已发布任务。需要回退时再来这里看。" : "当前没有待处理任务。先去素材批次页完成人工审核。"}</div>
          ) : null}
        </div>
      </section>
    </>
  );
}
