"""Mobile-friendly web UI for playing no-start-env scenarios by hand.

Dev/play tool, not part of the eval itself. Wraps ToolSession; shows only
tool outputs until finish(), then reveals the grade breakdown. Useful for
domain verification and collecting human-baseline transcripts.

Run:   python scripts/webapp.py        (serves on http://127.0.0.1:8642)
Phone: cloudflared tunnel --url http://localhost:8642
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from nostart.domain.scenarios import list_scenarios  # noqa: E402
from nostart.grader import grade  # noqa: E402
from nostart.tools import ToolSession  # noqa: E402

PORT = 8642

NODES = [
    "battery_positive", "battery_negative", "engine_block",
    "starter_stud", "alt_output", "chassis",
]
STATES = ["key_off", "key_on", "cranking", "running"]
PIDS = ["battery_voltage", "alt_output_v", "rpm", "can_status"]
COMPONENTS = [
    "battery", "ground_strap", "starter_relay", "starter_motor",
    "alternator", "fusible_link", "ignition_switch", "ecu_can_node",
]

STATE: dict = {"session": None, "scenario": None}


def _status() -> dict:
    if STATE["session"] is None:
        return {}
    return STATE["session"].get_status().model_dump()


def handle_action(payload: dict) -> dict:
    action = payload.get("action")
    args = payload.get("args", {})

    if action == "list_scenarios":
        return {"result": list_scenarios()}

    if action == "new_episode":
        sid = args["scenario"]
        STATE["session"] = ToolSession(sid)
        STATE["scenario"] = sid
        return {"result": {"complaint": STATE["session"].get_complaint()},
                "status": _status()}

    session: ToolSession | None = STATE["session"]
    if session is None:
        return {"error": "No episode started. Pick a scenario first."}

    try:
        if action == "scan_dtcs":
            result = session.scan_dtcs()
        elif action == "read_pid":
            result = session.read_pid(args["pid"])
        elif action == "measure_voltage":
            result = session.measure_voltage(
                args["point_a"], args["point_b"], args["engine_state"]
            )
        elif action == "visual_inspect":
            result = session.visual_inspect(args["area"])
        elif action == "replace_part":
            result = session.replace_part(args["component"])
        elif action == "attempt_start":
            result = session.attempt_start()
        elif action == "finish":
            status = session.finish(args["diagnosis"])
            breakdown = grade(session.world)
            return {"result": status.model_dump(),
                    "grade": breakdown.model_dump(),
                    "status": _status()}
        else:
            return {"error": f"Unknown action '{action}'"}
    except ValueError as exc:
        return {"error": str(exc), "status": _status()}

    return {"result": result, "status": _status()}


PAGE = """<!doctype html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>no-start-env</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: -apple-system, sans-serif; margin: 0; padding: 12px;
         max-width: 640px; margin-inline: auto; }
  h1 { font-size: 1.1rem; }
  fieldset { border: 1px solid #8884; border-radius: 8px; margin: 8px 0;
             padding: 8px; }
  legend { font-size: .8rem; opacity: .7; }
  select, input[type=text] { font-size: 1rem; padding: 6px; margin: 2px;
             border-radius: 6px; border: 1px solid #8886; max-width: 100%; }
  button { font-size: 1rem; padding: 8px 14px; margin: 3px; border-radius: 8px;
           border: 1px solid #8886; background: #4a6cd4; color: #fff; }
  button:active { opacity: .7; }
  #complaint { font-style: italic; }
  #cost { font-size: .85rem; opacity: .8; }
  #log { display: flex; flex-direction: column-reverse; gap: 6px; }
  .entry { border: 1px solid #8883; border-radius: 8px; padding: 6px 8px;
           font-size: .85rem; }
  .entry .act { font-weight: 600; }
  .err { color: #d44; }
  pre { white-space: pre-wrap; word-break: break-word; margin: 4px 0 0; }
  .grade { border: 2px solid #4a6cd4; }
</style>
</head><body>
<h1>🔧 no-start-env — scenario play</h1>

<fieldset><legend>episode</legend>
  <select id="scenario"></select>
  <button onclick="newEpisode()">Start / restart</button>
  <div id="complaint"></div>
  <div id="cost"></div>
</fieldset>

<fieldset><legend>probe</legend>
  <button onclick="act('scan_dtcs')">scan_dtcs</button>
  <button onclick="act('attempt_start')">attempt_start</button>
  <br>
  <select id="pid"></select>
  <button onclick="act('read_pid',{pid:val('pid')})">read_pid</button>
  <br>
  <select id="pa"></select> → <select id="pb"></select>
  <select id="es"></select>
  <button onclick="act('measure_voltage',{point_a:val('pa'),point_b:val('pb'),engine_state:val('es')})">measure</button>
</fieldset>

<fieldset><legend>act</legend>
  <select id="insp"></select>
  <button onclick="act('visual_inspect',{area:val('insp')})">inspect</button>
  <button onclick="act('replace_part',{component:val('insp')})">replace</button>
</fieldset>

<fieldset><legend>finish</legend>
  <input type="text" id="diag" placeholder="diagnosis, e.g. 'corroded ground strap'" size="30">
  <button onclick="act('finish',{diagnosis:val('diag')})">finish</button>
</fieldset>

<fieldset><legend>transcript</legend>
  <button id="copybtn" onclick="copyLog()">📋 Copy full transcript</button>
</fieldset>

<div id="log"></div>

<script>
const NODES = __NODES__, STATES = __STATES__, PIDS = __PIDS__, COMPS = __COMPS__;
function fill(id, opts, dflt) {
  const s = document.getElementById(id);
  opts.forEach(o => { const e = document.createElement('option');
    e.value = e.textContent = o; s.appendChild(e); });
  if (dflt) s.value = dflt;
}
function val(id) { return document.getElementById(id).value; }
async function api(body) {
  const r = await fetch('/api', {method:'POST',
    headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  return r.json();
}
const transcript = [];
function copyText() {
  return transcript.map(e =>
    e.title + '\\n' + JSON.stringify(e.data, null, 1)).join('\\n\\n');
}
async function copyLog() {
  const btn = document.getElementById('copybtn');
  try {
    await navigator.clipboard.writeText(copyText());
    btn.textContent = '✓ Copied';
  } catch (e) {
    // Clipboard blocked: show selectable text instead.
    const ta = document.createElement('textarea');
    ta.value = copyText(); ta.style.width = '100%'; ta.rows = 12;
    btn.after(ta); ta.select();
    btn.textContent = 'Select & copy below';
  }
  setTimeout(() => { btn.textContent = '📋 Copy full transcript'; }, 1500);
}
function logEntry(title, data, cls) {
  transcript.push({title, data});
  const d = document.createElement('div');
  d.className = 'entry ' + (cls||'');
  d.innerHTML = '<span class="act">' + title + '</span><pre>' +
    JSON.stringify(data, null, 1) + '</pre>';
  document.getElementById('log').appendChild(d);
}
function showStatus(st) {
  if (!st || !st.cumulative_cost) return;
  document.getElementById('cost').textContent =
    'actions: ' + st.action_count + ' · cost: ' +
    JSON.stringify(st.cumulative_cost);
}
async function act(action, args) {
  const resp = await api({action, args: args||{}});
  if (resp.error) { logEntry(action + ' ✗', resp.error, 'err'); }
  else { logEntry(action, resp.result); }
  if (resp.grade) logEntry('GRADE', resp.grade, 'grade');
  showStatus(resp.status);
}
async function newEpisode() {
  document.getElementById('log').innerHTML = '';
  transcript.length = 0;
  const resp = await api({action:'new_episode', args:{scenario: val('scenario')}});
  transcript.push({title: 'new_episode ' + val('scenario'),
                   data: resp.result});
  document.getElementById('complaint').textContent =
    '“' + resp.result.complaint + '”';
  showStatus(resp.status);
}
(async () => {
  const sc = await api({action:'list_scenarios'});
  fill('scenario', sc.result);
  fill('pid', PIDS); fill('pa', NODES, 'battery_positive');
  fill('pb', NODES, 'battery_negative'); fill('es', STATES, 'cranking');
  fill('insp', COMPS);
})();
</script>
</body></html>
"""

PAGE = (PAGE
        .replace("__NODES__", json.dumps(NODES))
        .replace("__STATES__", json.dumps(STATES))
        .replace("__PIDS__", json.dumps(PIDS))
        .replace("__COMPS__", json.dumps(COMPONENTS)))


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/", "/index.html"):
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api":
            self._send(404, b"not found", "text/plain")
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length))
            resp = handle_action(payload)
        except Exception as exc:  # noqa: BLE001 — surface anything to the UI
            resp = {"error": f"{type(exc).__name__}: {exc}"}
        self._send(200, json.dumps(resp).encode(), "application/json")

    def log_message(self, fmt: str, *args) -> None:
        pass  # quiet


if __name__ == "__main__":
    print(f"serving on http://127.0.0.1:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
