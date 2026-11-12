# PDOK Import - Archicad Add-On (skelet)

Dit is het **skelet** van de add-on: één menu "PDOK Import" met de opdracht "Over PDOK Import...", die een melding
toont. Het enige doel is te bewijzen dat de hele keten werkt (bouwen met GitHub, het `.apx` toevoegen in de
Add-On Manager, het menu in Archicad). De echte functies komen er daarna in.

## Stap 1: een GitHub-repository maken

1. Ga op github.com naar **New repository** (de groene knop of het plusje rechtsboven).
2. Naam bijvoorbeeld `pdok-import-archicad`. Kies *Private* of *Public*. Laat de rest leeg. **Create repository**.

## Stap 2: de bestanden uploaden

1. Pak de ZIP uit. Je krijgt een map met o.a. `Sources`, `Tools`, `CMakeLists.txt` en een map `.github`.
2. Klik in je nieuwe, lege repository op **uploading an existing file**.
3. **Sleep de inhoud van de uitgepakte map** (alle mappen en bestanden, ook `.github`) in het venster.
   Gebruik slepen en niet "choose your files": dat neemt geen mappen mee.
4. Controleer onderaan dat er 17 bestanden staan en klik op **Commit changes**.
5. Controleer dat het bestand `.github/workflows/build.yml` in je repository staat. Zo niet: **Add file > Create new
   file**, typ als naam `.github/workflows/build.yml` en plak de inhoud erin.

## Stap 3: laten bouwen

1. Open het tabblad **Actions**. De bouw ("Bouw de add-on") start vanzelf na de upload (soms moet je eerst de
   workflows toestaan: de knop *I understand my workflows, go ahead and enable them*). Je kunt hem ook
   starten via *Bouw de add-on > Run workflow*.
2. Het duurt ongeveer 5 tot 10 minuten. Een **groen vinkje** is gelukt, een **rood kruis** is mislukt:
   open die run, klik op de mislukte stap, en kopieer de laatste ~40 regels (of de regels met `error`).
3. Bij een gelukte bouw staat onderaan de runpagina onder **Artifacts** het bestand `PDOKImport_AC29_Win`.
   Download dat: het is een ZIP met daarin `PDOKImport_AC29.apx`. Pak het uit.

## Stap 4: de add-on in Archicad laden

1. Klik met de rechtermuisknop op het `.apx` > **Eigenschappen**. Staat onderaan "Blokkering opheffen"
   (*Unblock*)? Zet daar een vinkje en klik OK.
2. Archicad: **Opties > Add-On Manager > tabblad "Edit List of Available Add-Ons" > Add**, kies het `.apx`, **OK**.
3. Herstart Archicad als het dat vraagt. Er hoort een menu **PDOK Import** te zijn met de opdracht
   **Over PDOK Import...**. Die toont een melding met de versie.

## De MDID (belangrijk)

Elke add-on heeft twee ID's, de **MDID** (developer ID en local ID), in `Sources/RFIX/AddOnFix.grc`. In dit skelet staan
de voorbeeldwaarden `1` en `1`. Volgens de README van het Graphisoft-sjabloon werkt een add-on met die
voorbeeldwaarden **alleen in de demoversie van Archicad**.

- **Testen kan dus meteen in demo-modus**: start Archicad met `Archicad.exe -DEMO` (bijvoorbeeld via een
  snelkoppeling met `-DEMO` achter het pad).
- **Voor een gewone Archicad en voor verspreiding heb je eigen ID's nodig.** De README van het sjabloon verwijst
  daarvoor naar <https://archicadapi.graphisoft.com/profile/add-ons> (aanmelden met een Graphisoft-account). Pas dan de
  twee getallen in `AddOnFix.grc` aan en laat opnieuw bouwen (de bouw start vanzelf bij elke wijziging).
  **Gebruik niet de ID's van een ander project** (zoals Tapir): die horen bij hun add-on.

## Wat je terugmeldt

- Bouw: groen of rood? Zo rood: de foutregels.
- Archicad: is de add-on geladen, verschijnt het menu, en wat toont "Over PDOK Import..."? Zo niet: welke melding
  geeft de Add-On Manager?
