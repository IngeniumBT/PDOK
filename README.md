# PDOK Import - Archicad Add-On

Eén `.apx`-bestand dat PDOK-gegevens in Archicad importeert. De add-on bevat een **motor** (Python, ingebouwd in het
`.apx`) en toont de kaart in een **palet in Archicad**.

## Stand van zaken

- **0.1:** skelet (menu en melding). Gelukt.
- **0.2:** de motor (Python) zit in het `.apx`, wordt gestart, en de kaart staat in een palet in Archicad. Gelukt.
- **0.3 (groep 1):** de eerste **opdrachten van de add-on zelf**: lagen (lezen, aanmaken in een map), het actieve venster
  (lezen, wisselen), elementen (per type lezen, details lezen, laag en ID zetten, verwijderen) en de selectie. De motor
  roept ze aan via Archicads JSON-interface (namespace `PDOKImport`). Een testpaneel in het palet laat elke opdracht proberen.
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
   naadsluiting tussen de vlakken van een import werkt; de aansluiting op meshes van een eerdere import volgt nog. Begin met een
   klein gebied (ongeveer 300 x 300 m). Het testpaneel heeft **Test: mesh (terrein) maken**.
   Controleer in 3D of de gebouwen op het terrein staan.
9. De gedownloade 3D-gegevens bewaart de motor in `%LOCALAPPDATA%\PDOKImport\cache`.

## Wat je terugmeldt

- Een schermafbeelding van het testpaneel na de basistests, en van de uitvoer van de overige tests.
- Wat er mislukt: de melding in de voortgang of in het testpaneel (en zo nodig de inhoud van `engine.log`, te vinden via *Over PDOK Import...*).
- Of de lagen, het venster en de ID's in Archicad zelf kloppen met wat het paneel meldt.
- Wat de database-melding zegt na *Naar plattegrond* en *Naar 3D*.
- Of de lijn en het vlak er in Archicad goed uitzien (het gat, de kleur, de pen).

## MDID

De ID's in `Sources/RFIX/AddOnFix.grc` zijn die van jouw account. Wijzig ze niet; laat dit bestand ook bij een update
ongemoeid.
