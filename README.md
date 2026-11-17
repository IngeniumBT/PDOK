# PDOK Import - Archicad Add-On

Eén `.apx`-bestand dat PDOK-gegevens in Archicad importeert. De add-on bevat een **motor** (Python, ingebouwd in het
`.apx`) en toont de kaart in een **palet in Archicad**.

## Stand van zaken

Wat nog openstaat en wat we hebben gemeten staat in **OPENSTAAND.md**.


- **0.1:** skelet (menu en melding). Gelukt.
- **0.2:** de motor (Python) zit in het `.apx`, wordt gestart, en de kaart staat in een palet in Archicad. Gelukt.
- **0.3 (groep 1):** de eerste **opdrachten van de add-on zelf**: lagen (lezen, aanmaken in een map), het actieve venster
  (lezen, wisselen), elementen (per type lezen, details lezen, laag en ID zetten, verwijderen) en de selectie. De motor
  roept ze aan via Archicads JSON-interface (namespace `PDOKImport`). Een testpaneel in het palet laat elke opdracht proberen.
- **0.24.0: bomen en heesters in groenvlakken.** Nieuwe module `groen.py` en een vinkje *Groenvlakken* in het 3D-deel van het palet (met een zoekvak voor het bibliotheekobject, standaard *Boom stedenbouw 02*, en een vinkje per soort). De groenvlakken komen uit de 3D Basisvoorziening (dezelfde uitsnede als terrein en gebouwen), de soort uit de stijltabel (`groen_bos`, `groen_bosplantsoen` en `groen_heesters`). Per vlak wordt een punt gekozen in een willekeurige driehoek (naar oppervlakte; dus nooit in een gat), met een minimale afstand (bos 5,5 m, heesters 2 m), een vrije strook langs de rand van 0,35 x de kroon en niet binnen de afstand van een BGT-vegetatiepunt; de hoogte is die van de driehoek. Willekeurig maar vast (seed uit het vlak-ID), Element-ID `GROEN-<id>-<nummer>`, lagen `3D_bos` en `3D_heesters` (apart van `3D_bomen`), maten kroon/hoogte met een kleine variatie en een willekeurige draaiing. Meer dan 2000 objecten geeft een melding in het log. Geen C++-wijziging.
- **0.23.3: knoppen in de BGT-kop.** Bij een lange tekst als "(0 van 45 lagen aan)" liepen *Alles aan* en *Alles uit* onder elkaar. De tekst is korter ("(0 van 45 aan)") en de knoppen blijven altijd naast elkaar. Geen C++-wijziging.
- **0.23.2: een rustiger palet.** Het blok *BGT* in *2D · BGT en Kadaster* is inklapbaar (standaard dicht); de kopregel toont "(alle lagen aan)" of "(n van m lagen aan)" en houdt *Alles aan* en *Alles uit* zichtbaar. De vinkjes *Kleuren per soort* (2D en 3D) en *Viaducten en bruggen meenemen (als dun dek)* zijn vervallen: ze staan altijd aan (`stijl2d`, `stijl3d` en `terreindekken` worden altijd waar verstuurd). Oude opgeslagen instellingen met deze vinkjes worden genegeerd. Geen C++-wijziging.
- **0.23.1: bouwdelen in groepen.** `bouwdelen.maak_alle` maakte elk bouwdeel met een eigen `CreateMorphs`-opdracht (41 bouwdelen kostten 4 tot 7 s, tegen 1 tot 3 s voor 71 gebouwen die in groepen gaan). Nu gaan ze in groepen van 25 (`bouwdelen.GROEP`); een bouwdeel dat in een groep niet lukt, wordt apart opnieuw geprobeerd, zo nodig met boven- en onderkant als driehoeken. Geen C++-wijziging.
- **0.23.0: sneller importeren met meerdere 3D-onderdelen.** Terrein, scheidingen, de terreinhoogte voor bomen, lichtmasten en bouwdelen lazen elk het volledige tegelbestand van de 3D Basisvoorziening (tot ~100 MB CityJSON) opnieuw in. Nu wordt een groot bestand (vanaf 20 MB; `drie_d.SNEL_MB`) eenmaal gelezen en teruggebracht tot een
  **uitsnede**: de objecten die het gebied met een rand van 30 m raken (afgerond op een raster van 50 m), met een eigen hoekpuntenlijst en met de ouders en kinderen van die objecten (`drie_d.maak_uitsnede`, `drie_d.lees_json`). Die wordt in het geheugen en op schijf bewaard (`<cache>\uitsneden\*.pkl`, de sleutel bevat het bestand, de grootte, de datum en het
  gebied; hoogstens 40 stuks). `terrein.verzamel`, `terrein.vlak_niveau`, `terrein.json_van_tegel`, `drie_d.verzamel` en `bomen.hoogtes_uit_terreindata` (nieuwe parameter `uitsnede_gebied`, door bomen, lichtmasten en bouwdelen gevuld met het gebied van de import) gebruiken dit. De blokkenimport voor grote gebieden en kleine bestanden
  (de gebouwen) lezen zoals voorheen. Gemeten met een synthetische tegel van 18 tot 57 MB: dezelfde uitkomsten als helemaal lezen (terreinobjecten, hoogtes, panden), de tegel wordt per import eenmaal gelezen, een volgende onderdeel kost ~0 s en een volgende import uit de cache ~0,2 s; de eerste keer met een onderdeel is ongeveer 10% langzamer dan voorheen.
  Geen C++-wijziging.
- **0.22.2: bouwdelen met de materialen van de gebouwen.** In plaats van een eigen oppervlak per soort (`PDOK_bwd_<regel>`) krijgen de bouwdelen nu de oppervlakken van de gebouwen: bovenkant `PDOK_dak_plat`, zijkanten `PDOK_muur`, onderkant `PDOK_grondvlak` (ook bij de terugval met boven- en onderkant als driehoeken);
  met *Kleuren per soort* aan komen de kleuren uit de stijlregels voor laag `gebouw`. De `kleur` in de bouwdeelregels telt niet meer. Bouwdelen die al op `3D_bouwdelen` staan, veranderen niet vanzelf: verwijder ze eerst. Geen C++-wijziging.
- **0.22.1: bouwdelen: een duidelijker log en objecten boven maaiveld.** Eerst nam 0.22.0 alleen BGT-objecten op maaiveld mee (`relatieve_hoogteligging` 0), terwijl een luifel of overkapping boven een andere ondergrond vaak op niveau 1 staat. Nu worden niveaus boven maaiveld meegenomen en alleen onder maaiveld
  overgeslagen. Het log meldt wat PDOK per collectie teruggeeft (`PDOK geeft voor dit gebied: overigbouwwerk N, gebouwinstallatie M`), wat is overgeslagen en waarom (beëindigd, onder maaiveld, te klein, zwaartepunt buiten het gebied, geen vlak), en de plek en hoogte van de eerste drie. Geen C++-wijziging.
- **0.22.0: overige bouwdelen.** Nieuwe module `bouwdelen.py` en het vinkje *Overige bouwdelen*: de BGT-collecties `overigbouwwerk` en `gebouwinstallatie` worden uitgetrokken morphs op de laag `3D_bouwdelen` met het oppervlak `PDOK_<regel>` en het ID `BWD-<BGT-id>`.
  De BGT heeft geen hoogte voor deze objecten (de 3D Basisvoorziening kent een overkapping hooguit als terreinvlak), dus de hoogte is een aanname per soort: stijlregels met `vorm` (`blok`: op het maaiveld, `hoogte` hoog; `plaat`: `hoogte` boven het maaiveld, `dikte` dik), 12 standaardregels
  (overkapping, open loods, schuur, tank, silo, trafo, bunker, bezinkbak, bassin, luifel, bordes, trap). Maaiveld uit de 3D Basisvoorziening (blok: onderkant op het laagste punt van de omtrek, bovenkant op het gemiddelde plus de hoogte; plaat: gemiddelde plus de hoogte). Gaten in het vlak worden meegenomen; weigert Archicad een
  vlak met gaten, dan worden boven- en onderkant als driehoeken gemaakt. Soorten zonder regel worden overgeslagen en genoemd. Een stijlbestand zonder regels voor bouwdelen gebruikt de standaardregels (tabelversie 3). Geen C++-wijziging.
- **0.21.0: lichtmasten.** C++: nieuwe opdracht `CreateLamps` (`lampsData`), een variant van `CreateObjects` die een **Lamp**-element maakt (in de DevKit is `API_LampType` hetzelfde type als `API_ObjectType`, zoals Tapir ook gebruikt; `CreateObjectsCommand` is daarvoor geen `final` meer), en `GetLibraryObjectNames`
  geeft nu ook onderdelen van het type lamp (Archicad meldt lampen soms als object, soms als lamp). Python: `lichtmasten.py` leest de BGT-collectie `paal` (soort `lichtmast` in `plus_type`, alleen op maaiveld, niet beëindigd), bepaalt de terreinhoogte met dezelfde route als de bomen, en plaatst *Lantaarnpaal 04* op de laag `3D_lichtmasten` met
  het ID `LAMP-<BGT-id>` (nogmaals importeren slaat bestaande over). Palet: het vinkje *Lichtmasten* met een eigen zoekvak voor de lamp (een gedeelde zoekfunctie met de bomen), naamcontrole voor het importeren, en een melding bij een oudere add-on. Geen hoogte of draaiing: de BGT heeft die niet.
- **0.20.1: palet bijgesteld.** De importbalk is nu een vaste strook onder het scrollende deel (`#paneel` is een kolom met `#inhoud` en `#actie`), in plaats van een vastgeprikte balk die over de tekst heen lag en de laatste regel afsneed. De titel is *PDOK Import* (ook de paginatitel) en het vinkje *Gebouwen (LoD 2.2)* heet *Gebouwen*. Geen C++-wijziging.
- **0.20.0: een compacter palet.** Het palet is opnieuw ingedeeld in kaarten: Gebied (zoeken, drie knoppen op een regel, de afmeting, de uitleg ingeklapt), *2D · BGT en Kadaster* (met *Kleuren per soort* en *Ook viaducten en tunnels*), *3D* (een schakelaar *Volgens NAP | Vlak (0 m)*,
  vinkjes Gebouwen (LoD 2.2), Terrein, Scheidingen en Bomen, met subopties die alleen verschijnen als hun vinkje aan staat, een eigen *Kleuren per soort* en een ingeklapt *Geavanceerd* met Onderkant en Naden), *Bestemmingsplan* (de maatvoering kan pas zodra er een plan is gekozen),
  en een ingeklapt *Hulpmiddelen en instellingen* (meten, opruimen, stijlen, updatecontrole, diagnose). De importknop met de status staat vastgeprikt onderaan. Opties die verdwenen en nu altijd aan staan: *met materialen*, *naadsluiting* en *2D-vlakken over lagen per soort*; *Terreintypen overslaan* is vervallen.
  De gebiedsafmeting heeft een eigen regel (`gebiedinfo`) los van de statusregel. Een onderdeel dat de add-on niet kent, wordt overgeslagen bij het terugzetten van instellingen; een uitgeschakelde optie (maatvoering zonder plan) wordt wel teruggezet. Geen C++-wijziging.
- **0.19.1: een stijlbestand van een eerdere versie groeit mee.** Een `stijlen.json` uit 0.18.0 (geschreven door *Stijlbestand openen*) kent de sleutel `deellaag` niet en gaat voor op de standaardtabel; daardoor bleven alle 2D-vlakken op de laag van hun BGT-laag. Nu krijgt een regel zonder
  `deellaag` die van de standaardregel met dezelfde naam (een lege `"deellaag": ""` blijft leeg), met een melding in het log. Nieuw: de knop *Stijlbestand bijwerken* (`stijl.bijwerken()`): voegt ontbrekende standaardregels toe en vult `deellaag` aan, laat eigen regels en kleuren ongemoeid en bewaart een kopie
  `stijlen.json.bak`; het bestand krijgt een `versie`. Het log toont hoeveel regels een deellaag hebben en waarschuwt als er geen enkele is. Geen C++-wijziging.
- **0.19.0: oppervlakken in een map en 2D-lagen per soort.** C++: `EnsureSurface` heeft een optionele `folder` (de map in de oppervlakken, aangemaakt als hij er niet is; ook bestaande oppervlakken worden erin gezet, via de hulpfunctie `PlaceAttributeInFolder`).
  Alle `PDOK_`-oppervlakken krijgen die map (*PDOK Import*) mee. 2D: met het keuzevakje *2D-vlakken over lagen per soort verdelen* komen BGT-vlakken op `BGT_<laag>_<deellaag>` (bijvoorbeeld `BGT_wegdeel_fietspad`); de deellaag komt uit de stijlregel (sleutel `deellaag`,
  28 standaardregels hebben er een: rijbaan, parkeren, fietspad, voetpad, trap, inrit, voetgangersgebied, gras, heesters, bosplantsoen, planten, bos, heide, akker, erf, verhard, halfverhard, zand, berm, verkeerseiland). Zonder regel of deellaag blijft een vlak op de basislaag.
  Het pennummer per BGT-laag geldt voor al zijn deellagen. Het log toont *Lagen per soort (...)*.
- **0.18.1: gebouwkleuren.** 2D: de gebouwlagen (`pand`, `gebouwinstallatie`, `overigbouwwerk`) zijn lichtgrijs (lichter dan alle wegdelen), zowel als laagkleur (`KLEUREN`) als als regel in de stijltabel (`alleen: 2d`). 3D: platte daken (vlak dat minder dan `PLAT_DAK_HOEK` = 10 graden van
  horizontaal afwijkt) krijgen het oppervlak `PDOK_dak_plat` (grijs); hellende daken houden `PDOK_dak`. De kleuren van de vier gebouwoppervlakken (dak, dak_plat, muur, grondvlak) staan met *Kleuren per soort* aan in de stijltabel (laag `gebouw`, `type` = het vlaktype) en worden dan bij elke import
  bijgewerkt. `weg_klinker` en `weg_voetpad_klinker` zijn minder verzadigd rood. Geen C++-wijziging.
- **0.18.0: kleuren per soort (2D en terrein in 3D).** Nieuwe module `stijl.py`: een tabel met regels (naam, kleur, voorwaarden op laag, `functie`, `fysiek_voorkomen`, `plus_fysiek_voorkomen` en type, met `alleen` voor 2d of 3d en een `prioriteit`) die zowel de 2D-vulkleur als het 3D-oppervlak bepaalt.
  2D: elk vlak krijgt zijn kleur per soort (`foregroundColor` per hatch). 3D: elke terreinmesh krijgt een eigen oppervlak `PDOK_<naam>` (topMaterial), aangemaakt of bijgewerkt bij het importeren (de kleur komt uit de tabel); alleen wat in het gebied voorkomt.
  De standaardtabel (31 regels) is gemaakt op de waarden uit de meting (*Soorten meten*); een eigen tabel staat in `%LOCALAPPDATA%\PDOKImport\stijlen.json` (knoppen *Stijlbestand openen* en *Standaardstijlen herstellen*; een beschadigd of onvolledig bestand geeft de standaardtabel of slaat die regels over, met een melding in het log).
  Keuzevakjes *2D-vullingen kleuren op functie en fysiek voorkomen* en *3D-terrein: een eigen oppervlak per soort*. Scheidingen in 3D volgen later (op `bgt_type`). Geen C++-wijziging.
- **0.17.5: soorten meten.** Nieuw hulpmiddel *Soorten meten*: telt voor het getekende gebied per combinatie van `functie`, `fysiek_voorkomen` en `plus_fysiek_voorkomen` hoeveel objecten en hoeveel m2 er zijn, in de 2D-bron (per BGT-laag met vlakken,
  zonder beeindigde objecten en zonder objecten boven of onder maaiveld) en in de 3D-bron (de terreintegels; daar heten de velden `bgt_functie`, `bgt_fysiekvoorkomen` en `plus_fysiekvoorkomen`, plus `tabelnaam`, `bgt_type` en `plus_type`), en per eigenschap alle waarden. Het verandert niets;
  het is de eerste stap voor kleuren en oppervlakken per soort (zie OPENSTAAND.md).
- **0.17.4: echte stappen blijven staan.** De naadsluiting trok het hoogteverschil tussen meshes die elkaar raken gelijk naar het gemiddelde zolang dat kleiner was dan 0,75 m. Een stap van 50 cm werd daardoor een stap van 0: de lage kant ging 25 cm
  omhoog ("het lage terrein tegen de muur is te hoog") en de hoge kant 25 cm omlaag. De drempel (`NAAD_MAX_VERSCHIL`) is nu 0,10 m en instelbaar in het palet (*Naden: hoogteverschillen tot ... cm gelijktrekken*). Alleen kleine verschillen (ruis,
  interpolatie op T-kruisingen) worden nog gelijkgetrokken; grotere stappen (stoeprand, kade, talud) blijven zoals in de bron. Een mesh-import voor een gebied dat je al had, wordt niet vanzelf aangepast: wis het terrein en importeer opnieuw.
- **0.17.3: scheidingen meten.** Een nieuw hulpmiddel meet de scheidingen (muren, hekken) in de bron voor het getekende gebied: de vorm (open randen, soorten vlakken, hoogte), de stand op het terrein (onderkant en bovenkant ten opzichte van het terrein in de bron,
  per punt in plattegrond) en de aansluiting tussen scheidingen (punten binnen 20 cm: op dezelfde plek met een hoogteverschil, of net niet op dezelfde plek). Het verandert niets; het is bedoeld om te zien waarom bepaalde aansluitingen er niet goed uitzien.
- **0.17.2: de meting leesbaarder.** Een samenvatting bovenaan (welk deel van het terreinoppervlak binnen 1, 5 en 20 cm van de bron ligt, gewogen naar oppervlak in plattegrond, zowel in hoogte als loodrecht op het oppervlak). (Bijna) verticale
  brondriehoeken (vanaf 85 graden: kademuurtjes en taluds) tellen niet meer als gat of afwijking, want een mesh kan dat niet weergeven. Bij overlap staat of de bron zelf al overlapt of dat de import het veroorzaakt.
  Eerste meting in jouw project: de hoekpunten kloppen op 0,0 mm, de afwijkingen hangen af van de helling en zitten niet aan de rand van objecten.
- **0.17.1: de meshkwaliteit-meting nauwkeuriger.** De eerste meting (0.17.0) liet steile vlakken (normaal-z onder 0,3, helling boven ongeveer 73 graden) buiten het bovenvlak; bij een talud of kade telde dat als gat en gaf het grote
  schijnbare hoogteverschillen. Nu gaat de grens naar 0,02 (alleen echt verticale zijkanten vallen weg). Nieuw in het rapport: de helling bij elke grote afwijking, de afwijkingen aan de rand van een object (waar de naadsluiting ingrijpt) apart van
  die binnen een object, de afwijkingen per hellingsklasse, en per object met gaten het aantal driehoeken, het oppervlak en de gemiddelde helling (met het volledige ID). Geen C++-wijziging.
- **0.17.0: meshkwaliteit meten.** Nieuwe opdracht `GetMeshSurfaces` in de add-on: het bovenoppervlak van elementen zoals Archicad het zelf heeft gedriehoekt (alleen de vlakken die omhoog kijken, in wereldcoordinaten, als platte lijsten;
  naar Tapirs model-toegang). Het hulpmiddel *Meshkwaliteit meten* (in het uitklapvak onder Terrein) vergelijkt dat met de bron: de **hoogteafwijking** in de hoekpunten en de zwaartepunten van de brondriehoeken (per soort, 95%-waarde, de grootste
  afwijkingen met plek), de **dekking** (zwaartepunten zonder oppervlak = een gat, met een schatting van het oppervlak), de **overlap** (dubbel of gestapeld oppervlak) en de **kwaliteit van de driehoeken** (scherpe hoeken, hele kleine vlakken). Er wordt niets
  veranderd; het is bedoeld om te zien waar het terrein afwijkt voordat we iets verbeteren. Bij een groot gebied is het een steekproef. Vereist add-on 0.17.0 of nieuwer.
- **0.16.1: de scheidingen uit de terreintegels.** Bij 0.16.0 werden de scheidingen opgezocht in de tegels van de gebouwencollectie (`basisbestand_gebouwen`), waar alleen gebouwen in zitten (*"0 scheidingen"*). Ze staan
  in de terreintegels (`basisbestand_gebouwen_terreinen`, de `volledig_...`-bestanden). Het profiel *scheidingen* legt nu die collectie vast; het log noemt het goede woord (*scheidingen* in plaats van *panden*).
- **0.16.0: scheidingen uit de bron.** In de 3D Basisvoorziening staan de BGT-scheidingen (muren, kademuren, hekken) als CityJSON-type `OtherConstruction`; die werden niet gelezen. Nieuw is de keuze
  *Scheidingen (muren en hekken, als Morphs)*. De gebouwroute (lichaam opbouwen, aanmaken, terugvallen) is daarvoor een *profiel* geworden (`PROFIELEN` in `drie_d.py`: typen, laag, oppervlakken, ID, namen): gebouwen en
  scheidingen gebruiken dezelfde code. Scheidingen komen op de laag `3D_scheidingen` met het oppervlak `PDOK_scheiding`, het hoogste detailniveau dat het object heeft, het ID uit `3df_id`, en volgen de hoogtekeuze.
  Het log noemt de soorten (`bgt_type`) en de detailniveaus in de bron. De *Terreincontrole* geeft bij de soorten objecten nu aan welke bij een aparte keuze horen. Geen C++-wijziging.
- **0.15.1: instellingen onthouden en een melding bij een nieuwe versie.** Het palet bewaart de aangevinkte lagen en pennen, de 3D-opties, de boomnaam, het laatst getekende gebied en de kaartpositie in
  `%LOCALAPPDATA%\PDOKImport\instellingen.json` (naast de motor, dus ze overleven een update; het bestand wordt in een keer weggeschreven, een beschadigd bestand geeft gewoon de beginwaarden).
  De velden die worden onthouden komen uit de pagina zelf, dus nieuwe velden doen vanzelf mee. *standaardinstellingen* onderaan zet alles terug. De motor vraagt bij het starten aan GitHub
  (`releases/latest` van `IngeniumBT/PDOK`) of er een nieuwere release is; zo ja, dan staat er bovenaan een melding met een link (alleen die releasepagina kan vanuit het palet in de browser worden geopend). Uit te
  zetten met het vinkje onderaan. Geen C++-wijziging, maar het `.apx` moet wel opnieuw gebouwd worden.
- **0.15.0: een zoekvak voor de bomen.** Nieuwe opdracht `GetLibraryObjectNames` in de add-on (alle plaatsbare bibliotheekobjecten). De motor bewaart de lijst; het veld bij de
  bomen is nu een zoekvak met een uitklaplijst (alle woorden moeten in de naam voorkomen, namen die ermee beginnen eerst), met een melding of de naam bestaat. Bij het importeren wordt
  de naam gecontroleerd en met de hoofdletters van de bibliotheek doorgegeven; een onbekende naam geeft een foutmelding voordat er iets wordt gemaakt. Is de bibliotheek niet te lezen (een
  oudere add-on), dan meldt het zoekvak dat en wordt de naam niet gecontroleerd. In het testpaneel staat *Bibliotheek lezen*.
- **0.14.5: de kleinste groep vlakken in driehoeken, gezocht met proefaanmaken.** Bij een pand dat Archicad weigert, werd het op LoD 2.2 pas gemaakt als *alle* vlakken in
  driehoeken waren verdeeld (lange dunne waaiers op de daken). Nu zoekt de motor met **proefaanmaken** (nieuwe vlag `dryRun` in de aanmaakopdrachten van de add-on:
  het element wordt gemaakt en direct weer verwijderd, binnen dezelfde opdracht) de kleinste groep vlakken die echt in driehoeken moet; de rest blijft een vlak. Dit werkt alleen
  met add-on 0.14.5 of nieuwer; bij een oudere add-on wordt het zoeken overgeslagen, zodat er nooit proefelementen achterblijven. Het log noemt hoeveel vlakken in
  driehoeken moesten en hoeveel proefaanmaken nodig waren.
- **0.14.4: gebouwen met minder driehoeken.** Dat het pand 0173100000141026 nu op LoD 2.2 stond, kostte veel driehoeken: de opschoonstap verdeelde alle vlakken in driehoeken,
  wat lange dunne waaiers op de daken gaf. Nu worden alleen vlakken die meer dan 5 mm van vlak afwijken in driehoeken verdeeld; de rest blijft een vlak. De oude
  verdeling van alles blijft als laatste stap binnen LoD 2.2.
- **0.14.3: het versienummer is zichtbaar.** Het staat onderaan in het palet (naast *diagnose*), bovenaan elke import in het logboek en in `engine.log`, en `/info`
  geeft het ook. Het wordt bij het bouwen uit `AddOnVersion.hpp` in de motor gezet. Zo is te zien welke versie echt draait, bijvoorbeeld als een update niet is aangekomen.
- **0.14.2: sterkere opschoonstap voor gebouwen.** Het geweigerde pand 0173100000141026 had een vlak met een gat dat bijna 1 m van vlak was en niet in driehoeken
  te verdelen was, 21 open randen en een rand in drie vlakken. De opschoonstap maakt zo'n vlak nu zonder gat (of laat het weg), brengt randen in meer dan twee vlakken terug tot twee
  en laat alleen vlakken weg die echt leeg zijn. Het log toont per pand welke stappen zijn geprobeerd en wat het lichaam bevat (gewoon en opgeschoond).
- **0.14.1: een keuze voor de hoogtes, en opgeschoonde gebouwen.** De opties voor het vlakke terrein zijn teruggebracht tot twee keuzes: *volgens de 3D
  Basisvoorziening (NAP)* en *vlak, bovenkant terrein op 0 m*. De keuze geldt ook voor de gebouwen (de onderkant van elk pand op 0 m) en de bomen (op 0 m).
  Een pand dat Archicad blijft weigeren (APIERR_BADPARS, bijvoorbeeld door hoekpunten op bijna dezelfde plek) wordt nu eerst opgeschoond (hoekpunten binnen
  5 mm samengevoegd, spijkers en samenvallende vlakken weg) en op LoD 2.2 opnieuw geprobeerd; faalt het toch, dan beschrijft het log wat er in het lichaam zit.
- **0.14.0: een timer, vlak terrein, de hulpmiddelen terug, en gebouwen op LoD 2.2.** Het palet toont een timer en na afloop de duur per onderdeel.
  Nieuw is de optie *Vlak terrein* (de bovenkant van alle meshes op de gemiddelde hoogte, het laagste of hoogste punt, of een eigen niveau; de bomen
  volgen). *Terreincontrole* en *Terrein wissen* staan weer in het palet, in het uitklapbare vak *Hulpmiddelen voor het terrein*. Gebouwen die
  Archicad als geheel weigert (bijvoorbeeld rijtjes met gedeelde scheidingsmuren) worden nu eerst op LoD 2.2 in losse delen gemaakt (`BAGID-deel1`, ...),
  en alleen daarna op een lager niveau; het overzicht noemt hoeveel panden op welke manier zijn gemaakt en welke panden in de bron geen LoD 2.2 hebben.
- **0.13.0: de eerste proefversie voor gebruikers.** De pagina is hersteld (bij het weghalen van de twee terreinknoppen was de lagenlijst niet
  meer geladen), de projectlocatie (Survey Point) is uitgezet (het projectnulpunt wordt als RD (0, 0) gezien), de motor ruimt oude versies in
  AppData op, en er is een handleiding voor proefgebruikers (HANDLEIDING.md).
- **0.12.1: de projectlocatie via de omrekening van het Survey Point.** De add-on gebruikt de omrekening die Archicad zelf geeft van
  projectcoordinaten naar het Survey Point-stelsel (de plek van het Survey Point en zijn Project North-draaiing), en rekent daarmee alle
  coordinaten van RD naar het project, en bij het teruglezen van meshes weer terug. Het Survey Point is het nulpunt van het landelijke stelsel.
  De IFC-georeferentie (stelselnaam, E/N) wordt niet gebruikt. De knoppen *Terreincontrole* en *Terrein wissen* zijn uit het palet gehaald.
- **0.12.0:** eerste versie van de projectlocatie, gebaseerd op de IFC-georeferentie (vervangen door 0.12.1).
- **0.11.2:** pijlers (en landhoofden) van een brug blijven een **massieve kolom** tot de onderkant; alleen het brugdek wordt een dun
  dek. De eigenschap heet in de bron `relatievehoogteligging` (zonder streepje); die wordt nu herkend. De **Terreincontrole** toont per
  brugobject de soort, hoogteligging, oppervlakte, hoogtes en wat eronder ligt, en meldt kleine verschillen in oppervlakte (onder 3% of
  2 m2) niet meer als afwijking.
- **0.11.1: bruggen en viaducten uit de bron.** De tegels bevatten viaducten als eigen soort object (CityJSON-type `Bridge` en
  `BridgePart`), die tot nu toe niet werden ingelezen; daardoor ontbraken sommige viaducten helemaal. Ze worden nu ingelezen (alleen de
  bovenkant, ook als de bron ze als gesloten lichaam geeft), op de laag `3D_terrein_bruggen` met het oppervlak `PDOK_brug`, altijd als
  dun dek. De **Terreincontrole** toont nu alle soorten objecten in de bron voor het gebied.
- **0.11.0: viaducten en brugdekken.** Een viaduct werd een massief blok tot de onderkant van het terrein. Nu worden meshes die een
  dek zijn (ze liggen in plattegrond boven een ander object, of de bron zegt dat ze boven het maaiveld liggen) een dunne plaat van
  0,6 m, met het terrein eronder dat gewoon doorloopt. Te kiezen met *Viaducten en brugdekken als dun dek*. De **Terreincontrole**
  noemt nu ook de eigenschappen van de bron en hoeveel dekken zijn herkend.
- **0.10.1: de aansluiting van gebieden.** Een object dat de gebiedsrand kruist (een lange weg) werd bij een klein gebied afgeknipt;
  een aangrenzende import sloeg het daarna over omdat het ID er al stond, en zo ontstonden witte delen. Nu wordt een object dat het
  gebied raakt als geheel gemaakt. Nieuw: de knoppen **Terreincontrole** (vergelijkt Archicad met de bron en meldt wat ontbreekt of
  afwijkt) en **Terrein wissen**. Het lezen van ID's is ook sneller.
- **0.10.0:** het **logo van Ingenium** in de kop van het paneel (klein, met doorzichtige achtergrond), de keuze voor de **onderkant
  van het terrein** (als volume, met zijvlakken of alleen het bovenvlak) en de **diepte** onder het laagste punt, en het **lezen van
  meshes** (omtrek met hoogtes, gaten, niveau en skirt). Daardoor sluit een nieuwe terreinimport met naadsluiting aan op meshes
  van een eerdere import.
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
   naadsluiting werkt binnen een import en sluit nu ook aan op meshes van een eerdere import. Begin met een
   klein gebied (ongeveer 300 x 300 m). Het testpaneel heeft **Test: mesh (terrein) maken**.
   **Let op bij een update van 0.10.0 of eerder:** de meshes die je al hebt zijn afgeknipt en worden niet vanzelf aangevuld. Klik op
   **Terreincontrole** (met een getekend gebied) om te zien wat er ontbreekt, dan op **Terrein wissen** (twee klikken) en importeer opnieuw.
   **Viaducten:** vink *Viaducten en bruggen meenemen (als dun dek)* aan (standaard). Dit leest de bruggen uit de bron in en maakt ze, en
   andere meshes die boven een ander object liggen, tot een dunne plaat. Klopt een viaduct nog niet, klik dan op **Terreincontrole**
   en plak de uitvoer: de lijst met eigenschappen van de bron laat zien onder welke naam de hoogteligging staat.
   Onder *Terrein* kies je de **onderkant** (volume, zijvlakken of alleen het bovenvlak) en de **diepte** in meter.
   Controleer in 3D of de gebouwen op het terrein staan. Test de aansluiting door een tweede, aangrenzend gebied te importeren:
   de vlakken langs de grens horen dezelfde hoogte te hebben.
9. De gedownloade 3D-gegevens bewaart de motor in `%LOCALAPPDATA%\PDOKImport\cache`.

## Wat je terugmeldt

- Een schermafbeelding van het testpaneel na de basistests, en van de uitvoer van de overige tests.
- Wat er mislukt: de melding in de voortgang of in het testpaneel (en zo nodig de inhoud van `engine.log`, te vinden via *Over PDOK Import...*).
- Of de lagen, het venster en de ID's in Archicad zelf kloppen met wat het paneel meldt.
- Wat de database-melding zegt na *Naar plattegrond* en *Naar 3D*.
- Of de lijn en het vlak er in Archicad goed uitzien (het gat, de kleur, de pen).

## De projectlocatie (voor andere gebruikers)

De import werkt in RD, het landelijke stelsel. In Archicad is het **Survey Point het nulpunt van dat stelsel**: de coordinaten van een
punt in het Survey Point-stelsel zijn zijn RD-coordinaten. De add-on gebruikt de omrekening die Archicad daarvoor zelf biedt.

**Heeft jouw project het projectnulpunt op RD (0, 0)** en staat het Survey Point op het projectnulpunt, dan is er niets in te stellen.

**Ligt het projectnulpunt ergens anders** (de gewone situatie: het gebouw staat bij het Archicad-nulpunt), zet dan het Survey Point op
**min de RD-coordinaten van het projectnulpunt**:

1. Archicad: **Options > Project Preferences > Location Settings > Survey Point**.
2. Vul bij **Easting, Northing en Elevation** de plek van het Survey Point *ten opzichte van het projectnulpunt* in. Ligt het projectnulpunt op
   RD (260250, 482250) en 35,00 m NAP, vul dan in: Easting -260250, Northing -482250, Elevation -35.
3. Staat het project niet recht op het noorden, vul dan de **Project North**-hoek in.
4. De **georeferentie voor IFC** (stelselnaam, Eastings, Northings enzovoort) en de **breedte- en lengtegraad** van de projectlocatie hoef je
   voor deze add-on niet in te vullen; ze worden niet gebruikt.

Het palet toont bovenaan wat het Survey Point zegt: *"Volgens het Survey Point ligt het projectnulpunt op RD (260250, 482250), hoogte
35,00 m."* Klopt dat niet, of ligt het buiten het bereik van RD, dan staat er een waarschuwing. Het testpaneel heeft **Projectlocatie lezen**
(de matrix en de uitleg). Test het met een klein gebied rond een gebouw dat je kent: de BGT-lagen moeten op dat gebouw liggen.

## MDID

De ID's in `Sources/RFIX/AddOnFix.grc` zijn die van jouw account. Wijzig ze niet; laat dit bestand ook bij een update
ongemoeid.
