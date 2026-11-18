# Openstaande punten en bevindingen (PDOK Import)

Dit bestand legt vast wat er nog open staat en wat we hebben gemeten, zodat het later opgepakt kan worden. Bijgewerkt bij versie 0.27.1.

## Wat af is
Kaart en palet, 2D-lagen (BGT, kadaster, bestemmingsplan), teksten, bomen (met zoekvak), 3D-gebouwen (LoD 2.2, met terugvalstappen en zoeken naar de kleinste groep driehoeken),
3D-terrein (meshes, naadsluiting, viaducten als dun dek, vlak terrein), scheidingen (muren, hekken), hoogtekeuze (NAP of vlak op 0 m), timer, instellingen onthouden, melding bij een nieuwe versie,
handleiding (Markdown en Word), meetinstrumenten (terreincontrole, meshkwaliteit, scheidingen).

## Nieuwe wens: stijlen per soort (functie, fysiek voorkomen, plus-fysiek voorkomen)
Idee: een stijltabel (regels met voorwaarden, een naam en een kleur) die zowel de 2D-vulkleur als het 3D-oppervlak bepaalt; de meest specifieke regel wint, zonder regel valt het terug op de kleur van de laag. Het bestand komt naast de instellingen te staan, zodat je kleuren kunt aanpassen zonder opnieuw te bouwen. 3D: per mesh een eigen oppervlak (`PDOK_<naam>`), alleen aangemaakt voor wat in het gebied voorkomt. Eerst toepassen op 2D en het terrein in 3D; scheidingen (op `bgt_type`) later.
Stand: af en bevestigd door de gebruiker: *Soorten meten* (0.17.5), de stijltabel met palet voor 2D en terrein in 3D (0.18.0), gebouwkleuren met platte en hellende daken (0.18.1), oppervlakken in de map PDOK Import en 2D-lagen per soort (0.19.0), en het meegroeien van een oud stijlbestand met de knop *Stijlbestand bijwerken* (0.19.1).
Palet (0.20.0): opnieuw ingedeeld volgens het goedgekeurde voorstel (een canvas met twee borden).
Nog te doen: de scheidingen in 3D op `bgt_type` (muur, hek, kademuur) en zo nodig meer soorten (water, kunstwerken) zodra gebieden daarvoor waarden laten zien. Eventueel: de bovenkant van een stijlbestand een versie laten bijhouden zodat een nieuwe standaardkleur ook bij een eigen bestand kan worden aangeboden.

## Ideeën voor later (nog niet ingepland)
Uit de verkenning van de BGT-collecties bij PDOK (puntobjecten, vegetatie en labels). Eerst een overzicht van wat er is; wat gewenst is, staat hieronder.

1. **Lichtmasten in 3D: gebouwd in 0.21.0** (als Lamp-element, standaard *Lantaarnpaal 04*; wacht op de test van de gebruiker). Eventueel later ook andere palen en masten (`mast`), op dezelfde manier.
2. **Straatnamen als tekst: gebouwd in 0.25.0** (wacht op de test van de gebruiker; de veldnamen en de eenheid van de hoek zijn nog niet aan echte data getoetst). Oorspronkelijke notitie: Collectie `openbareruimtelabel`: labelpunten met de straatnaam en de hoek waaronder het label staat. Eventueel ook huisnummers (`pand_nummeraanduiding`).
3. **Overige bouwwerken in 3D: een eerste versie is gebouwd in 0.22.0** (wacht op de test van de gebruiker). De hoogte is een aanname per soort in de stijltabel; de BGT heeft er geen en de 3D Basisvoorziening kent een overkapping alleen als terreinvlak. Mogelijke verbeteringen: bij een overkapping ook palen of wanden, een echte trap (helling) voor een toegangstrap, en een hoogte uit het AHN.
4. **3D-hagen.** Collecties `vegetatieobject_lijn` en `vegetatieobject_vlak`, soort `haag`: als morph met een aangenomen hoogte.
5a. **Bomen in groenvlakken: gebouwd in 0.24.0** (wacht op de test van de gebruiker). Maten en afstanden zijn aannames die je in het palet kunt aanpassen (standaardwaarden in `groen.py`); mogelijk later per soort een eigen object en een hoogte uit het AHN.
5. **Boomhoogte uit het AHN.** In de BGT hangt aan bomen geen soort, hoogte of kroon; alleen het soort (`boom` of `haag`) en registratiegegevens. Een hoogte zou kunnen worden afgeleid uit het AHN (oppervlakmodel min maaiveld; PDOK biedt het als WCS). Niet uitgeprobeerd.
6. **Technisch: de BGT-API-basis.** PDOK noemt `api.pdok.nl/kadaster/bgt/ogc/v1` nu de canonieke basis; wij gebruiken nog `api.pdok.nl/lv/bgt/ogc/v1`. Dat werkt nu nog; bij een volgende versie omzetten.
7. *Optioneel:* *Soorten meten* uitbreiden met puntobjecten, zodat je per gebied ziet welke soorten palen, putten, borden en meubilair er staan (nu telt het alleen de vlaklagen en de bomen).

Aandachtspunt: bomen, palen en straatmeubilair zijn in de BGT zogenoemde plus-objecten (het BGT-type staat in de voorbeelden op *niet-bgt* en de soort in `plus_type`); ze worden door gemeenten niet overal bijgehouden. In sommige gebieden ontbreken ze dus in de bron.

## Nog open, in de volgorde die is afgesproken
1. **Meer Archicad-versies (27, 28, 30)**: bouwen voor die versies; alleen 29 is getest.
2. **Survey Point (projectlocatie)**: staat uit. De code (omrekening via `GetSurveyPointTransformation`) is klaar, maar gaf bij een echt verplaatst Survey Point niet wat de bedoeling was; er is een project met een ingevuld Survey Point nodig om te testen.
3. **Viaducten en bruggen**: geparkeerd. Bevindingen: een dek komt in de bron in meerdere stukken (onder een ID, soms met stukken van 0 m2), is niet vlak (tot 4 m hoogteverschil binnen een dek), en wat eronder ligt zit op bijna dezelfde hoogte.
4. **Mac**: eerst een kleine pilot met een testgebruiker, pas als de rest klaar is (andere Python, ondertekenen, `127.0.0.1` in het palet).

## Bevindingen uit de meshkwaliteit-meting (gebied x 259808 tot 259968, y 482770 tot 482887, na versie 0.17.4)
- **Goed:** 99,3% van het terreinoppervlak ligt binnen 1 cm van de bron, 99,8% binnen 5 cm, 100% binnen 20 cm (gewogen naar oppervlak in plattegrond). Op de hoekpunten is het gemiddelde verschil 0,0 tot 0,3 mm; 2 van 8.673 hoekpunten wijken meer dan 5 cm af (was 10 van 12.666 vooraf).
- **Gaten:** er zijn er nog 1 (0 m2). Eerder leken er 324 (335 m2); dat waren verticale brondriehoeken (kademuurtjes, taluds), die een mesh niet kan weergeven.
- **Afwijkingen hangen af van de helling:** onder 30 graden 0,4% boven 5 cm; 30 tot 60 graden 4,3%; 60 tot 80 graden 6,8%; vanaf 80 graden 11,6%. Oorzaak: dezelfde punten, maar Archicad verdeelt ze anders in driehoeken. Een mogelijke verbetering (nog niet gebouwd): de bronranden van steile driehoeken als lijnen (sublines met twee punten) meegeven. Raakt ongeveer 4,5% van het oppervlak, maakt meshes zwaarder.
- **Nog te onderzoeken:**
  - Een hoekpunt van PlantCover 01KPTKEVQQB2QZ13DV9GBC3VP1 bij (259906.1, 482786.0) ligt 0,8 m te hoog (bron 41,00 m). Dit bleef bestaan na het verlagen van de naaddrempel, dus het zit niet in het gelijktrekken van naden.
  - Overlap: 83 driehoeken (0,4%) liggen dubbel op dezelfde hoogte en dat ontstaat bij het importeren (de bron overlapt daar niet). Betrokken meshes: 01KPMC1C8M07 en 01KPMC1C8FBC; 01KP7PWZKW40 met 01KPHVFAE87J en 01KPMC1CC0WH; 01KPHVEWHT90 met 01KPHVFP1NFM. Een deel van die meshes is waarschijnlijk teruggezet naar de oorspronkelijke omtrek of zonder naadsluiting gemaakt.
  - Archicad maakt ongeveer twee keer zoveel driehoeken als de bron (21.053 tegen 10.718), met 23% scherper dan 5 graden. De hoogte lijdt daar niet onder; wel een eventuele reden om meshes lichter te maken.
- **Scheidingen** in dit gebied: 11 muren, onderkant gemiddeld +1 cm op het terrein in de bron, alle 11 met open randen (alleen zijkanten en bovenkant), geen spleten of hoogteverschillen op de hoeken.

## Naadsluiting
Uitschieters (0.26.0): `terrein.gladstrijken_uitschieters`, standaard 0,30 m, instelbaar in het palet (0 = uit). Gemeten op tegel 260000_482000 (970.000 hoekpunten): bij 0,30 m worden 988 hoekpunten (0,10 %) aangepast (gemiddeld 0,39 m, hoogstens 1,5 m); in 300 x 300 m rond 260250 / 482850 zijn dat er 27. De grote sprongen (37 posities in dat gebied, 0,5 tot 0,9 m, op twee plekken 2,5 en 3,7 m, meestal weg tegen groen) zijn echte discontinuïteiten in de bron en blijven bestaan. Mogelijke vervolgstappen: de spleten dichten met zijwanden, of een talud van 0,3 tot 1 m tussen weg en groen.
De drempel `NAAD_MAX_VERSCHIL` staat op 0,10 m (was 0,75 m; een stap van 50 cm werd daardoor platgetrokken). Instelbaar in het palet; zie README 0.17.4.

Naadsluiting, herstel (0.27.0): in het gebied van het gelogde voorbeeld (x 260204-260411, y 482286-482500, uitschieters 10 cm) werden 23 van 312 meshes teruggezet naar hun oorspronkelijke omtrek, waardoor daar de aansluiting verloren ging. Oorzaak voor de meeste: een buurpunt dat al een hoekpunt van de eigen mesh was (samengevoegd binnen de marge) werd nog eens als tussenpunt in een nabije eigen rand ingevoegd, waardoor de omtrek zichzelf raakte. Dat wordt nu overgeslagen. Daarnaast probeert `herstel_mesh` een ongeldige omtrek lokaal te herstellen (korte randen weg, raakpunten terug naar de oorspronkelijke plek of weg, anders 1 tot 4 cm naar binnen) voordat teruggezet wordt. Resultaat in dat gebied: 13 meshes hersteld, 1 nog teruggezet (aan de gebiedsrand). De echte sprongen in de bron blijven: bij (260316.7, 482376.9) en (260318.8, 482377.1) loopt het verschil tussen twee stoepdelen op van 0,51 naar 0,58 m. Die vragen om zijwanden of een talud (open punt).

## Gepland moment: 18 november 2026, groot probleem gemeld
Stand op dit moment: versie 0.27.0 (naadherstel) is geleverd (`pdok-import-0.27.0-naadherstel.zip`), nog niet door de gebruiker bevestigd; 0.26.0 (uitschieters) ook nog niet bevestigd. De gebruiker heeft een groot probleem met de plugin ontdekt en wil daar later mee verder. De details volgen nog (nog niet beschreven), dus eerst vragen: wat gebeurt er, in welke versie, met welk gebied/log/screenshot. Nog niets onderzocht of aangepast.
Daarnaast nog open: zijwanden of talud bij echte sprongen in het terrein (bijvoorbeeld 0,51 tot 0,58 m bij 260316.7 / 482376.9), uitschieters-waarde 30 cm aanraden (log stond op 10 cm), en de rest van de lijst hierboven.

Het probleem (18 nov): de eerste import komt op de juiste plek. Project opslaan, Archicad afsluiten, opnieuw starten en project openen: een tweede import komt dan niet op de juiste plek. Vermoeden: de oorsprong/referentie voor RD naar Archicad-coordinaten wordt tijdens de eerste import onthouden (geheugen of cachebestand) en na een herstart niet of anders bepaald. Nog te onderzoeken.
Bevindingen tot nu toe (nog geen oorzaak): de add-on schrijft RD-coordinaten rechtstreeks als projectcoordinaten (`GEOREFERENTIE = "rd"`, `PROJECTLOCATIE_GEBRUIKEN = False`, Survey Point wordt niet gelezen). In de Python-motor staat daardoor geen onthouden oorsprong die een herstart kan wijzigen. Het verschil moet dus uit Archicad komen (bijvoorbeeld Survey Point, projectnulpunt, gebruikersoorsprong, Project North of hoogte-referentie in het geopende project) of uit het gebied dat de kaart na de herstart gebruikt. Te vragen: hoe groot en in welke richting is de afwijking, geldt het voor alle onderdelen (2D, gebouwen, terrein), en welke Survey Point-waarden en gebruikersoorsprong heeft het project voor en na de herstart. Eerste test voor later: na de herstart dezelfde import als de eerste en de log vergelijken (gebied en eerste coordinaten).
Gegevens van de gebruiker (18 nov): afwijking zeer groot, alsof het nulpunt van de tweede import in de eerste import ligt; geldt voor 2D en 3D; Location Settings ongewijzigd (Survey Point 0,0,0, Project North 90 graden). Logs 1e en 2e import (versie 0.26.0): beide sturen dezelfde RD-coordinaten (bijvoorbeeld basePoint 253260.95, 471138.03 in beide), gebied 1: x 253092-253472, y 470936-471436; gebied 2: x 253230-253719, y 470950-471433. De add-on stuurt dus identieke coordinaten; het verschil ontstaat in Archicad. Het tweede log toont 16 bestaande panden die worden overgeslagen. Versie 0.27.1 logt de Survey Point-matrix en de werkelijke positie van een voorbeeldmesh; volgende stap: logs van een nieuwe 1e en 2e import (met herstart ertussen) vergelijken.

