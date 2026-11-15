"""Lichtmasten: plaats een Archicad-lamp (standaard "Lantaarnpaal 04") op de lichtmasten van de BGT.

De posities komen uit de BGT (collectie paal, soort lichtmast in het plus-type, via PDOK) voor het gebied dat je opgeeft. De hoogte komt, net
als bij de bomen, uit de 3D Basisvoorziening van PDOK: er hoeven geen terreinmeshes in Archicad te staan. Een lantaarnpaal is in Archicad een
Lamp (een eigen gereedschap) en geen Object; daarom gebruikt dit de opdracht CreateLamps van de add-on (vanaf versie 0.21.0).

De BGT geeft geen hoogte of draaiing van een paal: de lamp komt zoals de bibliotheek hem tekent, op het terrein. Elk element krijgt het
Element-ID LAMP-<BGT-id>, zodat een tweede keer importeren geen dubbelen maakt. De lampen komen op de laag 3D_lichtmasten in de map PDOK Import.

Dezelfde functie (plaats_lichtmasten) wordt gebruikt door het kaartvenster (kaart.py).
"""
import json
from collections import Counter

import bomen as B                                   # de terreinhoogte uit de 3D Basisvoorziening en de hulpfuncties van de bomen

STANDAARD_OBJECT = "Lantaarnpaal 04"
BRON_COLLECTIE = "paal"
SOORT = "lichtmast"
LAAG = "3D_lichtmasten"
MIN_ADDON = (0, 21, 0)                              # CreateLamps bestaat vanaf deze versie van de add-on


def punten_uit_pdok(k, gebied):
    """De lichtmasten van de BGT in het gebied (x0, y0, x1, y1 in RD), met een vast ID per paal, en een telling van alle soorten palen."""
    features = k.haal_features("bgt", BRON_COLLECTIE, *gebied)
    uit, soorten = [], Counter()
    for f in features:
        eigen = f.get("properties") or {}
        if eigen.get("eind_registratie"):
            continue                                        # een beëindigde paal staat er niet meer
        soort = str(eigen.get("plus_type") or eigen.get("plus-type") or eigen.get("type") or "").strip().lower()
        soorten[soort or "(leeg)"] += 1
        if SOORT not in soort or (eigen.get("relatieve_hoogteligging") or 0) != 0:
            continue
        g = f.get("geometry") or {}
        fid = str(f.get("id") or eigen.get("lokaal_id") or eigen.get("lokaalid") or eigen.get("identificatie") or "")
        co = g.get("coordinates")
        if g.get("type") == "Point" and co:
            lijst = [co]
        elif g.get("type") == "MultiPoint" and co:
            lijst = co
        else:
            continue
        for n, c in enumerate(lijst):
            if not (gebied[0] <= c[0] <= gebied[2] and gebied[1] <= c[1] <= gebied[3]):
                continue
            sleutel = (fid + (f"-{n}" if len(lijst) > 1 else "")) if fid else f"{c[0]:.2f}_{c[1]:.2f}"
            uit.append({"x": c[0], "y": c[1], "type": soort, "id": f"LAMP-{sleutel}"})
    return uit, soorten


def bestaande_ids(k, laag):
    """De Element-ID's van de lampen die al op de laag staan."""
    r = k.tapir("GetDetailsOfElements", {"types": ["Lamp"], "layerIndices": [laag]})
    d = k.pak(r).get("detailsOfElements", []) if r.get("succeeded") else []
    return {x.get("id") for x in d if isinstance(x, dict) and x.get("layerIndex") == laag and x.get("id")}


def addon_kan_lampen(k):
    try:
        import re
        versie = re.findall(r"\d+\.\d+\.\d+", json.dumps(k.tapir("GetAddOnVersion")))
        return bool(versie) and tuple(int(x) for x in versie[0].split(".")) >= MIN_ADDON
    except Exception:
        return False


def maak_alle(k, items, voortgang=None, stop=None):
    uit = {"gelukt": 0, "mislukt": 0, "fouten": Counter()}
    for i in range(0, len(items), 50):
        if stop and stop():
            print("   Gestopt op verzoek.")
            break
        if voortgang:
            voortgang(f"Lichtmasten: {i} van {len(items)}", i / max(1, len(items)))
        deel = items[i:i + 50]
        r = k.tapir("CreateLamps", {"lampsData": deel})
        if not r.get("succeeded"):
            uit["mislukt"] += len(deel)
            uit["fouten"][str(r.get("error", r))[:150]] += len(deel)
            continue
        for e in k.pak(r).get("elements", []):
            if "elementId" in e:
                uit["gelukt"] += 1
            else:
                uit["mislukt"] += 1
                uit["fouten"][str(e.get("error", e))[:150]] += 1
    return uit


def plaats_lichtmasten(k, gebied, opties=None, voortgang=None, stop=None):
    """Plaatst de gekozen lamp op de lichtmasten van de BGT in het gebied (x0, y0, x1, y1 in RD).

    opties: object (naam van de lamp in de bibliotheek) en z (een vaste hoogte, bijvoorbeeld 0 bij vlak terrein; anders de terreinhoogte).
    Geeft een woordenboek met onder meer 'gelukt', 'mislukt', 'overgeslagen' en 'punten'."""
    o = {"object": STANDAARD_OBJECT, "z": None, "laag": LAAG}
    o.update(opties or {})
    uit = {"punten": 0, "gelukt": 0, "mislukt": 0, "overgeslagen": 0, "zonder_terrein": 0}

    def meld(tekst, f=None):
        if voortgang:
            voortgang(tekst, f)

    if not addon_kan_lampen(k):
        print(f"De lichtmasten vragen add-on {'.'.join(map(str, MIN_ADDON))} of nieuwer (de opdracht CreateLamps). Werk het .apx bij en probeer het opnieuw.")
        return uit
    meld("Lichtmasten: BGT-palen ophalen")
    punten, soorten = punten_uit_pdok(k, gebied)
    uit["punten"] = len(punten)
    print(f"{sum(soorten.values())} palen in de BGT voor dit gebied (x {gebied[0]:.0f}-{gebied[2]:.0f}, y {gebied[1]:.0f}-{gebied[3]:.0f}); "
          f"{len(punten)} daarvan zijn lichtmasten op maaiveld binnen het gebied.")
    if soorten:
        print("   soorten palen (plus_type): " + ", ".join(f"{t} {n}" for t, n in soorten.most_common(8)))
    if not punten:
        return uit

    lagen = k.alle_lagen()
    bestaand = bestaande_ids(k, lagen[o["laag"]]["index"]) if o["laag"] in lagen else set()
    nieuw = [p for p in punten if p["id"] not in bestaand]
    uit["overgeslagen"] = len(punten) - len(nieuw)
    if uit["overgeslagen"]:
        print(f"   {uit['overgeslagen']} lichtmasten staan al op de laag {o['laag']} en worden overgeslagen.")
    punten = nieuw
    if not punten:
        print("Er is niets nieuws te plaatsen.")
        return uit

    meld("Lichtmasten: terreinhoogte bepalen")
    if o["z"] is not None:
        hoogtes = [o["z"]] * len(punten)
    else:
        print("Terreinhoogte bepalen uit de 3D Basisvoorziening van PDOK...")
        try:
            hoogtes, _ = B.hoogtes_uit_terreindata(punten)
        except Exception as fout:
            print(f"   De terreinhoogte kon niet worden opgehaald ({fout}).")
            return uit
    items = []
    for p, z in zip(punten, hoogtes):
        if z is None:
            uit["zonder_terrein"] += 1
            continue
        items.append({"libraryPartName": o["object"], "coordinates": {"x": round(p["x"], 3), "y": round(p["y"], 3), "z": round(z, 3)},
                      "floorIndex": 0, "id": p["id"]})
    if uit["zonder_terrein"]:
        print(f"   {uit['zonder_terrein']} lichtmasten liggen niet op of vlak bij terrein en worden overgeslagen.")
    if not items:
        return uit
    for it in items[:2]:
        c = it["coordinates"]
        print(f"   bijvoorbeeld: {it['libraryPartName']} op ({c['x']:.2f}, {c['y']:.2f}) op {c['z']:.2f} m")

    k.MAPNAAM = "PDOK Import"
    laag = k.zorg_voor_laag(o["laag"])
    for it in items:
        it["layerIndex"] = laag
    wissel = getattr(k, "PlattegrondActief", None)
    r = maak_alle(k, items, voortgang, stop)
    if r["gelukt"] == 0 and wissel is not None and not B.venster_is_plattegrond(k):
        print("\nHet aanmaken mislukte in het actieve venster; ik probeer het opnieuw in de plattegrond.")
        with wissel():
            r = maak_alle(k, items, voortgang, stop)
    uit["gelukt"], uit["mislukt"] = r["gelukt"], r["mislukt"]
    print(f"\n{r['gelukt']} lichtmasten aangemaakt, {r['mislukt']} mislukt, op de laag {o['laag']}.")
    for tekst, n in r["fouten"].most_common(4):
        print(f"   {n} x: {tekst}")
    if r["fouten"]:
        print("   Controleer de naam van de lamp (die is gelokaliseerd); zoek hem in het vak bij de lichtmasten.")
    return uit
