"use client";
import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export default function Home() {
  const [jobUrl, setJobUrl] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [profile, setProfile] = useState({
    name: "",
    email: "",
    phone: "",
    school: "",
    grad_date: "",
    links: { github: "", linkedin: "", portfolio: "" },
    skills: [],
  });

  const setField = (k, v) => setProfile((p) => ({ ...p, [k]: v }));

  const onSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_url: jobUrl, profile }),
      });
      if (!res.ok) throw new Error(`Failed: ${res.status}`);
      const data = await res.json();
      const runId = data.id;
      const url = new URL(jobUrl);
      url.searchParams.set("autofill", "1");
      url.searchParams.set("runId", runId);
      window.open(url.toString(), "_blank");
    } catch (err) {
      setError(err?.message || "Failed to start run");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-3xl mx-auto px-4 py-10">
        <div className="mb-8">
          <h1 className="text-2xl font-bold">AutoInternshipFill — Paste a job link</h1>
          <p className="text-gray-600 mt-1">
            We’ll open the job in a new tab and your extension will autofill
            using your details.
          </p>
        </div>

        <form
          onSubmit={onSubmit}
          className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-6"
        >
          <div>
            <label className="block text-sm font-medium mb-1">Job Link</label>
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-gray-800"
              placeholder="https://company.greenhouse.io/..."
              value={jobUrl}
              onChange={(e) => setJobUrl(e.target.value)}
              required
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Name</label>
              <input
                className="w-full border border-gray-300 rounded-lg px-3 py-2"
                value={profile.name}
                onChange={(e) => setField("name", e.target.value)}
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Email</label>
              <input
                type="email"
                className="w-full border border-gray-300 rounded-lg px-3 py-2"
                value={profile.email}
                onChange={(e) => setField("email", e.target.value)}
                required
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Phone</label>
              <input
                className="w-full border border-gray-300 rounded-lg px-3 py-2"
                value={profile.phone}
                onChange={(e) => setField("phone", e.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">School</label>
              <input
                className="w-full border border-gray-300 rounded-lg px-3 py-2"
                value={profile.school}
                onChange={(e) => setField("school", e.target.value)}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">
                Graduation Date
              </label>
              <input
                className="w-full border border-gray-300 rounded-lg px-3 py-2"
                placeholder="2026"
                value={profile.grad_date}
                onChange={(e) => setField("grad_date", e.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">
                Skills (comma separated)
              </label>
              <input
                className="w-full border border-gray-300 rounded-lg px-3 py-2"
                placeholder="python, react, sql"
                onChange={(e) =>
                  setField(
                    "skills",
                    e.target.value
                      .split(",")
                      .map((s) => s.trim())
                      .filter(Boolean)
                  )
                }
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">LinkedIn</label>
              <input
                className="w-full border border-gray-300 rounded-lg px-3 py-2"
                value={profile.links?.linkedin || ""}
                onChange={(e) =>
                  setField("links", { ...profile.links, linkedin: e.target.value })
                }
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">GitHub</label>
              <input
                className="w-full border border-gray-300 rounded-lg px-3 py-2"
                value={profile.links?.github || ""}
                onChange={(e) =>
                  setField("links", { ...profile.links, github: e.target.value })
                }
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Portfolio</label>
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-2"
              value={profile.links?.portfolio || ""}
              onChange={(e) =>
                setField("links", { ...profile.links, portfolio: e.target.value })
              }
            />
          </div>

          {error && <div className="text-red-600 text-sm">{error}</div>}

          <div>
            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center px-4 py-2 rounded-lg bg-gray-900 text-white hover:bg-gray-800 disabled:opacity-50"
            >
              {saving ? "Starting…" : "Open and Autofill"}
            </button>
          </div>
        </form>

        <p className="text-gray-500 text-sm mt-4">
          Make sure the Chrome extension is loaded and has host permissions.
        </p>
      </div>
    </div>
  );
}
