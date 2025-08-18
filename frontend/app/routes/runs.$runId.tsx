import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router";
import type { RunEvent } from "../utils/types";

export default function RunView() {
  const { runId } = useParams();
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [vncUrl, setVncUrl] = useState<string>("");
  const [jdText, setJdText] = useState<string>("");
  const [jsonInput, setJsonInput] = useState<string>("");
  const [renderResult, setRenderResult] = useState<any>(null);
  const [authGate, setAuthGate] = useState<any>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const es = new EventSource(`/api.events.${runId}`);
    es.onmessage = (e) => {
      try {
        const evt = JSON.parse(e.data) as any;
        setEvents(prev => [...prev, evt]);
        
        // Handle special event types
        if (evt.type === "vnc") {
          setVncUrl(evt.url);
          // Auto-open VNC URL in a new tab for full-screen control as requested
          try {
            if (evt.url) window.open(evt.url, "_blank");
          } catch {}
        } else if (evt.type === "jd") {
          setJdText(evt.text);
        } else if (evt.type === "auth_gate") {
          setAuthGate(evt);
        }
      } catch {}
    };
    es.onerror = () => es.close();
    return () => es.close();
  }, [runId]);

  useEffect(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), [events.length]);

  const copyJD = () => {
    navigator.clipboard.writeText(jdText);
  };

  const continueRun = async () => {
    await fetch(`http://localhost:8000/runs/${runId}/continue`, { method: "POST" });
  };

  const markSignedIn = async () => {
    await fetch(`http://localhost:8000/runs/${runId}/continue`, { method: "POST" });
    setAuthGate(null); // Clear the auth gate
  };

  const renderJSON = async () => {
    try {
      const jobId = events.find(e => e.type === "log")?.message?.match(/job_id:(\w+)/)?.[1] || "unknown";
      const res = await fetch(`http://localhost:8000/jobs/${jobId}/tailor/import-json`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: jsonInput
      });
      const result = await res.json();
      setRenderResult(result);
    } catch (err) {
      alert("Failed to render PDF: " + err);
    }
  };

  const lastScreen = [...events].reverse().find(e => e.type === "screenshot") as any;
  const hasGate = events.some(e => e.type === "gate");

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      {/* Auth Gate - Show prominently when auth is needed */}
      {authGate && (
        <div className="col-span-full rounded-xl bg-amber-50 border border-amber-200 p-6 dark:bg-amber-900/30 dark:border-amber-700">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-amber-800">
                Login Required on {authGate.provider.charAt(0).toUpperCase() + authGate.provider.slice(1)}
              </h2>
              <p className="text-amber-700 mt-2">{authGate.instructions}</p>
              <p className="text-sm text-amber-600 mt-1">URL: {authGate.url}</p>
            </div>
            <button 
              onClick={markSignedIn}
              className="bg-amber-600 text-white px-4 py-2 rounded-lg font-medium transition-colors hover:bg-amber-500 active:bg-amber-700"
            >
              I'm Signed In
            </button>
          </div>
        </div>
      )}

      {/* VNC Desktop */}
      {vncUrl && (
        <div className="rounded-xl bg-white p-4 dark:bg-gray-800 dark:text-gray-100 dark:border dark:border-gray-700">
          <h2 className="mb-2 text-lg font-semibold">Desktop (VNC)</h2>
          <iframe 
            src={vncUrl} 
            className="h-[60vh] w-full rounded border" 
            title="VNC Desktop"
          />
        </div>
      )}

      {/* Live Logs */}
      <div className="rounded-xl bg-white p-4 dark:bg-gray-800 dark:text-gray-100 dark:border dark:border-gray-700">
        <h2 className="mb-2 text-lg font-semibold">Live Logs</h2>
        <div className="h-[60vh] overflow-auto rounded border bg-gray-50 p-3 text-sm dark:bg-gray-900 dark:border-gray-700">
          {events.map((e, i) => (
            <div key={i} className="mb-1">
              {e.type === "log" && <div>[{e.level}] {e.message}</div>}
              {e.type === "gate" && (
                <div className="rounded border border-amber-400 bg-amber-50 p-2 dark:bg-amber-900/30 dark:border-amber-700">
                  Human action needed: {e.prompt}
                  <button 
                    onClick={continueRun}
                    className="ml-2 rounded bg-amber-600 px-2 py-1 text-white text-xs transition-colors hover:bg-amber-500 active:bg-amber-700"
                  >
                    Mark Submitted
                  </button>
                </div>
              )}
              {e.type === "done" && (
                <div className={`rounded p-2 ${e.ok ? "bg-emerald-50 dark:bg-emerald-900/30" : "bg-rose-50 dark:bg-rose-900/30"}`}>
                  {e.ok ? "Run completed ✅" : "Run failed ❌"}{e.receiptUrl && <> — <a className="underline" href={e.receiptUrl} target="_blank" rel="noreferrer">receipt</a></>}
                </div>
              )}
            </div>
          ))}
          <div ref={endRef} />
        </div>
        
        {/* Latest Screenshot */}
        {lastScreen?.url && (
          <div className="mt-4">
            <h3 className="text-sm font-medium mb-2">Latest Screen</h3>
            <img src={lastScreen.url} alt="latest screen" className="w-full rounded border" />
          </div>
        )}
      </div>

      {/* Job Description + JSON Import */}
      <div className="rounded-xl bg-white p-4 space-y-4 dark:bg-gray-800 dark:text-gray-100 dark:border dark:border-gray-700">
        {/* Job Description Panel */}
        {jdText && (
          <div>
            <div className="flex justify-between items-center mb-2">
              <h3 className="text-lg font-semibold">Job Description</h3>
              <button 
                onClick={copyJD}
                className="rounded bg-blue-600 px-2 py-1 text-white text-xs transition-colors hover:bg-blue-500 active:bg-blue-700"
              >
                Copy JD
              </button>
            </div>
            <div className="h-32 overflow-auto rounded border bg-gray-50 p-2 text-xs">
              {jdText}
            </div>
          </div>
        )}

        {/* ChatGPT Prompt */}
        <div>
          <h3 className="text-sm font-semibold mb-2">ChatGPT Prompt</h3>
          <div className="rounded border bg-gray-50 p-2 text-xs dark:bg-gray-900 dark:border-gray-700">
            <strong>Task:</strong> You are an expert ATS resume editor. You'll see a job description (JD) and my resume (attached).<br/>
            <strong>Output:</strong><br/>
            1. keywords: the top 5–10 ATS-friendly keywords/phrases from the JD.<br/>
            2. resume: a strict JSON resume with fields:<br/>
            <pre className="mt-1 text-xs">{`{
  "name": "...", "contact": {"email":"...", "phone":"...", "links":["..."]},
  "summary": "...", "skills": ["..."],
  "experience": [{"company":"...", "title":"...", "start":"YYYY-MM", "end":"YYYY-MM|Present", "bullets":["..."]}],
  "projects": [{"name":"...", "bullets":["..."]}],
  "education": [{"school":"...", "degree":"...", "grad":"YYYY"}]
}`}</pre>
            <strong>Rules:</strong> Keep it factual (no fabrications). Use JD terminology where I actually have experience. Prefer measurable outcomes. One page when rendered. No tables.<br/>
            <strong>Deliver:</strong> Return strict JSON object: {`{"keywords":["..."], "resume": {...}}`}<br/>
            <strong>Here is the JD:</strong> (paste JD text)
          </div>
        </div>

        {/* JSON Import */}
        <div>
          <h3 className="text-sm font-semibold mb-2">Import ChatGPT JSON</h3>
          <textarea
            value={jsonInput}
            onChange={(e) => setJsonInput(e.target.value)}
            placeholder='Paste JSON result from ChatGPT here: {"keywords":["..."], "resume":{...}}'
            className="w-full h-32 rounded border p-2 text-xs font-mono dark:bg-gray-900 dark:border-gray-700"
          />
          <button 
            onClick={renderJSON}
            className="mt-2 rounded bg-emerald-600 px-3 py-1.5 text-white transition-colors hover:bg-emerald-500 active:bg-emerald-700"
            disabled={!jsonInput.trim()}
          >
            Render PDF
          </button>
        </div>

        {/* Render Result */}
        {renderResult && (
          <div className="rounded border border-emerald-200 bg-emerald-50 p-3 dark:bg-emerald-900/30 dark:border-emerald-800">
            <h3 className="text-sm font-semibold text-emerald-800">PDF Generated!</h3>
            <p className="text-xs text-emerald-700 mb-2">Keywords: {renderResult.keywords.join(", ")}</p>
            <a 
              href={`http://localhost:8000${renderResult.pdfUrl}`}
              target="_blank" 
              rel="noreferrer"
              className="inline-block rounded bg-emerald-600 px-2 py-1 text-white text-xs transition-colors hover:bg-emerald-500 active:bg-emerald-700"
            >
              Download PDF
            </a>
          </div>
        )}
      </div>
    </div>
  );
}


