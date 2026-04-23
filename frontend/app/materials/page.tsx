import { MaterialReviewTable } from "@/components/material-review-table";
import { getMaterialBatches, getTasks } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function MaterialsPage() {
  const [batches, tasks] = await Promise.all([getMaterialBatches(), getTasks()]);
  return <MaterialReviewTable batches={batches} tasks={tasks} />;
}
