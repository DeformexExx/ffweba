from bottle import route, run, request, response
import subprocess
import html
import json

from database import db


def run_root(cmd: str) -> str:
    return subprocess.getoutput(f"su -c '{cmd}'")


@route('/')
def index():
    devices = db.list_devices()

    cards = []
    for d in devices:
        did = d.get('id', '')
        name = d.get('name', did)
        status = d.get('status', 'offline')
        dot = '🟢' if status == 'online' else '🔴'
        tcp = d.get('tcp_count', 0)
        ram = d.get('ram', 0)
        link = d.get('saved_link', '') or ''
        watchdog = 'checked' if int(d.get('watchdog_enabled', 0)) == 1 else ''
        screenshot = d.get('screenshot_b64', '') or ''

        img_html = ''
        if screenshot:
            img_html = f"<img src='data:image/png;base64,{screenshot}' style='width:100%;border:1px solid #0f0;margin-top:8px;'/>"

        card = f"""
        <div class='card'>
            <h3>{html.escape(name)} {dot}</h3>
            <p>ID: {html.escape(did)}</p>
            <p>RAM: {float(ram):.1f}% | TCP: {int(tcp)}</p>

            <form action='/setlink' method='post'>
                <input type='hidden' name='device_id' value='{html.escape(did)}'/>
                <input name='link' value='{html.escape(link)}' placeholder='roblox:// or private link' style='width:100%;margin-bottom:6px;'/>
                <button type='submit'>SAVE LINK</button>
            </form>

            <p style='margin-top:8px;'>
                <label>
                    <input type='checkbox' onchange="fetch('/watchdog?device_id={html.escape(did)}&enabled='+(this.checked?1:0))" {watchdog}/>
                    WATCHDOG
                </label>
            </p>

            <button onclick="fetch('/start?device_id={html.escape(did)}').then(()=>location.reload())">START</button>
            <button onclick="fetch('/stop?device_id={html.escape(did)}').then(()=>location.reload())">STOP</button>
            <button onclick="fetch('/screenshot?device_id={html.escape(did)}').then(()=>location.reload())">CAPTURE</button>
            <button onclick="location.href='/console?device_id={html.escape(did)}'">CONSOLE</button>
            {img_html}
        </div>
        """
        cards.append(card)

    cards_html = ''.join(cards) if cards else "<p>NO DEVICES REGISTERED</p>"

    return f"""
    <html>
    <head>
        <title>VEX AEGIS PANEL</title>
        <meta name='viewport' content='width=device-width,initial-scale=1'/>
        <style>
            body {{ background: #000; color: #0f0; font-family: monospace; padding: 20px; }}
            .card {{ border: 1px solid #0f0; padding: 15px; margin: 10px; width: 320px; display: inline-block; vertical-align: top; }}
            button {{ background: #0f0; color: #000; border: none; padding: 10px; cursor: pointer; font-weight: bold; margin: 2px 0; width: 100%; }}
            input, textarea {{ background: #111; color: #0f0; border: 1px solid #0f0; padding: 5px; }}
            .top {{ margin-bottom: 16px; }}
        </style>
    </head>
    <body>
        <h1>[ AEGIS WEB CONTROL ]</h1>
        <div class='top'>
            <button onclick="fetch('/start_all').then(()=>location.reload())" style='max-width:220px;'>START ALL</button>
            <button onclick="fetch('/stop_all').then(()=>location.reload())" style='max-width:220px;'>STOP ALL</button>
            <button onclick="location.href='/getlink'" style='max-width:220px;'>GET LINK (LOCAL)</button>
        </div>
        {cards_html}
    </body>
    </html>
    """


@route('/exec')
def execute():
    cmd = request.query.cmd or ''
    result = run_root(cmd)
    response.content_type = 'application/json'
    return json.dumps({'status': 'ok', 'output': result})


@route('/getlink')
def get_link():
    cmd = "dumpsys activity recents | grep -oE 'https://auth.platorelay.com/a\\?d=[^ ]+' | head -n 1"
    link = run_root(cmd)
    return f"<h1>LINK:</h1><p>{html.escape(link)}</p><a href='/'>BACK</a>"


@route('/setlink', method='POST')
def set_link():
    device_id = request.forms.get('device_id', '').strip()
    link = request.forms.get('link', '').strip()
    if device_id:
        db.set_link(device_id, link)
    return "<meta http-equiv='refresh' content='0; url=/' />"


@route('/watchdog')
def set_watchdog():
    device_id = request.query.device_id or ''
    enabled = str(request.query.enabled or '0') in ('1', 'true', 'True', 'on')
    if device_id:
        db.set_watchdog(device_id, enabled)
        db.queue_command(device_id, 'set_watchdog', json.dumps({'enabled': enabled}))
    response.content_type = 'application/json'
    return json.dumps({'ok': True})


@route('/start')
def start_device():
    device_id = request.query.device_id or ''
    if device_id:
        device = db.get_device(device_id)
        if device:
            cookie = (device.get('last_cookie') or '').strip()
            link = (device.get('saved_link') or '').strip()
            if cookie:
                db.queue_command(device_id, 'inject_cookie', json.dumps({'cookie': cookie}))
            db.queue_command(device_id, 'start', json.dumps({'link': link}))
    response.content_type = 'application/json'
    return json.dumps({'ok': True})


@route('/stop')
def stop_device():
    device_id = request.query.device_id or ''
    if device_id:
        db.queue_command(device_id, 'stop', '{}')
    response.content_type = 'application/json'
    return json.dumps({'ok': True})


@route('/start_all')
def start_all():
    for d in db.list_devices():
        did = d.get('id')
        if not did:
            continue
        cookie = (d.get('last_cookie') or '').strip()
        link = (d.get('saved_link') or '').strip()
        if cookie:
            db.queue_command(did, 'inject_cookie', json.dumps({'cookie': cookie}))
        db.queue_command(did, 'start', json.dumps({'link': link}))
    response.content_type = 'application/json'
    return json.dumps({'ok': True})


@route('/stop_all')
def stop_all():
    for d in db.list_devices():
        did = d.get('id')
        if did:
            db.queue_command(did, 'stop', '{}')
    response.content_type = 'application/json'
    return json.dumps({'ok': True})


@route('/screenshot')
def screenshot():
    device_id = request.query.device_id or ''
    if device_id:
        db.queue_command(device_id, 'screenshot', '{}')
    response.content_type = 'application/json'
    return json.dumps({'ok': True})


@route('/console')
def console_page():
    device_id = request.query.device_id or ''
    lines = db.get_console_tail(device_id, 250) if device_id else []
    text = '\n'.join([f"[{x.get('stream','stdout')}] {x.get('line','')}" for x in lines])
    return f"""
    <html><head><title>Console {html.escape(device_id)}</title>
    <style>
      body {{ background:#000;color:#0f0;font-family:monospace;padding:20px; }}
      pre {{ border:1px solid #0f0;background:#050505;padding:10px;white-space:pre-wrap; }}
      input {{ width:80%;background:#111;color:#0f0;border:1px solid #0f0;padding:8px; }}
      button {{ background:#0f0;color:#000;border:none;padding:8px 12px;font-weight:bold; }}
    </style></head><body>
      <h2>CONSOLE :: {html.escape(device_id)}</h2>
      <pre>{html.escape(text)}</pre>
      <form action='/console_exec' method='post'>
        <input type='hidden' name='device_id' value='{html.escape(device_id)}'/>
        <input name='cmd' placeholder='su -c command'/>
        <button type='submit'>EXEC</button>
      </form>
      <p><a href='/' style='color:#0f0;'>BACK</a></p>
    </body></html>
    """


@route('/console_exec', method='POST')
def console_exec():
    device_id = request.forms.get('device_id', '').strip()
    cmd = request.forms.get('cmd', '').strip()
    if device_id and cmd:
        db.queue_command(device_id, 'console_exec', json.dumps({'cmd': cmd}))
    return f"<meta http-equiv='refresh' content='0; url=/console?device_id={html.escape(device_id)}' />"


run(host='0.0.0.0', port=8000)
