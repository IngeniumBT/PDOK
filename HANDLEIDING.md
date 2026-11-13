# PDOK Import voor Archicad - handleiding voor proefgebruikers

Versie 0.13.0 (proefversie). Deze add-on haalt gegevens van PDOK (de BGT, het kadaster, bestemmingsplannen en de 3D Basisvoorziening) op
en zet ze in je Archicad-project: als lijnen en vlakken, als 3D-gebouwen, als terrein en als bomen.

## Wat heb je nodig

- **Windows** en **Archicad 29**.
- Een **internetverbinding** (de gegevens komen van PDOK).
- Een project waarvan het **projectnulpunt op RD (0, 0)** ligt, het landelijke coordinatenstelsel (Rijksdriehoek, EPSG:28992). In deze
  versie wordt alles in RD op het projectnulpunt gezet: staat jouw gebouw ver van RD (0, 0), dan komt de import ook ver van het project
  terecht. Het Survey Point wordt in deze versie niet gebruikt.

## Installeren

1. Download het bestand **`PDOKImport_AC29.apx`** van de pagina Releases (je krijgt de link van degene die je de proefversie geeft).
2. Klik met de rechtermuisknop op het bestand > **Eigenschappen**. Staat onderaan **Blokkering opheffen** (*Unblock*)? Zet daar een vinkje en
   klik op OK.
3. Archicad: **Opties > Add-On Manager** (*Options > Add-On Manager*) > tabblad **Edit List of Available Add-Ons** > **Add** > kies het bestand > **OK**.
4. Herstart Archicad als dat gevraagd wordt. Er staat nu een menu **PDOK Import** in de menubalk.

*Een nieuwe versie installeren:* sluit Archicad, vervang het oude `.apx` door het nieuwe (zelfde plek), zet weer *Blokkering opheffen* aan, en start
Archicad. Een oude versie wordt vanzelf opgeruimd.

## Gebruiken

1. Kies **PDOK Import > PDOK Import openen...**. Er opent een palet met een **kaart** en daarnaast de opties. De eerste keer duurt het
   openen een paar seconden.
2. **Zoek je locatie**: typ een adres bij *Zoek een adres* en klik op *Zoeken*, of verschuif en zoom de kaart (*Kaart uitzoomen* toont heel Nederland).
3. **Teken je importgebied**: klik op *Gebied tekenen* en sleep een rechthoek over de kaart, of houd **Shift** ingedrukt en sleep. Slepen zonder
   Shift verschuift de kaart. Onder de kaart staat de afmeting. Maximaal 3000 x 3000 m; **begin klein** (bijvoorbeeld 300 x 300 m). Een gebied
   groter dan 600 m wordt in blokken verwerkt. **Esc** annuleert het tekenen.
4. **Kies wat je wilt importeren** (zie hieronder) en klik op **Importeren in Archicad**. Een voortgangsbalk toont hoever het is, met een knop om te stoppen.
5. Het resultaat staat in lagen in de map **PDOK Import** in je project.

Het palet heeft rechtsboven **A-** en **A+** voor de tekstgrootte (de keuze wordt onthouden).

## De onderdelen

**Lagen (2D)** - de BGT en het kadaster, als vlakken en lijnen op een eigen laag per soort (bijvoorbeeld `BGT_wegdeel`, `KAD_perceel`). Rechts van
elke laag kun je een **pennummer** invullen; leeg is de standaardpen. *Alles aan* en *Alles uit* per groep. *Perceelnummers als tekst* zet ook de
nummers bij de percelen. *Ook objecten boven en onder maaiveld* neemt de BGT-objecten mee die niet op maaiveldhoogte liggen.

**Bestemmingsplan** - kies met *Kies gml-bestand* een IMRO-bestand (GML) van je bestemmingsplan; *Wissen* haalt het weer weg. *Maatvoering (bouwhoogte e.d.) als tekst*
zet de maatvoeringen als tekst in de tekening. Het bestemmingsplan komt in de plattegrond.

**3D** (de 3D Basisvoorziening van PDOK, hoogtes in NAP):
- **Gebouwen** (LoD 2.2, als morphs): elk pand wordt een morph op de laag `3D_gebouwen`, met het BAG-pandnummer als ID. *Met materialen* geeft dak, muur en
  grondvlak een eigen oppervlak (`PDOK_dak`, `PDOK_muur`, `PDOK_grondvlak`).
- **Terrein** (als meshes, op vier lagen: wegen, landgebruik, begroeiing en water): elk BGT-object wordt een mesh met een eigen oppervlak. *Naadsluiting*
  trekt vlakken die tegen elkaar liggen gelijk, zodat er geen spleten zijn. *Terreintypen overslaan* laat soorten weg (gescheiden door `;`).
  *Onderkant* bepaalt of het terrein een massief **volume** wordt, **zijvlakken** krijgt of alleen een **bovenvlak**; de diepte geeft de onderkant
  in meters onder het laagste punt.
- **Viaducten en bruggen meenemen (als dun dek)**: leest de bruggen uit de bron in en maakt ze tot een dunne plaat. Deze functie is nog in ontwikkeling
  (zie Beperkingen).
- **Bomen** (BGT-vegetatiepunten): op elk punt komt een bibliotheekobject te staan, op de hoogte van het terrein. Vul bij het veld de **naam van het
  bibliotheekobject** in (standaard *Boom stedenbouw 02*); de namen zijn gelokaliseerd en moeten in jouw geladen bibliotheek staan.

De eerste keer dat je 3D importeert voor een gebied wordt een grote tegel van PDOK opgehaald (tientallen MB); dat kan een minuut duren. Daarna staat die in
de cache en gaat het sneller.

## Goed om te weten

- **Archicad lijkt tijdens een import soms vast te lopen.** De add-on werkt via Archicad zelf, en Archicad is dan even bezet. Wacht tot de voortgangsbalk klaar is.
- **Het venster wisselt tijdelijk naar de plattegrond** voor lijnen en vlakken, en springt daarna terug naar waar je was.
- **Ongedaan maken** werkt: elke stap in Archicad is een eigen, ongedaan te maken opdracht.
- **Nogmaals importeren** slaat gebouwen, terrein en bomen over die er al staan (ze herkennen elkaar aan het ID). Lijnen en vlakken worden opnieuw getekend: wis
  ze eerst als je ze vervangt.
- **Alles komt in de map PDOK Import** (lagen), zodat je het makkelijk kunt tonen, verbergen of verwijderen.

## Beperkingen van deze proefversie

- **Het coordinatenstelsel:** alleen een project met het nulpunt op RD (0, 0); het Survey Point wordt niet gebruikt.
- **Viaducten** en bruggen worden in sommige gevallen nog niet goed gemaakt (bijvoorbeeld als dek en weg op dezelfde hoogte liggen in de bron).
- **Terrein wissen** zit niet in het palet. Verwijder het terrein door de lagen `3D_terrein_*` te selecteren en te wissen.
- **Alleen Windows en Archicad 29.**

## Problemen oplossen

- **Het palet blijft leeg of toont een foutmelding.** De motor draait niet goed. Kies **PDOK Import > Over PDOK Import...**: daar staat de map en het
  logboek (`engine.log`). Open dat bestand en stuur de laatste regels mee als je hulp vraagt. Beveiligingssoftware die programma's in
  `%LOCALAPPDATA%\PDOKImport` blokkeert, is een bekende oorzaak.
- **"Archicad antwoordt niet"** - er staat waarschijnlijk een dialoog open in Archicad. Sluit die en probeer opnieuw.
- **De kaart toont geen achtergrond of de lagenlijst laadt niet** - controleer de internetverbinding. De knop *Openen in browser* opent dezelfde kaart in je browser.
- **Een import mislukt of is onvolledig** - de voortgangsmelding noemt de reden. Probeer een kleiner gebied.

## Feedback geven

Het meest helpend is: de **versie** (PDOK Import > Over PDOK Import...), wat je deed (welk gebied en welke opties), wat je verwachtte en wat er gebeurde, een
**schermafbeelding**, en zo nodig de laatste regels uit `engine.log`.

## Verwijderen

Haal het bestand uit de **Add-On Manager** (selecteer het en klik op *Remove*) en verwijder het `.apx`. De uitgepakte onderdelen en de cache staan in
`%LOCALAPPDATA%\PDOKImport`; die map mag je verwijderen.

## Bronnen en licenties

De gegevens komen van PDOK (BGT, kadaster, bestemmingsplannen, 3D Basisvoorziening en de BRT-achtergrondkaart); raadpleeg PDOK voor de gebruiksvoorwaarden.
Delen van de bouwopzet komen uit het open-sourceproject Tapir (MIT) en het sjabloon van Graphisoft (MIT); zie `THIRD_PARTY_NOTICES.md`.
