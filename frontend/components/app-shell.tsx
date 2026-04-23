"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { PropsWithChildren } from "react";

const NAV_ITEMS = [
  { href: "/tasks", label: "任务控制台" },
  { href: "/materials", label: "素材批次" },
  { href: "/devices", label: "账号设备" },
  { href: "/logs", label: "运行日志" },
];

export function AppShell({ children }: PropsWithChildren) {
  const pathname = usePathname();

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand-block">
          <p className="eyebrow">DEWU CONSOLE</p>
          <h1>得物自动发布控制台</h1>
          <p className="muted">
            用任务去驱动发布，把素材、账号、设备和执行日志放到一个地方管理。
          </p>
        </div>

        <nav className="nav-list">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname.startsWith(item.href);
            return (
              <Link key={item.href} href={item.href} className={`nav-link ${isActive ? "active" : ""}`}>
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>

      <main className="content-area">{children}</main>
    </div>
  );
}
