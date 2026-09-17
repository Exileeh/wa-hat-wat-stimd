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

Niet openbaar: `/roles` (401 "Insufficient rights"), `/persons` (401). De koppeling
`role_id → fractie` moet dus worden **afgeleid** (zie §3).

## 2. Koppeling stemming ↔ document/indieners (`collect.py`, `match_module_item`)

1. Kandidaten = module-items met hetzelfde agendapunt (`parent.id` ↔ attribuut 54), gefilterd op
   type (Moasje* ↔ motie, Amendemint ↔ amendement).
2. Zelfde **nummer**: uit attribuut 26 of uit de titel (`Moasje 9 (…)`, `03 Moasje 09 - …`,
   `Moasje 6-M-21: …`, `Motie (26): …`).
3. Anders de unieke beste **titel-overlap** (≥ 2 gedeelde woorden, accenten en leestekens
   genegeerd). Terugval: kandidaten van dezelfde vergaderdatum.
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

Gevolg voor dit project: de dagelijkse cloud-run is een **waakhond** (houdt de data, wordt rood
als iets nieuws breekt of de data > 45 dagen oud is). Echt verversen: self-hosted runner in NL
(repository variable `RUNNER`) of `collector/refresh-local.ps1`. De site zelf blijft actueel via
het live bijladen.

## 5. Datamodel (`data/fryslan.json`)

```jsonc
{
  "meta": { "province": "Fryslân", "body": "Provinciale Staten", "term": "2023-2027",
            "generated_at": "…", "source": "https://fryslan.notubiz.nl", "license": "…", "note": "…",
            "style": {"accent": "#c8102e", "headerBg": "#2a0a0c"}, "granularity": "member",
            "counts": {"moties": 836, "parties": 15}, "types": ["amendement","besluit","motie"],
            "organisationId": 822, "gremiumId": 430, "moduleId": 6,
            "knownIssue": "…tekst voor de melding…", "noticeAfterDays": 14 },
  "parties": [ {"slug": "bbb", "name": "BBB"}, … ],            // kolomvolgorde: grootste fractie eerst
  "moties": [ {
      "id": 10358759, "date": "2026-05-06",
      "title": "Moasje 9 (CDA en BBB): Each foar predatoaren yn N2000 gebieten",
      "type": "motie", "result": "accepted", "resultLabel": "Aangenomen",
      "source": "https://fryslan.notubiz.nl/vergadering/1488191",
      "document": "https://fryslan.notubiz.nl/document/16906811/1/03+Moasje+09+-+…",   // optioneel
      "documentTitle": "03 Moasje 09 - each foar predatoaren …",                          // optioneel
      "indieners": ["cda", "bbb"],                                                        // optioneel
      "votes": { "bbb": {"agree": 14, "disagree": 0, "abstain": 0}, … },
      "totals": {"agree": 25, "disagree": 13}
  } ]
}
```

`data/roles.json`: `{ "generated_at", "term", "organisationId", "roles": {"173341": "pvda", …},
"unmapped": [ {"role_id", "reason", …} ], "seats": {"bbb": 16, …} }`.
