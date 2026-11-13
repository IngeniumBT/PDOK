# PDOK Import - Archicad Add-On

Eén `.apx`-bestand dat PDOK-gegevens in Archicad importeert. De add-on bevat een **motor** (Python, ingebouwd in het
`.apx`) en toont de kaart in een **palet in Archicad**.

## Stand van zaken

- **0.1:** skelet (menu en melding). Gelukt.
- **0.2:** de motor (Python) zit in het `.apx`, wordt gestart, en de kaart staat in een palet in Archicad. Gelukt.
- **0.3 (groep 1):** de eerste **opdrachten van de add-on zelf**: lagen (lezen, aanmaken in een map), het actieve venster
  (lezen, wisselen), elementen (per type lezen, details lezen, laag en ID zetten, verwijderen) en de selectie. De motor
  roept ze aan via Archicads JSON-interface (namespace `PDOKImport`). Een testpaneel in het palet laat elke opdracht proberen.
- **0.14.0: een timer, vlak terrein, de hulpmiddelen terug, en gebouwen op LoD 2.2.** Het palet toont een timer en na afloop de duur per onderdeel.
  Nieuw is de optie *Vlak terrein* (de bovenkant van alle meshes op de gemiddelde hoogte, het laagste of hoogste punt, of een eigen niveau; de bomen
  volgen). *Terreincontrole* en *Terrein wissen* staan weer in het palet, in het uitklapbare vak *Hulpmiddelen voor het terrein*. Gebouwen die
  Archicad als geheel weigert (bijvoorbeeld rijtjes met gedeelde scheidingsmuren) worden nu eerst op LoD 2.2 in losse delen gemaakt (`BAGID-deel1`, ...),
  en alleen daarna op een lager niveau; het overzicht noemt hoeveel panden op welke manier zijn gemaakt en welke panden in de bron geen LoD 2.2 hebben.
- **0.13.0: de eerste proefversie voor gebruikers.** De pagina is hersteld (bij het weghalen van de twee terreinknoppen was de lagenlijst niet
  meer geladen), de projectlocatie (Survey Point) is uitgezet (het projectnulpunt wordt als RD (0, 0) gezien), de motor ruimt oude versies in
  AppData op, en er is een handleiding voor proefgebruikers (HANDLEIDING.md).
- **0.12.1: de projectlocatie via de omrekening van het Survey Point.** De add-on gebruikt de omrekening die Archicad zelf geeft van
  projectcoordinaten naar het Survey Point-stelsel (de plek van het Survey Point en zijn Project North-draaiing), en rekent daarmee alle
  coordinaten van RD naar het project, en bij het teruglezen van meshes weer terug. Het Survey Point is het nulpunt van het landelijke stelsel.
  De IFC-georeferentie (stelselnaam, E/N) wordt niet gebruikt. De knoppen *Terreincontrole* en *Terrein wissen* zijn uit het palet gehaald.
- **0.12.0:** eerste versie van de projectlocatie, gebaseerd op de IFC-georeferentie (vervangen door 0.12.1).
- **0.11.2:** pijlers (en landhoofden) van een brug blijven een **massieve kolom** tot de onderkant; alleen het brugdek wordt een dun
  dek. De eigenschap heet in de bron `relatievehoogteligging` (zonder streepje); die wordt nu herkend. De **Terreincontrole** toont per
  brugobject de soort, hoogteligging, oppervlakte, hoogtes en wat eronder ligt, en meldt kleine verschillen in oppervlakte (onder 3% of
  2 m2) niet meer als afwijking.
- **0.11.1: bruggen en viaducten uit de bron.** De tegels bevatten viaducten als eigen soort object (CityJSON-type `Bridge` en
  `BridgePart`), die tot nu toe niet werden ingelezen; daardoor ontbraken sommige viaducten helemaal. Ze worden nu ingelezen (alleen de
  bovenkant, ook als de bron ze als gesloten lichaam geeft), op de laag `3D_terrein_bruggen` met het oppervlak `PDOK_brug`, altijd als
  dun dek. De **Terreincontrole** toont nu alle soorten objecten in de bron voor het gebied.
- **0.11.0: viaducten en brugdekken.** Een viaduct werd een massief blok tot de onderkant van het terrein. Nu worden meshes die een
  dek zijn (ze liggen in plattegrond boven een ander object, of de bron zegt dat ze boven het maaiveld liggen) een dunne plaat van
  0,6 m, met het terrein eronder dat gewoon doorloopt. Te kiezen met *Viaducten en brugdekken als dun dek*. De **Terreincontrole**
  noemt nu ook de eigenschappen van de bron en hoeveel dekken zijn herkend.
- **0.10.1: de aansluiting van gebieden.** Een object dat de gebiedsrand kruist (een lange weg) werd bij een klein gebied afgeknipt;
  een aangrenzende import sloeg het daarna over omdat het ID er al stond, en zo ontstonden witte delen. Nu wordt een object dat het
  gebied raakt als geheel gemaakt. Nieuw: de knoppen **Terreincontrole** (vergelijkt Archicad met de bron en meldt wat ontbreekt of
  afwijkt) en **Terrein wissen**. Het lezen van ID's is ook sneller.
- **0.10.0:** het **logo van Ingenium** in de kop van het paneel (klein, met doorzichtige achtergrond), de keuze voor de **onderkant
  van het terrein** (als volume, met zijvlakken of alleen het bovenvlak) en de **diepte** onder het laagste punt, en het **lezen van
  meshes** (omtrek met hoogtes, gaten, niveau en skirt). Daardoor sluit een nieuwe terreinimport met naadsluiting aan op meshes
  van een eerdere import.
- **0.9.0: het 3D-terrein.** De opdracht **CreateMeshes** (omtrek met hoogtes, gaten, extra hoogtepunten, de onderkant van het
  terrein (skirt), en het oppervlak per terreintype). De terreinimport werkt nu vanuit het palet. De ruimte tussen de zoek- en
  bedienknoppen is overal even groot.
- **0.8.0: de 3D-gebouwen.** De opdrachten **EnsureSurface** (de oppervlakken PDOK_dak, PDOK_muur en PDOK_grondvlak) en
  **CreateMorphs** (het gebouw als morph, met een oppervlak per vlak) zijn er. Ook is het paneel compacter: de knoppen heten nu
  *Kaart uitzoomen* en *Openen in browser*, en de uitleg is kleiner.
- **0.7.0:** de opdracht **CreateTexts**: de **perceelnummers** (kadaster) en de **teksten van het bestemmingsplan** komen nu binnen.
  Het paneel heeft **A-** en **A+** voor de tekstgrootte (standaard 80% in het palet; de kaart zelf verandert niet).
- **0.6.0: de echte kaart en import in het palet.** BGT- en kadasterlagen (als vlakken en polylijnen) en de **bomen**
  worden vanuit het palet geimporteerd, via de opdrachten van de add-on zelf. 3D-gebouwen, 3D-terrein en teksten staan nog
  uitgeschakeld (die opdrachten volgen). Het testpaneel staat nu op de link **testpaneel** rechtsonder.
- **0.5.0 (groep 3, deel 1):** de opdracht **CreateObjects** voor bibliotheekobjecten (zoals de bomen): op naam zoeken, plaatsen op
  een absolute hoogte (omgerekend naar de verdieping), met afmetingen (A, B, ZZYZX), draaiing, laag en ID.
- **0.4.1:** een ID voor een element dat er geen kan hebben (lijn, polylijn) verwijdert het element niet meer.
- **0.4 (groep 2, deel 1):** de opdrachten **CreatePolylines** en **CreateHatches** (vlakken met gaten, pennen, kleur en
  effen vulling), en bij het wisselen van venster meldt de add-on nu ook de **database** waarin de opdrachten werken.
- **Volgt:** groep 2 deel 2 (teksten voor de perceelnummers), groep 3 (3D: meshes, morphs, objecten) en de echte kaart met de import.

## Een nieuwe versie bouwen (zoals je al deed)

1. Zet de nieuwe bestanden in je GitHub-repository: **Add file > Upload files**, en **sleep de mappen en bestanden
   uit de update-ZIP** erin (niet de map `.github`; die blijft zoals hij is). Bestaande bestanden met dezelfde naam
   worden vervangen. Klik **Commit changes**.
2. Het tabblad **Actions** bouwt vanzelf. Deze bouw duurt iets langer, omdat hij ook de Python (ongeveer 10 MB)
   downloadt en inpakt.
3. Download onder **Artifacts** `PDOKImport_AC29_Win`, pak het uit, en vervang het oude `PDOKImport_AC29.apx`
   (sluit Archicad eerst). Zet bij het nieuwe bestand *Blokkering opheffen* aan in de Eigenschappen.

## De motor

- De add-on pakt de motor eenmalig uit naar `%LOCALAPPDATA%\PDOKImport\<versie>\` (bijvoorbeeld
  `C:\Users\jouw naam\AppData\Local\PDOKImport\0.4.0-abc1234\`) en start hem verborgen op de achtergrond.
- De motor luistert alleen op deze computer (`127.0.0.1`) en stopt vanzelf als Archicad sluit.
- Het **logboek** staat in dezelfde map: `engine.log`. Bij een probleem staat daar de oorzaak in.
- Windows zoekt `tar.exe` (zit in Windows 10 en nieuwer) om het uit te pakken, en probeert anders PowerShell.

## Testen (versie 0.6.0: de echte import)

Archicad: **PDOK Import > PDOK Import openen...**. Het palet toont nu de **kaart** (rechtsonder de link *testpaneel*).

1. **Een gebied tekenen**: klik op *Gebied tekenen* en sleep, of houd **Shift** ingedrukt en sleep. Begin klein (bijvoorbeeld
   300 x 300 m).
2. **2D-lagen**: vink in de lijst een paar BGT-lagen aan (bijvoorbeeld *wegdeel* en *pand*) en het kadaster (*perceel*).
   Klik op **Importeren**. De voortgangsbalk loopt, en daarna staan er lagen in de map **PDOK Import** met de vlakken en
   lijnen. Het **venster** van Archicad wisselt tijdelijk naar de plattegrond en gaat daarna terug naar waar je was.
3. **Bomen**: vink *Bomen* aan (objectnaam standaard "Boom stedenbouw 02"). Ze komen op de laag `3D_bomen`, op de hoogte van het
   terrein (uit de 3D Basisvoorziening van PDOK; de eerste keer duurt het ophalen van de tegel even), met het ID `BOOM-<BGT-id>`.
   Een tweede keer importeren plaatst geen dubbelen.
4. **Teksten**: de perceelnummers (laag `KAD_perceelnummer`) en de maatvoering/teksten van het bestemmingsplan worden nu ook getekend.
   Kijk of ze leesbaar zijn (hoogte 2,5), op de goede plek staan, en of een tekst met meerdere regels meerdere regels toont.
   Het testpaneel heeft ook een knop **Test: tekst plaatsen**.
5. **Tekstgrootte van het paneel**: met **A-** en **A+** bovenaan het paneel. De keuze wordt onthouden.
6. **3D-gebouwen**: vink *Gebouwen* aan (met of zonder materialen). Elk pand wordt een morph op de laag `3D_gebouwen`, met het
   BAG-pandnummer als ID, en met een eigen oppervlak voor dak, muur en grondvlak. Een tweede keer importeren slaat panden over
   die er al staan. Begin met een klein gebied (een paar panden), want elk pand heeft veel vlakken.
   Het testpaneel heeft **Test: morph (blok) maken** (een blok van 10 x 10 x 8 m met een rood dak).
7. **3D-terrein**: vink *Terrein* aan. Elk BGT-object (weg, landgebruik, begroeiing, water) wordt een mesh met zijn eigen
   oppervlak, op vier lagen `3D_terrein_*` in de map PDOK Import, met een onderkant (skirt) 1 m onder het laagste punt. De
   naadsluiting werkt binnen een import en sluit nu ook aan op meshes van een eerdere import. Begin met een
   klein gebied (ongeveer 300 x 300 m). Het testpaneel heeft **Test: mesh (terrein) maken**.
   **Let op bij een update van 0.10.0 of eerder:** de meshes die je al hebt zijn afgeknipt en worden niet vanzelf aangevuld. Klik op
   **Terreincontrole** (met een getekend gebied) om te zien wat er ontbreekt, dan op **Terrein wissen** (twee klikken) en importeer opnieuw.
   **Viaducten:** vink *Viaducten en bruggen meenemen (als dun dek)* aan (standaard). Dit leest de bruggen uit de bron in en maakt ze, en
   andere meshes die boven een ander object liggen, tot een dunne plaat. Klopt een viaduct nog niet, klik dan op **Terreincontrole**
   en plak de uitvoer: de lijst met eigenschappen van de bron laat zien onder welke naam de hoogteligging staat.
   Onder *Terrein* kies je de **onderkant** (volume, zijvlakken of alleen het bovenvlak) en de **diepte** in meter.
   Controleer in 3D of de gebouwen op het terrein staan. Test de aansluiting door een tweede, aangrenzend gebied te importeren:
   de vlakken langs de grens horen dezelfde hoogte te hebben.
9. De gedownloade 3D-gegevens bewaart de motor in `%LOCALAPPDATA%\PDOKImport\cache`.

## Wat je terugmeldt

- Een schermafbeelding van het testpaneel na de basistests, en van de uitvoer van de overige tests.
- Wat er mislukt: de melding in de voortgang of in het testpaneel (en zo nodig de inhoud van `engine.log`, te vinden via *Over PDOK Import...*).
- Of de lagen, het venster en de ID's in Archicad zelf kloppen met wat het paneel meldt.
- Wat de database-melding zegt na *Naar plattegrond* en *Naar 3D*.
- Of de lijn en het vlak er in Archicad goed uitzien (het gat, de kleur, de pen).

## De projectlocatie (voor andere gebruikers)

De import werkt in RD, het landelijke stelsel. In Archicad is het **Survey Point het nulpunt van dat stelsel**: de coordinaten van een
punt in het Survey Point-stelsel zijn zijn RD-coordinaten. De add-on gebruikt de omrekening die Archicad daarvoor zelf biedt.

**Heeft jouw project het projectnulpunt op RD (0, 0)** en staat het Survey Point op het projectnulpunt, dan is er niets in te stellen.

**Ligt het projectnulpunt ergens anders** (de gewone situatie: het gebouw staat bij het Archicad-nulpunt), zet dan het Survey Point op
**min de RD-coordinaten van het projectnulpunt**:

1. Archicad: **Options > Project Preferences > Location Settings > Survey Point**.
2. Vul bij **Easting, Northing en Elevation** de plek van het Survey Point *ten opzichte van het projectnulpunt* in. Ligt het projectnulpunt op
   RD (260250, 482250) en 35,00 m NAP, vul dan in: Easting -260250, Northing -482250, Elevation -35.
3. Staat het project niet recht op het noorden, vul dan de **Project North**-hoek in.
4. De **georeferentie voor IFC** (stelselnaam, Eastings, Northings enzovoort) en de **breedte- en lengtegraad** van de projectlocatie hoef je
   voor deze add-on niet in te vullen; ze worden niet gebruikt.

Het palet toont bovenaan wat het Survey Point zegt: *"Volgens het Survey Point ligt het projectnulpunt op RD (260250, 482250), hoogte
35,00 m."* Klopt dat niet, of ligt het buiten het bereik van RD, dan staat er een waarschuwing. Het testpaneel heeft **Projectlocatie lezen**
(de matrix en de uitleg). Test het met een klein gebied rond een gebouw dat je kent: de BGT-lagen moeten op dat gebouw liggen.

## MDID

De ID's in `Sources/RFIX/AddOnFix.grc` zijn die van jouw account. Wijzig ze niet; laat dit bestand ook bij een update
ongemoeid.
