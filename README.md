# PDOK Import - Archicad Add-On

E©n `.apx`-bestand dat PDOK-gegevens in Archicad importeert. De add-on bevat een **motor** (Python, ingebouwd in het
`.apx`) en toont de kaart in een **palet in Archicad**.

## Stand van zaken

- **Versie 0.1:** skelet (menu en melding). Gelukt.
- **Versie 0.2 (stap A):** de motor zit in het `.apx`, wordt bij het eerste gebruik uitgepakt en gestart, en een testpagina
  met kaart staat in een palet. De echte kaart en import komen in de volgende stappen.

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
  `C:\Users\jouw naam\AppData\Local\PDOKImport\0.2.0-abc1234\`) en start hem verborgen op de achtergrond.
- De motor luistert alleen op deze computer (`127.0.0.1`) en stopt vanzelf als Archicad sluit.
- Het **logboek** staat in dezelfde map: `engine.log`. Bij een probleem staat daar de oorzaak in.
- Windows zoekt `tar.exe` (zit in Windows 10 en nieuwer) om het uit te pakken, en probeert anders PowerShell.

## Testen (stap A)

1. Archicad: menu **PDOK Import > PDOK Import openen...**. De eerste keer duurt dat een paar seconden (uitpakken).
2. Er opent een palet "PDOK Import" met drie onderdelen:
   1. **De motor:** de status en de gegevens van de motor (versie van Python, het programma, het proces-ID).
   2. **Internet vanuit de motor:** de knop *Test verbinding met PDOK*.
   3. **Kaart in dit palet:** een kaart met de PDOK-achtergrondkaart. Slepen verschuift de kaart; met **Shift**
      ingedrukt teken je een rechthoek.
3. **Over PDOK Import...** toont de versie, de poort, de map en het logboek van de motor.

## Wat je terugmeldt

- Opent het palet, en wat staat erin? (een schermafbeelding is ideaal)
- Staat bij onderdeel 1 "de motor draait"? Lukt de internettest? Verschijnt de kaart met tegels, en kun je met Shift een
  rechthoek tekenen? Verschuift de kaart bij gewoon slepen?
- Een foutmelding bij het openen? Plak de tekst, en de inhoud van `engine.log`.

## MDID

De ID's in `Sources/RFIX/AddOnFix.grc` zijn die van jouw account. Wijzig ze niet; laat dit bestand ook bij een update
ongemoeid.
