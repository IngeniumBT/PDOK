"""PDOK Import - de motor.

Deze motor wordt door de add-on gestart (met de meegeleverde Python) en draait op de achtergrond. Hij start een
webserver op een vrije poort, schrijft die poort naar het bestand dat de add-on opgeeft (--port-file) en toont in het
palet de kaart met de import (kaart.py). De import praat met de opdrachten van de add-on via de JSON-interface van
Archicad (--archicad-port, namespace PDOKImport). Op /test staat een testpaneel om die opdrachten los te proberen.
"""
import argparse
import ctypes
import json
import os
import platform
import sys
import tempfile
import threading
import time
import traceback
from urllib.parse import urlparse

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)                                   # de embeddable Python voegt de scriptmap niet toe
sys.path.insert(0, os.path.join(HIER, "lib"))              # meegeleverde pakketten (requests en wat daarbij hoort)

# De gedownloade 3D-gegevens blijven bewaard in een vaste map van de gebruiker, niet per versie van de motor.
os.environ.setdefault("PDOK_CACHE", os.path.join(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir(), "PDOKImport", "cache"))
try:
    os.makedirs(os.environ["PDOK_CACHE"], exist_ok=True)
except OSError:
    pass

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer  # noqa: E402

try:
    import kaart  # noqa: E402
    KAART_FOUT = None
except Exception:  # noqa: BLE001
    kaart = None
    KAART_FOUT = traceback.format_exc()

def _lees_versie():
    try:
        with open(os.path.join(HIER, "versie.txt"), encoding="utf-8") as f:
            return f.read().strip() or "onbekend"
    except OSError:
        return "onbekend"


VERSIE = _lees_versie()
if kaart is not None:
    kaart.VERSIE = VERSIE
START = time.time()
SERVER = {"obj": None}
ARCHICAD = {"port": 0}

TESTPAGINA = r"""<!DOCTYPE html>
<html lang="nl"><head><meta charset="utf-8">
<title>PDOK Import</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{font-family:Segoe UI,Arial,sans-serif;font-size:14px;margin:0;padding:12px;color:#222}
h1{font-size:18px;margin:0 0 6px}h2{font-size:15px;margin:14px 0 6px}
.ok{color:#0a7d2c;font-weight:600}.fout{color:#b00020;font-weight:600}.klein{color:#666}
button{padding:5px 10px;margin:2px 6px 2px 0}
#uit{background:#f4f4f4;border:1px solid #ccc;padding:8px;white-space:pre-wrap;max-height:300px;overflow:auto;font-family:Consolas,monospace;font-size:12px}
#kaart{height:260px;border:1px solid #999;margin-top:6px}
</style></head><body>
<h1>PDOK Import - testpaneel <span id="titelstatus"></span></h1>
<div class="klein" id="info">Bezig met laden...</div>

<h2>Testpaneel groep 1: de opdrachten van de add-on</h2>
<div>
 <button id="b_basis"><b>Draai de basistests</b></button>
 <button id="b_versie">Versie</button>
 <button id="b_geo">Projectlocatie lezen</button>
 <button id="b_bib">Bibliotheek lezen</button>
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
<div><b>Groep 2 (2D):</b> tekent op de laag PDOK_test, rond RD
 x <input id="x0" value="260250" size="8"> y <input id="y0" value="482250" size="8">
 <button id="b_lijn">Test: polylijn tekenen</button>
 <button id="b_vlak">Test: vlak met gat tekenen</button>
 <button id="b_tekst">Test: tekst plaatsen</button>
</div>
<div><b>Groep 3 (3D):</b> bibliotheekobject
 <input id="objnaam" value="Boom stedenbouw 02" size="22"> op hoogte z <input id="z0" value="0" size="6"> m
 <button id="b_obj">Test: object plaatsen</button>
 <button id="b_morph">Test: morph (blok) maken</button>
 <button id="b_mesh">Test: mesh (terrein) maken</button>
</div>
<div class="klein">Om de laatste vier te proberen: teken in Archicad zelf een lijn of een ander element, selecteer het, en kies
 "Selectie op de testlaag zetten". Het krijgt dan de laag PDOK_test en het ID TEST-1, TEST-2...</div>
<div id="uit">De uitvoer van de tests komt hier.</div>

<p><a href="/">&larr; terug naar de kaart</a></p>

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
  b_venster: async () => { const p = await stap('Venster', 'GetCurrentWindowType'); if (p) schrijf('Actief venster: ' + p.currentWindowType + ' | huidige database: ' + (p.currentDatabaseType || '?')); },
  b_plan: async () => { const p = await stap('Naar plattegrond', 'ChangeWindow', {windowType: 'FloorPlan', storyIndex: 0}); if (p) schrijf('Gewisseld naar de plattegrond (verdieping 0). Database gewisseld: ' + p.databaseSwitched + (p.databaseError ? ' (foutcode ' + p.databaseError + ')' : '') + ' | huidige database: ' + (p.currentDatabaseType || '?')); },
  b_3d: async () => { const p = await stap('Naar 3D', 'ChangeWindow', {windowType: '3DModel'}); if (p) schrijf('Gewisseld naar het 3D-venster. Database gewisseld: ' + p.databaseSwitched + (p.databaseError ? ' (foutcode ' + p.databaseError + ')' : '') + ' | huidige database: ' + (p.currentDatabaseType || '?')); },
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
    schrijf('Geselecteerd: ' + d.detailsOfElements.length + '\n  ' + d.detailsOfElements.map(e => e.type + ', laag ' + e.layerIndex + ', ID "' + e.id + '"' + (e.details && e.details.polygonCoordinates ? ' | mesh: ' + e.details.polygonCoordinates.length + ' punten, ' + (e.details.holes || []).length + ' gaten, niveau ' + e.details.level + ', skirt ' + e.details.skirtType + ' (' + e.details.skirtLevel + ')' : '')).join('\n  '));
  },
  b_zet: async () => {
    const laag = await testlaagIndex(); if (laag === null) return;
    const s = await stap('Selectie', 'GetSelectedElements'); if (!s) return;
    if (!(s.elements || []).length) { schrijf('Selecteer eerst een element in Archicad.'); return; }
    const lijst = s.elements.map((e, i) => ({elementId: e.elementId, details: {layerIndex: laag, id: 'TEST-' + (i + 1)}}));
    const p = await stap('Zetten', 'SetDetailsOfElements', {elementsWithDetails: lijst}); if (!p) return;
    const ok = p.executionResults.filter(r => r.success).length;
    const geenId = p.executionResults.filter(r => r.idIgnored).length;
    schrijf('Op laag PDOK_test (index ' + laag + ') gezet: ' + ok + ' van ' + lijst.length + '.' + (geenId ? ' (' + geenId + ' zonder ID: lijnen en polylijnen hebben geen Element-ID)' : '') +
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
async function officieel(command, params) {
  const r = await fetch('/ac', {method: 'POST', body: JSON.stringify({official: command, params: params || {}})});
  return await r.json();
}
async function zoekVulling() {
  const l = await officieel('API.GetAttributesByType', {attributeType: 'Fill'});
  const ids = (l.result && l.result.attributeIds) || [];
  if (!ids.length) return null;
  const d = await officieel('API.GetFillAttributes', {attributeIds: ids});
  const lijst = ((d.result && d.result.attributes) || []).map(a => a.fillAttribute || a);
  for (const fa of lijst) { if (String(fa.subType || '').toLowerCase().startsWith('solid')) return fa.attributeId; }
  return null;
}
function xy() { return [parseFloat(document.getElementById('x0').value) || 0, parseFloat(document.getElementById('y0').value) || 0]; }
async function naarPlattegrond() {
  const p = await stap('Naar plattegrond', 'ChangeWindow', {windowType: 'FloorPlan', storyIndex: 0});
  if (p && p.databaseSwitched === false) schrijf('LET OP: de database werd niet gewisseld (foutcode ' + p.databaseError + ').');
  return p;
}
knop.b_lijn = async () => {
  const laag = await testlaagIndex(); if (laag === null) return;
  if (!(await naarPlattegrond())) return;
  const [x, y] = xy();
  const p = await stap('Polylijn', 'CreatePolylines', {polylinesData: [{floorInd: 0, layerIndex: laag, linePenIndex: 3,
      coordinates: [{x: x, y: y}, {x: x + 20, y: y}, {x: x + 20, y: y + 10}], arcs: []}]});
  if (!p) return;
  const e = (p.elements || [])[0] || {};
  schrijf(e.elementId ? 'Polylijn getekend op laag PDOK_test rond (' + x + ', ' + y + '). Een polylijn heeft in Archicad geen Element-ID.' : 'Polylijn mislukt: ' + JSON.stringify(e));
};
knop.b_vlak = async () => {
  const laag = await testlaagIndex(); if (laag === null) return;
  if (!(await naarPlattegrond())) return;
  const [x, y] = xy(); const vulling = await zoekVulling();
  const vlak = {floorInd: 0, layerIndex: laag, contourPenIndex: 1, id: 'TEST-VLAK',
    foregroundColor: {red: 0.9, green: 0.2, blue: 0.2},
    coordinates: [{x: x, y: y + 20}, {x: x + 20, y: y + 20}, {x: x + 20, y: y + 40}, {x: x, y: y + 40}], arcs: [],
    holes: [{polygonOutline: [{x: x + 7, y: y + 27}, {x: x + 13, y: y + 27}, {x: x + 13, y: y + 33}, {x: x + 7, y: y + 33}]}]};
  if (vulling) vlak.fillId = vulling;
  const p = await stap('Vlak', 'CreateHatches', {hatchesData: [vlak]}); if (!p) return;
  const e = (p.elements || [])[0] || {};
  schrijf(e.elementId ? 'Vlak met gat getekend op laag PDOK_test rond (' + x + ', ' + (y + 20) + '), ID TEST-VLAK' + (vulling ? ', met effen vulling' : ', zonder effen vulling (niet gevonden)') + '.'
                      : 'Vlak mislukt: ' + JSON.stringify(e));
};
knop.b_obj = async () => {
  const laag = await testlaagIndex(); if (laag === null) return;
  const [x, y] = xy(); const z = parseFloat(document.getElementById('z0').value) || 0;
  const naam = (document.getElementById('objnaam').value || '').trim() || 'Boom stedenbouw 02';
  const vraag = {objectsData: [{libraryPartName: naam, coordinates: {x: x + 30, y: y, z: z}, dimensions: {x: 6, y: 6, z: 10},
                                floorIndex: 0, layerIndex: laag, id: 'TEST-OBJ'}]};
  let p = await stap('Object', 'CreateObjects', vraag); if (!p) return;
  let e = (p.elements || [])[0] || {}; let plan = false;
  if (!e.elementId) {                       // lukt het niet in het huidige venster, probeer het dan in de plattegrond
    schrijf('Eerste poging mislukt: ' + JSON.stringify(e.error || e) + ' - nu in de plattegrond.');
    if (!(await naarPlattegrond())) return;
    p = await stap('Object', 'CreateObjects', vraag); if (!p) return;
    e = (p.elements || [])[0] || {}; plan = true;
  }
  schrijf(e.elementId ? 'Object "' + naam + '" geplaatst op (' + (x + 30) + ', ' + y + ') op hoogte ' + z + ' m, ID TEST-OBJ' + (plan ? ' (na wisselen naar de plattegrond)' : ' (in het huidige venster)') + '.'
                      : 'Object mislukt: ' + JSON.stringify(e.error || e));
};
knop.b_tekst = async () => {
  const laag = await testlaagIndex(); if (laag === null) return;
  if (!(await naarPlattegrond())) return;
  const [x, y] = xy();
  const p = await stap('Tekst', 'CreateTexts', {textsData: [{floorIndex: 0, layerIndex: laag, height: 2.5, pen: 3,
      text: 'PDOK test\nregel twee', coordinate: {x: x, y: y + 45}}]}); if (!p) return;
  const e = (p.elements || [])[0] || {};
  schrijf(e.elementId ? 'Tekst met twee regels geplaatst op laag PDOK_test rond (' + x + ', ' + (y + 45) + '), hoogte 2,5.' : 'Tekst mislukt: ' + JSON.stringify(e.error || e));
};
knop.b_morph = async () => {
  const laag = await testlaagIndex(); if (laag === null) return;
  const [x, y] = xy(); const z = parseFloat(document.getElementById('z0').value) || 0;
  const dak = await stap('Oppervlak dak', 'EnsureSurface', {name: 'PDOK_dak', ambientReflection: 70, diffuseReflection: 90, specularReflection: 8,
      surfaceColor: {red: 0.55, green: 0.25, blue: 0.20}}); if (!dak) return;
  const muur = await stap('Oppervlak muur', 'EnsureSurface', {name: 'PDOK_muur', ambientReflection: 70, diffuseReflection: 90, specularReflection: 8,
      surfaceColor: {red: 0.85, green: 0.82, blue: 0.76}}); if (!muur) return;
  const v = [[0,0,0],[10,0,0],[10,10,0],[0,10,0],[0,0,8],[10,0,8],[10,10,8],[0,10,8]].map(c => ({x: c[0], y: c[1], z: c[2]}));
  const vlak = (ids, opp) => ({vertexIds: ids, surfaceId: opp.attributeId});
  const body = {vertices: v, polygons: [vlak([0,3,2,1], muur), vlak([4,5,6,7], dak), vlak([0,1,5,4], muur), vlak([1,2,6,5], muur), vlak([2,3,7,6], muur), vlak([3,0,4,7], muur)]};
  const p = await stap('Morph', 'CreateMorphs', {morphsData: [{basePoint: {x: x + 60, y: y, z: z}, body: body, layerIndex: laag, id: 'TEST-MORPH'}]}); if (!p) return;
  const e = (p.elements || [])[0] || {};
  schrijf(e.elementId ? 'Morph (blok 10 x 10 x 8 m, dak en muren met eigen oppervlak) geplaatst op (' + (x + 60) + ', ' + y + ') op hoogte ' + z + ' m, ID TEST-MORPH.' : 'Morph mislukt: ' + JSON.stringify(e.error || e));
};
knop.b_mesh = async () => {
  const laag = await testlaagIndex(); if (laag === null) return;
  const [x, y] = xy(); const z = parseFloat(document.getElementById('z0').value) || 0;
  const weg = await stap('Oppervlak weg', 'EnsureSurface', {name: 'PDOK_weg', ambientReflection: 70, diffuseReflection: 90, specularReflection: 8,
      surfaceColor: {red: 0.33, green: 0.33, blue: 0.35}}); if (!weg) return;
  const x0 = x + 90, y0 = y, h = (dx, dy) => z + 0.05 * dx + 0.02 * dy;       // een licht hellend terrein
  const punt = (dx, dy) => ({x: x0 + dx, y: y0 + dy, z: h(dx, dy)});
  const mesh = {
    polygonCoordinates: [punt(0, 0), punt(20, 0), punt(20, 20), punt(0, 20)],
    holes: [{polygonCoordinates: [punt(8, 8), punt(12, 8), punt(12, 12), punt(8, 12)]}],
    sublines: [{coordinates: [punt(5, 15)]}, {coordinates: [punt(15, 5)]}],
    level: 0, floorIndex: 0, skirtType: 'SolidBodyWithSkirt', skirtLevel: -(z - 1.0),
    showLines: true, topMaterial: {overridden: true, attributeId: weg.attributeId}, layerIndex: laag, id: 'TEST-MESH'};
  const p = await stap('Mesh', 'CreateMeshes', {meshesData: [mesh]}); if (!p) return;
  const e = (p.elements || [])[0] || {};
  schrijf(e.elementId ? 'Mesh (20 x 20 m, met een gat en twee hoogtepunten, een licht hellend vlak met oppervlak PDOK_weg en een onderkant op ' + (z - 1.0).toFixed(1) + ' m) geplaatst op (' + x0 + ', ' + y0 + '), ID TEST-MESH.' : 'Mesh mislukt: ' + JSON.stringify(e.error || e));
};
knop.b_geo = async () => {
  const t = await stap('Survey Point', 'GetSurveyPointTransformation'); if (!t) return;
  const g = await stap('Georeferentie', 'GetGeoLocation');
  const j = await (await fetch('/projectlocatie')).json();
  const m = t.projectToSurvey.map(w => Math.round(w * 1e6) / 1e6);
  let tekst = 'Omrekening project -> Survey Point-stelsel (3 x 4, rij voor rij):\n  ' + m.slice(0, 4).join('  ') + '\n  ' + m.slice(4, 8).join('  ') + '\n  ' + m.slice(8, 12).join('  ') +
              '\n  ' + j.tekst + (j.waarschuwing ? '\n  LET OP: ' + j.waarschuwing : '');
  if (g) { const sp = g.surveyPoint, gp = sp.geoReferencingParameters;
    tekst += '\n  (IFC-georeferentie, niet gebruikt: E ' + sp.position.eastings + ', N ' + sp.position.northings + ', hoogte ' + sp.position.elevation + ', stelsel ' + (gp.crsName || 'niet ingevuld') + ')'; }
  schrijf(tekst);
};
knop.b_bib = async () => {
  const d = await (await fetch('/bibliotheek?vernieuw=1&q=boom')).json();
  if (!d.beschikbaar) { schrijf('De bibliotheek kon niet worden gelezen: ' + (d.fout || 'onbekende fout')); return; }
  schrijf('Bibliotheek: ' + d.aantal_totaal + ' plaatsbare objecten. Zoeken naar "boom": ' + d.aantal + ' gevonden. Eerste: ' + d.resultaten.slice(0, 6).join(' | '));
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
laadInfo();
</script></body></html>
"""


def info():
    return {"versie": VERSIE, "python": sys.version.split()[0], "executable": sys.executable, "pid": os.getpid(),
            "uptime_s": round(time.time() - START, 1), "platform": platform.platform(),
            "archicad_port": ARCHICAD["port"], "kaart_geladen": kaart is not None,
            "cache": os.environ.get("PDOK_CACHE", "")}


FOUTPAGINA = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>PDOK Import</title></head>
<body style="font-family:Segoe UI,Arial,sans-serif;margin:16px"><h2>De kaart kon niet worden geladen</h2>
<p>De motor draait, maar het onderdeel met de kaart gaf een fout. Stuur deze tekst mee als je hulp vraagt:</p>
<pre style="background:#f4f4f4;padding:8px;white-space:pre-wrap">__FOUT__</pre>
<p><a href="/test">testpaneel</a></p></body></html>"""

BasisHandler = kaart.Handler if kaart is not None else BaseHTTPRequestHandler


class Handler(BasisHandler):
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
        pad = urlparse(self.path).path
        if pad == "/logo.png":
            try:
                with open(os.path.join(HIER, "logo.png"), "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "max-age=86400")
                self.end_headers()
                self.wfile.write(data)
            except OSError:
                self._stuur(404, "", "text/plain")
        elif pad == "/bibliotheek":
            from urllib.parse import parse_qs
            q = parse_qs(urlparse(self.path).query)
            try:
                if kaart is None:
                    raise RuntimeError("het onderdeel met de kaart is niet geladen")
                antwoord = kaart.zoek_bibliotheek((q.get("q") or [""])[0], vernieuw=bool(q.get("vernieuw")))
            except Exception as fout:  # noqa: BLE001
                antwoord = {"beschikbaar": False, "fout": str(fout)}
            self._stuur(200, json.dumps(antwoord), "application/json")
        elif pad == "/projectlocatie":
            try:
                kaart.laad_projectlocatie()
                self._stuur(200, json.dumps(kaart.PROJECT), "application/json")
            except Exception as fout:  # noqa: BLE001
                self._stuur(200, json.dumps({"actief": False, "tekst": "De projectlocatie kon niet worden gelezen: " + str(fout), "waarschuwing": ""}), "application/json")
        elif pad == "/test":
            self._stuur(200, TESTPAGINA, "text/html; charset=utf-8")
        elif pad == "/info":
            self._stuur(200, json.dumps(info()), "application/json")
        elif pad == "/stopmotor":
            self._stuur(200, json.dumps({"gestopt": True}), "application/json")
            threading.Thread(target=SERVER["obj"].shutdown, daemon=True).start()
        elif kaart is None:
            self._stuur(500, FOUTPAGINA.replace("__FOUT__", (KAART_FOUT or "").replace("<", "&lt;")), "text/html; charset=utf-8")
        else:
            super().do_GET()

    def do_POST(self):
        pad = urlparse(self.path).path
        if pad == "/ac":
            lengte = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(lengte) if lengte else b""
            try:
                vraag = json.loads(body.decode("utf-8") or "{}")
                if kaart is None:
                    raise RuntimeError("het onderdeel met de kaart is niet geladen")
                if vraag.get("official"):
                    antwoord = kaart.officieel(vraag["official"], vraag.get("params") or {})
                else:
                    antwoord = kaart.tapir(vraag["command"], vraag.get("params") or {})
            except Exception as fout:  # noqa: BLE001
                antwoord = {"succeeded": False, "error": {"message": type(fout).__name__ + ": " + str(fout)}}
            self._stuur(200, json.dumps(antwoord), "application/json")
        elif pad in ("/terreincontrole", "/terreinwissen"):
            import contextlib
            import io
            lengte = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(lengte) if lengte else b"{}"
            uit = io.StringIO()
            try:
                if kaart is None or getattr(kaart, "terrein", None) is None:
                    raise RuntimeError("het terreinonderdeel is niet geladen")
                with contextlib.redirect_stdout(uit):
                    if pad == "/terreincontrole":
                        g = json.loads(body.decode("utf-8") or "{}")
                        kaart.terrein.diagnose_dekking(kaart, (g["xmin"], g["ymin"], g["xmax"], g["ymax"]))
                    else:
                        kaart.terrein.wis_terrein(kaart)
            except Exception as fout:  # noqa: BLE001
                uit.write("\nMislukt: " + type(fout).__name__ + ": " + str(fout))
            self._stuur(200, json.dumps({"tekst": uit.getvalue()}), "application/json")
        elif kaart is None:
            self._stuur(500, json.dumps({"fout": "het onderdeel met de kaart is niet geladen"}), "application/json")
        else:
            super().do_POST()


def ruim_oude_versies():
    """Verwijdert de uitgepakte motoren van oudere versies uit %LOCALAPPDATA%\\PDOKImport (de map cache blijft). Een motor die nog draait
    (zijn python.exe is dan in gebruik) wordt overgeslagen."""
    try:
        import shutil
        mijn = os.path.dirname(HIER)                       # ...\PDOKImport\<versie>
        basis = os.path.dirname(mijn)
        if os.path.basename(basis).lower() != "pdokimport":
            return
        for naam in os.listdir(basis):
            pad = os.path.join(basis, naam)
            if os.path.normcase(pad) == os.path.normcase(mijn) or naam.lower() == "cache" or not os.path.isdir(pad):
                continue
            exe = os.path.join(pad, "python", "python.exe")
            try:
                if os.path.exists(exe):
                    open(exe, "ab").close()               # lukt niet als die motor nog draait
            except OSError:
                continue
            shutil.rmtree(pad, ignore_errors=True)
    except Exception:  # noqa: BLE001
        pass


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
    if kaart is not None:
        kaart.zet_archicad_poort(args.archicad_port or 19723)

    print("PDOK Import versie", VERSIE, "- motor start, Python", sys.version.split()[0], "pid", os.getpid(), "Archicad-poort", args.archicad_port, flush=True)
    if KAART_FOUT:
        print("LET OP: kaart.py kon niet worden geladen:\n" + KAART_FOUT, flush=True)
    bewaak_ouder(args.parent_pid)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)   # poort 0: Windows kiest een vrije poort
    server.daemon_threads = True
    SERVER["obj"] = server
    poort = server.server_address[1]
    if kaart is not None:
        kaart.SERVER["poort"] = poort
    tijdelijk = args.port_file + ".tmp"
    with open(tijdelijk, "w", encoding="ascii") as f:
        f.write(str(poort))
    os.replace(tijdelijk, args.port_file)                      # de add-on leest dit bestand pas als het compleet is
    print("motor luistert op poort", poort, flush=True)
    threading.Thread(target=ruim_oude_versies, daemon=True).start()
    server.serve_forever()
    print("motor gestopt", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.stdout.flush()
        sys.exit(1)
