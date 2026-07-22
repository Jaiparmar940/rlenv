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
  /* Force dark regardless of the OS/browser theme: under a light theme the
     UA painted inputs and log text near-white on white. Every surface below
     sets both background AND color explicitly — no UA defaults left. */
  :root { color-scheme: dark;
          --bg: #0f1115; --fg: #f3f4f6; --panel: #191c23; --panel-raised: #20242d;
          --line: #343a46; --muted: #9ca3af; --accent: #7697ff;
          --accent-soft: #25345e; --success: #74d6a0; --success-soft: #183b2a;
          --danger: #ff8c8c; --danger-soft: #482326; }
  html { background: var(--bg); }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         margin: 0; padding: 28px 16px 56px; max-width: 720px; margin-inline: auto;
         background: var(--bg); color: var(--fg); }
  * { box-sizing: border-box; }
  .page-header { margin: 0 0 24px; }
  .eyebrow { display: block; margin-bottom: 6px; color: var(--accent);
             font-size: .72rem; font-weight: 750; letter-spacing: .12em;
             text-transform: uppercase; }
  h1 { margin: 0; color: var(--fg); font-size: clamp(1.55rem, 5vw, 2rem);
       letter-spacing: -.035em; }
  .subtitle { margin: 7px 0 0; color: var(--muted); font-size: .94rem;
              line-height: 1.45; }
  fieldset { border: 1px solid var(--line); border-radius: 14px; margin: 12px 0;
             padding: 13px; background: var(--panel); }
  legend { padding: 0 6px; color: var(--muted); font-size: .72rem;
           font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
  select, input[type=text] { min-height: 42px; font-size: .95rem; padding: 9px 10px;
             margin: 3px; border-radius: 9px; border: 1px solid var(--line);
             max-width: 100%; background: var(--bg); color: var(--fg); }
  input[type=text] { width: min(100%, 390px); }
  select:focus-visible, input:focus-visible, button:focus-visible {
    outline: 3px solid color-mix(in srgb, var(--accent) 42%, transparent);
    outline-offset: 2px;
  }
  option { background: var(--bg); color: var(--fg); }
  button { min-height: 42px; font-size: .93rem; font-weight: 700; padding: 9px 14px;
           margin: 3px; border-radius: 9px; border: 1px solid var(--accent);
           background: var(--accent); color: #0c1428; cursor: pointer;
           transition: transform 120ms ease, filter 120ms ease; }
  button:hover { filter: brightness(1.08); }
  button:active { transform: translateY(1px); }
  #complaint { margin: 10px 3px 2px; padding: 12px 14px; border-left: 3px solid var(--accent);
               border-radius: 0 8px 8px 0; background: var(--panel-raised);
               color: var(--fg); font-size: .93rem; line-height: 1.45; }
  #complaint:empty { display: none; }
  #engine-state:empty { display: none; }
  .engine-indicator { display: inline-flex; align-items: center; gap: 8px; margin: 10px 3px 0;
                      padding: 8px 11px; border: 1px solid var(--line); border-radius: 10px;
                      background: var(--bg); color: var(--muted); font-size: .82rem; }
  .engine-indicator strong { color: var(--fg); }
  .engine-dot { width: 8px; height: 8px; border-radius: 999px; background: #6d7480; }
  .engine-indicator.running { border-color: color-mix(in srgb, var(--success) 48%, var(--line));
                              background: var(--success-soft); color: var(--success); }
  .engine-indicator.running .engine-dot { background: var(--success);
                                          box-shadow: 0 0 0 4px #74d6a024; }
  #cost { display: flex; flex-wrap: wrap; gap: 7px; margin: 10px 3px 0; }
  .status-pill { display: inline-flex; align-items: center; gap: 5px; padding: 5px 9px;
                 border: 1px solid var(--line); border-radius: 999px;
                 background: var(--bg); color: var(--muted); font-size: .78rem; }
  .status-pill strong { color: var(--fg); font-weight: 700; }
  .workspace { display: grid; gap: 28px; align-items: start; }
  .controls fieldset:first-child { margin-top: 0; }
  .voltage-controls { display: flex; flex-wrap: wrap; align-items: center; gap: 6px;
                      margin: 3px; }
  .voltage-controls select, .voltage-controls button { margin: 0; }
  .voltage-arrow { color: var(--muted); font-size: 1.25rem; line-height: 1; }
  .activity-header { display: flex; align-items: end; justify-content: space-between;
                     margin: 30px 2px 12px; }
  .activity-header h2 { margin: 0; font-size: 1.08rem; letter-spacing: -.015em; }
  .activity-tools { display: flex; align-items: center; justify-content: flex-end;
                    flex-wrap: wrap; gap: 8px; }
  .collapse-all { min-height: 32px; margin: 0; padding: 5px 9px;
                  border-color: var(--line); background: var(--panel);
                  color: var(--fg); font-size: .76rem; }
  .collapse-all:disabled { cursor: default; opacity: .45; filter: none; }
  #entry-count { color: var(--muted); font-size: .78rem; }
  #log { display: flex; flex-direction: column; gap: 10px; }
  .entry { flex: 0 0 auto; overflow: hidden; border: 1px solid var(--line); border-radius: 14px;
           background: var(--panel); color: var(--fg); box-shadow: 0 7px 24px #0000001f; }
  .entry-head { display: flex; align-items: center; gap: 10px; padding: 12px 14px;
                border-bottom: 1px solid var(--line); background: var(--panel-raised); }
  .entry-toggle { width: 100%; min-height: 0; margin: 0; border-width: 0 0 1px;
                  border-color: var(--line); border-radius: 0;
                  background: var(--panel-raised); color: var(--fg);
                  font: inherit; text-align: left; }
  .entry-toggle:hover { filter: brightness(1.05); }
  .entry-heading { flex: 1 1 auto; min-width: 0; }
  .entry-chevron { flex: 0 0 auto; color: var(--muted); font-size: 1.05rem;
                   transition: transform 140ms ease; }
  .entry.collapsed .entry-toggle { border-bottom-color: transparent; }
  .entry.collapsed .entry-body { display: none; }
  .entry.collapsed .entry-chevron { transform: rotate(-90deg); }
  .entry-icon { display: grid; place-items: center; width: 31px; height: 31px;
                flex: 0 0 auto; border-radius: 9px; background: var(--accent-soft);
                color: #c9d6ff; font-size: .95rem; }
  .entry .act { display: block; font-size: .92rem; font-weight: 750; }
  .entry-kicker { display: block; margin-top: 1px; color: var(--muted); font-size: .7rem; }
  .entry-body { padding: 6px 14px 8px; }
  .result-grid { display: grid; }
  .result-row { display: grid; grid-template-columns: minmax(100px, .44fr) minmax(0, 1fr);
                align-items: start; gap: 14px; padding: 9px 0;
                border-bottom: 1px solid color-mix(in srgb, var(--line) 65%, transparent); }
  .result-row:last-child { border-bottom: 0; }
  .result-label { padding-top: 2px; color: var(--muted); font-size: .75rem;
                  font-weight: 650; letter-spacing: .02em; }
  .result-value { min-width: 0; color: var(--fg); font-size: .9rem;
                  line-height: 1.45; overflow-wrap: anywhere; }
  .value-pill { display: inline-flex; max-width: 100%; padding: 4px 9px;
                border-radius: 999px; background: var(--accent-soft);
                color: #cbd7ff; font-size: .8rem; font-weight: 700; }
  .value-pill.good { background: var(--success-soft); color: var(--success); }
  .value-pill.bad { background: var(--danger-soft); color: var(--danger); }
  .empty-value { color: var(--muted); font-style: italic; }
  .nested-list { display: grid; gap: 7px; }
  .nested-card { padding: 5px 10px; border: 1px solid var(--line); border-radius: 9px;
                 background: var(--bg); }
  .message { margin: 0; padding: 7px 0; font-size: .92rem; line-height: 1.5; }
  .empty-log { padding: 24px 18px; border: 1px dashed var(--line); border-radius: 14px;
               color: var(--muted); text-align: center; font-size: .87rem; }
  .err { border-color: color-mix(in srgb, var(--danger) 55%, var(--line)); }
  .err .entry-icon { background: var(--danger-soft); color: var(--danger); }
  textarea { background: var(--bg); color: var(--fg);
             border: 1px solid var(--line); border-radius: 9px; padding: 10px; }
  .grade { border-color: var(--accent); }
  .grade .entry-head { background: var(--accent-soft); }
  @media (min-width: 1160px) {
    body { max-width: 1440px; }
    .workspace { grid-template-columns: minmax(660px, 1.1fr) minmax(420px, .9fr);
                 gap: 32px; }
    .voltage-controls { display: grid;
                        grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr)
                                               minmax(105px, .65fr) auto; }
    .voltage-controls select { width: 100%; min-width: 0; }
    .activity-panel { position: sticky; top: 24px; display: flex; flex-direction: column;
                      height: min(720px, calc(100vh - 48px)); }
    .activity-header { flex: 0 0 auto; margin-top: 0; }
    #log { flex: 1 1 auto; min-height: 0; overflow-y: auto; padding-right: 8px;
           overscroll-behavior: contain; scrollbar-gutter: stable; }
  }
  @media (max-width: 520px) {
    body { padding: 20px 11px 40px; }
    fieldset { padding: 10px; }
    .result-row { grid-template-columns: 92px minmax(0, 1fr); gap: 9px; }
    select { max-width: calc(100% - 8px); }
  }
</style>
</head><body>
<header class="page-header">
  <span class="eyebrow">Vehicle diagnostics simulator</span>
  <h1>No-start diagnostic lab</h1>
  <p class="subtitle">Investigate the symptoms, make a repair, and verify your diagnosis.</p>
</header>

<main class="workspace">
  <section class="controls" aria-label="Diagnostic controls">
    <fieldset><legend>Start an episode</legend>
      <select id="scenario"></select>
      <button onclick="newEpisode()">Start or restart</button>
      <div id="complaint"></div>
      <div id="engine-state" aria-live="polite"></div>
      <div id="cost"></div>
    </fieldset>

    <fieldset><legend>Run diagnostics</legend>
      <button onclick="act('scan_dtcs')">Scan codes</button>
      <button onclick="act('attempt_start')">Try to start</button>
      <br>
      <select id="pid"></select>
      <button onclick="act('read_pid',{pid:val('pid')})">Read PID</button>
      <br>
      <div class="voltage-controls">
        <select id="pa"></select>
        <span class="voltage-arrow" aria-hidden="true">→</span>
        <select id="pb"></select>
        <select id="es"></select>
        <button onclick="act('measure_voltage',{point_a:val('pa'),point_b:val('pb'),engine_state:val('es')})">Measure voltage</button>
      </div>
    </fieldset>

    <fieldset><legend>Inspect or repair</legend>
      <select id="insp"></select>
      <button onclick="act('visual_inspect',{area:val('insp')})">Inspect</button>
      <button onclick="act('replace_part',{component:val('insp')})">Replace</button>
    </fieldset>

    <fieldset><legend>Finish the episode</legend>
      <input type="text" id="diag" placeholder="diagnosis, e.g. 'corroded ground strap'" size="30">
      <button onclick="act('finish',{diagnosis:val('diag')})">Submit diagnosis</button>
    </fieldset>

    <fieldset><legend>transcript</legend>
      <button id="copybtn" onclick="copyLog()">Copy full transcript</button>
    </fieldset>
  </section>

  <aside class="activity-panel" aria-label="Episode activity">
    <div class="activity-header">
      <div>
        <span class="eyebrow">Episode timeline</span>
        <h2>Activity</h2>
      </div>
      <div class="activity-tools">
        <span id="entry-count">No actions yet</span>
        <button id="collapse-all" class="collapse-all" type="button"
                onclick="collapseAll()" disabled>Collapse all</button>
      </div>
    </div>
    <div id="log"><div class="empty-log">Your diagnostic results will appear here.</div></div>
  </aside>
</main>

<script>
const NODES = __NODES__, STATES = __STATES__, PIDS = __PIDS__, COMPS = __COMPS__;
function fill(id, opts, dflt) {
  const s = document.getElementById(id);
  opts.forEach(o => { const e = document.createElement('option');
    e.value = o; e.textContent = humanize(o); s.appendChild(e); });
  if (dflt) s.value = dflt;
}
function val(id) { return document.getElementById(id).value; }
async function api(body) {
  const r = await fetch('/api', {method:'POST',
    headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  return r.json();
}
const transcript = [];
const ACTIONS = {
  scan_dtcs: ['Scan codes', '⌁'],
  attempt_start: ['Start attempt', '↻'],
  read_pid: ['PID reading', '⌁'],
  measure_voltage: ['Voltage measurement', 'V'],
  visual_inspect: ['Visual inspection', '◉'],
  replace_part: ['Part replacement', '✓'],
  finish: ['Diagnosis submitted', '✓'],
  GRADE: ['Episode score', '★']
};
function humanize(value) {
  return String(value).replaceAll('_', ' ').replace(/\\b\\w/g, c => c.toUpperCase());
}
function actionMeta(title) {
  const raw = title.replace(/ ✗$/, '');
  return ACTIONS[raw] || [humanize(raw), '•'];
}
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
  setTimeout(() => { btn.textContent = 'Copy full transcript'; }, 1500);
}
function primitiveValue(value, key) {
  if (value === null || value === undefined || value === '') {
    const empty = document.createElement('span');
    empty.className = 'empty-value'; empty.textContent = 'Not available';
    return empty;
  }
  if (typeof value === 'boolean') {
    const pill = document.createElement('span');
    const positiveKeys = ['installed', 'fix_verified', 'finished', 'diagnosed_secondary'];
    const penaltyKeys = ['guessing_penalty_applied', 'resolution_penalty_applied'];
    let tone = '';
    if (positiveKeys.includes(key)) tone = value ? 'good' : 'bad';
    if (penaltyKeys.includes(key)) tone = value ? 'bad' : 'good';
    pill.className = 'value-pill ' + tone;
    pill.textContent = value ? 'Yes' : 'No';
    return pill;
  }
  const span = document.createElement('span');
  const tokenKeys = ['result', 'engine_state', 'pid', 'component', 'mode',
                     'true_component', 'true_mode', 'diagnosed_component',
                     'diagnosed_mode', 'scenario_id', 'point_a', 'point_b',
                     'true_secondary'];
  const machineToken = typeof value === 'string' &&
    /^[a-z0-9]+(?:_[a-z0-9]+)+$/.test(value);
  if (tokenKeys.includes(key) || machineToken) {
    span.className = 'value-pill';
    span.textContent = humanize(value);
    if (['starts', 'ok'].includes(value)) span.classList.add('good');
    if (['no_click', 'click_no_crank', 'slow_crank', 'crank_no_start',
         'bus_off'].includes(value)) span.classList.add('bad');
  } else {
    span.textContent = String(value);
  }
  return span;
}
function renderValue(value, key) {
  if (Array.isArray(value)) {
    if (!value.length) {
      const empty = document.createElement('span');
      empty.className = 'empty-value'; empty.textContent = 'None found';
      return empty;
    }
    const list = document.createElement('div'); list.className = 'nested-list';
    value.forEach(item => {
      const card = document.createElement('div'); card.className = 'nested-card';
      card.appendChild(renderValue(item, key)); list.appendChild(card);
    });
    return list;
  }
  if (value && typeof value === 'object') return renderObject(value);
  return primitiveValue(value, key);
}
function renderObject(data) {
  const grid = document.createElement('div'); grid.className = 'result-grid';
  Object.entries(data).forEach(([key, value]) => {
    const row = document.createElement('div'); row.className = 'result-row';
    const label = document.createElement('div'); label.className = 'result-label';
    label.textContent = humanize(key);
    const output = document.createElement('div'); output.className = 'result-value';
    output.appendChild(renderValue(value, key));
    row.append(label, output); grid.appendChild(row);
  });
  return grid;
}
let entrySequence = 0;
function updateCollapseAll() {
  const entries = [...document.querySelectorAll('#log .entry')];
  document.getElementById('collapse-all').disabled =
    !entries.some(entry => !entry.classList.contains('collapsed'));
}
function setEntryCollapsed(entry, collapsed) {
  entry.classList.toggle('collapsed', collapsed);
  const toggle = entry.querySelector('.entry-toggle');
  if (toggle) toggle.setAttribute('aria-expanded', String(!collapsed));
  updateCollapseAll();
}
function collapseAll() {
  document.querySelectorAll('#log .entry').forEach(entry => {
    entry.classList.add('collapsed');
    entry.querySelector('.entry-toggle')?.setAttribute('aria-expanded', 'false');
  });
  updateCollapseAll();
}
function logEntry(title, data, cls) {
  transcript.push({title, data});
  const meta = actionMeta(title);
  const d = document.createElement('div');
  d.className = 'entry ' + (cls||'');
  const bodyId = 'activity-body-' + (++entrySequence);
  const head = document.createElement('button');
  head.type = 'button'; head.className = 'entry-head entry-toggle';
  head.setAttribute('aria-expanded', 'true');
  head.setAttribute('aria-controls', bodyId);
  const icon = document.createElement('span'); icon.className = 'entry-icon';
  icon.textContent = meta[1];
  const heading = document.createElement('div'); heading.className = 'entry-heading';
  const action = document.createElement('span'); action.className = 'act';
  action.textContent = meta[0] + (title.endsWith('✗') ? ' failed' : '');
  const kicker = document.createElement('span'); kicker.className = 'entry-kicker';
  kicker.textContent = title === 'GRADE' ? 'Final result' : 'Diagnostic action';
  const chevron = document.createElement('span'); chevron.className = 'entry-chevron';
  chevron.textContent = '⌄'; chevron.setAttribute('aria-hidden', 'true');
  heading.append(action, kicker); head.append(icon, heading, chevron);
  head.addEventListener('click', () => {
    setEntryCollapsed(d, !d.classList.contains('collapsed'));
  });
  const body = document.createElement('div'); body.className = 'entry-body'; body.id = bodyId;
  if (data && typeof data === 'object') body.appendChild(renderValue(data, ''));
  else {
    const message = document.createElement('p'); message.className = 'message';
    message.textContent = data === null || data === undefined ? 'No result' : String(data);
    body.appendChild(message);
  }
  d.append(head, body);
  const log = document.getElementById('log');
  const empty = log.querySelector('.empty-log'); if (empty) empty.remove();
  log.prepend(d);
  const count = log.querySelectorAll('.entry').length;
  document.getElementById('entry-count').textContent =
    count + (count === 1 ? ' action' : ' actions');
  updateCollapseAll();
}
function showStatus(st) {
  if (!st || !st.cumulative_cost) return;
  const engine = document.getElementById('engine-state');
  const running = st.engine_state === 'running';
  engine.replaceChildren();
  const indicator = document.createElement('span');
  indicator.className = 'engine-indicator ' + (running ? 'running' : 'off');
  const dot = document.createElement('span'); dot.className = 'engine-dot';
  const label = document.createTextNode('Engine ');
  const state = document.createElement('strong'); state.textContent = running ? 'Running' : 'Off';
  indicator.append(dot, label, state); engine.appendChild(indicator);
  const cost = document.getElementById('cost'); cost.replaceChildren();
  [['Actions', st.action_count], ['Time', st.cumulative_cost.minutes + ' min'],
   ['Parts', '$' + st.cumulative_cost.dollars.toFixed(2)]].forEach(item => {
    const pill = document.createElement('span'); pill.className = 'status-pill';
    const label = document.createTextNode(item[0] + ' ');
    const value = document.createElement('strong'); value.textContent = item[1];
    pill.append(label, value); cost.appendChild(pill);
  });
}
async function act(action, args) {
  const resp = await api({action, args: args||{}});
  if (resp.error) { logEntry(action + ' ✗', resp.error, 'err'); }
  else { logEntry(action, resp.result); }
  if (resp.grade) logEntry('GRADE', resp.grade, 'grade');
  showStatus(resp.status);
}
async function newEpisode() {
  document.getElementById('log').innerHTML =
    '<div class="empty-log">Your diagnostic results will appear here.</div>';
  document.getElementById('entry-count').textContent = 'No actions yet';
  transcript.length = 0;
  updateCollapseAll();
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
