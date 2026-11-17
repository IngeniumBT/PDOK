# PDOK Import voor Archicad - handleiding voor proefgebruikers

Versie 0.25.0 (proefversie). Deze add-on haalt gegevens van PDOK (de BGT, het kadaster, bestemmingsplannen en de 3D Basisvoorziening) op
en zet ze in je Archicad-project: als lijnen en vlakken, als 3D-gebouwen, als terrein en als bomen.

## Wat heb je nodig

- **Windows** en **Archicad 29**.
- Een **internetverbinding** (de gegevens komen van PDOK).
- Een project waarvan het **projectnulpunt op RD (0, 0)** ligt, het landelijke coordinatenstelsel (Rijksdriehoek, EPSG:28992). In deze
  versie wordt alles in RD op het projectnulpunt gezet: staat jouw gebouw ver van RD (0, 0), dan komt de import ook ver van het project
  terecht. Het Survey Point wordt in deze versie niet gebruikt.

## Installeren

1. Download het bestand **`PDOKImport_AC29.apx`** van de pagina Releases: <https://github.com/IngeniumBT/PDOK/releases> (kies de nieuwste versie).
2. Klik met de rechtermuisknop op het bestand > **Eigenschappen**. Staat onderaan **Blokkering opheffen** (*Unblock*)? Zet daar een vinkje en
   klik op OK.
3. Archicad: **Opties > Add-On Manager** (*Options > Add-On Manager*) > tabblad **Edit List of Available Add-Ons** > **Add** > kies het bestand > **OK**.
4. Herstart Archicad als dat gevraagd wordt. Er staat nu een menu **PDOK Import** in de menubalk.

*Een nieuwe versie installeren:* sluit Archicad, vervang het oude `.apx` door het nieuwe (zelfde plek), zet weer *Blokkering opheffen* aan, en start
Archicad. Een oude versie wordt vanzelf opgeruimd.

## Gebruiken

1. Kies **PDOK Import > PDOK Import openen...**. Er opent een palet met een **kaart** en daarnaast de opties. Het **versienummer** staat onder *Hulpmiddelen en instellingen*, net boven de importknop (met een link *Diagnose*); het staat ook bovenaan elk logboek. De eerste keer duurt het
   openen een paar seconden.
2. **Zoek je locatie**: typ een adres bij *Zoek een adres* en klik op *Zoeken*, of verschuif en zoom de kaart (*Uitzoomen* toont heel Nederland).
3. **Teken je importgebied**: klik op *Gebied tekenen* en sleep een rechthoek over de kaart, of houd **Shift** ingedrukt en sleep. Slepen zonder
   Shift verschuift de kaart. Onder de knoppen staat de afmeting (en achter *Uitleg gebied tekenen* staat hoe het werkt). Maximaal 3000 x 3000 m; **begin klein** (bijvoorbeeld 300 x 300 m). Een gebied
   groter dan 600 m wordt in blokken verwerkt. **Esc** annuleert het tekenen.
4. **Kies wat je wilt importeren** (zie hieronder) en klik op **Importeren in Archicad**. De knop staat in een vaste strook onderaan het palet en blijft in beeld als je scrolt; de tekst erboven scrolt apart. Een voortgangsbalk toont hoever het is, met een knop om te stoppen. Eronder loopt een **timer**; na afloop staat daar hoe lang de import duurde, met de tijd per onderdeel (bijvoorbeeld *Klaar in 4:41 (3D-gebouwen 1:05 · 3D-terrein 3:20)*).
5. Het resultaat staat in lagen in de map **PDOK Import** in je project.

Het palet heeft rechtsboven **A-** en **A+** voor de tekstgrootte (de keuze wordt onthouden).

**Kleuren per soort.** De BGT kent per object een *functie*, een *fysiek voorkomen* en een *plus-fysiek voorkomen* (bijvoorbeeld rijbaan, open verharding, betonstraatstenen). De kleuren per soort staan altijd aan (er is geen vinkje meer): zo krijgt elk 2D-vlak een kleur op grond daarvan, en krijgt elke terreinmesh in 3D een eigen oppervlak (`PDOK_weg_asfalt`, `PDOK_groen_heesters`, ...), zodat 2D en 3D bij elkaar passen. Zonder passende regel blijft de kleur van de laag (2D) of van het type (3D). De kleuren staan in een tabel met regels; de standaardtabel is gemaakt voor wat in je gebied voorkomt (wegen op materiaal, fietspad, voetpad, parkeervlak, gras, heesters, bosplantsoen, erf, berm).

Een eigen tabel maak je met **Stijlbestand openen** (onder *Hulpmiddelen en instellingen*): dat schrijft `%LOCALAPPDATA%\PDOKImport\stijlen.json` (de standaardtabel, als het bestand er nog niet is) en opent het in je teksteditor. Elke regel heeft een `naam`, een `kleur` ([rood, groen, blauw] van 0 tot 255) en voorwaarden: `laag` (bijvoorbeeld wegdeel), `functie`, `fysiek`, `plus` en `type` (een voorwaarde past als de tekst erin voorkomt, dus `rijbaan` past bij *rijbaan lokale weg*), `alleen` (2d of 3d) en `prioriteit`. Past meer dan een regel, dan wint die met de hoogste prioriteit en daarna de meest specifieke. Verander je een kleur, importeer dan opnieuw: de 2D-lagen worden opnieuw getekend en de oppervlakken van de stijlen krijgen bij het importeren de nieuwe kleur. Met **Standaardstijlen herstellen** verwijder je je eigen bestand (dan gelden weer alle standaardkleuren en -lagen; je eigen wijzigingen gaan verloren). Met **Stijlbestand bijwerken** vul je je eigen bestand aan met wat de standaardtabel er sinds de vorige keer bij heeft gekregen (nieuwe regels en de deellagen), zonder je eigen kleuren en wijzigingen te veranderen; er komt een kopie `stijlen.json.bak`. Een regel in je bestand zonder sleutel `deellaag` krijgt die automatisch uit de standaardtabel; wil je voor een regel geen eigen laag, zet dan `"deellaag": ""`. Bovenaan het logboek van een import staat welke tabel is gebruikt en hoeveel regels een deellaag hebben. Bestaande vlakken en meshes veranderen niet vanzelf: wis ze eerst (het terrein met *Terrein wissen*). Gebruik **Soorten meten** om te zien welke waarden in jouw gebied voorkomen.

**Lagen per soort (2D).** De BGT-vlakken komen niet op een laag per BGT-laag, maar op een laag per soort (dit staat altijd aan): bijvoorbeeld `BGT_wegdeel_rijbaan`, `BGT_wegdeel_fietspad`, `BGT_wegdeel_voetpad`, `BGT_wegdeel_parkeren`, `BGT_begroeidterreindeel_gras`, `BGT_begroeidterreindeel_heesters`, `BGT_onbegroeidterreindeel_erf`, `BGT_ondersteunendwegdeel_berm`. Alle lagen komen in de map PDOK Import. Welke soort op welke laag komt, bepaalt de regel in de stijltabel met de sleutel `deellaag`; je kunt die in `stijlen.json` aanpassen (zonder `deellaag` blijft een soort op de laag van de BGT-laag zelf, ook als er geen regel past). Het pennummer dat je bij een BGT-laag kiest, geldt voor al zijn deellagen. Lijnen blijven op de laag van de BGT-laag.

**Oppervlakken in de map PDOK Import.** Alle `PDOK_`-oppervlakken (weg, groen, dak, ...) worden bij het importeren in de map *PDOK Import* van de oppervlakken gezet, net als de lagen; ook bestaande die al in de lijst stonden. Een oppervlak dat bij een import niet wordt gebruikt, blijft staan waar het stond tot een volgende import het gebruikt.

**Gebouwen.** In 2D zijn de gebouwen lichtgrijs, lichter dan de wegdelen. In 3D krijgen **platte daken** (een dakvlak dat minder dan 10 graden van horizontaal afwijkt) het oppervlak `PDOK_dak_plat` (grijs) en hellende daken `PDOK_dak`; muren en grondvlak houden `PDOK_muur` en `PDOK_grondvlak`. De kleuren van deze vier komen uit de stijltabel (laag `gebouw`, het `type` is `dak`, `dak_plat`, `muur` of `grondvlak`), zodat je ze zelf kunt aanpassen. Gebouwen die al op de laag `3D_gebouwen` staan, worden bij een volgende import overgeslagen: verwijder ze eerst (selecteer de elementen op die laag en wis ze) als je ze met de nieuwe oppervlakken wilt.

**Je keuzes worden onthouden.** Het palet bewaart de aangevinkte lagen en pennummers, de 3D-opties, de naam van het boomobject, het laatst getekende gebied en de positie van de kaart, en zet ze terug als je het palet weer opent, ook na een update van de add-on. De keuzes staan in `%LOCALAPPDATA%\PDOKImport\instellingen.json`. Met **Standaardinstellingen herstellen** (onder *Hulpmiddelen en instellingen*) zet je alles terug naar de beginwaarden. Het plan (GML-bestand) wordt niet onthouden.

**Een nieuwe versie.** Bij het starten controleert het palet op github.com of er een nieuwere release is; er wordt niets van jou verstuurd. Is er een nieuwere, dan staat er bovenaan een melding met een link naar de releasepagina. Onder *Hulpmiddelen en instellingen* kun je deze controle uitzetten.

## De onderdelen

**Lagen (2D)** - de BGT en het kadaster, als vlakken en lijnen op een eigen laag per soort (bijvoorbeeld `BGT_wegdeel`, `KAD_perceel`). Rechts van
elke laag kun je een **pennummer** invullen; leeg is de standaardpen. *Alles aan* en *Alles uit* per groep. *Perceelnummers als tekst* zet ook de
nummers bij de percelen. *Straatnamen als tekst* zet de straatnamen uit de BGT (de labelpunten van de openbare ruimte) als tekst op de laag `BGT_straatnamen`: hoogte 3,5, pen 1, in het midden uitgelijnd en gedraaid zoals het label in de BGT staat (een tekst die ondersteboven zou staan, wordt een halve slag gedraaid zodat hij leesbaar blijft). Een straat met meer labelpunten krijgt meer teksten. Nogmaals importeren maakt ze dubbel: wis eerst de laag. Het log toont de velden van een label, zodat je kunt zien waar de naam en de hoek vandaan komen. Huisnummers worden niet gemaakt. *Ook viaducten en tunnels (boven en onder maaiveld)* neemt de BGT-objecten mee die niet op maaiveldhoogte liggen (standaard uit: ze liggen in 2D boven op wat eronder ligt). De vlakken worden altijd gekleurd op functie en fysiek voorkomen. Het blok *BGT* is ingeklapt; de kopregel toont hoeveel lagen aan staan en heeft de knoppen *Alles aan* en *Alles uit*. Klik op de kop om de lagen en pennen te zien.

**Bestemmingsplan** - kies met *Kies gml-bestand* een IMRO-bestand (GML) van je bestemmingsplan; *Wissen* haalt het weer weg. *Maatvoering (bouwhoogte e.d.) als tekst*
zet de maatvoeringen als tekst in de tekening. Het bestemmingsplan komt in de plattegrond.

**3D** (de 3D Basisvoorziening van PDOK). Bovenaan staat de keuze voor de **hoogtes**; die geldt voor het terrein, de gebouwen en de bomen:
- **Volgens de 3D Basisvoorziening (NAP)**: alles krijgt zijn echte hoogte in meters NAP.
- **Vlak: bovenkant terrein op 0 m**: de bovenkant van alle terreinmeshes ligt op 0 m, de **onderkant van elk gebouw** komt op 0 m te staan en de **bomen** staan op 0 m. Bruggen en viaducten worden dan overgeslagen. Handig voor een vlakke maquette-ondergrond.

Daarna kies je wat je importeert:
- **Gebouwen** (LoD 2.2, als morphs): elk pand wordt een morph op de laag `3D_gebouwen`, met het BAG-pandnummer als ID. Dak, muur en grondvlak krijgen altijd een eigen oppervlak (`PDOK_dak`, `PDOK_muur`, `PDOK_grondvlak`). Een pand dat uit meerdere delen bestaat (bijvoorbeeld een rijtje met gedeelde
  scheidingsmuren) kan Archicad niet als een geheel maken; zo'n pand wordt dan in **delen** gemaakt (`BAGID-deel1`, `BAGID-deel2`, ...), nog steeds op LoD 2.2. Weigert Archicad een pand om een andere reden (bijvoorbeeld hoekpunten op bijna dezelfde plek), dan wordt het eerst **opgeschoond** (hoekpunten die op elkaar vallen samengevoegd, vlakken die niet in driehoeken te verdelen zijn zonder gat gemaakt of weggelaten, randen die in meer dan twee vlakken zitten teruggebracht; de add-on zoekt dan met proefaanmaken (die direct weer verwijderd worden) de kleinste groep vlakken die in driehoeken moet; de rest blijft een gewoon vlak) en opnieuw op LoD 2.2 geprobeerd, voordat een lager niveau wordt gekozen. Na de import
  meldt het overzicht hoeveel panden op welke manier zijn gemaakt, en of er panden zijn die in de bron geen LoD 2.2 hebben.
- **Terrein** (als meshes, op vier lagen: wegen, landgebruik, begroeiing en water): elk BGT-object wordt een mesh met een eigen oppervlak. De naadsluiting (staat altijd aan) trekt vlakken die tegen elkaar liggen gelijk, zodat er geen spleten zijn. Daarbij bepaalt *Naden: hoogteverschillen tot ... cm gelijktrekken* (onder *Geavanceerd*) (standaard 10 cm) tot welk hoogteverschil dat gebeurt; een groter verschil is een echte stap (een stoeprand, kade of talud) en blijft zoals in de bron. Een hogere waarde sluit de naden strakker, maar trekt echte stappen plat; een lagere waarde (bijvoorbeeld 2 cm) laat vrijwel alles zoals het is. *Terreintypen overslaan* laat soorten weg (gescheiden door `;`).
  *Onderkant* (ook onder *Geavanceerd*) bepaalt of het terrein een massief **volume** wordt, **zijvlakken** krijgt of alleen een **bovenvlak**; de diepte geeft de onderkant
  in meters onder het laagste punt.
- **Hulpmiddelen en instellingen** (uitklapbaar, onderaan het palet): *Terreincontrole* vergelijkt voor het getekende gebied het terrein in Archicad met de bron en meldt wat ontbreekt of afwijkt;
  *Terrein wissen* (twee klikken) verwijdert alle meshes op de terreinlagen; *Meshkwaliteit meten* leest het oppervlak van de terreinmeshes in Archicad en vergelijkt dat met de bron: het verschil in hoogte (in de hoekpunten en in het midden van de brondriehoeken), of er gaten of dubbele oppervlakken zijn, of de afwijkingen aan de rand van een object of erbinnen zitten en bij welke helling, en hoe scherp de driehoeken zijn die Archicad maakt. Er wordt niets veranderd. Teken eerst het gebied dat je wilt meten (liefst tot ongeveer 600 m; groter wordt een steekproef). *Soorten meten* telt voor het getekende gebied welke combinaties van functie, fysiek voorkomen en plus-fysiek voorkomen er in de BGT voorkomen (2D, per laag) en in de 3D-bron (het terrein), met aantallen en oppervlakte; het is bedoeld om te bepalen welke kleuren en oppervlakken per soort nodig zijn. *Scheidingen meten* doet hetzelfde voor de muren en hekken uit de bron: hoe hun onderkant en bovenkant op het terrein liggen (zweven ze of staan ze in de grond), hoe ze op elkaar aansluiten (spleten en hoogteverschillen op de hoeken) en hoe hun vorm is (open randen).
- **Viaducten en bruggen (als dun dek)**: dit gaat nu altijd mee (geen vinkje meer). Het leest de bruggen uit de bron in en maakt ze tot een dunne plaat. Deze functie is nog in ontwikkeling
  (zie Beperkingen).
- **Scheidingen** (muren en hekken): de overige bouwwerken in de 3D Basisvoorziening (CityJSON-type *OtherConstruction*, de BGT-scheidingen zoals muren, kademuren en hekken). Elke scheiding wordt een morph op de laag `3D_scheidingen`, met het oppervlak `PDOK_scheiding`, in het hoogste detailniveau dat de bron heeft (meestal LoD 1.2, een blokvorm). Het log toont de soorten die in het gebied voorkomen. De hoogtekeuze geldt ook hier (bij *Vlak* staat de onderkant van elke scheiding op 0 m), en bij nogmaals importeren worden scheidingen die er al staan overgeslagen. De scheidingen staan in dezelfde grote bestanden als het terrein; het kost daarom iets meer tijd (de eerste keer een minuut, daarna een paar tientallen seconden). De grond onder de gebouwen hoort al bij het terrein.
- **Overige bouwdelen** (overig bouwwerk en gebouwinstallatie uit de BGT: overkappingen, open loodsen, schuren, tanks, silo's, luifels, bordessen en trappen): het BGT-vlak wordt een morph op de laag `3D_bouwdelen`, met **dezelfde oppervlakken als de gebouwen**: de bovenkant `PDOK_dak_plat`, de zijkanten `PDOK_muur` en de onderkant `PDOK_grondvlak` (ze lopen dus mee met de kleuren die je voor gebouwen instelt). **Let op: de BGT geeft hiervoor geen hoogte; de hoogte is een aanname per soort.** Een **blok** (schuur, tank, bordes) staat op het maaiveld en is zo hoog als de regel zegt; een **plaat** (overkapping, open loods, luifel) hangt op die hoogte boven het maaiveld en is een aantal decimeters dik. De aannames staan als regels in de stijltabel (met `vorm`, `hoogte` en `dikte`) en zijn aan te passen in je stijlbestand; een soort zonder regel (bijvoorbeeld een windturbine) wordt overgeslagen en in het log genoemd. Heb je een stijlbestand van een eerdere versie, dan gebruikt de import de standaardregels en neemt *Stijlbestand bijwerken* ze in je bestand op. Het maaiveld komt uit de 3D Basisvoorziening (bij *Vlak (0 m)* 0 m). Objecten die in de BGT boven maaiveld liggen (zoals een luifel of overkapping boven een andere ondergrond) worden meegenomen; objecten onder maaiveld niet. Het log toont eerst wat PDOK voor het gebied teruggeeft en wat is overgeslagen en waarom (beëindigd, te klein, onder maaiveld, buiten het gebied, zonder regel), zodat je ziet of een soort in de BGT ontbreekt of door een filter valt. Nogmaals importeren slaat bestaande over.
- **Groenvlakken** (bomen en heesters over groenvlakken): verdeelt een bibliotheekobject, standaard *Boom stedenbouw 02*, over de groenvlakken van de 3D Basisvoorziening, dezelfde vlakken waar het terrein zijn groene oppervlak van krijgt (volgens de stijltabel: `groen_bos`, `groen_bosplantsoen` en `groen_heesters`). De maten vul je in het palet in (in meter; een komma of een punt mag): afstand, kroon en hoogte per soort, onthouden voor de volgende keer. Een waarde die geen getal is of buiten het bereik valt (afstand 0,5 tot 50 m, kroon 0,2 tot 30 m, hoogte 0,2 tot 60 m), wordt vervangen door de standaardwaarde en in het log gemeld. De standaardwaarden zijn: **bos en bosplantsoen** 6 m kroon, 10 m hoog, minimaal 5,5 m uit elkaar, op de laag `3D_bos`; **heesters** 2 m kroon, 1,5 m hoog, minimaal 2 m uit elkaar, op de laag `3D_heesters`. Elke soort heeft dus een eigen laag, los van `3D_bomen`, zodat je ze in Archicad apart kunt filteren of selecteren. De bomen staan op een willekeurige maar vaste plek (dezelfde import geeft dezelfde posities), met een vrije strook langs de rand van het vlak, niet in gaten, en niet binnen de afstand van een BGT-vegetatiepunt (de losse bomen). De hoogte is die van het terrein (bij *Vlak (0 m)* 0 m); kroon en hoogte verschillen per boom een beetje. Het zijn geen echte bomen maar een weergave van groen: de BGT kent voor vlakken geen boomhoogte. Nogmaals importeren slaat objecten over die er al staan. Het log noemt het aantal per soort en meldt bij meer dan 2000 objecten dat Archicad er traag van kan worden. De standaardwaarden staan in `groen.py` (`SOORTEN`).
- **Lichtmasten** (BGT-palen van het soort lichtmast): op elke lichtmast komt een **lamp** uit je bibliotheek te staan, standaard *Lantaarnpaal 04*. In Archicad is een lantaarnpaal een Lamp en geen Object (een eigen gereedschap), en zo wordt hij ook geplaatst, op de laag `3D_lichtmasten`. Kies de lamp in het zoekvak (typ bijvoorbeeld *lantaarn*); een naam die niet in de bibliotheek staat, wordt geweigerd voordat er iets wordt gemaakt. De lamp staat op de hoogte van het terrein (bij *Vlak (0 m)* op 0 m). De BGT geeft geen hoogte of richting van een paal, dus de lamp komt zoals de bibliotheek hem tekent. Alleen palen op maaiveld in het gebied tellen mee; nogmaals importeren slaat lichtmasten over die er al staan. Let op: lichtmasten staan alleen in de BGT waar de gemeente ze bijhoudt. Vereist add-on 0.21.0 of nieuwer.
- **Bomen** (BGT-vegetatiepunten): op elk punt komt een bibliotheekobject te staan, op de hoogte van het terrein. Gebruik het **zoekvak**: typ een deel van de naam (bijvoorbeeld *boom*) en kies een object uit de lijst. Het zoekt in alle plaatsbare objecten van de bibliotheken die in Archicad geladen
  zijn; onder het vak staat of de naam bestaat. Een naam die niet in de bibliotheek staat, wordt bij het importeren geweigerd, nog voordat er iets wordt gemaakt (standaard *Boom stedenbouw 02*).

De eerste keer dat je 3D importeert voor een gebied wordt een grote tegel van PDOK opgehaald (tientallen MB); dat kan een minuut duren. Daarna staat die in
de cache en gaat het sneller.

## Goed om te weten

- **Archicad lijkt tijdens een import soms vast te lopen.** De add-on werkt via Archicad zelf, en Archicad is dan even bezet. Wacht tot de voortgangsbalk klaar is.
- **Het venster wisselt tijdelijk naar de plattegrond** voor lijnen en vlakken, en springt daarna terug naar waar je was.
- **Ongedaan maken** werkt: elke stap in Archicad is een eigen, ongedaan te maken opdracht.
- **Nogmaals importeren** slaat gebouwen, terrein en bomen over die er al staan (ze herkennen elkaar aan het ID). Lijnen en vlakken worden opnieuw getekend: wis
  ze eerst als je ze vervangt.
- **De eerste import van een gebied is het langzaamst.** De 3D-gegevens komen in grote bestanden (tot ongeveer 100 MB). De import leest zo'n bestand één keer en bewaart alleen het stuk rond je gebied (met een rand van 30 m); terrein, scheidingen, bomen, lichtmasten en bouwdelen gebruiken dat samen. Dat stuk blijft ook op schijf bewaard (map `3d_cache\uitsneden` in `%LOCALAPPDATA%\PDOKImport`, hoogstens 40 stuks), dus een volgende import van hetzelfde gebied (of een iets kleiner gebied) hoeft het grote bestand niet meer te lezen. Het log meldt dit (*uitsnede uit de cache*).
- **Alles komt in de map PDOK Import** (lagen), zodat je het makkelijk kunt tonen, verbergen of verwijderen.

## Beperkingen van deze proefversie

- **Het coordinatenstelsel:** alleen een project met het nulpunt op RD (0, 0); het Survey Point wordt niet gebruikt.
- **Viaducten** en bruggen worden in sommige gevallen nog niet goed gemaakt (bijvoorbeeld als dek en weg op dezelfde hoogte liggen in de bron).
- Bij de keuze **Vlak (0 m)** worden bruggen en viaducten niet meegenomen.
- **Alleen Windows en Archicad 29.**

## Problemen oplossen

- **Het palet blijft leeg of toont een foutmelding.** De motor draait niet goed. Kies **PDOK Import > Over PDOK Import...**: daar staat de map en het
  logboek (`engine.log`). Open dat bestand en stuur de laatste regels mee als je hulp vraagt. Beveiligingssoftware die programma's in
  `%LOCALAPPDATA%\PDOKImport` blokkeert, is een bekende oorzaak.
- **"Archicad antwoordt niet"** - er staat waarschijnlijk een dialoog open in Archicad. Sluit die en probeer opnieuw.
- **De kaart toont geen achtergrond of de lagenlijst laadt niet** - controleer de internetverbinding. De knop *Openen in browser* opent dezelfde kaart in je browser.
- **Een import mislukt of is onvolledig** - de voortgangsmelding noemt de reden. Probeer een kleiner gebied.

## Feedback geven

Het meest helpend is: de **versie** (PDOK Import > Over PDOK Import...), wat je deed (welk gebied en welke opties), wat je verwachtte en wat er gebeurde, een
**schermafbeelding**, en zo nodig de laatste regels uit `engine.log`.

## Verwijderen

Haal het bestand uit de **Add-On Manager** (selecteer het en klik op *Remove*) en verwijder het `.apx`. De uitgepakte onderdelen en de cache staan in
`%LOCALAPPDATA%\PDOKImport`; die map mag je verwijderen.

## Bronnen en licenties

De gegevens komen van PDOK (BGT, kadaster, bestemmingsplannen, 3D Basisvoorziening en de BRT-achtergrondkaart); raadpleeg PDOK voor de gebruiksvoorwaarden.
Delen van de bouwopzet komen uit het open-sourceproject Tapir (MIT) en het sjabloon van Graphisoft (MIT); zie `THIRD_PARTY_NOTICES.md`.
