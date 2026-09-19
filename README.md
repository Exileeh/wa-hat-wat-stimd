# Wa hat wat stimd?

**▶ Live: (https://wa-hat-wat-stimd.vercel.app/#)**

> Wa hat wat stimd yn de Provinsjale Steaten fan Fryslân?

Een overzicht van het **stemgedrag per fractie** in de **Provinciale Staten van Fryslân**
(Statenperiode 2023–2027): per moasje (motie), moasje frjemd, amendemint (amendement) of besluit
zie je in één tabel of elke fractie **Voor (V, groen)** of **Tegen (T, rood)** stemde, met exacte aantallen,
een **directe link naar het ingediende document** (pdf) en de **indieners**. Gebaseerd op de
open data van het Statenportaal (Notubiz). De titels zijn zoals de Staten ze publiceren, vaak in het Frysk.

Afgeleid van [Wie stemde wat?](https://github.com/carefulCamel61097/wie-stemde-wat) (alle
niveaus, 12 provincies), teruggebracht tot alleen Fryslân en uitgebreid met een statistiekpagina.

**Functies**
- Tabel: **gegroepeerd per vergadering en per wurklistpunt** (agendapunt), standaard dichtgevouwen;
  filters (type, partij, zoeken op onderwerp of indiener, uitslag, "alleen omstreden"),
  vastpinnen, sorteren, ruwe getallen, **CSV-download** van de selectie. Zoeken of filteren vouwt de
  groepen met treffers vanzelf open.
- **Pagina per vergadering** (`#vergadering/<id>`, [meeting.js](meeting.js)): kerncijfers, de analyses
  van díe dag en alle stemmingen per agendapunt, met een filter op agendapunt. Te openen met de knop
  *Vergadering* in de tabel.
- **Wie was aan het woord** en **Zoek in het debat**, op die vergaderpagina: spreektijd per fractie
  volgens de sprekersindex van de griffie, en een zoekveld over de ondertiteling van de vergadering.
  Elke treffer noemt het tijdstip, de spreker en zijn fractie, en linkt naar de video op dat
  spreekmoment. De ondertiteling is automatische spraakherkenning, dus controleer een citaat in de
  video. Zie [docs/sprekers.md](docs/sprekers.md).
- Types: moasje, **moasje frjemd** (een motie over iets dat niet op de wurklist staat), amendemint
  en besluit — elk met een eigen filterknop en eigen cijfers.
- **📄 Moasje / Amendemint**: opent het document op het Statenportaal.
- Vier analyses als eigen weergaven (tabs, deelbaar via `#statistieken`, `#overeenkomst`,
  `#partijprofiel`, `#vergelijken`): **Statistieken** (stemmingen per vergadering — klik een balk voor
  die vergadering op het Statenportaal — met een filter op vergadering · indieners en hun succes ·
  aan de winnende kant · hoe omstreden), **Overeenkomst** (overeenkomstmatrix), **Partijprofiel** en
  **Vergelijken**.
- Kolomvolgorde op **stemgelijkenis**: fracties die vaak hetzelfde stemmen staan naast elkaar. Alleen
  als ze duidelijk in twee blokken uiteenvallen (coalitie | oppositie) komt daar een blauwe lijn tussen;
  bij een geleidelijk verloop, zoals in deze periode, blijft die weg. Uit te zetten onder *Weergave*.
- **Live bijladen**: stemmingen van vergaderingen na de laatste dagelijkse snapshot haalt de
  browser zelf op bij `api.notubiz.nl` (gemarkeerd als *live*).

## Hoe het werkt

```
collector/collect.py  ->  data/fryslan.json + data/roles.json     ->  statische site (index.html, app.js, app.css)
                          data/sprekers.json + data/transcript/
        ^                                                                     |
        └── GitHub Actions (dagelijks) of collector/refresh-local.ps1         └── browser laadt nieuwe
            ververst de snapshot                                                   vergaderingen live bij
```

- **Geen server, geen database.** De data is een gegenereerd JSON-bestand dat de site inleest.
- De collector (Python) leest de openbare Notubiz-API (vergaderingen, stemmingen,
  de module *Moasjes en amendeminten*, partijen) en de portaalpagina per vergadering (voor de
  verdeling per fractie), en schrijft `data/fryslan.json`. Daarnaast leert hij welke anonieme
  `role_id` bij welke fractie hoort en schrijft dat naar `data/roles.json`, zodat de browser nieuwe
  stemmingen zelf per fractie kan optellen. Details: [docs/notubiz.md](docs/notubiz.md).
- **Sinds 27 mei 2026** registreert de griffie de stemmingen niet meer in de Notubiz-stemmodule;
  ze publiceert per vergadering een PDF *"Útslach stimming"* met schermafdrukken van het
  stemdisplay. Voor die vergaderingen leest [collector/uitslag_pdf.py](collector/uitslag_pdf.py)
  de aantallen per fractie uit de kleuren van die afbeeldingen (titel en fractienamen via lokale
  OCR, met een controle op de totaalregel per pagina). Dat vraagt de optionele pakketten uit
  [collector/requirements-pdf.txt](collector/requirements-pdf.txt); zonder die pakketten worden
  zulke vergaderingen gemeld en overgeslagen. Zie [docs/notubiz.md §6](docs/notubiz.md).
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
2. **Lokaal**: `python collector/collect.py` en de databestanden committen, of
   [`collector/refresh-local.ps1`](collector/refresh-local.ps1) inplannen in Windows Task Scheduler
   (doet pull → collect → commit → push, alleen de databestanden in `data/`).

Wordt de snapshot ouder dan 14 dagen, dan toont de site daar een melding over; na 45 dagen wordt
de dagelijkse run rood.

## Lokaal draaien

```bash
python -m pip install -r collector/requirements-pdf.txt   # eenmalig, optioneel: PDF-terugval (zie boven)
python collector/collect.py      # ververs alle databestanden in data/
python -m unittest discover -s collector                  # tests (PDF-lezer, sprekers)
python -m http.server 8000       # bekijk de site op http://localhost:8000
```
> Bekijk de site via een server (niet `index.html` dubbelklikken): browsers blokkeren `fetch`
> van het databestand bij `file://`.

## Bestanden
- [index.html](index.html), [app.css](app.css), [app.js](app.js) — de site (vanilla JS, geen dependencies)
- [meeting.js](meeting.js) — de pagina van één vergadering, los van de rest van de site
- [collector/collect.py](collector/collect.py) — de collector;
  [collector/sprekers.py](collector/sprekers.py) — sprekersindex en ondertiteling
- [data/fryslan.json](data/fryslan.json) — snapshot; [data/roles.json](data/roles.json) — role_id → fractie;
  [data/sprekers.json](data/sprekers.json) — spreektijd; `data/transcript/<id>.json` — ondertiteling per vergadering
- [docs/notubiz.md](docs/notubiz.md) — databron, API-endpoints, datamodel, blokkade-diagnose
- [docs/sprekers.md](docs/sprekers.md) — sprekersstatistiek en doorzoekbare transcripten per vergadering
- [docs/claude-design-prompt.md](docs/claude-design-prompt.md) — briefing voor een herontwerp van de vormgeving

## Bron & licentie
Open data van de **Provinciale Staten van Fryslân** (Statengriffie, Notubiz vergaderportaal
[fryslan.notubiz.nl](https://fryslan.notubiz.nl)). Dit project hergebruikt die data met
bronvermelding en is geen officiële uitgave van de provincie. De **stemdata is op fractieniveau**:
hoe een individueel lid stemde wordt niet opgeslagen, ook niet waar het portaal dat toont. De
sprekersindex en de ondertiteling zijn daarop de uitzondering — daar staat wél wie sprak, precies
zoals de griffie dat zelf bij de video publiceert. Zie [docs/sprekers.md](docs/sprekers.md).
