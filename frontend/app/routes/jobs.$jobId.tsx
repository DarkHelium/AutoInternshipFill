import { useLoaderData, useNavigation, useFetcher, Form, useNavigate } from "react-router";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function loader({ params }: { params: { jobId?: string } }) {
  const [jobRes, profRes, latestTailor] = await Promise.all([
    fetch(`${BACKEND}/jobs/${params.jobId}`),
    fetch(`${BACKEND}/profile`),
    fetch(`${BACKEND}/jobs/${params.jobId}/tailor/latest`)
  ]);
  if (!jobRes.ok) throw new Response("job not found", { status: 404 });
  const job = await jobRes.json();
  const profile = await profRes.json();
  const tailor = latestTailor.ok ? await latestTailor.json() : null;
  return Response.json({ job, profile, tailor });
}

// One action that can: (a) start desktop directly, or (b) upload then start
export async function action({ request, params }: { request: Request; params: { jobId?: string } }) {
  const form = await request.formData();
  const intent = String(form.get("intent") || "");
  const jobId = params.jobId!;
  const file = form.get("resume") as File | null;

  // Helper: upload PDF to backend and set as base resume
  async function uploadAndSet(file: File) {
    // 1) ask backend for an upload URL
    const presigned = await fetch(`${BACKEND}/uploads/resumeUrl`, { method: "POST" }).then(r => r.json());
    // 2) stream the file bytes to the upload URL (PUT)
    const buf = Buffer.from(await file.arrayBuffer()); // Blob/File → ArrayBuffer → Buffer (node)
    await fetch(`${BACKEND}${presigned.uploadUrl}`, { method: "PUT", body: buf });
    // 3) tell backend to use this as base resume
    await fetch(`${BACKEND}/profile/base-resume`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: presigned.publicUrl })
    });
    return presigned.publicUrl as string;
  }

  // Start a desktop tailoring run and return runId (don't navigate here;
  // fetcher submits won't follow redirects)
  async function startDesktop() {
    const res = await fetch(`${BACKEND}/jobs/${jobId}/tailor/desktop/start`, { method: "POST" });
    if (!res.ok) throw new Response("Failed to start desktop", { status: 500 });
    return res.json() as Promise<{ runId: string }>;
  }

  if (intent === "start-desktop") {
    // direct start (assumes a PDF already exists; backend will re-validate)
    const out = await startDesktop();
    // Return JSON: the client can navigate programmatically
    return Response.json(out);
  }

  if (intent === "upload-then-start") {
    if (!file) return Response.json({ error: "Please choose a PDF." }, { status: 400 });
    // (client side `accept="application/pdf"` helps; backend still validates)
    await uploadAndSet(file);
    const out = await startDesktop();
    return Response.json(out);
  }

  return Response.json({ ok: true });
}

export default function JobDetail() {
  const { job, profile, tailor } = useLoaderData() as { job: any; profile: any; tailor: any };
  const nav = useNavigation();
  const navigate = useNavigate();
  const fetcher = useFetcher<{ runId?: string; error?: string }>();

  // After action returns { runId }, programmatically navigate to /runs/:runId
  if (fetcher.data?.runId) {
    navigate(`/runs/${fetcher.data.runId}`);
  }

  const hasPdf = Boolean(profile.base_resume_url);

  return (
    <div className="space-y-6">
      <div className="rounded-xl bg-white p-4 shadow">
        <h2 className="text-xl font-semibold">{job.company} — {job.role}</h2>
        <p className="text-sm text-gray-600">{job.location ?? "Remote/—"}</p>
        <a href={job.apply_url} target="_blank" rel="noreferrer" className="text-indigo-600 underline text-sm">See posting</a>
      </div>

      <div className="rounded-xl bg-white p-4">
        <h3 className="mb-3 font-medium">Tailor (Desktop)</h3>

        {hasPdf ? (
          // Case A: we already have a base resume → just start the desktop run
          <fetcher.Form method="post">
            <input type="hidden" name="intent" value="start-desktop" />
            <button
              className="rounded-md bg-gray-900 px-3 py-1.5 text-white disabled:opacity-50"
              disabled={nav.state !== "idle" || fetcher.state !== "idle"}
            >
              Start Desktop Tailor
            </button>
          </fetcher.Form>
        ) : (
          // Case B: no resume yet → show inline uploader that uploads then starts
          <fetcher.Form method="post" encType="multipart/form-data" className="flex items-center gap-3">
            <input
              type="hidden" name="intent" value="upload-then-start"
            />
            <input
              type="file" name="resume" accept="application/pdf" required
              className="block w-full text-sm"
            />
            <button
              className="rounded-md bg-gray-900 px-3 py-1.5 text-white disabled:opacity-50"
              disabled={fetcher.state !== "idle"}
            >
              Upload PDF & Start
            </button>
          </fetcher.Form>
        )}

        {fetcher.data?.error && (
          <p className="mt-2 text-sm text-rose-600">{fetcher.data.error}</p>
        )}
      </div>

      <div className="rounded-xl bg-white p-4">
        <h3 className="mb-2 font-medium">Tailored Resume Preview</h3>
        {tailor ? (
          <>
            <p className="mb-2 text-sm text-gray-600">Keywords: {tailor.keywords?.join(", ")}</p>
            {tailor.diffHtml ? (
              <div className="prose max-w-none" dangerouslySetInnerHTML={{ __html: tailor.diffHtml }} />
            ) : <p className="text-sm text-gray-500">No diff preview available.</p>}
            {tailor.pdfUrl && (
              <a className="mt-3 inline-block rounded-md bg-emerald-600 px-3 py-1.5 text-white" href={tailor.pdfUrl} target="_blank" rel="noreferrer">Open tailored PDF</a>
            )}
          </>
        ) : <p className="text-sm text-gray-500">Run "Tailor (Desktop)" to generate a PDF.</p>}
      </div>
    </div>
  );
}