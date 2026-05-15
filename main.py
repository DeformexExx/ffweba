from bottle import route, run, request, response
import base64
import html
import json
import subprocess
import time

from database import db


def run_root(cmd: str) -> str:
    return subprocess.getoutput(f"su -c '{cmd}'")


def json_out(payload: dict, code: int = 200):
    response.status = code
    response.content_type = "application/json"
    return json.dumps(payload, ensure_ascii=False)


def inject_roblox_cookie(cookie: str) -> tuple[bool, str]:
    cookie = (cookie or "").strip()
    if not cookie:
        return False, "empty_cookie"

    pref_path = "/data/data/com.roblox.client/shared_prefs/com.roblox.client.v2.playerprefs.xml"
    escaped = cookie.replace("'", "'\\''")
    cmd = (
        "if [ -f {p} ]; then "
        "sed -i \"s#<string name=\\\".ROBLOSECURITY\\\">.*</string>#<string name=\\\".ROBLOSECURITY\\\">{c}</string>#g\" {p}; "
        "else "
        "mkdir -p /data/data/com.roblox.client/shared_prefs; "
        "echo '<map><string name=\".ROBLOSECURITY\">{c}</string></map>' > {p}; "
        "fi"
    ).format(p=pref_path, c=escaped)

    out = run_root(cmd)
    if "not found" in out.lower() or "permission denied" in out.lower():
        return False, out
    return True, out or "ok"


@route("/")
def index():
    return """
<!doctype html>
<html lang='en'>
<head>
  <meta charset='UTF-8' />
  <meta name='viewport' content='width=device-width, initial-scale=1.0' />
  <title>AEGIS Professional Control</title>
  <script src='https://cdn.tailwindcss.com'></script>
  <style>
    body { background:#050505; color:#d9ffe1; }
    .glass { background:rgba(11,16,11,.78); border:1px solid #173117; }
    .active-neon { border-color:#39ff14 !important; box-shadow:0 0 22px rgba(57,255,20,.22); }
    .term { background:#040704; border:1px solid #1c4d1c; }
    .smooth { transition:all .25s ease; }
  </style>
</head>
<body class='min-h-screen font-mono'>
  <header class='sticky top-0 z-20 border-b border-green-900 bg-black/90 backdrop-blur px-3 py-3'>
    <div class='max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-3'>
      <h1 class='text-green-400 text-lg md:text-2xl tracking-wider'>[ AEGIS PROFESSIONAL WEB CONTROL ]</h1>
      <div class='flex flex-wrap gap-2'>
        <button id='startAll' class='smooth border border-green-500 hover:bg-green-950 px-3 py-1 text-green-300'>Global Start All</button>
        <button id='stopAll' class='smooth border border-green-500 hover:bg-green-950 px-3 py-1 text-green-300'>Global Stop All</button>
        <div class='glass px-3 py-1 text-sm'>System Load: <span id='sysLoad'>--</span></div>
      </div>
    </div>
  </header>

  <main class='max-w-7xl mx-auto p-3 md:p-4'>
    <section id='grid' class='grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4'></section>
  </main>

  <div id='authModal' class='hidden fixed inset-0 bg-black/80 items-center justify-center p-4'>
    <div class='w-full max-w-2xl glass p-4 border border-green-500'>
      <h2 class='text-green-400 text-lg mb-2'>Auth Injector (.ROBLOSECURITY)</h2>
      <div class='text-xs text-gray-300 mb-2'>Device: <span id='authDevice'></span></div>
      <textarea id='authCookie' class='w-full h-40 bg-black border border-green-800 p-2 text-sm' placeholder='Paste .ROBLOSECURITY cookie here'></textarea>
      <div class='mt-3 flex gap-2 justify-end'>
        <button id='authCancel' class='border border-green-700 px-3 py-1'>Cancel</button>
        <button id='authSave' class='border border-green-500 px-3 py-1 text-green-300'>Save + Inject</button>
      </div>
    </div>
  </div>

<script>
const state = { devices: [], authDeviceId: null };

async function api(url, method='GET', body=null){
  const res = await fetch(url, {
    method,
    headers: {'Content-Type':'application/json'},
    body: body ? JSON.stringify(body) : undefined
  });
  return await res.json();
}

function statusLabel(d){
  if ((d.status||'').toLowerCase() !== 'online') return 'Offline';
  return Number(d.tcp_count||0) >= 5 ? 'Farming' : 'Online';
}

function cardTemplate(d){
  const isOnline = (d.status||'').toLowerCase() === 'online';
  const isActive = isOnline || Number(d.tcp_count||0) >= 5;
  const neon = isActive ? 'active-neon' : '';
  const screenshot = d.screenshot_b64 ? `data:image/png;base64,${d.screenshot_b64}` : '';

  return `
  <article class='glass smooth ${neon} p-3 rounded-md'>
    <div class='flex justify-between items-center'>
      <div>
        <div class='text-green-300 text-sm'>${escapeHtml(d.name || d.id)}</div>
        <div class='text-xs text-gray-400'>${escapeHtml(d.id || '')} • ${escapeHtml(d.ip || 'unknown-ip')}</div>
      </div>
      <div class='text-xs px-2 py-1 border border-green-800'>${statusLabel(d)}</div>
    </div>

    <div class='mt-2 text-xs grid grid-cols-2 gap-1'>
      <div>TCP: <span class='text-green-300'>${Number(d.tcp_count||0)}</span></div>
      <div>RAM: <span class='text-green-300'>${Number(d.ram||0).toFixed(1)}%</span></div>
    </div>

    <div class='mt-2'>
      <input id='link-${d.id}' value='${escapeHtml(d.saved_link||'')}' placeholder='Persistent Roblox Link' class='w-full bg-black border border-green-900 p-1 text-xs'/>
      <button onclick='saveLink("${d.id}")' class='mt-1 w-full border border-green-700 py-1 text-xs hover:bg-green-950'>Save Link</button>
    </div>

    <div class='mt-2 grid grid-cols-2 gap-2'>
      <button onclick='startOne("${d.id}")' class='border border-green-500 text-green-300 py-1 text-xs hover:bg-green-950'>Start</button>
      <button onclick='stopOne("${d.id}")' class='border border-green-700 py-1 text-xs hover:bg-green-950'>Stop</button>
    </div>

    <div class='mt-2 flex items-center justify-between text-xs'>
      <span>Watchdog</span>
      <label class='inline-flex items-center cursor-pointer'>
        <input type='checkbox' ${Number(d.watchdog_enabled||0)===1?'checked':''} onchange='toggleWatchdog("${d.id}", this.checked)' />
      </label>
    </div>

    <div class='mt-2'>
      <div class='flex gap-1'>
        <input id='clip-${d.id}' placeholder='Clipboard text' class='flex-1 bg-black border border-green-900 p-1 text-xs'/>
        <button onclick='sendClipboard("${d.id}")' class='border border-green-700 px-2 text-xs hover:bg-green-950'>Send</button>
      </div>
      <button onclick='readClipboard("${d.id}")' class='mt-1 w-full border border-green-900 py-1 text-xs hover:bg-green-950'>Read Clipboard</button>
      <div class='text-[11px] text-gray-400 break-all mt-1'>${escapeHtml(d.clipboard_last_read||'')}</div>
    </div>

    <div class='mt-2'>
      <div class='flex gap-2'>
        <button onclick='captureShot("${d.id}")' class='w-full border border-green-700 py-1 text-xs hover:bg-green-950'>Capture</button>
        <button onclick='openAuth("${d.id}")' class='w-full border border-green-700 py-1 text-xs hover:bg-green-950'>Auth</button>
      </div>
      <div class='mt-2'>
        ${screenshot ? `<img src='${screenshot}' onclick='expandImg(this.src)' class='w-full h-28 object-cover border border-green-900 cursor-zoom-in smooth hover:opacity-90'/>` : `<div class='h-28 border border-green-950 grid place-items-center text-xs text-gray-500'>No screenshot</div>`}
      </div>
    </div>

    <div class='mt-2'>
      <div class='term p-2 h-24 overflow-auto text-[11px] whitespace-pre-wrap' id='term-${d.id}'></div>
      <div class='flex gap-1 mt-1'>
        <input id='cmd-${d.id}' placeholder='su -c command' class='flex-1 bg-black border border-green-900 p-1 text-xs'/>
        <button onclick='execOnDevice("${d.id}")' class='border border-green-700 px-2 text-xs'>Exec</button>
      </div>
    </div>
  </article>`;
}

function escapeHtml(s){
  return String(s||'').replaceAll('&','&').replaceAll('<','<').replaceAll('>','>').replaceAll('"','"').replaceAll("'",'&#039;');
}

function render(){
  const grid = document.getElementById('grid');
  grid.innerHTML = state.devices.map(cardTemplate).join('');
}

async function refresh(){
  const data = await api('/api/devices');
  state.devices = data.items || [];
  document.getElementById('sysLoad').textContent = `${data.system_load?.cpu ?? '--'}% CPU / ${data.system_load?.mem ?? '--'}% MEM`;
  render();
}

async function saveLink(id){
  const link = document.getElementById(`link-${id}`).value;
  await api(`/api/device/${id}/link`, 'POST', {link});
  refresh();
}

async function toggleWatchdog(id, enabled){
  await api(`/api/device/${id}/watchdog`, 'POST', {enabled});
}

async function sendClipboard(id){
  const text = document.getElementById(`clip-${id}`).value;
  await api(`/api/clipboard/${id}`, 'POST', {text});
}

async function readClipboard(id){
  await api(`/api/clipboard/${id}`, 'GET');
  setTimeout(refresh, 300);
}

async function captureShot(id){
  await api(`/api/screenshot/${id}`, 'GET');
  setTimeout(refresh, 300);
}

async function startOne(id){
  await api('/api/start', 'POST', {device_id:id});
}

async function stopOne(id){
  await api('/api/stop', 'POST', {device_id:id});
}

async function execOnDevice(id){
  const cmd = document.getElementById(`cmd-${id}`).value;
  const res = await api('/api/exec', 'POST', {device_id:id, cmd});
  const term = document.getElementById(`term-${id}`);
  term.textContent += `\n$ ${cmd}\n${res.output || ''}\n`;
  term.scrollTop = term.scrollHeight;
}

function openAuth(id){
  state.authDeviceId = id;
  document.getElementById('authDevice').textContent = id;
  document.getElementById('authCookie').value = '';
  document.getElementById('authModal').classList.remove('hidden');
  document.getElementById('authModal').classList.add('flex');
}

function closeAuth(){
  document.getElementById('authModal').classList.add('hidden');
  document.getElementById('authModal').classList.remove('flex');
}

async function saveAuth(){
  const cookie = document.getElementById('authCookie').value;
  if (!state.authDeviceId) return;
  await api('/api/device/' + state.authDeviceId + '/cookie', 'POST', {cookie});
  await api('/api/start', 'POST', {device_id: state.authDeviceId, inject_only: true});
  closeAuth();
  refresh();
}

function expandImg(src){
  const w = window.open('about:blank', '_blank');
  w.document.write(`<body style="margin:0;background:#000;display:grid;place-items:center"><img style="max-width:100vw;max-height:100vh" src="${src}"/></body>`);
}

document.getElementById('startAll').onclick = ()=>api('/api/start_all','POST',{});
document.getElementById('stopAll').onclick = ()=>api('/api/stop_all','POST',{});
document.getElementById('authCancel').onclick = closeAuth;
document.getElementById('authSave').onclick = saveAuth;

setInterval(refresh, 3500);
refresh();
</script>
</body>
</html>
"""


@route("/api/devices")
def api_devices():
    db.mark_offline_stale(75)
    try:
        import psutil
        cpu = round(psutil.cpu_percent(interval=0.1), 1)
        mem = round(psutil.virtual_memory().percent, 1)
    except Exception:
        cpu, mem = 0.0, 0.0
    return json_out({"ok": True, "items": db.list_devices(), "system_load": {"cpu": cpu, "mem": mem}})


@route("/api/device/<device_id>/link", method="POST")
def api_set_link(device_id: str):
    data = request.json or {}
    db.set_link(device_id, (data.get("link") or "").strip())
    return json_out({"ok": True})


@route("/api/device/<device_id>/cookie", method="POST")
def api_set_cookie(device_id: str):
    data = request.json or {}
    cookie = (data.get("cookie") or "").strip()
    db.set_cookie(device_id, cookie)
    return json_out({"ok": True})


@route("/api/device/<device_id>/watchdog", method="POST")
def api_watchdog(device_id: str):
    data = request.json or {}
    enabled = bool(data.get("enabled", False))
    db.set_watchdog(device_id, enabled)
    db.queue_command(device_id, "set_watchdog", json.dumps({"enabled": enabled}))
    return json_out({"ok": True})


@route("/api/screenshot/<device_id>", method="GET")
def api_screenshot(device_id: str):
    device = db.get_device(device_id)
    if not device:
        return json_out({"ok": False, "error": "device_not_found"}, 404)

    db.queue_command(device_id, "screenshot", "{}")

    # local fallback for master-host
    tmp_path = "/data/local/tmp/aegis_shot.png"
    cmd = f"screencap -p {tmp_path} && cat {tmp_path}"
    out = run_root(cmd)
    run_root(f"rm -f {tmp_path}")
    if out and "permission denied" not in out.lower() and "not found" not in out.lower():
        raw = out.encode("latin1", errors="ignore")
        image_b64 = base64.b64encode(raw).decode("ascii")
        db.set_screenshot(device_id, image_b64)
        return json_out({"ok": True, "image_b64": image_b64})

    return json_out({"ok": True, "queued": True})


@route("/api/clipboard/<device_id>", method="GET")
def api_clipboard_read(device_id: str):
    db.queue_command(device_id, "clipboard_read", "{}")
    out = run_root("service call clipboard 2")
    db.set_clipboard_text(device_id, out)
    return json_out({"ok": True, "text": out})


@route("/api/clipboard/<device_id>", method="POST")
def api_clipboard_write(device_id: str):
    data = request.json or {}
    text = (data.get("text") or "").strip()
    db.queue_command(device_id, "clipboard_write", json.dumps({"text": text}))
    escaped = text.replace("'", "'\\''")
    out = run_root(f"service call clipboard 3 i32 1 s16 '{escaped}'")
    db.set_clipboard_text(device_id, text)
    return json_out({"ok": True, "output": out})


@route("/api/exec", method=["GET", "POST"])
def api_exec():
    data = request.json or {}
    cmd = (data.get("cmd") or request.query.get("cmd") or "").strip()
    device_id = (data.get("device_id") or "").strip()
    if not cmd:
        return json_out({"ok": False, "error": "empty_cmd"}, 400)

    out = run_root(cmd)
    if device_id:
        db.queue_command(device_id, "console_exec", json.dumps({"cmd": cmd}))
        db.append_console(device_id, "stdout", f"$ {cmd}\n{out}")
    return json_out({"ok": True, "output": out})


@route("/api/start", method="POST")
def api_start():
    data = request.json or {}
    device_id = (data.get("device_id") or "").strip()
    inject_only = bool(data.get("inject_only", False))

    device = db.get_device(device_id)
    if not device:
        return json_out({"ok": False, "error": "device_not_found"}, 404)

    cookie = (device.get("last_cookie") or "").strip()
    link = (device.get("saved_link") or "").strip()

    inject_ok, inject_out = (True, "skip")
    if cookie:
        inject_ok, inject_out = inject_roblox_cookie(cookie)
        db.queue_command(device_id, "inject_cookie", json.dumps({"cookie": cookie}))

    if inject_only:
        return json_out({"ok": inject_ok, "inject_output": inject_out, "started": False})

    if not link:
        return json_out({"ok": False, "error": "empty_link", "inject_output": inject_out}, 400)

    db.queue_command(device_id, "start", json.dumps({"link": link}))
    start_out = run_root(f"am start -a android.intent.action.VIEW -d '{link}' com.roblox.client")
    return json_out({"ok": True, "inject_output": inject_out, "start_output": start_out})


@route("/api/stop", method="POST")
def api_stop():
    data = request.json or {}
    device_id = (data.get("device_id") or "").strip()
    if device_id:
        db.queue_command(device_id, "stop", "{}")
    out = run_root("am force-stop com.roblox.client")
    return json_out({"ok": True, "output": out})


@route("/api/start_all", method="POST")
def api_start_all():
    count = 0
    for device in db.list_devices():
        did = device.get("id")
        if not did:
            continue
        count += 1
        cookie = (device.get("last_cookie") or "").strip()
        link = (device.get("saved_link") or "").strip()
        if cookie:
            db.queue_command(did, "inject_cookie", json.dumps({"cookie": cookie}))
        db.queue_command(did, "start", json.dumps({"link": link}))
    return json_out({"ok": True, "count": count})


@route("/api/stop_all", method="POST")
def api_stop_all():
    count = 0
    for device in db.list_devices():
        did = device.get("id")
        if not did:
            continue
        count += 1
        db.queue_command(did, "stop", "{}")
    return json_out({"ok": True, "count": count})


@route("/api/node/register", method="POST")
def api_node_register():
    data = request.json or {}
    device_id = (data.get("device_id") or "").strip()
    name = (data.get("name") or device_id).strip()
    ip = request.environ.get("REMOTE_ADDR", "")
    if not device_id:
        return json_out({"ok": False, "error": "empty_device_id"}, 400)
    db.upsert_device(device_id, name, ip)
    return json_out({"ok": True})


@route("/api/node/heartbeat", method="POST")
def api_node_heartbeat():
    data = request.json or {}
    device_id = (data.get("device_id") or "").strip()
    if not device_id:
        return json_out({"ok": False, "error": "empty_device_id"}, 400)

    ram = float(data.get("ram", 0.0))
    tcp_count = int(data.get("tcp_count", 0))
    watchdog_enabled = bool(data.get("watchdog_enabled", False))
    ip = request.environ.get("REMOTE_ADDR", "")

    db.upsert_device(device_id, device_id, ip)
    db.update_heartbeat(device_id, ram, tcp_count, "online")
    db.set_watchdog(device_id, watchdog_enabled)
    return json_out({"ok": True, "ts": int(time.time())})


@route("/api/node/<device_id>/commands", method="GET")
def api_node_commands(device_id: str):
    return json_out({"ok": True, "items": db.list_pending_commands(device_id, 50)})


@route("/api/node/command_result", method="POST")
def api_node_command_result():
    data = request.json or {}
    device_id = (data.get("device_id") or "").strip()
    cmd_id = int(data.get("command_id", 0))
    ok = bool(data.get("ok", True))
    output = str(data.get("output", ""))

    if cmd_id:
        db.complete_command(cmd_id)
    if device_id and output:
        db.append_console(device_id, "stdout" if ok else "stderr", output)
    return json_out({"ok": True})


@route("/api/node/clipboard_result/<device_id>", method="POST")
def api_node_clipboard_result(device_id: str):
    data = request.json or {}
    text = str(data.get("text", ""))
    db.set_clipboard_text(device_id, text)
    return json_out({"ok": True})


@route("/api/node/screenshot_result/<device_id>", method="POST")
def api_node_screenshot_result(device_id: str):
    data = request.json or {}
    image_b64 = str(data.get("image_b64", ""))
    db.set_screenshot(device_id, image_b64)
    return json_out({"ok": True})


@route("/api/console/tail/<device_id>", method="GET")
def api_console_tail(device_id: str):
    return json_out({"ok": True, "items": db.get_console_tail(device_id, 150)})


run(host="0.0.0.0", port=8000, debug=False, reloader=False)
