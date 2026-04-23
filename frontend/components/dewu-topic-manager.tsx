"use client";

import { API_BASE_URL } from "@/lib/api";
import { DewuTopic } from "@/lib/types";
import { FormEvent, useMemo, useState } from "react";

function topicsToText(topics: DewuTopic[]): string {
  return topics.map((topic) => topic.topic_text).join("\n");
}

function splitTopicLines(rawText: string): string[] {
  const seen = new Set<string>();
  const topics: string[] = [];

  for (const line of rawText.replace(/\r/g, "\n").split("\n")) {
    const topic = line.trim();
    if (!topic || seen.has(topic)) {
      continue;
    }
    seen.add(topic);
    topics.push(topic);
  }

  return topics;
}

export function DewuTopicManager({ initialTopics }: { initialTopics: DewuTopic[] }) {
  const [topics, setTopics] = useState(initialTopics);
  const [rawText, setRawText] = useState(topicsToText(initialTopics));
  const [message, setMessage] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const previewTopics = useMemo(() => splitTopicLines(rawText), [rawText]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSaving(true);
    setMessage("");

    try {
      const response = await fetch(`${API_BASE_URL}/api/dewu-topics/bulk`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_text: rawText }),
      });

      const payload = await response.json().catch(() => []);
      if (!response.ok) {
        const detail =
          payload && typeof payload === "object" && "detail" in payload ? String(payload.detail) : "保存话题失败。";
        throw new Error(detail);
      }

      const nextTopics = payload as DewuTopic[];
      setTopics(nextTopics);
      setRawText(topicsToText(nextTopics));
      setMessage(`已保存 ${nextTopics.length} 条话题。`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存话题失败。");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="topic-layout">
      <section className="panel">
        <h3 className="section-title">批量粘贴话题</h3>
        <p className="muted topic-helper">
          你可以直接按换行粘贴，例如每行一个 <code>#A</code>、<code>#B</code>、<code>#C</code>。保存时会自动按换行拆分、去重并存储。
        </p>

        <form className="topic-form" onSubmit={handleSubmit}>
          <label className="field full">
            <span>话题文本</span>
            <textarea
              rows={14}
              value={rawText}
              onChange={(event) => setRawText(event.target.value)}
              placeholder={"#A\n#B\n#C\n#D"}
            />
          </label>

          <div className="action-row">
            <button className="button highlight" type="submit" disabled={isSaving}>
              {isSaving ? "保存中..." : "保存话题"}
            </button>
            <span className="toolbar-message">当前识别 {previewTopics.length} 条话题</span>
            {message ? <span className="toolbar-message">{message}</span> : null}
          </div>
        </form>
      </section>

      <section className="panel">
        <h3 className="section-title">当前预览</h3>
        {previewTopics.length === 0 ? (
          <div className="empty-state">还没有粘贴任何话题。</div>
        ) : (
          <div className="topic-preview-list">
            {previewTopics.map((topic, index) => (
              <div key={`${topic}-${index}`} className="topic-preview-chip">
                <span className="mono">{String(index + 1).padStart(2, "0")}</span>
                <strong>{topic}</strong>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="panel">
        <h3 className="section-title">已存储话题</h3>
        {topics.length === 0 ? (
          <div className="empty-state">当前数据库里还没有任何得物话题。</div>
        ) : (
          <div className="topic-preview-list">
            {topics.map((topic) => (
              <div key={topic.id} className="topic-preview-chip stored">
                <span className="mono">{String(topic.id).padStart(2, "0")}</span>
                <strong>{topic.topic_text}</strong>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
