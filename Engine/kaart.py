import atexit
import heapq
import json
import math
import os
import shutil
import sys
import tempfile
import uuid
import webbrowser
import zipfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import requests
try:
    import plan_import  # bestemmingsplannen (plan_import.py moet naast kaart.py staan)
except ImportError:
    plan_import = None

try:
    import drie_d  # 3D-gebouwen (drie_d.py moet naast kaart.py staan)
except ImportError:
    drie_d = None

try:
    import terrein  # 3D-terrein (terrein.py en drie_d.py moeten naast kaart.py staan)
except ImportError:
    terrein = None

try:
    import bomen  # bomen op de BGT-vegetatiepunten (bomen.py, met terrein.py en drie_d.py, naast kaart.py)
except ImportError:
    bomen = None

SERVER_POORT = 8765
RD = "http://www.opengis.net/def/crs/EPSG/0/28992"
MAX_ZIJDE = 3000  # meter: de grootste zijde van een importgebied; grotere gebieden worden in blokken verwerkt
BLOK_2D = 500  # meter: zo groot zijn de blokken voor de 2D-lagen
MAX_PAGINAS = 200  # pagina's van 1000 objecten per laag; daarna melden we dat het is afgekapt
GEOREFERENTIE = "rd"  # "rd": RD-coördinaten rechtstreeks; "lokaal": midden van het gebied op (0,0)
MAPNAAM = "PDOK Import"  # map in de laaginstellingen waarin nieuwe lagen komen

# Een bestemmingsplan (gml of zip met gml) kies je in het kaartvenster. De browser stuurt het
# bestand naar dit programma, dat het tijdelijk bewaart in een eigen map. Die map wordt
# opgeruimd als je het programma afsluit.
MAX_PLAN_MB = 300
UPLOAD_MAP = tempfile.mkdtemp(prefix="pdok_archicad_")
atexit.register(lambda: shutil.rmtree(UPLOAD_MAP, ignore_errors=True))
PLANNEN = {}  # token -> {"pad": pad naar de gml, "naam": oorspronkelijke bestandsnaam}

BRONNEN = {
    "bgt": {
        "naam": "BGT",
        "basis": "https://api.pdok.nl/lv/bgt/ogc/v1",
        "voorvoegsel": "BGT_",
    },
    "kad": {
        "naam": "Kadaster",
        "basis": "https://api.pdok.nl/kadaster/brk-kadastrale-kaart/ogc/v1",
        "voorvoegsel": "KAD_",
    },
}
KAD_STANDAARD_AAN = {"perceel"}
KAD_UITGESLOTEN = {"nummeraanduidingreeks", "openbareruimtenaam", "kadastralegrens"}

# Standaard pen per laag (in het kaartvenster per import aan te passen).
# Bij lijnen is dit de lijnpen, bij vlakken de randpen. Lagen die hier niet staan
# krijgen de standaardpen.
STANDAARD_PENNEN = {"kad:perceel": 3, "kad:bebouwing": 43}
BGT_STANDAARDPEN = 1  # pen voor alle BGT-lagen, tenzij je in het venster iets anders invult

# Perceelnummers als tekst (bij Kadaster: Perceel). In het formaat mag je {sectie},
# {perceelnummer} en {gemeente} gebruiken, bijvoorbeeld "{perceelnummer}" voor alleen het nummer.
PERCEELTEKST_FORMAAT = "{sectie} {perceelnummer}"
PERCEELTEKST_HOOGTE = 2.5  # hoogte van de tekst, zoals CreateTexts die verwacht
PERCEELTEKSTPEN = 3        # pen van de tekst, als je in het venster geen pen voor de percelen kiest
PERCEELTEKSTLAAG = "KAD_perceelnummer"

# Lagen die we niet aanbieden: historisch (leeg sinds 2020) en alleen labels
UITGESLOTEN = {
    "ongeclassificeerdobject", "overigescheiding",
    "openbareruimtelabel", "pand_nummeraanduiding",
}
# Bruggen en tunnels liggen per definitie niet op maaiveld
ALTIJD_ALLE_NIVEAUS = {"overbruggingsdeel", "tunneldeel"}
STANDAARD_AAN = {"pand", "wegdeel", "waterdeel"}
PUNT_STRAAL = 0.2  # meter, grootte van het symbool voor puntobjecten
CONTOURPEN = 1  # randpen van vlakken als er in het venster geen pen is gekozen

# Vulkleur (rood, groen, blauw van 0-255) per BGT-laag met vlakken.
# Lagen die hier niet staan houden de standaardkleur van Archicad.
KLEUREN = {
    "pand": (214, 120, 110),
    "gebouwinstallatie": (200, 140, 125),
    "overigbouwwerk": (190, 150, 140),
    "wegdeel": (200, 200, 200),
    "ondersteunendwegdeel": (170, 175, 150),
    "weginrichtingselement_vlak": (240, 200, 100),
    "onbegroeidterreindeel": (226, 212, 175),
    "begroeidterreindeel": (165, 210, 140),
    "vegetatieobject_vlak": (110, 170, 100),
    "waterdeel": (140, 190, 235),
    "ondersteunendwaterdeel": (175, 210, 235),
    "scheiding_vlak": (120, 120, 120),
    "kunstwerkdeel_vlak": (160, 140, 175),
    "overbruggingsdeel": (150, 150, 175),
    "tunneldeel": (130, 130, 130),
    "functioneelgebied": (235, 228, 190),
}

# Terugvaller als er geen effen vulling wordt gevonden. Dit is de vulling uit jouw
# project; in een ander project moet dit een eigen effen vulling zijn.
STANDAARD_EFFEN_VULLING = {"guid": "15EA2209-88BC-4272-8954-87ECD199FFD9"}


# ---------------------------------------------------------------- Archicad

_POORT = {"n": None}
TIJDSLIMIET = (10, 900)   # seconden: (verbinden, wachten op een antwoord van Archicad)


NAMESPACE = "PDOKImport"   # de opdrachten van de add-on zelf (niet meer van Tapir)

# Wat de add-on al kan. Wat nog niet beschikbaar is, wordt in de pagina uitgeschakeld en overgeslagen.
BESCHIKBAAR = {"tekst": True, "gebouwen": False, "terrein": False, "bomen": True}


def zet_archicad_poort(poort):
    """De poort van Archicads JSON-interface; de add-on geeft die door aan de motor."""
    _POORT["n"] = int(poort)


def archicad_poort():
    if _POORT["n"] is None:
        _POORT["n"] = 19723                       # de standaardpoort van Archicad
    return _POORT["n"]


def _post(json_inhoud, naam):
    """Stuurt een aanvraag naar Archicad, met een tijdslimiet en een tweede poging als de verbinding weg is."""
    for poging in (1, 2):
        try:
            return requests.post(f"http://127.0.0.1:{archicad_poort()}", json=json_inhoud, timeout=TIJDSLIMIET).json()
        except requests.exceptions.ReadTimeout:
            raise RuntimeError(
                f"Archicad antwoordt niet binnen {TIJDSLIMIET[1] // 60} minuten op '{naam}'. Is Archicad bezig, of "
                f"wacht er een venster of dialoog in Archicad op een antwoord? Sluit die en probeer het opnieuw.")
        except requests.exceptions.ConnectionError:
            if poging == 2:
                raise RuntimeError("Geen verbinding met Archicad. Staat Archicad nog open?")


def tapir(naam, parameters=None):
    """Roept een opdracht van de add-on aan (de naam is een erfenis uit de tijd van Tapir)."""
    return _post({
        "command": "API.ExecuteAddOnCommand",
        "parameters": {
            "addOnCommandId": {"commandNamespace": NAMESPACE, "commandName": naam},
            "addOnCommandParameters": parameters or {},
        },
    }, naam)


def pak(antwoord):
    return antwoord.get("result", {}).get("addOnCommandResponse", {})


def officieel(commando, parameters=None):
    return _post({"command": commando, "parameters": parameters or {}}, commando)


def alle_lagen():
    lagen = pak(tapir("GetLayers")).get("layers", [])
    return {laag["name"]: laag for laag in lagen}


def zorg_voor_laag(naam):
    """Geeft het laagnummer. Een nieuwe laag wordt in de map MAPNAAM gezet."""
    r = tapir("EnsureLayer", {"name": naam, "folder": [MAPNAAM]})
    if not r.get("succeeded") or "index" not in pak(r):
        raise RuntimeError(f"De laag {naam} kon niet worden aangemaakt: {str(r.get('error', r))[:300]}")
    return pak(r)["index"]


def zoek_volle_vulling():
    """Zoekt een effen vulling in het project, zodat de kleur zichtbaar is."""
    try:
        lijst = officieel("API.GetAttributesByType", {"attributeType": "Fill"})
        ids = lijst.get("result", {}).get("attributeIds", [])
        d = officieel("API.GetFillAttributes", {"attributeIds": ids})
        attributen = [a.get("fillAttribute", a)
                      for a in d.get("result", {}).get("attributes", [])]
        for fa in attributen:
            if str(fa.get("subType", "")).lower().startswith("solid"):
                return fa["attributeId"]
        for fa in attributen:
            if "solid" in json.dumps(fa).lower():
                return fa["attributeId"]
    except Exception as fout:
        print("Effen vulling zoeken mislukt:", fout)
    return None


# -------------------------------------------------------------------- PDOK

def haal_lagenlijst():
    lijst = []
    for bron, cfg in BRONNEN.items():
        try:
            r = requests.get(f"{cfg['basis']}/collections",
                             params={"f": "json"}, timeout=60)
            r.raise_for_status()
            collecties = r.json()["collections"]
        except Exception as fout:
            print(f"Lagenlijst van {cfg['naam']} ophalen mislukt: {fout}")
            continue
        deel = []
        for c in collecties:
            if bron == "bgt" and c["id"] in UITGESLOTEN:
                continue
            if bron == "kad" and c["id"] in KAD_UITGESLOTEN:
                continue
            sleutel = f"{bron}:{c['id']}"
            aan = ((bron == "bgt" and c["id"] in STANDAARD_AAN)
                   or (bron == "kad" and c["id"] in KAD_STANDAARD_AAN))
            deel.append({
                "id": sleutel,
                "bron": bron,
                "bronnaam": cfg["naam"],
                "naam": c.get("title", c["id"]),
                "title": f"{cfg['naam']}: {c.get('title', c['id'])}",
                "aan": aan,
                "pen": STANDAARD_PENNEN.get(sleutel, BGT_STANDAARDPEN if bron == "bgt" else None),
            })
        deel.sort(key=lambda l: l["title"].lower())
        lijst += deel
    return lijst


def controleer_rd(features, bron, laag):
    """Stopt als de coordinaten er niet uitzien als RD (meters) maar als graden."""
    for feature in features[:1]:
        geo = feature.get("geometry")
        if not geo:
            continue
        c = geo["coordinates"]
        while isinstance(c, list) and c and isinstance(c[0], list):
            c = c[0]
        if isinstance(c, list) and c and abs(c[0]) < 1000:
            raise ValueError(
                f"{bron}:{laag} levert geen RD-coordinaten ({c[:2]}), laag overgeslagen")


def haal_features(bron, laag, x_min, y_min, x_max, y_max):
    url = f"{BRONNEN[bron]['basis']}/collections/{laag}/items"
    params = {
        "f": "json",
        "limit": 1000,
        "bbox": f"{x_min},{y_min},{x_max},{y_max}",
        "bbox-crs": RD,
        "crs": RD,
    }
    features = []
    afgekapt = True
    for _ in range(MAX_PAGINAS):
        r = requests.get(url, params=params, timeout=60)
        if r.status_code == 400 and params and params.get("limit") == 1000:
            params["limit"] = 100  # sommige API's staan minder per pagina toe
            r = requests.get(url, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        features += data["features"]
        volgende = next(
            (l["href"] for l in data.get("links", []) if l.get("rel") == "next"),
            None,
        )
        if not volgende:
            afgekapt = False
            break
        url, params = volgende, None
    if afgekapt:
        print(f"   LET OP: {bron}:{laag} is afgekapt na {len(features)} objecten ({MAX_PAGINAS} pagina's); "
              f"kies een kleiner gebied, anders ontbreekt er iets.")
    controleer_rd(features, bron, laag)
    return features


# ---------------------------------------------------------------- Geometrie

def schoon(coords, midden_x, midden_y):
    """Trek het midden af en verwijder punten die (bijna) op elkaar liggen."""
    punten = []
    for p in coords:
        x, y = p[0] - midden_x, p[1] - midden_y
        if punten and abs(x - punten[-1]["x"]) < 0.001 and abs(y - punten[-1]["y"]) < 0.001:
            continue
        punten.append({"x": x, "y": y})
    return punten


def schoon_vlak(ring, midden_x, midden_y):
    """Ring voor een vulling: Archicad wil GEEN herhaald eindpunt."""
    punten = schoon(ring, midden_x, midden_y)
    while (len(punten) > 1
           and abs(punten[0]["x"] - punten[-1]["x"]) < 0.001
           and abs(punten[0]["y"] - punten[-1]["y"]) < 0.001):
        punten.pop()
    return punten


def oppervlak(punten):
    som = 0.0
    for k in range(len(punten)):
        a = punten[k]
        b = punten[(k + 1) % len(punten)]
        som += a["x"] * b["y"] - b["x"] * a["y"]
    return abs(som) / 2


def punt_symbool(coord, midden_x, midden_y):
    x, y = coord[0] - midden_x, coord[1] - midden_y
    punten = [
        {"x": x + PUNT_STRAAL * math.cos(k * math.pi / 4),
         "y": y + PUNT_STRAAL * math.sin(k * math.pi / 4)}
        for k in range(8)
    ]
    punten.append(dict(punten[0]))
    return punten


def maak_elementen(features, midden_x, midden_y, alle_niveaus):
    """Geeft (vlakken, lijnen): vlakken worden vullingen, de rest polylijnen."""
    vlakken = []
    lijnen = []

    def voeg_vlak_toe(polygoon):
        buiten = schoon_vlak(polygoon[0], midden_x, midden_y)
        if len(buiten) < 3 or oppervlak(buiten) < 0.0001:
            return
        gaten = []
        for ring in polygoon[1:]:
            gat = schoon_vlak(ring, midden_x, midden_y)
            if len(gat) >= 3 and oppervlak(gat) >= 0.0001:
                gaten.append({"polygonOutline": gat})
        element = {"floorInd": 0, "coordinates": buiten, "arcs": []}
        if gaten:
            element["holes"] = gaten
        vlakken.append(element)

    def voeg_lijn_toe(punten, minimum):
        if len(punten) >= minimum:
            lijnen.append({"floorInd": 0, "coordinates": punten, "arcs": []})

    for feature in features:
        eig = feature.get("properties") or {}
        if eig.get("eind_registratie"):
            continue
        if not alle_niveaus and (eig.get("relatieve_hoogteligging") or 0) != 0:
            continue
        geo = feature.get("geometry")
        if not geo:
            continue
        soort, c = geo["type"], geo["coordinates"]

        if soort == "Polygon":
            voeg_vlak_toe(c)
        elif soort == "MultiPolygon":
            for polygoon in c:
                voeg_vlak_toe(polygoon)
        elif soort == "LineString":
            voeg_lijn_toe(schoon(c, midden_x, midden_y), 2)
        elif soort == "MultiLineString":
            for lijn in c:
                voeg_lijn_toe(schoon(lijn, midden_x, midden_y), 2)
        elif soort == "Point":
            voeg_lijn_toe(punt_symbool(c, midden_x, midden_y), 4)
        elif soort == "MultiPoint":
            for punt in c:
                voeg_lijn_toe(punt_symbool(punt, midden_x, midden_y), 4)
    return vlakken, lijnen


def beschrijf_lijn(lijn):
    p = lijn["coordinates"]
    kortste = min(math.hypot(p[k + 1]["x"] - p[k]["x"], p[k + 1]["y"] - p[k]["y"])
                  for k in range(len(p) - 1))
    return f"{len(p)} punten, kortste zijde {kortste:.4f} m"


def beschrijf_vlak(vlak):
    return (f"{len(vlak['coordinates'])} punten, {len(vlak.get('holes', []))} gaten, "
            f"oppervlak {oppervlak(vlak['coordinates']):.3f} m2")


# ------------------------------------------------------------ Perceelnummers

def _afstand_tot_segment(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _afstand_tot_polygoon(x, y, ringen):
    """Positief binnen het polygoon, negatief erbuiten (afstand tot de dichtstbijzijnde rand)."""
    binnen = False
    kleinste = float("inf")
    for ring in ringen:
        n = len(ring)
        j = n - 1
        for i in range(n):
            ax, ay = ring[i][0], ring[i][1]
            bx, by = ring[j][0], ring[j][1]
            if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
                binnen = not binnen
            kleinste = min(kleinste, _afstand_tot_segment(x, y, ax, ay, bx, by))
            j = i
    return kleinste if binnen else -kleinste


def _ring_oppervlak(ring):
    s = 0.0
    for i in range(len(ring)):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[(i + 1) % len(ring)][0], ring[(i + 1) % len(ring)][1]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


def labelpunt(ringen, precisie=0.25):
    """Het punt in een polygoon (buitenring + gaten) dat het verst van alle randen ligt.

    Zo valt een label altijd binnen het perceel, ook bij een L-vorm of een gat."""
    buiten = ringen[0]
    xs = [p[0] for p in buiten]
    ys = [p[1] for p in buiten]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    breedte, hoogte = maxx - minx, maxy - miny
    cel = min(breedte, hoogte)
    if cel == 0:
        return minx, miny
    h = cel / 2
    teller = 0
    wachtrij = []

    def cel_maken(x, y, hh):
        d = _afstand_tot_polygoon(x, y, ringen)
        return (-(d + hh * math.sqrt(2)), x, y, hh, d)

    x = minx
    while x < maxx:
        y = miny
        while y < maxy:
            heapq.heappush(wachtrij, (cel_maken(x + h, y + h, h), teller))
            teller += 1
            y += cel
        x += cel

    a = 0.0
    cx = cy = 0.0
    for i in range(len(buiten)):
        x1, y1 = buiten[i][0], buiten[i][1]
        x2, y2 = buiten[(i + 1) % len(buiten)][0], buiten[(i + 1) % len(buiten)][1]
        f = x1 * y2 - x2 * y1
        a += f
        cx += (x1 + x2) * f
        cy += (y1 + y2) * f
    if a != 0:
        beste = cel_maken(cx / (3 * a), cy / (3 * a), 0)
    else:
        beste = cel_maken(buiten[0][0], buiten[0][1], 0)
    midden_cel = cel_maken(minx + breedte / 2, miny + hoogte / 2, 0)
    if midden_cel[4] > beste[4]:
        beste = midden_cel

    while wachtrij:
        (cel_t, _) = heapq.heappop(wachtrij)
        if cel_t[4] > beste[4]:
            beste = cel_t
        if -cel_t[0] - beste[4] <= precisie:
            continue
        hh = cel_t[3] / 2
        for dx in (-hh, hh):
            for dy in (-hh, hh):
                teller += 1
                heapq.heappush(wachtrij, (cel_maken(cel_t[1] + dx, cel_t[2] + dy, hh), teller))
    return beste[1], beste[2]


def perceel_teksten(features, midden_x, midden_y):
    """Een tekst per perceel (sectie en perceelnummer), op het punt dat het verst van de grenzen ligt."""
    teksten = []
    met_verschuiving = met_rotatie = 0
    voorbeelden = []
    for feature in features:
        eig = feature.get("properties") or {}
        geo = feature.get("geometry")
        nummer = eig.get("perceelnummer")
        if not geo or nummer is None:
            continue
        if geo["type"] == "Polygon":
            polygonen = [geo["coordinates"]]
        elif geo["type"] == "MultiPolygon":
            polygonen = geo["coordinates"]
        else:
            continue
        polygonen = [p for p in polygonen if p and len(p[0]) >= 3]
        if not polygonen:
            continue
        grootste = max(polygonen, key=lambda p: _ring_oppervlak(p[0]))
        x, y = labelpunt(grootste)
        try:
            tekst = PERCEELTEKST_FORMAAT.format(
                sectie=eig.get("sectie") or "", perceelnummer=nummer,
                gemeente=eig.get("kadastrale_gemeente_waarde") or "").strip()
        except (KeyError, IndexError, ValueError):
            tekst = f"{eig.get('sectie') or ''} {nummer}".strip()
        teksten.append({"x": x - midden_x, "y": y - midden_y, "tekst": tekst})

        dx = eig.get("perceelnummer_verschuiving_delta_x")
        dy = eig.get("perceelnummer_verschuiving_delta_y")
        rot = eig.get("perceelnummer_rotatie")
        if dx or dy:
            met_verschuiving += 1
        if rot:
            met_rotatie += 1
        if len(voorbeelden) < 3:
            voorbeelden.append(f"{tekst}: verschuiving ({dx}, {dy}), rotatie {rot}")
    if teksten:
        print(f"Perceelnummers: {len(teksten)} percelen, {met_verschuiving} met verschuiving, "
              f"{met_rotatie} met rotatie in de data (nog niet toegepast)")
        for v in voorbeelden:
            print("   voorbeeld", v)
    return teksten


def teken_teksten(laagnaam, teksten, hoogte, pen):
    if not BESCHIKBAAR["tekst"]:
        return 0, 0
    laag_index = zorg_voor_laag(laagnaam)
    gelukt = mislukt = 0
    for i in range(0, len(teksten), 100):
        batch = [{"floorIndex": 0, "coordinate": {"x": t["x"], "y": t["y"]},
                  "text": t["tekst"], "height": hoogte,
                  "layerIndex": laag_index, "pen": pen}
                 for t in teksten[i:i + 100]]
        r = tapir("CreateTexts", {"textsData": batch})
        if not r.get("succeeded"):
            print(f"{laagnaam}: CreateTexts fout:", str(r)[:300])
            mislukt += len(batch)
            continue
        for e in pak(r).get("elements", []):
            if "elementId" in e:
                gelukt += 1
            else:
                mislukt += 1
                if mislukt <= 3:
                    print(f"{laagnaam}: tekst mislukt:", str(e)[:200])
    return gelukt, mislukt


# ------------------------------------------------------------------ Tekenen

def herstel_vlak(laag, vlak):
    """Laat Archicad een geweigerd vlak herstellen (bijvoorbeeld een gat dat de rand raakt)
    en tekent het resultaat. Geeft True als er minstens een vulling is aangemaakt."""
    invoer = {
        "polygonCoordinates": vlak["coordinates"],
        "polygonArcs": [],
        "holes": [{"polygonCoordinates": h["polygonOutline"], "polygonArcs": []}
                  for h in vlak.get("holes", [])],
    }
    try:
        r = tapir("RegularizePolygons", {"polygons": [invoer]})
    except Exception as fout:
        print(f"{laag}: RegularizePolygons mislukt: {fout}")
        return False
    resultaten = pak(r).get("results") or []
    polygonen = (resultaten[0].get("polygons") or []) if resultaten else []
    if not polygonen:
        return False

    basis = {k: v for k, v in vlak.items() if k not in ("coordinates", "arcs", "holes")}
    gelukt = 0
    for pg in polygonen:
        if pg.get("polygonArcs"):
            return False  # bogen kunnen we hier niet doorgeven
        buiten = pg.get("polygonCoordinates") or []
        if len(buiten) < 3:
            continue
        element = dict(basis)
        element["coordinates"] = buiten
        element["arcs"] = []
        gaten = []
        for h in pg.get("holes") or []:
            punten = h.get("polygonOutline") or h.get("polygonCoordinates")
            if punten and len(punten) >= 3:
                gaten.append({"polygonOutline": punten})
        if gaten:
            element["holes"] = gaten
        r2 = tapir("CreateHatches", {"hatchesData": [element]})
        e = (pak(r2).get("elements") or [{}])[0]
        if "elementId" in e:
            gelukt += 1
        else:
            print(f"{laag}: hersteld vlak werd door Archicad geweigerd:", str(e or r2)[:200])
    if gelukt and gelukt < len(polygonen):
        print(f"{laag}: let op, van een geweigerd vlak zijn {gelukt} van de {len(polygonen)} "
              f"delen getekend")
    return gelukt > 0


def teken_vlakken(laag, vlakken):
    """Geeft (gelukt, mislukt, zonder_gaten). Geweigerde vlakken worden eerst hersteld met
    RegularizePolygons; lukt dat niet, dan wordt het vlak zonder gaten getekend."""
    gelukt = mislukt = zonder_gaten = hersteld = 0
    for i in range(0, len(vlakken), 100):
        batch = vlakken[i:i + 100]
        r = tapir("CreateHatches", {"hatchesData": batch})
        if not r.get("succeeded"):
            print(f"{laag}: CreateHatches fout:", str(r)[:400])
            mislukt += len(batch)
            continue
        antwoorden = pak(r).get("elements", [])
        opnieuw = []
        for j, e in enumerate(antwoorden):
            if "elementId" in e:
                gelukt += 1
            else:
                opnieuw.append((batch[j], e))
        for vlak, fout in opnieuw:
            if herstel_vlak(laag, vlak):
                gelukt += 1
                hersteld += 1
                continue
            if "holes" in vlak:
                zonder = {k: v for k, v in vlak.items() if k != "holes"}
                r2 = tapir("CreateHatches", {"hatchesData": [zonder]})
                e2 = (pak(r2).get("elements") or [{}])[0]
                if "elementId" in e2:
                    gelukt += 1
                    zonder_gaten += 1
                    continue
            mislukt += 1
            if mislukt <= 3:
                print(f"{laag}: vlak mislukt ({beschrijf_vlak(vlak)}):", str(fout)[:200])
    if hersteld:
        print(f"{laag}: {hersteld} vlakken hersteld met RegularizePolygons")
    return gelukt, mislukt, zonder_gaten


def teken_lijnen(laag, lijnen):
    gelukt = mislukt = 0
    for i in range(0, len(lijnen), 100):
        batch = lijnen[i:i + 100]
        r = tapir("CreatePolylines", {"polylinesData": batch})
        if not r.get("succeeded"):
            print(f"{laag}: CreatePolylines fout:", str(r)[:300])
            mislukt += len(batch)
            continue
        for j, e in enumerate(pak(r).get("elements", [])):
            if "elementId" in e:
                gelukt += 1
            else:
                mislukt += 1
                if mislukt <= 3:
                    print(f"{laag}: lijn mislukt:", beschrijf_lijn(batch[j]))
    return gelukt, mislukt


# ------------------------------------------------------- Bestemmingsplannen

def gml_uit_zip(pad_zip, token):
    """Haalt het grootste gml-bestand uit een zip. Geeft (pad, opmerking)."""
    with zipfile.ZipFile(pad_zip) as z:
        leden = [i for i in z.infolist()
                 if i.filename.lower().endswith(".gml") and not i.is_dir()]
        if not leden:
            raise ValueError("Er zit geen gml-bestand in deze zip.")
        lid = max(leden, key=lambda i: i.file_size)
        if lid.file_size > MAX_PLAN_MB * 1024 * 1024:
            raise ValueError(f"Het gml-bestand in de zip is groter dan {MAX_PLAN_MB} MB.")
        doel = os.path.join(UPLOAD_MAP, token + ".gml")
        with z.open(lid) as bron, open(doel, "wb") as uit:
            shutil.copyfileobj(bron, uit)
    opmerking = None
    if len(leden) > 1:
        opmerking = (f"De zip bevat {len(leden)} gml-bestanden, het grootste is gebruikt "
                     f"({os.path.basename(lid.filename)}).")
    return doel, opmerking


def verwerk_plan_upload(tijdelijk, naam):
    """Controleert het ontvangen bestand en geeft de gegevens voor het kaartvenster terug.

    Er wordt telkens maar een plan bewaard: een nieuw plan vervangt het vorige."""
    if plan_import is None:
        return {"fout": "plan_import.py staat niet in dezelfde map als kaart.py."}
    token = uuid.uuid4().hex
    opmerking = None
    pad = None
    try:
        if zipfile.is_zipfile(tijdelijk):
            pad, opmerking = gml_uit_zip(tijdelijk, token)
        else:
            pad = os.path.join(UPLOAD_MAP, token + ".gml")
            os.replace(tijdelijk, pad)
        meta, dekking = plan_import.plan_dekking(pad)
        if not dekking:
            raise ValueError("Geen plangebied in dit bestand gevonden. "
                             "Is het wel een bestemmingsplan?")
    except Exception as fout:
        if pad and os.path.exists(pad):
            os.remove(pad)
        return {"fout": f"Dit lijkt geen bruikbaar bestemmingsplan (IMRO-gml): {fout}"}
    finally:
        if os.path.exists(tijdelijk):
            os.remove(tijdelijk)

    for oud in PLANNEN.values():  # het vorige plan opruimen
        if os.path.exists(oud["pad"]):
            os.remove(oud["pad"])
    PLANNEN.clear()
    PLANNEN[token] = {"pad": pad, "naam": naam}
    return {"token": token, "xmin": dekking[0], "ymin": dekking[1],
            "xmax": dekking[2], "ymax": dekking[3],
            "titel": meta.get("datasetTitel"), "datum": meta.get("creatiedatum"),
            "opmerking": opmerking}


def ontvang_plan(rfile, lengte, naam):
    tijdelijk = os.path.join(UPLOAD_MAP, uuid.uuid4().hex + ".upload")
    resterend = lengte
    with open(tijdelijk, "wb") as f:
        while resterend > 0:
            blok = rfile.read(min(1024 * 1024, resterend))
            if not blok:
                break
            f.write(blok)
            resterend -= len(blok)
    return verwerk_plan_upload(tijdelijk, os.path.basename(naam or "plan.gml"))


def importeer_plan_uit_venster(token, gebied, teksten):
    if plan_import is None:
        print("Bestemmingsplan overgeslagen: plan_import.py staat niet naast kaart.py.")
        return 0
    if GEOREFERENTIE != "rd":
        print('Bestemmingsplan overgeslagen: zet GEOREFERENTIE in kaart.py op "rd".')
        return 0
    plan = PLANNEN.get(token or "")
    if not plan or not os.path.isfile(plan["pad"]):
        print("Bestemmingsplan niet meer beschikbaar, kies het bestand opnieuw in het venster.")
        return 0
    try:
        return plan_import.importeer_plan(sys.modules[__name__], plan["pad"], gebied, teksten)
    except Exception as fout:
        print("Bestemmingsplan importeren mislukt:", fout)
        return 0


class PlattegrondActief:
    """Zorgt dat de plattegrond (verdieping 0) het actieve venster is zolang het blok duurt, en zet daarna het
    oorspronkelijke venster terug (bijvoorbeeld het 3D-venster).

    Lijnen, vlakken, teksten en meshes kunnen alleen in de plattegrond worden aangemaakt; in een 3D-venster
    mislukken ze. Staat de plattegrond al open, dan gebeurt er niets."""

    def __enter__(self):
        self.oud = None
        try:
            r = tapir("GetCurrentWindowType")
            huidig = pak(r) if r.get("succeeded") else {}
        except Exception:
            huidig = {}
        soort = str(huidig.get("currentWindowType", ""))
        if soort and soort.lower() != "floorplan":
            r = tapir("ChangeWindow", {"windowType": "FloorPlan", "storyIndex": 0})
            if r.get("succeeded"):
                self.oud = huidig
                print(f"Het actieve venster was '{soort}'; gewisseld naar de plattegrond (verdieping 0).")
            else:
                print(f"LET OP: het actieve venster is '{soort}' en wisselen naar de plattegrond lukte niet "
                      f"({str(r.get('error', r))[:150]}). Wissel zelf naar de plattegrond; anders mislukken "
                      f"lijnen, vlakken, teksten en meshes.")
        return self

    def __exit__(self, soort, waarde, tb):
        if self.oud:
            oud_type = str(self.oud.get("currentWindowType", ""))
            if oud_type not in ("3DModel", "FloorPlan"):
                print(f"Het oorspronkelijke venster ({oud_type}) kan niet automatisch worden teruggezet; "
                      f"wissel zelf terug in Archicad.")
                return False
            try:
                r = tapir("ChangeWindow", {"windowType": oud_type})
                if r.get("succeeded"):
                    print("Het oorspronkelijke venster is teruggezet.")
                else:
                    print("Het oorspronkelijke venster terugzetten lukte niet; wissel zelf terug in Archicad.")
            except Exception as fout:
                print("Het oorspronkelijke venster terugzetten lukte niet:", fout)
        return False


def importeer_gebouwen_uit_venster(gebied, materiaal):
    if not BESCHIKBAAR["gebouwen"] or drie_d is None:
        print("\n3D-gebouwen zijn nog niet beschikbaar in de add-on (de opdracht voor morphs volgt).")
        return 0
    print("\n=== 3D-gebouwen ===")
    return 0


def importeer_bomen_uit_venster(gebied, object_naam):
    if bomen is None:
        print("3D-bomen overgeslagen: bomen.py (met terrein.py en drie_d.py) staat niet naast kaart.py.")
        return 0
    if GEOREFERENTIE != "rd":
        print('3D-bomen overgeslagen: zet GEOREFERENTIE in kaart.py op "rd".')
        return 0
    print("\n=== 3D-bomen ===")
    try:
        uitkomst = bomen.plaats_bomen(
            sys.modules[__name__], gebied,
            {"object": (object_naam or "").strip() or bomen.STANDAARD_OBJECT, "max": 0},
            voortgang=meld_voortgang_bomen, stop=moet_stoppen)
        return uitkomst["gelukt"]
    except Exception as fout:
        print("3D-bomen importeren mislukt:", fout)
        return 0


def meld_voortgang_bomen(tekst, fractie=None):
    binnen = BOMEN_VOORTGANG["binnen"]
    if binnen:
        binnen(tekst, fractie if fractie is not None else 0.0)


BOMEN_VOORTGANG = {"binnen": None}


def importeer_terrein_uit_venster(gebied, naadsluiting=True, overslaan=""):
    if not BESCHIKBAAR["terrein"] or terrein is None:
        print("\n3D-terrein is nog niet beschikbaar in de add-on (de opdracht voor meshes volgt).")
        return 0
    print("\n=== 3D-terrein ===")
    return 0


SERVER = {"poort": SERVER_POORT}
JOB = {"id": 0, "status": "inactief", "tekst": "", "fractie": 0.0, "aantal": None, "fout": None, "stop": False}
JOB_SLOT = threading.Lock()


def meld_voortgang(tekst, fractie=None):
    with JOB_SLOT:
        JOB["tekst"] = tekst
        if fractie is not None:
            JOB["fractie"] = max(0.0, min(1.0, fractie))


def moet_stoppen():
    return bool(JOB["stop"])


def blokken_2d(gebied, blok=BLOK_2D):
    """De blokken (op een vast raster) waarin de 2D-lagen worden opgehaald."""
    x0, y0, x1, y1 = gebied
    uit = []
    for j in range(int(math.floor(y0 / blok)), int(math.floor((y1 - 1e-9) / blok)) + 1):
        for i in range(int(math.floor(x0 / blok)), int(math.floor((x1 - 1e-9) / blok)) + 1):
            uit.append((max(x0, i * blok), max(y0, j * blok), min(x1, (i + 1) * blok), min(y1, (j + 1) * blok)))
    return uit


def importeer(aanvraag):
    """De 3D-gebouwen (Morphs) en het terrein (Meshes) worden gemaakt in het venster dat actief is: dat mag ook een
    3D-venster zijn. Lijnen, vlakken en teksten kunnen alleen in de plattegrond worden gemaakt; alleen als daarvoor
    iets is gekozen, wisselen we naar de plattegrond (en daarna weer terug).

    Een groot gebied wordt in blokken verwerkt; de voortgang staat in JOB zodat de webpagina die kan tonen."""
    x_min, y_min, x_max, y_max = aanvraag["xmin"], aanvraag["ymin"], aanvraag["xmax"], aanvraag["ymax"]
    if (x_max - x_min) > MAX_ZIJDE or (y_max - y_min) > MAX_ZIJDE:
        raise ValueError(f"Gebied te groot, maximaal {MAX_ZIJDE} x {MAX_ZIJDE} meter.")
    onderdelen = [n for n, aan in (("3D-gebouwen", aanvraag.get("gebouwen")), ("3D-terrein", aanvraag.get("terrein")),
                                   ("3D-bomen", aanvraag.get("bomen")), ("bestemmingsplan", aanvraag.get("plan")),
                   ("2D-lagen", aanvraag.get("lagen")))
                  if aan]
    stap = {"i": -1}
    print(f"Gebied in RD: x {x_min:.0f} tot {x_max:.0f}, y {y_min:.0f} tot {y_max:.0f}  "
          f"({(x_max - x_min) / 1000:.2f} x {(y_max - y_min) / 1000:.2f} km)")

    def begin(tekst):
        stap["i"] += 1
        meld_voortgang(tekst, stap["i"] / max(1, len(onderdelen)))

    def binnen(tekst, f):
        meld_voortgang(tekst, (stap["i"] + f) / max(1, len(onderdelen)))

    if terrein is not None:
        terrein.VOORTGANG = binnen
        terrein.STOP = moet_stoppen
    totaal = 0
    if aanvraag.get("gebouwen"):
        begin("3D-gebouwen")
        totaal += _importeer(aanvraag, "gebouwen")
    if aanvraag.get("terrein") and not moet_stoppen():
        begin("3D-terrein")
        totaal += _importeer(aanvraag, "terrein")         # wisselt alleen zelf van venster als meshes mislukken
    if aanvraag.get("bomen") and not moet_stoppen():
        begin("3D-bomen")
        BOMEN_VOORTGANG["binnen"] = binnen
        try:
            totaal += _importeer(aanvraag, "bomen")
        finally:
            BOMEN_VOORTGANG["binnen"] = None
    if (aanvraag.get("lagen") or aanvraag.get("plan")) and not moet_stoppen():
        with PlattegrondActief():
            if aanvraag.get("plan"):
                begin("Bestemmingsplan")
                totaal += _importeer(aanvraag, "plan")
            if aanvraag.get("lagen") and not moet_stoppen():
                begin("2D-lagen")
                blokken = blokken_2d((x_min, y_min, x_max, y_max))
                gedeeld = {}
                for n, bl in enumerate(blokken, 1):
                    if moet_stoppen():
                        print("\nGestopt op verzoek; wat al is gemaakt blijft staan.")
                        break
                    if len(blokken) > 1:
                        binnen(f"2D-lagen: blok {n} van {len(blokken)}", (n - 1) / len(blokken))
                        print(f"\n=== 2D-lagen, blok {n} van {len(blokken)} (x {bl[0]:.0f}-{bl[2]:.0f}, "
                              f"y {bl[1]:.0f}-{bl[3]:.0f}) ===")
                    totaal += _importeer(dict(aanvraag, xmin=bl[0], ymin=bl[1], xmax=bl[2], ymax=bl[3],
                                              _gedeeld=gedeeld, _blokken=len(blokken)), "lagen")
    return totaal


def _importeer(aanvraag, deel="alles"):
    x_min, y_min = aanvraag["xmin"], aanvraag["ymin"]
    x_max, y_max = aanvraag["xmax"], aanvraag["ymax"]
    if (x_max - x_min) > MAX_ZIJDE or (y_max - y_min) > MAX_ZIJDE:
        raise ValueError(f"Gebied te groot, maximaal {MAX_ZIJDE} x {MAX_ZIJDE} meter.")
    if deel == "plan":
        return importeer_plan_uit_venster(
            aanvraag["plan"], (x_min, y_min, x_max, y_max), bool(aanvraag.get("planteksten", True)))
    if deel == "gebouwen":
        return importeer_gebouwen_uit_venster(
            (x_min, y_min, x_max, y_max), bool(aanvraag.get("gebouwenmateriaal", True)))
    if deel == "bomen":
        return importeer_bomen_uit_venster((x_min, y_min, x_max, y_max), aanvraag.get("boomobject", ""))
    if deel == "terrein":
        return importeer_terrein_uit_venster(
            (x_min, y_min, x_max, y_max), bool(aanvraag.get("terreinnaad", True)),
            aanvraag.get("terreinoverslaan", ""))
    if GEOREFERENTIE == "rd":
        midden_x = midden_y = 0
    else:
        midden_x = (x_min + x_max) / 2
        midden_y = (y_min + y_max) / 2
    alle_niveaus_gekozen = bool(aanvraag.get("alleniveaus"))
    pennen = aanvraag.get("pennen") or {}

    gedeeld = aanvraag.setdefault("_gedeeld", {})
    vulling = gedeeld.get("vulling")
    if not vulling:
        vulling = zoek_volle_vulling()
        if not vulling:
            vulling = STANDAARD_EFFEN_VULLING
            print("Geen effen vulling gevonden, de terugvaller wordt gebruikt.")
        gedeeld["vulling"] = vulling

    totaal = 0
    for sleutel in aanvraag.get("lagen") or []:
        bron, _, laag = sleutel.partition(":")
        if bron not in BRONNEN:
            print(f"{sleutel}: onbekende bron, overgeslagen")
            continue
        archicad_laag = f"{BRONNEN[bron]['voorvoegsel']}{laag}"

        pen = pennen.get(sleutel)
        if pen is not None and not (isinstance(pen, int) and 1 <= pen <= 255):
            print(f"{sleutel}: ongeldig pennummer {pen}, de standaardpen wordt gebruikt")
            pen = None

        try:
            features = haal_features(bron, laag, x_min, y_min, x_max, y_max)
        except Exception as fout:
            print(f"{sleutel}: ophalen mislukt: {fout}")
            continue

        if aanvraag.get("_blokken", 1) > 1:
            # een object op een blokgrens wordt door beide blokken opgehaald: elk object maar een keer tekenen
            gezien = gedeeld.setdefault("gezien", {}).setdefault(sleutel, set())
            nieuwe = []
            for f in features:
                fid = f.get("id") or hash(json.dumps(f.get("geometry"), sort_keys=True))
                if fid not in gezien:
                    gezien.add(fid)
                    nieuwe.append(f)
            features = nieuwe

        alle_niveaus = alle_niveaus_gekozen or (bron == "bgt" and laag in ALTIJD_ALLE_NIVEAUS)
        vlakken, lijnen = maak_elementen(features, midden_x, midden_y, alle_niveaus)

        perceel_labels = []
        if bron == "kad" and laag == "perceel" and aanvraag.get("perceelteksten", True) and BESCHIKBAAR["tekst"]:
            perceel_labels = perceel_teksten(features, midden_x, midden_y)

        # Kadaster: percelen zijn grenzen, dus tekenen we alleen de omtrek als lijn
        if bron == "kad":
            for vlak in vlakken:
                ringen = [vlak["coordinates"]]
                ringen += [g["polygonOutline"] for g in vlak.get("holes", [])]
                for ring in ringen:
                    lijnen.append({
                        "floorInd": 0,
                        "coordinates": ring + [dict(ring[0])],
                        "arcs": [],
                    })
            vlakken = []

        if not vlakken and not lijnen:
            print(f"{sleutel}: niets gevonden in dit gebied")
            continue

        laag_index = zorg_voor_laag(archicad_laag)
        kleur = KLEUREN.get(laag) if bron == "bgt" else None
        for vlak in vlakken:
            vlak["layerIndex"] = laag_index
            vlak["contourPenIndex"] = pen if pen else CONTOURPEN
            if kleur:
                rood, groen, blauw = kleur
                vlak["foregroundColor"] = {
                    "red": rood / 255, "green": groen / 255, "blue": blauw / 255,
                }
                vlak["fillId"] = vulling
        for lijn in lijnen:
            lijn["layerIndex"] = laag_index
            if pen:
                lijn["linePenIndex"] = pen

        v_ok, v_fout, v_zg = teken_vlakken(sleutel, vlakken) if vlakken else (0, 0, 0)
        l_ok, l_fout = teken_lijnen(sleutel, lijnen) if lijnen else (0, 0)

        tekst = f"{sleutel}: {v_ok} vlakken ({v_fout} mislukt"
        if v_zg:
            tekst += f", {v_zg} zonder gaten"
        tekst += f"), {l_ok} lijnen ({l_fout} mislukt), op laag {archicad_laag}"
        if pen:
            tekst += f", pen {pen}"
        print(tekst)
        totaal += v_ok + l_ok

        if perceel_labels:
            t_ok, t_fout = teken_teksten(PERCEELTEKSTLAAG, perceel_labels,
                                         PERCEELTEKST_HOOGTE, pen or PERCEELTEKSTPEN)
            print(f"{sleutel}: {t_ok} perceelnummers als tekst ({t_fout} mislukt), "
                  f"op laag {PERCEELTEKSTLAAG}")
            totaal += t_ok

    return totaal


# ----------------------------------------------------------------- Webpagina

PAGINA = """<!DOCTYPE html>
<html lang="nl"><head><meta charset="utf-8">
<title>PDOK naar Archicad</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/proj4js/2.9.2/proj4.js"></script>
<style>
 body{margin:0;font-family:sans-serif;display:flex;height:100vh}
 #paneel{width:340px;padding:12px;box-sizing:border-box;overflow:auto;background:#f4f4f4}
 #map{flex:1}
 input[type=text]{width:100%;box-sizing:border-box;padding:6px}
 #plannaam{font-size:14px;margin:6px 0;word-break:break-all}
 button{margin-top:8px;padding:8px;width:100%}
 .rij{display:flex;gap:8px}
 #lagen{font-size:14px}
 .groep{background:#fff;border:1px solid #ccc;padding:6px;margin:6px 0}
 .groepkop{display:flex;justify-content:space-between;align-items:center;gap:6px;margin-bottom:4px}
 .groepkop button{width:auto;margin:0 0 0 4px;padding:3px 8px;font-size:12px}
 .groeplijst{max-height:200px;overflow:auto}
 .laagrij{display:flex;justify-content:space-between;align-items:center;gap:6px;margin-bottom:2px}
 .pen{width:56px;padding:2px}
 #planinfo{font-size:13px;color:#555;margin:4px 0}
 .klein{font-size:12px;color:#555;margin:4px 0}
 #status{margin-top:12px;font-size:14px;white-space:pre-wrap}
</style></head><body>
<div style="position:fixed;right:6px;bottom:4px;font-size:11px;z-index:5"><a href="/test">testpaneel</a></div>
<div id="paneel">
 <h3>PDOK naar Archicad <span style="float:right;font-weight:normal"><button id="kleiner" title="Kleinere tekst in dit paneel" style="width:auto;margin:0;padding:1px 8px">A-</button> <button id="groter" title="Grotere tekst in dit paneel" style="width:auto;margin:0;padding:1px 8px">A+</button></span></h3>
 <input type="text" id="adres" placeholder="Zoek een adres...">
 <button id="zoek">Zoeken</button>
 <button id="heelnl" title="Toon heel Nederland">Heel Nederland</button>
 <button id="teken" title="Teken het importgebied door een rechthoek over de kaart te slepen">Gebied tekenen</button>
 <button id="extern" style="display:none" title="Open deze kaart in je gewone browser, bijvoorbeeld om een bestand te kiezen">Open in je browser</button>
 <p>Teken je importgebied: klik op <b>Gebied tekenen</b> en sleep een rechthoek over de kaart, of houd <b>Shift</b> ingedrukt
 en sleep. Zonder dat verschuift slepen de kaart. Maximaal __MAX_ZIJDE__ x __MAX_ZIJDE__ m; een gebied groter dan 600 m wordt
 in blokken verwerkt. <b>Esc</b> annuleert.</p>
 <b>Lagen</b> <small>(rechts: pennummer, leeg = standaard)</small>
 <div id="lagen">Lagen laden...</div>
 <p><label><input type="checkbox" id="alleniveaus"> Ook objecten boven en onder maaiveld</label></p>
 <b>3D</b> <small>(PDOK 3D Basisvoorziening, hoogtes in NAP)</small>
 <div class="groep">
  <label><input type="checkbox" id="drie_gebouwen"> Gebouwen (LoD 2.2, als Morphs)</label><br>
  <label><input type="checkbox" id="drie_materiaal" checked> &nbsp;&nbsp;met materialen (dak, muur, grondvlak)</label><br>
  <label><input type="checkbox" id="drie_terrein"> Terrein (als Meshes, op vier lagen)</label><br>
  <label class="klein"><input type="checkbox" id="drie_naad" checked> &nbsp;&nbsp;naadsluiting (dicht spleten tussen vlakken)</label>
  <input type="text" id="drie_overslaan" placeholder="Terreintypen overslaan, bijv. open loods; overkapping"><br>
  <label><input type="checkbox" id="drie_bomen"> Bomen (BGT-vegetatiepunten, als 3D-object op het terrein)</label>
  <input type="text" id="drie_boomobject" value="Boom stedenbouw 02" placeholder="Naam van het bibliotheekobject">
  <div class="klein">Het eerste keer ophalen kan een minuut duren (tegel van enkele tientallen MB). Wat al bestaat
  wordt overgeslagen. De oppervlakken van het terrein stel je zelf per laag in; zie de terminal.</div>
 </div>
 <b>Bestemmingsplan</b>
 <input type="file" id="planbestand" accept=".gml,.xml,.zip" style="display:none">
 <div class="rij">
  <button id="planknop">Kies gml-bestand...</button>
  <button id="planwis">Wissen</button>
 </div>
 <div id="plannaam">Geen plan gekozen.</div>
 <label><input type="checkbox" id="planteksten" checked> Maatvoering (bouwhoogte e.d.) als tekst</label>
 <div id="planinfo"></div>
 <button id="importeer">Importeren in Archicad</button>
 <div id="status">Nog geen gebied gekozen.</div>
 <progress id="balk" max="100" value="0" style="width:100%;display:none"></progress>
 <button id="stop" style="display:none">Stop de import</button>
</div>
<div id="map"></div>
<script>
proj4.defs('EPSG:28992','+proj=sterea +lat_0=52.15616055555555 +lon_0=5.38763888888889 +k=0.9999079 +x_0=155000 +y_0=463000 +ellps=bessel +towgs84=565.417,50.3319,465.552,-0.398957,0.343988,-1.8774,4.0725 +units=m +no_defs');
const naarRD = ll => proj4('EPSG:4326','EPSG:28992',[ll.lng, ll.lat]);
const naarLL = xy => { const p = proj4('EPSG:28992','EPSG:4326',xy); return [p[1], p[0]]; };

const NEDERLAND = [[50.70, 3.20], [53.60, 7.30]];      // zuidwest en noordoost van Nederland
const map = L.map('map', {boxZoom: false}).fitBounds(NEDERLAND);
L.tileLayer('https://service.pdok.nl/brt/achtergrondkaart/wmts/v2_0/standaard/EPSG:3857/{z}/{x}/{y}.png',
  {maxZoom: 19, attribution: 'Kaartgegevens &copy; Kadaster'}).addTo(map);

let hoeken = [], vlak = null, gebied = null, planvlak = null, planToken = '';
const status = document.getElementById('status');
const doos = document.getElementById('lagen');
const planBestand = document.getElementById('planbestand');
const planNaam = document.getElementById('plannaam');
const MAX_PLAN_MB = __MAX_PLAN_MB__;
const POLL_MS = 1500;
if (location.search.indexOf('palet=1') >= 0) {                  // we draaien in het Archicad-palet
  const eb = document.getElementById('extern');
  eb.style.display = 'block';
  eb.onclick = () => fetch('/extern');
}
// De tekstgrootte van het paneel (niet van de kaart): in het palet standaard iets kleiner, en met A- en A+ te kiezen.
let schaal = location.search.indexOf('palet=1') >= 0 ? 0.8 : 1.0;
try { const o = parseFloat(localStorage.getItem('pdok_schaal')); if (o >= 0.5 && o <= 1.6) schaal = o; } catch (e) {}
function zetSchaal(s) {
  schaal = Math.max(0.5, Math.min(1.6, Math.round(s * 100) / 100));
  document.getElementById('paneel').style.zoom = schaal;
  try { localStorage.setItem('pdok_schaal', String(schaal)); } catch (e) {}
}
zetSchaal(schaal);
document.getElementById('kleiner').onclick = () => zetSchaal(schaal - 0.1);
document.getElementById('groter').onclick = () => zetSchaal(schaal + 0.1);
const BESCHIKBAAR = __BESCHIKBAAR__;
function nogNiet(ids) {                                          // een onderdeel dat de add-on nog niet kan
  ids.forEach(id => {
    const e = document.getElementById(id); if (!e) return;
    if (e.type === 'checkbox') e.checked = false;
    e.disabled = true;
    const l = e.closest ? e.closest('label') : null;
    if (l && !l.dataset.nogniet) { l.dataset.nogniet = '1'; l.style.opacity = '0.5'; l.appendChild(document.createTextNode(' (nog niet beschikbaar in de add-on)')); }
  });
}
if (!BESCHIKBAAR.gebouwen) nogNiet(['drie_gebouwen', 'drie_materiaal']);
if (!BESCHIKBAAR.terrein) nogNiet(['drie_terrein', 'drie_naad', 'drie_overslaan']);
if (!BESCHIKBAAR.tekst) nogNiet(['planteksten']);
const MAX_ZIJDE = __MAX_ZIJDE__;
const planInfo = document.getElementById('planinfo');
const vinkjes = () => [...doos.querySelectorAll('input.laagvink')];

const groepVinkjes = d => [...d.querySelectorAll('input[type=checkbox]')];

fetch('/lagen').then(r => r.json()).then(lijst => {
  doos.innerHTML = '';
  const groepen = {};
  lijst.forEach(l => {
    const sleutel = l.bron || 'overig';
    if (!groepen[sleutel]) {
      const groep = document.createElement('div');
      groep.className = 'groep';
      const kop = document.createElement('div');
      kop.className = 'groepkop';
      const titel = document.createElement('b');
      titel.textContent = l.bronnaam || sleutel;
      const knoppen = document.createElement('span');
      const aan = document.createElement('button');
      aan.textContent = 'Alles aan';
      const uit = document.createElement('button');
      uit.textContent = 'Alles uit';
      knoppen.appendChild(aan);
      knoppen.appendChild(uit);
      kop.appendChild(titel);
      kop.appendChild(knoppen);
      const inhoud = document.createElement('div');
      inhoud.className = 'groeplijst';
      groep.appendChild(kop);
      groep.appendChild(inhoud);
      if (sleutel === 'kad') {
        const extra = document.createElement('label');
        const vink = document.createElement('input');
        vink.type = 'checkbox';
        vink.id = 'perceelteksten';
        vink.checked = true;
        extra.appendChild(vink);
        extra.appendChild(document.createTextNode(' Perceelnummers als tekst'));
        groep.appendChild(extra);
      }
      doos.appendChild(groep);
      aan.onclick = () => groepVinkjes(inhoud).forEach(v => v.checked = true);
      uit.onclick = () => groepVinkjes(inhoud).forEach(v => v.checked = false);
      groepen[sleutel] = inhoud;
    }
    const rij = document.createElement('div');
    rij.className = 'laagrij';
    const lab = document.createElement('label');
    const inp = document.createElement('input');
    inp.type = 'checkbox'; inp.className = 'laagvink'; inp.value = l.id; inp.checked = l.aan;
    lab.appendChild(inp);
    lab.appendChild(document.createTextNode(' ' + (l.naam || l.title)));
    const pen = document.createElement('input');
    pen.type = 'number'; pen.min = 1; pen.max = 255; pen.className = 'pen';
    pen.placeholder = 'pen'; pen.title = 'Pennummer (leeg = standaard)';
    pen.dataset.laag = l.id;
    if (l.pen) pen.value = l.pen;
    rij.appendChild(lab);
    rij.appendChild(pen);
    groepen[sleutel].appendChild(rij);
  });
}).catch(e => { doos.textContent = 'Lagen laden mislukt: ' + e; });

function wisPlan() {
  planToken = '';
  planBestand.value = '';
  planNaam.textContent = 'Geen plan gekozen.';
  planInfo.textContent = '';
  if (planvlak) { map.removeLayer(planvlak); planvlak = null; }
}
document.getElementById('planknop').onclick = () => planBestand.click();
document.getElementById('planwis').onclick = wisPlan;

planBestand.onchange = async () => {
  const f = planBestand.files[0];
  if (!f) return;
  planToken = '';
  if (planvlak) { map.removeLayer(planvlak); planvlak = null; }
  planNaam.textContent = f.name;
  if (f.size > MAX_PLAN_MB * 1024 * 1024) {
    planInfo.textContent = 'Dit bestand is groter dan ' + MAX_PLAN_MB + ' MB en wordt niet ingelezen.';
    return;
  }
  planInfo.textContent = 'Bestand wordt ingelezen...';
  try {
    const r = await fetch('/planupload?naam=' + encodeURIComponent(f.name), {method: 'POST', body: f});
    const d = await r.json();
    if (d.fout) { planInfo.textContent = d.fout; return; }
    planToken = d.token;
    const rand = [[d.xmin, d.ymin],[d.xmax, d.ymin],[d.xmax, d.ymax],[d.xmin, d.ymax]].map(naarLL);
    planvlak = L.polygon(rand, {color: '#0066cc', dashArray: '6 6', fill: false}).addTo(map);
    map.fitBounds(planvlak.getBounds());
    planInfo.textContent = (d.titel || '') + (d.datum ? ' (' + d.datum + ')' : '') +
      '. Alleen het gebied dat je op de kaart kiest wordt geimporteerd.' +
      (d.opmerking ? ' ' + d.opmerking : '');
  } catch (e) { planInfo.textContent = 'Bestand inlezen mislukt: ' + e; }
};


// Het importgebied tekenen door te slepen: met de knop "Gebied tekenen", of met Shift ingedrukt.
let tekenmodus = false, slepen = null;
const tekenknop = document.getElementById('teken');
function zetTekenmodus(aan) {
  tekenmodus = aan;
  tekenknop.textContent = aan ? 'Sleep een rechthoek over de kaart...' : 'Gebied tekenen';
  map.getContainer().style.cursor = aan ? 'crosshair' : '';
  if (aan) map.dragging.disable(); else map.dragging.enable();
}
function rechthoekRD(a, b) {
  return {xmin: Math.min(a[0], b[0]), ymin: Math.min(a[1], b[1]), xmax: Math.max(a[0], b[0]), ymax: Math.max(a[1], b[1])};
}
function toonGebied(g) {
  const rand = [[g.xmin, g.ymin],[g.xmax, g.ymin],[g.xmax, g.ymax],[g.xmin, g.ymax]].map(naarLL);
  if (vlak) vlak.setLatLngs(rand); else vlak = L.polygon(rand, {color: '#e60000'}).addTo(map);
}
function gebiedTekst(g) {
  const b = g.xmax - g.xmin, h = g.ymax - g.ymin;
  let t = 'Gebied: ' + Math.round(b) + ' x ' + Math.round(h) + ' meter (' + (b * h / 1e6).toFixed(2) + ' km2).';
  if (b > MAX_ZIJDE || h > MAX_ZIJDE) t += ' Te groot: maximaal ' + MAX_ZIJDE + ' x ' + MAX_ZIJDE + ' m.';
  return t;
}
function wisGebied() {
  gebied = null; hoeken = [];
  if (vlak) { map.removeLayer(vlak); vlak = null; }
}
map.on('mousedown', e => {
  const oe = e.originalEvent;
  if (!oe || oe.button !== 0 || !(tekenmodus || oe.shiftKey)) return;
  wisGebied();
  slepen = {start: naarRD(e.latlng), eind: null};
  if (oe.preventDefault) oe.preventDefault();                  // geen tekst selecteren tijdens het slepen
  status.textContent = 'Sleep naar de tegenoverliggende hoek en laat los.';
});
map.on('mousemove', e => {
  if (!slepen) return;
  slepen.eind = naarRD(e.latlng);
  const g = rechthoekRD(slepen.start, slepen.eind);
  toonGebied(g);
  status.textContent = gebiedTekst(g);
});
function eindeSlepen() {
  if (!slepen) return;
  const s = slepen;
  slepen = null;
  zetTekenmodus(false);
  if (!s.eind) { status.textContent = 'Sleep over de kaart om een gebied te tekenen.'; return; }
  const g = rechthoekRD(s.start, s.eind);
  if (g.xmax - g.xmin < 2 || g.ymax - g.ymin < 2) {
    wisGebied();
    status.textContent = 'Dat gebied is te klein; sleep een grotere rechthoek.';
    return;
  }
  gebied = g;
  toonGebied(g);
  status.textContent = gebiedTekst(g);
}
window.addEventListener('mouseup', eindeSlepen);               // ook als je buiten de kaart loslaat
document.addEventListener('keydown', e => {
  if (e.key !== 'Escape') return;
  if (slepen) { slepen = null; wisGebied(); status.textContent = 'Tekenen geannuleerd.'; }
  zetTekenmodus(false);
});
tekenknop.onclick = () => zetTekenmodus(!tekenmodus);

document.getElementById('heelnl').onclick = () => map.fitBounds(NEDERLAND);
document.getElementById('zoek').onclick = async () => {
  const q = document.getElementById('adres').value;
  try {
    const r = await fetch('https://api.pdok.nl/bzk/locatieserver/search/v3_1/free?rows=1&q=' + encodeURIComponent(q));
    const d = await r.json();
    const m = d.response.docs[0].centroide_ll.match(/POINT\\(([-0-9.]+) ([-0-9.]+)\\)/);
    map.setView([parseFloat(m[2]), parseFloat(m[1])], 18);
  } catch (e) { status.textContent = 'Adres niet gevonden.'; }
};

// Een eigen bevestigingsvenster: confirm() werkt niet altijd in een ingebouwd browservenster (zoals het Archicad-palet).
function bevestig(tekst) {
  return new Promise(klaar => {
    const laag = document.createElement('div');
    laag.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.4);display:flex;' +
                         'align-items:center;justify-content:center;z-index:9999';
    const doos = document.createElement('div');
    doos.style.cssText = 'background:#fff;padding:16px;max-width:440px;border-radius:6px;font-size:14px;white-space:pre-wrap';
    doos.textContent = tekst;
    const rij = document.createElement('div');
    rij.style.cssText = 'display:flex;gap:8px;margin-top:12px';
    const sluit = antwoord => { document.body.removeChild(laag); klaar(antwoord); };
    const ja = document.createElement('button'); ja.textContent = 'Doorgaan'; ja.onclick = () => sluit(true);
    const nee = document.createElement('button'); nee.textContent = 'Annuleren'; nee.onclick = () => sluit(false);
    rij.appendChild(ja); rij.appendChild(nee); doos.appendChild(rij); laag.appendChild(doos);
    document.body.appendChild(laag);
  });
}

document.getElementById('importeer').onclick = async () => {
  if (!gebied) { status.textContent = 'Kies eerst een gebied op de kaart.'; return; }
  const aangevinkt = vinkjes().filter(v => v.checked);
  const lagen = aangevinkt.map(v => v.value);
  const plan = planToken;
  const gebouwen = document.getElementById('drie_gebouwen').checked;
  const gebouwenmateriaal = document.getElementById('drie_materiaal').checked;
  const terrein = document.getElementById('drie_terrein').checked;
  const terreinnaad = document.getElementById('drie_naad').checked;
  const terreinoverslaan = document.getElementById('drie_overslaan').value;
  const bomen = document.getElementById('drie_bomen').checked;
  const boomobject = document.getElementById('drie_boomobject').value;
  if (!lagen.length && !plan && !gebouwen && !terrein && !bomen) {
    status.textContent = 'Vink minstens een laag, 3D-onderdeel of bestemmingsplan aan.';
    return;
  }
  const pennen = {};
  aangevinkt.forEach(v => {
    const veld = doos.querySelector('input.pen[data-laag="' + v.value + '"]');
    if (veld && veld.value !== '') pennen[v.value] = parseInt(veld.value, 10);
  });
  const alleniveaus = document.getElementById('alleniveaus').checked;
  const planteksten = document.getElementById('planteksten').checked;
  const pv = document.getElementById('perceelteksten');
  const perceelteksten = pv ? pv.checked : false;
  const breedte = gebied.xmax - gebied.xmin, hoogte = gebied.ymax - gebied.ymin;
  const km2 = breedte * hoogte / 1e6;
  if (km2 > 1) {
    let tekst = 'Dit gebied is ' + Math.round(breedte) + ' x ' + Math.round(hoogte) + ' m (' + km2.toFixed(1) + ' km2).\\n\\n';
    if (terrein) tekst += '- Het terrein levert ruwweg ' + Math.round(km2 * 7000) + ' meshes op (2800 tot 13700 per km2).\\n';
    if (gebouwen) tekst += '- De gebouwen leveren ruwweg ' + Math.round(km2 * 1500) + ' Morphs op (600 tot 3100 per km2).\\n';
    if (bomen) tekst += '- De bomen leveren ruwweg ' + Math.round(km2 * 1000) + ' objecten op (een schatting; dat hangt sterk af van het gebied).\\n';
    tekst += '\\nDat kan lang duren en Archicad traag maken. Doorgaan?';
    if (!(await bevestig(tekst))) { status.textContent = 'Import geannuleerd.'; return; }
  }
  status.textContent = 'Bezig met importeren van ' + lagen.length + ' lagen' +
    (plan ? ', het bestemmingsplan' : '') + (gebouwen ? ', 3D-gebouwen' : '') + (terrein ? ', 3D-terrein' : '') +
    (bomen ? ', bomen' : '') +
    '... (kijk in de terminal voor de details)';
  const knop = document.getElementById('importeer'), balk = document.getElementById('balk');
  const stopknop = document.getElementById('stop');
  knop.disabled = true; balk.style.display = 'block'; balk.value = 0; stopknop.style.display = 'block';
  try {
    const r = await fetch('/import', {method: 'POST',
      body: JSON.stringify({...gebied, lagen, alleniveaus, pennen, plan, planteksten, perceelteksten,
                            gebouwen, gebouwenmateriaal, terrein, terreinnaad, terreinoverslaan,
                            bomen, boomobject})});
    const d = await r.json();
    if (d.fout) { status.textContent = 'Fout: ' + d.fout; return; }
    while (true) {
      await new Promise(ok => setTimeout(ok, POLL_MS));
      const v = await (await fetch('/voortgang')).json();
      balk.value = Math.round(v.fractie * 100);
      if (v.status === 'bezig') { status.textContent = v.tekst + ' (' + Math.round(v.fractie * 100) + '%)'; continue; }
      status.textContent = v.status === 'fout' ? 'Fout: ' + v.fout
        : (v.status === 'gestopt' ? 'Gestopt: ' : 'Klaar: ') + v.aantal + ' elementen getekend.';
      break;
    }
  } catch (e) { status.textContent = 'Er ging iets mis: ' + e; }
  finally { knop.disabled = false; balk.style.display = 'none'; stopknop.style.display = 'none'; }
};
document.getElementById('stop').onclick = async () => {
  status.textContent = 'Stoppen na het huidige blok...';
  try { await fetch('/stop', {method: 'POST', body: '{}'}); } catch (e) {}
};
</script></body></html>
"""


def start_job(aanvraag):
    """Start de import op de achtergrond, zodat de webpagina de voortgang kan volgen en kan stoppen."""
    with JOB_SLOT:
        if JOB["status"] == "bezig":
            return {"fout": "Er loopt al een import; wacht tot die klaar is of stop hem."}
        JOB.update(id=JOB["id"] + 1, status="bezig", tekst="Starten...", fractie=0.0, aantal=None, fout=None,
                   stop=False)
        taak = JOB["id"]

    def werk():
        try:
            aantal = importeer(aanvraag)
            with JOB_SLOT:
                JOB.update(status="gestopt" if JOB["stop"] else "klaar", aantal=aantal,
                           fractie=JOB["fractie"] if JOB["stop"] else 1.0, tekst="Klaar")
        except Exception as fout:
            print("FOUT:", fout)
            with JOB_SLOT:
                JOB.update(status="fout", fout=str(fout))
    threading.Thread(target=werk, daemon=True).start()
    return {"job": taak}


class Handler(BaseHTTPRequestHandler):
    def stuur(self, inhoud, soort):
        self.send_response(200)
        self.send_header("Content-Type", soort)
        self.send_header("Content-Length", str(len(inhoud)))
        self.end_headers()
        self.wfile.write(inhoud)

    def stuur_json(self, data):
        self.stuur(json.dumps(data).encode("utf-8"), "application/json")

    def do_GET(self):
        pad = urlparse(self.path).path
        if pad == "/lagen":
            try:
                lijst = haal_lagenlijst()
            except Exception as fout:
                print("FOUT bij ophalen lagenlijst:", fout)
                lijst = []
            self.stuur_json(lijst)
        elif pad == "/extern":
            webbrowser.open(f"http://localhost:{SERVER['poort']}/")
            self.stuur_json({"geopend": True})
        elif pad == "/voortgang":
            with JOB_SLOT:
                self.stuur_json(dict(JOB))
        else:
            pagina = (PAGINA.replace("__MAX_PLAN_MB__", str(MAX_PLAN_MB)).replace("__MAX_ZIJDE__", str(MAX_ZIJDE))
                      .replace("__BESCHIKBAAR__", json.dumps(BESCHIKBAAR)))
            self.stuur(pagina.encode("utf-8"), "text/html; charset=utf-8")

    def do_POST(self):
        delen = urlparse(self.path)
        lengte = int(self.headers.get("Content-Length", 0))
        if delen.path == "/planupload":
            naam = parse_qs(delen.query).get("naam", ["plan.gml"])[0]
            if lengte > MAX_PLAN_MB * 1024 * 1024:
                self.close_connection = True
                self.stuur_json({"fout": f"Bestand is groter dan {MAX_PLAN_MB} MB."})
                return
            try:
                antwoord = ontvang_plan(self.rfile, lengte, naam)
            except Exception as fout:
                antwoord = {"fout": f"Bestand verwerken mislukt: {fout}"}
            self.stuur_json(antwoord)
            return
        aanvraag = json.loads(self.rfile.read(lengte) or b"{}")
        if delen.path == "/stop":
            JOB["stop"] = True
            self.stuur_json({"gestopt": True})
            return
        self.stuur_json(start_job(aanvraag))


def start_server(voorkeur=SERVER_POORT):
    """Start de server op de eerste vrije poort vanaf `voorkeur`. Geeft (server, poort)."""
    for poort in range(voorkeur, voorkeur + 20):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", poort), Handler)
        except OSError:
            continue
        server.daemon_threads = True
        SERVER["poort"] = poort
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server, poort
    raise RuntimeError(f"Geen vrije poort gevonden vanaf {voorkeur}.")


if __name__ == "__main__":
    print("kaart.py wordt door de motor (engine.py) gebruikt; start de add-on in Archicad.")
