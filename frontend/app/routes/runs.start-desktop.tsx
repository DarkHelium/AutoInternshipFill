import { redirect } from "@remix-run/node";

export async function action({ request }: { request: Request }) {
  const form = await request.formData();
  const jobId = String(form.get("jobId") || new URL(request.url).searchParams.get("jobId"));
  const base = process.env.BACKEND_URL || "http://localhost:8000";
  const res = await fetch(`${base}/jobs/${jobId}/tailor/desktop/start`, { method: "POST" });
  const { runId } = await res.json();
  return redirect(`/runs/${runId}`);
}

export default function () { 
  return null; 
}
