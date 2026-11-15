"""Stijlen per soort: een kleur (voor de 2D-vulling) en een naam (voor het 3D-oppervlak) op grond van de BGT-eigenschappen
functie, fysiek voorkomen en plus-fysiek voorkomen.

Er is een tabel met regels. Een regel heeft een naam, een kleur en voorwaarden:

    {"naam": "weg_asfalt", "kleur": [88, 88, 94], "laag": "wegdeel", "functie": "rijbaan", "plus": "asfalt"}

  laag      de BGT-laag (wegdeel, begroeidterreindeel, onbegroeidterreindeel, ondersteunendwegdeel, waterdeel, pand, ...); moet gelijk zijn
  functie   komt voor in de functie (kleine letters; "rijbaan" past dus bij "rijbaan lokale weg" en "rijbaan regionale weg")
  fysiek    komt voor in het fysiek voorkomen (open verharding, gesloten verharding, groenvoorziening, erf, ...)
  plus      komt voor in het plus-fysiek voorkomen (asfalt, tegels, heesters, ...)
  type      komt voor in het BGT-type of plus-type (muur, hek, ...)
  alleen    "2d" of "3d": de regel geldt alleen daar (weglaten = beide)
  deellaag  de 2D-vlakken van deze soort komen op een eigen laag: BGT_<laag>_<deellaag> (bijvoorbeeld BGT_wegdeel_fietspad); zonder deellaag blijven ze op de
            laag van de BGT-laag zelf
  vorm      (alleen 3D, voor overige bouwdelen) "blok" of "plaat": een blok staat op het maaiveld en is `hoogte` meter hoog; een plaat hangt `hoogte` meter
            boven het maaiveld en is `dikte` meter dik (een overkapping of luifel)
  hoogte    meter (zie vorm); dikte  meter (alleen bij een plaat)
  prioriteit  een geheel getal (standaard 0): een regel met een hogere prioriteit wint van een met een lagere, ook als die meer voorwaarden heeft

Een voorwaarde die ontbreekt, past bij alles. Past meer dan een regel, dan wint die met de hoogste prioriteit, en daarna de meest specifieke (de meeste voorwaarden,
daarna de langste tekst). Past geen enkele regel, dan blijft de kleur van de laag (2D) of het oppervlak van het type (3D).

Een eigen tabel staat in stijlen.json naast de instellingen; ontbreekt dat bestand, dan geldt de standaardtabel hieronder."""

import json
import os
import re

BESTANDSNAAM = "stijlen.json"
TABEL_VERSIE = 3             # de versie van de standaardtabel: 2 = met deellagen en de gebouwregels (0.19.0); 3 = met de overige bouwdelen (0.22.0)

# De standaardtabel. De kleuren zijn rood, groen, blauw van 0 tot 255.
STANDAARD_REGELS = [
    # ---- wegen (wegdeel): functie, daarna het materiaal (plus-fysiek voorkomen)
    {"naam": "weg_asfalt", "kleur": [88, 88, 94], "laag": "wegdeel", "functie": "rijbaan", "plus": "asfalt", "deellaag": "rijbaan"},
    {"naam": "weg_beton", "kleur": [172, 172, 168], "laag": "wegdeel", "functie": "rijbaan", "plus": "beton", "deellaag": "rijbaan"},
    {"naam": "weg_straatsteen", "kleur": [146, 138, 134], "laag": "wegdeel", "functie": "rijbaan", "plus": "straatsten", "deellaag": "rijbaan"},
    {"naam": "weg_klinker", "kleur": [166, 124, 110], "laag": "wegdeel", "functie": "rijbaan", "plus": "klinker", "deellaag": "rijbaan"},
    {"naam": "weg_rijbaan", "kleur": [104, 104, 110], "laag": "wegdeel", "functie": "rijbaan", "deellaag": "rijbaan"},
    {"naam": "weg_parkeren", "kleur": [130, 130, 140], "laag": "wegdeel", "functie": "parkeervlak", "deellaag": "parkeren"},
    {"naam": "weg_fietspad", "kleur": [196, 104, 92], "laag": "wegdeel", "functie": "fietspad", "deellaag": "fietspad"},
    {"naam": "weg_trap", "kleur": [165, 165, 165], "laag": "wegdeel", "functie": "voetpad op trap", "prioriteit": 1, "deellaag": "trap"},
    {"naam": "weg_voetpad_klinker", "kleur": [178, 128, 112], "laag": "wegdeel", "functie": "voetpad", "plus": "klinker", "deellaag": "voetpad"},
    {"naam": "weg_voetpad_tegels", "kleur": [208, 202, 190], "laag": "wegdeel", "functie": "voetpad", "plus": "tegel", "deellaag": "voetpad"},
    {"naam": "weg_voetpad_straatsteen", "kleur": [186, 176, 166], "laag": "wegdeel", "functie": "voetpad", "plus": "straatsten", "deellaag": "voetpad"},
    {"naam": "weg_voetpad", "kleur": [196, 190, 180], "laag": "wegdeel", "functie": "voetpad", "deellaag": "voetpad"},
    {"naam": "weg_voetgangersgebied", "kleur": [214, 206, 192], "laag": "wegdeel", "functie": "voetgangersgebied", "deellaag": "voetgangersgebied"},
    {"naam": "weg_inrit", "kleur": [158, 150, 142], "laag": "wegdeel", "functie": "inrit", "deellaag": "inrit"},
    {"naam": "weg_gesloten", "kleur": [110, 110, 116], "laag": "wegdeel", "fysiek": "gesloten verharding", "prioriteit": -1},
    {"naam": "weg_open", "kleur": [160, 152, 146], "laag": "wegdeel", "fysiek": "open verharding", "prioriteit": -1},
    # ---- groen (begroeidterreindeel): het onderscheid zit in het plus-fysiek voorkomen
    {"naam": "groen_gras", "kleur": [152, 204, 112], "laag": "begroeidterreindeel", "plus": "gras", "deellaag": "gras"},
    {"naam": "groen_heesters", "kleur": [92, 152, 88], "laag": "begroeidterreindeel", "plus": "heester", "deellaag": "heesters"},
    {"naam": "groen_bosplantsoen", "kleur": [62, 118, 68], "laag": "begroeidterreindeel", "plus": "bosplantsoen", "deellaag": "bosplantsoen"},
    {"naam": "groen_planten", "kleur": [188, 206, 128], "laag": "begroeidterreindeel", "plus": "planten", "deellaag": "planten"},
    {"naam": "groen_bos", "kleur": [48, 104, 58], "laag": "begroeidterreindeel", "plus": "bos", "deellaag": "bos"},
    {"naam": "groen_heide", "kleur": [166, 128, 150], "laag": "begroeidterreindeel", "plus": "heide", "deellaag": "heide"},
    {"naam": "groen_akker", "kleur": [206, 196, 120], "laag": "begroeidterreindeel", "plus": "akker", "deellaag": "akker"},
    # ---- onbegroeid terrein
    {"naam": "terrein_erf", "kleur": [224, 210, 176], "laag": "onbegroeidterreindeel", "fysiek": "erf", "deellaag": "erf"},
    {"naam": "terrein_gesloten", "kleur": [150, 150, 156], "laag": "onbegroeidterreindeel", "fysiek": "gesloten verharding", "deellaag": "verhard"},
    {"naam": "terrein_open", "kleur": [170, 160, 150], "laag": "onbegroeidterreindeel", "fysiek": "open verharding", "deellaag": "verhard"},
    {"naam": "terrein_halfverhard", "kleur": [200, 185, 150], "laag": "onbegroeidterreindeel", "fysiek": "half verhard", "deellaag": "halfverhard"},
    {"naam": "terrein_zand", "kleur": [232, 220, 170], "laag": "onbegroeidterreindeel", "fysiek": "zand", "deellaag": "zand"},
    # ---- ondersteunend wegdeel (bermen e.d.)
    {"naam": "berm", "kleur": [170, 185, 135], "laag": "ondersteunendwegdeel", "functie": "berm", "deellaag": "berm"},
    {"naam": "verkeerseiland", "kleur": [200, 190, 140], "laag": "ondersteunendwegdeel", "functie": "verkeerseiland", "deellaag": "verkeerseiland"},
    # ---- de grond onder een gebouw (alleen in 3D)
    {"naam": "pand_grond", "kleur": [185, 178, 172], "laag": "pand", "alleen": "3d"},
    # ---- gebouwen in 2D: lichtgrijs, lichter dan de wegdelen
    {"naam": "pand", "kleur": [232, 232, 236], "laag": "pand", "alleen": "2d"},
    {"naam": "gebouwinstallatie", "kleur": [218, 218, 224], "laag": "gebouwinstallatie", "alleen": "2d"},
    {"naam": "overigbouwwerk", "kleur": [224, 224, 230], "laag": "overigbouwwerk", "alleen": "2d"},
    # ---- overige bouwdelen in 3D (overig bouwwerk en gebouwinstallatie): de BGT heeft hier geen hoogte, dus de hoogte is een AANNAME per soort.
    #      Een blok staat op het maaiveld (hoogte = hoe hoog); een plaat hangt hoogte meter boven het maaiveld en is dikte meter dik.
    #      De kleur telt hier niet: bouwdelen krijgen dezelfde oppervlakken als de gebouwen (dak plat, muur, grondvlak; zie laag "gebouw" hieronder).
    {"naam": "bwd_overkapping", "kleur": [168, 168, 172], "laag": "overigbouwwerk", "type": "overkapping", "alleen": "3d", "vorm": "plaat", "hoogte": 3.0, "dikte": 0.2},
    {"naam": "bwd_open_loods", "kleur": [150, 150, 156], "laag": "overigbouwwerk", "type": "open loods", "alleen": "3d", "vorm": "plaat", "hoogte": 4.0, "dikte": 0.3},
    {"naam": "bwd_schuur", "kleur": [196, 180, 150], "laag": "overigbouwwerk", "type": "schuur", "alleen": "3d", "vorm": "blok", "hoogte": 3.5},
    {"naam": "bwd_tank", "kleur": [190, 190, 194], "laag": "overigbouwwerk", "type": "opslagtank", "alleen": "3d", "vorm": "blok", "hoogte": 6.0},
    {"naam": "bwd_silo", "kleur": [200, 200, 204], "laag": "overigbouwwerk", "type": "silo", "alleen": "3d", "vorm": "blok", "hoogte": 10.0},
    {"naam": "bwd_trafo", "kleur": [170, 175, 170], "laag": "overigbouwwerk", "type": "trafo", "alleen": "3d", "vorm": "blok", "hoogte": 2.5},
    {"naam": "bwd_bunker", "kleur": [160, 160, 150], "laag": "overigbouwwerk", "type": "bunker", "alleen": "3d", "vorm": "blok", "hoogte": 2.5},
    {"naam": "bwd_bezinkbak", "kleur": [175, 180, 185], "laag": "overigbouwwerk", "type": "bezinkbak", "alleen": "3d", "vorm": "blok", "hoogte": 0.5},
    {"naam": "bwd_bassin", "kleur": [175, 185, 195], "laag": "overigbouwwerk", "type": "bassin", "alleen": "3d", "vorm": "blok", "hoogte": 0.5},
    {"naam": "bwd_luifel", "kleur": [165, 165, 170], "laag": "gebouwinstallatie", "type": "luifel", "alleen": "3d", "vorm": "plaat", "hoogte": 2.8, "dikte": 0.15},
    {"naam": "bwd_bordes", "kleur": [190, 185, 175], "laag": "gebouwinstallatie", "type": "bordes", "alleen": "3d", "vorm": "blok", "hoogte": 0.4},
    {"naam": "bwd_trap", "kleur": [185, 180, 170], "laag": "gebouwinstallatie", "type": "trap", "alleen": "3d", "vorm": "blok", "hoogte": 0.6},
    # ---- gebouwen in 3D (laag "gebouw"; het type is de soort vlak): hellend dak, plat dak, muur en grondvlak
    {"naam": "dak", "kleur": [140, 64, 51], "laag": "gebouw", "type": "dak", "alleen": "3d"},
    {"naam": "dak_plat", "kleur": [128, 128, 134], "laag": "gebouw", "type": "dak_plat", "alleen": "3d"},
    {"naam": "muur", "kleur": [217, 209, 194], "laag": "gebouw", "type": "muur", "alleen": "3d"},
    {"naam": "grondvlak", "kleur": [128, 128, 128], "laag": "gebouw", "type": "grondvlak", "alleen": "3d"},
]

# BGT-laag in 3D (de tabelnaam in de 3D-bron) -> de naam van de 2D-laag
LAAG_ALIAS = {"overigeconstructie": "overigbouwwerk"}
TYPE_NAAR_LAAG = {"Road": "wegdeel", "PlantCover": "begroeidterreindeel", "WaterBody": "waterdeel", "Bridge": "overbruggingsdeel",
                  "BridgePart": "overbruggingsdeel", "OtherConstruction": "scheiding"}

_CACHE = {"pad": None, "tijd": None, "regels": None, "fout": "", "eigen": False}


def bestand_pad():
    cache = os.environ.get("PDOK_CACHE")
    basis = os.path.dirname(cache) if cache else os.getcwd()
    return os.path.join(basis, BESTANDSNAAM)


def norm_laag(naam):
    """De naam van een BGT-laag in een vaste vorm: kleine letters, zonder _vlak en zonder tekens die geen letter zijn."""
    n = re.sub(r"[^a-z]", "", str(naam or "").lower().replace("_vlak", ""))
    return LAAG_ALIAS.get(n, n)


def veilige_naam(naam):
    return re.sub(r"[^A-Za-z0-9_]+", "_", str(naam)).strip("_")


def _schoon(regel):
    """Een regel uit het bestand in een vaste vorm, of None als hij niet bruikbaar is."""
    if not isinstance(regel, dict) or not regel.get("naam"):
        return None
    k = regel.get("kleur")
    if not (isinstance(k, (list, tuple)) and len(k) == 3 and all(isinstance(x, (int, float)) for x in k)):
        return None
    uit = {"naam": veilige_naam(regel["naam"]), "kleur": tuple(max(0, min(255, int(x))) for x in k)}
    if not uit["naam"]:
        return None
    for sl in ("functie", "fysiek", "plus", "type"):
        if str(regel.get(sl) or "").strip():
            uit[sl] = str(regel[sl]).strip().lower()
    if str(regel.get("laag") or "").strip():
        uit["laag"] = norm_laag(regel["laag"])
    if str(regel.get("alleen") or "").lower() in ("2d", "3d"):
        uit["alleen"] = str(regel["alleen"]).lower()
    if str(regel.get("vorm") or "").strip().lower() in ("blok", "plaat"):
        uit["vorm"] = str(regel["vorm"]).strip().lower()
        for sl in ("hoogte", "dikte"):
            try:
                uit[sl] = max(0.0, float(regel.get(sl)))
            except (TypeError, ValueError):
                pass
        if "hoogte" not in uit:
            return None                                     # een vorm zonder hoogte is niet bruikbaar
    deel = re.sub(r"[^a-z0-9_]+", "_", str(regel.get("deellaag") or "").strip().lower()).strip("_")
    if deel:
        uit["deellaag"] = deel
    try:
        uit["prioriteit"] = int(regel.get("prioriteit") or 0)
    except (TypeError, ValueError):
        uit["prioriteit"] = 0
    return uit


def laad():
    """(regels, eigen_bestand, fout). Een ongeldig bestand geeft de standaardtabel en een foutmelding."""
    pad = bestand_pad()
    try:
        tijd = os.path.getmtime(pad)
    except OSError:
        tijd = None
    if _CACHE["regels"] is not None and _CACHE["pad"] == pad and _CACHE["tijd"] == tijd:
        return _CACHE["regels"], _CACHE["eigen"], _CACHE["fout"]
    fout, eigen, bron = "", False, STANDAARD_REGELS
    if tijd is not None:
        try:
            with open(pad, encoding="utf-8") as f:
                data = json.load(f)
            lijst = data.get("regels") if isinstance(data, dict) else data
            if not isinstance(lijst, list):
                raise ValueError("er staat geen lijst met regels in")
            bron, eigen = lijst, True
        except (OSError, ValueError) as e:
            fout = f"{BESTANDSNAAM} is niet te lezen ({e}); de standaardtabel wordt gebruikt"
    regels, overgeslagen, geerfd = [], 0, 0
    standaard_deel = {r["naam"]: r["deellaag"] for r in (_schoon(x) for x in STANDAARD_REGELS) if r and r.get("deellaag")}
    for r in bron:
        s = _schoon(r)
        if s:
            # Een regel in een bestand van een eerdere versie kent de sleutel deellaag nog niet: die komt dan uit de standaardtabel.
            # Staat de sleutel er wel (ook leeg), dan geldt wat jij hebt ingesteld.
            if eigen and isinstance(r, dict) and "deellaag" not in r and s["naam"] in standaard_deel:
                s["deellaag"] = standaard_deel[s["naam"]]
                geerfd += 1
            regels.append(s)
        else:
            overgeslagen += 1
    if overgeslagen and eigen:
        fout = (fout + "; " if fout else "") + f"{overgeslagen} regels in {BESTANDSNAAM} zijn onvolledig en worden overgeslagen"
    if eigen and geerfd:
        fout = (fout + "; " if fout else "") + f"{geerfd} regels in {BESTANDSNAAM} hadden nog geen deellaag en hebben die uit de standaardtabel gekregen"
    if eigen:
        aanwezig = {r["naam"] for r in regels}
        ontbreekt = [r["naam"] for r in (_schoon(x) for x in STANDAARD_REGELS) if r and r["naam"] not in aanwezig]
        if ontbreekt:
            fout = (fout + "; " if fout else "") + f"{BESTANDSNAAM} mist {len(ontbreekt)} regels uit de standaardtabel (zoals {', '.join(ontbreekt[:3])}); 'Stijlbestand bijwerken' voegt ze toe"
    _CACHE.update(pad=pad, tijd=tijd, regels=regels, fout=fout, eigen=eigen)
    return regels, eigen, fout


def standaardregels():
    """De standaardtabel in de vaste vorm (ook als je een eigen stijlbestand hebt)."""
    return [r for r in (_schoon(x) for x in STANDAARD_REGELS) if r]


def eig_uit_2d(eig):
    """De eigenschappen van een 2D-BGT-object (properties van de OGC API) in een vaste vorm."""
    def w(*namen):
        for n in namen:
            v = eig.get(n)
            if v not in (None, ""):
                return str(v).strip().lower()
        return ""
    return {"functie": (w("functie", "bgt_functie") + " " + w("plus_functie")).strip(), "fysiek": w("fysiek_voorkomen", "bgt_fysiekvoorkomen"),
            "plus": w("plus_fysiek_voorkomen", "plus_fysiekvoorkomen"), "type": (w("bgt_type", "type") + " " + w("plus_type")).strip()}


def eig_uit_3d(at):
    """De eigenschappen van een object uit de 3D-bron in een vaste vorm."""
    return eig_uit_2d(at)


def laag_uit_3d(typ, at):
    """De BGT-laag van een 3D-object: de tabelnaam, of bij ontbreken het CityJSON-type."""
    tabel = norm_laag((at or {}).get("tabelnaam"))
    return tabel or TYPE_NAAR_LAAG.get(typ, "")


def kies(laag, eig, dim, regels=None):
    """De best passende regel voor een object, of None. dim is "2d" of "3d"."""
    if regels is None:
        regels = laad()[0]
    laag = norm_laag(laag)
    beste, beste_score = None, None
    for r in regels:
        if r.get("alleen") and r["alleen"] != dim:
            continue
        if "laag" in r and r["laag"] != laag:
            continue
        ok = True
        score_lengte = len(r.get("laag", ""))
        for sl in ("functie", "fysiek", "plus", "type"):
            if sl in r:
                if r[sl] not in (eig.get(sl) or ""):
                    ok = False
                    break
                score_lengte += len(r[sl])
        if not ok:
            continue
        score = (r.get("prioriteit", 0), sum(1 for sl in ("laag", "functie", "fysiek", "plus", "type") if sl in r), score_lengte)
        if beste_score is None or score > beste_score:
            beste, beste_score = r, score
    return beste


def schrijf_standaard():
    """Schrijft de standaardtabel naar stijlen.json (als dat bestand er nog niet is) en geeft het pad."""
    pad = bestand_pad()
    if not os.path.exists(pad):
        os.makedirs(os.path.dirname(pad), exist_ok=True)
        data = {"versie": TABEL_VERSIE, "uitleg": ["Kleur per soort. Pas de kleuren en de regels aan en importeer opnieuw (de 2D-lagen en het terrein worden dan opnieuw getekend).",
                           "Elke regel heeft een naam, een kleur [rood, groen, blauw] van 0 tot 255 en voorwaarden: laag, functie, fysiek, plus, type en alleen (2d of 3d).",
                           "Een voorwaarde die ontbreekt past bij alles; past meer dan een regel, dan wint de meest specifieke. Zie de handleiding voor de uitleg.",
                           "Verwijder dit bestand (of gebruik 'Standaardstijlen herstellen' in het palet) om weer de standaardtabel te gebruiken."],
                "regels": [dict(r, kleur=list(r["kleur"])) for r in STANDAARD_REGELS]}
        with open(pad, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        _CACHE["regels"] = None
    return pad


def bijwerken():
    """Vult je stijlbestand aan met wat de standaardtabel sinds de vorige keer erbij heeft gekregen, zonder je eigen regels en kleuren te
    veranderen: regels die ontbreken worden toegevoegd en regels zonder deellaag krijgen die van de standaardtabel. Er komt een kopie
    (stijlen.json.bak) van het oude bestand. Geeft (toegevoegd, aangevuld, bestand_was_er_niet)."""
    pad = bestand_pad()
    if not os.path.exists(pad):
        schrijf_standaard()
        return 0, 0, True
    with open(pad, encoding="utf-8") as f:
        data = json.load(f)
    lijst = data.get("regels") if isinstance(data, dict) else data
    if not isinstance(lijst, list):
        raise ValueError("er staat geen lijst met regels in")
    standaard = {veilige_naam(r["naam"]): r for r in STANDAARD_REGELS}
    aanwezig = set()
    aangevuld = 0
    for r in lijst:
        if isinstance(r, dict) and r.get("naam"):
            naam = veilige_naam(r["naam"])
            aanwezig.add(naam)
            if "deellaag" not in r and naam in standaard and standaard[naam].get("deellaag"):
                r["deellaag"] = standaard[naam]["deellaag"]
                aangevuld += 1
    toegevoegd = 0
    for naam, r in standaard.items():
        if naam not in aanwezig:
            lijst.append(dict(r, kleur=list(r["kleur"])))
            toegevoegd += 1
    if not isinstance(data, dict):
        data = {"regels": lijst}
    data["regels"] = lijst
    data["versie"] = TABEL_VERSIE
    try:
        import shutil
        shutil.copyfile(pad, pad + ".bak")
    except OSError:
        pass
    with open(pad, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    _CACHE["regels"] = None
    return toegevoegd, aangevuld, False


def herstel():
    """Verwijdert stijlen.json: daarna geldt weer de standaardtabel."""
    try:
        os.remove(bestand_pad())
    except OSError:
        pass
    _CACHE["regels"] = None
