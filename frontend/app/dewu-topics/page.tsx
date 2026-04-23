import { DewuTopicManager } from "@/components/dewu-topic-manager";
import { getDewuTopics } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function DewuTopicsPage() {
  const topics = await getDewuTopics();

  return (
    <>
      <section className="page-head">
        <div>
          <h2>最新得物话题</h2>
          <p>这里使用最简单的维护方式：直接粘贴多行话题，一行一个，保存时会自动拆分并存储。</p>
        </div>
      </section>

      <DewuTopicManager initialTopics={topics} />
    </>
  );
}
