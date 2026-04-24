import { StatusPill } from "@/components/status-pill";
import { getLogs } from "@/lib/api";
import { getResultPreviewUrl, getResultThumbnailUrl } from "@/lib/media";

export const dynamic = "force-dynamic";

export default async function LogsPage() {
  const logs = await getLogs();

  return (
    <>
      <section className="page-head">
        <div>
          <h2>运行日志</h2>
          <p>这里用来排查发布过程里的每一步，也会展示回传的截图反馈。</p>
        </div>
      </section>

      <section className="log-grid">
        {logs.map((log) => {
          const screenshotUrl = getResultPreviewUrl(log.screenshot);
          const screenshotPreviewUrl = getResultThumbnailUrl(log.screenshot) ?? screenshotUrl;

          return (
            <article key={log.id} className="log-card">
              <div className="action-row">
                <StatusPill status={log.result} />
                <span className="mono">{new Date(log.created_at).toLocaleString("zh-CN")}</span>
              </div>
              <h3>{log.step_name}</h3>
              <p className="muted">任务ID：{log.task_id}</p>
              <p>{log.detail ?? "无补充信息"}</p>
              {screenshotUrl && screenshotPreviewUrl ? (
                <a href={screenshotUrl} target="_blank" rel="noreferrer" className="result-shot-frame">
                  <img src={screenshotPreviewUrl} alt={`${log.step_name} screenshot`} className="result-shot-image small" loading="lazy" decoding="async" />
                </a>
              ) : null}
              <p className="muted">截图：{log.screenshot ?? "-"}</p>
            </article>
          );
        })}

        {logs.length === 0 ? <div className="empty-state">还没有运行日志。发布任务后，执行步骤会持续写入这里。</div> : null}
      </section>
    </>
  );
}
