"""Groenvlakken: bomen en heesters verdeeld over de groenvlakken (bos, bosplantsoen, heesters) uit de 3D Basisvoorziening.

De groenvlakken zijn dezelfde objecten als waar het terrein zijn groene oppervlak (PDOK_groen_bos, PDOK_groen_bosplantsoen,
PDOK_groen_heesters) van krijgt: de stijltabel (stijl.py) bepaalt welk object tot welke soort hoort. Over elk vlak wordt een
bibliotheekobject verdeeld met een minimale onderlinge afstand, een vrije strook langs de rand en op de hoogte van het terrein (NAP).
Er hoeven geen terreinmeshes in Archicad te staan; Archicad wordt alleen gebruikt om de objecten te plaatsen.

De posities zijn willekeurig maar vast: dezelfde import geeft dezelfde posities, en elk object krijgt het Element-ID
GROEN-<id van het vlak>-<nummer>, zodat een tweede keer draaien geen dubbelen maakt. Er komt niets binnen de afstand van een
BGT-vegetatiepunt (de losse bomen, die bomen.py plaatst).

Dit zijn geen echte bomen maar een weergave van groen: de BGT heeft voor vlakken geen boomhoogte, dus kroon en hoogte zijn
aannames per soort (SOORTEN hieronder).
"""
import json
import math
import random
import zlib
from collections import Counter, defaultdict

import bomen as B
import drie_d as D
import stijl
import terrein as T

STANDAARD_OBJECT = B.STANDAARD_OBJECT

# Per soort: de laag in Archicad, de minimale afstand tussen de objecten, de doorsnede van de kroon en de hoogte (m).
SOORTEN = {
    "bos": {"naam": "bos en bosplantsoen", "laag": "3D_bos", "afstand": 5.5, "kroon": 6.0, "hoogte": 10.0},
    "heesters": {"naam": "heesters", "laag": "3D_heesters", "afstand": 2.0, "kroon": 2.0, "hoogte": 1.5},
}
# Welke stijlregel (naam) bij welke soort hoort.
REGEL_NAAR_SOORT = {"groen_bos": "bos", "groen_bosplantsoen": "bos", "groen_heesters": "heesters"}
RAND_FACTOR = 0.35                 # vrije strook langs de rand van een vlak, als deel van de kroon
WAARSCHUWING_AANTAL = 2000         # meer dan dit aantal objecten in een import: een melding (Archicad kan er traag van worden)


GRENZEN = {"afstand": (0.5, 50.0), "kroon": (0.2, 30.0), "hoogte": (0.2, 60.0)}     # wat je in het palet kunt invullen (m)


def soortinstellingen(maten=None):
    """De instellingen per soort: de standaardwaarden, overschreven door wat in het palet is ingevuld.

    maten: {soort: {'afstand': .., 'kroon': .., 'hoogte': ..}} in meter. Een waarde die ontbreekt, geen getal is of buiten GRENZEN valt,
    blijft de standaardwaarde (en wordt gemeld). Geeft (instellingen, meldingen)."""
    cfg = {s: dict(c) for s, c in SOORTEN.items()}
    meldingen = []
    for soort, w in (maten or {}).items():
        if soort not in cfg or not isinstance(w, dict):
            continue
        for sl, (lo, hi) in GRENZEN.items():
            if sl not in w or w[sl] in (None, ""):
                continue
            try:
                x = float(str(w[sl]).replace(",", "."))
            except ValueError:
                x = None
            if x is None or not (lo <= x <= hi):
                meldingen.append(f"{cfg[soort]['naam']}: {sl} '{w[sl]}' is geen getal tussen {lo:g} en {hi:g} m; de standaardwaarde {cfg[soort][sl]:g} m wordt gebruikt")
            else:
                cfg[soort][sl] = x
    return cfg, meldingen


def standaard_opties(**kw):
    o = {"object": STANDAARD_OBJECT, "z": None, "bos": True, "heesters": True, "droog": False}
    o.update(kw)
    return o


# ---------------------------------------------------------------- de vlakken uit de bron
def soort_van(o, regels):
    """De soort ('bos' of 'heesters') van een terreinobject, of None als het geen groenvlak van die soorten is."""
    at = o.get("attributes") or {}
    laag = stijl.laag_uit_3d(o.get("type"), at)
    eig = stijl.eig_uit_3d(at)
    for lijst in (regels, stijl.standaardregels()):        # een oud stijlbestand mist de groenregels soms: dan de standaardtabel
        r = stijl.kies(laag, eig, "3d", lijst)
        if r and r.get("naam") in REGEL_NAAR_SOORT:
            return REGEL_NAAR_SOORT[r["naam"]]
        if r:
            return None
    return None


def vlakken_uit_data(data, gebied, regels, gezien=None, soorten=("bos", "heesters")):
    """De groenvlakken uit een CityJSON-terreinbestand die het gebied raken.

    Geeft een lijst {'id', 'soort', 'driehoeken': [((x, y, z) x3)], 'randen': [((x, y), (x, y))]}; de randen zijn de ribben die
    maar bij een driehoek horen (de omtrek en de gaten)."""
    X, Y, Z = T.vertexlijsten(data)
    uit = []
    for sleutel, o in data.get("CityObjects", {}).items():
        if o.get("type") not in T.OBJECT_TYPEN or (o.get("attributes") or {}).get("hoortbijbrug"):
            continue
        soort = soort_van(o, regels)
        if soort is None or soort not in soorten:
            continue
        at = o.get("attributes") or {}
        oid = str(at.get("3df_id") or sleutel)
        if gezien is not None and oid in gezien:
            continue
        drie = []
        ribben = Counter()
        for g in o.get("geometry") or []:
            for vl in D.oppervlakken_van(g):
                if not vl or len(vl[0]) < 3:
                    continue
                ring = vl[0]
                for i in range(1, len(ring) - 1):
                    a, b, c = ring[0], ring[i], ring[i + 1]
                    drie.append(((X[a], Y[a], Z[a]), (X[b], Y[b], Z[b]), (X[c], Y[c], Z[c])))
                    for p, q in ((a, b), (b, c), (c, a)):
                        ribben[(min(p, q), max(p, q))] += 1
        if not drie:
            continue
        xs = [p[0] for t in drie for p in t]
        ys = [p[1] for t in drie for p in t]
        if max(xs) < gebied[0] or min(xs) > gebied[2] or max(ys) < gebied[1] or min(ys) > gebied[3]:
            continue
        randen = [((X[p], Y[p]), (X[q], Y[q])) for (p, q), n in ribben.items() if n == 1]
        if gezien is not None:
            gezien.add(oid)
        uit.append({"id": oid, "soort": soort, "driehoeken": drie, "randen": randen})
    return uit


def vlakken_uit_pdok(gebied, uitsnede_gebied=None, soorten=("bos", "heesters")):
    """De groenvlakken in het gebied (x0, y0, x1, y1 in RD), uit de tegels van de 3D Basisvoorziening."""
    regels = stijl.laad()[0]
    marge = 30.0
    zoek = (gebied[0] - marge, gebied[1] - marge, gebied[2] + marge, gebied[3] + marge)
    tegels = D.kies_tegels(zoek, T.COLLECTIE)
    print(f"   {len(tegels)} tegel(s) van de 3D Basisvoorziening voor de groenvlakken:")
    for t_ in tegels:
        print(f"      {t_['download_link'].split('/')[-1]}  {(t_.get('download_size_bytes') or 0) / 1024 / 1024:.1f} MB")
    uit, gezien = [], set()
    for tegel in tegels:
        pad = D.download(tegel)
        for data in T.json_van_tegel(pad, uitsnede_gebied or zoek):
            bereik = D.bereik_vertices(data)
            if bereik and (bereik[2] < zoek[0] or bereik[0] > zoek[2] or bereik[3] < zoek[1] or bereik[1] > zoek[3]):
                continue
            uit += vlakken_uit_data(data, zoek, regels, gezien, soorten)
            del data
    return uit


# ---------------------------------------------------------------- verdelen
def afstand_tot_randen(x, y, randen):
    best = 1e9
    for (ax, ay), (bx, by) in randen:
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy
        t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / l2))
        d = math.hypot(x - ax - t * dx, y - ay - t * dy)
        if d < best:
            best = d
    return best


def verdeel(vlak, cfg, gebied, blokkeren=()):
    """Verdeelt punten over een vlak. Geeft een lijst (x, y, z) in het gebied, met minimaal cfg['afstand'] tussen de punten
    en tot de `blokkeren` (de BGT-vegetatiepunten), en minstens RAND_FACTOR * kroon van de rand af.

    Een punt wordt in een willekeurige driehoek gekozen (naar oppervlakte), dus altijd op het vlak en niet in een gat;
    de hoogte is die van het vlak op die plek."""
    drie = vlak["driehoeken"]
    opp = []
    for (a, b, c) in drie:
        opp.append(abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) / 2)
    totaal = sum(opp)
    R = cfg["afstand"]
    if totaal < 0.5 * R * R:
        return []
    cum, s = [], 0.0
    for v in opp:
        s += v
        cum.append(s)
    rng = random.Random(zlib.crc32(f"{vlak['id']}|{vlak['soort']}".encode()))
    rand = RAND_FACTOR * cfg["kroon"]
    cel = R
    raster = defaultdict(list)
    xs = [p[0] for t in drie for p in t]
    ys = [p[1] for t in drie for p in t]
    for bx, by in blokkeren:
        if min(xs) - R <= bx <= max(xs) + R and min(ys) - R <= by <= max(ys) + R:
            raster[(int(bx // cel), int(by // cel))].append((bx, by))
    punten = []
    pogingen = int(totaal / (R * R) * 40) + 100
    reeks = 0
    for _ in range(pogingen):
        if reeks > 400:
            break
        u = rng.random() * totaal
        lo, hi = 0, len(cum) - 1
        while lo < hi:
            m = (lo + hi) // 2
            if cum[m] < u:
                lo = m + 1
            else:
                hi = m
        a, b, c = drie[lo]
        r1, r2 = rng.random(), rng.random()
        if r1 + r2 > 1:
            r1, r2 = 1 - r1, 1 - r2
        x = a[0] + r1 * (b[0] - a[0]) + r2 * (c[0] - a[0])
        y = a[1] + r1 * (b[1] - a[1]) + r2 * (c[1] - a[1])
        z = a[2] + r1 * (b[2] - a[2]) + r2 * (c[2] - a[2])
        if not (gebied[0] <= x <= gebied[2] and gebied[1] <= y <= gebied[3]):
            reeks += 1
            continue
        ci, cj = int(x // cel), int(y // cel)
        if any(math.hypot(x - qx, y - qy) < R for i in (ci - 1, ci, ci + 1) for j in (cj - 1, cj, cj + 1)
               for qx, qy in raster.get((i, j), ())):
            reeks += 1
            continue
        if afstand_tot_randen(x, y, vlak["randen"]) < rand:
            reeks += 1
            continue
        raster[(ci, cj)].append((x, y))
        punten.append((x, y, z))
        reeks = 0
    return punten


def maak_items(vlakken, opties, gebied, blokkeren):
    """De objecten per soort: {soort: [item, ...]} voor CreateObjects (zonder laag), plus tellingen per soort."""
    items = {s: [] for s in SOORTEN}
    instellingen = opties.get("cfg") or SOORTEN
    for vlak in vlakken:
        cfg = instellingen[vlak["soort"]]
        rng = random.Random(zlib.crc32(f"maat|{vlak['id']}".encode()))
        for n, (x, y, z) in enumerate(verdeel(vlak, cfg, gebied, blokkeren)):
            kroon = round(cfg["kroon"] * rng.uniform(0.9, 1.15), 2)
            hoogte = round(cfg["hoogte"] * rng.uniform(0.85, 1.2), 2)
            items[vlak["soort"]].append({
                "libraryPartName": opties["object"],
                "coordinates": {"x": round(x, 3), "y": round(y, 3), "z": round(opties["z"] if opties["z"] is not None else z, 3)},
                "dimensions": {"x": kroon, "y": kroon, "z": hoogte}, "floorIndex": 0,
                "angle": round(rng.uniform(0, 2 * math.pi), 4), "_id": f"GROEN-{vlak['id']}-{n}"})
    return items


# ---------------------------------------------------------------- plaatsen
def _maak(k, items, voortgang, stop):
    wissel = getattr(k, "PlattegrondActief", None)
    r = B.maak_alle(k, items, voortgang, stop)
    if r["gelukt"] == 0 and wissel is not None and not B.venster_is_plattegrond(k):
        print("\nHet aanmaken mislukte in het actieve venster; ik probeer het opnieuw in de plattegrond.")
        with wissel():
            r = B.maak_alle(k, items, voortgang, stop)
    return r


def plaats_groen(k, gebied, opties=None, voortgang=None, stop=None, uitsnede_gebied=None):
    """Verdeelt het gekozen bibliotheekobject over de groenvlakken in het gebied (x0, y0, x1, y1 in RD).

    Geeft een woordenboek met onder meer 'gelukt', 'mislukt' en 'overgeslagen'."""
    o = standaard_opties(**(opties or {}))
    uit = {"vlakken": 0, "gelukt": 0, "mislukt": 0, "overgeslagen": 0}
    cfg, meldingen = soortinstellingen(o.get("maten"))
    o["cfg"] = cfg
    for m in meldingen:
        print("LET OP: " + m)
    soorten = tuple(s for s in SOORTEN if o.get(s))
    if not soorten:
        print("Geen soort gekozen.")
        return uit
    if voortgang:
        voortgang("Groen: vlakken ophalen", None)
    vlakken = vlakken_uit_pdok(gebied, uitsnede_gebied or tuple(gebied), soorten)      # dezelfde uitsnede als het terrein en de gebouwen
    uit["vlakken"] = len(vlakken)
    tel = Counter(v["soort"] for v in vlakken)
    print(f"{len(vlakken)} groenvlakken in de 3D Basisvoorziening voor dit gebied: "
          + (", ".join(f"{SOORTEN[s]['naam']} {n}" for s, n in tel.items()) or "geen"))
    if not vlakken:
        return uit
    try:                                                            # de losse bomen uit de BGT: daar komt niets naast
        blokkeren = [(p["x"], p["y"]) for p in B.punten_uit_pdok(k, (gebied[0] - 10, gebied[1] - 10, gebied[2] + 10, gebied[3] + 10))]
        print(f"   {len(blokkeren)} BGT-vegetatiepunten blijven vrij.")
    except Exception as fout:
        blokkeren = []
        print(f"   (de BGT-vegetatiepunten konden niet worden opgehaald: {fout})")
    items = maak_items(vlakken, o, gebied, blokkeren)
    for s in soorten:
        c = cfg[s]
        print(f"   {c['naam']}: {len(items[s])} objecten (afstand {c['afstand']:g} m, kroon {c['kroon']:g} m, hoogte {c['hoogte']:g} m) "
              f"op laag {c['laag']}")
    totaal = sum(len(v) for v in items.values())
    if totaal > WAARSCHUWING_AANTAL:
        print(f"   LET OP: {totaal} objecten; dat kan Archicad traag maken. Een kleiner gebied of minder soorten helpt.")
    for s in soorten:
        for it in items[s][:2]:
            c = it["coordinates"]
            print(f"   bijvoorbeeld ({s}): {it['libraryPartName']} op ({c['x']:.2f}, {c['y']:.2f}) op {c['z']:.2f} m NAP")
    if o["droog"] or not totaal:
        if o["droog"]:
            print("\nDroog: er is niets aangemaakt.")
        return uit

    k.MAPNAAM = "PDOK Import"
    for s in soorten:
        if not items[s]:
            continue
        c = cfg[s]
        laag = k.zorg_voor_laag(c["laag"])
        try:
            bestaand = B.bestaande_ids(k, laag)
        except Exception:
            bestaand = set()
        nieuw = [it for it in items[s] if it["_id"] not in bestaand]
        if len(nieuw) < len(items[s]):
            uit["overgeslagen"] += len(items[s]) - len(nieuw)
            print(f"   {c['naam']}: {len(items[s]) - len(nieuw)} staan al op de laag {c['laag']} en worden overgeslagen.")
        if not nieuw:
            continue
        for it in nieuw:
            it["layerIndex"] = laag
        r = _maak(k, nieuw, voortgang, stop)
        uit["gelukt"] += r["gelukt"]
        uit["mislukt"] += r["mislukt"]
        for i in range(0, len(r["gemaakt"]), 100):
            k.tapir("SetDetailsOfElements", {"elementsWithDetails": [
                {"elementId": e["elementId"], "details": {"layerIndex": laag, "id": it["_id"]}}
                for e, it in r["gemaakt"][i:i + 100]]})
        print(f"   {c['naam']}: {r['gelukt']} aangemaakt, {r['mislukt']} mislukt, op de laag {c['laag']}.")
        for tekst, n in r["fouten"].most_common(3):
            print(f"      {n} x: {tekst}")
    print(f"\n{uit['gelukt']} groenobjecten aangemaakt, {uit['mislukt']} mislukt.")
    return uit
