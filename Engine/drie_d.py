"""Haalt 3D-gebouwen (PDOK 3D Basisvoorziening, CityJSON) op en maakt ze als Morphs aan in Archicad.

Eerst alleen kijken wat er zou gebeuren (Archicad is dan niet nodig, er wordt niets aangemaakt):

    python drie_d.py 260278 482339 260427 482533 --droog

Daarna echt aanmaken (Archicad open):

    python drie_d.py 260278 482339 260427 482533

Opties:
    --droog        alleen lezen en rapporteren
    --maaiveld     hoogtes omrekenen naar het laagste punt van de gebouwen (anders NAP, zoals in de data)
    --max N        maak hooguit N gebouwen aan (handig om te testen)
    --forceer      maak ook panden aan waarvan al een Morph met hetzelfde Element-ID op de laag staat
    --zonder-materiaal   geef de vlakken geen oppervlak (dak, muur, grondvlak); standaard krijgt elk vlak
                   het oppervlak PDOK_dak, PDOK_muur of PDOK_grondvlak, naar zijn type in de data
    --oppervlakken-bijwerken   schrijf de drie oppervlakken opnieuw weg, ook als ze al bestaan (bijvoorbeeld
                   na het aanpassen van kleuren in dit script); nu worden bestaande oppervlakken met jouw
                   eigen aanpassingen met rust gelaten
    --leegmaken    verwijder ALLE Morphs op de laag 3D_gebouwen (vraagt eerst om bevestiging; met --ja
                   sla je die vraag over). Morphs op andere lagen blijven ongemoeid.

Panden die al op de laag 3D_gebouwen staan (zelfde Element-ID) worden standaard overgeslagen,
zodat je het script veilig opnieuw kunt draaien. Dubbele Morphs ruim je op met:

    python drie_d.py --ontdubbel

De gebieden worden in RD (meters) opgegeven: xmin ymin xmax ymax.
Elk pand wordt een Morph op de laag 3D_gebouwen, met het BAG-pandnummer als Element-ID.
"""
import json
import math
import os
import re
import sys
import zipfile
from collections import Counter

BASIS = "https://api.pdok.nl/kadaster/3d-basisvoorziening/ogc/v1"
COLLECTIE = "basisbestand_gebouwen"
RD = "http://www.opengis.net/def/crs/EPSG/0/28992"
CACHE = os.environ.get("PDOK_CACHE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "3d_cache")   # de motor zet PDOK_CACHE op een vaste map van de gebruiker
MAX_DOWNLOAD_MB = 150
MAX_PARSE_MB = 400

# De kaart-module waarmee we met Archicad praten. kaart.py zet dit bij het aanroepen vanuit het kaartvenster;
# bij gebruik vanaf de opdrachtregel wordt kaart.py gewoon geimporteerd.
KAART = None
LAATSTE = {"gelukt": 0, "mislukt": 0}      # uitkomst van de laatste keer aanmaken


def _kaart():
    if KAART is not None:
        return KAART
    import kaart
    return kaart


LAAGNAAM = "3D_gebouwen"
MAP = "PDOK Import"
# Voorkeursvolgorde van detailniveaus; het eerste dat een pand heeft, wordt gebruikt.
LOD_VOLGORDE = ["2.2", "2.1", "2.0", "1.3", "1.2", "1.1", "1.0"]
BATCH = 20                  # gebouwen per aanroep van CreateMorphs
MIN_VLAKOPPERVLAK = 1e-4    # m2, kleinere vlakken worden overgeslagen
AFRONDEN = 3                # decimalen van de lokale hoekpunten


# ------------------------------------------------------------ Oppervlakken

# naam in Archicad, kleur (rood, groen, blauw; 0 tot 1). Pas de kleuren hier aan als je ze anders wilt.
OPPERVLAKKEN = {
    "dak": ("PDOK_dak", (0.55, 0.25, 0.20)),
    "muur": ("PDOK_muur", (0.85, 0.82, 0.76)),
    "grondvlak": ("PDOK_grondvlak", (0.50, 0.50, 0.50)),
}
# CityJSON-vlaktype -> sleutel in OPPERVLAKKEN
TYPE_NAAR_OPPERVLAK = {
    "RoofSurface": "dak", "OuterCeilingSurface": "dak",
    "WallSurface": "muur", "ClosureSurface": "muur",
    "GroundSurface": "grondvlak", "OuterFloorSurface": "grondvlak",
}


def oppervlak_definitie(naam, kleur):
    """Alle velden van een oppervlak; de reflecties lijken op die van gewone oppervlakken in een project
    (met nul diffuse reflectie reageert een oppervlak niet op licht en zie je het zwart)."""
    return {"name": naam, "materialType": "General",
            "ambientReflection": 70, "diffuseReflection": 90, "specularReflection": 8,
            "transparency": 0, "shine": 0, "transparencyAttenuation": 0, "emissionAttenuation": 0,
            "surfaceColor": {"red": kleur[0], "green": kleur[1], "blue": kleur[2]},
            "specularColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
            "emissionColor": {"red": 0, "green": 0, "blue": 0}}


def guid_uit(item):
    if isinstance(item, dict):
        if "guid" in item:
            return item["guid"]
        for v in item.values():
            g = guid_uit(v)
            if g:
                return g
    return None


def zorg_voor_oppervlakken(k, bijwerken=False, definities=None):
    """Maakt de oppervlakken aan als ze nog niet bestaan. Geeft {'dak': {'guid': ..}, ...} of None bij een fout.

    Een bestaand oppervlak blijft ongemoeid, behalve als het nog de nulwaarden heeft die een eerdere proef
    achterliet (zonder reflectie ziet het er zwart uit), of als je --oppervlakken-bijwerken gebruikt. Dat beslist de
    opdracht EnsureSurface van de add-on."""
    try:
        uit = {}
        for sleutel, (naam, kleur) in (definities or OPPERVLAKKEN).items():
            invoer = oppervlak_definitie(naam, kleur)
            invoer["update"] = bool(bijwerken)
            r = k.tapir("EnsureSurface", invoer)
            if not r.get("succeeded") or not guid_uit(k.pak(r).get("attributeId")):
                print(f"   oppervlak {naam} aanmaken mislukt:", str(r.get("error", r))[:300])
                return None
            p = k.pak(r)
            uit[sleutel] = {"guid": guid_uit(p["attributeId"])}
            toestand = "aangemaakt" if p.get("created") else ("bijgewerkt" if p.get("updated") else "bestond al")
            print(f"   oppervlak {naam}: {toestand}")
        return uit
    except Exception as fout:
        print("   oppervlakken aanmaken mislukt:", fout)
        return None


# ------------------------------------------------------------------ PDOK


def kies_tegels(gebied, collectie=None):
    """Zoekt de nieuwste tegel(s) die het gebied raken. Geeft een lijst items (properties)."""
    import requests

    url = f"{BASIS}/collections/{collectie or COLLECTIE}/items"
    params = {"f": "json", "limit": 100, "bbox": ",".join(str(x) for x in gebied), "bbox-crs": RD}
    items = []
    for _ in range(20):
        r = requests.get(url, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        items += [f.get("properties", {}) for f in data.get("features", [])]
        volgende = next((l["href"] for l in data.get("links", []) if l.get("rel") == "next"), None)
        if not volgende:
            break
        url, params = volgende, None
    return kies_nieuwste(items)


def tegel_sleutel(p):
    """Nieuwe tegels heten ..._<x>_<y>.zip; oude kaartbladen hebben een bladnummer."""
    naam = os.path.basename(p.get("download_link", ""))
    m = re.search(r"_(\d{5,6})_(\d{5,6})\.zip$", naam)
    return ("nieuw", m.group(1), m.group(2)) if m else ("oud", p.get("bladnr"))


def kies_nieuwste(items):
    """Per tegel het nieuwste jaar; nieuwe tegels gaan voor oude kaartbladen die hetzelfde gebied dekken."""
    groepen = {}
    for p in items:
        groepen.setdefault(tegel_sleutel(p), []).append(p)
    gekozen = {k: max(v, key=lambda p: (p.get("jaargang_luchtfoto") or 0, p.get("startdatum") or ""))
               for k, v in groepen.items()}
    nieuw = [p for k, p in gekozen.items() if k[0] == "nieuw"]
    return nieuw if nieuw else list(gekozen.values())


def download(p):
    import requests

    os.makedirs(CACHE, exist_ok=True)
    naam = os.path.basename(p["download_link"])
    pad = os.path.join(CACHE, naam)
    verwacht = p.get("download_size_bytes")
    if os.path.exists(pad) and verwacht and os.path.getsize(pad) == verwacht:
        return pad
    mb = (verwacht or 0) / 1024 / 1024
    if mb > MAX_DOWNLOAD_MB:
        raise ValueError(f"{naam} is {mb:.0f} MB, groter dan de limiet van {MAX_DOWNLOAD_MB} MB")
    print(f"   downloaden: {naam} ({mb:.1f} MB)")
    with requests.get(p["download_link"], stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(pad, "wb") as f:
            for blok in r.iter_content(1024 * 1024):
                f.write(blok)
    return pad


# --------------------------------------------------------------- CityJSON


def lod_tekst(waarde):
    """2.2 -> '2.2', '2.2' -> '2.2', 1 -> '1.0'."""
    try:
        return f"{float(waarde):.1f}"
    except (TypeError, ValueError):
        return str(waarde)


def vertex_lezer(data):
    tf = data.get("transform")
    pts = data.get("vertices", [])
    if tf:
        s, t = tf["scale"], tf["translate"]
        return lambda i: (pts[i][0] * s[0] + t[0], pts[i][1] * s[1] + t[1], pts[i][2] * s[2] + t[2])
    return lambda i: tuple(pts[i])


def bereik_vertices(data):
    """(minx, miny, maxx, maxy) van alle hoekpunten, in meters."""
    pts = data.get("vertices", [])
    if not pts:
        return None
    lees = vertex_lezer(data)
    xs = [lees(i)[0] for i in range(0, len(pts), max(1, len(pts) // 5000))]
    ys = [lees(i)[1] for i in range(0, len(pts), max(1, len(pts) // 5000))]
    return min(xs), min(ys), max(xs), max(ys)


def oppervlakken_van(geom):
    """Lijst oppervlakken van een geometrie; elk oppervlak is een lijst ringen (eerst buiten, dan gaten)."""
    soort = geom.get("type")
    b = geom.get("boundaries", [])
    if soort == "Solid":
        return list(b[0]) if b else []                       # alleen de buitenste schil
    if soort in ("MultiSurface", "CompositeSurface"):
        return list(b)
    if soort in ("MultiSolid", "CompositeSolid"):
        return [vl for solid in b for vl in (solid[0] if solid else [])]
    return []


def oppervlakken_met_types(geom):
    """Zoals oppervlakken_van, maar geeft ook het vlaktype per oppervlak (RoofSurface, WallSurface, ...).

    Geeft (oppervlakken, typen); een type is None als de data het niet vermeldt."""
    vl = oppervlakken_van(geom)
    sem = geom.get("semantics") or {}
    soorten = [x.get("type") if isinstance(x, dict) else None for x in sem.get("surfaces", [])]
    waarden = sem.get("values")
    if geom.get("type") == "Solid" and waarden:
        waarden = waarden[0]
    typen = []
    for i in range(len(vl)):
        idx = waarden[i] if isinstance(waarden, list) and i < len(waarden) else None
        typen.append(soorten[idx] if isinstance(idx, int) and 0 <= idx < len(soorten) else None)
    return vl, typen


def panden_in_gebied(data, gebied):
    """Geeft {pand_id: {'attributen': .., 'geometrieen': {lod: [oppervlakken]}}} voor de panden die het gebied raken.

    Een pand is een Building zonder ouder; zijn delen (BuildingPart) worden samengenomen."""
    objecten = data.get("CityObjects", {})
    lees = vertex_lezer(data)
    uit = {}
    for sleutel, o in objecten.items():
        if o.get("type") != "Building" or o.get("parents"):
            continue
        onderdelen = [o] + [objecten[k] for k in (o.get("children") or []) if k in objecten]
        per_lod = {}
        per_typen = {}
        delen = []                  # elk deel (BuildingPart) apart: voor panden die als geheel niet gemaakt kunnen worden
        for deel in onderdelen:
            deel_lod, deel_typen = {}, {}
            for g in deel.get("geometry", []) or []:
                lod = lod_tekst(g.get("lod"))
                if lod == "0.0":
                    continue
                vl, typen = oppervlakken_met_types(g)
                if vl:
                    per_lod.setdefault(lod, []).extend(vl)
                    per_typen.setdefault(lod, []).extend(typen)
                    deel_lod.setdefault(lod, []).extend(vl)
                    deel_typen.setdefault(lod, []).extend(typen)
            if deel_lod:
                delen.append({"geometrieen": deel_lod, "typen": deel_typen})
        if not per_lod:
            continue
        # hoekpunten van het voorkeursniveau voor de ligging
        lod = next((l for l in LOD_VOLGORDE if l in per_lod), next(iter(per_lod)))
        xs, ys = [], []
        for vl in per_lod[lod]:
            for ring in vl:
                for i in ring:
                    x, y, _ = lees(i)
                    xs.append(x)
                    ys.append(y)
        if not xs:
            continue
        if gebied and (max(xs) < gebied[0] or min(xs) > gebied[2] or max(ys) < gebied[1] or min(ys) > gebied[3]):
            continue
        uit[sleutel] = {"attributen": o.get("attributes") or {}, "geometrieen": per_lod, "typen": per_typen,
                        "lees": lees, "delen": delen}
    return uit


# ------------------------------------------------------------- Geometrie


def newell_normaal(punten):
    nx = ny = nz = 0.0
    n = len(punten)
    for i in range(n):
        x1, y1, z1 = punten[i]
        x2, y2, z2 = punten[(i + 1) % n]
        nx += (y1 - y2) * (z1 + z2)
        ny += (z1 - z2) * (x1 + x2)
        nz += (x1 - x2) * (y1 + y2)
    return nx, ny, nz


def vlak_oppervlak(punten):
    nx, ny, nz = newell_normaal(punten)
    return math.sqrt(nx * nx + ny * ny + nz * nz) / 2


def zonder_dubbelen(ring):
    """Verwijdert opeenvolgende gelijke indices en een herhaald eindpunt."""
    uit = []
    for i in ring:
        if not uit or uit[-1] != i:
            uit.append(i)
    while len(uit) > 1 and uit[0] == uit[-1]:
        uit.pop()
    return uit


def bouw_lichaam(pand, lod, z_verschuiving=0.0, opp_ids=None, driehoeken=False, opschonen=False):
    """Zet een pand om naar (basePoint, lichaam, statistiek) in lokale coordinaten.

    lichaam = {'vertices': [{x,y,z}], 'polygons': [{'vertexIds': [...], 'holes': [[...]]}]}"""
    lees = pand["lees"]
    z_verschuiving = pand.get("z_verschuiving", z_verschuiving)          # per pand (bijvoorbeeld de onderkant op 0 m)
    oppervlakken = pand["geometrieen"][lod]
    typen = pand.get("typen", {}).get(lod) or [None] * len(oppervlakken)
    wereld = {}      # globale index -> (x, y, z)
    for vl in oppervlakken:
        for ring in vl:
            for i in ring:
                if i not in wereld:
                    x, y, z = lees(i)
                    wereld[i] = (x, y, z + z_verschuiving)
    if not wereld:
        return None
    bx = min(p[0] for p in wereld.values())
    by = min(p[1] for p in wereld.values())
    bz = min(p[2] for p in wereld.values())
    lokaal_index = {}
    vertices = []

    plek_index = {}                    # alleen bij opschonen: hoekpunten op dezelfde plek worden een hoekpunt
    stap = OPSCHOON_RASTER if opschonen else None

    def idx(i):
        if i not in lokaal_index:
            x, y, z = wereld[i]
            if stap:
                sleutel = (round((x - bx) / stap), round((y - by) / stap), round((z - bz) / stap))
                if sleutel not in plek_index:
                    plek_index[sleutel] = len(vertices)
                    vertices.append({"x": round(sleutel[0] * stap, 4), "y": round(sleutel[1] * stap, 4), "z": round(sleutel[2] * stap, 4)})
                lokaal_index[i] = plek_index[sleutel]
            else:
                lokaal_index[i] = len(vertices)
                vertices.append({"x": round(x - bx, AFRONDEN), "y": round(y - by, AFRONDEN),
                                 "z": round(z - bz, AFRONDEN)})
        return lokaal_index[i]

    vlakken = []
    overgeslagen = 0
    for vl, soort in zip(oppervlakken, typen):
        buiten = zonder_dubbelen(vl[0])
        if len(buiten) < 3:
            overgeslagen += 1
            continue
        if vlak_oppervlak([wereld[i] for i in buiten]) < MIN_VLAKOPPERVLAK:
            overgeslagen += 1
            continue
        nb = newell_normaal([wereld[i] for i in buiten])
        gaten = []
        for ring in vl[1:]:
            g = zonder_dubbelen(ring)
            if len(g) >= 3 and vlak_oppervlak([wereld[i] for i in g]) >= MIN_VLAKOPPERVLAK:
                ng = newell_normaal([wereld[i] for i in g])
                if nb[0] * ng[0] + nb[1] * ng[1] + nb[2] * ng[2] > 0:   # een gat draait tegen de buitenring in
                    g = list(reversed(g))
                gaten.append(g)
        vlakken.append((buiten, gaten, soort))

    # Oriëntatie: het volume moet positief zijn (vlakken wijzen naar buiten); anders omkeren.
    volume = 0.0
    for buiten, gaten, _ in vlakken:
        volume += fan_volume([wereld[i] for i in buiten])
        for g in gaten:
            volume += fan_volume([wereld[i] for i in g])
    omkeren = volume < 0

    polygonen = []
    soorten_teller = Counter()
    zonder_driehoeken = 0
    gaten_gevuld = weggelaten = 0
    for buiten, gaten, soort in vlakken:
        sleutel = TYPE_NAAR_OPPERVLAK.get(soort)
        soorten_teller[sleutel] += 1
        oppervlak_id = opp_ids[sleutel] if opp_ids and sleutel in opp_ids else None
        if driehoeken:
            b = list(reversed(buiten)) if omkeren else buiten
            gs = [list(reversed(g)) if omkeren else g for g in gaten]
            tris = triangulatie_vlak(wereld, b, gs)
            if tris is None and opschonen:
                # Een scheef vlak (soms bijna een meter uit het vlak) met een gat is niet altijd te verdelen. Eerst zonder het gat,
                # dan met een andere projectie; lukt dat niet, dan laten we het vlak weg (een open lichaam is beter dan geen pand).
                if gs:
                    tris = triangulatie_vlak(wereld, b, [])
                    if tris is not None:
                        gaten_gevuld += 1
                if tris is None:
                    for as_ in range(3):
                        tris = triangulatie_vlak(wereld, b, [], as_keuze=as_)
                        if tris is not None:
                            break
                if tris is None:
                    weggelaten += 1
                    continue
            if tris is not None:
                for a_, b_, c_ in tris:
                    d = {"vertexIds": [idx(a_), idx(b_), idx(c_)]}
                    if oppervlak_id:
                        d["surfaceId"] = oppervlak_id
                    polygonen.append(d)
                continue
            zonder_driehoeken += 1                  # niet te verdelen: het vlak blijft zoals het is
        b = list(reversed(buiten)) if omkeren else buiten
        d = {"vertexIds": [idx(i) for i in b]}
        if oppervlak_id:
            d["surfaceId"] = oppervlak_id
        if gaten:
            d["holes"] = [{"vertexIds": [idx(i) for i in (list(reversed(g)) if omkeren else g)]} for g in gaten]
        polygonen.append(d)

    if opschonen:
        polygonen = opgeschoonde_polygonen(polygonen, vertices)

    # Gesloten? Elke rand hoort in precies twee vlakken voor te komen.
    randen = Counter()
    for d in polygonen:
        for ring in [d["vertexIds"]] + [h["vertexIds"] for h in d.get("holes", [])]:
            for a, b in zip(ring, ring[1:] + ring[:1]):
                randen[(min(a, b), max(a, b))] += 1
    open_randen = sum(1 for n in randen.values() if n == 1)
    meer_dan_twee = sum(1 for n in randen.values() if n > 2)

    stat = {"vlakken": len(polygonen), "gaten": sum(len(d.get("holes", [])) for d in polygonen),
            "hoekpunten": len(vertices), "volume": abs(volume), "omgekeerd": omkeren,
            "open_randen": open_randen, "meer_dan_twee": meer_dan_twee, "overgeslagen": overgeslagen,
            "soorten": soorten_teller, "zonder_driehoeken": zonder_driehoeken, "gaten_gevuld": gaten_gevuld, "weggelaten": weggelaten}
    return {"x": bx, "y": by, "z": bz}, {"vertices": vertices, "polygons": polygonen}, stat


OPSCHOON_RASTER = 0.005     # m: bij opschonen vallen hoekpunten binnen 5 mm op elkaar


def _schoon_ring(ring):
    """Haalt dubbele opeenvolgende hoekpunten en spijkers (A, B, A) uit een ring."""
    ring = zonder_dubbelen(list(ring))
    veranderd = True
    while veranderd and len(ring) >= 3:
        veranderd = False
        for i in range(len(ring)):
            if ring[i - 1] == ring[(i + 1) % len(ring)]:         # een spijker: heen en terug over dezelfde rand
                del ring[i]
                ring = zonder_dubbelen(ring)
                veranderd = True
                break
    return ring if len(ring) >= 3 else None


def opgeschoonde_polygonen(polygonen, vertices, min_oppervlak=1e-5):
    """Na het samenvoegen van hoekpunten: ringen zonder dubbele punten en spijkers, vlakken die geen vlak meer zijn en
    dubbele vlakken (dezelfde hoekpunten) weglaten."""
    uit, gezien = [], set()
    for d in polygonen:
        ring = _schoon_ring(d["vertexIds"])
        if ring is None:
            continue
        pt = [(vertices[i]["x"], vertices[i]["y"], vertices[i]["z"]) for i in ring]
        if vlak_oppervlak(pt) < min_oppervlak:
            continue
        sleutel = tuple(sorted(ring))
        if sleutel in gezien:
            continue
        gezien.add(sleutel)
        nieuw = dict(d, vertexIds=ring)
        gaten = []
        for h in d.get("holes", []):
            g = _schoon_ring(h["vertexIds"])
            if g is not None:
                gaten.append({"vertexIds": g})
        if gaten:
            nieuw["holes"] = gaten
        else:
            nieuw.pop("holes", None)
        uit.append(nieuw)
    # Een rand die in meer dan twee vlakken zit, kan niet in een lichaam: houd de twee grootste vlakken en laat de rest vallen.
    pt = lambda i: (vertices[i]["x"], vertices[i]["y"], vertices[i]["z"])
    for _ in range(5):
        per_rand = {}
        for n, d in enumerate(uit):
            for ring in [d["vertexIds"]] + [h["vertexIds"] for h in d.get("holes", [])]:
                for a, b in zip(ring, ring[1:] + ring[:1]):
                    per_rand.setdefault((min(a, b), max(a, b)), set()).add(n)
        weg = set()
        for vlakken_aan_rand in per_rand.values():
            if len(vlakken_aan_rand) > 2:
                op_grootte = sorted(vlakken_aan_rand, key=lambda n: -vlak_oppervlak([pt(i) for i in uit[n]["vertexIds"]]))
                weg.update(op_grootte[2:])
        if not weg:
            break
        uit = [d for n, d in enumerate(uit) if n not in weg]
    return uit


def beschrijf_lichaam(lichaam):
    """Een korte beschrijving van wat er in een lichaam zit, om te zien waarom Archicad het weigert."""
    v, pg = lichaam["vertices"], lichaam["polygons"]
    pt = lambda i: (v[i]["x"], v[i]["y"], v[i]["z"])
    kortste = min((math.dist(pt(r[k]), pt(r[(k + 1) % len(r)])) for d in pg for r in [d["vertexIds"]] for k in range(len(r))), default=0.0)
    plekken = Counter((round(p["x"], 3), round(p["y"], 3), round(p["z"], 3)) for p in v)
    dubbel = sum(n - 1 for n in plekken.values() if n > 1)
    klein = sum(1 for d in pg if vlak_oppervlak([pt(i) for i in d["vertexIds"]]) < 1e-2)
    scheef = 0.0
    for d in pg:
        r = d["vertexIds"]
        if len(r) <= 3:
            continue
        p = [pt(i) for i in r]
        n = newell_normaal(p)
        ln = math.sqrt(sum(c * c for c in n)) or 1.0
        n = tuple(c / ln for c in n)
        scheef = max(scheef, max(abs(sum(n[k] * (q[k] - p[0][k]) for k in range(3))) for q in p))
    randen = Counter()
    for d in pg:
        for ring in [d["vertexIds"]] + [h["vertexIds"] for h in d.get("holes", [])]:
            for a, b in zip(ring, ring[1:] + ring[:1]):
                randen[(min(a, b), max(a, b))] += 1
    return (f"{len(v)} hoekpunten, {len(pg)} vlakken ({sum(1 for d in pg if d.get('holes'))} met gaten), kortste rand {kortste * 1000:.1f} mm, "
            f"{dubbel} hoekpunten op dezelfde plek als een ander, {klein} vlakken kleiner dan 1 dm2, grootste afwijking van vlakheid "
            f"{scheef * 1000:.1f} mm, {sum(1 for n in randen.values() if n == 1)} open randen, {sum(1 for n in randen.values() if n > 2)} randen in meer dan twee vlakken")


# ------------------------------------------------------------ Driehoeken


def _kruis(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _vlak_oppervlak_2d(ring):
    return sum(ring[i][0] * ring[(i + 1) % len(ring)][1] - ring[(i + 1) % len(ring)][0] * ring[i][1]
               for i in range(len(ring))) / 2


def _segmenten_snijden(p1, p2, p3, p4, eps=1e-12):
    """Echte doorsnijding van p1p2 met p3p4 (aanraking in een eindpunt telt niet)."""
    d1, d2 = _kruis(p3, p4, p1), _kruis(p3, p4, p2)
    d3, d4 = _kruis(p1, p2, p3), _kruis(p1, p2, p4)
    return d1 * d2 < -eps and d3 * d4 < -eps


def _punt_in_ring_2d(p, ring):
    binnen = False
    j = len(ring) - 1
    for i in range(len(ring)):
        if (ring[i][1] > p[1]) != (ring[j][1] > p[1]) and \
                p[0] < (ring[j][0] - ring[i][0]) * (p[1] - ring[i][1]) / (ring[j][1] - ring[i][1]) + ring[i][0]:
            binnen = not binnen
        j = i
    return binnen


def _punt_in_driehoek(p, a, b, c, eps=1e-12):
    d1, d2, d3 = _kruis(a, b, p), _kruis(b, c, p), _kruis(c, a, p)
    return d1 >= -eps and d2 >= -eps and d3 >= -eps


def triangulatie_2d(buiten, gaten):
    """Verdeelt een veelhoek met gaten in driehoeken. buiten en gaten zijn lijsten van (x, y).

    Geeft een lijst driehoeken als drietallen indexen in buiten + gaten (achter elkaar), of None als het niet
    lukt. Gaten worden met een brug aan de buitenring gekoppeld; daarna worden oren afgeknipt."""
    pts = list(buiten)
    ring = list(range(len(buiten)))
    if _vlak_oppervlak_2d(buiten) < 0:
        ring.reverse()
    gaten_idx = []
    for g in gaten:
        start = len(pts)
        pts += list(g)
        idx = list(range(start, start + len(g)))
        if _vlak_oppervlak_2d(g) > 0:
            idx.reverse()                       # gaten draaien met de klok mee
        gaten_idx.append(idx)

    def randen(r):
        return [(pts[r[i]], pts[r[(i + 1) % len(r)]]) for i in range(len(r))]

    gaten_idx.sort(key=lambda h: -max(pts[i][0] for i in h))
    while gaten_idx:
        h = gaten_idx.pop(0)
        mi = max(range(len(h)), key=lambda k: (pts[h[k]][0], -pts[h[k]][1]))
        m = h[mi]
        ring_pts = [pts[i] for i in ring]
        overig = [[pts[i] for i in o] for o in gaten_idx]
        alle_randen = randen(ring) + randen(h) + [e for o in gaten_idx for e in randen(o)]
        gekozen = None
        kandidaten = sorted(range(len(ring)), key=lambda k: (pts[ring[k]][0] - pts[m][0]) ** 2
                            + (pts[ring[k]][1] - pts[m][1]) ** 2)
        for k in kandidaten:
            v = pts[ring[k]]
            if v == pts[m]:
                continue
            if any(_segmenten_snijden(v, pts[m], a, b) for a, b in alle_randen):
                continue
            mid = ((v[0] + pts[m][0]) / 2, (v[1] + pts[m][1]) / 2)
            if not _punt_in_ring_2d(mid, ring_pts) or any(_punt_in_ring_2d(mid, o) for o in overig) \
                    or _punt_in_ring_2d(mid, [pts[i] for i in h]):
                continue
            gekozen = k
            break
        if gekozen is None:
            return None
        ring = ring[:gekozen + 1] + h[mi:] + h[:mi] + [m, ring[gekozen]] + ring[gekozen + 1:]

    tris = []
    ring = list(ring)
    teller = 0
    while len(ring) > 3 and teller < 4 * len(pts) + 20:
        teller += 1
        m_ = len(ring)
        geknipt = False
        for i in range(m_):
            a, b, c = ring[i - 1], ring[i], ring[(i + 1) % m_]
            pa, pb, pc = pts[a], pts[b], pts[c]
            if _kruis(pa, pb, pc) <= 1e-10:
                continue
            if any(d not in (a, b, c) and pts[d] not in (pa, pb, pc) and _punt_in_driehoek(pts[d], pa, pb, pc)
                   for d in ring):
                continue
            tris.append((a, b, c))
            del ring[i]
            geknipt = True
            break
        if not geknipt:                         # vast: haal een punt op een rechte lijn weg
            for i in range(len(ring)):
                a, b, c = ring[i - 1], ring[i], ring[(i + 1) % len(ring)]
                if abs(_kruis(pts[a], pts[b], pts[c])) <= 1e-9:
                    del ring[i]
                    geknipt = True
                    break
            if not geknipt:
                return None
    if len(ring) == 3 and abs(_kruis(*(pts[i] for i in ring))) > 1e-10:
        tris.append(tuple(ring))
    # controle: de oppervlakte van de driehoeken moet gelijk zijn aan die van de veelhoek met gaten
    verwacht = abs(_vlak_oppervlak_2d(buiten)) - sum(abs(_vlak_oppervlak_2d(g)) for g in gaten)
    gevonden = sum(abs(_kruis(pts[a], pts[b], pts[c])) / 2 for a, b, c in tris)
    if verwacht <= 0 or abs(gevonden - verwacht) > 1e-6 * max(1.0, verwacht):
        return None
    return tris


def triangulatie_vlak(wereld, buiten, gaten, as_keuze=None):
    """Driehoeken voor een vlak in 3D. wereld: {index: (x, y, z)}; buiten en gaten zijn lijsten van die indexen.
    Geeft een lijst drietallen (indexen), met dezelfde draairichting als het vlak, of None."""
    pb = [wereld[i] for i in buiten]
    nx = ny = nz = 0.0
    n = len(pb)
    for i in range(n):
        x1, y1, z1 = pb[i]
        x2, y2, z2 = pb[(i + 1) % n]
        nx += (y1 - y2) * (z1 + z2)
        ny += (z1 - z2) * (x1 + x2)
        nz += (x1 - x2) * (y1 + y2)
    normaal = (nx, ny, nz)
    ax = as_keuze if as_keuze is not None else max(range(3), key=lambda i: abs(normaal[i]))
    if as_keuze is None and abs(normaal[ax]) < 1e-12:
        return None
    assen = [i for i in range(3) if i != ax]
    ids = list(buiten)
    for g in gaten:
        ids += list(g)
    p2 = [(wereld[i][assen[0]], wereld[i][assen[1]]) for i in ids]
    nb = len(buiten)
    tris = triangulatie_2d(p2[:nb], [p2[nb + sum(len(x) for x in gaten[:k]):nb + sum(len(x) for x in gaten[:k + 1])]
                                     for k in range(len(gaten))])
    if tris is None:
        return None
    uit = []
    for a, b, c in tris:
        ia, ib, ic = ids[a], ids[b], ids[c]
        pa, pbb, pc = wereld[ia], wereld[ib], wereld[ic]
        ux, uy, uz = pbb[0] - pa[0], pbb[1] - pa[1], pbb[2] - pa[2]
        vx, vy, vz = pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2]
        tn = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
        if tn[0] * normaal[0] + tn[1] * normaal[1] + tn[2] * normaal[2] < 0:
            ib, ic = ic, ib
        uit.append((ia, ib, ic))
    return uit


def fan_volume(punten):
    """Bijdrage van een ring aan het volume (met teken), via een waaier van driehoeken."""
    p0 = punten[0]
    v = 0.0
    for k in range(1, len(punten) - 1):
        p1, p2 = punten[k], punten[k + 1]
        v += (p0[0] * (p1[1] * p2[2] - p1[2] * p2[1])
              - p0[1] * (p1[0] * p2[2] - p1[2] * p2[0])
              + p0[2] * (p1[0] * p2[1] - p1[1] * p2[0])) / 6.0
    return v


def pand_id(sleutel):
    """Het BAG-pandnummer: het laatste deel van de sleutel, bijvoorbeeld NL.IMBAG.Pand.0173... -> 0173..."""
    return sleutel.split(".")[-1]


# ----------------------------------------------------------------- Uitvoer


def verzamel(gebied):
    tegels = kies_tegels(gebied)
    print(f"{len(tegels)} tegel(s) voor dit gebied:")
    for p in tegels:
        print(f"   {os.path.basename(p['download_link'])}  luchtfoto {p.get('jaargang_luchtfoto')}  "
              f"{(p.get('download_size_bytes') or 0) / 1024 / 1024:.1f} MB")
    panden = {}
    for p in tegels:
        pad = download(p)
        with zipfile.ZipFile(pad) as z:
            for i in z.infolist():
                if not i.filename.lower().endswith(".json") or i.is_dir():
                    continue
                if i.file_size / 1024 / 1024 > MAX_PARSE_MB:
                    print(f"   {i.filename}: te groot om te lezen, overgeslagen")
                    continue
                with z.open(i) as f:
                    data = json.load(f)
                bereik = bereik_vertices(data)
                if bereik and (bereik[2] < gebied[0] or bereik[0] > gebied[2]
                               or bereik[3] < gebied[1] or bereik[1] > gebied[3]):
                    print(f"   {i.filename}: ligt buiten het gebied, overgeslagen")
                    continue
                gevonden = panden_in_gebied(data, gebied)
                print(f"   {i.filename}: {len(gevonden)} panden in het gebied "
                      f"(CityJSON {data.get('version')})")
                for k, v in gevonden.items():
                    panden.setdefault(k, v)
                del data
    return panden


def lees_argumenten(argumenten):
    """Geeft (gebied, droog, maaiveld, max_n); gebied is None als er geen vier getallen zijn."""
    droog = "--droog" in argumenten
    maaiveld = "--maaiveld" in argumenten
    max_n = None
    getallen = []
    i = 0
    while i < len(argumenten):
        a = argumenten[i]
        if a == "--max" and i + 1 < len(argumenten):
            max_n = int(argumenten[i + 1])
            i += 2
            continue
        if re.fullmatch(r"-?\d+(\.\d+)?", a):
            getallen.append(float(a))
        i += 1
    gebied = tuple(getallen[:4]) if len(getallen) >= 4 else None
    return gebied, droog, maaiveld, max_n


def hoofd(argumenten):
    if "--ontdubbel" in argumenten:
        return ontdubbel()
    if "--leegmaken" in argumenten:
        return leegmaken("--ja" in argumenten)
    gebied, droog, maaiveld, max_n = lees_argumenten(argumenten)
    if gebied is None:
        print(__doc__)
        return 1
    print(f"Gebied (RD): x {gebied[0]:.0f} tot {gebied[2]:.0f}, y {gebied[1]:.0f} tot {gebied[3]:.0f}\n")

    panden = verzamel(gebied)
    if not panden:
        print("Geen panden gevonden in dit gebied.")
        return 1

    # Hoogte-instelling
    z_verschuiving = 0.0
    if maaiveld:
        laagste = float("inf")
        for pand in panden.values():
            lod = next((l for l in LOD_VOLGORDE if l in pand["geometrieen"]),
                       next(iter(pand["geometrieen"])))
            for vl in pand["geometrieen"][lod]:
                for ring in vl:
                    for i in ring:
                        laagste = min(laagste, pand["lees"](i)[2])
        z_verschuiving = -laagste
        print(f"Hoogtes omgerekend: laagste punt {laagste:.2f} m NAP wordt 0.")

    # De onderkant van elk pand op 0 m (bij vlak terrein): per pand, zodat elk pand op het vlakke terrein staat
    if "--op-nul" in argumenten:
        for pand in panden.values():
            lod = next((l for l in LOD_VOLGORDE if l in pand["geometrieen"]), next(iter(pand["geometrieen"])))
            pand["z_verschuiving"] = -min(pand["lees"](i)[2] for vl in pand["geometrieen"][lod] for ring in vl for i in ring)
        print("Hoogtes: de onderkant van elk pand ligt op 0 m (vlak terrein).")

    # Oppervlakken (alleen bij echt aanmaken; bij --droog is Archicad niet nodig)
    opp = None
    if not droog and "--zonder-materiaal" not in argumenten:
        kaart = _kaart()

        print("\nOppervlakken voor de vlakken:")
        opp = zorg_voor_oppervlakken(kaart, "--oppervlakken-bijwerken" in argumenten)
        if opp is None:
            print("   Er worden geen oppervlakken toegewezen; de vlakken krijgen het standaardoppervlak.")

    # Omzetten
    gebouwen = []
    lod_teller = Counter()
    for sleutel, pand in panden.items():
        keuze = [l for l in LOD_VOLGORDE if l in pand["geometrieen"]] or list(pand["geometrieen"])
        omzetting = None
        for lod in keuze:
            res = bouw_lichaam(pand, lod, z_verschuiving, opp)
            if res:
                omzetting = (lod, res)
                break
        if not omzetting:
            continue
        lod, (basis, lichaam, stat) = omzetting
        lod_teller[lod] += 1
        gebouwen.append({"sleutel": sleutel, "id": pand_id(sleutel), "lod": lod, "basis": basis,
                         "lichaam": lichaam, "stat": stat, "alternatieven": keuze[keuze.index(lod) + 1:],
                         "pand": pand})
    print(f"\n{len(gebouwen)} panden omgezet. Detailniveaus: {dict(lod_teller)}")
    open_gebouwen = [g for g in gebouwen if g["stat"]["open_randen"] or g["stat"]["meer_dan_twee"]]
    met_gaten = [g for g in gebouwen if g["stat"]["gaten"]]
    print(f"   {sum(g['stat']['vlakken'] for g in gebouwen)} vlakken, "
          f"{sum(g['stat']['hoekpunten'] for g in gebouwen)} hoekpunten, "
          f"{len(met_gaten)} panden met vlakken met gaten, "
          f"{sum(1 for g in gebouwen if g['stat']['omgekeerd'])} panden met omgekeerde oriëntatie hersteld")
    print(f"   {len(open_gebouwen)} panden zijn niet helemaal gesloten (open of dubbele randen)")
    soorten = Counter()
    for g in gebouwen:
        soorten.update(g["stat"]["soorten"])
    if any(k for k in soorten):
        print("   vlakken per type: " + ", ".join(f"{k or 'onbekend'} {v}" for k, v in soorten.most_common()))
        if not droog and opp:
            print("   elk vlak krijgt het oppervlak van zijn type (dak, muur of grondvlak)")
    else:
        print("   de data vermeldt geen vlaktypen; er worden geen oppervlakken toegewezen")
    for g in gebouwen[:3]:
        s = g["stat"]
        print(f"   voorbeeld {g['id']}: LoD {g['lod']}, {s['vlakken']} vlakken, {s['hoekpunten']} hoekpunten, "
              f"volume {s['volume']:.1f} m3, basePoint ({g['basis']['x']:.2f}, {g['basis']['y']:.2f}, {g['basis']['z']:.2f})")
    if droog:
        print("\nDroog-modus: er is niets aangemaakt.")
        return 0

    if max_n:
        gebouwen = gebouwen[:max_n]
        print(f"\nAlleen de eerste {len(gebouwen)} panden worden aangemaakt (--max).")
    return teken(gebouwen, z_verschuiving, forceer="--forceer" in argumenten, opp=opp)


def bestaande_ids(k, laag):
    """Geeft {element-id: [elementen]} van de Morphs op de gegeven laag."""
    r = k.tapir("GetElementsByType", {"elementType": "Morph"})
    elementen = k.pak(r).get("elements", [])
    ids = {}
    for i in range(0, len(elementen), 200):
        blok = elementen[i:i + 200]
        d = k.tapir("GetDetailsOfElements", {"elements": blok})
        items = k.pak(d).get("detailsOfElements", [])
        for e, it in zip(blok, items):
            if isinstance(it, dict) and it.get("layerIndex") == laag and it.get("id"):
                ids.setdefault(it["id"], []).append(e)
    return ids


def ontdubbel():
    """Verwijdert dubbele Morphs (zelfde Element-ID) op de laag 3D_gebouwen; de eerste blijft staan."""
    kaart = _kaart()

    kaart.MAPNAAM = MAP
    laag = kaart.zorg_voor_laag(LAAGNAAM)
    ids = bestaande_ids(kaart, laag)
    te_verwijderen = [e for lijst in ids.values() for e in lijst[1:]]
    dubbel = sum(1 for lijst in ids.values() if len(lijst) > 1)
    print(f"{sum(len(v) for v in ids.values())} Morphs op de laag '{LAAGNAAM}', "
          f"{len(ids)} verschillende panden, {dubbel} panden komen dubbel voor.")
    if not te_verwijderen:
        print("Niets te verwijderen.")
        return 0
    r = kaart.tapir("DeleteElements", {"elements": te_verwijderen})
    print(f"{len(te_verwijderen)} dubbele Morphs verwijderd:", "gelukt" if r.get("succeeded") else str(r)[:200])
    return 0


def leegmaken(zonder_vraag=False):
    """Verwijdert alle Morphs op de laag 3D_gebouwen, welk Element-ID ze ook hebben."""
    kaart = _kaart()

    lagen = kaart.alle_lagen()
    if LAAGNAAM not in lagen:
        print(f"De laag '{LAAGNAAM}' bestaat niet in dit project; er is niets te verwijderen.")
        return 0
    laag = lagen[LAAGNAAM]["index"]
    r = kaart.tapir("GetElementsByType", {"elementType": "Morph"})
    elementen = kaart.pak(r).get("elements", [])
    te_verwijderen = []
    for i in range(0, len(elementen), 200):
        blok = elementen[i:i + 200]
        d = kaart.tapir("GetDetailsOfElements", {"elements": blok})
        for e, it in zip(blok, kaart.pak(d).get("detailsOfElements", [])):
            if isinstance(it, dict) and it.get("layerIndex") == laag:
                te_verwijderen.append(e)
    print(f"{len(elementen)} Morphs in het project, waarvan {len(te_verwijderen)} op de laag '{LAAGNAAM}'.")
    if not te_verwijderen:
        print("Niets te verwijderen.")
        return 0
    if not zonder_vraag:
        antwoord = input(f"Typ JA om deze {len(te_verwijderen)} Morphs te verwijderen: ")
        if antwoord.strip().upper() != "JA":
            print("Afgebroken, er is niets verwijderd.")
            return 1
    r = kaart.tapir("DeleteElements", {"elements": te_verwijderen})
    print(f"{len(te_verwijderen)} Morphs verwijderd:", "gelukt" if r.get("succeeded") else str(r)[:200])
    return 0


def teken(gebouwen, z_verschuiving, forceer=False, opp=None):
    kaart = _kaart()

    kaart.MAPNAAM = MAP
    laag = kaart.zorg_voor_laag(LAAGNAAM)
    print(f"\nLaag '{LAAGNAAM}' in de map '{MAP}' (index {laag}).")
    if not forceer:
        try:
            aanwezig = bestaande_ids(kaart, laag)
        except Exception as fout:
            aanwezig = {}
            print("Controle op bestaande panden mislukt:", fout)
        aanwezig_basis = set(aanwezig) | {re.sub(r"-deel\d+$", "", i) for i in aanwezig}      # een pand in delen heet BAGID-deel1, -deel2, ...
        over = [g for g in gebouwen if g["id"] not in aanwezig_basis]
        if len(over) < len(gebouwen):
            print(f"{len(gebouwen) - len(over)} panden staan al op de laag en worden overgeslagen "
                  f"(met --forceer maak je ze toch aan).")
        gebouwen = over
        if not gebouwen:
            print("Er is niets nieuws om aan te maken.")
            LAATSTE.update(gelukt=0, mislukt=0)
            return 0
    gelukt = mislukt = 0
    mislukte = []
    methoden = Counter()          # hoe elk pand is gemaakt (voor het rapport)
    lager = []                    # (id, van, naar, reden): panden die niet op het gevraagde LoD zijn gemaakt

    def item(g):
        return {"basePoint": g["basis"], "body": g["lichaam"], "layerIndex": laag, "id": g["id"]}

    def maak(batch):
        r = kaart.tapir("CreateMorphs", {"morphsData": batch})
        if not r.get("succeeded"):
            return None, r
        return kaart.pak(r).get("elements", []), r

    def lukt(elementen):
        return bool(elementen) and all("elementId" in e for e in elementen)

    def als_open_lichaam(lichaam):
        return dict(lichaam, bodyType="Surface")

    def in_delen(g, lod):
        """Maakt elk deel van het pand als eigen morph (zonder gedeelde scheidingsmuren), elk deel zo mogelijk als gesloten lichaam,
        anders met driehoeken, anders als open lichaam. Lukt een deel helemaal niet, dan worden de gemaakte delen weer weggehaald.
        Geeft None als het niet lukt (of het pand maar een deel heeft), anders ({manier: aantal}, [gebruikte LoD's])."""
        pand = g["pand"]
        delen = pand.get("delen") or []
        if len(delen) < 2:
            return None
        gemaakt, manieren, gebruikt = [], Counter(), []
        for n, deel in enumerate(delen, 1):
            kies = lod if lod in deel["geometrieen"] else next((l for l in LOD_VOLGORDE if l in deel["geometrieen"]), None)
            if kies is None:
                continue
            deel_pand = {"attributen": pand["attributen"], "lees": pand["lees"], "geometrieen": deel["geometrieen"], "typen": deel["typen"]}
            if "z_verschuiving" in pand:
                deel_pand["z_verschuiving"] = pand["z_verschuiving"]
            klaar = False
            for naam, driehoeken, open_lichaam in (("gesloten", False, False), ("met driehoeken", True, False), ("open", True, True)):
                res = bouw_lichaam(deel_pand, kies, z_verschuiving, opp, driehoeken=driehoeken)
                if not res:
                    continue
                basis, lichaam, _ = res
                els, _ = maak([{"basePoint": basis, "body": als_open_lichaam(lichaam) if open_lichaam else lichaam,
                                "layerIndex": laag, "id": f"{g['id']}-deel{n}"}])
                if els and lukt(els):
                    gemaakt.append(els[0]["elementId"])
                    manieren[naam] += 1
                    gebruikt.append(kies)
                    klaar = True
                    break
            if not klaar:
                if gemaakt:
                    kaart.tapir("DeleteElements", {"elements": [{"elementId": x} for x in gemaakt]})
                return None
        return (manieren, gebruikt) if gemaakt else None

    for i in range(0, len(gebouwen), BATCH):
        deel = gebouwen[i:i + BATCH]
        elementen, r = maak([item(g) for g in deel])
        if elementen is None:
            print("CreateMorphs fout:", str(r)[:400])
            mislukt += len(deel)
            mislukte += [g["id"] for g in deel]
            continue
        for g, e in zip(deel, elementen):
            if "elementId" in e:
                gelukt += 1
                methoden["als een lichaam"] += 1
                if g.get("lod") and g["lod"] != LOD_VOLGORDE[0]:
                    lager.append((g["id"], LOD_VOLGORDE[0], g["lod"], "geen LoD 2.2 in de bron"))
                continue
            fout = str(e.get("error", e))[:160]
            klaar = False
            pog = []                                    # de stappen die voor dit pand zijn geprobeerd (voor het log)
            # Binnen hetzelfde detailniveau eerst alle mogelijkheden proberen; pas daarna een lager niveau.
            # 1: alle vlakken in driehoeken (bijvoorbeeld vlakken die niet helemaal vlak zijn)
            res = bouw_lichaam(g["pand"], g["lod"], z_verschuiving, opp, driehoeken=True)
            if res:
                basis, lichaam, _ = res
                els, _ = maak([{"basePoint": basis, "body": lichaam, "layerIndex": laag, "id": g["id"]}])
                if els and lukt(els):
                    gelukt += 1
                    methoden["met driehoeken"] += 1
                    klaar = True
                pog.append("driehoeken: " + ("gelukt" if klaar else "geweigerd"))
            else:
                pog.append("driehoeken: niet op te bouwen")
            # 2: elk deel van het pand als eigen morph (gedeelde scheidingsmuren geven anders een gesloten lichaam dat niet kan)
            if not klaar:
                uitkomst = in_delen(g, g["lod"])
                pog.append("in delen: " + ("gelukt" if uitkomst else ("geweigerd" if len(g["pand"].get("delen") or []) >= 2 else "niet van toepassing (een deel)")))
                if uitkomst:
                    manieren, gebruikt = uitkomst
                    gelukt += 1
                    methoden["in delen" + (" (waarvan " + ", ".join(f"{n} {m_}" for m_, n in manieren.items() if m_ != "gesloten") + ")"
                                           if any(m_ != "gesloten" for m_ in manieren) else "")] += 1
                    if any(l != g["lod"] for l in gebruikt):
                        lager.append((g["id"], g["lod"], "/".join(sorted(set(gebruikt))), "een deel heeft geen LoD " + g["lod"] + " in de bron"))
                    klaar = True
            # 3: als open lichaam (alleen de vlakken, zonder dat het gesloten hoeft te zijn)
            if not klaar and res:
                basis, lichaam, _ = res
                els, _ = maak([{"basePoint": basis, "body": als_open_lichaam(lichaam), "layerIndex": laag, "id": g["id"]}])
                if els and lukt(els):
                    gelukt += 1
                    methoden["als open lichaam"] += 1
                    klaar = True
                pog.append("open lichaam: " + ("gelukt" if klaar else "geweigerd"))
            # 3b: opgeschoond (hoekpunten op dezelfde plek samengevoegd, spijkers en samenvallende vlakken weg), eerst gesloten, dan open
            if not klaar:
                schoon = bouw_lichaam(g["pand"], g["lod"], z_verschuiving, opp, driehoeken=True, opschonen=True)
                if schoon:
                    basis, lichaam, _ = schoon
                    for naam, body in (("opgeschoond", lichaam), ("opgeschoond en open", als_open_lichaam(lichaam))):
                        els, _ = maak([{"basePoint": basis, "body": body, "layerIndex": laag, "id": g["id"]}])
                        if els and lukt(els):
                            gelukt += 1
                            methoden[f"als een lichaam, {naam}"] += 1
                            klaar = True
                            pog.append(f"{naam}: gelukt")
                            break
                        pog.append(f"{naam}: geweigerd")
                else:
                    pog.append("opgeschoond: niet op te bouwen")
            # 4: pas dan een lager detailniveau
            for lod in ([] if klaar else g["alternatieven"]):
                res = bouw_lichaam(g["pand"], lod, z_verschuiving, opp)
                if not res:
                    continue
                basis, lichaam, _ = res
                els, _ = maak([{"basePoint": basis, "body": lichaam, "layerIndex": laag, "id": g["id"]}])
                if els and lukt(els):
                    gelukt += 1
                    methoden[f"lager LoD ({lod})"] += 1
                    lager.append((g["id"], g["lod"], lod, fout))
                    if len(lager) <= 3:
                        print(f"   pand {g['id']}: stappen op LoD {g['lod']}: " + "; ".join(pog))
                        for naam, kw in (("gewoon", {}), ("opgeschoond", {"opschonen": True})):
                            d_ = bouw_lichaam(g["pand"], g["lod"], z_verschuiving, opp, driehoeken=True, **kw)
                            if d_:
                                extra = (f" ({d_[2]['gaten_gevuld']} vlakken met gat zonder gat gemaakt, {d_[2]['weggelaten']} vlakken weggelaten)"
                                         if naam == "opgeschoond" else "")
                                print(f"      het geweigerde LoD {g['lod']}-lichaam ({naam}) bevat {beschrijf_lichaam(d_[1])}{extra}")
                    klaar = True
                    break
            if not klaar:
                mislukt += 1
                mislukte.append(g["id"])
                if len(mislukte) <= 3:
                    print(f"   pand {g['id']} mislukt (LoD {g['lod']}): {fout}")
                    print(f"      stappen: " + "; ".join(pog))
                    for naam, kw in (("gewoon", {}), ("opgeschoond", {"opschonen": True})):
                        d_ = bouw_lichaam(g["pand"], g["lod"], z_verschuiving, opp, driehoeken=True, **kw)
                        if d_:
                            print(f"      lichaam ({naam}): {beschrijf_lichaam(d_[1])}")
    print(f"\n{gelukt} panden aangemaakt, {mislukt} mislukt.")
    print("Hoe de panden zijn gemaakt: " + ", ".join(f"{n} {k_}" for k_, n in methoden.most_common()))
    if lager:
        bron = [x for x in lager if x[3].startswith(("geen LoD", "een deel heeft geen LoD"))]
        geweigerd = [x for x in lager if not x[3].startswith(("geen LoD", "een deel heeft geen LoD"))]
        if bron:
            print(f"   {len(bron)} panden (of delen daarvan) hebben geen LoD 2.2 in de bron (alleen {', '.join(sorted({x[2] for x in bron}))}); die kunnen niet hoger.")
        if geweigerd:
            print(f"   {len(geweigerd)} panden zijn op een lager LoD gemaakt omdat Archicad LoD 2.2 weigerde:")
            for pid, van, naar, fout in geweigerd[:10]:
                print(f"      {pid}: LoD {van} werd geweigerd ({fout}), gemaakt op LoD {naar}")
    elif not mislukt:
        print("   Alle panden zijn op LoD 2.2 gemaakt.")
    if mislukte:
        print("Mislukte panden (eerste 10):", ", ".join(mislukte[:10]))
    LAATSTE.update(gelukt=gelukt, mislukt=mislukt)
    return 0 if gelukt else 1


def importeer_gebouwen(k, gebied, materiaal=True, op_nul=False):
    """Voor het kaartvenster: haalt de gebouwen voor het gebied (xmin, ymin, xmax, ymax in RD) op en maakt ze
    aan als Morphs. k is de kaart-module. Geeft het aantal aangemaakte Morphs terug."""
    global KAART
    KAART = k
    LAATSTE.update(gelukt=0, mislukt=0)
    argumenten = [str(float(x)) for x in gebied]
    if not materiaal:
        argumenten.append("--zonder-materiaal")
    if op_nul:
        argumenten.append("--op-nul")
    hoofd(argumenten)
    return LAATSTE["gelukt"]


if __name__ == "__main__":
    sys.exit(hoofd(sys.argv[1:]))
