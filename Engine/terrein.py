"""Haalt terrein (PDOK 3D Basisvoorziening, CityJSON) op en maakt het als Meshes aan in Archicad.

Eerst alleen kijken wat er zou gebeuren (Archicad is dan niet nodig, er wordt niets aangemaakt):

    python terrein.py 260278 482339 260427 482533 --droog

Daarna echt aanmaken (Archicad open):

    python terrein.py 260278 482339 260427 482533

Opties:
    --droog              alleen lezen en rapporteren
    --max N              maak hooguit N meshes aan (handig om te testen)
    --typen Road,PlantCover   alleen deze objecttypen (standaard: LandUse, Road, PlantCover, WaterBody)
    --brug               ook wegen die bij een brug horen (standaard overgeslagen)
    --sla-over X         sla objecten over waarvan het BGT-type (bgt_type) X is, bijvoorbeeld "open loods" of
                         "overkapping"; mag meerdere keren (--sla-over "open loods" --sla-over overkapping)
    --controle           (met --droog) meet gaten en toont welke objecten over elkaar liggen (met hun BGT-type): vergelijkt de oppervlakte van de driehoeken met die van de
                         meshes en zoekt onbedekte plekken op een raster van 1 m; toont hun coordinaten
    --geen-naadsluiting  sla de naadsluiting over (standaard krijgen meshes die elkaar raken op de gedeelde
                         rand dezelfde punten en dezelfde hoogte, zodat er geen spleten ontstaan)
    --naadmarge X        punten van verschillende meshes die binnen X meter van elkaar of van elkaars rand
                         liggen, worden als hetzelfde punt behandeld (standaard 0,03)
    --geen-ankers        gebruik de meshes die al in het project staan niet als vaste punten voor de naadsluiting
                         (standaard sluiten nieuwe meshes aan op de bestaande meshes die aan het gebied grenzen)
    --naadcontrole       (geen gebied nodig, Archicad open) toont waar de meshes in het project nu niet op elkaar
                         aansluiten: hoogteverschillen en net-niet-samenvallende punten, met ligging en ID's
    --venster-test       (geen gebied nodig, Archicad open) test of in het actieve venster een Mesh en een Morph
                         kunnen worden aangemaakt; draai het met het 3D-venster actief en met de plattegrond actief
    --naadmax X          grotere hoogteverschillen dan X meter (standaard 0,75) worden niet gelijkgetrokken: dat
                         zijn echte sprongen, zoals een viaduct, een kade of een trap
    --naad X             hoe de hoogte op een naad wordt bepaald: gemiddelde (standaard), weg, laagste, hoogste.
                         'weg' houdt de hoogte van wegen vast (daarna landgebruik, begroeiing, water)
    --skirt X            soort mesh: volume (standaard: een gesloten volumelichaam met een onderkant), zijvlakken
                         (alleen zijvlakken, de skirt) of oppervlak (alleen het bovenvlak)
    --diepte X           hoe ver het volume of de zijvlakken onder het laagste punt van het terrein reiken
                         (standaard 1 m); alle meshes van een import krijgen dezelfde onderkant
    --skirt-bijwerken    (geen gebied nodig, Archicad open) zet de soort en de diepte ook bij de meshes die er al
                         staan, met ModifyMeshes; werkt dat niet, maak dan de terreinlagen leeg en importeer opnieuw
    --bomen              plaats na het terrein een 3D-object (standaard "Boom stedenbouw 02") op de BGT-vegetatiepunten
                         in het gebied; de hoogte komt uit hetzelfde terreinmodel (zie bomen.py)
    --boomobject "Naam"  de naam van het bibliotheekobject voor de bomen (de namen zijn gelokaliseerd)
    --zonder-materiaal   geef de meshes geen oppervlak (standaard krijgt elke mesh bij het aanmaken het oppervlak van
                         zijn type: PDOK_weg, PDOK_landgebruik, PDOK_groen of PDOK_water)
    --meshoppervlak-test (geen gebied nodig, Archicad open) test of jouw Tapir het oppervlak van een mesh kan instellen
                         bij het aanmaken (CreateMeshes) en achteraf (ModifyMeshes), en toont de Tapir-versie
    --favorieten-maken   (geen gebied nodig, Archicad open) maakt van een mesh per terreinlaag een favoriet
                         (PDOK_weg, PDOK_groen, ...), waarvan het oppervlak je eerst zelf moet hebben ingesteld
    --materialen         (geen gebied nodig, Archicad open) past die favorieten toe op de meshes die er al staan, zodat
                         ze hun oppervlak krijgen; bij een nieuwe import gebeurt dit automatisch
    --oppervlakken       (geen gebied nodig, Archicad open) maakt de oppervlakken PDOK_weg, PDOK_landgebruik,
                         PDOK_groen en PDOK_water aan en legt uit hoe je ze per laag instelt; met
                         --oppervlakken-bijwerken schrijf je ze opnieuw weg (bestaande blijven anders ongemoeid)
    --overlap            (geen gebied nodig, Archicad open) zoekt meshes op onze terreinlagen die over elkaar liggen:
                         exacte dubbelen en gedeeltelijke overlap, met Element-ID, laag, oppervlakte en ligging
    --selectie           (geen gebied nodig, Archicad open) toont welk element je hebt geselecteerd: type, laag,
                         Element-ID, ligging, vorm en bij een mesh de instellingen (zoals ridges)
    --controle-archicad  (geen gebied nodig, Archicad open) leest de meshes uit Archicad terug en vergelijkt
                         per mesh de oppervlakte die Archicad dekt met die van de omtrek; zoekt de gaten
    --raster X           rastergrootte in meter (standaard 1 voor --controle, 0,25 voor --controle-archicad)
    --ondergrond         maak ook een extra Mesh over het hele gebied, 5 cm onder de rest, zodat kleine
                         gaten tussen de vlakken niet doorzichtig zijn
    --lijnen             toon de meshlijnen op de plattegrond (standaard uit)
    --z-verschuiving X   tel X meter bij alle hoogtes op (standaard 0: hoogtes in NAP, zoals de gebouwen)
    --forceer            maak ook meshes aan waarvan het Element-ID al op onze lagen staat
    --ontdubbel          verwijder dubbele meshes (zelfde Element-ID) op onze terreinlagen
    --leegmaken          verwijder ALLE meshes op onze vier terreinlagen (vraagt eerst om bevestiging;
                         met --ja sla je die vraag over). Meshes op andere lagen blijven ongemoeid.

Elk BGT-object wordt een Mesh (een object in meerdere delen wordt meerdere meshes), op een laag per
type, met het 3df-id van de PDOK-gegevens als Element-ID.
"""
import math
import re
import sys
import zipfile
import json
from collections import Counter, defaultdict

import drie_d as D

# De kaart-module waarmee we met Archicad praten. kaart.py zet dit bij het aanroepen vanuit het kaartvenster;
# bij gebruik vanaf de opdrachtregel wordt kaart.py gewoon geimporteerd.
KAART = None
LAATSTE = {"gelukt": 0, "mislukt": 0}      # uitkomst van de laatste keer aanmaken


def _kaart():
    if KAART is not None:
        return KAART
    import kaart
    return kaart


COLLECTIE = "basisbestand_gebouwen_terreinen"
MAP = "PDOK Import"
TYPEN = {
    "LandUse": "3D_terrein_landgebruik",
    "Road": "3D_terrein_wegen",
    "PlantCover": "3D_terrein_begroeiing",
    "WaterBody": "3D_terrein_water",
}
OBJECT_TYPEN = list(TYPEN)                       # de typen die uit de data komen
ONDERGROND_LAAG = "3D_terrein_ondergrond"
ONDERGROND_DIEPTE = 0.05                         # m onder de rest
ALLE_LAGEN = dict(TYPEN, Ondergrond=ONDERGROND_LAAG)

# Oppervlakken voor het terrein: type -> (naam in Archicad, kleur 0 tot 1). Pas de kleuren hier aan.
TERREIN_OPPERVLAKKEN = {
    "Road": ("PDOK_weg", (0.33, 0.33, 0.35)),
    "LandUse": ("PDOK_landgebruik", (0.60, 0.58, 0.48)),
    "PlantCover": ("PDOK_groen", (0.33, 0.52, 0.24)),
    "WaterBody": ("PDOK_water", (0.22, 0.42, 0.68)),
}
AFRONDEN = 3
MIN_RINGOPPERVLAK = 1e-3    # m2, kleinere ringen worden weggelaten
GAT_TOL = 0.001             # m: een gatpunt binnen deze afstand van de rand of een ander gat "raakt"
GAT_UITBUIGING = 0.02       # m: zoveel schuiven we een rakend gatpunt naar het midden van zijn gat
VLAK_TOLERANTIE = 0.02      # m, binnen deze spreiding in hoogte is een object vlak (geen binnenpunten)
MAX_PUNTEN_PER_AANROEP = 4000
# Een viaduct of brugdek ligt in plattegrond boven een ander object (de weg of het water eronder). Zo'n dek wordt een dunne plaat
# met een eigen onderkant, in plaats van een massief blok tot de gemeenschappelijke onderkant van het terrein.
DEK_MIN_VERSCHIL = 1.0      # m: zoveel hoger dan het object eronder moet het liggen
DEK_MIN_DEEL = 0.25         # minstens dit deel van het oppervlak ligt boven een ander object
DEK_DIKTE = 0.6             # m: de dikte van een dek (onder zijn laagste punt)
DEK_STAP = 2.0              # m: rastermaat voor het meten van overlap
MAX_HELE_OBJECT = 60000     # een object met meer driehoeken wordt bij een klein gebied afgeknipt tot het gebied
SKIRT_TYPEN = {"oppervlak": "SurfaceOnlyWithoutSkirt", "zijvlakken": "WithSkirt", "volume": "SolidBodyWithSkirt"}
STANDAARD_SKIRT = "volume"
STANDAARD_DIEPTE = 1.0      # m onder het laagste punt van het terrein


# ----------------------------------------------------------------- Lezen


def vertexlijsten(data):
    tf = data.get("transform") or {"scale": [1, 1, 1], "translate": [0, 0, 0]}
    s, t = tf["scale"], tf["translate"]
    v = data.get("vertices", [])
    return ([p[0] * s[0] + t[0] for p in v], [p[1] * s[1] + t[1] for p in v], [p[2] * s[2] + t[2] for p in v])


BLOK = 500.0          # m: zo groot zijn de blokken waarin een groot gebied wordt verdeeld
VOORTGANG = None      # functie (tekst, fractie) die het kaartvenster instelt om de voortgang te tonen
STOP = None           # functie die True geeft als de gebruiker de import wil stoppen


def maak_blokken(gebied, blok=BLOK):
    """Verdeelt een gebied in blokken op een vast raster (veelvouden van blok), begrensd tot het gebied.
    Geeft {(i, j): (x0, y0, x1, y1)}; een vast raster houdt de blokken gelijk bij een volgende import."""
    x0, y0, x1, y1 = gebied
    uit = {}
    for j in range(int(math.floor(y0 / blok)), int(math.floor((y1 - 1e-9) / blok)) + 1):
        for i in range(int(math.floor(x0 / blok)), int(math.floor((x1 - 1e-9) / blok)) + 1):
            uit[(i, j)] = (max(x0, i * blok), max(y0, j * blok), min(x1, (i + 1) * blok), min(y1, (j + 1) * blok))
    return uit


def indexeer_tegel(data, X, Y, gebied, typen, met_bruggen, sla_over, blok=BLOK):
    """{(i, j): [sleutels]}: de objecten van een tegel die het gebied raken, elk toegewezen aan het blok waarin hun
    midden valt (begrensd tot het gebied). Een object hoort zo bij precies een blok, met al zijn driehoeken."""
    x0, y0, x1, y1 = gebied
    uit = defaultdict(list)
    for sleutel, o in data.get("CityObjects", {}).items():
        if o.get("type") not in typen:
            continue
        at = o.get("attributes") or {}
        if at.get("hoortbijbrug") and not met_bruggen:
            continue
        if sla_over and str(at.get("bgt_type") or "").strip().lower() in sla_over:
            continue
        idx = set()
        for g in o.get("geometry") or []:
            for vl in D.oppervlakken_van(g):
                if vl and vl[0]:
                    idx.update(vl[0])
        if not idx:
            continue
        xs = [X[i] for i in idx]
        ys = [Y[i] for i in idx]
        if max(xs) < x0 or min(xs) > x1 or max(ys) < y0 or min(ys) > y1:
            continue
        cx = min(max((min(xs) + max(xs)) / 2, x0), x1 - 1e-6)
        cy = min(max((min(ys) + max(ys)) / 2, y0), y1 - 1e-6)
        uit[(int(math.floor(cx / blok)), int(math.floor(cy / blok)))].append(sleutel)
    return uit


def basis_id(mesh_id):
    """Het object-ID bij een mesh-ID: een extra deel van een object heeft '-k' erachter."""
    kop, _, staart = str(mesh_id).rpartition("-")
    return kop if kop and staart.isdigit() else str(mesh_id)


def mesh_guids(k):
    r = k.tapir("GetElementsByType", {"elementType": "Mesh"})
    return {e["elementId"]["guid"] for e in k.pak(r).get("elements", []) if "elementId" in e}


def nieuw_run(k, gebied):
    """De gegevens die een import in blokken tussen de blokken bewaart, zodat ze niet bij elk blok opnieuw worden
    uitgelezen: de ID's van bestaande meshes, hun GUID's en hun omtrek (als vast punt voor de naadsluiting)."""
    run = {"ids": set(), "objecten": set(), "guids": set(), "ankers": [], "direct": None, "skirt": None}
    try:
        run["guids"] = mesh_guids(k)
        x0, y0, x1, y1 = gebied
        for typ, lijst in terreinmeshes_per_type(k).items():
            for e, it in lijst:
                if it.get("id"):
                    run["ids"].add(it["id"])
                    run["objecten"].update((it["id"], basis_id(it["id"])))
                m = mesh_uit_details(it)
                if not m:
                    continue
                xs = [p["x"] for p in m["polygonCoordinates"]]
                ys = [p["y"] for p in m["polygonCoordinates"]]
                if max(xs) >= x0 - 5 and min(xs) <= x1 + 5 and max(ys) >= y0 - 5 and min(ys) <= y1 + 5:
                    run["ankers"].append((typ, m, (min(xs), min(ys), max(xs), max(ys))))
    except Exception as fout:
        print(f"   (de bestaande meshes konden niet volledig worden gelezen: {fout})")
    return run


def ankers_bij(run, blok, rand=3.0):
    x0, y0, x1, y1 = blok
    return [(t, m) for t, m, bb in run["ankers"]
            if bb[2] >= x0 - rand and bb[0] <= x1 + rand and bb[3] >= y0 - rand and bb[1] <= y1 + rand]


def voeg_dubbelen_samen(objecten):
    """Een object dat op een tegelrand ligt, kan in beide tegels voorkomen. Objecten met hetzelfde type en id
    worden samengevoegd tot een object met de unieke driehoeken van alle tegels (op coordinaten, want de
    hoekpuntnummers verschillen per tegel). Geeft (objecten, aantal samengevoegde)."""
    per_sleutel = defaultdict(list)
    for o in objecten:
        per_sleutel[(o["type"], o["id"])].append(o)
    uit, samengevoegd = [], 0
    for lijst in per_sleutel.values():
        if len(lijst) == 1:
            uit.append(lijst[0])
            continue
        samengevoegd += len(lijst) - 1
        index, X, Y, Z, gezien, tris = {}, [], [], [], set(), []
        for o in lijst:
            xo, yo, zo = o["xyz"]

            def vid(i):
                sleutel = (round(xo[i], 3), round(yo[i], 3), round(zo[i], 3))
                if sleutel not in index:
                    index[sleutel] = len(X)
                    X.append(xo[i])
                    Y.append(yo[i])
                    Z.append(zo[i])
                return index[sleutel]

            for a, b, c in o["driehoeken"]:
                t = (vid(a), vid(b), vid(c))
                handtekening = tuple(sorted(t))
                if handtekening not in gezien:
                    gezien.add(handtekening)
                    tris.append(t)
        nieuw = dict(lijst[0])
        nieuw["driehoeken"] = tris
        nieuw["xyz"] = (X, Y, Z)
        uit.append(nieuw)
    return uit, samengevoegd


def lees_objecten(data, gebied, typen, met_bruggen=False, sla_over=(), alleen=None, xyz=None):
    """Geeft een lijst {'id', 'type', 'attributen', 'driehoeken'} met alleen de driehoeken die het gebied raken.

    Is gebied None, dan krijgt elk object al zijn driehoeken. alleen: een verzameling sleutels; dan worden alleen die
    objecten gelezen. xyz: de al berekende hoekpuntlijsten (scheelt tijd bij meerdere aanroepen voor een tegel)."""
    X, Y, Z = xyz if xyz is not None else vertexlijsten(data)
    uit = []
    alle = data.get("CityObjects", {})
    bron = ((k_, alle[k_]) for k_ in alleen if k_ in alle) if alleen is not None else alle.items()
    for sleutel, o in bron:
        t = o.get("type")
        if t not in typen:
            continue
        at = o.get("attributes") or {}
        if at.get("hoortbijbrug") and not met_bruggen:
            continue
        if sla_over and str(at.get("bgt_type") or "").strip().lower() in sla_over:
            continue
        driehoeken = []          # alle driehoeken van het object
        rakend = []              # alleen de driehoeken die het gebied raken
        for g in o.get("geometry") or []:
            for vl in D.oppervlakken_van(g):
                if not vl or len(vl[0]) < 3:
                    continue
                ring = vl[0]
                for k in range(1, len(ring) - 1):        # een driehoek blijft een driehoek; een veelhoek wordt een waaier
                    a, b, c = ring[0], ring[k], ring[k + 1]
                    driehoeken.append((a, b, c))
                    if gebied:
                        xs = (X[a], X[b], X[c])
                        ys = (Y[a], Y[b], Y[c])
                        if not (max(xs) < gebied[0] or min(xs) > gebied[2] or max(ys) < gebied[1] or min(ys) > gebied[3]):
                            rakend.append((a, b, c))
        if gebied:
            # Een object dat het gebied raakt, wordt als geheel gemaakt, niet afgeknipt: zo staat het bij een volgende import
            # van een aangrenzend gebied al compleet en blijft er geen gat langs de grens. Alleen een heel groot object
            # (meer dan MAX_HELE_OBJECT driehoeken) wordt afgeknipt.
            driehoeken = driehoeken if (rakend and len(driehoeken) <= MAX_HELE_OBJECT) else rakend
        if driehoeken:
            uit.append({"sleutel": sleutel, "id": str(at.get("3df_id") or sleutel), "type": t,
                        "attributen": at, "driehoeken": driehoeken, "xyz": (X, Y, Z)})
    return uit, (X, Y, Z)


# -------------------------------------------------------------- Geometrie


def ring_oppervlak(ring, X, Y):
    s = 0.0
    n = len(ring)
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        s += X[a] * Y[b] - X[b] * Y[a]
    return s / 2


def punt_in_ring(px, py, ring, X, Y):
    binnen = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi, xj, yj = X[ring[i]], Y[ring[i]], X[ring[j]], Y[ring[j]]
        if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
            binnen = not binnen
        j = i
    return binnen


def orienteer(driehoeken, X, Y):
    """Alle driehoeken tegen de klok in (gezien van boven); verticale of nul-driehoeken vallen weg."""
    uit = []
    for a, b, c in driehoeken:
        ar = (X[b] - X[a]) * (Y[c] - Y[a]) - (X[c] - X[a]) * (Y[b] - Y[a])
        if abs(ar) < 1e-6:
            continue
        uit.append((a, b, c) if ar > 0 else (a, c, b))
    return uit


def splits_op_herhaling(ring):
    """Splitst een ring die een hoekpunt twee keer bezoekt (een 8-vorm) in twee eenvoudige ringen,
    zo vaak als nodig. Een ring die zichzelf raakt, weigert Archicad."""
    uit, stapel = [], [ring]
    while stapel:
        r = stapel.pop()
        gezien = {}
        gesplitst = False
        for i, v in enumerate(r):
            if v in gezien:
                j = gezien[v]
                for deel in (r[j:i], r[:j] + r[i:]):
                    if len(deel) >= 3:
                        stapel.append(deel)
                gesplitst = True
                break
            gezien[v] = i
        if not gesplitst:
            uit.append(r)
    return uit


def bouw_ringen(driehoeken, X, Y):
    """Randen van een driehoekennet als gesloten ringen. Geeft (ringen, aantal_knijppunten, onafgemaakt).

    Een knijppunt is een hoekpunt waar het net zichzelf raakt; daar kiest de ring de dichtstbijzijnde
    afslag met de klok mee, zodat elke ring eenvoudig blijft."""
    kanten = set()
    for a, b, c in driehoeken:
        kanten.update(((a, b), (b, c), (c, a)))
    rand = [e for e in kanten if (e[1], e[0]) not in kanten]
    uitgaand = defaultdict(list)
    for u, v in rand:
        uitgaand[u].append(v)
    knijp = sum(1 for lijst in uitgaand.values() if len(lijst) > 1)
    gebruikt = set()
    ringen = []
    onafgemaakt = 0
    for u0, v0 in sorted(rand):
        if (u0, v0) in gebruikt:
            continue
        ring = [u0]
        u, v = u0, v0
        gebruikt.add((u, v))
        stappen = 0
        gesloten = False
        while stappen <= len(rand):
            stappen += 1
            if v == ring[0]:
                gesloten = True
                break
            ring.append(v)
            kandidaten = [w for w in uitgaand[v] if (v, w) not in gebruikt]
            if not kandidaten:
                break
            terug = math.atan2(Y[u] - Y[v], X[u] - X[v])
            beste = None
            beste_hoek = None
            for w in kandidaten:
                hoek = (terug - math.atan2(Y[w] - Y[v], X[w] - X[v])) % (2 * math.pi)
                if hoek < 1e-9:
                    hoek = 2 * math.pi
                if beste_hoek is None or hoek < beste_hoek:
                    beste, beste_hoek = w, hoek
            gebruikt.add((v, beste))
            u, v = v, beste
        if gesloten and len(ring) >= 3:
            ringen.extend(splits_op_herhaling(ring))
        else:
            onafgemaakt += 1
    return ringen, knijp, onafgemaakt


def _punt_op_segment(px, py, ax, ay, bx, by, tol):
    if px < min(ax, bx) - tol or px > max(ax, bx) + tol or py < min(ay, by) - tol or py > max(ay, by) + tol:
        return False
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    if l2 < 1e-18:
        return math.hypot(px - ax, py - ay) <= tol
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy)) <= tol


def raakpunten_gaten(buiten, gaten, tol=GAT_TOL):
    """Punten van gaten die de buitenrand of een ander gat raken. buiten en gaten zijn lijsten van (x, y).
    Geeft een lijst (gatnummer, puntnummer)."""
    uit = []
    for k, g in enumerate(gaten):
        for i, (px, py) in enumerate(g):
            raakt = any(_punt_op_segment(px, py, a[0], a[1], b[0], b[1], tol)
                        for a, b in zip(buiten, buiten[1:] + buiten[:1]))
            if not raakt:
                for k2, g2 in enumerate(gaten):
                    if k2 != k and any(_punt_op_segment(px, py, a[0], a[1], b[0], b[1], tol)
                                       for a, b in zip(g2, g2[1:] + g2[:1])):
                        raakt = True
                        break
            if raakt:
                uit.append((k, i))
    return uit


def los_gatcontact_op(mesh):
    """Schuift gatpunten die de buitenrand of een ander gat raken 2 cm naar het midden van hun gat.
    Geeft (aantal verschoven, aantal dat nog raakt)."""
    if not mesh.get("holes"):
        return 0, 0
    buiten = [(p["x"], p["y"]) for p in mesh["polygonCoordinates"]]
    gaten = [[(p["x"], p["y"]) for p in h["polygonCoordinates"]] for h in mesh["holes"]]
    verschoven = 0
    for k, i in raakpunten_gaten(buiten, gaten):
        punten = mesh["holes"][k]["polygonCoordinates"]
        cx = sum(p["x"] for p in punten) / len(punten)
        cy = sum(p["y"] for p in punten) / len(punten)
        p = punten[i]
        afstand = math.hypot(cx - p["x"], cy - p["y"])
        if afstand > 4 * GAT_UITBUIGING:
            p["x"] = round(p["x"] + (cx - p["x"]) / afstand * GAT_UITBUIGING, AFRONDEN)
            p["y"] = round(p["y"] + (cy - p["y"]) / afstand * GAT_UITBUIGING, AFRONDEN)
            verschoven += 1
    gaten = [[(p["x"], p["y"]) for p in h["polygonCoordinates"]] for h in mesh["holes"]]
    return verschoven, len(raakpunten_gaten(buiten, gaten))


def bouw_meshes(obj, X, Y, Z, z_verschuiving=0.0):
    """Zet een object om naar een lijst meshes (elk een woordenboek voor CreateMeshes) en een statistiek."""
    tris = orienteer(obj["driehoeken"], X, Y)
    stat = {"driehoeken": len(tris), "ringen": 0, "gaten": 0, "binnenpunten": 0, "knijp": 0,
            "onafgemaakt": 0, "weggelaten": 0, "vlak": 0, "gat_verschoven": 0, "gat_raakt": 0}
    if not tris:
        return [], stat
    ringen, knijp, onafgemaakt = bouw_ringen(tris, X, Y)
    stat["knijp"], stat["onafgemaakt"] = knijp, onafgemaakt
    buiten, gaten = [], []
    for r in ringen:
        a = ring_oppervlak(r, X, Y)
        if abs(a) < MIN_RINGOPPERVLAK:
            stat["weggelaten"] += 1
        elif a > 0:
            buiten.append((r, a))
        else:
            gaten.append((r, -a))
    stat["ringen"] = len(buiten)
    stat["gaten"] = len(gaten)
    if not buiten:
        return [], stat

    # Gaten bij de kleinste buitenring die ze omsluit
    gaten_van = defaultdict(list)
    buiten_sets = [set(b) for b, _ in buiten]
    for g, ga in gaten:
        vertex = next((i for i in g if all(i not in bs for bs in buiten_sets)), g[0])
        px, py = X[vertex], Y[vertex]
        kandidaten = [k for k, (b, ba) in enumerate(buiten) if ba > ga and punt_in_ring(px, py, b, X, Y)]
        if kandidaten:
            gaten_van[min(kandidaten, key=lambda k: buiten[k][1])].append(g)

    def punt(i):
        return {"x": round(X[i], AFRONDEN), "y": round(Y[i], AFRONDEN),
                "z": round(Z[i] + z_verschuiving, AFRONDEN)}

    meshes = []
    for k, (b, _) in enumerate(buiten):
        if len(buiten) == 1:
            leden = tris
        else:
            leden = []
            for a, bb, c in tris:
                cx, cy = (X[a] + X[bb] + X[c]) / 3, (Y[a] + Y[bb] + Y[c]) / 3
                if punt_in_ring(cx, cy, b, X, Y) and not any(punt_in_ring(cx, cy, g, X, Y) for g in gaten_van[k]):
                    leden.append((a, bb, c))
        ring_vertices = set(b)
        for g in gaten_van[k]:
            ring_vertices.update(g)
        binnen = {i for t in leden for i in t} - ring_vertices
        zs = [Z[i] for i in binnen] + [Z[i] for i in ring_vertices]
        vlak = bool(zs) and (max(zs) - min(zs)) < VLAK_TOLERANTIE
        stat["vlak"] += 1 if vlak else 0
        sublines = [] if vlak else [{"coordinates": [punt(i)]} for i in sorted(binnen)]
        stat["binnenpunten"] += len(sublines)
        mesh = {"polygonCoordinates": [punt(i) for i in b]}
        if gaten_van[k]:
            mesh["holes"] = [{"polygonCoordinates": [punt(i) for i in g]} for g in gaten_van[k]]
        if sublines:
            mesh["sublines"] = sublines
        mesh["id"] = obj["id"] if k == 0 else f"{obj['id']}-{k}"
        verschoven, blijft = los_gatcontact_op(mesh)
        stat["gat_verschoven"] += verschoven
        stat["gat_raakt"] += blijft
        meshes.append(mesh)
    return meshes, stat


def lees_voetafdrukken(data, gebied, X, Y):
    """Voetafdrukken (ringen van (x, y)) van de gebouwen die het gebied raken, uit het LoD 0-vlak."""
    uit = []
    for o in data.get("CityObjects", {}).values():
        if o.get("type") != "Building" or o.get("parents"):
            continue
        for g in o.get("geometry") or []:
            if D.lod_tekst(g.get("lod")) != "0.0":
                continue
            for vl in D.oppervlakken_van(g):
                if not vl or len(vl[0]) < 3:
                    continue
                ring = [(X[i], Y[i]) for i in vl[0]]
                xs, ys = [p[0] for p in ring], [p[1] for p in ring]
                if max(xs) < gebied[0] or min(xs) > gebied[2] or max(ys) < gebied[1] or min(ys) > gebied[3]:
                    continue
                uit.append(ring)
    return uit


# -------------------------------------------------------------- Naadsluiting

NAAD_TOL = 0.003          # m: punten binnen deze afstand van een rand horen erbij
NAAD_MARGE_STANDAARD = 0.03   # m: standaardmarge waarbinnen punten en randen van buurmeshes als een geldt
NAAD_CEL = 5.0            # m: celgrootte van de ruimtelijke index
NAAD_PRIORITEIT = ["Road", "LandUse", "PlantCover", "WaterBody"]
NAAD_BELEID = ("gemiddelde", "weg", "laagste", "hoogste")
NAAD_MAX_VERSCHIL = 0.75  # m: een groter hoogteverschil is een echte sprong en wordt niet gelijkgetrokken


MIN_RAND = 0.005          # m: kortere randen in een omtrek worden door Archicad vaak geweigerd


def ring_problemen(punten):
    """Problemen in een omtrek: heel korte randen, en randen die elkaar snijden of raken."""
    n = len(punten)
    pts = [(p["x"], p["y"]) for p in punten]
    problemen = []
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        if math.hypot(a[0] - b[0], a[1] - b[1]) < MIN_RAND:
            problemen.append(("korte rand", a))

    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    def afstand(p, a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        l2 = dx * dx + dy * dy
        if l2 < 1e-18:
            return math.hypot(p[0] - a[0], p[1] - a[1])
        t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2))
        return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))

    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            c, d = pts[j], pts[(j + 1) % n]
            if (orient(a, b, c) * orient(a, b, d) < 0 and orient(c, d, a) * orient(c, d, b) < 0):
                problemen.append(("snijdt zichzelf", a))
            elif min(afstand(c, a, b), afstand(d, a, b), afstand(a, c, d), afstand(b, c, d)) < 1e-3:
                problemen.append(("raakt zichzelf", a))
    return problemen


def mesh_problemen(m):
    uit = ring_problemen(m["polygonCoordinates"])
    for h in m.get("holes", []):
        uit += ring_problemen(h["polygonCoordinates"])
    return uit


def naad_nabij(ringen, index, ondergrens, bovengrens=0.05):
    """Punten van verschillende meshes die net niet samenvallen (tussen ondergrens en bovengrens), of net niet
    op een rand van een andere mesh liggen. Geeft (aantal punt-punt, aantal punt-rand, voorbeelden)."""
    pp, pr, voorbeelden = set(), set(), []
    kant_index = defaultdict(list)
    for rn, (mi, t, r) in enumerate(ringen):
        n = len(r)
        for k in range(n):
            a, b = r[k], r[(k + 1) % n]
            for cx in range(int(math.floor((min(a["x"], b["x"]) - bovengrens) / NAAD_CEL)),
                            int(math.floor((max(a["x"], b["x"]) + bovengrens) / NAAD_CEL)) + 1):
                for cy in range(int(math.floor((min(a["y"], b["y"]) - bovengrens) / NAAD_CEL)),
                                int(math.floor((max(a["y"], b["y"]) + bovengrens) / NAAD_CEL)) + 1):
                    kant_index[(cx, cy)].append((mi, a, b))
    for rn, (mi, t, r) in enumerate(ringen):
        for p in r:
            cel = (int(math.floor(p["x"] / NAAD_CEL)), int(math.floor(p["y"] / NAAD_CEL)))
            for rn2, q in index.get(cel, ()):
                mi2 = ringen[rn2][0]
                if mi2 == mi:
                    continue
                d = math.hypot(p["x"] - q["x"], p["y"] - q["y"])
                if ondergrens < d <= bovengrens:
                    sleutel = (min(id(p), id(q)), max(id(p), id(q)))
                    if sleutel not in pp:
                        pp.add(sleutel)
                        voorbeelden.append((d, p["x"], p["y"], "punt-punt"))
            for mi2, a, b in kant_index.get(cel, ()):
                if mi2 == mi:
                    continue
                dx, dy = b["x"] - a["x"], b["y"] - a["y"]
                l2 = dx * dx + dy * dy
                if l2 < 1e-12:
                    continue
                t_ = ((p["x"] - a["x"]) * dx + (p["y"] - a["y"]) * dy) / l2
                if t_ <= 0 or t_ >= 1:
                    continue
                d = abs((p["x"] - a["x"]) * dy - (p["y"] - a["y"]) * dx) / math.sqrt(l2)
                afstand_eind = min(math.hypot(p["x"] - a["x"], p["y"] - a["y"]),
                                   math.hypot(p["x"] - b["x"], p["y"] - b["y"]))
                if ondergrens < d <= bovengrens and afstand_eind > bovengrens:
                    sleutel = (id(p), id(a), id(b))
                    if sleutel not in pr:
                        pr.add(sleutel)
                        voorbeelden.append((d, p["x"], p["y"], "punt-rand"))
    return len(pp), len(pr), sorted(voorbeelden, reverse=True)


def naadsluiting(meshes, beleid="gemiddelde", marge=NAAD_MARGE_STANDAARD, max_verschil=NAAD_MAX_VERSCHIL,
                 ankers=None):
    """Laat meshes die elkaar raken op hun gedeelde rand dezelfde punten en dezelfde hoogte hebben.

    meshes: lijst (type, mesh); de meshes worden ter plekke gewijzigd. Geeft een statistiek.
    ankers: lijst (type, mesh) van meshes die al in het project staan. Die worden niet gewijzigd: de nieuwe
            meshes sluiten er op aan (hun hoogte en hoekpunten gelden als vast).

    0. Punten van verschillende meshes die binnen 'marge' van elkaar liggen, vallen samen.
    1. Waar het hoekpunt van de ene mesh binnen 'marge' van de rand van een andere mesh ligt (een T-kruising),
       wordt dat punt ook in de rand van die andere mesh ingevoegd, met de hoogte die daar langs de rand hoort.
       Ligt een nieuw hoekpunt bij de rand van een anker, dan schuift het op die rand en neemt zijn hoogte over.
    2. Alle punten op dezelfde plaats krijgen een gezamenlijke hoogte (volgens het beleid); een anker wint altijd.
    3. Een mesh waarvan de omtrek door deze stappen meer problemen krijgt (heel korte randen, zelfdoorsnijding)
       dan hij oorspronkelijk had, wordt teruggezet naar zijn oorspronkelijke omtrek."""
    import copy

    for t, m in meshes:
        if "_oorspronkelijk" not in m:
            m["_oorspronkelijk"] = {"polygonCoordinates": copy.deepcopy(m["polygonCoordinates"]),
                                    "holes": copy.deepcopy(m.get("holes", []))}
    ringen = []                                   # (mesh_index, type, lijst met punten)
    anker_rn = set()                              # ringnummers van de ankers
    ankers = list(ankers or [])
    for j, (t, m) in enumerate(ankers):           # eerst de ankers, zodat nieuwe punten daar naartoe schuiven
        mi = len(meshes) + j
        anker_rn.add(len(ringen))
        ringen.append((mi, t, m["polygonCoordinates"]))
        for h in m.get("holes", []):
            anker_rn.add(len(ringen))
            ringen.append((mi, t, h["polygonCoordinates"]))
    anker_mi = {len(meshes) + j for j in range(len(ankers))}
    for mi, (t, m) in enumerate(meshes):
        ringen.append((mi, t, m["polygonCoordinates"]))
        for h in m.get("holes", []):
            ringen.append((mi, t, h["polygonCoordinates"]))

    def maak_index():
        idx = defaultdict(list)
        for rn, (mi, t, r) in enumerate(ringen):
            for p in r:
                idx[(int(math.floor(p["x"] / NAAD_CEL)), int(math.floor(p["y"] / NAAD_CEL)))].append((rn, p))
        return idx

    index = maak_index()
    nabij_pp, nabij_pr, nabij_voorbeelden = naad_nabij(ringen, index, NAAD_TOL)

    # 0. punten samenvoegen die dicht bij elkaar liggen (ankers blijven staan, de rest schuift naar het eerste punt)
    samengevoegd = 0
    if marge > NAAD_TOL:
        gezien = defaultdict(list)
        for rn, (mi, t, r) in enumerate(ringen):
            for p in r:
                cel = (int(math.floor(p["x"] / NAAD_CEL)), int(math.floor(p["y"] / NAAD_CEL)))
                doel = None
                if rn not in anker_rn:
                    for dx in (-1, 0, 1):
                        for dy in (-1, 0, 1):
                            for mi2, q in gezien.get((cel[0] + dx, cel[1] + dy), ()):
                                if mi2 != mi and math.hypot(p["x"] - q["x"], p["y"] - q["y"]) <= marge:
                                    doel = q
                                    break
                            if doel:
                                break
                        if doel:
                            break
                if doel is not None and (p["x"], p["y"]) != (doel["x"], doel["y"]):
                    p["x"], p["y"] = doel["x"], doel["y"]
                    samengevoegd += 1
                gezien[cel].append((mi, p))
        index = maak_index()

    # 1a. T-kruisingen: hoekpunten van buurmeshes (ook ankers) als tussenpunt in de randen van nieuwe meshes
    ingevoegd = set()                             # id() van ingevoegde punten
    aantal_ingevoegd = 0
    for rn, (mi, t, r) in enumerate(ringen):
        if rn in anker_rn:
            continue
        nieuw = []
        n = len(r)
        for k in range(n):
            a, b = r[k], r[(k + 1) % n]
            nieuw.append(a)
            dx, dy = b["x"] - a["x"], b["y"] - a["y"]
            lengte2 = dx * dx + dy * dy
            if lengte2 < 1e-12:
                continue
            lengte = math.sqrt(lengte2)
            gevonden = {}
            for cx in range(int(math.floor((min(a["x"], b["x"]) - marge) / NAAD_CEL)),
                            int(math.floor((max(a["x"], b["x"]) + marge) / NAAD_CEL)) + 1):
                for cy in range(int(math.floor((min(a["y"], b["y"]) - marge) / NAAD_CEL)),
                                int(math.floor((max(a["y"], b["y"]) + marge) / NAAD_CEL)) + 1):
                    for rn2, p in index.get((cx, cy), ()):
                        if rn2 == rn:
                            continue
                        t_ = ((p["x"] - a["x"]) * dx + (p["y"] - a["y"]) * dy) / lengte2
                        if t_ * lengte <= marge or (1 - t_) * lengte <= marge:
                            continue              # bij een eindpunt: al hetzelfde punt
                        afstand = abs((p["x"] - a["x"]) * dy - (p["y"] - a["y"]) * dx) / lengte
                        if afstand <= marge:
                            gevonden.setdefault((round(p["x"], 3), round(p["y"], 3)), (t_, p))
            for t_, p in sorted(gevonden.values(), key=lambda v: v[0]):
                nieuw_punt = {"x": p["x"], "y": p["y"], "z": a["z"] + t_ * (b["z"] - a["z"])}
                ingevoegd.add(id(nieuw_punt))
                nieuw.append(nieuw_punt)
                aantal_ingevoegd += 1
        r[:] = nieuw

    # 1b. nieuwe hoekpunten die bij de rand van een anker liggen: op die rand leggen, met de hoogte van die rand
    op_anker_rand = 0
    if anker_rn:
        kant_index = defaultdict(list)
        for rn in anker_rn:
            r = ringen[rn][2]
            n = len(r)
            for k in range(n):
                a, b = r[k], r[(k + 1) % n]
                for cx in range(int(math.floor((min(a["x"], b["x"]) - marge) / NAAD_CEL)),
                                int(math.floor((max(a["x"], b["x"]) + marge) / NAAD_CEL)) + 1):
                    for cy in range(int(math.floor((min(a["y"], b["y"]) - marge) / NAAD_CEL)),
                                    int(math.floor((max(a["y"], b["y"]) + marge) / NAAD_CEL)) + 1):
                        kant_index[(cx, cy)].append((a, b))
        for rn, (mi, t, r) in enumerate(ringen):
            if rn in anker_rn:
                continue
            for p in r:
                cel = (int(math.floor(p["x"] / NAAD_CEL)), int(math.floor(p["y"] / NAAD_CEL)))
                beste = None
                for a, b in kant_index.get(cel, ()):
                    dx, dy = b["x"] - a["x"], b["y"] - a["y"]
                    lengte2 = dx * dx + dy * dy
                    if lengte2 < 1e-12:
                        continue
                    lengte = math.sqrt(lengte2)
                    t_ = ((p["x"] - a["x"]) * dx + (p["y"] - a["y"]) * dy) / lengte2
                    if t_ * lengte <= marge or (1 - t_) * lengte <= marge:
                        continue                  # bij een hoekpunt van het anker: dat regelt stap 0 en de groepen
                    afstand = abs((p["x"] - a["x"]) * dy - (p["y"] - a["y"]) * dx) / lengte
                    if 1e-6 < afstand <= marge and (beste is None or afstand < beste[0]):
                        beste = (afstand, a, b, t_)
                if beste:
                    _, a, b, t_ = beste
                    p["x"] = round(a["x"] + t_ * (b["x"] - a["x"]), 3)
                    p["y"] = round(a["y"] + t_ * (b["y"] - a["y"]), 3)
                    p["z"] = round(a["z"] + t_ * (b["z"] - a["z"]), AFRONDEN)
                    op_anker_rand += 1

    # groepen punten op dezelfde plaats
    groepen = defaultdict(list)
    for rn, (mi, t, r) in enumerate(ringen):
        for p in r:
            groepen[(round(p["x"], 3), round(p["y"], 3))].append((t, p, mi))
    stat = {"ringpunten": sum(len(r) for _, _, r in ringen), "ingevoegd": aantal_ingevoegd,
            "naadpunten": 0, "voor": [], "echt": 0, "interpolatie": 0, "samengevoegd": samengevoegd,
            "nabij_pp": nabij_pp, "nabij_pr": nabij_pr, "nabij_voorbeelden": nabij_voorbeelden,
            "teruggezet": [], "groot": 0, "ankers": len(ankers), "op_anker_rand": op_anker_rand,
            "anker_plaatsen": 0, "anker_verschil": 0}
    for (x, y), lid in groepen.items():
        if len({mi for _, _, mi in lid}) < 2:
            continue
        zs = [p["z"] for _, p, _ in lid]
        spreiding = max(zs) - min(zs)
        stat["naadpunten"] += 1
        met_anker = any(mi in anker_mi for _, _, mi in lid)
        if met_anker:
            stat["anker_plaatsen"] += 1
        if spreiding > 0.01:
            echt = sum(1 for _, p, _ in lid if id(p) not in ingevoegd) >= 2 and \
                len({round(p["z"], 3) for _, p, _ in lid if id(p) not in ingevoegd}) > 1
            stat["echt" if echt else "interpolatie"] += 1
            stat["voor"].append((spreiding, x, y, sorted({(t, round(p["z"], 3)) for t, p, _ in lid})))
            if met_anker:
                stat["anker_verschil"] += 1
        if spreiding > max_verschil:
            stat["groot"] += 1          # een echte sprong (viaduct, kade, trap): de hoogtes blijven zoals ze zijn
            continue
        if met_anker:                     # een bestaande mesh wordt niet gewijzigd: de nieuwe sluiten er op aan
            doel = [p["z"] for _, p, mi in lid if mi in anker_mi]
            z = round(sum(doel) / len(doel), AFRONDEN)
            for _, p, mi in lid:
                if mi not in anker_mi:
                    p["z"] = z
            continue
        if beleid == "laagste":
            z = min(zs)
        elif beleid == "hoogste":
            z = max(zs)
        elif beleid == "weg":
            gekozen = None
            for voorkeur in NAAD_PRIORITEIT:
                waarden = [p["z"] for t, p, _ in lid if t == voorkeur]
                if waarden:
                    gekozen = sum(waarden) / len(waarden)
                    break
            z = gekozen if gekozen is not None else sum(zs) / len(zs)
        else:
            z = sum(zs) / len(zs)
        z = round(z, AFRONDEN)
        for _, p, _ in lid:
            p["z"] = z
    stat["voor"].sort(reverse=True)

    # 3. meshes met een omtrek die slechter is geworden, terugzetten
    for t, m in meshes:
        nieuw_p = mesh_problemen(m)
        if not nieuw_p:
            continue
        oud = m["_oorspronkelijk"]
        oud_p = ring_problemen(oud["polygonCoordinates"])
        for h in oud["holes"]:
            oud_p += ring_problemen(h["polygonCoordinates"])
        if len(nieuw_p) > len(oud_p):
            m["polygonCoordinates"] = copy.deepcopy(oud["polygonCoordinates"])
            if oud["holes"]:
                m["holes"] = copy.deepcopy(oud["holes"])
            stat["teruggezet"].append((m["id"], t, [f"{n_} bij ({q[0]:.2f}, {q[1]:.2f})" for n_, q in nieuw_p[:2]]))
    return stat


def mesh_uit_details(it):
    """Een mesh (met punten {x, y, z}) uit de details van een mesh in Archicad; None als die niet te lezen is."""
    det = it.get("details") or {}
    punten = det.get("polygonCoordinates") or []

    def ring(pts):
        r = [{"x": p["x"], "y": p["y"], "z": p.get("z", 0.0)} for p in pts]
        if len(r) > 1 and (r[0]["x"], r[0]["y"]) == (r[-1]["x"], r[-1]["y"]):
            r.pop()                       # Archicad geeft de omtrek gesloten terug
        return r
    buiten = ring(punten)
    if len(buiten) < 3:
        return None
    gaten = []
    for h in det.get("holes") or []:
        pts = h.get("polygonCoordinates") if isinstance(h, dict) else h
        g = ring(pts or [])
        if len(g) >= 3:
            gaten.append({"polygonCoordinates": g})
    return {"polygonCoordinates": buiten, "holes": gaten, "id": it.get("id")}


def lees_bestaande_ankers(k, gebied, rand=2.0, uitsluiten=()):
    """De meshes op de terreinlagen die in of vlak bij het gebied liggen, als ankers voor de naadsluiting."""
    per_type = terreinmeshes_per_type(k)
    x0, y0, x1, y1 = gebied
    uit = []
    for typ, lijst in per_type.items():
        for e, it in lijst:
            if it.get("id") in uitsluiten:
                continue
            m = mesh_uit_details(it)
            if not m:
                continue
            xs = [p["x"] for p in m["polygonCoordinates"]]
            ys = [p["y"] for p in m["polygonCoordinates"]]
            if max(xs) < x0 - rand or min(xs) > x1 + rand or max(ys) < y0 - rand or min(ys) > y1 + rand:
                continue
            uit.append((typ, m))
    return uit


def naadcontrole_project(marge=NAAD_MARGE_STANDAARD):
    """Toont waar de meshes in het project nu niet op elkaar aansluiten. Leest alleen."""
    k = _kaart()
    per_type = terreinmeshes_per_type(k)
    meshes = []
    for typ, lijst in per_type.items():
        for e, it in lijst:
            m = mesh_uit_details(it)
            if m:
                meshes.append((typ, m))
    if not meshes:
        print("Er zijn geen terreinmeshes in dit project.")
        return 1
    print(f"{len(meshes)} meshes op de terreinlagen worden vergeleken (marge {marge * 100:g} cm)...")
    stat = naadsluiting(meshes, "gemiddelde", marge, NAAD_MAX_VERSCHIL)      # werkt op kopieen; er wordt niets verstuurd
    voor = stat["voor"]
    print(f"\n{stat['naadpunten']} plaatsen waar meshes elkaar raken.")
    print("Hoogteverschil tussen buurmeshes op die plaatsen (zoals het nu in Archicad staat): "
          f"{sum(1 for v in voor if v[0] > 0.01)} > 1 cm, {sum(1 for v in voor if v[0] > 0.05)} > 5 cm, "
          f"{sum(1 for v in voor if v[0] > 0.20)} > 20 cm, {sum(1 for v in voor if v[0] > 0.50)} > 50 cm, "
          f"{sum(1 for v in voor if v[0] > NAAD_MAX_VERSCHIL)} > {NAAD_MAX_VERSCHIL:g} m (echte sprongen)")
    print(f"Punten die net niet samenvallen (3 mm tot 5 cm): {stat['nabij_pp']} punt-punt, {stat['nabij_pr']} punt-rand")

    # samenvatten per plek: punten binnen 2 m van elkaar vormen een plek
    plekken = []
    for spreiding, x, y, leden in sorted(voor, reverse=True):
        for pl in plekken:
            if math.hypot(pl["x"] - x, pl["y"] - y) <= 2.0:
                pl["n"] += 1
                pl["typen"].update(t for t, _ in leden)
                break
        else:
            plekken.append({"x": x, "y": y, "max": spreiding, "n": 1, "leden": leden,
                            "typen": Counter(t for t, _ in leden)})
    oplosbaar = [pl for pl in plekken if pl["max"] <= NAAD_MAX_VERSCHIL]
    sprongen = [pl for pl in plekken if pl["max"] > NAAD_MAX_VERSCHIL]
    print(f"\nDat zijn {len(plekken)} plekken: {len(oplosbaar)} met een verschil tot {NAAD_MAX_VERSCHIL:g} m "
          f"(dat strijkt de naadsluiting glad bij een nieuwe import) en {len(sprongen)} echte sprongen.")

    def toon(lijst, kop):
        if not lijst:
            return
        print(f"\n{kop}")
        for pl in lijst[:10]:
            print(f"   {pl['max']:5.2f} m bij ({pl['x']:.1f}, {pl['y']:.1f}), {pl['n']} punten: "
                  + ", ".join(f"{t} {z:.2f}" for t, z in pl["leden"]))
    toon(oplosbaar, "Verschillen die een nieuwe import oplost (de grootste tien):")
    toon(sprongen, "Echte sprongen (de grootste tien; bijvoorbeeld een brug, kade of viaduct):")
    if sprongen:
        print("\nVoor een echte sprong: kijk met 'python terrein.py <gebied rond die plek> --droog --controle' welke "
              "objecten dat zijn (type, BGT-type en functie staan in het rapport).")
    if not voor:
        print("   Geen hoogteverschillen gevonden.")
    return 0


def test_venster():
    """Probeert in het actieve venster een Mesh en een Morph aan te maken, en ruimt ze op."""
    k = _kaart()
    venster = actief_venster(k)
    print("Actief venster:", venster or "onbekend")
    x0, y0, z0 = 1000.0, 1000.0, 50.0
    vierkant = [{"x": x0, "y": y0, "z": z0}, {"x": x0 + 4, "y": y0, "z": z0},
                {"x": x0 + 4, "y": y0 + 4, "z": z0}, {"x": x0, "y": y0 + 4, "z": z0}]
    gemaakt = []
    uit = {}
    try:
        for naam, commando, sleutel, item in (
                ("Mesh", "CreateMeshes", "meshesData", {"polygonCoordinates": vierkant, "level": 0, "floorIndex": 0}),
                ("Morph", "CreateMorphs", "morphsData", {"basePoint": {"x": x0, "y": y0 + 10, "z": z0},
                                                         "size": {"x": 2.0, "y": 2.0, "z": 2.0}})):
            r = k.tapir(commando, {sleutel: [item]})
            e = (k.pak(r).get("elements") or [{}])[0] if r.get("succeeded") else {}
            if "elementId" in e:
                gemaakt.append(e)
                uit[naam] = True
                print(f"   {naam}: aangemaakt")
            else:
                uit[naam] = False
                print(f"   {naam}: mislukt: {str(e.get('error', r.get('error', r)))[:170]}")
    finally:
        if gemaakt:
            k.tapir("DeleteElements", {"elements": gemaakt})
    print()
    if uit.get("Mesh") and uit.get("Morph"):
        print("In dit venster kunnen zowel meshes als morphs worden aangemaakt; wisselen is dan niet nodig.")
    elif uit.get("Morph") and not uit.get("Mesh"):
        print("In dit venster kunnen morphs worden aangemaakt, maar geen meshes: voor meshes is de plattegrond nodig.")
    else:
        print("Zie de meldingen hierboven.")
    return 0


def toon_naadstatistiek(stat, beleid):
    print(f"\nNaadsluiting (beleid '{beleid}'): {stat['naadpunten']} plaatsen waar meshes elkaar raken, "
          f"{stat['ingevoegd']} tussenpunten ingevoegd op randen (T-kruisingen).")
    voor = stat["voor"]
    grootte = lambda d: sum(1 for v in voor if v[0] > d)
    print(f"   hoogteverschil tussen de meshes op die plaatsen, voor de correctie: "
          f"{len(voor)} plaatsen > 1 cm, {grootte(0.05)} > 5 cm, {grootte(0.20)} > 20 cm, "
          f"{grootte(0.50)} > 50 cm")
    print(f"   daarvan door een echt verschil op gedeelde hoekpunten: {stat['echt']}; "
          f"door een extra punt op de rand van de buur (interpolatie): {stat['interpolatie']}")
    for spreiding, x, y, lid in voor[:5]:
        print(f"      {spreiding:5.2f} m verschil bij ({x:.2f}, {y:.2f}): " +
              ", ".join(f"{t} {z:.2f}" for t, z in lid))
    if stat.get("ankers"):
        print(f"   {stat['ankers']} bestaande meshes in het project grenzen aan dit gebied en dienen als vast punt: "
              f"{stat['anker_plaatsen']} plaatsen sluiten erop aan"
              + (f", waarvan {stat['anker_verschil']} met een hoogteverschil dat is weggewerkt" if stat["anker_verschil"] else "")
              + (f"; {stat['op_anker_rand']} nieuwe hoekpunten zijn op de rand van een bestaande mesh gelegd"
                 if stat["op_anker_rand"] else ""))
    if stat["groot"]:
        print(f"   {stat['groot']} plaatsen met een verschil groter dan het maximum (echte sprongen, zoals een viaduct "
              f"of kade) zijn niet gelijkgetrokken")
    if stat["samengevoegd"]:
        print(f"   {stat['samengevoegd']} punten van buurmeshes zijn samengevoegd (binnen de marge).")
    print(f"   punten die net niet samenvallen (3 mm tot 5 cm): {stat['nabij_pp']} punt-punt, "
          f"{stat['nabij_pr']} punt-rand; deze blijven als naadje bestaan tenzij je --naadmarge verhoogt")
    for d, x, y, soort in stat["nabij_voorbeelden"][:5]:
        print(f"      {d * 1000:5.1f} mm {soort} bij ({x:.2f}, {y:.2f})")
    if stat["teruggezet"]:
        print(f"   {len(stat['teruggezet'])} meshes zijn teruggezet naar hun oorspronkelijke omtrek, omdat de "
              f"naadsluiting ze ongeldig zou maken:")
        for mid, t, redenen in stat["teruggezet"][:5]:
            print(f"      {t} {mid}: {'; '.join(redenen)}")
    if voor:
        print("   na de correctie hebben alle punten op een naad dezelfde hoogte.")


# ----------------------------------------------------------------- Controle


def in_driehoek(px, py, ax, ay, bx, by, cx, cy):
    d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(d) < 1e-12:
        return False
    l1 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / d
    l2 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / d
    e = -1e-9
    return l1 >= e and l2 >= e and 1 - l1 - l2 >= e


def punt_in_polygoon(px, py, ring):
    binnen = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
            binnen = not binnen
        j = i
    return binnen


def vorm_oppervlak(ring):
    return sum(ring[i][0] * ring[(i + 1) % len(ring)][1] - ring[(i + 1) % len(ring)][0] * ring[i][1]
               for i in range(len(ring))) / 2


class Raster:
    """Een raster over het gebied, met een teller per cel."""

    def __init__(self, gebied, stap):
        self.x0, self.y0, self.stap = gebied[0], gebied[1], stap
        self.nx = int(math.ceil((gebied[2] - gebied[0]) / stap))
        self.ny = int(math.ceil((gebied[3] - gebied[1]) / stap))
        self.tel = [0] * (self.nx * self.ny)

    def cellen(self, minx, miny, maxx, maxy):
        i0 = max(0, int(math.floor((minx - self.x0) / self.stap)))
        i1 = min(self.nx - 1, int(math.floor((maxx - self.x0) / self.stap)))
        j0 = max(0, int(math.floor((miny - self.y0) / self.stap)))
        j1 = min(self.ny - 1, int(math.floor((maxy - self.y0) / self.stap)))
        for j in range(j0, j1 + 1):
            cy = self.y0 + (j + 0.5) * self.stap
            for i in range(i0, i1 + 1):
                yield i, j, self.x0 + (i + 0.5) * self.stap, cy

    def vul_driehoek(self, a, b, c):
        for i, j, cx, cy in self.cellen(min(a[0], b[0], c[0]), min(a[1], b[1], c[1]),
                                        max(a[0], b[0], c[0]), max(a[1], b[1], c[1])):
            if in_driehoek(cx, cy, a[0], a[1], b[0], b[1], c[0], c[1]):
                self.tel[j * self.nx + i] += 1

    def vul_vorm(self, buiten, gaten=()):
        xs, ys = [p[0] for p in buiten], [p[1] for p in buiten]
        for i, j, cx, cy in self.cellen(min(xs), min(ys), max(xs), max(ys)):
            if punt_in_polygoon(cx, cy, buiten) and not any(punt_in_polygoon(cx, cy, g) for g in gaten):
                self.tel[j * self.nx + i] += 1


def clusters(raster, masker):
    """Aaneengesloten groepen cellen waarvoor masker(tel_index) waar is: lijst (aantal, centrum x, y, bbox)."""
    gezien = bytearray(raster.nx * raster.ny)
    uit = []
    for start in range(raster.nx * raster.ny):
        if gezien[start] or not masker(start):
            continue
        stapel = [start]
        gezien[start] = 1
        cellen = []
        while stapel:
            k = stapel.pop()
            cellen.append(k)
            j, i = divmod(k, raster.nx)
            for ni, nj in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
                if 0 <= ni < raster.nx and 0 <= nj < raster.ny:
                    nk = nj * raster.nx + ni
                    if not gezien[nk] and masker(nk):
                        gezien[nk] = 1
                        stapel.append(nk)
        xs = [raster.x0 + (k % raster.nx + 0.5) * raster.stap for k in cellen]
        ys = [raster.y0 + (k // raster.nx + 0.5) * raster.stap for k in cellen]
        uit.append((len(cellen), sum(xs) / len(xs), sum(ys) / len(ys), (min(xs), min(ys), max(xs), max(ys))))
    return sorted(uit, reverse=True)


def overlap_objecten(objecten, meshes_per_object, stap=1.0):
    """Toont objecten die (gedeeltelijk) over elkaar liggen, met hun BGT-kenmerken."""
    per_id = {o["id"]: o for o in objecten}
    cellen = {}
    for oid, ms in meshes_per_object.items():
        c = set()
        for m in ms:
            c |= cellen_binnen([(p["x"], p["y"]) for p in m["polygonCoordinates"]],
                               [[(p["x"], p["y"]) for p in h["polygonCoordinates"]] for h in m.get("holes", [])], stap)
        cellen[oid] = c
    cel_van = {}
    paren = defaultdict(lambda: [0, 0.0, 0.0])
    for oid, c in cellen.items():
        for cel in c:
            andere = cel_van.get(cel)
            if andere is None:
                cel_van[cel] = oid
            elif andere != oid:
                p = paren[(andere, oid)]
                p[0] += 1
                p[1] += (cel[0] + 0.5) * stap
                p[2] += (cel[1] + 0.5) * stap
    print(f"3. Overlap tussen objecten in de data: {len(paren)} paren liggen (gedeeltelijk) over elkaar.")
    rijen = []
    for (a, b), (n, sx, sy) in paren.items():
        kleinste = min(len(cellen[a]), len(cellen[b])) or 1
        rijen.append((n * stap * stap, 100 * n / kleinste, a, b, sx / n, sy / n))
    rijen.sort(reverse=True)

    def beschrijf(o):
        at = o["attributen"]
        delen = [str(at.get(k)) for k in ("bgt_type", "bgt_functie", "bgt_fysiekvoorkomen", "3df_class") if at.get(k)]
        return f"{o['type']} {o['id']} [{', '.join(delen) or 'geen kenmerken'}]"
    for opp, pct, a, b, cx, cy in rijen[:12]:
        print(f"   {opp:7.1f} m2 ({pct:3.0f}% van de kleinste) rond ({cx:.0f}, {cy:.0f}):")
        print(f"      {beschrijf(per_id[a])}")
        print(f"      {beschrijf(per_id[b])}")
    if rijen:
        telling = Counter()
        for _, pct, a, b, _, _ in rijen:
            kleinste = a if len(cellen[a]) <= len(cellen[b]) else b
            telling[str(per_id[kleinste]["attributen"].get("bgt_type") or "(geen bgt_type)")] += 1
        print("   BGT-type van het kleinste object per paar: " + ", ".join(f"{k} {v}" for k, v in telling.most_common()))


def controle(objecten, meshes_per_object, meshes_extra, voetafdrukken, gebied, stap=1.0):
    """Meet gaten: (1) driehoeksoppervlak tegen meshoppervlak per object, (2) onbedekte plekken op een raster."""
    print("\n=== Controle op gaten ===")
    # 1. oppervlakte per object
    afwijkend = []
    for o in objecten:
        X, Y, Z = o["xyz"]
        tri = sum(abs((X[b] - X[a]) * (Y[c] - Y[a]) - (X[c] - X[a]) * (Y[b] - Y[a])) / 2
                  for a, b, c in o["driehoeken"])
        mesh = 0.0
        for m in meshes_per_object.get(o["id"], []):
            buiten = [(p["x"], p["y"]) for p in m["polygonCoordinates"]]
            mesh += abs(vorm_oppervlak(buiten))
            for h in m.get("holes", []):
                mesh -= abs(vorm_oppervlak([(p["x"], p["y"]) for p in h["polygonCoordinates"]]))
        if abs(tri - mesh) > max(0.05, 0.001 * tri):
            afwijkend.append((abs(tri - mesh), o["id"], o["type"], tri, mesh))
    print(f"1. Oppervlakte per object: {len(afwijkend)} van de {len(objecten)} objecten wijken af "
          f"(driehoeken tegen mesh-omtrek min gaten).")
    for verschil, oid, t, tri, mesh in sorted(afwijkend, reverse=True)[:6]:
        print(f"   {t} {oid}: driehoeken {tri:.2f} m2, mesh {mesh:.2f} m2, verschil {verschil:.2f} m2")
    if not afwijkend:
        print("   Geen afwijkingen: de omtrekken en gaten komen precies overeen met de driehoeken.")

    # 2. raster
    data = Raster(gebied, stap)
    dek = Raster(gebied, stap)
    voet = Raster(gebied, stap)
    for o in objecten:
        X, Y, Z = o["xyz"]
        for a, b, c in o["driehoeken"]:
            data.vul_driehoek((X[a], Y[a]), (X[b], Y[b]), (X[c], Y[c]))
    for ring in voetafdrukken:
        voet.vul_vorm(ring)
    alle_meshes = [m for ms in meshes_per_object.values() for m in ms] + list(meshes_extra)
    for m in alle_meshes:
        dek.vul_vorm([(p["x"], p["y"]) for p in m["polygonCoordinates"]],
                     [[(p["x"], p["y"]) for p in h["polygonCoordinates"]] for h in m.get("holes", [])])
    n = data.nx * data.ny
    oppervlak = n * stap * stap
    d, w, v = data.tel, dek.tel, voet.tel
    leeg_data = sum(1 for k in range(n) if not d[k] and not v[k])
    verlies = sum(1 for k in range(n) if d[k] and not w[k] and not v[k])
    dubbel = sum(1 for k in range(n) if w[k] > 1)
    print(f"2. Raster van {stap:g} m over {oppervlak:.0f} m2:")
    print(f"   niet gedekt door driehoeken of gebouwvoetafdrukken (gaten in de DATA): "
          f"{leeg_data * stap * stap:.0f} m2 ({100 * leeg_data / n:.2f}%)")
    print(f"   wel in de data maar niet in onze meshes (VERLIES door de omzetting): "
          f"{verlies * stap * stap:.0f} m2 ({100 * verlies / n:.2f}%)")
    print(f"   door meer dan een mesh bedekt (overlap): {dubbel * stap * stap:.0f} m2 ({100 * dubbel / n:.2f}%)")
    if dubbel:
        print()
        overlap_objecten(objecten, meshes_per_object, stap)
        print()
    for naam, masker in (("gaten in de data", lambda k: not d[k] and not v[k]),
                         ("verlies door de omzetting", lambda k: d[k] and not w[k] and not v[k])):
        groepen = clusters(dek, masker)
        if not groepen:
            continue
        print(f"   grootste groepen onbedekte cellen, {naam}:")
        for aantal, cx, cy, (x0, y0, x1, y1) in groepen[:6]:
            print(f"      {aantal * stap * stap:6.0f} m2 rond ({cx:.1f}, {cy:.1f}); "
                  f"x {x0:.1f}-{x1:.1f}, y {y0:.1f}-{y1:.1f}")


def maak_terreinoppervlakken(bijwerken=False):
    """Maakt de terreinoppervlakken aan en legt uit hoe je ze per laag instelt.

    Het oppervlak van een bestaande Mesh is niet via Tapir in te stellen; dat doe je in Archicad zelf."""
    kaart = _kaart()

    print("Oppervlakken voor het terrein:")
    opp = D.zorg_voor_oppervlakken(kaart, bijwerken, TERREIN_OPPERVLAKKEN)
    if opp is None:
        print("De oppervlakken konden niet worden aangemaakt.")
        return 1
    print("\nStel de oppervlakken eenmalig in Archicad in, per laag:")
    print("   1. Zoek en selecteer (Ctrl+F): elementtype Mesh en de laag hieronder.")
    print("   2. Open de instellingen van de selectie en kies bij het model het oppervlak hieronder.")
    for typ, (naam, _) in TERREIN_OPPERVLAKKEN.items():
        print(f"      laag {TYPEN[typ]:26} -> oppervlak {naam}")
    return 0


# ------------------------------------------------------------- Materialen


MESH_OPPERVLAK_VELDEN = ("topMaterial", "sideMaterial", "bottomMaterial")


def oppervlak_velden(guid):
    """Het bovenoppervlak, het zijoppervlak en het onderoppervlak van een mesh, alle drie hetzelfde oppervlak."""
    return {veld: {"overridden": True, "attributeId": {"guid": guid}} for veld in MESH_OPPERVLAK_VELDEN}


def _lijst_met_namen(antwoord):
    """De eerste lijst woordenboeken met een 'name' in een antwoord, in welke sleutel die ook staat."""
    if isinstance(antwoord, dict):
        for v in antwoord.values():
            if isinstance(v, list) and v and isinstance(v[0], dict) and "name" in v[0]:
                return v
    return []


def lees_bouwmaterialen(k):
    """{naam: details} van alle bouwmaterialen in het project."""
    r = k.officieel("API.GetAttributesByType", {"attributeType": "BuildingMaterial"})
    ids = r.get("result", {}).get("attributeIds", [])
    uit = {}
    for i in range(0, len(ids), 100):
        d = k.tapir("GetBuildingMaterials", {"attributeIds": ids[i:i + 100]})
        for it in _lijst_met_namen(k.pak(d) if d.get("succeeded") else {}):
            uit[it.get("name")] = it
    return uit


def lees_oppervlakken_met_index(k):
    """{naam: (guid, index)} van alle oppervlakken."""
    r = k.officieel("API.GetAttributesByType", {"attributeType": "Surface"})
    ids = r.get("result", {}).get("attributeIds", [])
    uit = {}
    for i in range(0, len(ids), 100):
        for it in k.pak(k.tapir("GetSurfaces", {"attributeIds": ids[i:i + 100]})).get("surfaces", []):
            uit[it.get("name")] = (D.guid_uit(it.get("attributeId")), it.get("index"))
    return uit


def zorg_voor_bouwmaterialen(k, typen=None):
    """Zorgt voor een bouwmateriaal per terreintype met het oppervlak van dat type als oppervlak van het materiaal.

    Geeft {type: {'guid': ...}} voor de materialen die bestaan of zijn aangemaakt. De overige velden (prioriteit,
    snijvulling en pennen) komen van een bestaand bouwmateriaal in het project."""
    oppervlakken = lees_oppervlakken_met_index(k)
    bestaande = lees_bouwmaterialen(k)
    sjabloon = next(iter(bestaande.values()), {})
    uit = {}
    for typ, (naam, _) in TERREIN_OPPERVLAKKEN.items():
        if typen is not None and typ not in typen:
            continue
        guid, index = oppervlakken.get(naam, (None, None))
        if guid is None or index is None:
            continue
        bestaand = bestaande.get(naam)
        if bestaand and bestaand.get("cutSurfaceIndex") == index:
            uit[typ] = {"guid": D.guid_uit(bestaand.get("attributeId"))}
            continue
        data = {"name": naam, "connPriority": sjabloon.get("connPriority", 1),
                "cutFillIndex": sjabloon.get("cutFillIndex", 1), "cutFillPen": sjabloon.get("cutFillPen", 1),
                "cutFillBackgroundPen": sjabloon.get("cutFillBackgroundPen", 0), "cutSurfaceIndex": index}
        if bestaand and bestaand.get("attributeId"):
            data["attributeId"] = bestaand["attributeId"]
        r = k.tapir("CreateBuildingMaterials", {"buildingMaterialDataArray": [data], "overwriteExisting": True})
        nieuw = k.pak(r).get("attributeIds") if r.get("succeeded") else None
        if not nieuw or not D.guid_uit(nieuw[0]):
            print(f"   bouwmateriaal {naam} aanmaken mislukt: {str(r.get('error', r))[:200]}")
            continue
        uit[typ] = {"guid": D.guid_uit(nieuw[0])}
        print(f"   bouwmateriaal {naam}: {'bijgewerkt' if bestaand else 'aangemaakt'} (met het oppervlak {naam})")
    return uit


def favorietnaam(typ):
    """De naam van de favoriet voor een terreintype: gelijk aan de naam van het oppervlak, bijvoorbeeld PDOK_weg."""
    return TERREIN_OPPERVLAKKEN[typ][0]


def lees_oppervlakken(k):
    """{naam: guid} van alle oppervlakken in het project."""
    r = k.officieel("API.GetAttributesByType", {"attributeType": "Surface"})
    ids = r.get("result", {}).get("attributeIds", [])
    uit = {}
    for i in range(0, len(ids), 100):
        for it in k.pak(k.tapir("GetSurfaces", {"attributeIds": ids[i:i + 100]})).get("surfaces", []):
            uit[it.get("name")] = D.guid_uit(it.get("attributeId"))
    return uit


def favorieten_van_mesh(k):
    """Namen van de favorieten voor meshes."""
    r = k.tapir("GetFavoritesByType", {"elementType": "Mesh"})
    if not r.get("succeeded"):
        return set()
    namen = set()

    def verzamel_namen(x):
        if isinstance(x, str):
            namen.add(x)
        elif isinstance(x, list):
            for y in x:
                verzamel_namen(y)
        elif isinstance(x, dict):
            if isinstance(x.get("name"), str):
                namen.add(x["name"])
            else:
                for y in x.values():
                    verzamel_namen(y)
    verzamel_namen(k.pak(r))
    return namen


def terreinmeshes_per_type(k):
    """{type: [(element, details)]} van de meshes op de vier terreinlagen."""
    bestaande = k.alle_lagen()
    laag_naar_type = {bestaande[naam]["index"]: t for t, naam in TYPEN.items() if naam in bestaande}
    if not laag_naar_type:
        return {}
    r = k.tapir("GetElementsByType", {"elementType": "Mesh"})
    elementen = k.pak(r).get("elements", [])
    uit = defaultdict(list)
    for i in range(0, len(elementen), 200):
        blok = elementen[i:i + 200]
        d = k.tapir("GetDetailsOfElements", {"elements": blok})
        for e, it in zip(blok, k.pak(d).get("detailsOfElements", [])):
            if isinstance(it, dict) and it.get("layerIndex") in laag_naar_type:
                uit[laag_naar_type[it["layerIndex"]]].append((e, it))
    return uit


def oppervlakken_van_mesh(k, element):
    """Telling {guid: aantal vlakken} van de oppervlakken van een mesh, zoals Archicad ze nu heeft."""
    g = k.pak(k.tapir("Get3DGeometryOfElements", {"elements": [element]}))
    teller = Counter()
    for geo in g.get("geometries3D", []):
        for lichaam in geo.get("bodies", []):
            for pg in lichaam.get("polygons", []):
                teller[D.guid_uit(pg.get("surfaceId"))] += 1
    return teller


def pas_favorieten_toe(k, per_type, melden=True):
    """Past de favoriet van elk terreintype toe op de meshes van dat type en zet daarna de laag en het Element-ID
    terug. per_type: {type: [(element, laag_index, element_id)]}. Geeft {type: aantal toegepast}."""
    bestaan = favorieten_van_mesh(k)
    toegepast = {}
    for typ, lijst in per_type.items():
        naam = favorietnaam(typ)
        if not lijst:
            continue
        if naam not in bestaan:
            if melden:
                print(f"   geen favoriet '{naam}': de meshes van {typ} behouden het standaardoppervlak "
                      f"(maak de favorieten met 'python terrein.py --favorieten-maken')")
            continue
        elementen = [e for e, _, _ in lijst]
        basis = {"favorite": naam, "elements": elementen, "applySettings": True, "applyClassifications": False,
                 "applyCategories": False, "applyProperties": False}
        r = k.tapir("ApplyFavoritesToElements", dict(basis, keepFields=["id", "layerIndex"]))
        if not r.get("succeeded"):
            r = k.tapir("ApplyFavoritesToElements", basis)     # zonder keepFields; laag en ID zetten we hierna zelf terug
        if not r.get("succeeded"):
            print(f"   favoriet '{naam}' toepassen mislukt: {str(r.get('error', r))[:200]}")
            continue
        # laag en ID terugzetten, ook als keepFields het al deed
        for i in range(0, len(lijst), 100):
            blok = lijst[i:i + 100]
            k.tapir("SetDetailsOfElements", {"elementsWithDetails": [
                {"elementId": e["elementId"], "details": {"layerIndex": laag, "id": eid}}
                for e, laag, eid in blok]})
        toegepast[typ] = len(lijst)
    return toegepast


def maak_favorieten():
    """Maakt van een mesh per terreinlaag een favoriet, mits die mesh het juiste oppervlak heeft."""
    k = _kaart()
    oppervlakken = lees_oppervlakken(k)
    per_type = terreinmeshes_per_type(k)
    if not per_type:
        print("Er zijn geen terreinmeshes in dit project.")
        return 1
    bestaan = favorieten_van_mesh(k)
    print("Favorieten voor de terreinoppervlakken:")
    ontbreekt = []
    for typ, (opp_naam, _) in TERREIN_OPPERVLAKKEN.items():
        naam = favorietnaam(typ)
        meshes = per_type.get(typ, [])
        if naam in bestaan:
            print(f"   {naam}: bestaat al (verwijder de favoriet in Archicad als je hem opnieuw wilt maken)")
            continue
        if not meshes:
            print(f"   {naam}: geen meshes op laag {TYPEN[typ]}")
            continue
        guid = oppervlakken.get(opp_naam)
        if not guid:
            print(f"   {naam}: het oppervlak {opp_naam} bestaat niet; maak het eerst met 'python terrein.py --oppervlakken'")
            continue
        bron = None
        for e, it in meshes[:60]:
            telling = oppervlakken_van_mesh(k, e)
            if telling and set(telling) == {guid}:
                bron = e
                break
        if bron is None:
            ontbreekt.append((typ, opp_naam))
            print(f"   {naam}: geen enkele mesh op {TYPEN[typ]} heeft het oppervlak {opp_naam}")
            continue
        r = k.tapir("CreateFavoritesFromElements", {"favoritesFromElements": [
            {"elementId": bron["elementId"], "favorite": naam}]})
        if r.get("succeeded"):
            print(f"   {naam}: gemaakt van een mesh met het oppervlak {opp_naam}")
        else:
            print(f"   {naam}: aanmaken mislukt: {str(r.get('error', r))[:200]}")
    if ontbreekt:
        print("\nStel eerst in Archicad bij minstens een mesh per laag het oppervlak in, en voer dit opnieuw uit:")
        for typ, opp_naam in ontbreekt:
            print(f"   laag {TYPEN[typ]:26} -> oppervlak {opp_naam}")
        print("   (selecteer een mesh van die laag, open de instellingen en kies bij het model het oppervlak)")
        return 1
    return 0


def pas_materialen_toe_op_bestaande():
    """Past de favorieten toe op alle meshes op de terreinlagen die er al staan."""
    k = _kaart()
    per_type = terreinmeshes_per_type(k)
    if not per_type:
        print("Er zijn geen terreinmeshes in dit project.")
        return 1
    invoer = {t: [(e, it.get("layerIndex"), it.get("id")) for e, it in lijst] for t, lijst in per_type.items()}
    oppervlakken = lees_oppervlakken(k)
    print("Oppervlakken toekennen aan de bestaande terreinmeshes:")
    # eerst rechtstreeks met ModifyMeshes (kan in een Tapir die topMaterial kent); anders via de favorieten
    direct_gedaan = {}
    for typ, lijst in per_type.items():
        guid = oppervlakken.get(TERREIN_OPPERVLAKKEN[typ][0])
        if not guid or not lijst:
            continue
        proef = lijst[0][0]
        k.tapir("ModifyMeshes", {"meshesData": [{"elementId": proef["elementId"],
                                                  "meshData": oppervlak_velden(guid)}]})
        tel = oppervlakken_van_mesh(k, proef)
        if tel and set(tel) == {guid}:
            for i in range(0, len(lijst), 50):
                k.tapir("ModifyMeshes", {"meshesData": [
                    {"elementId": e["elementId"], "meshData": oppervlak_velden(guid)} for e, _ in lijst[i:i + 50]]})
            direct_gedaan[typ] = len(lijst)
            print(f"   {TYPEN[typ]}: {len(lijst)} meshes, oppervlak {TERREIN_OPPERVLAKKEN[typ][0]} rechtstreeks "
                  f"ingesteld (gecontroleerd bij een voorbeeld)")
    invoer = {t: v for t, v in invoer.items() if t not in direct_gedaan}
    if direct_gedaan and not invoer:
        return 0
    if invoer and not direct_gedaan:
        print("   ModifyMeshes kan het oppervlak in deze Tapir niet instellen; ik gebruik de favorieten.")
    toegepast = pas_favorieten_toe(k, invoer)
    for typ, n in toegepast.items():
        opp_naam = TERREIN_OPPERVLAKKEN[typ][0]
        voorbeeld = per_type[typ][0][0]
        telling = oppervlakken_van_mesh(k, voorbeeld)
        goed = bool(telling) and set(telling) == {oppervlakken.get(opp_naam)}
        print(f"   {TYPEN[typ]}: {n} meshes, oppervlak {opp_naam} "
              f"{'toegekend (gecontroleerd bij een voorbeeld)' if goed else 'toegepast, maar bij het voorbeeld niet bevestigd'}")
    if not toegepast:
        print("Er is niets toegepast.")
        return 1
    return 0


def test_meshoppervlak():
    """Test of deze Tapir het oppervlak van een mesh kan instellen, en welke versie het is. Ruimt zelf op."""
    k = _kaart()
    try:
        v = k.tapir("GetAddOnVersion")
        print("Tapir-versie:", json.dumps(k.pak(v), ensure_ascii=False) if v.get("succeeded") else "onbekend")
    except Exception:
        print("Tapir-versie: onbekend")
    oppervlakken = lees_oppervlakken(k)
    kies = next(((n, g) for n, g in oppervlakken.items() if n and n.startswith("PDOK_")), None) \
        or next(((n, g) for n, g in oppervlakken.items() if n), None)
    if not kies:
        print("Er zijn geen oppervlakken in het project.")
        return 1
    naam, guid = kies
    print(f"Testoppervlak: {naam}")
    x0, y0, z0 = 1000.0, 1000.0, 50.0
    vierkant = [{"x": x0, "y": y0, "z": z0}, {"x": x0 + 4, "y": y0, "z": z0},
                {"x": x0 + 4, "y": y0 + 4, "z": z0}, {"x": x0, "y": y0 + 4, "z": z0}]
    basis = {"polygonCoordinates": vierkant, "level": 0, "floorIndex": 0, "skirtType": "SurfaceOnlyWithoutSkirt"}
    gemaakt = []
    uitkomst = {}
    try:
        r = k.tapir("CreateMeshes", {"meshesData": [dict(basis, **oppervlak_velden(guid))]})
        e = (k.pak(r).get("elements") or [{}])[0] if r.get("succeeded") else {}
        if "elementId" in e:
            gemaakt.append(e)
            tel = oppervlakken_van_mesh(k, e)
            uitkomst["create"] = bool(tel) and set(tel) == {guid}
            print("CreateMeshes met oppervlak: " + ("WERKT (het oppervlak is toegekend)" if uitkomst["create"]
                  else "geslaagd, maar het oppervlak is niet veranderd (deze Tapir negeert het veld)"))
        else:
            tekst = str(r.get("error", r))
            uitkomst["create"] = False
            print("CreateMeshes met oppervlak: wordt geweigerd" + (" (het veld bestaat in deze Tapir niet)"
                  if "additionalProperties" in tekst else "") + f": {tekst[:160]}")
        r = k.tapir("CreateMeshes", {"meshesData": [dict(basis)]})
        e2 = (k.pak(r).get("elements") or [{}])[0] if r.get("succeeded") else {}
        if "elementId" in e2:
            gemaakt.append(e2)
            k.tapir("ModifyMeshes", {"meshesData": [{"elementId": e2["elementId"],
                                                      "meshData": oppervlak_velden(guid)}]})
            tel = oppervlakken_van_mesh(k, e2)
            uitkomst["modify"] = bool(tel) and set(tel) == {guid}
            print("ModifyMeshes met oppervlak: " + ("WERKT (het oppervlak is toegekend)" if uitkomst["modify"]
                  else "meldt succes, maar het oppervlak is niet veranderd (deze Tapir negeert het veld)"))
        # derde route: een bouwmateriaal met het oppervlak als oppervlak, gekoppeld bij het aanmaken
        typ_test = next((t for t, (n, _) in TERREIN_OPPERVLAKKEN.items() if oppervlakken.get(n)), None)
        if typ_test:
            bm = zorg_voor_bouwmaterialen(k, {typ_test})
            if typ_test in bm:
                r = k.tapir("CreateMeshes", {"meshesData": [dict(basis, buildingMaterialId=bm[typ_test])]})
                e3 = (k.pak(r).get("elements") or [{}])[0] if r.get("succeeded") else {}
                if "elementId" in e3:
                    gemaakt.append(e3)
                    tel = oppervlakken_van_mesh(k, e3)
                    uitkomst["bm"] = bool(tel) and set(tel) == {oppervlakken[TERREIN_OPPERVLAKKEN[typ_test][0]]}
                    print("CreateMeshes met buildingMaterialId: " + (
                        "WERKT (het bouwmateriaal bepaalt het oppervlak)" if uitkomst["bm"]
                        else "geslaagd, maar het oppervlak is niet het oppervlak van het bouwmateriaal"))
                else:
                    print("CreateMeshes met buildingMaterialId: geweigerd: " + str(r.get("error", r))[:160])
    finally:
        if gemaakt:
            k.tapir("DeleteElements", {"elements": gemaakt})
    print()
    if uitkomst.get("bm") and not (uitkomst.get("create") or uitkomst.get("modify")):
        print("Het oppervlak van een mesh is in te stellen via een bouwmateriaal bij het aanmaken. Nieuwe meshes "
              "krijgen het zo automatisch; voor meshes die er al staan maak je de terreinlagen leeg en importeer je opnieuw.")
    elif uitkomst.get("create") or uitkomst.get("modify"):
        print("Het oppervlak kan rechtstreeks worden ingesteld: nieuwe meshes krijgen het bij het aanmaken.")
    else:
        print("Dit Tapir kan het oppervlak van een mesh nog niet instellen. De wijziging staat sinds 10 november 2026 in "
              "Tapir (pull request 2645); controleer of er een nieuwere versie is dan de jouwe. Intussen "
              "kan het via favorieten (zie --favorieten-maken).")
    return 0


def toon_selectie():
    """Toont wat er in Archicad is geselecteerd (selecteer bijvoorbeeld het witte vlak in 3D)."""
    kaart = _kaart()

    kaart.MAPNAAM = MAP
    r = kaart.tapir("GetSelectedElements")
    sel = kaart.pak(r).get("elements", [])
    if not sel:
        print("Er is niets geselecteerd. Klik in Archicad een element aan (in 3D of op de plattegrond) en draai opnieuw.")
        return 1
    laagnaam = {v["index"]: n for n, v in kaart.alle_lagen().items()}
    print(f"{len(sel)} element(en) geselecteerd" + (" (de eerste 5 worden getoond)" if len(sel) > 5 else "") + ".")
    for e in sel[:5]:
        d = kaart.pak(kaart.tapir("GetDetailsOfElements", {"elements": [e]})).get("detailsOfElements", [{}])
        it = d[0] if d else {}
        det = it.get("details") or {}
        print(f"\n--- {it.get('type')}  laag: {laagnaam.get(it.get('layerIndex'), it.get('layerIndex'))}  "
              f"Element-ID: {it.get('id')!r}  verdieping: {it.get('floorIndex')}")
        g = kaart.pak(kaart.tapir("Get3DGeometryOfElements", {"elements": [e]}))
        lichamen = []
        for geo in g.get("geometries3D", []):
            lichamen += geo.get("bodies", [])
        pts = [v for l in lichamen for v in l.get("vertices", [])]
        pols = [pg for l in lichamen for pg in l.get("polygons", [])]
        if pts:
            xs, ys, zs = [v["x"] for v in pts], [v["y"] for v in pts], [v["z"] for v in pts]
            print(f"    ligging x {min(xs):.2f}-{max(xs):.2f}, y {min(ys):.2f}-{max(ys):.2f}, hoogte {min(zs):.2f}-{max(zs):.2f}; "
                  f"{len(pts)} hoekpunten, {len(pols)} vlakken")
            n_omlaag = 0
            for pg in pols:
                ids = pg.get("vertexIds", [])
                if len(ids) >= 3:
                    a, b, c = pts[ids[0]], pts[ids[1]], pts[ids[2]]
                    nz = (b["x"] - a["x"]) * (c["y"] - a["y"]) - (c["x"] - a["x"]) * (b["y"] - a["y"])
                    if nz < 0:
                        n_omlaag += 1
            print(f"    vlakken waarvan de bovenkant naar beneden wijst (omgekeerde draairichting): {n_omlaag} van {len(pols)}")
        if it.get("type") == "Mesh":
            sub = {k: det.get(k) for k in ("level", "skirtType", "skirtLevel", "ridges", "showLines",
                                              "contourPen", "levelPen", "lineTypeIndex") if k in det}
            print("    meshinstellingen:", sub)
            print(f"    omtrek {len(det.get('polygonCoordinates') or [])} punten, {len(det.get('holes') or [])} gaten")
    return 0


def ring_xy(punten):
    """Lijst (x, y) uit coordinaten (woordenboeken of paren); een herhaald eindpunt wordt weggelaten."""
    pts = [(p["x"], p["y"]) if isinstance(p, dict) else (p[0], p[1]) for p in punten]
    if len(pts) > 1 and abs(pts[0][0] - pts[-1][0]) < 1e-6 and abs(pts[0][1] - pts[-1][1]) < 1e-6:
        pts.pop()
    return pts


def gaten_uit_details(details):
    """De gaten van een mesh uit GetDetailsOfElements, als lijst ringen."""
    uit = []
    for h in details.get("holes") or []:
        punten = h.get("polygonCoordinates") if isinstance(h, dict) else h
        if punten:
            uit.append(ring_xy(punten))
    return uit


def cellen_binnen(buiten, gaten, stap):
    """Cellen (i, j) van een raster met oorsprong (0, 0) waarvan het midden binnen de vorm ligt, buiten de gaten."""
    xs, ys = [p[0] for p in buiten], [p[1] for p in buiten]
    uit = set()
    for i in range(int(math.floor(min(xs) / stap)), int(math.floor(max(xs) / stap)) + 1):
        cx = (i + 0.5) * stap
        for j in range(int(math.floor(min(ys) / stap)), int(math.floor(max(ys) / stap)) + 1):
            cy = (j + 0.5) * stap
            if punt_in_polygoon(cx, cy, buiten) and not any(punt_in_polygoon(cx, cy, g) for g in gaten):
                uit.add((i, j))
    return uit


def controle_overlap(stap=1.0):
    """Zoekt meshes op onze terreinlagen die over elkaar liggen. Leest alleen."""
    kaart = _kaart()
    bestaande = kaart.alle_lagen()
    lagen = {bestaande[n]["index"]: n for n in ALLE_LAGEN.values() if n in bestaande}
    if not lagen:
        print("Er zijn geen terreinlagen in dit project.")
        return 1
    r = kaart.tapir("GetElementsByType", {"elementType": "Mesh"})
    elementen = kaart.pak(r).get("elements", [])
    meshes = []
    for i in range(0, len(elementen), 200):
        blok = elementen[i:i + 200]
        d = kaart.tapir("GetDetailsOfElements", {"elements": blok})
        for e, it in zip(blok, kaart.pak(d).get("detailsOfElements", [])):
            if not (isinstance(it, dict) and it.get("layerIndex") in lagen):
                continue
            det = it.get("details") or {}
            buiten = ring_xy(det.get("polygonCoordinates") or [])
            if len(buiten) >= 3:
                meshes.append({"id": it.get("id"), "laag": lagen[it["layerIndex"]], "buiten": buiten,
                               "gaten": gaten_uit_details(det)})
    print(f"{len(meshes)} meshes op de terreinlagen worden vergeleken (raster {stap:g} m)...")

    # 1. exacte dubbelen: dezelfde omtrek
    groepen = defaultdict(list)
    for k, m in enumerate(meshes):
        handtekening = tuple(sorted((round(x, 2), round(y, 2)) for x, y in m["buiten"]))
        groepen[handtekening].append(k)
    exact = [g for g in groepen.values() if len(g) > 1]
    print(f"\n1. Exacte dubbelen (dezelfde omtrek): {len(exact)} groepen, "
          f"{sum(len(g) - 1 for g in exact)} meshes te veel.")
    for g in exact[:8]:
        ids = [meshes[k]["id"] for k in g]
        print(f"   {len(g)}x op {meshes[g[0]]['laag']}, ID's: {', '.join(str(i) for i in ids)}"
              f" ({'zelfde ID' if len(set(ids)) == 1 else 'verschillende ID' + chr(39) + 's'})")

    # 2. overlap per paar
    cel_van = {}
    paren = defaultdict(lambda: [0, 0.0, 0.0])        # (i, j) -> [cellen, som x, som y]
    for k, m in enumerate(meshes):
        m["cellen"] = cellen_binnen(m["buiten"], m["gaten"], stap)
        for cel in m["cellen"]:
            andere = cel_van.get(cel)
            if andere is None:
                cel_van[cel] = k
            else:
                p = paren[(andere, k)]
                p[0] += 1
                p[1] += (cel[0] + 0.5) * stap
                p[2] += (cel[1] + 0.5) * stap
    print(f"\n2. Overlap: {len(paren)} paren meshes liggen (gedeeltelijk) over elkaar.")
    rijen = []
    for (a, b), (n, sx, sy) in paren.items():
        kleinste = min(len(meshes[a]["cellen"]), len(meshes[b]["cellen"])) or 1
        rijen.append((n * stap * stap, 100 * n / kleinste, a, b, sx / n, sy / n))
    rijen.sort(reverse=True)
    zelfde = sum(1 for r_ in rijen if meshes[r_[2]]["id"] == meshes[r_[3]]["id"])
    print(f"   daarvan met hetzelfde Element-ID: {zelfde}; met verschillende ID's: {len(rijen) - zelfde}")
    for opp, pct, a, b, cx, cy in rijen[:12]:
        ma, mb = meshes[a], meshes[b]
        print(f"   {opp:8.1f} m2 ({pct:3.0f}% van de kleinste) rond ({cx:.0f}, {cy:.0f}): "
              f"{ma['laag'][11:]} {ma['id']} en {mb['laag'][11:]} {mb['id']}"
              f" ({'zelfde ID' if ma['id'] == mb['id'] else 'verschillende ID' + chr(39) + 's'})")
    if not rijen:
        print("   Geen overlap gevonden.")
    return 0


def controle_archicad(stap=0.25):
    """Leest de meshes op onze lagen uit Archicad terug en meet waar driehoeken ontbreken."""
    kaart = _kaart()

    kaart.MAPNAAM = MAP
    bestaande = kaart.alle_lagen()
    lagen = {bestaande[n]["index"]: n for n in ALLE_LAGEN.values() if n in bestaande}
    if not lagen:
        print("Er zijn geen terreinlagen in dit project.")
        return 1
    r = kaart.tapir("GetElementsByType", {"elementType": "Mesh"})
    elementen = kaart.pak(r).get("elements", [])
    ours = []
    for i in range(0, len(elementen), 200):
        blok = elementen[i:i + 200]
        d = kaart.tapir("GetDetailsOfElements", {"elements": blok})
        for e, it in zip(blok, kaart.pak(d).get("detailsOfElements", [])):
            if isinstance(it, dict) and it.get("layerIndex") in lagen:
                ours.append((e, it))
    print(f"{len(ours)} meshes op de terreinlagen ({', '.join(lagen.values())}).")
    afwijkend = []
    gemeten = 0
    for e, it in ours:
        det = it.get("details") or {}
        buiten = ring_xy(det.get("polygonCoordinates") or [])
        if len(buiten) < 3:
            continue
        gaten = gaten_uit_details(det)
        verwacht = abs(vorm_oppervlak(buiten)) - sum(abs(vorm_oppervlak(g)) for g in gaten)
        g3 = kaart.tapir("Get3DGeometryOfElements", {"elements": [e]})
        antwoord = kaart.pak(g3)
        lichamen = []
        for geo in antwoord.get("geometries3D", []):
            lichamen += geo.get("bodies", [])
        driehoeken = []
        for lichaam in lichamen:
            punten = lichaam.get("vertices", [])
            for pg in lichaam.get("polygons", []):
                ids = pg.get("vertexIds", [])
                for k in range(1, len(ids) - 1):
                    a, b, c = punten[ids[0]], punten[ids[k]], punten[ids[k + 1]]
                    driehoeken.append(((a["x"], a["y"]), (b["x"], b["y"]), (c["x"], c["y"])))
        gedekt = sum(abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) / 2 for a, b, c in driehoeken)
        gemeten += 1
        if abs(verwacht - gedekt) > max(0.02, 0.0005 * verwacht):
            afwijkend.append((abs(verwacht - gedekt), it.get("id"), lagen.get(it.get("layerIndex")),
                              verwacht, gedekt, buiten, gaten, driehoeken))
    print(f"{gemeten} meshes teruggelezen; {len(afwijkend)} wijken af (oppervlakte van de driehoeken in "
          f"Archicad tegen die van de omtrek min gaten).")
    if not afwijkend:
        print("Geen afwijkingen: Archicad dekt elke omtrek volledig.")
        return 0
    for verschil, mid, laag, verwacht, gedekt, buiten, gaten, driehoeken in sorted(afwijkend, key=lambda a: -a[0])[:12]:
        xs, ys = [p[0] for p in buiten], [p[1] for p in buiten]
        r2 = Raster((min(xs), min(ys), max(xs), max(ys)), stap)
        wens = Raster((min(xs), min(ys), max(xs), max(ys)), stap)
        wens.vul_vorm(buiten, gaten)
        for a, b, c in driehoeken:
            r2.vul_driehoek(a, b, c)
        ontbreekt = clusters(wens, lambda k: wens.tel[k] > 0 and r2.tel[k] == 0)
        teveel = clusters(wens, lambda k: wens.tel[k] == 0 and r2.tel[k] > 0)
        print(f"\n   {laag} {mid}: omtrek {verwacht:.2f} m2, Archicad dekt {gedekt:.2f} m2 "
              f"(verschil {verwacht - gedekt:+.2f} m2)")
        print(f"      ligging x {min(xs):.1f}-{max(xs):.1f}, y {min(ys):.1f}-{max(ys):.1f}; "
              f"{len(buiten)} omtrekpunten, {len(gaten)} gaten, {len(driehoeken)} driehoeken in Archicad")
        for aantal, cx, cy, (x0, y0, x1, y1) in ontbreekt[:4]:
            print(f"      ontbreekt: {aantal * stap * stap:6.2f} m2 rond ({cx:.1f}, {cy:.1f}); "
                  f"x {x0:.1f}-{x1:.1f}, y {y0:.1f}-{y1:.1f}")
        for aantal, cx, cy, (x0, y0, x1, y1) in teveel[:2]:
            print(f"      buiten de omtrek: {aantal * stap * stap:6.2f} m2 rond ({cx:.1f}, {cy:.1f})")
    totaal = sum(a[3] - a[4] for a in afwijkend)
    print(f"\nTotaal ontbrekend oppervlak in deze meshes: {totaal:.1f} m2")
    return 0


# ---------------------------------------------------------------- Ondergrond


def hoogte_op(objecten, x, y):
    """Hoogte op een punt: geinterpoleerd in de driehoek die het bevat, anders van het dichtstbijzijnde hoekpunt."""
    dichtst = None
    for o in objecten:
        X, Y, Z = o["xyz"]
        for a, b, c in o["driehoeken"]:
            if in_driehoek(x, y, X[a], Y[a], X[b], Y[b], X[c], Y[c]):
                d = (Y[b] - Y[c]) * (X[a] - X[c]) + (X[c] - X[b]) * (Y[a] - Y[c])
                l1 = ((Y[b] - Y[c]) * (x - X[c]) + (X[c] - X[b]) * (y - Y[c])) / d
                l2 = ((Y[c] - Y[a]) * (x - X[c]) + (X[a] - X[c]) * (y - Y[c])) / d
                return l1 * Z[a] + l2 * Z[b] + (1 - l1 - l2) * Z[c]
            for i in (a, b, c):
                afstand = (X[i] - x) ** 2 + (Y[i] - y) ** 2
                if dichtst is None or afstand < dichtst[0]:
                    dichtst = (afstand, Z[i])
    return dichtst[1] if dichtst else 0.0


def bouw_ondergrond(objecten, gebied, z_verschuiving=0.0, diepte=ONDERGROND_DIEPTE):
    """Een Mesh over het hele gebied, iets onder de rest, met alle hoekpunten van het terrein als hoogtepunten."""
    punten = {}
    for o in objecten:
        X, Y, Z = o["xyz"]
        for a, b, c in o["driehoeken"]:
            for i in (a, b, c):
                if gebied[0] < X[i] < gebied[2] and gebied[1] < Y[i] < gebied[3]:
                    punten.setdefault((round(X[i], AFRONDEN), round(Y[i], AFRONDEN)), Z[i])
    hoeken = [(gebied[0], gebied[1]), (gebied[2], gebied[1]), (gebied[2], gebied[3]), (gebied[0], gebied[3])]
    z0 = z_verschuiving - diepte
    omtrek = [{"x": round(x, AFRONDEN), "y": round(y, AFRONDEN),
               "z": round(hoogte_op(objecten, x, y) + z0, AFRONDEN)} for x, y in hoeken]
    sublines = [{"coordinates": [{"x": x, "y": y, "z": round(z + z0, AFRONDEN)}]}
                for (x, y), z in sorted(punten.items())]
    return {"polygonCoordinates": omtrek, "sublines": sublines,
            "id": f"ondergrond_{int(gebied[0])}_{int(gebied[1])}_{int(gebied[2])}_{int(gebied[3])}"}


# ----------------------------------------------------------------- Uitvoer


def verzamel(gebied, typen, met_bruggen, voetafdrukken=False, sla_over=()):
    tegels = D.kies_tegels(gebied, COLLECTIE)
    print(f"{len(tegels)} tegel(s) voor dit gebied:")
    for p in tegels:
        print(f"   {p['download_link'].split('/')[-1]}  luchtfoto {p.get('jaargang_luchtfoto')}  "
              f"{(p.get('download_size_bytes') or 0) / 1024 / 1024:.1f} MB")
    objecten = []
    voet = []
    X = Y = Z = None
    for p in tegels:
        pad = D.download(p)
        with zipfile.ZipFile(pad) as z:
            for i in z.infolist():
                if not i.filename.lower().endswith(".json") or i.is_dir():
                    continue
                if i.file_size / 1024 / 1024 > D.MAX_PARSE_MB:
                    print(f"   {i.filename}: te groot om te lezen, overgeslagen")
                    continue
                print(f"   {i.filename} lezen ({i.file_size / 1024 / 1024:.0f} MB uitgepakt)...")
                with z.open(i) as f:
                    data = json.load(f)
                bereik = D.bereik_vertices(data)
                if bereik and (bereik[2] < gebied[0] or bereik[0] > gebied[2]
                               or bereik[3] < gebied[1] or bereik[1] > gebied[3]):
                    print("   ligt buiten het gebied, overgeslagen")
                    continue
                gevonden, (X, Y, Z) = lees_objecten(data, gebied, typen, met_bruggen, sla_over)
                if voetafdrukken:
                    voet += lees_voetafdrukken(data, gebied, X, Y)
                print(f"   {len(gevonden)} terreinobjecten raken het gebied (CityJSON {data.get('version')})")
                objecten += gevonden
                del data
    objecten, samengevoegd = voeg_dubbelen_samen(objecten)
    if samengevoegd:
        print(f"   {samengevoegd} objecten kwamen in meerdere tegels voor (tegelrand) en zijn samengevoegd")
    return objecten, voet


GROOT_GEBIED = 600.0  # m: een gebied met een zijde groter dan dit wordt in blokken geimporteerd


HOOGTELIGGING = {}   # mesh-ID -> relatieve hoogteligging uit de bron (zie bouw_alle_meshes)


def hoogteligging_van(at):
    """De relatieve hoogteligging (0 = maaiveld, 1 en hoger = erboven, negatief = eronder) uit de eigenschappen, of None."""
    for sleutel in ("relatieve_hoogteligging", "relatieveHoogteligging", "relatieve-hoogteligging", "hoogteligging"):
        if sleutel in at:
            try:
                return int(float(at[sleutel]))
            except (TypeError, ValueError):
                return None
    return None


def mesh_zgemiddeld(m):
    zs = [p["z"] for p in m["polygonCoordinates"]]
    return sum(zs) / len(zs)


def bepaal_dekken(meshes):
    """De ID's van meshes die een dek zijn: ze liggen (voor een groot deel) in plattegrond boven een ander object, of de bron zegt
    dat ze boven het maaiveld liggen (relatieve hoogteligging groter dan 0). Geeft (ID's, aantal door de bron, aantal door overlap)."""
    cel = defaultdict(list)
    totaal = Counter()
    for i, (_t, m) in enumerate(meshes):
        buiten = ring_xy(m["polygonCoordinates"])
        gaten = [ring_xy(h["polygonCoordinates"]) for h in m.get("holes", [])]
        z = mesh_zgemiddeld(m)
        for c in cellen_binnen(buiten, gaten, DEK_STAP):
            cel[c].append((z, i))
            totaal[i] += 1
    boven = Counter()
    for lijst in cel.values():
        if len(lijst) < 2:
            continue
        lijst.sort()
        laagste = lijst[0][0]
        for z, i in lijst[1:]:
            if z - laagste >= DEK_MIN_VERSCHIL:
                boven[i] += 1
    door_overlap = {meshes[i][1]["id"] for i, n in boven.items() if totaal[i] and n >= DEK_MIN_DEEL * totaal[i]}
    door_bron = {m["id"] for _t, m in meshes if (HOOGTELIGGING.get(m["id"]) or 0) > 0}
    return door_overlap | door_bron, len(door_bron), len(door_overlap)


def bouw_alle_meshes(objecten, opties):
    meshes, totaal = [], Counter()
    for o in objecten:
        X, Y, Z = o["xyz"]
        ms, st = bouw_meshes(o, X, Y, Z, opties["z"])
        for k_, v in st.items():
            totaal[k_] += v
        hl = hoogteligging_van(o.get("attributen") or {})
        for m in ms:
            HOOGTELIGGING[m["id"]] = hl          # apart bewaard: de naadsluiting maakt nieuwe mesh-gegevens
        meshes += [(o["type"], m) for m in ms]
    return meshes, totaal


def json_van_tegel(pad):
    """De CityJSON-bestanden uit een tegel (zip), een voor een."""
    with zipfile.ZipFile(pad) as z:
        for i in z.infolist():
            if not i.filename.lower().endswith(".json") or i.is_dir():
                continue
            if i.file_size / 1024 / 1024 > D.MAX_PARSE_MB:
                print(f"   {i.filename}: te groot om te lezen, overgeslagen")
                continue
            print(f"   {i.filename} lezen ({i.file_size / 1024 / 1024:.0f} MB uitgepakt)...")
            with z.open(i) as f:
                yield json.load(f)


def importeer_terrein_blokken(k, gebied, opties):
    """Importeert een groot gebied in blokken van BLOK meter.

    Een object hoort bij precies een blok (het blok waarin zijn midden valt) en wordt met al zijn driehoeken
    gemaakt, dus er ontstaan geen dubbelen of afgekapte objecten op blokgrenzen. Elk blok sluit via de naadsluiting
    aan op de meshes die al staan. Wat al bestaat, wordt overgeslagen: een onderbroken import kun je opnieuw starten."""
    global KAART
    KAART = k
    LAATSTE.update(gelukt=0, mislukt=0)
    blokken = maak_blokken(gebied)
    print(f"Groot gebied: {(gebied[2] - gebied[0]) / 1000:.2f} x {(gebied[3] - gebied[1]) / 1000:.2f} km, "
          f"verdeeld in {len(blokken)} blokken van {BLOK:g} m.")
    tegels = D.kies_tegels(gebied, COLLECTIE)
    print(f"{len(tegels)} tegel(s):")
    for t_ in tegels:
        print(f"   {t_['download_link'].split('/')[-1]}  {(t_.get('download_size_bytes') or 0) / 1024 / 1024:.1f} MB")
    run = nieuw_run(k, gebied)
    print(f"{len(run['ids'])} meshes staan al op de terreinlagen; {len(run['ankers'])} daarvan grenzen aan het gebied.")
    opties = dict(opties, _run=run)
    gedaan = set()
    gelukt = mislukt = 0
    gestopt = False

    def meld(tekst):
        if VOORTGANG:
            VOORTGANG(tekst, min(1.0, len(gedaan) / max(1, len(blokken))))

    for tegel in tegels:
        if gestopt:
            break
        pad = D.download(tegel)
        for data in json_van_tegel(pad):
            bereik = D.bereik_vertices(data)
            if bereik and (bereik[2] < gebied[0] or bereik[0] > gebied[2] or bereik[3] < gebied[1]
                           or bereik[1] > gebied[3]):
                print("   ligt buiten het gebied, overgeslagen")
                continue
            X, Y, Z = vertexlijsten(data)
            index = indexeer_tegel(data, X, Y, gebied, opties["typen"], opties["bruggen"], set(opties["sla_over"]))
            print(f"   {sum(len(v) for v in index.values())} terreinobjecten in {len(index)} blokken voor dit gebied")
            for sleutel_blok in sorted(index):
                if STOP and STOP():
                    gestopt = True
                    print("\nGestopt op verzoek; wat al is gemaakt blijft staan en een volgende import gaat verder.")
                    break
                gedaan.add(sleutel_blok)
                alle = data.get("CityObjects", {})
                sleutels = [sl for sl in index[sleutel_blok]
                            if str((alle[sl].get("attributes") or {}).get("3df_id") or sl) not in run["objecten"]]
                if not sleutels:
                    meld(f"Terrein: blok {len(gedaan)} van {len(blokken)} (al aanwezig)")
                    continue
                objecten, _ = lees_objecten(data, None, opties["typen"], opties["bruggen"], set(opties["sla_over"]),
                                            alleen=set(sleutels), xyz=(X, Y, Z))
                meshes, _tot = bouw_alle_meshes(objecten, opties)
                bbox = blokken[sleutel_blok]
                print(f"\n=== Blok {len(gedaan)} van {len(blokken)}  (x {bbox[0]:.0f}-{bbox[2]:.0f}, "
                      f"y {bbox[1]:.0f}-{bbox[3]:.0f}): {len(objecten)} objecten, {len(meshes)} meshes ===")
                if opties["naadsluiting"] and meshes:
                    naadsluiting(meshes, opties["naad"], opties["marge"], opties["naadmax"],
                                 ankers_bij(run, bbox) if opties.get("ankers", True) else None)
                meld(f"Terrein: blok {len(gedaan)} van {len(blokken)} ({len(meshes)} meshes)")
                teken(meshes, opties)
                gelukt += LAATSTE["gelukt"]
                mislukt += LAATSTE["mislukt"]
                for t_, m_ in meshes:         # de nieuwe meshes zijn voor de volgende blokken een vast punt
                    xs = [p["x"] for p in m_["polygonCoordinates"]]
                    ys = [p["y"] for p in m_["polygonCoordinates"]]
                    run["ankers"].append((t_, {"polygonCoordinates": m_["polygonCoordinates"],
                                               "holes": m_.get("holes", []), "id": m_["id"]},
                                          (min(xs), min(ys), max(xs), max(ys))))
                run["objecten"].update(o["id"] for o in objecten)
                del objecten, meshes
            del data, X, Y, Z, index
            import gc
            gc.collect()
            if gestopt:
                break
    LAATSTE.update(gelukt=gelukt, mislukt=mislukt)
    meld("Terrein klaar")
    print(f"\nTerrein in blokken klaar: {gelukt} meshes aangemaakt, {mislukt} mislukt, "
          f"{len(gedaan)} van {len(blokken)} blokken verwerkt.")
    return 0 if gelukt or not mislukt else 1


def lees_argumenten(argumenten):
    gebied = None
    opties = {"droog": "--droog" in argumenten, "bruggen": "--brug" in argumenten,
              "lijnen": "--lijnen" in argumenten, "forceer": "--forceer" in argumenten,
              "sla_over": [], "materialen": "--zonder-materiaal" not in argumenten,
              "bomen": "--bomen" in argumenten, "boomobject": "",
              "skirt": STANDAARD_SKIRT, "diepte": STANDAARD_DIEPTE,
              "dekken": "--geen-dekken" not in argumenten, "dekdikte": DEK_DIKTE,
              "controle": "--controle" in argumenten, "ondergrond": "--ondergrond" in argumenten,
              "raster": None, "naad": "gemiddelde", "marge": NAAD_MARGE_STANDAARD, "ankers": "--geen-ankers" not in argumenten,
              "naadmax": NAAD_MAX_VERSCHIL, "naadsluiting": "--geen-naadsluiting" not in argumenten,
              "max": None, "z": 0.0, "typen": list(OBJECT_TYPEN)}
    getallen = []
    i = 0
    while i < len(argumenten):
        a = argumenten[i]
        if a == "--max" and i + 1 < len(argumenten):
            opties["max"] = int(argumenten[i + 1])
            i += 2
            continue
        if a == "--z-verschuiving" and i + 1 < len(argumenten):
            opties["z"] = float(argumenten[i + 1])
            i += 2
            continue
        if a == "--boomobject" and i + 1 < len(argumenten):
            opties["boomobject"] = argumenten[i + 1].strip()
            i += 2
            continue
        if a == "--skirt" and i + 1 < len(argumenten):
            opties["skirt"] = argumenten[i + 1].strip().lower()
            i += 2
            continue
        if a == "--dekdikte" and i + 1 < len(argumenten):
            opties["dekdikte"] = float(argumenten[i + 1])
            i += 2
            continue
        if a == "--diepte" and i + 1 < len(argumenten):
            opties["diepte"] = float(argumenten[i + 1])
            i += 2
            continue
        if a == "--sla-over" and i + 1 < len(argumenten):
            opties["sla_over"].append(argumenten[i + 1].strip().lower())
            i += 2
            continue
        if a == "--naadmax" and i + 1 < len(argumenten):
            opties["naadmax"] = float(argumenten[i + 1])
            i += 2
            continue
        if a == "--naadmarge" and i + 1 < len(argumenten):
            opties["marge"] = float(argumenten[i + 1])
            i += 2
            continue
        if a == "--naad" and i + 1 < len(argumenten):
            opties["naad"] = argumenten[i + 1]
            i += 2
            continue
        if a == "--raster" and i + 1 < len(argumenten):
            opties["raster"] = float(argumenten[i + 1])
            i += 2
            continue
        if a == "--typen" and i + 1 < len(argumenten):
            opties["typen"] = [t for t in argumenten[i + 1].split(",") if t]
            i += 2
            continue
        if re.fullmatch(r"-?\d+(\.\d+)?", a):
            getallen.append(float(a))
        i += 1
    if len(getallen) >= 4:
        gebied = tuple(getallen[:4])
    return gebied, opties


def hoofd(argumenten):
    if "--ontdubbel" in argumenten:
        return ontdubbel()
    if "--leegmaken" in argumenten:
        return leegmaken("--ja" in argumenten)
    if "--selectie" in argumenten:
        return toon_selectie()
    if "--overlap" in argumenten:
        return controle_overlap(lees_argumenten(argumenten)[1]["raster"] or 1.0)
    if "--oppervlakken" in argumenten:
        return maak_terreinoppervlakken("--oppervlakken-bijwerken" in argumenten)
    if "--meshoppervlak-test" in argumenten:
        return test_meshoppervlak()
    if "--naadcontrole" in argumenten:
        return naadcontrole_project(lees_argumenten(argumenten)[1]["marge"])
    if "--venster-test" in argumenten:
        return test_venster()
    if "--skirt-bijwerken" in argumenten:
        opt = lees_argumenten(argumenten)[1]
        return skirt_bijwerken(opt["skirt"], opt["diepte"])
    if "--favorieten-maken" in argumenten:
        return maak_favorieten()
    if "--materialen" in argumenten:
        return pas_materialen_toe_op_bestaande()
    if "--controle-archicad" in argumenten:
        return controle_archicad(lees_argumenten(argumenten)[1]["raster"] or 0.25)
    gebied, opties = lees_argumenten(argumenten)
    if gebied is None:
        print(__doc__)
        return 1
    onbekend = [t for t in opties["typen"] if t not in OBJECT_TYPEN]
    if onbekend:
        print("Onbekend objecttype:", ", ".join(onbekend), "| bekend:", ", ".join(OBJECT_TYPEN))
        return 1
    if opties["skirt"] not in SKIRT_TYPEN:
        print("Onbekende soort bij --skirt:", opties["skirt"], "| bekend:", ", ".join(SKIRT_TYPEN))
        return 1
    if opties["controle"]:
        opties["droog"] = True
    print(f"Gebied (RD): x {gebied[0]:.0f} tot {gebied[2]:.0f}, y {gebied[1]:.0f} tot {gebied[3]:.0f}\n")

    if (gebied[2] - gebied[0]) > GROOT_GEBIED or (gebied[3] - gebied[1]) > GROOT_GEBIED:
        if opties["droog"]:
            print(f"Voor een gebied met een zijde groter dan {GROOT_GEBIED:g} m werkt --droog/--controle niet; "
                  f"kies een kleiner gebied om te controleren.")
            return 1
        return bomen_na_terrein(gebied, opties, importeer_terrein_blokken(_kaart(), gebied, opties))

    objecten, voetafdrukken = verzamel(gebied, opties["typen"], opties["bruggen"], opties["controle"],
                                       set(opties["sla_over"]))
    if not objecten:
        print("Geen terreinobjecten gevonden in dit gebied.")
        return 1

    meshes = []   # (type, mesh)
    per_object = {}
    tellers = defaultdict(Counter)
    totaal = Counter()
    problemen = []
    for o in objecten:
        X, Y, Z = o["xyz"]
        ms, st = bouw_meshes(o, X, Y, Z, opties["z"])
        per_object[o["id"]] = ms
        hl = hoogteligging_van(o.get("attributen") or {})
        for m in ms:
            HOOGTELIGGING[m["id"]] = hl
        for k, v in st.items():
            totaal[k] += v
        tellers[o["type"]]["objecten"] += 1
        tellers[o["type"]]["meshes"] += len(ms)
        tellers[o["type"]]["driehoeken"] += st["driehoeken"]
        tellers[o["type"]]["binnenpunten"] += st["binnenpunten"]
        if st["onafgemaakt"] or not ms:
            problemen.append((o["id"], o["type"], st))
        meshes += [(o["type"], m) for m in ms]
    if opties["naadsluiting"]:
        if opties["naad"] not in NAAD_BELEID:
            print("Onbekend beleid voor --naad:", opties["naad"], "| bekend:", ", ".join(NAAD_BELEID))
            return 1
        ankers = []
        if opties.get("ankers", True) and not opties["droog"]:
            try:
                ankers = lees_bestaande_ankers(_kaart(), gebied, uitsluiten={m_["id"] for _, m_ in meshes})
            except Exception as fout:
                print(f"   (de bestaande meshes konden niet worden gelezen voor de naadsluiting: {fout})")
        naad_stat = naadsluiting(meshes, opties["naad"], opties["marge"], opties["naadmax"], ankers)
    bgt_typen = Counter(str(o["attributen"].get("bgt_type") or "").strip() for o in objecten)
    bgt_typen.pop("", None)
    print(f"\n{len(objecten)} objecten omgezet naar {len(meshes)} meshes:")
    for t, c in tellers.items():
        print(f"   {t:12} {c['objecten']:4} objecten -> {c['meshes']:4} meshes, {c['driehoeken']} driehoeken, "
              f"{c['binnenpunten']} binnenpunten")
    if totaal["gat_verschoven"] or totaal["gat_raakt"]:
        print(f"   {totaal['gat_verschoven']} gatpunten raakten de buitenrand of een ander gat (Archicad weigert dat) "
              f"en zijn {GAT_UITBUIGING * 100:g} cm naar het midden van hun gat geschoven"
              + (f"; bij {totaal['gat_raakt']} punten lukte dat niet" if totaal["gat_raakt"] else ""))
    if bgt_typen:
        print("   BGT-typen in dit gebied (bgt_type): " + ", ".join(f"{k} {v}" for k, v in bgt_typen.most_common(10))
              + "  (met --sla-over sla je er een over)")
    print(f"   {totaal['gaten']} gaten, {totaal['vlak']} vlakke meshes (zonder binnenpunten), "
          f"{totaal['knijp']} knijppunten, {totaal['weggelaten']} te kleine ringen weggelaten")
    if totaal["onafgemaakt"]:
        print(f"   LET OP: {totaal['onafgemaakt']} randen konden niet tot een gesloten ring worden gemaakt")
    for pid, t, st in problemen[:5]:
        print(f"   probleem bij {t} {pid}: {st}")
    if opties["naadsluiting"]:
        toon_naadstatistiek(naad_stat, opties["naad"])
    for t, m in meshes[:2]:
        zs = [p["z"] for p in m["polygonCoordinates"]]
        print(f"   voorbeeld {t} {m['id']}: {len(m['polygonCoordinates'])} omtrekpunten, "
              f"{len(m.get('sublines', []))} binnenpunten, hoogte {min(zs):.2f} tot {max(zs):.2f}")
    extra = []
    if opties["ondergrond"]:
        ondergrond = bouw_ondergrond(objecten, gebied, opties["z"])
        extra.append(ondergrond)
        zs = [p["z"] for p in ondergrond["polygonCoordinates"]]
        print(f"   ondergrond: een mesh over het hele gebied met {len(ondergrond['sublines'])} hoogtepunten, "
              f"{ONDERGROND_DIEPTE * 100:.0f} cm onder de rest (hoekhoogtes {min(zs):.2f} tot {max(zs):.2f})")
        meshes.append(("Ondergrond", ondergrond))
    if opties["controle"]:
        controle(objecten, per_object, [], voetafdrukken, gebied, opties["raster"] or 1.0)   # de ondergrond telt niet mee
    if opties["droog"]:
        print("\nDroog-modus: er is niets aangemaakt.")
        return bomen_na_terrein(gebied, opties, 0)

    if opties["max"]:
        meshes = meshes[:opties["max"]]
        print(f"\nAlleen de eerste {len(meshes)} meshes worden aangemaakt (--max).")
    return bomen_na_terrein(gebied, opties, teken(meshes, opties))


def bomen_na_terrein(gebied, opties, rc):
    """Met --bomen: plaatst na het terrein de bomen op de BGT-vegetatiepunten (zie bomen.py)."""
    if not opties.get("bomen"):
        return rc
    try:
        import bomen
    except ImportError:
        print("\nBomen overgeslagen: bomen.py staat niet naast terrein.py.")
        return rc
    print("\n=== Bomen ===")
    r = bomen.plaats_bomen(_kaart(), gebied,
                           {"object": opties.get("boomobject") or bomen.STANDAARD_OBJECT, "max": 0,
                            "droog": bool(opties["droog"])},
                           voortgang=VOORTGANG, stop=STOP)
    return rc if rc else (0 if (r["gelukt"] or opties["droog"] or not r["punten"]) else 1)


# ---------------------------------------------------------------- Archicad


def bestaande_ids(k, lagen):
    """{element-id: [elementen]} van de meshes die op een van de gegeven lagen staan."""
    r = k.tapir("GetElementsByType", {"elementType": "Mesh"})
    elementen = k.pak(r).get("elements", [])
    ids = defaultdict(list)
    for i in range(0, len(elementen), 200):
        blok = elementen[i:i + 200]
        d = k.tapir("GetDetailsOfElements", {"elements": blok, "withDetails": False})
        for e, it in zip(blok, k.pak(d).get("detailsOfElements", [])):
            if isinstance(it, dict) and it.get("layerIndex") in lagen and it.get("id"):
                ids[it["id"]].append(e)
    return ids


def ontdubbel():
    kaart = _kaart()

    kaart.MAPNAAM = MAP
    lagen = {kaart.zorg_voor_laag(naam) for naam in ALLE_LAGEN.values()}
    ids = bestaande_ids(kaart, lagen)
    te_verwijderen = [e for lijst in ids.values() for e in lijst[1:]]
    print(f"{sum(len(v) for v in ids.values())} meshes op de terreinlagen, {len(ids)} verschillende ID's, "
          f"{sum(1 for v in ids.values() if len(v) > 1)} komen dubbel voor.")
    if not te_verwijderen:
        print("Niets te verwijderen.")
        return 0
    r = kaart.tapir("DeleteElements", {"elements": te_verwijderen})
    print(f"{len(te_verwijderen)} dubbele meshes verwijderd:", "gelukt" if r.get("succeeded") else str(r)[:200])
    return 0


def leegmaken(zonder_vraag=False):
    """Verwijdert alle meshes op de vier terreinlagen, welk Element-ID ze ook hebben."""
    kaart = _kaart()

    kaart.MAPNAAM = MAP
    lagen = {kaart.zorg_voor_laag(naam) for naam in ALLE_LAGEN.values()}
    r = kaart.tapir("GetElementsByType", {"elementType": "Mesh"})
    elementen = kaart.pak(r).get("elements", [])
    te_verwijderen = []
    for i in range(0, len(elementen), 200):
        blok = elementen[i:i + 200]
        d = kaart.tapir("GetDetailsOfElements", {"elements": blok, "withDetails": False})
        for e, it in zip(blok, kaart.pak(d).get("detailsOfElements", [])):
            if isinstance(it, dict) and it.get("layerIndex") in lagen:
                te_verwijderen.append(e)
    print(f"{len(elementen)} meshes in het project, waarvan {len(te_verwijderen)} op de terreinlagen "
          f"({', '.join(ALLE_LAGEN.values())}).")
    if not te_verwijderen:
        print("Niets te verwijderen.")
        return 0
    if not zonder_vraag:
        antwoord = input(f"Typ JA om deze {len(te_verwijderen)} meshes te verwijderen: ")
        if antwoord.strip().upper() != "JA":
            print("Afgebroken, er is niets verwijderd.")
            return 1
    r = kaart.tapir("DeleteElements", {"elements": te_verwijderen})
    print(f"{len(te_verwijderen)} meshes verwijderd:", "gelukt" if r.get("succeeded") else str(r)[:200])
    return 0


def actief_venster(k):
    """Het actieve venster van Archicad als tekst, of None als dat niet te lezen is."""
    try:
        r = k.tapir("GetCurrentWindowType")
        if r.get("succeeded"):
            return json.dumps(k.pak(r), ensure_ascii=False)
    except Exception:
        pass
    return None


def venster_is_plattegrond(tekst):
    """True/False als het type te herkennen is, anders None."""
    if not tekst:
        return None
    t = tekst.lower().replace(" ", "").replace("_", "")
    if "floorplan" in t or "plattegrond" in t:
        return True
    if "3d" in t or "model" in t:
        return False
    return None


def diagnose_mesh_aanmaken(kaart, mesh):
    """Probeert een paar eenvoudige meshes aan te maken om te zien of Archicad meshes uberhaupt accepteert,
    en ruimt ze weer op. Wordt gebruikt als alle meshes mislukken."""
    p0 = mesh["polygonCoordinates"][0]
    x0, y0, z0 = p0["x"], p0["y"], p0["z"]
    vierkant = [{"x": x0, "y": y0, "z": z0}, {"x": x0 + 3, "y": y0, "z": z0},
                {"x": x0 + 3, "y": y0 + 3, "z": z0}, {"x": x0, "y": y0 + 3, "z": z0}]
    proeven = [
        ("een vierkant van 3 x 3 m, alleen de omtrek", {"polygonCoordinates": vierkant}),
        ("hetzelfde met level, floorIndex en skirtType", {"polygonCoordinates": vierkant, "level": 0,
                                                          "floorIndex": 0, "skirtType": "SurfaceOnlyWithoutSkirt"}),
        ("de omtrek van de eerste echte mesh, zonder rest", {"polygonCoordinates": mesh["polygonCoordinates"]}),
    ]
    aangemaakt = []
    print("   Diagnose: Archicad accepteert de volgende eenvoudige meshes:")
    try:
        for naam, item in proeven:
            r = kaart.tapir("CreateMeshes", {"meshesData": [item]})
            e = (kaart.pak(r).get("elements") or [{}])[0] if r.get("succeeded") else {}
            if "elementId" in e:
                aangemaakt.append(e)
                print(f"      GELUKT: {naam}")
            else:
                print(f"      mislukt: {naam}: {str(e.get('error', r.get('error', r)))[:150]}")
    finally:
        if aangemaakt:
            kaart.tapir("DeleteElements", {"elements": aangemaakt})


def mesh_zmin(m):
    """Het laagste punt van een mesh (omtrek, gaten en extra punten)."""
    zs = [p["z"] for p in m["polygonCoordinates"]]
    for h in m.get("holes", []):
        zs += [p["z"] for p in h["polygonCoordinates"]]
    for sl in m.get("sublines", []):
        zs += [p["z"] for p in sl["coordinates"]]
    return min(zs)


# Hoe kan skirtLevel werken? Per model: de onderkant bij skirtLevel s en laagste punt zmin, en het skirtLevel voor een
# gewenste onderkant.
SKIRT_MODELLEN = {
    # zo werkt het in Archicad: skirtLevel is een diepte onder het referentievlak (level, hier 0), dus
    # onderkant = level - skirtLevel en voor een onderkant op +32 m heb je een skirtLevel van -32 nodig
    "een diepte onder het referentievlak (level)": (lambda s, zmin: -s, lambda zmin, doel: -doel),
    "een absolute hoogte": (lambda s, zmin: s, lambda zmin, doel: doel),
    "een diepte onder het laagste punt": (lambda s, zmin: zmin - s, lambda zmin, doel: zmin - doel),
    "een hoogte ten opzichte van het laagste punt": (lambda s, zmin: zmin + s, lambda zmin, doel: doel - zmin),
}


def kies_skirtmodel(metingen, z):
    """metingen: lijst (skirtLevel, onderkant). Geeft (naam, functie voor skirtLevel) of None."""
    informatief = [(s_, onder) for s_, onder in metingen if onder < z - 0.001]      # alleen waar een skirt ontstond
    if len(informatief) < 2:
        return None
    for naam, (onderkant, niveau) in SKIRT_MODELLEN.items():
        if all(abs(onderkant(s_, z) - onder) < 0.01 for s_, onder in informatief):
            return naam, niveau
    return None


def kalibreer_skirt(k, skirt_type, z=50.0):
    """Maakt tijdelijke testmeshes met verschillende skirtLevel-waarden, leest de onderkant van hun lichaam terug en
    leidt af hoe skirtLevel werkt. Geeft (naam, functie) of None. De testmeshes worden altijd verwijderd."""
    if getattr(k, "SKIRT_BEKEND", False):
        naam, (_onderkant, niveau) = next(iter(SKIRT_MODELLEN.items()))
        print(f"   skirtLevel is {naam} (vast model van de add-on, geen ijking nodig).")
        return naam, niveau
    x0, y0 = 1000.0, 1000.0
    vierkant = [{"x": x0, "y": y0, "z": z}, {"x": x0 + 4, "y": y0, "z": z},
                {"x": x0 + 4, "y": y0 + 4, "z": z}, {"x": x0, "y": y0 + 4, "z": z}]
    metingen, aangemaakt = [], []
    try:
        for s_ in (0.5, 2.0, 5.0, -1.0, -2.0, -5.0):
            r = k.tapir("CreateMeshes", {"meshesData": [{
                "polygonCoordinates": vierkant, "level": 0, "floorIndex": 0,
                "skirtType": skirt_type, "skirtLevel": s_}]})
            e = (k.pak(r).get("elements") or [{}])[0] if r.get("succeeded") else {}
            if "elementId" not in e:
                continue
            aangemaakt.append(e)
            g = k.pak(k.tapir("Get3DGeometryOfElements", {"elements": [e]}))
            zs = [v["z"] for geo in g.get("geometries3D", []) for b in geo.get("bodies", [])
                  for v in b.get("vertices", [])]
            if zs:
                metingen.append((s_, min(zs)))
    finally:
        if aangemaakt:
            k.tapir("DeleteElements", {"elements": aangemaakt})
    resultaat = kies_skirtmodel(metingen, z)
    print("   ijking: " + (", ".join(f"skirtLevel {s_:g} -> onderkant {o:.2f}" for s_, o in metingen) or "geen metingen"))
    if resultaat:
        print(f"   skirtLevel blijkt {resultaat[0]} te zijn.")
    return resultaat


def skirt_bijwerken(skirt="volume", diepte=STANDAARD_DIEPTE):
    """Zet de soort mesh (volume, zijvlakken of oppervlak) en de diepte ook bij de meshes die er al staan."""
    k = _kaart()
    skirt_type = SKIRT_TYPEN[skirt]
    per_type = terreinmeshes_per_type(k)
    if not per_type:
        print("Er zijn geen terreinmeshes in dit project.")
        return 1
    meshes = [(e, it) for lijst in per_type.values() for e, it in lijst]

    def zmin_van(it):
        det = it.get("details") or {}
        zs = [p["z"] for p in det.get("polygonCoordinates") or [] if "z" in p]
        for h in det.get("holes") or []:
            zs += [p["z"] for p in (h.get("polygonCoordinates") if isinstance(h, dict) else h) or [] if "z" in p]
        return min(zs) if zs else None

    zmins = [zmin_van(it) for _, it in meshes]
    bekend = [z for z in zmins if z is not None]
    if not bekend:
        print("De hoogtes van de meshes zijn niet te lezen.")
        return 1
    onderkant = min(bekend) - diepte
    niveau = None
    if skirt_type != "SurfaceOnlyWithoutSkirt":
        print("Skirt ijken met tijdelijke testmeshes...")
        model = kalibreer_skirt(k, skirt_type)
        if model is None:
            print("De ijking mislukte; er is niets aangepast.")
            return 1
        niveau = model[1]

    def meshdata(zmin):
        d = {"skirtType": skirt_type}
        if niveau and zmin is not None:
            d["skirtLevel"] = round(niveau(zmin, onderkant), 3)
        return d

    proef_e, proef_it = meshes[0]
    k.tapir("ModifyMeshes", {"meshesData": [{"elementId": proef_e["elementId"],
                                              "meshData": meshdata(zmin_van(proef_it))}]})
    det = k.pak(k.tapir("GetDetailsOfElements", {"elements": [proef_e]})).get("detailsOfElements", [{}])[0]
    huidig = (det.get("details") or {}).get("skirtType")
    if huidig != skirt_type:
        print(f"ModifyMeshes kan de soort mesh in deze Tapir niet wijzigen (nu {huidig!r}). Maak de terreinlagen leeg "
              f"met 'python terrein.py --leegmaken' en importeer opnieuw; nieuwe meshes krijgen de soort wel mee.")
        return 1
    for i in range(0, len(meshes), 50):
        blok = meshes[i:i + 50]
        k.tapir("ModifyMeshes", {"meshesData": [
            {"elementId": e["elementId"], "meshData": meshdata(zmin_van(it))} for e, it in blok]})
    print(f"{len(meshes)} meshes ingesteld op '{skirt}' ({skirt_type}), met de onderkant op "
          f"{onderkant:.2f} m ({diepte:g} m onder het laagste punt).")
    return 0


def aantal_punten(mesh):
    return (len(mesh["polygonCoordinates"]) + len(mesh.get("sublines", []))
            + sum(len(h["polygonCoordinates"]) for h in mesh.get("holes", [])))


def teken(meshes, opties):
    """Maakt de meshes aan in het venster dat actief is (dat werkt ook in een 3D-venster). Mislukken alle meshes,
    dan probeert het de plattegrond: het wisselt erheen, probeert het opnieuw en zet daarna het venster terug."""
    kaart = _kaart()
    wissel = getattr(kaart, "PlattegrondActief", None)
    rc = _teken(meshes, dict(opties, _eerste_poging=wissel is not None))
    if wissel is not None and LAATSTE["gelukt"] == 0 and LAATSTE["mislukt"] > 0 \
            and venster_is_plattegrond(actief_venster(kaart)) is not True:
        print("\nHet aanmaken mislukte in het actieve venster; ik probeer het opnieuw in de plattegrond.")
        with wissel():
            rc = _teken(meshes, opties)
    return rc


def _teken(meshes, opties):
    kaart = _kaart()

    kaart.MAPNAAM = MAP
    gebruikte = {t for t, _ in meshes}
    bestaande_lagen = kaart.alle_lagen()
    laag_van = {}                 # lagen waarop we meshes aanmaken (worden zo nodig aangemaakt)
    controle_lagen = set()        # lagen waarop we bestaande meshes zoeken
    for t, naam in ALLE_LAGEN.items():
        if t in gebruikte or t in TYPEN:
            laag_van[t] = kaart.zorg_voor_laag(naam)
            controle_lagen.add(laag_van[t])
        elif naam in bestaande_lagen:
            controle_lagen.add(bestaande_lagen[naam]["index"])
    print("\nLagen: " + ", ".join(f"{ALLE_LAGEN[t]} ({laag_van[t]})" for t in laag_van))
    run = opties.get("_run")
    if not opties["forceer"]:
        try:
            aanwezig = run["ids"] if run is not None else bestaande_ids(kaart, controle_lagen)
        except Exception as fout:
            aanwezig = {}
            print("Controle op bestaande meshes mislukt:", fout)
        over = [(t, m) for t, m in meshes if m["id"] not in aanwezig]
        if len(over) < len(meshes):
            print(f"{len(meshes) - len(over)} meshes staan al op de terreinlagen en worden overgeslagen "
                  f"(met --forceer maak je ze toch aan).")
        meshes = over
        if not meshes:
            print("Er is niets nieuws om aan te maken.")
            LAATSTE.update(gelukt=0, mislukt=0)
            return 0

    for t_, m_ in meshes:
        m_["_type"] = t_
    # de oppervlakken van de terreintypen bestaan al (of worden nu aangemaakt) en worden bij het aanmaken meegegeven
    type_van_id = {m_["id"]: t_ for t_, m_ in meshes}
    if run is not None and run.get("direct") is not None:
        direct = run["direct"]
    else:
        direct = {"aan": False, "guid": {}, "geweigerd": False, "bm": {}, "bm_aan": False, "bm_geprobeerd": False}
        if opties.get("materialen", True):
            opp = D.zorg_voor_oppervlakken(kaart, False, TERREIN_OPPERVLAKKEN)
            if opp:
                direct["guid"] = {typ: v["guid"] for typ, v in opp.items()}
                direct["aan"] = True
        if run is not None:
            run["direct"] = direct

    skirt_type = SKIRT_TYPEN.get(opties.get("skirt", STANDAARD_SKIRT), "SurfaceOnlyWithoutSkirt")
    skirt_model = None
    onderkant = None
    if run is not None and run.get("skirt") is not None:
        skirt_type, skirt_model = run["skirt"]          # al geijkt bij een eerder blok
    elif skirt_type != "SurfaceOnlyWithoutSkirt":
        print(f"\nSkirt ('{opties.get('skirt', STANDAARD_SKIRT)}') ijken met tijdelijke testmeshes...")
        try:
            skirt_model = kalibreer_skirt(kaart, skirt_type)
        except Exception as fout_:
            print(f"   De ijking gaf een fout ({fout_}).")
            skirt_model = None
        if skirt_model is None:
            print("   De ijking mislukte; de meshes worden zonder skirt aangemaakt (alleen het bovenvlak).")
            skirt_type = "SurfaceOnlyWithoutSkirt"
    if run is not None and run.get("skirt") is None:
        run["skirt"] = (skirt_type, skirt_model)
    dekken = set()
    if skirt_type != "SurfaceOnlyWithoutSkirt" and opties.get("dekken", True):
        dekken, n_bron, n_overlap = bepaal_dekken(meshes)
        if dekken:
            print(f"\n{len(dekken)} meshes herkend als viaduct of brugdek ({n_bron} volgens de bron, {n_overlap} doordat ze boven een ander "
                  f"object liggen); die krijgen een dunne onderkant van {opties.get('dekdikte', DEK_DIKTE):g} m.")
    if skirt_model:
        onderkant = min(mesh_zmin(m_) for _, m_ in meshes) - opties.get("diepte", STANDAARD_DIEPTE)
        if run is None:
            print(f"   onderkant van het terrein: {onderkant:.2f} m "
                  f"({opties.get('diepte', STANDAARD_DIEPTE):g} m onder het laagste punt)")

    def item(m, zonder_punten=False, zonder_gaten=False, oorspronkelijk=False):
        bron = m["_oorspronkelijk"] if oorspronkelijk and m.get("_oorspronkelijk") else m
        d = {"polygonCoordinates": bron["polygonCoordinates"], "level": 0, "floorIndex": 0,
             "skirtType": skirt_type, "id": m["id"], "showLines": bool(opties["lijnen"])}
        if skirt_model:
            doel = (mesh_zmin(bron) - opties.get("dekdikte", DEK_DIKTE)) if m["id"] in dekken else onderkant
            d["skirtLevel"] = round(skirt_model[1](mesh_zmin(bron), doel), 3)
        if bron.get("holes") and not zonder_gaten:
            d["holes"] = bron["holes"]
        if m.get("sublines") and not zonder_punten:
            d["sublines"] = m["sublines"]
        guid = direct["guid"].get(m.get("_type"))
        if direct["aan"] and guid:
            d.update(oppervlak_velden(guid))
        elif direct["bm_aan"] and direct["bm"].get(m.get("_type")):
            d["buildingMaterialId"] = direct["bm"][m["_type"]]
        return d

    venster = actief_venster(kaart)
    if venster:
        print(f"Actief venster in Archicad: {venster}")
    zonder_gaten_ids = []
    gelukt = mislukt = zonder_punten_n = zonder_gaten_n = zonder_naad_n = 0
    gemaakt = []   # (type, element, element-id)
    mislukte = []

    losse = [0]    # aantal door Archicad half aangemaakte meshes dat we hebben opgeruimd

    def alle_mesh_guids():
        r_ = kaart.tapir("GetElementsByType", {"elementType": "Mesh"})
        return {e["elementId"]["guid"] for e in kaart.pak(r_).get("elements", []) if "elementId" in e}

    def maak(batch):
        """Maakt meshes aan. Een mesh die Archicad half heeft aangemaakt maar als fout meldt, wordt direct
        verwijderd, zodat een tweede poging geen dubbele mesh oplevert."""
        bekend = run["guids"] if run is not None else None
        voor = None
        if bekend is None:
            try:
                voor = alle_mesh_guids()
            except Exception:
                voor = None
        r = kaart.tapir("CreateMeshes", {"meshesData": batch})
        tekst_r = json.dumps(r)
        if (not r.get("succeeded")) and direct["aan"] and "additionalProperties" in tekst_r and "Material" in tekst_r:
            # deze Tapir kent het oppervlak bij het aanmaken van een mesh nog niet: zonder opnieuw proberen
            direct["aan"] = False
            direct["geweigerd"] = True
            for it_ in batch:
                for veld in MESH_OPPERVLAK_VELDEN:
                    it_.pop(veld, None)
            if not direct["bm_geprobeerd"]:
                direct["bm_geprobeerd"] = True
                print("   De Tapir kent topMaterial niet; ik koppel de meshes aan een bouwmateriaal met het goede oppervlak.")
                try:
                    direct["bm"] = zorg_voor_bouwmaterialen(kaart, set(direct["guid"]))
                    direct["bm_aan"] = bool(direct["bm"])
                except Exception as fout_:
                    print("   bouwmaterialen aanmaken mislukt:", fout_)
            if direct["bm_aan"]:
                for it_ in batch:
                    bm_ = direct["bm"].get(type_van_id.get(it_.get("id")))
                    if bm_:
                        it_["buildingMaterialId"] = bm_
            r = kaart.tapir("CreateMeshes", {"meshesData": batch})
        elementen = kaart.pak(r).get("elements", []) if r.get("succeeded") else None
        if bekend is not None:
            # in een grote run lezen we niet bij elke batch alle meshes: alleen als er iets misging
            gelukt_ = {e["elementId"]["guid"] for e in (elementen or []) if "elementId" in e}
            if elementen is None or len(gelukt_) < len(batch):
                try:
                    nu = alle_mesh_guids()
                    over = nu - bekend - gelukt_
                    if over:
                        kaart.tapir("DeleteElements", {"elements": [{"elementId": {"guid": g}} for g in sorted(over)]})
                        losse[0] += len(over)
                        nu -= over
                    bekend |= nu
                except Exception:
                    pass
            bekend |= gelukt_
        elif voor is not None:
            try:
                gelukt_ = {e["elementId"]["guid"] for e in (elementen or []) if "elementId" in e}
                over = alle_mesh_guids() - voor - gelukt_
                if over:
                    kaart.tapir("DeleteElements", {"elements": [{"elementId": {"guid": g}} for g in sorted(over)]})
                    losse[0] += len(over)
            except Exception:
                pass
        return elementen, r

    # batches met een maximum aantal punten per aanroep
    batches, huidig, punten = [], [], 0
    for t, m in meshes:
        n = aantal_punten(m)
        if huidig and (punten + n > MAX_PUNTEN_PER_AANROEP or len(huidig) >= 25):
            batches.append(huidig)
            huidig, punten = [], 0
        huidig.append((t, m))
        punten += n
    if huidig:
        batches.append(huidig)

    for deel in batches:
        elementen, r = maak([item(m) for _, m in deel])
        if elementen is None:
            print("CreateMeshes fout:", str(r)[:400])
            mislukt += len(deel)
            mislukte += [m["id"] for _, m in deel]
            continue
        if deel is batches[0] and len(deel) >= 3 and all("elementId" not in e for e in elementen):
            codes = {str((e.get("error") or {}).get("code")) for e in elementen}
            if len(codes) == 1:
                print(f"\nAlle {len(deel)} meshes van de eerste aanroep mislukten met dezelfde fout "
                      f"({str(elementen[0].get('error'))[:140]}). Verder proberen heeft geen zin.")
                if not opties.get("_eerste_poging"):
                    diagnose_mesh_aanmaken(kaart, deel[0][1])
                    print("   Houdt dit aan, plak dan deze uitvoer; mogelijk ligt het aan dit project.")
                mislukt += len(meshes)
                LAATSTE.update(gelukt=0, mislukt=mislukt)
                return 1
        for (t, m), e in zip(deel, elementen):
            if "elementId" in e:
                gelukt += 1
                gemaakt.append((t, e, m["id"]))
                continue
            fout = str(e.get("error", e))[:160]
            klaar = False
            for variant, naam in ((dict(oorspronkelijk=True), "met de oorspronkelijke omtrek (zonder naadsluiting)"),
                                  (dict(oorspronkelijk=True, zonder_punten=True), "oorspronkelijke omtrek zonder binnenpunten"),
                                  (dict(zonder_punten=True), "zonder binnenpunten"),
                                  (dict(zonder_punten=True, zonder_gaten=True), "zonder binnenpunten en gaten")):
                els, _ = maak([item(m, **variant)])
                if els and "elementId" in els[0]:
                    gelukt += 1
                    gemaakt.append((t, els[0], m["id"]))
                    if variant.get("oorspronkelijk"):
                        zonder_naad_n += 1
                    elif "zonder_gaten" in variant:
                        zonder_gaten_n += 1
                        zonder_gaten_ids.append(m["id"])
                    else:
                        zonder_punten_n += 1
                    if zonder_naad_n + zonder_punten_n + zonder_gaten_n <= 3:
                        print(f"   mesh {m['id']} werd geweigerd en is gemaakt {naam}")
                    klaar = True
                    break
            if not klaar:
                mislukt += 1
                mislukte.append(m["id"])
                if len(mislukte) <= 3:
                    print(f"   mesh {m['id']} mislukt: {fout}")

    # Laag en Element-ID instellen: CreateMeshes heeft geen laagparameter en het ID komt niet altijd aan.
    ingesteld = 0
    for i in range(0, len(gemaakt), 100):
        blok = gemaakt[i:i + 100]
        r = kaart.tapir("SetDetailsOfElements", {"elementsWithDetails": [
            {"elementId": e["elementId"], "details": {"layerIndex": laag_van[t], "id": mid}}
            for t, e, mid in blok]})
        if r.get("succeeded"):
            ingesteld += len(blok)
        else:
            print("Laag en ID instellen mislukt:", str(r)[:300])
    if run is not None and run.get("ids") is not None:
        for t_, e_, mid_ in gemaakt:
            run["ids"].add(mid_)
            run["objecten"].update((mid_, basis_id(mid_)))
    # oppervlakken: zijn ze bij het aanmaken toegekend? Zo niet, dan via de favorieten (als die er zijn)
    if gemaakt and opties.get("materialen", True) and getattr(kaart, "ADDON", False):
        if direct["guid"]:
            typen_gemaakt = sorted({t for t, _, _ in gemaakt if t in TERREIN_OPPERVLAKKEN})
            print("Oppervlakken direct bij het aanmaken toegekend: " + ", ".join(favorietnaam(t) for t in typen_gemaakt))
    elif gemaakt and opties.get("materialen", True):
        typen_gemaakt = sorted({t for t, _, _ in gemaakt if t in TERREIN_OPPERVLAKKEN})
        direct_ok = set()
        if direct["guid"] and (not direct["geweigerd"] or direct["bm_aan"]):
            for typ in typen_gemaakt:
                voorbeeld = next(e for t, e, _ in gemaakt if t == typ)
                tel = oppervlakken_van_mesh(kaart, voorbeeld)
                if tel and set(tel) == {direct["guid"].get(typ)}:
                    direct_ok.add(typ)
            if direct_ok:
                route = "via het bouwmateriaal" if direct["bm_aan"] else "direct bij het aanmaken"
                print(f"Oppervlakken {route} toegekend: " + ", ".join(favorietnaam(t) for t in sorted(direct_ok)))
        rest = [t for t in typen_gemaakt if t not in direct_ok]
        if rest:
            if direct["geweigerd"] and direct["bm_aan"]:
                print("   LET OP: de meshes zijn aan een bouwmateriaal gekoppeld, maar hun oppervlak is niet "
                      "veranderd voor " + ", ".join(favorietnaam(t) for t in rest)
                      + ". Het bouwmateriaal bepaalt het oppervlak van een mesh hier dus niet.")
            elif direct["geweigerd"]:
                print("   Deze versie van Tapir kan het oppervlak nog niet bij het aanmaken van een mesh instellen "
                      "(CreateMeshes kent topMaterial niet) en de bouwmaterialen konden niet worden gemaakt.")
            elif direct["guid"]:
                print("   LET OP: Archicad meldde succes, maar het oppervlak van " + ", ".join(
                    favorietnaam(t) for t in rest) + " is niet veranderd. Deze Tapir negeert het veld waarschijnlijk.")
            per_type_nieuw = defaultdict(list)
            for t, e, mid in gemaakt:
                if t in rest:
                    per_type_nieuw[t].append((e, laag_van[t], mid))
            try:
                gedaan = pas_favorieten_toe(kaart, per_type_nieuw)
                if gedaan:
                    print("Oppervlakken toegekend via favorieten: " + ", ".join(
                        f"{n} {favorietnaam(t)}" for t, n in gedaan.items()))
            except Exception as fout:
                print("Oppervlakken toekennen via favorieten mislukt:", fout)
    # controle van de onderkant: ligt het volume echt waar we het hebben gevraagd?
    if gemaakt and skirt_model:
        try:
            voorbeeld = gemaakt[0][1]
            g_ = kaart.pak(kaart.tapir("Get3DGeometryOfElements", {"elements": [voorbeeld]}))
            zs_ = [v["z"] for geo in g_.get("geometries3D", []) for b_ in geo.get("bodies", [])
                   for v in b_.get("vertices", [])]
            if zs_:
                laagste = min(zs_)
                if abs(laagste - onderkant) < 0.05:
                    print(f"Onderkant gecontroleerd bij een voorbeeld: {laagste:.2f} m (gevraagd {onderkant:.2f} m).")
                else:
                    print(f"   LET OP: de onderkant van een voorbeeldmesh ligt op {laagste:.2f} m, terwijl "
                          f"{onderkant:.2f} m was gevraagd.")
        except Exception as fout:
            print("Onderkant controleren mislukt:", fout)
    # controle: staan de ID's er nu echt?
    if gemaakt:
        proef = gemaakt[:5]
        d = kaart.tapir("GetDetailsOfElements", {"elements": [e for _, e, _ in proef]})
        details = kaart.pak(d).get("detailsOfElements", [])
        goed = sum(1 for (_, _, mid), it in zip(proef, details) if isinstance(it, dict) and it.get("id") == mid)
        print(f"Controle: bij {goed} van de {len(proef)} gecontroleerde meshes staat het verwachte Element-ID.")
    print(f"\n{gelukt} meshes aangemaakt, {mislukt} mislukt; {ingesteld} op hun laag gezet.")
    if zonder_naad_n:
        print(f"   {zonder_naad_n} meshes met hun oorspronkelijke omtrek, zonder naadsluiting "
              f"(Archicad weigerde de omtrek met naadpunten)")
    if zonder_gaten_ids:
        print(f"   LET OP: deze meshes zijn ZONDER hun gaten gemaakt en kunnen daardoor over andere meshes heen "
              f"liggen: {', '.join(zonder_gaten_ids[:10])}" + (" ..." if len(zonder_gaten_ids) > 10 else ""))
    if zonder_punten_n or zonder_gaten_n:
        print(f"   {zonder_punten_n} meshes zonder binnenpunten en {zonder_gaten_n} zonder binnenpunten en gaten "
              f"(Archicad weigerde de volledige vorm)")
    if mislukte:
        print("Mislukte meshes (eerste 10):", ", ".join(mislukte[:10]))
    if losse[0]:
        print(f"   {losse[0]} meshes die Archicad half had aangemaakt, maar als fout meldde, zijn weer "
              f"verwijderd (zo ontstaan er geen dubbelen).")
    LAATSTE.update(gelukt=gelukt, mislukt=mislukt)
    return 0 if gelukt else 1


def diagnose_dekking(k, gebied):
    """Vergelijkt het terrein in Archicad met de bron (de 3D Basisvoorziening) voor het gebied en meldt wat ontbreekt of
    afwijkt. Zo zie je of er meshes zijn overgeslagen, afgeknipt of niet gelukt. k is de kaart-module."""
    global KAART
    KAART = k
    k.MAPNAAM = MAP
    print(f"Terreincontrole voor het gebied x {gebied[0]:.0f} tot {gebied[2]:.0f}, y {gebied[1]:.0f} tot {gebied[3]:.0f}\n")
    objecten, _ = verzamel(gebied, list(OBJECT_TYPEN), True)
    brug = [o for o in objecten if (o["attributen"] or {}).get("hoortbijbrug")]
    gewone = [o for o in objecten if not (o["attributen"] or {}).get("hoortbijbrug")]
    meshes, _stat = bouw_alle_meshes(gewone, {"z": 0.0})
    # welke eigenschappen heeft de bron? (zo zien we onder welke naam bijvoorbeeld de hoogteligging staat)
    sleutels = defaultdict(Counter)
    for o in objecten:
        for sl, w in (o["attributen"] or {}).items():
            sleutels[sl][str(w)[:40]] += 1
    print("Eigenschappen van de terreinobjecten in de bron:")
    for sl in sorted(sleutels):
        waarden = sleutels[sl]
        if len(waarden) <= 8:
            print(f"   {sl}: " + ", ".join(f"{w} ({n})" for w, n in waarden.most_common()))
        else:
            print(f"   {sl}: {len(waarden)} verschillende waarden")
    dekken, n_bron, n_overlap = bepaal_dekken(meshes)
    print(f"Viaducten of brugdekken: {len(dekken)} meshes ({n_bron} volgens de eigenschappen, {n_overlap} doordat ze boven een ander object liggen).\n")
    verwacht = defaultdict(lambda: {"opp": 0.0, "n": 0, "type": "", "punten": []})
    for typ, m in meshes:
        b = verwacht[basis_id(m["id"])]
        b["type"] = typ
        b["n"] += 1
        buiten = ring_xy(m["polygonCoordinates"])
        b["opp"] += abs(vorm_oppervlak(buiten)) - sum(abs(vorm_oppervlak(g)) for g in gaten_uit_details({"holes": m.get("holes", [])}))
        b["punten"] += buiten
    at = {basis_id(o["id"]): (o["attributen"] or {}) for o in gewone}
    print(f"Bron: {len(objecten)} terreinobjecten raken het gebied; {len(brug)} daarvan horen bij een brug en worden "
          f"standaard niet geimporteerd.")
    # wat staat er in Archicad?
    aanwezig = defaultdict(lambda: {"opp": 0.0, "n": 0})
    per_type = terreinmeshes_per_type(k)
    totaal_ac = 0
    for typ, lijst in per_type.items():
        for e, it in lijst:
            totaal_ac += 1
            m = mesh_uit_details(it)
            if not m:
                continue
            a = aanwezig[basis_id(it.get("id") or "")]
            a["n"] += 1
            a["opp"] += abs(vorm_oppervlak(ring_xy(m["polygonCoordinates"]))) - sum(
                abs(vorm_oppervlak(ring_xy(h["polygonCoordinates"]))) for h in m["holes"])
    print(f"Archicad: {totaal_ac} meshes op de terreinlagen.\n")
    ontbreekt = [(i, b) for i, b in verwacht.items() if i not in aanwezig]
    afwijkend = [(i, b, aanwezig[i]) for i, b in verwacht.items()
                 if i in aanwezig and abs(aanwezig[i]["opp"] - b["opp"]) > max(0.5, 0.01 * b["opp"])]
    print(f"Ontbrekend in Archicad: {len(ontbreekt)} objecten ({sum(b['opp'] for _, b in ontbreekt):.0f} m2).")
    per = defaultdict(lambda: [0, 0.0])
    for _, b in ontbreekt:
        per[b["type"]][0] += 1
        per[b["type"]][1] += b["opp"]
    for typ, (n, opp) in sorted(per.items()):
        print(f"   {typ}: {n} objecten, {opp:.0f} m2")
    for i, b in sorted(ontbreekt, key=lambda x: -x[1]["opp"])[:8]:
        xs = [p[0] for p in b["punten"]]
        ys = [p[1] for p in b["punten"]]
        print(f"   {i} ({b['type']}, {at.get(i, {}).get('bgt_type') or '-'}): {b['opp']:.0f} m2 rond "
              f"({(min(xs) + max(xs)) / 2:.0f}, {(min(ys) + max(ys)) / 2:.0f})")
    print(f"\nAfwijkende vorm (oppervlakte in Archicad wijkt meer dan 1% af van de bron): {len(afwijkend)} objecten.")
    for i, b, a in sorted(afwijkend, key=lambda x: -abs(x[1]["opp"] - x[2]["opp"]))[:8]:
        print(f"   {i}: bron {b['opp']:.0f} m2, Archicad {a['opp']:.0f} m2 "
              f"({'afgeknipt bij een eerdere import?' if a['opp'] < b['opp'] else 'groter dan de bron'})")
    dubbel = [i for i, a in aanwezig.items() if a["n"] > (verwacht[i]["n"] if i in verwacht else 1)]
    if dubbel:
        print(f"\nLET OP: {len(dubbel)} objecten staan dubbel in Archicad (bijvoorbeeld {', '.join(dubbel[:3])}).")
    print("\nBeoordeling: " + ("het terrein in dit gebied is compleet." if not ontbreekt and not afwijkend else
          "er ontbreekt of wijkt iets af. Wis het terrein (knop 'Terrein wissen') en importeer het gebied opnieuw."))
    return 0


def wis_terrein(k):
    """Verwijdert alle meshes op de terreinlagen (voor het kaartvenster)."""
    global KAART
    KAART = k
    return leegmaken(zonder_vraag=True)


def importeer_terrein(k, gebied, oppervlakken=True, naadsluiting=True, sla_over=(), skirt=None, diepte=None, dekken=True):
    """Voor het kaartvenster: haalt het terrein voor het gebied (xmin, ymin, xmax, ymax in RD) op en maakt het
    aan als Meshes. naadsluiting zet de naadsluiting aan of uit; sla_over is een lijst BGT-typen (bgt_type) die
    worden overgeslagen. Maakt ook de terreinoppervlakken aan. k is de kaart-module.
    Geeft het aantal aangemaakte meshes terug."""
    global KAART
    KAART = k
    LAATSTE.update(gelukt=0, mislukt=0)
    argumenten = [str(float(x)) for x in gebied]
    if not naadsluiting:
        argumenten.append("--geen-naadsluiting")
    for soort in sla_over:
        if str(soort).strip():
            argumenten += ["--sla-over", str(soort).strip()]
    if not oppervlakken:
        argumenten.append("--zonder-materiaal")
    if not dekken:
        argumenten.append("--geen-dekken")
    if skirt in SKIRT_TYPEN:
        argumenten += ["--skirt", str(skirt)]
    try:
        if diepte is not None and float(diepte) > 0:
            argumenten += ["--diepte", str(float(diepte))]
    except (TypeError, ValueError):
        pass
    hoofd(argumenten)
    return LAATSTE["gelukt"]


if __name__ == "__main__":
    sys.exit(hoofd(sys.argv[1:]))
