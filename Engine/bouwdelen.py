"""Overige bouwdelen: overig bouwwerk en gebouwinstallatie (overkappingen, open loodsen, luifels, schuren, tanks, ...) uit de BGT als morph.

De BGT heeft voor deze objecten alleen een vlak (de omtrek), geen hoogte, en de 3D Basisvoorziening kent ze hoogstens als vlak op het terrein.
De hoogte is hier dus een AANNAME per soort. Die staat als regel in de stijltabel (stijl.py, of je eigen stijlen.json): een `vorm` ("blok" of
"plaat"), een `hoogte` en bij een plaat een `dikte`. Een blok staat op het maaiveld; een plaat (overkapping, luifel) hangt op die hoogte boven het
maaiveld. Soorten zonder zo'n regel worden overgeslagen en in het log genoemd.

Het maaiveld komt uit de 3D Basisvoorziening van PDOK, net als bij de bomen (er hoeven geen terreinmeshes in Archicad te staan). De morphs komen op de
laag 3D_bouwdelen in de map PDOK Import, met het oppervlak PDOK_<naam van de regel> en het Element-ID BWD-<BGT-id> (nogmaals importeren slaat bestaande
over).

Dezelfde functie (plaats_bouwdelen) wordt gebruikt door het kaartvenster (kaart.py).
"""
import json
import math
from collections import Counter

import bomen as B
import drie_d as D
import stijl

LAAG = "3D_bouwdelen"
COLLECTIES = ("overigbouwwerk", "gebouwinstallatie")
MIN_OPPERVLAK = 0.5            # m2: kleinere vlakken zijn ruis
MAX_MONSTERS = 14              # hoogstens zoveel punten van de omtrek om het maaiveld te bepalen


def _ring_schoon(ring):
    """Een GeoJSON-ring zonder sluitpunt en zonder dubbele punten, als lijst (x, y)."""
    uit = []
    for p in ring:
        q = (float(p[0]), float(p[1]))
        if not uit or math.hypot(q[0] - uit[-1][0], q[1] - uit[-1][1]) > 0.01:
            uit.append(q)
    if len(uit) > 1 and math.hypot(uit[0][0] - uit[-1][0], uit[0][1] - uit[-1][1]) <= 0.01:
        uit.pop()
    return uit


def _gesigneerd_oppervlak(ring):
    return sum(ring[i][0] * ring[(i + 1) % len(ring)][1] - ring[(i + 1) % len(ring)][0] * ring[i][1] for i in range(len(ring))) / 2


def vlakken_uit_pdok(k, gebied, regels):
    """De vlakken van de BGT in het gebied met een regel in de stijltabel.
    Geeft (lijst, telling zonder regel, telling per soort, telling van wat PDOK gaf en wat er is overgeslagen of meegenomen)."""
    uit, zonder, soorten, tel = [], Counter(), Counter(), Counter()
    for laag in COLLECTIES:
        for f in k.haal_features("bgt", laag, *gebied):
            tel[f"gegeven {laag}"] += 1
            eigen = f.get("properties") or {}
            geo = f.get("geometry") or {}
            niveau = eigen.get("relatieve_hoogteligging") or 0
            if eigen.get("eind_registratie"):
                tel["beëindigd"] += 1
                continue
            if niveau < 0:
                tel["onder maaiveld"] += 1                    # een kelderluik of tunnel: niet in 3D
                continue
            st_eig = stijl.eig_uit_2d(eigen)
            soort = (st_eig.get("type") or "").strip() or "(leeg)"
            if geo.get("type") == "Polygon":
                polygonen = [geo.get("coordinates")]
            elif geo.get("type") == "MultiPolygon":
                polygonen = geo.get("coordinates") or []
            else:
                tel["geen vlak"] += 1
                continue
            regel = stijl.kies(laag, st_eig, "3d", regels)
            fid = str(f.get("id") or eigen.get("lokaal_id") or eigen.get("lokaalid") or eigen.get("identificatie") or "")
            for n, pol in enumerate(polygonen):
                if not pol or not pol[0]:
                    continue
                buiten = _ring_schoon(pol[0])
                if len(buiten) < 3:
                    continue
                if _gesigneerd_oppervlak(buiten) < 0:
                    buiten.reverse()                         # de buitenrand tegen de klok in
                gaten = []
                for g in pol[1:]:
                    gat = _ring_schoon(g)
                    if len(gat) >= 3:
                        if _gesigneerd_oppervlak(gat) > 0:
                            gat.reverse()                    # een gat met de klok mee
                        gaten.append(gat)
                opp = abs(_gesigneerd_oppervlak(buiten)) - sum(abs(_gesigneerd_oppervlak(g)) for g in gaten)
                cx = sum(p[0] for p in buiten) / len(buiten)
                cy = sum(p[1] for p in buiten) / len(buiten)
                if opp < MIN_OPPERVLAK:
                    tel["te klein"] += 1
                    continue
                if not (gebied[0] <= cx <= gebied[2] and gebied[1] <= cy <= gebied[3]):
                    tel["zwaartepunt buiten het gebied"] += 1
                    continue
                if niveau > 0:
                    tel["op een hoger niveau dan maaiveld meegenomen"] += 1
                soorten[f"{laag}: {soort}"] += 1
                if not regel or "vorm" not in regel:
                    zonder[f"{laag}: {soort}"] += 1
                    continue
                sleutel = (fid + (f"-{n}" if len(polygonen) > 1 else "")) if fid else f"{cx:.2f}_{cy:.2f}"
                uit.append({"id": f"BWD-{sleutel}", "buiten": buiten, "gaten": gaten, "regel": regel, "soort": f"{laag}: {soort}", "opp": opp})
    return uit, zonder, soorten, tel


def lichaam(buiten, gaten, z_onder, z_boven, oppervlak=None, kappen_als_driehoeken=False):
    """Trekt een omtrek (met gaten) uit tussen twee hoogtes. Geeft (basePoint, body) met de hoekpunten ten opzichte van het basispunt.

    De buitenrand loopt tegen de klok in en de gaten met de klok mee; dan wijzen alle vlakken naar buiten."""
    bx, by, bz = min(p[0] for p in buiten), min(p[1] for p in buiten), z_onder
    verts = []

    def punt(x, y, z):
        verts.append({"x": round(x - bx, 3), "y": round(y - by, 3), "z": round(z - bz, 3)})
        return len(verts) - 1
    ringen = [buiten] + list(gaten)
    onder = [[punt(x, y, z_onder) for x, y in r] for r in ringen]
    boven = [[punt(x, y, z_boven) for x, y in r] for r in ringen]
    polys = []
    if kappen_als_driehoeken:
        wereld = {i: (v["x"], v["y"], v["z"]) for i, v in enumerate(verts)}
        for ring_ids, omkeren in ((boven, False), (onder, True)):
            tri = D.triangulatie_vlak(wereld, ring_ids[0], ring_ids[1:])
            if tri is None:
                return None
            for a, b, c in tri:
                polys.append({"vertexIds": [c, b, a] if omkeren else [a, b, c]})
    else:
        polys.append({"vertexIds": list(boven[0]), "holes": [{"vertexIds": list(r)} for r in boven[1:]]})
        polys.append({"vertexIds": list(reversed(onder[0])), "holes": [{"vertexIds": list(reversed(r))} for r in onder[1:]]})
    for o, b in zip(onder, boven):                          # de zijkanten
        n = len(o)
        for i in range(n):
            polys.append({"vertexIds": [o[i], o[(i + 1) % n], b[(i + 1) % n], b[i]]})
    if oppervlak:
        for pg in polys:
            pg["surfaceId"] = oppervlak
    return {"x": round(bx, 3), "y": round(by, 3), "z": round(bz, 3)}, {"vertices": verts, "polygons": polys}


def bestaande_ids(k, laag):
    r = k.tapir("GetDetailsOfElements", {"types": ["Morph"], "layerIndices": [laag]})
    d = k.pak(r).get("detailsOfElements", []) if r.get("succeeded") else []
    return {x.get("id") for x in d if isinstance(x, dict) and x.get("layerIndex") == laag and x.get("id")}


def maak_alle(k, items, voortgang=None, stop=None):
    uit = {"gelukt": 0, "mislukt": 0, "fouten": Counter(), "met_driehoeken": 0}
    for i, it in enumerate(items):
        if stop and stop():
            print("   Gestopt op verzoek.")
            break
        if voortgang and i % 10 == 0:
            voortgang(f"Bouwdelen: {i} van {len(items)}", i / max(1, len(items)))
        payload = {"basePoint": it["basis"], "body": it["body"], "layerIndex": it["laag"], "id": it["id"]}
        r = k.tapir("CreateMorphs", {"morphsData": [payload]})
        e = (k.pak(r).get("elements", [None]) or [None])[0] if r.get("succeeded") else None
        if not (e and "elementId" in e):
            alt = lichaam(it["buiten"], it["gaten"], it["z_onder"], it["z_boven"], it["oppervlak"], kappen_als_driehoeken=True)
            if alt:                                          # de boven- en onderkant als driehoeken
                r = k.tapir("CreateMorphs", {"morphsData": [dict(payload, basePoint=alt[0], body=alt[1])]})
                e = (k.pak(r).get("elements", [None]) or [None])[0] if r.get("succeeded") else None
                if e and "elementId" in e:
                    uit["met_driehoeken"] += 1
        if e and "elementId" in e:
            uit["gelukt"] += 1
        else:
            uit["mislukt"] += 1
            uit["fouten"][str((e or {}).get("error", r.get("error", r)))[:150]] += 1
    return uit


def plaats_bouwdelen(k, gebied, opties=None, voortgang=None, stop=None):
    """Maakt van de overige bouwwerken en gebouwinstallaties van de BGT in het gebied (x0, y0, x1, y1 in RD) uitgetrokken morphs.

    opties: z (een vaste maaiveldhoogte, bijvoorbeeld 0 bij vlak terrein; anders het maaiveld uit de 3D Basisvoorziening)."""
    o = {"z": None, "laag": LAAG}
    o.update(opties or {})
    uit = {"vlakken": 0, "gelukt": 0, "mislukt": 0, "overgeslagen": 0, "zonder_regel": 0, "zonder_terrein": 0}

    def meld(tekst, f=None):
        if voortgang:
            voortgang(tekst, f)

    regels, eigen, fout = stijl.laad()
    if fout:
        print(f"LET OP: {fout}")
    if eigen and not any(r.get("vorm") for r in regels):         # een stijlbestand van voor 0.22.0 kent de regels voor bouwdelen nog niet
        regels = regels + [r for r in stijl.standaardregels() if r.get("vorm")]
        print("   Je stijlbestand heeft nog geen regels voor bouwdelen; de standaardregels worden gebruikt (met 'Stijlbestand bijwerken' neem je ze in je bestand op).")
    meld("Bouwdelen: BGT-vlakken ophalen")
    vlakken, zonder, soorten, tel = vlakken_uit_pdok(k, gebied, regels)
    totaal = len(vlakken) + sum(zonder.values())
    print("PDOK geeft voor dit gebied: " + ", ".join(f"{c} {tel.get('gegeven ' + c, 0)}" for c in COLLECTIES) + " (BGT-vlakken, voor het filteren).")
    overgeslagen = [f"{n} {t}" for t, n in tel.items() if not t.startswith("gegeven") and not t.startswith("op een hoger") and n]
    if overgeslagen:
        print("   overgeslagen: " + ", ".join(overgeslagen))
    if tel.get("op een hoger niveau dan maaiveld meegenomen"):
        print(f"   {tel['op een hoger niveau dan maaiveld meegenomen']} liggen boven maaiveld (zoals een luifel boven een andere ondergrond) en zijn meegenomen.")
    print(f"{totaal} overige bouwdelen om te maken (x {gebied[0]:.0f}-{gebied[2]:.0f}, y {gebied[1]:.0f}-{gebied[3]:.0f})"
          + (": " + ", ".join(f"{t} {n}" for t, n in soorten.most_common(8)) if soorten else "."))
    uit["vlakken"] = len(vlakken)
    uit["zonder_regel"] = sum(zonder.values())
    if zonder:
        print("   zonder regel in de stijltabel (dus overgeslagen): " + ", ".join(f"{t} {n}" for t, n in zonder.most_common(6))
              + "; geef ze een regel met een vorm en een hoogte in je stijlbestand als je ze wilt.")
    if not vlakken:
        return uit

    lagen = k.alle_lagen()
    bestaand = bestaande_ids(k, lagen[o["laag"]]["index"]) if o["laag"] in lagen else set()
    nieuw = [v for v in vlakken if v["id"] not in bestaand]
    uit["overgeslagen"] = len(vlakken) - len(nieuw)
    if uit["overgeslagen"]:
        print(f"   {uit['overgeslagen']} staan al op de laag {o['laag']} en worden overgeslagen.")
    vlakken = nieuw
    if not vlakken:
        print("Er is niets nieuws te maken.")
        return uit

    # het maaiveld: de hoogte op de omtrek, in een keer opgevraagd
    meld("Bouwdelen: maaiveld bepalen")
    monsters, bereik = [], []
    for v in vlakken:
        b = v["buiten"]
        stap = max(1, len(b) // MAX_MONSTERS)
        pts = [b[i] for i in range(0, len(b), stap)] + [(sum(p[0] for p in b) / len(b), sum(p[1] for p in b) / len(b))]
        bereik.append((len(monsters), len(monsters) + len(pts)))
        monsters += [{"x": p[0], "y": p[1]} for p in pts]
    if o["z"] is not None:
        hoogtes = [o["z"]] * len(monsters)
    else:
        print("Maaiveld bepalen uit de 3D Basisvoorziening van PDOK...")
        try:
            hoogtes, _ = B.hoogtes_uit_terreindata(monsters)
        except Exception as fout_:
            print(f"   Het maaiveld kon niet worden opgehaald ({fout_}).")
            return uit

    namen = {}                                                # stijlnaam -> (naam, kleur) voor de oppervlakken
    for v in vlakken:
        namen[v["regel"]["naam"]] = (v["regel"]["naam"], v["regel"]["kleur"])
    defs = {f"bwd:{n}": ("PDOK_" + n, tuple(c / 255 for c in kleur), True) for n, (_, kleur) in namen.items()}
    opp = D.zorg_voor_oppervlakken(k, False, defs) or {}

    k.MAPNAAM = "PDOK Import"
    laag = k.zorg_voor_laag(o["laag"])
    items = []
    for v, (a, b) in zip(vlakken, bereik):
        z = [h for h in hoogtes[a:b] if h is not None]
        if not z:
            uit["zonder_terrein"] += 1
            continue
        regel = v["regel"]
        z_min, z_gem = min(z), sum(z) / len(z)
        if regel["vorm"] == "plaat":
            z_onder = z_gem + regel["hoogte"]
            z_boven = z_onder + max(0.05, regel.get("dikte", 0.2))
        else:
            z_onder, z_boven = z_min, z_gem + regel["hoogte"]
        if z_boven - z_onder < 0.05:
            z_boven = z_onder + 0.05
        oppervlak = (opp.get(f"bwd:{regel['naam']}") or {}).get("guid")
        oppervlak = {"guid": oppervlak} if oppervlak else None
        basis, body = lichaam(v["buiten"], v["gaten"], z_onder, z_boven, oppervlak)
        items.append({"id": v["id"], "basis": basis, "body": body, "laag": laag, "buiten": v["buiten"], "gaten": v["gaten"],
                      "z_onder": z_onder, "z_boven": z_boven, "oppervlak": oppervlak, "soort": v["soort"], "regel": regel})
    if uit["zonder_terrein"]:
        print(f"   {uit['zonder_terrein']} liggen niet op of vlak bij terrein en worden overgeslagen.")
    if not items:
        return uit
    for it in items[:3]:
        print(f"   bijvoorbeeld: {it['soort']} bij ({it['basis']['x']:.1f}, {it['basis']['y']:.1f}), {it['regel']['vorm']} van {it['z_onder']:.2f} tot {it['z_boven']:.2f} m")
    voorbeeld = Counter((it["regel"]["naam"], it["regel"]["vorm"], it["regel"]["hoogte"]) for it in items)
    print("   per soort: " + ", ".join(f"{n} x {nm} ({vorm}, {h:g} m)" for (nm, vorm, h), n in voorbeeld.most_common(8)))
    r = maak_alle(k, items, voortgang, stop)
    uit["gelukt"], uit["mislukt"] = r["gelukt"], r["mislukt"]
    print(f"\n{r['gelukt']} bouwdelen aangemaakt, {r['mislukt']} mislukt, op de laag {o['laag']}."
          + (f" ({r['met_driehoeken']} met boven- en onderkant als driehoeken.)" if r["met_driehoeken"] else ""))
    for tekst, n in r["fouten"].most_common(4):
        print(f"   {n} x: {tekst}")
    return uit
