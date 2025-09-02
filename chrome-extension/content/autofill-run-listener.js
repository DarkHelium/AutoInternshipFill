// Listens for ?autofill=1&runId=... in URL, fetches payload, and triggers filling
(function () {
  const params = new URLSearchParams(window.location.search);
  const shouldAutofill = params.get('autofill') === '1';
  const runId = params.get('runId');
  const API_BASE = 'http://localhost:8000';

  async function run() {
    if (!shouldAutofill || !runId) return;
    try {
      // Give page a moment to render dynamic forms
      await new Promise(r => setTimeout(r, 1500));
      const res = await fetch(`${API_BASE}/runs/${runId}/payload`);
      if (!res.ok) throw new Error(`Payload fetch failed: ${res.status}`);
      const payload = await res.json();

      // Prefer calling into the already-injected formFiller instance
      if (window.formFiller && typeof window.formFiller.fillForm === 'function') {
        await window.formFiller.fillForm(payload);
      } else {
        // Fallback via runtime message to same tab
        chrome.runtime.sendMessage({ action: 'fillWithPayload', data: payload }, (resp) => {
          // no-op; errors are logged by content script
        });
      }
    } catch (e) {
      console.error('Autofill run failed:', e);
    }
  }

  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    run();
  } else {
    window.addEventListener('DOMContentLoaded', run);
  }
})();

