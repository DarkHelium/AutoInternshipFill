import type { ApplicantProfile, Job, TailorResult } from "./types";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const base = process.env.BACKEND_URL ?? "http://localhost:8000";
  const res = await fetch(`${base}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const API = {
  listJobs: () => api<Job[]>("/jobs"),
  getJob: (id: string) => api<Job>(`/jobs/${id}`),
  tailor: (jobId: string, profileId: string) =>
    api<TailorResult>(`/jobs/${jobId}/tailor?profileId=${profileId}`, { method: "POST" }),
  apply: (jobId: string, profileId: string) =>
    api<{ runId: string }>(`/jobs/${jobId}/apply?profileId=${profileId}`, { method: "POST" }),
  profile: {
    get: () => api<ApplicantProfile>("/profile"),
    update: (p: ApplicantProfile) => api<ApplicantProfile>("/profile", { method: "PUT", body: JSON.stringify(p) }),
  },
  uploadResume: async (file: File) => {
    const presigned = await api<{ uploadUrl: string; publicUrl: string }>("/uploads/resumeUrl", { method: "POST" });
    await fetch(presigned.uploadUrl, { method: "PUT", body: file });
    return presigned.publicUrl;
  },
};


