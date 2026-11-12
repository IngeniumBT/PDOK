"""Importeert een bestemmingsplan (IMRO-GML) in Archicad.

Gebruik (in de map waar ook kaart.py staat):

    python plan_import.py plannen\\NL_IMRO_0173_BP09029-va01.gml

Optioneel alleen een gebied (RD-coordinaten in meters): xmin ymin xmax ymax

    python plan_import.py plan.gml 260063 482696 260237 482889

Met --teksten worden alleen de teksten bij de maatvoeringen getekend (handig als
je de vlakken en lijnen al eerder hebt geimporteerd):

    python plan_import.py plan.gml --teksten

Bij elke maatvoering van het plan (maximale bouwhoogte, goothoogte, bebouwings-
percentage, aantal wooneenheden) komt een tekst op de plattegrond, op het
plaatsingspunt dat het plan zelf aangeeft, op de laag BP_maatvoering.

Het script hergebruikt de functies uit kaart.py (verbinding met Archicad, lagen,
mappen en het tekenen van vlakken en lijnen), dus kaart.py moet in dezelfde map staan.
"""
import collections
import glob
import math
import os
import re
import sys
import xml.etree.ElementTree as ET

# ------------------------------------------------------------------ Instellingen

MAP = "PDOK Import"          # map in de laaginstellingen waarin de lagen komen
LAAGVOORVOEGSEL = "BP_"      # Archicad-lagen worden BP_enkelbestemming_wonen enz.
CONTOURPEN = 1               # randpen van de gevulde bestemmingsvlakken
LIJNPEN = 1                  # standaard pen voor omtrekken en lijnen
LIJNPEN_PER_SOORT = {}       # bijvoorbeeld {"Bouwvlak": 3, "Bestemmingsplangebied": 5}
MIN_OPPERVLAK = 0.0001       # m2, kleinere vlakken worden overgeslagen
BOOG_AFWIJKING = 0.02        # m, maximale afwijking bij het omzetten van bogen naar lijnstukken

# Soorten waarvan we het vlak vullen (met kleur per bestemmingshoofdgroep).
GEVULD = {"Enkelbestemming"}
# Soorten die we niet tekenen.
OVERSLAAN = set()
# Soorten die als tekst op de plattegrond komen (op hun plaatsingspunt).
TEKST_SOORTEN = {"Maatvoering"}
TEKSTEN_TEKENEN = True       # zet op False als je de maatvoeringen niet als tekst wilt
TEKSTHOOGTE = 2.5            # hoogte van de tekst, zoals CreateTexts die verwacht
TEKSTPEN = 1                 # pen van de tekst
TEKSTLAAG = LAAGVOORVOEGSEL + "maatvoering"

# Vulkleur (rood, groen, blauw, 0-255) per bestemmingshoofdgroep.
KLEUREN = {
    "wonen": (255, 205, 100),
    "tuin": (225, 235, 175),
    "groen": (140, 200, 110),
    "verkeer": (200, 200, 200),
    "maatschappelijk": (215, 160, 185),
    "bedrijf": (195, 175, 215),
    "bedrijventerrein": (195, 175, 215),
    "agrarisch": (240, 235, 160),
    "centrum": (240, 150, 130),
    "gemengd": (240, 175, 140),
    "sport": (165, 215, 150),
    "horeca": (240, 160, 130),
    "recreatie": (160, 215, 160),
    "water": (150, 195, 235),
    "natuur": (120, 185, 110),
    "bos": (110, 170, 100),
    "detailhandel": (240, 140, 120),
    "kantoor": (200, 185, 225),
    "cultuur_en_ontspanning": (215, 165, 200),
    "wonen_woonwagenstandplaats": (255, 205, 100),
}
KLEUR_ONBEKEND = (220, 220, 220)

# ------------------------------------------------------------------ Lezen van het GML


def lokaal(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def kind(el, naam):
    for c in el:
        if lokaal(c.tag) == naam:
            return c
    return None


def kinderen(el, naam):
    return [c for c in el if lokaal(c.tag) == naam]


def afstammelingen(el, naam):
    return [d for d in el.iter() if lokaal(d.tag) == naam]


def posities(tekst):
    waarden = [float(x) for x in tekst.split()]
    return [(waarden[i], waarden[i + 1]) for i in range(0, len(waarden) - 1, 2)]


def boog(p1, p2, p3):
    """Punten van een cirkelboog door drie punten, van p1 (niet inbegrepen) tot p3."""
    ax, ay = p1
    bx, by = p2
    cx, cy = p3
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-9:  # bijna een rechte lijn
        return [p2, p3]
    s1, s2, s3 = ax * ax + ay * ay, bx * bx + by * by, cx * cx + cy * cy
    ux = (s1 * (by - cy) + s2 * (cy - ay) + s3 * (ay - by)) / d
    uy = (s1 * (cx - bx) + s2 * (ax - cx) + s3 * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    a1 = math.atan2(ay - uy, ax - ux)
    a2 = math.atan2(by - uy, bx - ux)
    a3 = math.atan2(cy - uy, cx - ux)
    tau = 2 * math.pi
    if (a2 - a1) % tau < (a3 - a1) % tau:   # tegen de klok in
        sweep = (a3 - a1) % tau
    else:                                    # met de klok mee
        sweep = -((a1 - a3) % tau)
    if r > BOOG_AFWIJKING:
        stap = 2 * math.acos(max(0.0, 1 - BOOG_AFWIJKING / r))
    else:
        stap = math.pi / 4
    n = max(2, int(abs(sweep) / max(stap, 1e-6)) + 1)
    punten = [(ux + r * math.cos(a1 + sweep * k / n), uy + r * math.sin(a1 + sweep * k / n))
              for k in range(1, n)]
    punten.append(p3)
    return punten


def segment_punten(el):
    """Punten van een Ring of Curve uit lijnstukken (LineStringSegment) en bogen (Arc)."""
    punten = []
    for seg in el.iter():
        naam = lokaal(seg.tag)
        if naam not in ("LineStringSegment", "Arc"):
            continue
        pl = kind(seg, "posList")
        if pl is None or not pl.text:
            continue
        p = posities(pl.text)
        if naam == "LineStringSegment":
            for pt in p:
                if not punten or pt != punten[-1]:
                    punten.append(pt)
        elif len(p) >= 3:
            if not punten:
                punten.append(p[0])
            punten += boog(p[0], p[1], p[2])
    return punten


def ring_punten(ring):
    """Een ring is een LinearRing met posList, of een Ring met bogen en lijnstukken."""
    lin = kind(ring, "LinearRing")
    if lin is not None:
        pl = kind(lin, "posList")
        return posities(pl.text) if pl is not None and pl.text else []
    return segment_punten(ring)


def oppervlak(punten):
    som = 0.0
    for i in range(len(punten)):
        x1, y1 = punten[i]
        x2, y2 = punten[(i + 1) % len(punten)]
        som += x1 * y2 - x2 * y1
    return abs(som) / 2


def lees_plan(pad):
    """Geeft (metadata, objecten). Elk object heeft soort, naam, groep, vlakken en lijnen."""
    wortel = ET.parse(pad).getroot()
    meta = {}
    objecten = []
    for lid in wortel.iter():
        if lokaal(lid.tag) not in ("featureMember", "featureMembers"):
            continue
        for el in list(lid):
            soort = lokaal(el.tag)
            if soort.startswith("Metadata"):
                meta = {lokaal(c.tag): c.text for c in el}
                continue

            def tekst(naam):
                x = kind(el, naam)
                return x.text.strip() if x is not None and x.text else None

            geo = kind(el, "geometrie")
            vlakken = []
            lijnen = []
            if geo is not None:
                for patch in afstammelingen(geo, "PolygonPatch"):
                    ext = kind(patch, "exterior")
                    buiten = ring_punten(ext) if ext is not None else []
                    gaten = [ring_punten(i) for i in kinderen(patch, "interior")]
                    vlakken.append({"buiten": buiten, "gaten": gaten})
                if not vlakken:
                    for curve in afstammelingen(geo, "Curve"):
                        lijnen.append(segment_punten(curve))
                    for ls in afstammelingen(geo, "LineString"):
                        pl = kind(ls, "posList")
                        if pl is not None and pl.text:
                            lijnen.append(posities(pl.text))
            waarden = []
            for w in afstammelingen(el, "WaardeEnType"):
                waarde = kind(w, "waarde")
                soort_w = kind(w, "waardeType")
                if waarde is not None and waarde.text:
                    waarden.append((soort_w.text.strip() if soort_w is not None and soort_w.text
                                    else "", waarde.text.strip()))
            punten = []
            for lp in afstammelingen(el, "Labelpositie"):
                for pos in afstammelingen(lp, "pos"):
                    if pos.text:
                        p = posities(pos.text)
                        if p:
                            punten.append(p[0])
            objecten.append({
                "id": el.attrib.get("{http://www.opengis.net/gml}id") or tekst("identificatie"),
                "waarden": waarden,
                "punten": punten,
                "soort": soort,
                "naam": tekst("naam"),
                "groep": tekst("bestemmingshoofdgroep"),
                "vlakken": vlakken,
                "lijnen": lijnen,
            })
    return meta, objecten


# ------------------------------------------------------------ Elementen voor Archicad


def schoon(punten):
    """Verwijder punten die (bijna) op elkaar liggen, en zet om naar x/y-woordenboeken."""
    uit = []
    for x, y in punten:
        if uit and abs(x - uit[-1]["x"]) < 0.001 and abs(y - uit[-1]["y"]) < 0.001:
            continue
        uit.append({"x": x, "y": y})
    return uit


def zonder_sluitpunt(punten):
    """Een vulling in Archicad mag het beginpunt niet aan het einde herhalen."""
    while (len(punten) > 1 and abs(punten[0]["x"] - punten[-1]["x"]) < 0.001
           and abs(punten[0]["y"] - punten[-1]["y"]) < 0.001):
        punten.pop()
    return punten


def met_sluitpunt(punten):
    """Een gesloten polylijn heeft het beginpunt wel aan het einde."""
    uit = list(punten)
    if (abs(uit[0]["x"] - uit[-1]["x"]) >= 0.001
            or abs(uit[0]["y"] - uit[-1]["y"]) >= 0.001):
        uit.append(dict(uit[0]))
    return uit


def pts_oppervlak(punten):
    return oppervlak([(p["x"], p["y"]) for p in punten])


def slug(tekst):
    return re.sub(r"[^a-z0-9]+", "_", (tekst or "onbekend").lower()).strip("_") or "onbekend"


def getal(tekst):
    """10.0 wordt 10 en 7.5 wordt 7,5."""
    try:
        w = float(tekst)
    except ValueError:
        return tekst
    return str(int(w)) if w == int(w) else str(w).replace(".", ",")


def maatvoering_tekst(waarden):
    """Bijvoorbeeld 'BH 10 / GH 6 / 80%'."""
    volgorde = {"bouwhoogte": 0, "goothoogte": 1, "bebouwingspercentage": 2, "wooneenheden": 3}
    delen = []
    for soort, waarde in waarden:
        laag = soort.lower()
        w = getal(waarde)
        if "bouwhoogte" in laag:
            delen.append((volgorde["bouwhoogte"], f"BH {w}"))
        elif "goothoogte" in laag:
            delen.append((volgorde["goothoogte"], f"GH {w}"))
        elif "bebouwingspercentage" in laag:
            delen.append((volgorde["bebouwingspercentage"], f"{w}%"))
        elif "wooneenheden" in laag:
            delen.append((volgorde["wooneenheden"], f"{w} won."))
        else:
            delen.append((9, f"{soort} {w}".strip()))
    delen.sort(key=lambda d: d[0])
    return " / ".join(t for _, t in delen)


def laagnaam(obj):
    soort = slug(obj["soort"])
    if obj["soort"] in ("Enkelbestemming", "Dubbelbestemming") and obj["groep"]:
        return f"{LAAGVOORVOEGSEL}{soort}_{slug(obj['groep'])}"
    return f"{LAAGVOORVOEGSEL}{soort}"


def raakt_gebied(punten, gebied):
    if not gebied:
        return True
    xmin, ymin, xmax, ymax = gebied
    xs = [p[0] for p in punten]
    ys = [p[1] for p in punten]
    return not (max(xs) < xmin or min(xs) > xmax or max(ys) < ymin or min(ys) > ymax)


def bouw_groepen(objecten, gebied=None):
    """Sorteert de objecten per Archicad-laag in gevulde vlakken en lijnen."""
    groepen = collections.OrderedDict()
    teksten = []
    overgeslagen = collections.Counter()

    def groep(obj):
        naam = laagnaam(obj)
        if naam not in groepen:
            groepen[naam] = {"soort": obj["soort"], "groep": obj["groep"],
                             "vlakken": [], "lijnen": []}
        return groepen[naam]

    volgorde = sorted(objecten, key=lambda o: (o["soort"] not in GEVULD, o["soort"]))
    for obj in volgorde:
        if obj["soort"] in OVERSLAAN:
            overgeslagen[obj["soort"]] += 1
            continue
        if obj["soort"] in TEKST_SOORTEN:
            inhoud = maatvoering_tekst(obj["waarden"])
            if not inhoud:
                overgeslagen["maatvoering zonder waarden"] += 1
                continue
            for x, y in obj["punten"]:
                if raakt_gebied([(x, y)], gebied):
                    teksten.append({"x": x, "y": y, "tekst": inhoud})
            continue
        for v in obj["vlakken"]:
            if len(v["buiten"]) < 3 or not raakt_gebied(v["buiten"], gebied):
                continue
            buiten = zonder_sluitpunt(schoon(v["buiten"]))
            if len(buiten) < 3 or pts_oppervlak(buiten) < MIN_OPPERVLAK:
                overgeslagen["te klein of ongeldig"] += 1
                continue
            gaten = []
            for g in v["gaten"]:
                gat = zonder_sluitpunt(schoon(g))
                if len(gat) >= 3 and pts_oppervlak(gat) >= MIN_OPPERVLAK:
                    gaten.append(gat)
            doel = groep(obj)
            if obj["soort"] in GEVULD:
                element = {"floorInd": 0, "coordinates": buiten, "arcs": []}
                if gaten:
                    element["holes"] = [{"polygonOutline": g} for g in gaten]
                doel["vlakken"].append(element)
            else:
                for ring in [buiten] + gaten:
                    doel["lijnen"].append({"floorInd": 0, "coordinates": met_sluitpunt(ring),
                                           "arcs": []})
        for lijn in obj["lijnen"]:
            if len(lijn) < 2 or not raakt_gebied(lijn, gebied):
                continue
            punten = schoon(lijn)
            if len(punten) >= 2:
                groep(obj)["lijnen"].append({"floorInd": 0, "coordinates": punten, "arcs": []})
    return groepen, teksten, overgeslagen


# ----------------------------------------------------------------------- Uitvoeren


def plan_dekking(pad):
    """Rechthoek (xmin, ymin, xmax, ymax) van het plangebied, of None."""
    meta, objecten = lees_plan(pad)
    xs, ys = [], []
    for o in objecten:
        if o["soort"] == "Bestemmingsplangebied" or not xs:
            for v in o["vlakken"]:
                xs += [p[0] for p in v["buiten"]]
                ys += [p[1] for p in v["buiten"]]
            if o["soort"] == "Bestemmingsplangebied" and xs:
                break
    if not xs:
        return meta, None
    return meta, (min(xs), min(ys), max(xs), max(ys))


def importeer_plan(k, pad, gebied=None, teksten_tekenen=None, alleen_teksten=False):
    """Tekent het plan in Archicad. k is de module kaart (of iets met dezelfde functies).

    Geeft het aantal getekende elementen terug."""
    if teksten_tekenen is None:
        teksten_tekenen = TEKSTEN_TEKENEN
    meta, objecten = lees_plan(pad)
    print(f"Plan: {meta.get('datasetTitel')} | beheerder: {meta.get('bronbeheerder')} | "
          f"gemaakt: {meta.get('creatiedatum')} | stelsel: EPSG:{meta.get('codeReferentiesysteem')}")
    stelsel = meta.get("codeReferentiesysteem")
    if stelsel and stelsel != "28992":
        raise ValueError("Dit plan staat niet in RD New (28992), import afgebroken.")
    tellers = collections.Counter(o["soort"] for o in objecten)
    print("Objecten in het bestand:", dict(tellers))

    groepen, teksten, overgeslagen = bouw_groepen(objecten, gebied)
    if not groepen and not teksten:
        print("Geen planobjecten gevonden" + (" in dit gebied." if gebied else "."))
        return 0

    vulling = k.zoek_volle_vulling()
    if not vulling:
        vulling = k.STANDAARD_EFFEN_VULLING
        print("Geen effen vulling gevonden, de terugvaller wordt gebruikt.")

    totaal = 0
    for naam, g in ([] if alleen_teksten else groepen.items()):
        laag_index = k.zorg_voor_laag(naam)
        kleur = KLEUREN.get(slug(g["groep"]), KLEUR_ONBEKEND)
        for vlak in g["vlakken"]:
            vlak["layerIndex"] = laag_index
            vlak["contourPenIndex"] = CONTOURPEN
            vlak["foregroundColor"] = {"red": kleur[0] / 255, "green": kleur[1] / 255,
                                       "blue": kleur[2] / 255}
            vlak["fillId"] = vulling
        pen = LIJNPEN_PER_SOORT.get(g["soort"], LIJNPEN)
        for lijn in g["lijnen"]:
            lijn["layerIndex"] = laag_index
            lijn["linePenIndex"] = pen

        v_ok, v_fout, v_zg = k.teken_vlakken(naam, g["vlakken"]) if g["vlakken"] else (0, 0, 0)
        l_ok, l_fout = k.teken_lijnen(naam, g["lijnen"]) if g["lijnen"] else (0, 0)
        tekst = f"{naam}: {v_ok} vlakken ({v_fout} mislukt"
        if v_zg:
            tekst += f", {v_zg} zonder gaten"
        tekst += f"), {l_ok} lijnen ({l_fout} mislukt)"
        print(tekst)
        totaal += v_ok + l_ok

    if teksten and teksten_tekenen:
        laag_index = k.zorg_voor_laag(TEKSTLAAG)
        gelukt = mislukt = 0
        for i in range(0, len(teksten), 100):
            batch = [{"floorIndex": 0, "coordinate": {"x": t["x"], "y": t["y"]},
                      "text": t["tekst"], "height": TEKSTHOOGTE,
                      "layerIndex": laag_index, "pen": TEKSTPEN}
                     for t in teksten[i:i + 100]]
            r = k.tapir("CreateTexts", {"textsData": batch})
            if not r.get("succeeded"):
                print(f"{TEKSTLAAG}: CreateTexts fout:", str(r)[:400])
                mislukt += len(batch)
                continue
            for e in k.pak(r).get("elements", []):
                if "elementId" in e:
                    gelukt += 1
                else:
                    mislukt += 1
                    if mislukt <= 3:
                        print(f"{TEKSTLAAG}: tekst mislukt:", str(e)[:200])
        print(f"{TEKSTLAAG}: {gelukt} teksten ({mislukt} mislukt)")
        totaal += gelukt

    if overgeslagen:
        print("Niet getekend:", dict(overgeslagen))
    print(f"Plan klaar: {totaal} elementen getekend.")
    return totaal


def hoofd(argumenten):
    if not argumenten:
        print(__doc__)
        return 1
    alleen_teksten = "--teksten" in argumenten
    argumenten = [a for a in argumenten if a != "--teksten"]
    if not argumenten:
        print(__doc__)
        return 1
    pad = argumenten[0]
    if not os.path.isfile(pad):
        print(f"Bestand niet gevonden: {pad}")
        print(f"De terminal staat in: {os.getcwd()}")
        gevonden = glob.glob("*.gml") + glob.glob(os.path.join("plannen", "*.gml"))
        if gevonden:
            print("Wel gevonden gml-bestanden:")
            for g in gevonden:
                print("   ", g)
            print("Gebruik een van deze namen, bijvoorbeeld:")
            print(f'    python plan_import.py "{gevonden[0]}"')
        else:
            print("Er staat geen gml-bestand in deze map of in de submap 'plannen'.")
            print("Zet het bestand in deze map en voer uit: python plan_import.py bestandsnaam.gml")
        return 1
    gebied = None
    if len(argumenten) >= 5:
        gebied = tuple(float(a) for a in argumenten[1:5])

    import kaart  # hier pas, zodat het lezen ook zonder Archicad te testen is

    if kaart.GEOREFERENTIE != "rd":
        print("In kaart.py staat GEOREFERENTIE niet op \"rd\". Een bestemmingsplan heeft "
              "RD-coordinaten, dus zet die eerst op \"rd\".")
        return 1

    kaart.MAPNAAM = MAP
    try:
        importeer_plan(kaart, pad, gebied, alleen_teksten=alleen_teksten)
    except ValueError as fout:
        print(fout)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(hoofd(sys.argv[1:]))
