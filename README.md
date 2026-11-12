# PDOK Import - Archicad Add-On

Eén `.apx`-bestand dat PDOK-gegevens in Archicad importeert. De add-on bevat een **motor** (Python, ingebouwd in het
`.apx`) en toont de kaart in een **palet in Archicad**.

## Stand van zaken

- **0.1:** skelet (menu en melding). Gelukt.
- **0.2:** de motor (Python) zit in het `.apx`, wordt gestart, en de kaart staat in een palet in Archicad. Gelukt.
- **0.3 (groep 1):** de eerste **opdrachten van de add-on zelf**: lagen (lezen, aanmaken in een map), het actieve venster
  (lezen, wisselen), elementen (per type lezen, details lezen, laag en ID zetten, verwijderen) en de selectie. De motor
  roept ze aan via Archicads JSON-interface (namespace `PDOKImport`). Een testpaneel in het palet laat elke opdracht proberen.
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

## Testen

Archicad: **PDOK Import > PDOK Import openen...**. Het palet toont bovenaan de motor en daaronder het **testpaneel**.

**Groep 1** (zoals eerder): **Draai de basistests**, **Naar plattegrond / Naar 3D**, en met een zelf getekend element
**Selectie lezen**, **Selectie op de testlaag zetten**, **tonen** en **verwijderen** (twee klikken).

**Nieuw in deze versie**
1. **Naar plattegrond** en **Naar 3D** melden nu ook of de **database** is gewisseld (`Database gewisseld: true`) en wat de
   **huidige database** is. Bij je vorige test bleef het paneel na *Naar 3D* een 2D-vlak tonen; met deze melding zien we waarom.
   Na *Naar 3D* hoort de huidige database `3DModel` te zijn, en na *Naar plattegrond* `FloorPlan`.
2. Vul bij **Groep 2 (2D)** de coordinaten in waar je de testvormen wilt hebben (standaard rond RD 260250, 482250, het
   gebied van je eerdere tests; pas aan als jouw model elders ligt).
3. **Test: polylijn tekenen**: een lijn van 20 m met een knik, op de laag `PDOK_test`, ID `TEST-LIJN`.
4. **Test: vlak met gat tekenen**: een vlak van 20 x 20 m met een gat van 6 x 6 m, rode kleur, effen vulling (als er een
   effen vulling in het project is), pen 1 voor de rand, ID `TEST-VLAK`.
5. Zoom in Archicad naar die plek, of kies *Bewerken > Selecteren > Alle elementen op een laag* voor `PDOK_test`. Kijk of
   het vlak het gat heeft, de kleur klopt en de lijn er staat.
6. **Elementen op de testlaag tonen** en **verwijderen** (twee klikken) ruimen alles weer op. **Ongedaan maken** brengt het terug.

## Wat je terugmeldt

- Een schermafbeelding van het testpaneel na de basistests, en van de uitvoer van de overige tests.
- Wat er mislukt: de melding in het paneel (en zo nodig de inhoud van `engine.log`, te vinden via *Over PDOK Import...*).
- Of de lagen, het venster en de ID's in Archicad zelf kloppen met wat het paneel meldt.
- Wat de database-melding zegt na *Naar plattegrond* en *Naar 3D*.
- Of de lijn en het vlak er in Archicad goed uitzien (het gat, de kleur, de pen).

## MDID

De ID's in `Sources/RFIX/AddOnFix.grc` zijn die van jouw account. Wijzig ze niet; laat dit bestand ook bij een update
ongemoeid.
