# Databron: Notubiz (Provinciale Staten van Fryslân)

Alles komt van openbare Notubiz-oppervlakken, zonder token. Provincie Fryslân = organisatie
**822**, plenair gremium "Provinsjale Steaten" = **430**, portaal `https://fryslan.notubiz.nl`.
`version=1.21` is verplicht op elke API-call (andere versies negeren alle parameters).

## 1. Endpoints

| Doel | Call | Opmerkingen |
|---|---|---|
| Vergaderingen | `GET api.notubiz.nl/events?organisation_id=822&date_from=YYYY-MM-DD%2000:00:00&date_to=…&page=N&format=json&version=1.21` | 200 per pagina, `pagination.has_more_pages`. Filter `gremium.id == 430` en `event_type_data.agenda_item_count > 0` (recessen weg). Datum: `plannings[0].start_date`. |
| Stemmingen | `GET api.notubiz.nl/agenda_items/votings?meeting_id=<mid>&format=json&version=1.21` | `votings[]`: `id`, `parent.id` (agendapunt), `type_data.title`, `voting_type` (motion/amendment/council_proposal), `voting_result` (adopted/rejected/equal/withdrawn), `votes[]` = `{role_id, vote}` met `in_favor` / `against` / `absent`. **Hoofdelijk, maar anoniem** (alleen `role_id`). |
| Portaalpagina | `https://fryslan.notubiz.nl/vergadering/<mid>` | Per stemming `<div id="chart_<id>">` (`id` == votings-`id`) gevolgd door een blok per fractie: `<li>FRACTIE<ul><li class="in_favor\|against">Naam</li>…</ul></li>`. Hieruit komen de exacte aantallen per fractie. Cloudflare-challenge voor `curl`; de gewone collector-UA werkt. **Geen CORS** → niet vanuit de browser te lezen. |
| Moasjes en amendeminten | `GET api.notubiz.nl/modules/6/items?organisation_id=822&format=json&version=1.21` | 1 930 items (≈3,5 MB, geen paginering, geen datumfilter). Attributen: `1` titel, `15` datum, `45` type (Moasje / Amendemint / Moasje frjemd …), `2` document `{document:{id,url,title}}` (pdf), `54` agendapunt-id (== `votings[].parent.id`), `37` partij-id's (indieners), `26` nummer, `62` uitslag (Oannommen/Fersmiten/Ynlutsen). |
| Partijen | `GET api.notubiz.nl/organisations/822/parties?format=json&version=1.21` | `id → name` (incl. historische fracties). |
| Document-URL | `https://fryslan.notubiz.nl/document/<docid>/1/<titel-met-plussen>` | Geeft `application/pdf`. |
| Vergaderdetail | `GET api.notubiz.nl/events/meetings/<mid>?format=json&version=1.21` | Voor **elke** vergadering opgehaald. `meeting.agenda_items[]` (genest): `type_data.title_prefix` (agendapuntnummer, ook "2a"), `type_data.attributes[id=1].value` (titel), `documents[] {id, title}`. Elk genummerd agendapunt met titel komt in de map `agenda item id → {nr, title}`; `votings[].parent.id` wijst daarop, zodat elke stemming onder haar wurklistpunt valt. Hier staat ook, onder het agendapunt "Stimming", het document **"Útslach stimming <datum>"** (zie §6). |

Niet openbaar: `/roles` (401 "Insufficient rights"), `/persons` (401). De koppeling
`role_id → fractie` moet dus worden **afgeleid** (zie §3).

**Let op (sinds 27 mei 2026):** de griffie registreert de hoofdelijke stemmingen niet meer in de
Notubiz-stemmodule. Voor de plenaire vergaderingen vanaf die datum geeft de stemmingen-API
`{"votings": []}` en heeft de portaalpagina geen `chart_`-blokken. De module *Moasjes en
amendeminten* is wél gewoon bijgewerkt (titel, indieners, document, uitslag), maar zonder
verdeling per fractie. Die staat alleen nog in de PDF van §6.

## 2. Koppeling stemming ↔ document/indieners (`collect.py`, `match_module_item`)

1. Kandidaten = module-items met hetzelfde agendapunt (`parent.id` ↔ attribuut 54), gefilterd op
   type (Moasje* ↔ motie en moasje frjemd, Amendemint ↔ amendement). Voor een **moasje frjemd**
   tellen eerst de items waarvan attribuut 45 zelf "frjemd"/"fremd" zegt; de griffie schrijft dat
   type niet consequent, dus zonder treffer gelden alle moasje-items alsnog als kandidaat.
2. Zelfde **nummer**: uit attribuut 26 of uit de titel (`Moasje 9 (…)`, `03 Moasje 09 - …`,
   `Moasje 6-M-21: …`, `Motie (26): …`).
3. Anders de unieke beste **titel-overlap** (≥ 2 gedeelde woorden, accenten en leestekens
   genegeerd). Terugval: kandidaten van dezelfde vergaderdatum.
**Types.** `notubiz_classify` kijkt eerst naar de titel: begint die met "Moasje frjemd"/"Moasje
fremd" (eventueel na het agendapuntnummer), dan is het type `frjemd` — de API zet zulke moties weg
als gewone `motion` en een enkele keer zelfs als `council_proposal`. Daarna pas telt `voting_type`.

**Eén kolom voor Van Dijk.** Het lid is gekozen voor FVD en staat tot medio 2024 onder die naam
als indiener in de module; de stemmen staan de hele periode op "Steatelid Van Dijk". Beide namen
worden in `NOTUBIZ_ALIASES` naar **"Van Dijk (FvD)"** gemapt, dus naar één slug `van-dijk-fvd`.

4. Resultaat 2026-09-17: **671 van 676** moties+amendementen gekoppeld (99 %); 663 met document
   (8 module-items hebben geen bijlage). Indieners: partij-id's → namen → `slugify` (met alias
   "Partij voor de Dieren" → "PvdD"). Een indiener zonder eigen kolom (bijv. FVD, in deze periode
   zonder zetel-stemmen) blijft gewoon staan.

## 3. `data/roles.json`: role_id → fractie

De API geeft per stem een anonieme `role_id`; het portaal noemt per stem de naam en fractie. Over
de hele periode heeft elk lid een uniek stempatroon (incl. afwezigheid), dus per `role_id` wordt
het lid met de hoogste overeenstemming gezocht (`learn_roles`): minstens 20 gezamenlijke
stemmingen, één fractie op de eerste plaats en ≥ 90 % gelijk. Leden van dezelfde fractie zijn
soms onderling niet te onderscheiden — dat is prima, we hebben alleen de fractie nodig.
Stand 2026-09-17: 54 rollen gekoppeld (43 zittende leden + vervangers), 5 niet (rollen met
2–13 stemmen, tijdelijke vervangers). Namen worden **niet** opgeslagen.

Met dit bestand telt de browser (`app.js`, `liveTopUp`) nieuwe vergaderingen zelf op:
events sinds de snapshot → votings per vergadering → per `role_id` de fractie → aantallen.
`api.notubiz.nl` stuurt `Access-Control-Allow-Origin: *`, dus dit werkt zonder proxy. Stemmen van
onbekende rollen worden geteld en in de melding genoemd, niet gegokt. De module-lijst (3,5 MB)
wordt alleen opgehaald als er echt nieuwe stemmingen zijn.

## 4. Waarom GitHub Actions de bron niet kan bereiken

Diagnose van de oorspronkelijke maintainer (2026-09-13, twee GitHub-runners in Azure eastus/westus):
DNS werkt, maar **TCP naar `api.notubiz.nl:443` wordt stil gedropt** en het Cloudflare-portaal
geeft 403. Notubiz (2026-09-15): blokkade op herkomst (geo-IP / datacenter), *"hierop maken wij
geen uitzonderingen; u kunt de requests wel uitvoeren van Nederlandse servers."* Log van de
upstream-run van 2026-09-17: `== Fryslân (notubiz) == 0 plenaire vergadering(en) … KNOWN ISSUE:
no data at all; failed requests: URLError ([Errno 101] Network is unreachable)`.

Maar het filter blijkt niet op Nederland te zitten, wel op de herkomst. Gemeten op 19 september
2026: vanaf een Duitse consumentenlijn geven zowel `api.notubiz.nl` als het portaal **200**, en
vanaf een Vercel-functie in `fra1` (AWS `eu-central-1`, IP `35.156.88.0`) net zo goed — alle vier
de oppervlakken, inclusief de 3,4 MB module-lijst. Geblokkeerd zijn dus de cloudrunners van
GitHub (Azure, VS), niet datacenters in het algemeen.

### De relay

De collector draait daarom gewoon in GitHub Actions — daar staan de OCR-pakketten, is er geen
tijdslimiet en kan hij committen — en alleen zijn **uitgaande requests** gaan via een kleine
Vercel-functie:

```
Actions-runner ──> https://<project>.vercel.app/api/notubiz?u=<url> ──> api.notubiz.nl
                   (fra1, host-allowlist + X-Relay-Key)                fryslan.notubiz.nl
```

* `api/notubiz.py` laat alleen `https` naar `api.notubiz.nl` en `fryslan.notubiz.nl` door en
  vraagt de header `X-Relay-Key` (env `RELAY_KEY` in het Vercel-project); zonder die sleutel
  antwoordt hij 404, zodat de functie op het publieke domein geen open proxy is. De status van de
  bron gaat ongewijzigd terug, zodat `fetch()` zijn eigen 429/5xx-retries houdt.
* Een antwoordbody op Vercel mag hoogstens 4,5 MB zijn. Grotere bodies (de Útslach-PDF's; ooit de
  module-lijst, nu 3,4 MB) komen in stukken: de relay geeft 206 met `Content-Range`, `http()` in
  `collect.py` vraagt de rest op met een `Range`-header en plakt het aan elkaar.
* In de workflow staan de secrets `NOTUBIZ_RELAY` en `RELAY_KEY`. Zijn ze leeg — een lokale run,
  `refresh-local.ps1` — dan gaan alle requests rechtstreeks, precies zoals eerst.

Alternatieven blijven bestaan: een self-hosted runner in NL (repository variable `RUNNER`) of
`collector/refresh-local.ps1`. De site zelf blijft daarnaast actueel via het live bijladen, al
werkt dat sinds 27 mei 2026 alleen voor vergaderingen die nog digitale stemmingen hebben.

## 5. Datamodel (`data/fryslan.json`)

```jsonc
{
  "meta": { "province": "Fryslân", "body": "Provinciale Staten", "term": "2023-2027",
            "generated_at": "…", "source": "https://fryslan.notubiz.nl", "license": "…", "note": "…",
            "style": {"accent": "#c8102e", "headerBg": "#2a0a0c"}, "granularity": "member",
            "counts": {"moties": 913, "parties": 15, "fromPdf": 77},
            "types": ["amendement","besluit","frjemd","motie"],
            "organisationId": 822, "gremiumId": 430, "moduleId": 6,
            "knownIssue": "…tekst voor de melding…", "noticeAfterDays": 14 },
  "parties": [ {"slug": "bbb", "name": "BBB"}, … ],            // kolomvolgorde: grootste fractie eerst
  "moties": [ {
      "id": 10358759, "date": "2026-05-06", "meetingId": 1488191,
      "title": "Moasje 9 (CDA en BBB): Each foar predatoaren yn N2000 gebieten",
      "type": "motie",                        // motie | frjemd | amendement | besluit | ordevoorstel | overig
      "result": "accepted", "resultLabel": "Aangenomen",
      "source": "https://fryslan.notubiz.nl/vergadering/1488191",
      "agenda": {"id": 10204740, "nr": "3", "title": "Untwerp Fryske Oanpak Stikstofreduksje"},  // optioneel
      "document": "https://fryslan.notubiz.nl/document/16906811/1/03+Moasje+09+-+…",   // optioneel
      "documentTitle": "03 Moasje 09 - each foar predatoaren …",                          // optioneel
      "indieners": ["cda", "bbb"],                                                        // optioneel
      "votes": { "bbb": {"agree": 14, "disagree": 0, "abstain": 0}, … },
      "totals": {"agree": 25, "disagree": 13}
  } ]
}
```

`meetingId` staat op elke stemming, `agenda` op vrijwel alle (2026-09-19: 11 van de 913 niet — hun
`parent.id` hoort bij een agendapunt zonder nummer of titel). De site groepeert de tabel op deze
twee velden en `#vergadering/<meetingId>` is de pagina van één vergadering.

`data/roles.json`: `{ "generated_at", "term", "organisationId", "roles": {"173341": "pvda", …},
"unmapped": [ {"role_id", "reason", …} ], "seats": {"bbb": 16, …} }`.

Dezelfde portaalpagina levert ook de sprekersindex en de ondertiteling van de vergadering; die
gaan naar `data/sprekers.json` en `data/transcript/<meetingId>.json`. Zie
[sprekers.md](sprekers.md).

## 6. Terugval: de PDF "Útslach stimming" (`collector/uitslag_pdf.py`)

Voor elke plenaire vergadering die via de API géén stemmingen oplevert, zoekt `collect.py` in
het vergaderdetail naar een document met "Útslach stimming" in de titel en leest dat.

**Wat erin staat.** Een voorblad (aanwezig/afwezig) en daarna per stemming één schermafdruk
(JPEG, 1280×800) van het stemdisplay: de titel bovenaan, per fractie een donkere kopbalk met
daaronder één gekleurde regel per lid — groen = foar, rood = tsjin, geel = ûnthâlding, grijs =
ôfwêzich — en onderaan `Voor: N Tegen: N Onthouding: N`. Ynlutsen (ingetrokken) moasjes staan er
met `YNLUTSEN` in de titel en 0-0-0 in; die worden overgeslagen. Ook de eindstemming over het
Statenvoorstel zelf ("… - Finale beslút") staat erin, en een herstemming ("Werstimming") op een
moasje van een eerdere vergadering.

**Hoe het gelezen wordt.**
1. `pypdf` haalt per pagina de afbeelding eruit.
2. Het raster wordt uit **pixelkleuren** gelezen: per kolom worden aan de rechterrand (waar geen
   tekst staat) de kopbalken gezocht en daaronder de ledenregels met een vaste steek van 31 px
   afgelopen; de klasse van een regel is de meerderheidskleur van een vlak van 5×21 pixels
   (bestand tegen JPEG-ruis). De aantallen zelf hangen dus **niet** van OCR af.
3. `RapidOCR` (lokaal ONNX-model, geen netwerk) leest alleen de titel, de fractienamen in de
   kopbalken en de totaalregel. Een kopbalk zonder OCR-tekst (komt voor bij "VVD") wordt
   opnieuw gelezen op een uitvergrote, geïnverteerde uitsnede.
4. **Controle per pagina**: de per kleur getelde regels moeten gelijk zijn aan de OCR-totaalregel
   en elke kopbalk moet (fuzzy, ≥ 0,75) op een bekende fractie uitkomen — eerst de fracties die
   deze periode al een kolom hebben, dan de partijenlijst van de organisatie; "PBF" is een alias
   voor "Provinciaal Belang Fryslân". Anders wordt de pagina **afgekeurd** en in het log genoemd,
   nooit geraden.
5. Titel, document en indieners komen van het module-item met dezelfde datum, hetzelfde type en
   hetzelfde nummer (spatieloze titelovereenkomst als terugval, want OCR laat spaties weg);
   voor een "Finale beslút" komt de titel van het agendapunt uit het vergaderdetail. De uitslag
   volgt uit de aantallen (voor > tegen = aangenomen, gelijk = staken van stemmen).

**Datamodel.** Zulke stemmingen hebben `id = document-id × 1000 + paginanummer` (numeriek en
stabiel), dezelfde `source` (vergaderpagina) als de API-stemmingen, en extra het veld
`uitslag` met de URL van de PDF. `meta.counts.fromPdf` telt ze. Ze voeden `roles.json` niet
(geen role_id's), maar `app.js` laadt deze vergaderingen ook niet live bij: die herkent ze aan
`source`.

**Validatie.** Voor 6 mei 2026 bestaan de digitale stemmingen én de PDF naast elkaar: alle 24
vergelijkbare stemmingen komen per fractie exact overeen; de PDF bevat daarnaast de gestaakte
stemming (19-19) en de eindstemming, die de API-route niet had.

**Afhankelijkheden.** `collector/requirements-pdf.txt` (pypdf, Pillow, numpy,
rapidocr_onnxruntime, samen ± 100 MB). `refresh-local.ps1` en de workflow installeren ze; zonder
deze pakketten draait de API-route gewoon en meldt de collector welke vergaderingen hij oversloeg
(`WARN: … alleen met een 'Útslach stimming'-PDF overgeslagen`).
