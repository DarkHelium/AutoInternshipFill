import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router";
import type { RunEvent } from "../utils/types";

export default function RunView() {
  const { runId } = useParams();
  const [events, setEvents] = useState<RunEvent[]>([]);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const es = new EventSource(`/api.events.${runId}`);
    es.onmessage = (e) => {
      try {
        const evt = JSON.parse(e.data) as RunEvent;
        setEvents(prev => [...prev, evt]);
      } catch {}
    };
    es.onerror = () => es.close();
    return () => es.close();
  }, [runId]);

  useEffect(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), [events.length]);

  const lastScreen = [...events].reverse().find(e => e.type === "screenshot") as any;

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <div className="rounded-xl bg-white p-4">
        <h2 className="mb-2 text-lg font-semibold">Live Logs</h2>
        <div className="h-[60vh] overflow-auto rounded border bg-gray-50 p-3 text-sm">
          {events.map((e, i) => (
            <div key={i} className="mb-1">
              {e.type === "log" && <div>[{e.level}] {e.message}</div>}
              {e.type === "gate" && (
                <div className="rounded border border-amber-400 bg-amber-50 p-2">
                  Human action needed: {e.prompt}
                </div>
              )}
              {e.type === "done" && (
                <div className={`rounded p-2 ${e.ok ? "bg-emerald-50" : "bg-rose-50"}`}>
                  {e.ok ? "Run completed ✅" : "Run failed ❌"}{e.receiptUrl && <> — <a className="underline" href={e.receiptUrl} target="_blank" rel="noreferrer">receipt</a></>}
                </div>
              )}
            </div>
          ))}
          <div ref={endRef} />
        </div>
      </div>

      <div className="rounded-xl bg-white p-4">
        <h2 className="mb-2 text-lg font-semibold">Latest Screen</h2>
        {lastScreen?.url ? (
          <img src={lastScreen.url} alt="latest screen" className="h-[60vh] w-full rounded object-contain" />
        ) : (
          <p className="text-sm text-gray-500">Waiting for first screenshot…</p>
        )}
      </div>
    </div>
  );
}


