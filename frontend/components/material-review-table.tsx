"use client";

import { useMemo, useState } from "react";

import { FeishuSyncButton } from "@/components/feishu-sync-button";
import { StatusPill } from "@/components/status-pill";
import { TaskActions } from "@/components/task-actions";
import { getMaterialFileName, getMaterialPreviewUrl } from "@/lib/media";
import { MaterialBatch, PublishTask } from "@/lib/types";

function MaterialPreview({ path, alt }: { path?: string | null; alt: string }) {
  const previewUrl = getMaterialPreviewUrl(path);
  const fileName = getMaterialFileName(path);

  if (!path || !previewUrl) {
    return <span className="muted">{path ?? "-"}</span>;
  }

  return (
    <a href={previewUrl} target="_blank" rel="noreferrer" className="media-thumb">
      <span className="media-thumb-frame">
        <img src={previewUrl} alt={alt} />
      </span>
      <span className="media-thumb-name" title={path}>
        {fileName}
      </span>
    </a>
  );
}

interface MaterialReviewTableProps {
  batches: MaterialBatch[];
  tasks: PublishTask[];
}

export function MaterialReviewTable({ batches, tasks }: MaterialReviewTableProps) {
  const [showReviewed, setShowReviewed] = useState(false);
  const taskByBatchId = useMemo(() => new Map(tasks.filter((task) => task.material_batch_id).map((task) => [task.material_batch_id!, task])), [tasks]);

  const pendingBatches = useMemo(
    () =>
      batches.filter((batch) => {
        const task = taskByBatchId.get(batch.batch_id);
        return !task || ["draft", "pending_review"].includes(task.status);
      }),
    [batches, taskByBatchId],
  );

  const reviewedBatches = useMemo(
    () =>
      batches.filter((batch) => {
        const task = taskByBatchId.get(batch.batch_id);
        return Boolean(task) && !["draft", "pending_review"].includes(task!.status);
      }),
    [batches, taskByBatchId],
  );

  const visibleBatches = showReviewed ? reviewedBatches : pendingBatches;

  return (
    <>
      <section className="page-head">
        <div>
          <h2>素材批次</h2>
          <p>默认只显示待审核素材。已审核素材放在单独视图里，需要审核回退时再切进去处理。</p>
        </div>
        <div className="action-row">
          <button className={showReviewed ? "button secondary" : "button highlight"} onClick={() => setShowReviewed(false)}>
            待审核素材 ({pendingBatches.length})
          </button>
          <button className={showReviewed ? "button highlight" : "button secondary"} onClick={() => setShowReviewed(true)}>
            已审核素材 ({reviewedBatches.length})
          </button>
          <FeishuSyncButton />
        </div>
      </section>

      <section className="panel">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>批次ID</th>
                <th>款号</th>
                <th>标题</th>
                <th>正文</th>
                <th>账号设备</th>
                <th>状态</th>
                <th>当前步骤</th>
                <th>操作</th>
                <th>图片1</th>
                <th>图片2</th>
                <th>图片3</th>
                <th>图片4</th>
                <th>封面图</th>
                <th>标签</th>
                <th>创建时间</th>
              </tr>
            </thead>
            <tbody>
              {visibleBatches.map((batch) => {
                const task = taskByBatchId.get(batch.batch_id);

                return (
                  <tr key={batch.batch_id}>
                    <td>
                      <code>{batch.batch_id}</code>
                    </td>
                    <td>{batch.sku_code}</td>
                    <td>
                      <div className="copy-cell">
                        <div className="copy-title">{task?.title ?? "-"}</div>
                      </div>
                    </td>
                    <td>
                      <div className="copy-cell">
                        <div className="copy-body">{task?.content ?? "-"}</div>
                      </div>
                    </td>
                    <td>
                      {task ? (
                        <div className="stacked-meta">
                          <div>{task.account_device?.account_name ?? task.account_id ?? "-"}</div>
                          <div className="muted">{task.account_device?.device_name ?? task.device_id ?? "-"}</div>
                        </div>
                      ) : (
                        <span className="muted">未绑定任务</span>
                      )}
                    </td>
                    <td>{task ? <StatusPill status={task.status} /> : <span className="muted">-</span>}</td>
                    <td>
                      <div className="step-cell">{task?.current_step ?? "-"}</div>
                    </td>
                    <td>{task ? <TaskActions taskId={task.task_id} status={task.status} mode="review" /> : <span className="muted">-</span>}</td>
                    <td>
                      <MaterialPreview path={batch.image_1} alt={`${batch.batch_id} 图片1`} />
                    </td>
                    <td>
                      <MaterialPreview path={batch.image_2} alt={`${batch.batch_id} 图片2`} />
                    </td>
                    <td>
                      <MaterialPreview path={batch.image_3} alt={`${batch.batch_id} 图片3`} />
                    </td>
                    <td>
                      <MaterialPreview path={batch.image_4} alt={`${batch.batch_id} 图片4`} />
                    </td>
                    <td>
                      <MaterialPreview path={batch.cover_image} alt={`${batch.batch_id} 封面图`} />
                    </td>
                    <td>{batch.tags ?? "-"}</td>
                    <td>{new Date(batch.created_at).toLocaleString("zh-CN")}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {visibleBatches.length === 0 ? (
            <div className="empty-state">{showReviewed ? "当前没有已审核素材。需要审核回退时再切回来。" : "当前没有待审核素材。"}</div>
          ) : null}
        </div>
      </section>
    </>
  );
}
