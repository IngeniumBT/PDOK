# PDOK Import 0.29.2 (proefversie)

Eén Archicad-add-on (`PDOKImport_AC29.apx`) die gegevens van PDOK in je project zet, met een kaart in een palet in Archicad.

## Nieuw sinds 0.20.1

**Nulpunt en dubbelen**
- **Verschoven tweede import opgelost.** Archicad meet alle coördinaten vanaf een virtueel nulpunt dat bij het openen van een bestand wordt gezet. De add-on leest die verschuiving nu bij elke import en corrigeert ervoor. Een import na het opslaan en heropenen van het project komt dus weer op dezelfde plek als de eerste.
- **Geen dubbelen meer bij nogmaals importeren (2D).** BGT-vlakken krijgen een ID en worden overgeslagen als ze er al staan; lijnen worden herkend aan hun vorm en teksten aan hun plek. Ook objecten op de grens tussen twee blokken komen niet meer dubbel. Het log meldt wat is overgeslagen.

**3D**
- **Groenvlakken:** bomen en heesters verdeeld over de groenvlakken van de 3D Basisvoorziening (bos, bosplantsoen, heesters), met instelbare maten in het palet en eigen lagen (`3D_bos`, `3D_heesters`).
- **Lichtmasten** als lamp uit je bibliotheek op de BGT-palen, en **overige bouwdelen** (overkappingen, loodsen, tanks, trappen) met de materialen van de gebouwen.
- **Terrein:** uitschieters in de hoogte worden gladgestreken (instelbaar, standaard 30 cm), en de naadsluiting herstelt meshes in plaats van ze terug te zetten, zodat de aansluiting tussen meshes beter blijft. Echte sprongen in de brongegevens (bijvoorbeeld tussen weg en groen) blijven bestaan.
- Sneller importeren als je meerdere 3D-onderdelen tegelijk kiest.

**2D en palet**
- **Straatnamen als tekst** (hoogte 3,5, pen 1, gedraaid zoals het label in de BGT).
- Een rustiger palet: het blok *BGT* is inklapbaar met *Alles aan* en *Alles uit*; kleuren per soort en het dunne dek voor viaducten staan standaard aan.
- Diagnose in het log: het virtuele nulpunt, het Survey Point en de positie van een voorbeeldmesh.

## Installeren

1. Download hieronder **`PDOKImport_AC29.apx`**.
2. Rechtermuisknop op het bestand > **Eigenschappen** > zet **Blokkering opheffen** aan > OK.
3. Archicad: **Opties > Add-On Manager** > tabblad *Edit List of Available Add-Ons* > **Add** > kies het bestand > OK. Herstart Archicad als dat gevraagd wordt.
4. Kies **PDOK Import > PDOK Import openen...**

Een nieuwe versie installeren: sluit Archicad, vervang het oude `.apx` door het nieuwe, zet weer *Blokkering opheffen* aan en start Archicad. De handleiding staat in de bijlage (`Handleiding_PDOK_Import.docx`) en in `HANDLEIDING.md`.

## Let op

- Alleen **Windows** en **Archicad 29** (getest op build 3200 NED).
- Het projectnulpunt moet op **RD (0, 0)** liggen; het Survey Point wordt nog niet gebruikt. Het model komt daardoor op RD-coördinaten (ver van het nulpunt) te staan. Graphisoft meldt dat Archicad vanaf enkele kilometers van het nulpunt beeldproblemen kan geven (zoals flikkeren in 3D). De add-on corrigeert wel voor het virtuele nulpunt, zodat de plaatsing klopt.
- Vlakken die met een eerdere versie zijn gemaakt hebben geen ID en worden bij de eerste import met deze versie nog één keer opnieuw getekend; wis de laag als je schoon wilt beginnen. Een object dat bij PDOK is aangepast, wordt niet bijgewerkt.
- **Viaducten en bruggen** worden in sommige gevallen nog niet goed gemaakt.
- De eerste keer ophalen van het terrein kan een minuut duren (grote bestanden bij PDOK). Begin met een klein gebied (bijvoorbeeld 300 x 300 m).

## Privacy en bronnen

- Bij het starten controleert het palet op github.com of er een nieuwere versie is; er wordt niets van jou verstuurd. Dat kun je uitzetten onder *Hulpmiddelen en instellingen*.
- De gegevens komen van PDOK (BGT, kadaster, bestemmingsplannen, 3D Basisvoorziening en de BRT-achtergrondkaart); raadpleeg PDOK voor de gebruiksvoorwaarden. Zie `THIRD_PARTY_NOTICES.md` voor de gebruikte open-sourceonderdelen.

## Feedback

Meld de **versie** (*PDOK Import > Over PDOK Import...*), wat je deed (gebied en opties), wat je verwachtte en wat er gebeurde, met een schermafbeelding en zo nodig de laatste regels uit `engine.log`.
