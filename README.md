# Wa hat wat stimd?

**▶ Live: https://lucsmits5-afk.github.io/wa-hat-wat-stimd/**

> Wa hat wat stimd yn de Provinsjale Steaten fan Fryslân?

Een overzicht van het **stemgedrag per fractie** in de **Provinciale Staten van Fryslân**
(Statenperiode 2023–2027): per moasje (motie), amendemint (amendement) of besluit zie je in één
tabel of elke fractie **Voor (V, groen)** of **Tegen (T, rood)** stemde, met exacte aantallen,
een **directe link naar het ingediende document** (pdf) en de **indieners**. Gebaseerd op de
open data van het Statenportaal (Notubiz). De titels zijn zoals de Staten ze publiceren, vaak in het Frysk.

Afgeleid van [Wie stemde wat?](https://github.com/carefulCamel61097/wie-stemde-wat) (alle
niveaus, 12 provincies), teruggebracht tot alleen Fryslân en uitgebreid met een statistiekpagina.

**Functies**
- Tabel: filters (type, partij, zoeken op onderwerp of indiener, uitslag, "alleen omstreden"),
  vastpinnen, sorteren, ruwe getallen, **CSV-download** van de selectie.
- **📄 Moasje / Amendemint**: opent het document op het Statenportaal.
- Vier analyses: **Statistieken** (stemmingen per maand · indieners en hun succes · aan de winnende
  kant · hoe omstreden), **Overeenkomst** (overeenkomstmatrix), **Partijprofiel** en **Vergelijken**.
- **Live bijladen**: stemmingen van vergaderingen na de laatste dagelijkse snapshot haalt de
  browser zelf op bij `api.notubiz.nl` (gemarkeerd als *live*).

## Hoe het werkt

```
collector/collect.py  ->  data/fryslan.json + data/roles.json  ->  statische site (index.html, app.js, app.css)
        ^                                                                     |
        └── GitHub Actions (dagelijks) of collector/refresh-local.ps1         └── browser laadt nieuwe
            ververst de snapshot                                                   vergaderingen live bij
```

- **Geen server, geen database.** De data is een gegenereerd JSON-bestand dat de site inleest.
- De collector (Python, alleen stdlib) leest de openbare Notubiz-API (vergaderingen, stemmingen,
  de module *Moasjes en amendeminten*, partijen) en de portaalpagina per vergadering (voor de
  verdeling per fractie), en schrijft `data/fryslan.json`. Daarnaast leert hij welke anonieme
  `role_id` bij welke fractie hoort en schrijft dat naar `data/roles.json`, zodat de browser nieuwe
  stemmingen zelf per fractie kan optellen. Details: [docs/notubiz.md](docs/notubiz.md).
- De aantallen (`voor` / `tegen` / `onthouden`) staan in de data; V/T wordt in de browser afgeleid
  (`voor > tegen`), zodat afsplitsingen en verdeelde fracties zichtbaar blijven (stip in de cel).

## Dagelijkse verversing

De workflow [`.github/workflows/refresh.yml`](.github/workflows/refresh.yml) draait elke dag
06:00 UTC en is handmatig te starten. **Let op:** Notubiz blokkeert GitHub's cloudservers
(bevestigd door Notubiz, geen uitzonderingen). Vanaf `ubuntu-latest` logt de run daarom
`KNOWN ISSUE … Network is unreachable`, houdt de bestaande data en blijft groen; de site laadt
nieuwe stemmingen live bij. Twee manieren om de snapshot wél te verversen:

1. **Self-hosted runner** op een altijd-aan machine in Nederland: registreer een runner
   (repo → Settings → Actions → Runners → New self-hosted runner) en zet de repository variable
   `RUNNER` op zijn label (Settings → Secrets and variables → Actions → Variables), bijv.
   `self-hosted`. Dezelfde workflow draait dan dagelijks vanaf die machine.
2. **Lokaal**: `python collector/collect.py` en de twee databestanden committen, of
   [`collector/refresh-local.ps1`](collector/refresh-local.ps1) inplannen in Windows Task Scheduler
   (doet pull → collect → commit → push, alleen de databestanden).

Wordt de snapshot ouder dan 14 dagen, dan toont de site daar een melding over; na 45 dagen wordt
de dagelijkse run rood.

## Lokaal draaien

```bash
python collector/collect.py      # ververs data/fryslan.json + data/roles.json (alleen stdlib)
python -m http.server 8000       # bekijk de site op http://localhost:8000
```
> Bekijk de site via een server (niet `index.html` dubbelklikken): browsers blokkeren `fetch`
> van het databestand bij `file://`.

## Bestanden
- [index.html](index.html), [app.css](app.css), [app.js](app.js) — de site (vanilla JS, geen dependencies)
- [collector/collect.py](collector/collect.py) — de collector
- [data/fryslan.json](data/fryslan.json) — snapshot; [data/roles.json](data/roles.json) — role_id → fractie
- [docs/notubiz.md](docs/notubiz.md) — databron, API-endpoints, datamodel, blokkade-diagnose
- [docs/claude-design-prompt.md](docs/claude-design-prompt.md) — briefing voor een herontwerp van de vormgeving

## Bron & licentie
Open data van de **Provinciale Staten van Fryslân** (Statengriffie, Notubiz vergaderportaal
[fryslan.notubiz.nl](https://fryslan.notubiz.nl)). Dit project hergebruikt die data met
bronvermelding en is geen officiële uitgave van de provincie. Ledennamen worden niet opgeslagen:
de dataset is op fractieniveau.
