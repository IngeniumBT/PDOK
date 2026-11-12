# PDOK Import - Archicad Add-On

Eén `.apx`-bestand dat PDOK-gegevens in Archicad importeert. De add-on bevat een **motor** (Python, ingebouwd in het
`.apx`) en toont de kaart in een **palet in Archicad**.

## Stand van zaken

- **0.1:** skelet (menu en melding). Gelukt.
- **0.2:** de motor (Python) zit in het `.apx`, wordt gestart, en de kaart staat in een palet in Archicad. Gelukt.
- **0.3 (groep 1):** de eerste **opdrachten van de add-on zelf**: lagen (lezen, aanmaken in een map), het actieve venster
  (lezen, wisselen), elementen (per type lezen, details lezen, laag en ID zetten, verwijderen) en de selectie. De motor
  roept ze aan via Archicads JSON-interface (namespace `PDOKImport`). Een testpaneel in het palet laat elke opdracht proberen.
- **Volgt:** groep 2 (2D: lijnen, vlakken, teksten), groep 3 (3D: meshes, morphs, objecten) en de echte kaart met de import.

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
  `C:\Users\jouw naam\AppData\Local\PDOKImport\0.3.0-abc1234\`) en start hem verborgen op de achtergrond.
- De motor luistert alleen op deze computer (`127.0.0.1`) en stopt vanzelf als Archicad sluit.
- Het **logboek** staat in dezelfde map: `engine.log`. Bij een probleem staat daar de oorzaak in.
- Windows zoekt `tar.exe` (zit in Windows 10 en nieuwer) om het uit te pakken, en probeert anders PowerShell.

## Testen (groep 1)

Archicad: **PDOK Import > PDOK Import openen...**. Het palet toont bovenaan de motor en daaronder het **testpaneel**.

1. **Draai de basistests**: leest de versie, de lagen en het actieve venster, telt de elementen per type, en maakt de
   laag **PDOK_test** aan in de map **PDOK Import**. Controleer in Archicad (*Document > Lagen > Laaginstellingen*) dat
   die laag er staat, in een map met die naam.
2. **Naar plattegrond / Naar 3D**: het actieve venster van Archicad hoort mee te wisselen.
3. Teken zelf een lijn of ander element en selecteer het. Daarna:
   - **Selectie lezen**: toont het type, de laag en het ID.
   - **Selectie op de testlaag zetten**: het element krijgt de laag `PDOK_test` en het ID `TEST-1`. Controleer dat in
     Archicad (het ID staat in de instellingen van het element).
   - **Elementen op de testlaag tonen**: toont wat er nu op die laag staat.
   - **Elementen op de testlaag verwijderen** (twee klikken): het element verdwijnt. **Ongedaan maken** in Archicad
     moet het terugbrengen.

## Wat je terugmeldt

- Een schermafbeelding van het testpaneel na de basistests, en van de uitvoer van de overige tests.
- Wat er mislukt: de melding in het paneel (en zo nodig de inhoud van `engine.log`, te vinden via *Over PDOK Import...*).
- Of de lagen, het venster en de ID's in Archicad zelf kloppen met wat het paneel meldt.

## MDID

De ID's in `Sources/RFIX/AddOnFix.grc` zijn die van jouw account. Wijzig ze niet; laat dit bestand ook bij een update
ongemoeid.
