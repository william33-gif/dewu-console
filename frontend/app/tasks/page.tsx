import { TaskConsoleTable } from "@/components/task-console-table";
import { getMaterialBatches, getTasks } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function TasksPage() {
  const [tasks, materialBatches] = await Promise.all([getTasks(), getMaterialBatches()]);
  const controllerTasks = tasks.filter((task) => !["draft", "pending_review"].includes(task.status));

  return <TaskConsoleTable tasks={controllerTasks} materialBatches={materialBatches} />;
}
