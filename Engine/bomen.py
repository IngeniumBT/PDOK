"""Bomen: plaats een Archicad-object (bijvoorbeeld een boom) op de BGT-vegetatiepunten uit PDOK.

De posities komen uit de BGT (collectie vegetatieobject_punt, via PDOK) voor het gebied dat je opgeeft. De hoogte
komt uit de 3D Basisvoorziening van PDOK (hetzelfde terreinmodel waar de terreinmeshes van worden gemaakt), dus er
hoeven geen terreinmeshes in Archicad te staan. Archicad wordt alleen gebruikt om de objecten te plaatsen.

Gebruik (in de map waar kaart.py staat, Archicad open):

    python bomen.py --zoek boom                       toont de bibliotheekobjecten waarvan de naam 'boom' bevat
    python bomen.py x0 y0 x1 y1 --droog               toont wat er zou gebeuren (gebied in RD), zonder iets te maken
    python bomen.py x0 y0 x1 y1 --max 5               plaatst de eerste 5 bomen
    python bomen.py --opruimen                        verwijdert alle objecten op de laag 3D_bomen

Opties:
    --object "Naam"     de exacte naam van het bibliotheekobject (standaard "Boom stedenbouw 02"; de namen zijn
                        gelokaliseerd, zoek ze met --zoek)
    --max N             hoeveel punten (standaard 20; 0 = alle)
    --maat X            doorsnede van de kroon in meter (standaard 6)
    --hoogte X          hoogte in meter (standaard 10)
    --z X               vaste hoogte in meter NAP in plaats van de terreinhoogte
    --hoogte-uit meshes haal de hoogte uit de terreinmeshes in Archicad (alleen als je die hebt) in plaats van uit
                        de brongegevens van PDOK (de standaard)
    --draai             geef elke boom een andere draaiing
    --param Naam=waarde stel een GDL-parameter van het object in (meerdere keren mogelijk); na het aanmaken toont het
                        script alle parameters van het object, zodat je de namen kunt zien

Struiken en hagen (BGT-type plus_type) krijgen een kleinere maat dan bomen. Elk object krijgt het Element-ID
BOOM-<BGT-id>, zodat een tweede keer draaien geen dubbelen maakt. De objecten komen op de laag 3D_bomen in de map
PDOK Import.

Dezelfde functie (plaats_bomen) wordt gebruikt door het kaartvenster (kaart.py) en door terrein.py (--bomen).
"""
import json
import math
import sys
from collections import Counter, defaultdict

STANDAARD_OBJECT = "Boom stedenbouw 02"
BRON_COLLECTIE = "vegetatieobject_punt"
LAAG_BOMEN = "3D_bomen"
ZOEKWOORDEN = ("boom", "tree", "plant", "struik", "shrub", "vegetat", "heg", "haag", "hedge")


def antwoord_van(r):
    return r.get("result", {}).get("addOnCommandResponse", {}) if isinstance(r, dict) else {}


def namen_in(x, uit=None):
    """Alle teksten die een naam lijken te zijn in een antwoord, in welke vorm Archicad of Tapir dat ook geeft."""
    uit = [] if uit is None else uit
    if isinstance(x, list):
        for y in x:
            namen_in(y, uit)
    elif isinstance(x, dict):
        for sleutel in ("name", "libraryPartName", "fileName"):
            if isinstance(x.get(sleutel), str):
                uit.append(x[sleutel])
                break
        else:
            for y in x.values():
                namen_in(y, uit)
    elif isinstance(x, str):
        uit.append(x)
    return uit


def punten_in(x, uit=None):
    """De lijst met punten {x, y} in een structuur (de omtrek van een polylijn)."""
    if isinstance(x, list):
        if x and all(isinstance(p, dict) and "x" in p and "y" in p for p in x):
            return x
        for y in x:
            r = punten_in(y)
            if r:
                return r
    elif isinstance(x, dict):
        for v in x.values():
            r = punten_in(v)
            if r:
                return r
    return None


def zoek_objecten(k, woord):
    r = k.tapir("GetAvailableLibraryParts", {"typeId": "Object"})
    if not r.get("succeeded"):
        print("Bibliotheekobjecten ophalen mislukt:", str(r.get("error", r))[:200])
        return 1
    namen = sorted(set(namen_in(k.pak(r))))
    print(f"{len(namen)} bibliotheekobjecten beschikbaar.")
    woorden = [woord.lower()] if woord else list(ZOEKWOORDEN)
    gevonden = [n for n in namen if any(w in n.lower() for w in woorden)]
    if gevonden:
        print(f"\nObjecten met {' / '.join(woorden)} in de naam ({len(gevonden)}):")
        for n in gevonden[:60]:
            print("   ", n)
        if len(gevonden) > 60:
            print(f"    ... en {len(gevonden) - 60} meer; zoek gerichter, bijvoorbeeld --zoek \"{woorden[0]} 3D\"")
        print("\nKies er een en draai: python bomen.py --object \"<naam>\" --droog")
    else:
        print(f"\nGeen object met {' / '.join(woorden)} in de naam. De eerste 40 namen:")
        for n in namen[:40]:
            print("   ", n)
    return 0


def punten_uit_pdok(k, gebied):
    """De vegetatiepunten van de BGT in het gebied (x0, y0, x1, y1 in RD), met BGT-type en een vast ID per punt."""
    features = k.haal_features("bgt", BRON_COLLECTIE, *gebied)
    uit = []
    for f in features:
        g = f.get("geometry") or {}
        eigen = f.get("properties") or {}
        soort = str(eigen.get("plus_type") or eigen.get("plus-type") or eigen.get("type") or "")
        fid = str(f.get("id") or eigen.get("lokaalid") or eigen.get("identificatie") or "")
        co = g.get("coordinates")
        if g.get("type") == "Point" and co:
            lijst = [co]
        elif g.get("type") == "MultiPoint" and co:
            lijst = co
        else:
            continue
        for n, c in enumerate(lijst):
            if not (gebied[0] <= c[0] <= gebied[2] and gebied[1] <= c[1] <= gebied[3]):
                continue                                   # alleen punten in het gebied zelf
            sleutel = (fid + (f"-{n}" if len(lijst) > 1 else "")) if fid else f"{c[0]:.2f}_{c[1]:.2f}"
            uit.append({"x": c[0], "y": c[1], "type": soort, "id": f"BOOM-{sleutel}"})
    return uit


def maat_voor(soort, maat, hoogte):
    """Struiken en hagen zijn kleiner dan bomen."""
    s = soort.lower()
    if any(w in s for w in ("struik", "haag", "heg", "hedge", "shrub")):
        return min(maat, 2.0), min(hoogte, 1.5)
    return maat, hoogte


def z_in_driehoek(x, y, a, b, c):
    """De hoogte op (x, y) in de driehoek a, b, c ((x, y, z) elk), of None als het punt er niet in ligt."""
    d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    if abs(d) < 1e-12:
        return None
    l1 = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / d
    l2 = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / d
    l3 = 1 - l1 - l2
    if l1 < -1e-9 or l2 < -1e-9 or l3 < -1e-9:
        return None
    return l1 * a[2] + l2 * b[2] + l3 * c[2]


def hoogtes_uit_terreindata(punten, marge=1.0, terugval=15.0):
    """De terreinhoogte onder elk punt uit de 3D Basisvoorziening van PDOK (het CityJSON-terreinmodel).

    Per punt wordt de driehoek gezocht waarin het punt ligt, en de hoogte daarop geinterpoleerd; liggen er meer
    driehoeken boven elkaar, dan telt de hoogste. Een punt zonder driehoek (bijvoorbeeld in de voetafdruk van een
    gebouw) krijgt de hoogte van het dichtstbijzijnde hoekpunt binnen `terugval` meter.
    Geeft (hoogtes, methoden): per punt de hoogte en 'terreindata' of 'nabij', of None."""
    import drie_d as D
    import terrein as T

    n = len(punten)
    hoogtes = [None] * n
    methoden = [None] * n
    if not n:
        return hoogtes, methoden
    gebied = (min(p["x"] for p in punten) - marge, min(p["y"] for p in punten) - marge,
              max(p["x"] for p in punten) + marge, max(p["y"] for p in punten) + marge)
    cellen = defaultdict(list)
    for i, p in enumerate(punten):
        cellen[(int(p["x"] // 50), int(p["y"] // 50))].append(i)
    tegels = D.kies_tegels(gebied, T.COLLECTIE)
    print(f"   {len(tegels)} tegel(s) van de 3D Basisvoorziening voor de hoogte:")
    for t_ in tegels:
        print(f"      {t_['download_link'].split('/')[-1]}  {(t_.get('download_size_bytes') or 0) / 1024 / 1024:.1f} MB")
    for tegel in tegels:
        pad = D.download(tegel)
        for data in T.json_van_tegel(pad):
            bereik = D.bereik_vertices(data)
            if bereik and (bereik[2] < gebied[0] or bereik[0] > gebied[2] or bereik[3] < gebied[1]
                           or bereik[1] > gebied[3]):
                continue
            print("      hoekpunten berekenen...", flush=True)
            X, Y, Z = T.vertexlijsten(data)
            alle_objecten = data.get("CityObjects", {})
            print(f"      {len(alle_objecten)} objecten doorzoeken...", flush=True)
            for teller, o in enumerate(alle_objecten.values(), 1):
                if teller % 10000 == 0:
                    print(f"      {teller} van {len(alle_objecten)}", flush=True)
                if o.get("type") not in T.OBJECT_TYPEN or (o.get("attributes") or {}).get("hoortbijbrug"):
                    continue
                ringen = []
                for g in o.get("geometry") or []:
                    for vl in D.oppervlakken_van(g):
                        if vl and len(vl[0]) >= 3:
                            ringen.append(vl[0])
                if not ringen:
                    continue
                idx = set()
                for r in ringen:
                    idx.update(r)
                xs = [X[i] for i in idx]
                ys = [Y[i] for i in idx]
                minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
                if maxx < gebied[0] or minx > gebied[2] or maxy < gebied[1] or miny > gebied[3]:
                    continue
                kand = []
                for cx in range(int(minx // 50), int(maxx // 50) + 1):
                    for cy in range(int(miny // 50), int(maxy // 50) + 1):
                        kand += [i for i in cellen.get((cx, cy), ())
                                 if minx <= punten[i]["x"] <= maxx and miny <= punten[i]["y"] <= maxy]
                if not kand:
                    continue
                for ring in ringen:
                    for kk in range(1, len(ring) - 1):
                        a, b, c = ring[0], ring[kk], ring[kk + 1]
                        for i in kand:
                            z = z_in_driehoek(punten[i]["x"], punten[i]["y"], (X[a], Y[a], Z[a]),
                                              (X[b], Y[b], Z[b]), (X[c], Y[c], Z[c]))
                            if z is not None and (hoogtes[i] is None or z > hoogtes[i]):
                                hoogtes[i] = z
                                methoden[i] = "terreindata"
            # terugval: het dichtstbijzijnde hoekpunt, voor de punten zonder driehoek
            open_ = [i for i in range(n) if hoogtes[i] is None]
            if open_:
                dicht = defaultdict(list)
                for i in open_:
                    dicht[(int(punten[i]["x"] // 50), int(punten[i]["y"] // 50))].append(i)
                beste = {}
                for vx, vy, vz in zip(X, Y, Z):
                    for i in dicht.get((int(vx // 50), int(vy // 50)), ()):
                        d = math.hypot(vx - punten[i]["x"], vy - punten[i]["y"])
                        if d <= terugval and (i not in beste or d < beste[i][0]):
                            beste[i] = (d, vz)
                for i, (d, vz) in beste.items():
                    if hoogtes[i] is None:
                        hoogtes[i] = vz
                        methoden[i] = "nabij"
            del data, X, Y, Z
    return hoogtes, methoden


def bovenvlakken(k, element):
    """De bovenvlakken (omhoog kijkende vlakken) van een mesh: lijst {bbox, pts, n}."""
    uit = []
    g = k.pak(k.tapir("Get3DGeometryOfElements", {"elements": [element]}))
    for geo in g.get("geometries3D", []):
        for lichaam in geo.get("bodies", []):
            v = lichaam.get("vertices", [])
            for pg in lichaam.get("polygons", []):
                ids = pg.get("vertexIds") or []
                if len(ids) < 3:
                    continue
                pts = [(v[i]["x"], v[i]["y"], v[i]["z"]) for i in ids]
                nx = ny = nz = 0.0                               # normaalvector (Newell)
                for i in range(len(pts)):
                    a_, b_ = pts[i], pts[(i + 1) % len(pts)]
                    nx += (a_[1] - b_[1]) * (a_[2] + b_[2])
                    ny += (a_[2] - b_[2]) * (a_[0] + b_[0])
                    nz += (a_[0] - b_[0]) * (a_[1] + b_[1])
                lengte = math.sqrt(nx * nx + ny * ny + nz * nz)
                if lengte < 1e-9 or nz / lengte < 0.05:          # alleen het bovenvlak
                    continue
                xs = [q[0] for q in pts]
                ys = [q[1] for q in pts]
                uit.append({"bbox": (min(xs), min(ys), max(xs), max(ys)), "pts": pts, "n": (nx, ny, nz)})
    return uit


def punt_in_vlak(x, y, pts):
    binnen = False
    j = len(pts) - 1
    for i in range(len(pts)):
        if (pts[i][1] > y) != (pts[j][1] > y) and \
                x < (pts[j][0] - pts[i][0]) * (y - pts[i][1]) / (pts[j][1] - pts[i][1]) + pts[i][0]:
            binnen = not binnen
        j = i
    return binnen


def z_op_vlakken(vlakken, x, y):
    hoogste = None
    for vl in vlakken:
        b = vl["bbox"]
        if b[0] - 1e-6 <= x <= b[2] + 1e-6 and b[1] - 1e-6 <= y <= b[3] + 1e-6 and punt_in_vlak(x, y, vl["pts"]):
            nx, ny, nz = vl["n"]
            px, py, pz = vl["pts"][0]
            z = pz - (nx * (x - px) + ny * (y - py)) / nz
            if hoogste is None or z > hoogste:
                hoogste = z
    return hoogste


def terreinhoogtes(k, punten):
    """De terreinhoogte onder elk punt, uit de bovenvlakken van de terreinmeshes in Archicad.

    Per punt wordt eerst de mesh gezocht waarvan de omtrek het punt omsluit (en geen gat), dan wordt van alleen die
    meshes de 3D-geometrie gelezen. Geeft een lijst met per punt de hoogte of None (geen terrein onder het punt)."""
    import terrein as T
    T.KAART = k
    per_type = T.terreinmeshes_per_type(k)
    raster = defaultdict(list)
    n_mesh = 0
    for lijst in per_type.values():
        for e, it in lijst:
            m = T.mesh_uit_details(it)
            if not m:
                continue
            n_mesh += 1
            ring = [(q["x"], q["y"]) for q in m["polygonCoordinates"]]
            gaten = [[(q["x"], q["y"]) for q in h["polygonCoordinates"]] for h in m.get("holes", [])]
            xs = [q[0] for q in ring]
            ys = [q[1] for q in ring]
            mesh = {"e": e, "ring": ring, "gaten": gaten, "bbox": (min(xs), min(ys), max(xs), max(ys))}
            for cx in range(int(min(xs) // 50), int(max(xs) // 50) + 1):
                for cy in range(int(min(ys) // 50), int(max(ys) // 50) + 1):
                    raster[(cx, cy)].append(mesh)
    print(f"   {n_mesh} terreinmeshes in het project.")
    nodig = defaultdict(list)                                 # mesh -> [index van punt]
    meshes_van = {}
    for i, p in enumerate(punten):
        gezien = set()
        for mesh in raster.get((int(p["x"] // 50), int(p["y"] // 50)), ()):
            if id(mesh) in gezien:
                continue
            gezien.add(id(mesh))
            b = mesh["bbox"]
            if b[0] <= p["x"] <= b[2] and b[1] <= p["y"] <= b[3] and \
                    T.punt_in_polygoon(p["x"], p["y"], mesh["ring"]) and \
                    not any(T.punt_in_polygoon(p["x"], p["y"], g) for g in mesh["gaten"]):
                nodig[id(mesh)].append(i)
                meshes_van[id(mesh)] = mesh
    hoogtes = [None] * len(punten)
    print(f"   de 3D-geometrie van {len(nodig)} meshes wordt gelezen voor {len(punten)} punten...")
    gelezen = 0
    for sleutel, indices in nodig.items():
        mesh = meshes_van[sleutel]
        try:
            vlakken = bovenvlakken(k, mesh["e"])
        except Exception:
            continue
        gelezen += 1
        for i in indices:
            z = z_op_vlakken(vlakken, punten[i]["x"], punten[i]["y"])
            if z is not None and (hoogtes[i] is None or z > hoogtes[i]):
                hoogtes[i] = z
    return hoogtes


def bestaande_ids(k, laag):
    """De Element-ID's van de objecten die al op de laag staan."""
    r = k.tapir("GetDetailsOfElements", {"types": ["Object"], "layerIndices": [laag]})
    if r.get("succeeded"):
        d = k.pak(r).get("detailsOfElements", [])
    else:
        e = k.pak(k.tapir("GetElementsByType", {"elementType": "Object"})).get("elements", [])
        d = []
        for i in range(0, len(e), 200):
            d += k.pak(k.tapir("GetDetailsOfElements", {"elements": e[i:i + 200]})).get("detailsOfElements", [])
    return {x.get("id") for x in d if isinstance(x, dict) and x.get("layerIndex") == laag and x.get("id")}


def opruimen(k):
    lagen = k.alle_lagen()
    if LAAG_BOMEN not in lagen:
        print(f"De laag {LAAG_BOMEN} bestaat niet; er is niets op te ruimen.")
        return 0
    laag = lagen[LAAG_BOMEN]["index"]
    r = k.tapir("GetDetailsOfElements", {"types": ["Object"], "layerIndices": [laag]})
    if r.get("succeeded"):
        elementen = [{"elementId": d["elementId"]} for d in k.pak(r).get("detailsOfElements", [])
                     if isinstance(d, dict) and "elementId" in d]
    else:
        e = k.pak(k.tapir("GetElementsByType", {"elementType": "Object"})).get("elements", [])
        elementen = []
        for i in range(0, len(e), 200):
            d = k.pak(k.tapir("GetDetailsOfElements", {"elements": e[i:i + 200]})).get("detailsOfElements", [])
            elementen += [x for x, dd in zip(e[i:i + 200], d) if isinstance(dd, dict) and dd.get("layerIndex") == laag]
    if not elementen:
        print("Geen objecten op de laag 3D_bomen.")
        return 0
    k.tapir("DeleteElements", {"elements": elementen})
    print(f"{len(elementen)} objecten op de laag {LAAG_BOMEN} verwijderd.")
    return 0


def getallen_met_naam(x, naam, uit=None):
    uit = [] if uit is None else uit
    if isinstance(x, dict):
        for sl, v in x.items():
            if sl.lower() == naam and isinstance(v, (int, float)):
                uit.append(v)
            else:
                getallen_met_naam(v, naam, uit)
    elif isinstance(x, list):
        for v in x:
            getallen_met_naam(v, naam, uit)
    return uit


def controleer_hoogte(k, elementen, items):
    """Leest van de eerste objecten de laagste hoogte van hun 3D-omhullende en vergelijkt die met de terreinhoogte."""
    n = min(5, len(elementen))
    r = k.tapir("Get3DBoundingBoxes", {"elements": elementen[:n]})
    if not r.get("succeeded"):
        print("   (de 3D-omhullende kon niet worden gelezen, dus de hoogte is niet gecontroleerd)")
        return
    vakken = k.pak(r)
    lijst = next((v for v in vakken.values() if isinstance(v, list)), [])
    print("   Hoogtecontrole (laagste punt van het object tegenover de terreinhoogte):")
    for i, v in enumerate(lijst[:n]):
        zmin = getallen_met_naam(v, "zmin")
        gevraagd = items[i]["coordinates"]["z"]
        if not zmin:
            continue
        verschil = zmin[0] - gevraagd
        print(f"      boom {i + 1}: onderkant {zmin[0]:.2f} m, terrein {gevraagd:.2f} m, verschil {verschil * 100:+.0f} cm"
              + ("" if abs(verschil) < 0.05 else "   <-- let op: staat niet op de terreinhoogte"))


def toon_parameters(k, element):
    r = k.tapir("GetGDLParametersOfElements", {"elements": [element]})
    if not r.get("succeeded"):
        return
    lijst = k.pak(r).get("gdlParametersOfElements", [])
    params = (lijst[0] or {}).get("parameters", []) if lijst else []
    if not params:
        return
    print(f"   GDL-parameters van het object ({len(params)}); de eerste 25, met hun waarde:")
    for p in params[:25]:
        w = p.get("value")
        print(f"      {p.get('name')}  [{p.get('type')}]  {json.dumps(w, ensure_ascii=False)[:60]}")
    print("   Stel er een in met --param Naam=waarde (bijvoorbeeld de hoogte of de kroondiameter van de boom).")


def venster_is_plattegrond(k):
    try:
        r = k.tapir("GetCurrentWindowType")
        tekst = json.dumps(k.pak(r)).lower().replace(" ", "") if r.get("succeeded") else ""
    except Exception:
        return False
    return "floorplan" in tekst


def standaard_opties(**kw):
    o = {"object": STANDAARD_OBJECT, "max": 0, "maat": 6.0, "hoogte": 10.0, "z": None, "droog": False,
         "draai": False, "param": {}, "laag": LAAG_BOMEN, "controle": True, "hoogte_uit": "data"}
    o.update(kw)
    return o


def lees_opties(argumenten):
    o = standaard_opties(max=20)
    o.update({"zoek": None, "opruimen": "--opruimen" in argumenten, "droog": "--droog" in argumenten,
              "draai": "--draai" in argumenten, "gebied": None})
    getallen = []
    i = 0
    while i < len(argumenten):
        a = argumenten[i]
        if a == "--zoek":
            o["zoek"] = argumenten[i + 1] if i + 1 < len(argumenten) and not argumenten[i + 1].startswith("--") else ""
            i += 2 if o["zoek"] else 1
            continue
        if a == "--hoogte-uit" and i + 1 < len(argumenten):
            o["hoogte_uit"] = argumenten[i + 1].strip().lower()
            i += 2
            continue
        if a in ("--object", "--max", "--maat", "--hoogte", "--z") and i + 1 < len(argumenten):
            sleutel = a[2:]
            w = argumenten[i + 1]
            o[sleutel] = w if sleutel == "object" else (int(w) if sleutel == "max" else float(w))
            i += 2
            continue
        if a == "--param" and i + 1 < len(argumenten) and "=" in argumenten[i + 1]:
            naam, _, waarde = argumenten[i + 1].partition("=")
            try:
                o["param"][naam.strip()] = float(waarde)
            except ValueError:
                o["param"][naam.strip()] = waarde.strip()
            i += 2
            continue
        if not a.startswith("--"):
            try:
                getallen.append(float(a))
            except ValueError:
                pass
        i += 1
    if len(getallen) >= 4:
        o["gebied"] = (min(getallen[0], getallen[2]), min(getallen[1], getallen[3]),
                       max(getallen[0], getallen[2]), max(getallen[1], getallen[3]))
    return o


def plaats_bomen(k, gebied, opties=None, voortgang=None, stop=None):
    """Plaatst het gekozen bibliotheekobject op de BGT-vegetatiepunten in het gebied (x0, y0, x1, y1 in RD).

    Geeft een woordenboek met onder meer 'gelukt', 'mislukt', 'overgeslagen' en 'punten'. Bedoeld om ook vanuit de
    terreinimport te worden aangeroepen (na het terrein, want de hoogte komt uit de terreinmeshes)."""
    o = standaard_opties(**(opties or {}))
    uit = {"punten": 0, "gelukt": 0, "mislukt": 0, "overgeslagen": 0, "zonder_terrein": 0}

    def meld(tekst, f=None):
        if voortgang:
            voortgang(tekst, f)

    # 1. de posities uit de BGT
    meld("Bomen: BGT-punten ophalen")
    punten = punten_uit_pdok(k, gebied)
    uit["punten"] = len(punten)
    print(f"{len(punten)} vegetatiepunten in de BGT voor dit gebied (x {gebied[0]:.0f}-{gebied[2]:.0f}, "
          f"y {gebied[1]:.0f}-{gebied[3]:.0f}).")
    if not punten:
        return uit
    soorten = Counter(p["type"] for p in punten if p["type"])
    if soorten:
        print("   BGT-type (plus_type): " + ", ".join(f"{t} {n}" for t, n in soorten.most_common(8)))
    if o["max"]:
        punten = punten[:o["max"]]
        print(f"   de eerste {len(punten)} worden gebruikt (--max {o['max']}; --max 0 voor alle).")

    # 2. wat er al staat, overslaan
    try:
        lagen = k.alle_lagen()
        bestaand = bestaande_ids(k, lagen[o["laag"]]["index"]) if o["laag"] in lagen else set()
    except Exception as fout:
        if not o["droog"]:
            raise
        print(f"   (Archicad niet bereikt om bestaande bomen te zoeken: {fout})")
        bestaand = set()
    nieuw = [p for p in punten if p["id"] not in bestaand]
    uit["overgeslagen"] = len(punten) - len(nieuw)
    if uit["overgeslagen"]:
        print(f"   {uit['overgeslagen']} bomen staan al op de laag {o['laag']} en worden overgeslagen.")
    punten = nieuw
    if not punten:
        print("Er is niets nieuws te plaatsen.")
        return uit

    # 3. de hoogte
    methoden = Counter()
    if o["z"] is not None:
        hoogtes = [o["z"]] * len(punten)
        methoden["vast"] = len(punten)
    elif o["hoogte_uit"] == "meshes":
        meld("Bomen: terreinhoogte bepalen")
        print("Terreinhoogte bepalen uit de terreinmeshes in Archicad...")
        try:
            hoogtes = terreinhoogtes(k, punten)
        except Exception as fout:
            print(f"   De terreinhoogte kon niet worden bepaald ({fout}); gebruik eventueel --z.")
            return uit
        for z in hoogtes:
            methoden["meshes" if z is not None else "geen"] += 1
    else:
        meld("Bomen: terreinhoogte bepalen")
        print("Terreinhoogte bepalen uit de 3D Basisvoorziening van PDOK...")
        try:
            hoogtes, soort = hoogtes_uit_terreindata(punten)
        except Exception as fout:
            print(f"   De terreinhoogte kon niet worden opgehaald ({fout}); gebruik eventueel --z.")
            return uit
        for m in soort:
            methoden[m or "geen"] += 1
    items = []
    rng = __import__("random").Random(1)
    for p, z in zip(punten, hoogtes):
        if z is None:
            uit["zonder_terrein"] += 1
            continue
        maat, hoogte = maat_voor(p["type"], o["maat"], o["hoogte"])
        item = {"libraryPartName": o["object"],
                "coordinates": {"x": round(p["x"], 3), "y": round(p["y"], 3), "z": round(z, 3)},
                "dimensions": {"x": maat, "y": maat, "z": hoogte}, "floorIndex": 0, "_id": p["id"]}
        if o["draai"]:
            item["angle"] = round(rng.uniform(0, 2 * math.pi), 4)          # in radialen
        if o["param"]:
            item["parameters"] = dict(o["param"])
        items.append(item)
    if o["z"] is None:
        uitleg = {"terreindata": "op het terreinoppervlak (driehoek)", "meshes": "uit de terreinmeshes",
                  "nabij": "van het dichtstbijzijnde hoekpunt (geen driehoek onder het punt)", "geen": "niet te bepalen"}
        print("   hoogte per boom: " + ", ".join(f"{n} {uitleg.get(m, m)}" for m, n in methoden.most_common()))
    if uit["zonder_terrein"]:
        print(f"   {uit['zonder_terrein']} punten liggen niet op of vlak bij terrein (bijvoorbeeld buiten de dekking van "
              f"de gegevens) en worden overgeslagen.")
    for it in items[:3]:
        c = it["coordinates"]
        print(f"   bijvoorbeeld: {it['libraryPartName']} op ({c['x']:.2f}, {c['y']:.2f}) op {c['z']:.2f} m NAP, "
              f"{it['dimensions']['x']:g} x {it['dimensions']['y']:g} x {it['dimensions']['z']:g} m")
    if o["droog"]:
        print("\nDroog: er is niets aangemaakt.")
        return uit
    if not items:
        return uit

    # 4. aanmaken: bij voorkeur in het actieve venster, anders in de plattegrond
    k.MAPNAAM = "PDOK Import"
    laag = k.zorg_voor_laag(o["laag"])
    for it in items:
        it["layerIndex"] = laag
    wissel = getattr(k, "PlattegrondActief", None)
    r = maak_alle(k, items, voortgang, stop)
    if r["gelukt"] == 0 and wissel is not None and not venster_is_plattegrond(k):
        print("\nHet aanmaken mislukte in het actieve venster; ik probeer het opnieuw in de plattegrond.")
        with wissel():
            r = maak_alle(k, items, voortgang, stop)
    uit["gelukt"], uit["mislukt"] = r["gelukt"], r["mislukt"]
    # laag en Element-ID zetten (ook als CreateObjects ze niet kende)
    for i in range(0, len(r["gemaakt"]), 100):
        k.tapir("SetDetailsOfElements", {"elementsWithDetails": [
            {"elementId": e["elementId"], "details": {"layerIndex": laag, "id": it["_id"]}}
            for e, it in r["gemaakt"][i:i + 100]]})
    print(f"\n{r['gelukt']} objecten aangemaakt, {r['mislukt']} mislukt, op de laag {o['laag']}.")
    if r["laten_vallen"]:
        print("   Tapir kende deze velden niet en ik heb ze weggelaten: " + ", ".join(r["laten_vallen"]))
    for tekst, n in r["fouten"].most_common(4):
        print(f"   {n} x: {tekst}")
    if r["fouten"]:
        print("   Controleer de naam van het object (gelokaliseerd) met: python bomen.py --zoek boom")
    if r["gemaakt"] and o["controle"]:
        controleer_hoogte(k, [e for e, _ in r["gemaakt"]], [it for _, it in r["gemaakt"]])
        toon_parameters(k, r["gemaakt"][0][0])
    return uit


def hoofd(argumenten):
    import faulthandler

    import kaart as k

    # Waakhond: blijft het script langer dan 90 seconden bezig, dan toont het waar het op wacht (en daarna elke 90 s)
    faulthandler.dump_traceback_later(90, repeat=True)
    try:
        return _hoofd(k, argumenten)
    finally:
        faulthandler.cancel_dump_traceback_later()


def _hoofd(k, argumenten):
    o = lees_opties(argumenten)
    if o["zoek"] is not None:
        return zoek_objecten(k, o["zoek"])
    if o["opruimen"]:
        return opruimen(k)
    if not o["gebied"]:
        print("Geef het gebied op als x0 y0 x1 y1 (RD), bijvoorbeeld:\n"
              "   python bomen.py 260100 482100 260400 482400 --droog\n"
              "De posities komen uit de BGT (PDOK) voor dat gebied. Zoek eerst de objectnaam met --zoek boom.")
        return 1
    r = plaats_bomen(k, o["gebied"], o)
    if not o["droog"] and r["gelukt"]:
        print("\nOpruimen kan met: python bomen.py --opruimen")
    return 0 if (r["gelukt"] or o["droog"]) else 1


def maak_alle(k, items, voortgang=None, stop=None):
    uit = {"gelukt": 0, "mislukt": 0, "fouten": Counter(), "gemaakt": [], "laten_vallen": []}
    for i in range(0, len(items), 50):
        if stop and stop():
            print("   Gestopt op verzoek.")
            break
        if voortgang:
            voortgang(f"Bomen: {i} van {len(items)}", i / max(1, len(items)))
        deel = items[i:i + 50]
        batch = [{sl: v for sl, v in it.items() if not sl.startswith("_")} for it in deel]
        for _ in range(5):
            r = k.tapir("CreateObjects", {"objectsData": batch})
            tekst = json.dumps(r)
            if r.get("succeeded"):
                break
            veld = None
            for kandidaat in ("layerIndex", "floorIndex", "angle", "parameters", "dimensions"):
                if "additionalProperties" in tekst and f"/{kandidaat}" in tekst:
                    veld = kandidaat
                    break
            if not veld:
                break
            for it in batch:                                   # het veld bestaat in deze Tapir niet: weglaten
                it.pop(veld, None)
            if veld not in uit["laten_vallen"]:
                uit["laten_vallen"].append(veld)
        if not r.get("succeeded"):
            uit["mislukt"] += len(deel)
            uit["fouten"][str(r.get("error", r))[:150]] += len(deel)
            continue
        for e, it in zip(k.pak(r).get("elements", []), deel):
            if "elementId" in e:
                uit["gelukt"] += 1
                uit["gemaakt"].append((e, it))
            else:
                uit["mislukt"] += 1
                uit["fouten"][str(e.get("error", e))[:150]] += 1
    return uit


if __name__ == "__main__":
    sys.exit(hoofd(sys.argv[1:]))
