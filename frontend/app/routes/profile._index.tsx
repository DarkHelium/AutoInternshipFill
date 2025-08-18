
import { useFetcher, useLoaderData } from "react-router";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import type { ApplicantProfile } from "../utils/types";

// Avoid process.env at module scope (breaks in the browser). Use a browser-safe default here
const BACKEND_BROWSER = "http://localhost:8000";

export async function loader() {
  const BACKEND = (typeof process !== 'undefined' && (process as any).env?.BACKEND_URL) || BACKEND_BROWSER;
  const [profRes, jobsRes] = await Promise.all([
    fetch(`${BACKEND}/profile`),
    fetch(`${BACKEND}/jobs`),
  ]);
  if (!profRes.ok) throw new Response("Failed to load profile", { status: profRes.status });
  if (!jobsRes.ok) throw new Response("Failed to load jobs", { status: jobsRes.status });
  const [profile, jobs] = await Promise.all([profRes.json(), jobsRes.json()]);
  return Response.json({ profile, jobs });
}

export async function action({ request }: { request: Request }) {
  const BACKEND = (typeof process !== 'undefined' && (process as any).env?.BACKEND_URL) || BACKEND_BROWSER;
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
  const { profile, jobs } = useLoaderData() as { profile: any; jobs: any[] };
  const initial = JSON.stringify(profile, null, 2);
  const fetcher = useFetcher<{ profile?: any; error?: string }>();
  const [uploading, setUploading] = useState(false);
  const [resumeVerified, setResumeVerified] = useState<boolean>(Boolean(profile?.base_resume_url));
  const [resumeUrl, setResumeUrl] = useState<string | null>(profile?.base_resume_url || null);
  const [resumeMeta, setResumeMeta] = useState<{ name: string; sizeKb: number } | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<string>("");
  const navigate = useNavigate();

  // Show a toast once when a submission completes (avoid double toasts)
  const prevStateRef = useRef(fetcher.state);
  const prevDataRef = useRef<any>(null);
  useEffect(() => {
    const prevState = prevStateRef.current;
    const sameData = prevDataRef.current === fetcher.data;
    if (prevState !== "idle" && fetcher.state === "idle" && !sameData && fetcher.data) {
      if (fetcher.data.profile) toast.success("Profile saved");
      if (fetcher.data.error) toast.error(fetcher.data.error);
      prevDataRef.current = fetcher.data;
    }
    prevStateRef.current = fetcher.state;
  }, [fetcher.state, fetcher.data]);

  // Verify an existing resume URL by issuing a HEAD request
  useEffect(() => {
    const BACKEND = BACKEND_BROWSER; // browser runtime default
    (async () => {
      if (!resumeUrl) return;
      try {
        const r = await fetch(`${BACKEND}${resumeUrl}`, { method: "HEAD", cache: "no-store" as RequestCache });
        const ct = r.headers.get("content-type") || "";
        setResumeVerified(r.ok && ct.includes("pdf"));
      } catch {
        setResumeVerified(false);
      }
    })();
  }, [resumeUrl]);

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="rounded-xl bg-white p-4 dark:bg-gray-800 dark:text-gray-100">
        <h2 className="mb-2 text-lg font-semibold">Applicant Profile</h2>
        <fetcher.Form method="post">
          <textarea name="profile" defaultValue={initial} rows={18}
            className="w-full rounded border p-2 font-mono text-sm dark:bg-gray-900 dark:border-gray-700" />
                      <button
              type="submit"
              className="mt-2 inline-flex items-center rounded-md bg-blue-600 px-3 py-1.5 text-white cursor-pointer transition-colors hover:bg-blue-500 active:bg-blue-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={fetcher.state !== "idle"}
              aria-busy={fetcher.state !== "idle"}
            aria-live="polite"
          >
            {fetcher.state !== "idle" ? "Saving…" : "Save"}
          </button>
        </fetcher.Form>
        <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">Tip: include eligibility, relocation, and per-company “Why us” snippets.</p>
      </div>

      <div className="rounded-xl bg-white p-4 dark:bg-gray-800 dark:text-gray-100">
        <h2 className="mb-2 text-lg font-semibold">Base Resume</h2>
        <p className="text-sm text-gray-600 dark:text-gray-300">Upload your base resume here; backend will use it as the source for tailoring.</p>
        <ul className="list-disc pl-5 text-sm text-gray-600 dark:text-gray-300">
          <li>Keep fonts standard; no tables</li>
          <li>&lt; 1 MB PDF</li>
        </ul>

        <div className="mt-4 flex items-center gap-3">
          <label className="inline-flex items-center rounded-md bg-indigo-600 px-3 py-1.5 text-white cursor-pointer transition-colors hover:bg-indigo-500">
            <input
              type="file"
              accept="application/pdf"
              className="hidden"
              onChange={async (e) => {
                const file = e.currentTarget.files?.[0];
                if (!file) return;
                setUploading(true);
                try {
                  const presigned = await fetch(`${BACKEND_BROWSER}/uploads/resumeUrl`, { method: "POST" }).then(r => r.json());
                  const putRes = await fetch(`${BACKEND_BROWSER}${presigned.uploadUrl}`, { method: "PUT", body: file });
                  if (!putRes.ok) throw new Error("upload failed");
                  await fetch(`${BACKEND_BROWSER}/profile/base-resume`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ url: presigned.publicUrl })
                  });
                  // Verify and show meta
                  setResumeUrl(presigned.publicUrl);
                  setResumeMeta({ name: file.name, sizeKb: Math.round(file.size / 1024) });
                  toast.success("Base resume uploaded");
                  // HEAD check
                  const head = await fetch(`${BACKEND_BROWSER}${presigned.publicUrl}`, { method: "HEAD", cache: "no-store" as RequestCache });
                  setResumeVerified(head.ok && (head.headers.get("content-type") || "").includes("pdf"));
                } catch (err: any) {
                  toast.error("Upload failed");
                } finally {
                  setUploading(false);
                  e.currentTarget.value = "";
                }
              }}
            />
            {uploading ? "Uploading…" : "Upload PDF"}
          </label>

          {resumeUrl && (
            <a
              className="text-sm underline text-indigo-700 dark:text-indigo-300"
              href={`${BACKEND_BROWSER}${resumeUrl}`}
              target="_blank" rel="noreferrer"
            >
              Open current
            </a>
          )}
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          {resumeVerified ? (
            <span className="inline-flex items-center rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200">Verified PDF</span>
          ) : (
            <span className="inline-flex items-center rounded-full bg-rose-100 px-2.5 py-0.5 text-xs font-medium text-rose-800 dark:bg-rose-900 dark:text-rose-200">No resume</span>
          )}

          {resumeMeta && (
            <span className="text-xs text-gray-600 dark:text-gray-300">{resumeMeta.name} • {resumeMeta.sizeKb} KB</span>
          )}

                      <button
              className="inline-flex items-center rounded-md bg-emerald-600 px-3 py-1.5 text-white cursor-pointer transition-all hover:bg-emerald-500 active:bg-emerald-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={!resumeVerified || uploading || !jobs || jobs.length === 0}
            onClick={async () => {
              try {
                const targetJobId = jobs?.[0]?.id;
                if (!targetJobId) throw new Error('no jobs');
                const res = await fetch(`${BACKEND_BROWSER}/jobs/${targetJobId}/tailor/desktop/start`, { method: "POST" });
                if (!res.ok) throw new Error("start failed");
                const out = await res.json();
                // Redirect user directly to the VNC desktop as requested
                if (out?.vncUrl) {
                  window.location.href = out.vncUrl;
                } else {
                  // Fallback: go to run logs page
                  navigate(`/runs/${out.runId}`);
                }
              } catch {
                toast.error("Failed to start desktop run");
              }
            }}
          >
            Start Desktop Tailor
          </button>
          {(!jobs || jobs.length === 0) && (
            <span className="text-xs text-gray-500 dark:text-gray-400">No jobs detected yet; ensure README source is reachable.</span>
          )}
        </div>
      </div>
    </div>
  );
}


