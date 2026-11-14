# Openstaande punten en bevindingen (PDOK Import)

Dit bestand legt vast wat er nog open staat en wat we hebben gemeten, zodat het later opgepakt kan worden. Bijgewerkt bij versie 0.17.4.

## Wat af is
Kaart en palet, 2D-lagen (BGT, kadaster, bestemmingsplan), teksten, bomen (met zoekvak), 3D-gebouwen (LoD 2.2, met terugvalstappen en zoeken naar de kleinste groep driehoeken),
3D-terrein (meshes, naadsluiting, viaducten als dun dek, vlak terrein), scheidingen (muren, hekken), hoogtekeuze (NAP of vlak op 0 m), timer, instellingen onthouden, melding bij een nieuwe versie,
handleiding (Markdown en Word), meetinstrumenten (terreincontrole, meshkwaliteit, scheidingen).

## Nieuwe wens: stijlen per soort (functie, fysiek voorkomen, plus-fysiek voorkomen)
Idee: een stijltabel (regels met voorwaarden, een naam en een kleur) die zowel de 2D-vulkleur als het 3D-oppervlak bepaalt; de meest specifieke regel wint, zonder regel valt het terug op de kleur van de laag. Het bestand komt naast de instellingen te staan, zodat je kleuren kunt aanpassen zonder opnieuw te bouwen. 3D: per mesh een eigen oppervlak (`PDOK_<naam>`), alleen aangemaakt voor wat in het gebied voorkomt. Eerst toepassen op 2D en het terrein in 3D; scheidingen (op `bgt_type`) later.
Stand: *Soorten meten* is gebouwd (0.17.5). Volgende stap: de echte waarden bekijken en samen een palet vaststellen, daarna de stijltabel bouwen.

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
