export async function loader({ params }: { params: { runId?: string } }) {
  const runId = params.runId!;
  const backend = process.env.BACKEND_URL ?? "http://localhost:8000";
  const upstream = await fetch(`${backend}/runs/${runId}/events`, { headers: { Accept: "text/event-stream" } });

  const headers = new Headers({
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
  });

  const stream = new ReadableStream({
    start(controller) {
      const reader = upstream.body!.getReader();
      const pump = (): Promise<void> => reader.read().then(({ done, value }) => {
        if (done) { controller.close(); return; }
        controller.enqueue(value);
        return pump();
      }).catch(err => controller.error(err));
      pump();
    }
  });

  return new Response(stream, { headers });
}


