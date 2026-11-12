"""PDOK Import - de motor (stap A: testversie).

Deze motor wordt door de add-on gestart (met de meegeleverde Python) en draait op de achtergrond. Hij start een
kleine webserver op een vrije poort, schrijft die poort naar het bestand dat de add-on opgeeft (--port-file) en
toont een testpagina met een kaart. In de volgende stappen komt hier de echte kaart en de import in.
"""
import argparse
import ctypes
import json
import os
import platform
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # de embeddable Python voegt de scriptmap niet toe

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer  # noqa: E402
import urllib.request  # noqa: E402

START = time.time()
SERVER = {"obj": None}

PAGINA = """<!DOCTYPE html>
<html lang="nl"><head><meta charset="utf-8">
<title>PDOK Import</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
<style>
body{font-family:Segoe UI,Arial,sans-serif;font-size:14px;margin:0;padding:12px;color:#222}
h1{font-size:18px;margin:0 0 8px}
.ok{color:#0a7d2c;font-weight:600}.fout{color:#b00020;font-weight:600}
table{border-collapse:collapse;margin:6px 0 12px}td{padding:2px 12px 2px 0;vertical-align:top}
button{padding:5px 10px;margin-right:6px}
#kaart{height:360px;border:1px solid #999;margin-top:6px}
#uitleg{margin:6px 0;color:#555}
</style></head><body>
<h1>PDOK Import <span id="titelstatus"></span></h1>

<b>1. De motor</b>
<table id="info"><tr><td>Bezig met laden...</td></tr></table>

<b>2. Internet vanuit de motor</b><br>
<button id="inet">Test verbinding met PDOK</button> <span id="inetuit"></span>

<p><b>3. Kaart in dit palet</b></p>
<div id="uitleg">Houd <b>Shift</b> ingedrukt en sleep om een rechthoek te tekenen. Slepen zonder Shift verschuift de kaart.
 <span id="kaartstatus" class="fout">De kaartbibliotheek is nog niet geladen.</span></div>
<div id="kaart"></div>
<div id="rechthoek"></div>

<script>
async function laadInfo() {
  try {
    const r = await fetch('/info'); const d = await r.json();
    const rij = (a, b) => '<tr><td>' + a + '</td><td>' + b + '</td></tr>';
    document.getElementById('info').innerHTML =
      rij('Status', '<span class="ok">de motor draait</span>') +
      rij('Python', d.python) + rij('Programma', d.executable) + rij('Proces-ID', d.pid) +
      rij('Gestart', d.uptime_s + ' s geleden') + rij('Systeem', d.platform) + rij('SSL', d.ssl);
    document.getElementById('titelstatus').innerHTML = '<span class="ok">- motor actief</span>';
  } catch (e) {
    document.getElementById('info').innerHTML = '<tr><td class="fout">Kon de motor niet bereiken: ' + e + '</td></tr>';
  }
}
document.getElementById('inet').onclick = async () => {
  const uit = document.getElementById('inetuit'); uit.textContent = 'bezig...'; uit.className = '';
  try {
    const d = await (await fetch('/internet')).json();
    uit.className = d.ok ? 'ok' : 'fout';
    uit.textContent = d.ok ? ('gelukt: HTTP ' + d.status + ', ' + d.bytes + ' bytes in ' + d.ms + ' ms') : ('mislukt: ' + d.fout);
  } catch (e) { uit.className = 'fout'; uit.textContent = 'mislukt: ' + e; }
};

function startKaart() {
  const st = document.getElementById('kaartstatus');
  if (typeof L === 'undefined') {
    st.textContent = 'De kaartbibliotheek (Leaflet van cdnjs.cloudflare.com) kon niet worden geladen.';
    return;
  }
  st.className = 'ok'; st.textContent = 'Leaflet is geladen.';
  const kaart = L.map('kaart', {boxZoom: false}).setView([51.97, 5.70], 13);
  const tegels = L.tileLayer('https://service.pdok.nl/brt/achtergrondkaart/wmts/v2_0/standaard/EPSG:3857/{z}/{x}/{y}.png',
                             {maxZoom: 19, attribution: 'Kaartgegevens PDOK'}).addTo(kaart);
  let geladen = 0;
  tegels.on('tileload', () => { geladen++; st.textContent = 'Leaflet is geladen; kaarttegels geladen: ' + geladen; });
  tegels.on('tileerror', () => { st.className = 'fout'; st.textContent = 'Kaarttegels van PDOK konden niet worden geladen.'; });
  let slepen = null, vlak = null;
  kaart.on('mousedown', e => {
    if (!e.originalEvent.shiftKey || e.originalEvent.button !== 0) return;
    if (vlak) { kaart.removeLayer(vlak); vlak = null; }
    slepen = e.latlng;
    if (e.originalEvent.preventDefault) e.originalEvent.preventDefault();
  });
  kaart.on('mousemove', e => {
    if (!slepen) return;
    const grenzen = L.latLngBounds(slepen, e.latlng);
    if (vlak) vlak.setBounds(grenzen); else vlak = L.rectangle(grenzen, {color: '#e60000'}).addTo(kaart);
    const b = kaart.distance(grenzen.getSouthWest(), grenzen.getSouthEast());
    const h = kaart.distance(grenzen.getSouthWest(), grenzen.getNorthWest());
    document.getElementById('rechthoek').textContent = 'Rechthoek: ongeveer ' + Math.round(b) + ' x ' + Math.round(h) + ' meter';
  });
  window.addEventListener('mouseup', () => { slepen = null; });
}
laadInfo();
startKaart();
</script></body></html>
"""


def info():
    try:
        import ssl
        ssl_info = ssl.OPENSSL_VERSION
    except Exception as fout:  # noqa: BLE001
        ssl_info = "niet beschikbaar: " + str(fout)
    return {
        "python": sys.version.split()[0], "executable": sys.executable, "pid": os.getpid(),
        "uptime_s": round(time.time() - START, 1), "platform": platform.platform(), "ssl": ssl_info,
    }


def test_internet():
    url = "https://api.pdok.nl/lv/bgt/ogc/v1?f=json"
    t = time.time()
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            data = r.read()
            return {"ok": True, "status": r.status, "bytes": len(data), "ms": round((time.time() - t) * 1000)}
    except Exception as fout:  # noqa: BLE001
        return {"ok": False, "fout": type(fout).__name__ + ": " + str(fout)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):                     # stil: de aanvragen hoeven niet in het logboek
        pass

    def _stuur(self, code, inhoud, soort):
        data = inhoud if isinstance(inhoud, bytes) else inhoud.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", soort)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        pad = self.path.split("?")[0]
        if pad in ("/", "/index.html"):
            self._stuur(200, PAGINA, "text/html; charset=utf-8")
        elif pad == "/info":
            self._stuur(200, json.dumps(info()), "application/json")
        elif pad == "/internet":
            self._stuur(200, json.dumps(test_internet()), "application/json")
        elif pad == "/stop":
            self._stuur(200, json.dumps({"gestopt": True}), "application/json")
            threading.Thread(target=SERVER["obj"].shutdown, daemon=True).start()
        else:
            self._stuur(404, json.dumps({"fout": "onbekend adres"}), "application/json")


def bewaak_ouder(pid):
    """Stopt de motor zodra Archicad (het ouderproces) niet meer bestaat."""
    if not pid or os.name != "nt":
        return
    kernel = ctypes.windll.kernel32
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    handle = kernel.OpenProcess(0x00100000, 0, pid)       # SYNCHRONIZE
    if not handle:
        return

    def wacht():
        kernel.WaitForSingleObject(handle, 0xFFFFFFFF)
        os._exit(0)

    threading.Thread(target=wacht, daemon=True).start()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port-file", required=True, help="bestand waarin de motor zijn poort schrijft")
    ap.add_argument("--parent-pid", type=int, default=0, help="proces-ID van Archicad")
    args = ap.parse_args()

    print("motor start, Python", sys.version.split()[0], "pid", os.getpid(), flush=True)
    bewaak_ouder(args.parent_pid)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)   # poort 0: Windows kiest een vrije poort
    server.daemon_threads = True
    SERVER["obj"] = server
    poort = server.server_address[1]
    tijdelijk = args.port_file + ".tmp"
    with open(tijdelijk, "w", encoding="ascii") as f:
        f.write(str(poort))
    os.replace(tijdelijk, args.port_file)                      # de add-on leest dit bestand pas als het compleet is
    print("motor luistert op poort", poort, flush=True)
    server.serve_forever()
    print("motor gestopt", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        sys.exit(1)
