
import { Form, useLoaderData } from "react-router";
import type { ApplicantProfile } from "../utils/types";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function loader() {
  const res = await fetch(`${BACKEND}/profile`);
  if (!res.ok) throw new Response("Failed to load profile", { status: res.status });
  const profile = await res.json();
  return Response.json({ profile });
}

export async function action({ request }: { request: Request }) {
  const form = await request.formData();
  const profile: ApplicantProfile = JSON.parse(String(form.get("profile")));
  const res = await fetch(`${BACKEND}/profile`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile),
  });
  if (!res.ok) throw new Response("Failed to update profile", { status: res.status });
  const updated = await res.json();
  return Response.json({ profile: updated });
}

export default function ProfileIndex() {
  const { profile } = useLoaderData() as { profile: any };
  const initial = JSON.stringify(profile, null, 2);

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="rounded-xl bg-white p-4 dark:bg-gray-800 dark:text-gray-100">
        <h2 className="mb-2 text-lg font-semibold">Applicant Profile</h2>
        <Form method="post">
          <textarea name="profile" defaultValue={initial} rows={18}
            className="w-full rounded border p-2 font-mono text-sm dark:bg-gray-900 dark:border-gray-700" />
          <button className="mt-2 rounded-md bg-gray-900 px-3 py-1.5 text-white">Save</button>
        </Form>
        <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">Tip: include eligibility, relocation, and per-company “Why us” snippets.</p>
      </div>

      <div className="rounded-xl bg-white p-4 dark:bg-gray-800 dark:text-gray-100">
        <h2 className="mb-2 text-lg font-semibold">Base Resume</h2>
        <p className="text-sm text-gray-600 dark:text-gray-300">Upload in the job page; backend will use it as the source for tailoring.</p>
        <ul className="list-disc pl-5 text-sm text-gray-600 dark:text-gray-300">
          <li>Keep fonts standard; no tables</li>
          <li>&lt; 1 MB PDF</li>
        </ul>
      </div>
    </div>
  );
}


