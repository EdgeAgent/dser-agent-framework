"""Dependency-free local browser demo for DSER."""

from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
import webbrowser

from .local import demo_payloads, run_local_decision


PAGE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DSER Local Lab</title>
  <style>
    :root { --bg:#0b1020; --panel:#111a32; --panel2:#152242; --line:#293a63; --ink:#e8efff; --muted:#9fb0d8; --blue:#67a3ff; --teal:#46d7c5; --amber:#ffc667; --red:#ff8297; --violet:#b59cff; }
    * { box-sizing: border-box; }
    body { margin:0; min-height:100vh; color:var(--ink); background:radial-gradient(circle at 12% 8%, #1c2d58 0, transparent 30rem), radial-gradient(circle at 88% 12%, #153e45 0, transparent 27rem), var(--bg); font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    main { max-width:1200px; margin:0 auto; padding:42px 24px 64px; }
    .eyebrow { color:var(--teal); text-transform:uppercase; letter-spacing:.16em; font-size:.73rem; font-weight:800; }
    h1 { font-size:clamp(2.1rem, 5vw, 3.8rem); margin:.35rem 0 .8rem; letter-spacing:-.055em; }
    .lede { max-width:760px; color:var(--muted); line-height:1.65; font-size:1.08rem; }
    .pill { display:inline-flex; align-items:center; gap:.45rem; padding:.35rem .65rem; margin:.35rem .4rem .2rem 0; border:1px solid var(--line); background:#101a35aa; color:var(--muted); border-radius:999px; font-size:.78rem; }
    .dot { width:.5rem; height:.5rem; border-radius:50%; background:var(--teal); box-shadow:0 0 16px var(--teal); }
    .scenario-row { display:flex; flex-wrap:wrap; gap:10px; margin:28px 0 20px; }
    button { border:1px solid var(--line); color:var(--ink); background:#18274d; border-radius:10px; padding:.68rem .9rem; font-weight:750; cursor:pointer; transition:transform .16s, background .16s, border .16s; }
    button:hover { transform:translateY(-1px); background:#223669; border-color:#5272bb; }
    button.primary { color:#061523; background:linear-gradient(135deg, var(--teal), #78a8ff); border:none; padding:.82rem 1.1rem; }
    button.primary:hover { background:linear-gradient(135deg, #6cf2df, #91baff); }
    .grid { display:grid; grid-template-columns:minmax(0, 1.15fr) minmax(360px, .85fr); gap:20px; align-items:start; }
    .card { background:linear-gradient(145deg, #15213fdd, #0e1730e8); border:1px solid var(--line); border-radius:18px; box-shadow:0 22px 50px #02071466; overflow:hidden; }
    .card-head { padding:17px 20px; border-bottom:1px solid var(--line); display:flex; align-items:center; justify-content:space-between; gap:10px; }
    .card-head h2 { margin:0; font-size:1rem; letter-spacing:.01em; }
    .badge { font-size:.68rem; color:var(--teal); border:1px solid #247b78; border-radius:999px; padding:.2rem .45rem; }
    form { padding:20px; }
    fieldset { border:0; padding:0; margin:0 0 22px; }
    legend { color:var(--blue); font-size:.76rem; letter-spacing:.12em; text-transform:uppercase; font-weight:800; padding:0 0 10px; }
    .fields { display:grid; grid-template-columns:repeat(2, minmax(0,1fr)); gap:12px; }
    .wide { grid-column:1 / -1; }
    label { display:block; color:var(--muted); font-size:.78rem; font-weight:700; }
    input, select, textarea { width:100%; margin-top:6px; border:1px solid #344a7c; border-radius:9px; color:var(--ink); background:#0c1530; padding:.7rem .72rem; font:inherit; outline:none; }
    input:focus, select:focus { border-color:var(--teal); box-shadow:0 0 0 3px #46d7c51a; }
    .checks { display:flex; flex-wrap:wrap; gap:14px; margin:5px 0 18px; }
    .checks label { display:flex; gap:7px; align-items:center; color:var(--ink); font-size:.83rem; }
    .checks input { width:auto; margin:0; accent-color:var(--teal); }
    .hint { color:var(--muted); font-size:.75rem; line-height:1.45; margin:8px 0 0; }
    #output { padding:20px; min-height:610px; }
    .empty { color:var(--muted); border:1px dashed #3a4c78; border-radius:12px; padding:26px; line-height:1.6; }
    .status { display:inline-block; border-radius:999px; padding:.35rem .72rem; font-size:.75rem; letter-spacing:.07em; font-weight:900; }
    .act { background:#0c4f49; color:#71f7e3; } .plan { background:#55410c; color:#ffe28a; } .verify { background:#3f285c; color:#d7c3ff; } .ask { background:#5b2636; color:#ffb7c5; } .defer { background:#263553; color:#b7ccff; }
    .decision-title { display:flex; gap:12px; align-items:center; flex-wrap:wrap; margin-bottom:14px; }
    .reason { color:var(--muted); line-height:1.58; margin:0 0 18px; }
    .metric-grid { display:grid; grid-template-columns:repeat(2, 1fr); gap:10px; margin-bottom:18px; }
    .metric { background:#0c1530; border:1px solid #2b3b64; border-radius:11px; padding:11px; }
    .metric span { display:block; color:var(--muted); font-size:.7rem; text-transform:uppercase; letter-spacing:.08em; } .metric strong { display:block; margin-top:5px; font-size:.98rem; word-break:break-word; }
    .trace { margin-top:17px; border-top:1px solid var(--line); padding-top:16px; }
    .trace h3 { font-size:.78rem; letter-spacing:.1em; color:var(--blue); text-transform:uppercase; margin:0 0 10px; }
    .claim { background:#0b1430; border-left:3px solid var(--blue); padding:10px 11px; border-radius:0 8px 8px 0; margin:8px 0; }
    .claim strong { font-size:.87rem; } .claim small { display:block; color:var(--muted); margin-top:4px; line-height:1.4; }
    .error { color:#ffc0cc; background:#4f1f31; padding:13px; border-radius:10px; line-height:1.5; }
    .footer { color:#7990c0; margin-top:18px; font-size:.75rem; line-height:1.55; }
    @media (max-width:900px) { .grid { grid-template-columns:1fr; } #output { min-height:auto; } }
    @media (max-width:540px) { main { padding:28px 15px; } .fields, .metric-grid { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <main>
    <div class="eyebrow">Local interactive demo</div>
    <h1>DSER Local Lab</h1>
    <p class="lede">Change the evidence, risk, memory, and verification settings. DSER will show whether an agent should <strong>act, plan, verify, ask,</strong> or <strong>defer</strong>—and why.</p>
    <span class="pill"><span class="dot"></span>Runs entirely on 127.0.0.1</span><span class="pill">No API key</span><span class="pill">No external action</span>
    <div class="scenario-row">
      <button type="button" data-scenario="clean">Load clean evidence</button>
      <button type="button" data-scenario="conflict">Load verified conflict</button>
      <button type="button" data-scenario="uncertain">Load missing provenance</button>
    </div>
    <div class="grid">
      <section class="card">
        <div class="card-head"><h2>Evidence controls</h2><span class="badge">edit & run</span></div>
        <form id="run-form">
          <fieldset><legend>Task</legend><div class="fields">
            <label>Decision key<input required name="key" value="customer.delivery_preference"></label>
            <label>Risk<select name="risk"><option value="low">low</option><option value="medium" selected>medium</option><option value="high">high</option><option value="critical">critical</option></select></label>
            <label class="wide">Goal<input required name="goal" value="Choose the notification channel for a delivery update."></label>
          </div></fieldset>
          <fieldset><legend>Current observation</legend><div class="fields">
            <label>Value<input required name="current_value" value="sms"></label>
            <label>Source<select name="current_source"><option value="system_of_record" selected>system of record</option><option value="tool">tool</option><option value="user">user</option><option value="document">document</option><option value="model">model</option></select></label>
            <label>Authority<input required type="number" min="0" max="1" step="0.01" name="authority" value="0.95"></label>
            <label>Confidence<input required type="number" min="0" max="1" step="0.01" name="confidence" value="0.99"></label>
            <label>Relevance<input required type="number" min="0" max="1" step="0.01" name="relevance" value="1.00"></label>
            <label>Provenance<input name="provenance" value="crm-api:customer-42"></label>
          </div></fieldset>
          <fieldset><legend>Memory & verification</legend>
            <div class="checks"><label><input type="checkbox" name="include_memory" checked> Include remembered evidence</label><label><input type="checkbox" name="verify" checked> Enable verifier</label><label><input type="checkbox" name="run_action" checked> Run safe local action</label></div>
            <div class="fields"><label>Remembered value<input name="memory_value" value="email"></label><label>Memory age (days)<input type="number" min="0" name="memory_age_days" value="90"></label><label class="wide">Verified value<input name="verification_value" value="sms"></label></div>
            <p class="hint">The local verifier is deterministic and only confirms the value entered here. No external system is queried.</p>
          </fieldset>
          <button class="primary" type="submit">Run DSER decision</button>
        </form>
      </section>
      <section class="card">
        <div class="card-head"><h2>Decision trace</h2><span class="badge">auditable output</span></div>
        <div id="output"><div class="empty">Load a scenario or change the fields, then run a decision. The output will show the selected claim, conflicts, verification path, action status, and memory-retention result.</div></div>
      </section>
    </div>
    <p class="footer">DSER Local Lab is a deterministic educational demo. It demonstrates evidence reconciliation and does not perform network calls, authorization, or side effects outside its in-memory example.</p>
  </main>
<script>
  let examples = {};
  const form = document.getElementById('run-form');
  const output = document.getElementById('output');
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  function applyPayload(payload) {
    Object.entries(payload).forEach(([name, value]) => {
      const field = form.elements.namedItem(name); if (!field) return;
      if (field.type === 'checkbox') field.checked = Boolean(value); else field.value = value;
    });
  }
  function claimHtml(claim) {
    return `<div class="claim"><strong>${esc(claim.key)} = ${esc(claim.value)}</strong><small>${esc(claim.source)} · authority ${esc(claim.authority)} · provenance ${esc(claim.provenance || 'none')}</small></div>`;
  }
  function render(result) {
    const d = result.decision, selected = d.selected_claim;
    const conflicts = d.conflicts.length ? d.conflicts.map(claimHtml).join('') : '<p class="hint">No material conflicting values.</p>';
    const required = d.required_evidence.length ? `<div class="trace"><h3>Required evidence</h3><p class="reason">${esc(d.required_evidence.join('; '))}</p></div>` : '';
    output.innerHTML = `<div class="decision-title"><span class="status ${esc(d.disposition)}">${esc(d.disposition)}</span><strong>Evidence score ${esc(d.score)}</strong></div><p class="reason">${esc(d.reason)}</p><div class="metric-grid"><div class="metric"><span>Selected value</span><strong>${selected ? esc(selected.value) : '—'}</strong></div><div class="metric"><span>Selected source</span><strong>${selected ? esc(selected.source) : '—'}</strong></div><div class="metric"><span>Verifier used</span><strong>${result.verification_used ? 'yes' : 'no'}</strong></div><div class="metric"><span>Memory retained</span><strong>${result.memory_written ? 'yes' : 'no'}</strong></div></div><div class="trace"><h3>Conflicting claims</h3>${conflicts}</div>${result.action ? `<div class="trace"><h3>Local action</h3><p class="reason">${esc(result.action.message)}</p></div>` : ''}${required}<div class="trace"><h3>Evidence ledger (${result.claims.length})</h3>${result.claims.map(claimHtml).join('')}</div>`;
  }
  async function loadExamples() { examples = await fetch('/api/examples').then(r => r.json()); applyPayload(examples.conflict); }
  document.querySelectorAll('[data-scenario]').forEach(button => button.addEventListener('click', () => applyPayload(examples[button.dataset.scenario])));
  form.addEventListener('submit', async event => { event.preventDefault(); const payload = {}; new FormData(form).forEach((value, key) => payload[key] = value); ['include_memory','verify','run_action'].forEach(key => payload[key] = form.elements.namedItem(key).checked); output.innerHTML = '<div class="empty">Reconciling current evidence, memory, and verification…</div>'; try { const response = await fetch('/api/run', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)}); const data = await response.json(); if (!response.ok) throw new Error(data.error || 'Local demo failed'); render(data); } catch (error) { output.innerHTML = `<div class="error"><strong>Input error</strong><br>${esc(error.message)}</div>`; } });
  loadExamples().catch(error => output.innerHTML = `<div class="error">Could not load built-in scenarios: ${esc(error.message)}</div>`);
</script>
</body>
</html>"""


class DemoHandler(BaseHTTPRequestHandler):
    """Serve the local page and a tiny same-origin JSON API."""

    server_version = "DSERLocalLab/0.1"

    def _send_json(self, status: HTTPStatus, payload: object) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_page(self) -> None:
        body = PAGE.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in {"/", "/index.html"}:
            self._send_page()
        elif path == "/api/examples":
            self._send_json(HTTPStatus.OK, demo_payloads())
        else:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/run":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 65_536:
                raise ValueError("Request body must be between 1 and 65536 bytes")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Request JSON must be an object")
            self._send_json(HTTPStatus.OK, run_local_decision(payload))
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    def log_message(self, format: str, *args: object) -> None:
        print(f"[DSER Local Lab] {format % args}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the DSER local browser demo.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1).")
    parser.add_argument("--port", type=int, default=8765, help="Local port (default: 8765).")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the local page automatically.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    url = f"http://{args.host}:{args.port}"
    httpd = ThreadingHTTPServer((args.host, args.port), DemoHandler)
    print(f"DSER Local Lab running at {url}")
    print("Press Ctrl+C to stop the local server.")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nDSER Local Lab stopped.")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
