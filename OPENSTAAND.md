# Openstaande punten en bevindingen (PDOK Import)

Dit bestand legt vast wat er nog open staat en wat we hebben gemeten, zodat het later opgepakt kan worden. Bijgewerkt bij versie 0.22.0.

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
2. **Straatnamen als tekst.** Collectie `openbareruimtelabel`: labelpunten met de straatnaam en de hoek waaronder het label staat. Eventueel ook huisnummers (`pand_nummeraanduiding`).
3. **Overige bouwwerken in 3D: een eerste versie is gebouwd in 0.22.0** (wacht op de test van de gebruiker). De hoogte is een aanname per soort in de stijltabel; de BGT heeft er geen en de 3D Basisvoorziening kent een overkapping alleen als terreinvlak. Mogelijke verbeteringen: bij een overkapping ook palen of wanden, een echte trap (helling) voor een toegangstrap, en een hoogte uit het AHN.
4. **3D-hagen.** Collecties `vegetatieobject_lijn` en `vegetatieobject_vlak`, soort `haag`: als morph met een aangenomen hoogte.
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
De drempel `NAAD_MAX_VERSCHIL` staat op 0,10 m (was 0,75 m; een stap van 50 cm werd daardoor platgetrokken). Instelbaar in het palet; zie README 0.17.4.
