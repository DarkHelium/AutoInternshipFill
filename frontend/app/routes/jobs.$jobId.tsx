
import { Form, useLoaderData } from "react-router";
import { API } from "../utils/api.client";
import type { Job, TailorResult } from "../utils/types";

export async function loader({ params }: { params: { jobId?: string } }) {
  const job = await API.getJob(params.jobId!);
  const tailor = await fetch(`${process.env.BACKEND_URL}/jobs/${params.jobId}/tailor/latest`).then(r => r.ok ? r.json() : null) as TailorResult | null;
  return Response.json({ job, tailor });
}

export async function action({ request, params }: { request: Request; params: { jobId?: string } }) {
  const form = await request.formData();
  if (form.get("intent") === "upload-resume") {
    const file = form.get("resume") as File;
    const url = await API.uploadResume(file);
    await fetch(`${process.env.BACKEND_URL}/profile/base-resume`, { method: "PUT", headers: { "Content-Type":"application/json" }, body: JSON.stringify({ url }) });
    return Response.json({ ok: true });
  }
  return Response.json({ ok: true });
}

export default function JobDetail() {
  const { job, tailor } = useLoaderData() as { job: Job; tailor: TailorResult | null };
  return (
    <div className="space-y-6">
      <div className="rounded-xl bg-white p-4 shadow">
        <h2 className="text-xl font-semibold">{job.company} — {job.role}</h2>
        <p className="text-sm text-gray-600">{job.location ?? "Remote/—"}</p>
        <a href={job.applyUrl} target="_blank" rel="noreferrer" className="text-indigo-600 underline text-sm">See posting</a>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-xl bg-white p-4">
          <h3 className="mb-2 font-medium">Upload/Replace Base Resume</h3>
          <Form method="post" encType="multipart/form-data">
            <input type="file" name="resume" accept="application/pdf" required />
            <button className="ml-2 rounded-md bg-gray-900 px-3 py-1.5 text-white" name="intent" value="upload-resume">Save</button>
          </Form>

          <div className="mt-6 space-y-2">
            <Form method="post" action="/jobs">
              <input type="hidden" name="jobId" value={job.id} />
              <button className="rounded-md bg-indigo-600 px-3 py-1.5 text-white" name="intent" value="tailor">Tailor for this job</button>
            </Form>
            <Form method="post" action={`/runs/start-desktop?jobId=${job.id}`}>
              <button className="rounded-md bg-gray-900 px-3 py-1.5 text-white">Tailor (Desktop)</button>
            </Form>
          </div>
        </div>

        <div className="rounded-xl bg-white p-4">
          <h3 className="mb-2 font-medium">Tailored Resume Preview</h3>
          {tailor ? (
            <>
              <p className="mb-2 text-sm text-gray-600">Keywords: {tailor.keywords.join(", ")}</p>
              {tailor.diffHtml ? (
                <div className="prose max-w-none" dangerouslySetInnerHTML={{ __html: tailor.diffHtml }} />
              ) : <p className="text-sm text-gray-500">No diff preview available.</p>}
              {tailor.pdfUrl && (
                <a className="mt-3 inline-block rounded-md bg-emerald-600 px-3 py-1.5 text-white" href={tailor.pdfUrl} target="_blank" rel="noreferrer">Open tailored PDF</a>
              )}
            </>
          ) : <p className="text-sm text-gray-500">Run “Tailor” to generate a preview.</p>}
        </div>
      </div>
    </div>
  );
}


