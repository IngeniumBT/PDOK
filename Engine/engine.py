"""PDOK Import - de motor (versie 0.3: testpaneel voor groep 1).

Deze motor wordt door de add-on gestart (met de meegeleverde Python) en draait op de achtergrond. Hij start een
kleine webserver op een vrije poort, schrijft die poort naar het bestand dat de add-on opgeeft (--port-file) en toont
een testpaneel waarmee je de opdrachten van de add-on in Archicad kunt uitproberen. De motor roept die opdrachten aan
via de JSON-interface van Archicad (--archicad-port), namespace PDOKImport.
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
ARCHICAD = {"port": 0}
NAMESPACE = "PDOKImport"
TIJDSLIMIET = 900


def ac(naam, parameters=None, namespace=NAMESPACE):
    """Roept een opdracht van de add-on aan via de JSON-interface van Archicad. Geeft het ruwe antwoord."""
    if not ARCHICAD["port"]:
        raise RuntimeError("De add-on gaf de poort van Archicad niet door (--archicad-port).")
    inhoud = {
        "command": "API.ExecuteAddOnCommand",
        "parameters": {
            "addOnCommandId": {"commandNamespace": namespace, "commandName": naam},
            "addOnCommandParameters": parameters or {},
        },
    }
    verzoek = urllib.request.Request(
        f"http://127.0.0.1:{ARCHICAD['port']}", data=json.dumps(inhoud).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(verzoek, timeout=TIJDSLIMIET) as r:
        return json.loads(r.read().decode("utf-8"))


PAGINA = r"""<!DOCTYPE html>
<html lang="nl"><head><meta charset="utf-8">
<title>PDOK Import</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
<style>
body{font-family:Segoe UI,Arial,sans-serif;font-size:14px;margin:0;padding:12px;color:#222}
h1{font-size:18px;margin:0 0 6px}h2{font-size:15px;margin:14px 0 6px}
.ok{color:#0a7d2c;font-weight:600}.fout{color:#b00020;font-weight:600}.klein{color:#666}
button{padding:5px 10px;margin:2px 6px 2px 0}
#uit{background:#f4f4f4;border:1px solid #ccc;padding:8px;white-space:pre-wrap;max-height:300px;overflow:auto;font-family:Consolas,monospace;font-size:12px}
#kaart{height:260px;border:1px solid #999;margin-top:6px}
</style></head><body>
<h1>PDOK Import <span id="titelstatus"></span></h1>
<div class="klein" id="info">Bezig met laden...</div>

<h2>Testpaneel groep 1: de opdrachten van de add-on</h2>
<div>
 <button id="b_basis"><b>Draai de basistests</b></button>
 <button id="b_versie">Versie</button>
 <button id="b_lagen">Lagen tonen</button>
 <button id="b_testlaag">Testlaag maken</button>
</div>
<div>
 <button id="b_venster">Huidig venster</button>
 <button id="b_plan">Naar plattegrond</button>
 <button id="b_3d">Naar 3D</button>
 <button id="b_tel">Tel elementen</button>
</div>
<div>
 <button id="b_sel">Selectie lezen</button>
 <button id="b_zet">Selectie op de testlaag zetten</button>
 <button id="b_toon">Elementen op de testlaag tonen</button>
 <button id="b_wis">Elementen op de testlaag verwijderen</button>
</div>
<div class="klein">Om de laatste vier te proberen: teken in Archicad zelf een lijn of een ander element, selecteer het, en kies
 "Selectie op de testlaag zetten". Het krijgt dan de laag PDOK_test en het ID TEST-1, TEST-2...</div>
<div id="uit">De uitvoer van de tests komt hier.</div>

<h2>Kaart in dit palet</h2>
<div class="klein">Houd <b>Shift</b> ingedrukt en sleep om een rechthoek te tekenen. <span id="kaartstatus" class="fout">De kaartbibliotheek is nog niet geladen.</span></div>
<div id="kaart"></div>
<div id="rechthoek" class="klein"></div>

<script>
const TYPEN = ['Wall','Column','Beam','Window','Door','Object','Lamp','Slab','Roof','Mesh','Zone','Shell','Morph','Line','Arc','Polyline','Spline','Text','Hatch'];
const uit = document.getElementById('uit');
function tijd() { return new Date().toLocaleTimeString(); }
function schrijf(t) { uit.textContent = (uit.textContent.startsWith('De uitvoer') ? '' : uit.textContent + '\n') + '[' + tijd() + '] ' + t; uit.scrollTop = uit.scrollHeight; }
async function ac(command, params) {
  const r = await fetch('/ac', {method: 'POST', body: JSON.stringify({command: command, params: params || {}})});
  return await r.json();
}
function pak(d) { return (d.result && d.result.addOnCommandResponse) || {}; }
function fout(d) {
  if (d.succeeded === false) return JSON.stringify(d.error || d);
  const p = pak(d); if (p.error) return JSON.stringify(p.error);
  return null;
}
async function stap(naam, command, params) {
  const d = await ac(command, params); const f = fout(d);
  if (f) { schrijf(naam + ': MISLUKT ' + f); return null; }
  return pak(d);
}
async function testlaagIndex() {
  const p = await stap('Testlaag', 'EnsureLayer', {name: 'PDOK_test', folder: ['PDOK Import']});
  return p ? p.index : null;
}

const knop = {
  b_versie: async () => { const p = await stap('Versie', 'GetAddOnVersion'); if (p) schrijf('Versie: ' + p.version + ' (bouw ' + p.buildCommit + ')'); },
  b_lagen: async () => {
    const p = await stap('Lagen', 'GetLayers'); if (!p) return;
    const namen = (p.layers || []).map(l => l.index + ' ' + l.name);
    schrijf('Lagen: ' + namen.length + '\n  ' + namen.slice(0, 30).join('\n  ') + (namen.length > 30 ? '\n  ...' : ''));
  },
  b_testlaag: async () => {
    const p = await stap('Testlaag', 'EnsureLayer', {name: 'PDOK_test', folder: ['PDOK Import']});
    if (p) schrijf('Laag PDOK_test: index ' + p.index + (p.created ? ' (nieuw gemaakt, in de map PDOK Import)' : ' (bestond al)'));
  },
  b_venster: async () => { const p = await stap('Venster', 'GetCurrentWindowType'); if (p) schrijf('Actief venster: ' + p.currentWindowType); },
  b_plan: async () => { const p = await stap('Naar plattegrond', 'ChangeWindow', {windowType: 'FloorPlan', storyIndex: 0}); if (p) schrijf('Gewisseld naar de plattegrond (verdieping 0).'); },
  b_3d: async () => { const p = await stap('Naar 3D', 'ChangeWindow', {windowType: '3DModel'}); if (p) schrijf('Gewisseld naar het 3D-venster.'); },
  b_tel: async () => {
    const regels = [];
    for (const t of TYPEN) {
      const p = await stap('Tel ' + t, 'GetElementsByType', {elementType: t}); if (!p) return;
      if ((p.elements || []).length) regels.push(t + ': ' + p.elements.length);
    }
    schrijf('Elementen in het actieve venster:\n  ' + (regels.length ? regels.join('\n  ') : '(geen)'));
  },
  b_sel: async () => {
    const s = await stap('Selectie', 'GetSelectedElements'); if (!s) return;
    if (!(s.elements || []).length) { schrijf('Er is niets geselecteerd in Archicad.'); return; }
    const d = await stap('Details', 'GetDetailsOfElements', {elements: s.elements}); if (!d) return;
    schrijf('Geselecteerd: ' + d.detailsOfElements.length + '\n  ' + d.detailsOfElements.map(e => e.type + ', laag ' + e.layerIndex + ', ID "' + e.id + '"').join('\n  '));
  },
  b_zet: async () => {
    const laag = await testlaagIndex(); if (laag === null) return;
    const s = await stap('Selectie', 'GetSelectedElements'); if (!s) return;
    if (!(s.elements || []).length) { schrijf('Selecteer eerst een element in Archicad.'); return; }
    const lijst = s.elements.map((e, i) => ({elementId: e.elementId, details: {layerIndex: laag, id: 'TEST-' + (i + 1)}}));
    const p = await stap('Zetten', 'SetDetailsOfElements', {elementsWithDetails: lijst}); if (!p) return;
    const ok = p.executionResults.filter(r => r.success).length;
    schrijf('Op laag PDOK_test (index ' + laag + ') gezet: ' + ok + ' van ' + lijst.length + '.' +
            p.executionResults.filter(r => !r.success).map(r => '\n  mislukt: ' + JSON.stringify(r.error)).join(''));
  },
  b_toon: async () => {
    const laag = await testlaagIndex(); if (laag === null) return;
    const p = await stap('Tonen', 'GetDetailsOfElements', {types: TYPEN, layerIndices: [laag]}); if (!p) return;
    const l = p.detailsOfElements || [];
    schrijf('Op laag PDOK_test: ' + l.length + (l.length ? '\n  ' + l.map(e => e.type + ', ID "' + e.id + '"').join('\n  ') : ''));
  },
  b_wis: async () => {
    const b = document.getElementById('b_wis');
    if (!b.dataset.klaar) {
      b.dataset.klaar = '1'; b.textContent = 'Klik nogmaals om te verwijderen';
      setTimeout(() => { delete b.dataset.klaar; b.textContent = 'Elementen op de testlaag verwijderen'; }, 5000); return;
    }
    delete b.dataset.klaar; b.textContent = 'Elementen op de testlaag verwijderen';
    const laag = await testlaagIndex(); if (laag === null) return;
    const l = await stap('Zoeken', 'GetDetailsOfElements', {types: TYPEN, layerIndices: [laag]}); if (!l) return;
    if (!l.detailsOfElements.length) { schrijf('Er staat niets op de laag PDOK_test.'); return; }
    const p = await stap('Verwijderen', 'DeleteElements', {elements: l.detailsOfElements.map(e => ({elementId: e.elementId}))});
    if (p) schrijf('Verwijderd: ' + p.deleted + ' (niet gevonden: ' + p.notFound + '). Controleer in Archicad dat ze weg zijn en dat Ongedaan maken ze terugbrengt.');
  },
};
knop.b_basis = async () => {
  schrijf('--- basistests ---');
  await knop.b_versie(); await knop.b_lagen(); await knop.b_testlaag(); await knop.b_venster(); await knop.b_tel();
  schrijf('--- einde basistests ---');
};
for (const id in knop) { document.getElementById(id).onclick = () => knop[id]().catch(e => schrijf(id + ': fout ' + e)); }

async function laadInfo() {
  try {
    const d = await (await fetch('/info')).json();
    document.getElementById('info').textContent = 'Motor: Python ' + d.python + ', proces ' + d.pid + ', Archicad-poort ' + d.archicad_port + '.';
    document.getElementById('titelstatus').innerHTML = '<span class="ok">- motor actief</span>';
  } catch (e) { document.getElementById('info').innerHTML = '<span class="fout">Kon de motor niet bereiken: ' + e + '</span>'; }
}
function startKaart() {
  const st = document.getElementById('kaartstatus');
  if (typeof L === 'undefined') { st.textContent = 'De kaartbibliotheek kon niet worden geladen.'; return; }
  st.className = 'ok'; st.textContent = 'Leaflet is geladen.';
  const kaart = L.map('kaart', {boxZoom: false}).setView([51.97, 5.70], 13);
  L.tileLayer('https://service.pdok.nl/brt/achtergrondkaart/wmts/v2_0/standaard/EPSG:3857/{z}/{x}/{y}.png', {maxZoom: 19, attribution: 'Kaartgegevens PDOK'}).addTo(kaart);
  let slepen = null, vlak = null;
  kaart.on('mousedown', e => { if (!e.originalEvent.shiftKey || e.originalEvent.button !== 0) return; if (vlak) { kaart.removeLayer(vlak); vlak = null; } slepen = e.latlng; if (e.originalEvent.preventDefault) e.originalEvent.preventDefault(); });
  kaart.on('mousemove', e => {
    if (!slepen) return;
    const g = L.latLngBounds(slepen, e.latlng);
    if (vlak) vlak.setBounds(g); else vlak = L.rectangle(g, {color: '#e60000'}).addTo(kaart);
    document.getElementById('rechthoek').textContent = 'Rechthoek: ongeveer ' + Math.round(kaart.distance(g.getSouthWest(), g.getSouthEast())) + ' x ' + Math.round(kaart.distance(g.getSouthWest(), g.getNorthWest())) + ' meter';
  });
  window.addEventListener('mouseup', () => { slepen = null; });
}
laadInfo();
startKaart();
</script></body></html>
"""


def info():
    return {"python": sys.version.split()[0], "executable": sys.executable, "pid": os.getpid(),
            "uptime_s": round(time.time() - START, 1), "platform": platform.platform(),
            "archicad_port": ARCHICAD["port"]}


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
        elif pad == "/stop":
            self._stuur(200, json.dumps({"gestopt": True}), "application/json")
            threading.Thread(target=SERVER["obj"].shutdown, daemon=True).start()
        else:
            self._stuur(404, json.dumps({"fout": "onbekend adres"}), "application/json")

    def do_POST(self):
        pad = self.path.split("?")[0]
        lengte = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(lengte) if lengte else b""
        if pad != "/ac":
            self._stuur(404, json.dumps({"fout": "onbekend adres"}), "application/json")
            return
        try:
            vraag = json.loads(body.decode("utf-8") or "{}")
            antwoord = ac(vraag["command"], vraag.get("params") or {})
        except Exception as fout:  # noqa: BLE001
            antwoord = {"succeeded": False, "error": {"message": type(fout).__name__ + ": " + str(fout)}}
        self._stuur(200, json.dumps(antwoord), "application/json")


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
    ap.add_argument("--archicad-port", type=int, default=0, help="poort van de JSON-interface van Archicad")
    args = ap.parse_args()
    ARCHICAD["port"] = args.archicad_port

    print("motor start, Python", sys.version.split()[0], "pid", os.getpid(), "Archicad-poort", args.archicad_port, flush=True)
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
