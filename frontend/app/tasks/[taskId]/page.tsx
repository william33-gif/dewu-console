import Link from "next/link";
import { notFound } from "next/navigation";

import { StatusPill } from "@/components/status-pill";
import { TaskActions } from "@/components/task-actions";
import { API_BASE_URL, getTask } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function TaskDetailPage({ params }: { params: Promise<{ taskId: string }> }) {
  const { taskId } = await params;
  const task = await getTask(taskId);

  if (!task) {
    notFound();
  }

  const images = [
    task.material_batch?.image_1,
    task.material_batch?.image_2,
    task.material_batch?.image_3,
    task.material_batch?.image_4,
  ];
  const resultScreenshotUrl = task.result_screenshot
    ? task.result_screenshot.startsWith("http")
      ? task.result_screenshot
      : `${API_BASE_URL}${task.result_screenshot}`
    : null;

  return (
    <>
      <section className="page-head">
        <div>
          <h2>{task.title}</h2>
          <p>
            任务号 <code>{task.task_id}</code> · 当前状态 <StatusPill status={task.status} />
          </p>
        </div>
        <div className="action-row">
          <Link href="/tasks" className="button secondary">
            返回任务列表
          </Link>
          <TaskActions taskId={task.task_id} status={task.status} />
        </div>
      </section>

      <section className="detail-grid">
        <div className="panel">
          <h3 className="section-title">基本信息</h3>
          <div className="kv-list">
            <div className="kv-item">
              <span>任务ID</span>
              <code>{task.task_id}</code>
            </div>
            <div className="kv-item">
              <span>款号</span>
              <div>{task.sku_code}</div>
            </div>
            <div className="kv-item">
              <span>标题</span>
              <div>{task.title}</div>
            </div>
            <div className="kv-item">
              <span>正文</span>
              <div>{task.content ?? "-"}</div>
            </div>
            <div className="kv-item">
              <span>话题</span>
              <div>{task.topics ?? "-"}</div>
            </div>
          </div>
        </div>

        <div className="panel">
          <h3 className="section-title">执行区</h3>
          <div className="kv-list">
            <div className="kv-item">
              <span>绑定账号</span>
              <div>{task.account_device?.account_name ?? task.account_id ?? "-"}</div>
            </div>
            <div className="kv-item">
              <span>绑定设备</span>
              <div>{task.account_device?.device_name ?? task.device_id ?? "-"}</div>
            </div>
            <div className="kv-item">
              <span>当前步骤</span>
              <div>{task.current_step ?? "-"}</div>
            </div>
            <div className="kv-item">
              <span>开始时间</span>
              <div>{task.execution_started_at ? new Date(task.execution_started_at).toLocaleString("zh-CN") : "-"}</div>
            </div>
            <div className="kv-item">
              <span>结束时间</span>
              <div>{task.execution_finished_at ? new Date(task.execution_finished_at).toLocaleString("zh-CN") : "-"}</div>
            </div>
          </div>
        </div>
      </section>

      <section className="panel" style={{ marginTop: 20 }}>
        <h3 className="section-title">素材区</h3>
        <div className="image-grid">
          {images.map((image, index) => (
            <div key={`${task.task_id}-image-${index + 1}`} className="image-card">
              <div className="image-box">{image ? `图片 ${index + 1}` : `图片 ${index + 1} 未配置`}</div>
              <p className="muted">{image ?? "-"}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="detail-grid" style={{ marginTop: 20 }}>
        <div className="panel">
          <h3 className="section-title">结果区</h3>
          <div className="kv-list">
            <div className="kv-item">
              <span>发布链接</span>
              <div>{task.publish_url ?? "-"}</div>
            </div>
            <div className="kv-item">
              <span>发布截图</span>
              <div>
                {resultScreenshotUrl ? (
                  <a href={resultScreenshotUrl} target="_blank" rel="noreferrer" className="result-shot-frame">
                    <img src={resultScreenshotUrl} alt={`发布截图 ${task.task_id}`} className="result-shot-image" />
                  </a>
                ) : (
                  "-"
                )}
                <div className="result-shot-meta muted">{task.result_screenshot ?? "-"}</div>
              </div>
            </div>
            <div className="kv-item">
              <span>错误日志</span>
              <div>{task.error_message ?? "-"}</div>
            </div>
          </div>
        </div>

        <div className="panel">
          <h3 className="section-title">运行日志</h3>
          <div className="kv-list">
            {task.logs.slice(0, 5).map((log) => (
              <div className="kv-item" key={log.id}>
                <span>
                  {new Date(log.created_at).toLocaleString("zh-CN")} · <StatusPill status={log.result} />
                </span>
                <div>{log.step_name}</div>
                <div className="muted">{log.detail ?? "-"}</div>
              </div>
            ))}
            {task.logs.length === 0 ? <div className="empty-state">还没有运行日志。</div> : null}
          </div>
        </div>
      </section>
    </>
  );
}
