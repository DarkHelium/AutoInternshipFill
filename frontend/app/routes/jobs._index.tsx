import { redirect } from "@remix-run/node";
import { Form, useLoaderData, useNavigation } from "react-router";
import type { Job } from "../utils/types";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function loader() {
  const res = await fetch(`${BACKEND}/jobs`);
  if (!res.ok) throw new Response("Failed to load jobs", { status: res.status });
  const jobs = await res.json();
  return Response.json({ jobs });
}

export async function action({ request }: { request: Request }) {
  const form = await request.formData();
  const intent = String(form.get("intent"));
  const jobId = String(form.get("jobId"));
  const profileId = "default";

  if (intent === "tailor") {
    await fetch(`${BACKEND}/jobs/${jobId}/tailor?profileId=${profileId}`, { method: "POST" });
    return redirect(`/jobs/${jobId}`);
  }
  if (intent === "apply") {
    const out = await fetch(`${BACKEND}/jobs/${jobId}/apply?profileId=${profileId}`, { method: "POST" })
      .then(r => r.json());
    const { runId } = out;
    return redirect(`/runs/${runId}`);
  }
  return Response.json({ ok: true });
}

export default function JobsIndex() {
  const { jobs } = useLoaderData() as { jobs: Job[] };
  const nav = useNavigation();

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-medium">Open Internship Postings</h2>
      <div className="overflow-hidden rounded-xl border bg-white dark:border-gray-700 dark:bg-gray-800">
        <table className="w-full text-sm">
          <thead className="bg-gray-100 text-left dark:bg-gray-700">
            <tr>
              <th className="p-3">Company</th>
              <th className="p-3">Role</th>
              <th className="p-3">Location</th>
              <th className="p-3">Posted</th>
              <th className="p-3">Status</th>
              <th className="p-3"></th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((j: Job) => (
              <tr key={j.id} className="border-t dark:border-gray-700">
                <td className="p-3">{j.company}</td>
                <td className="p-3">
                  <a className="font-medium underline text-indigo-700 dark:text-indigo-300" href={`/jobs/${j.id}`}>{j.role}</a>
                </td>
                <td className="p-3">{j.location ?? "-"}</td>
                <td className="p-3">{j.datePosted?.slice(0,10) ?? "-"}</td>
                <td className="p-3">{j.status}</td>
                <td className="p-3">
                  <Form method="post" className="flex gap-2">
                    <input type="hidden" name="jobId" value={j.id} />
                    <button name="intent" value="tailor" className="rounded-lg bg-indigo-600 px-3 py-1.5 text-white disabled:opacity-50"
                      disabled={nav.state !== "idle"}>Tailor</button>
                    <button name="intent" value="apply" className="rounded-lg bg-emerald-600 px-3 py-1.5 text-white disabled:opacity-50"
                      disabled={nav.state !== "idle"}>Apply</button>
                  </Form>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}


