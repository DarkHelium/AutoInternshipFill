
import { Form, useLoaderData } from "react-router";
import { API } from "../utils/api.client";
import type { ApplicantProfile } from "../utils/types";

export async function loader() {
  const profile = await API.profile.get();
  return Response.json({ profile });
}

export async function action({ request }: { request: Request }) {
  const form = await request.formData();
  const profile: ApplicantProfile = JSON.parse(String(form.get("profile")));
  const updated = await API.profile.update(profile);
  return Response.json({ profile: updated });
}

export default function ProfileIndex() {
  const { profile } = useLoaderData<typeof loader>();
  const initial = JSON.stringify(profile, null, 2);

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="rounded-xl bg-white p-4">
        <h2 className="mb-2 text-lg font-semibold">Applicant Profile</h2>
        <Form method="post">
          <textarea name="profile" defaultValue={initial} rows={18}
            className="w-full rounded border p-2 font-mono text-sm" />
          <button className="mt-2 rounded-md bg-gray-900 px-3 py-1.5 text-white">Save</button>
        </Form>
        <p className="mt-2 text-xs text-gray-500">Tip: include eligibility, relocation, and per-company “Why us” snippets.</p>
      </div>

      <div className="rounded-xl bg-white p-4">
        <h2 className="mb-2 text-lg font-semibold">Base Resume</h2>
        <p className="text-sm text-gray-600">Upload in the job page; backend will use it as the source for tailoring.</p>
        <ul className="list-disc pl-5 text-sm text-gray-600">
          <li>Keep fonts standard; no tables</li>
          <li>&lt; 1 MB PDF</li>
        </ul>
      </div>
    </div>
  );
}


