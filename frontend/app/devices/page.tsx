import { StatusPill } from "@/components/status-pill";
import { getAccountDevices } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function DevicesPage() {
  const devices = await getAccountDevices();

  return (
    <>
      <section className="page-head">
        <div>
          <h2>账号设备</h2>
          <p>一号一机最稳。这一页专门看账号、设备、ADB、Appium 和心跳状态。</p>
        </div>
      </section>

      <section className="device-grid">
        {devices.map((device) => (
          <article key={device.device_id} className="panel">
            <h3 className="section-title">{device.account_name}</h3>
            <div className="kv-list">
              <div className="kv-item">
                <span>账号ID</span>
                <code>{device.account_id}</code>
              </div>
              <div className="kv-item">
                <span>设备ID</span>
                <code>{device.device_id}</code>
              </div>
              <div className="kv-item">
                <span>ADB 序列号</span>
                <div>{device.adb_serial ?? "-"}</div>
              </div>
              <div className="kv-item">
                <span>Appium 地址</span>
                <div>{device.appium_url ?? "-"}</div>
              </div>
              <div className="kv-item">
                <span>当前状态</span>
                <StatusPill status={device.status} />
              </div>
              <div className="kv-item">
                <span>最后心跳时间</span>
                <div>{device.last_heartbeat ? new Date(device.last_heartbeat).toLocaleString("zh-CN") : "-"}</div>
              </div>
              <div className="kv-item">
                <span>备注</span>
                <div>{device.remark ?? "-"}</div>
              </div>
            </div>
          </article>
        ))}

        {devices.length === 0 ? <div className="empty-state">还没有账号设备绑定。先把账号和手机绑定起来。</div> : null}
      </section>
    </>
  );
}
