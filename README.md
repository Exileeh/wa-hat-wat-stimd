# Wie stemde wat?

**▶ Live: https://carefulcamel61097.github.io/wie-stemde-wat/**

> Ik wil zien wie wat gestemd heeft in de Tweede Kamer, de Eerste Kamer, de provinciale staten en het Europees Parlement.

Een overzicht van het **stemgedrag per partij** op moties, amendementen, wetsvoorstellen en
besluiten. Per stemming zie je in één tabel of elke fractie **Voor (V, groen)** of
**Tegen (T, rood)** was — gebaseerd op open data van het orgaan zelf. Je kiest eerst een **niveau**
(Tweede Kamer, Eerste Kamer, Provinciale Staten of Europees Parlement) en daarna de **scope** (bij de
provincies: welke provincie; bij het Europees Parlement: per Europese fractie of de Nederlandse afvaardiging).

**Nu live (vier categorieën):**
- **Tweede Kamer** (OData open data, één scope per Kamer, terug tot 2008) — exacte zetelaantallen
  per fractie, inclusief *verworpen*; moties, amendementen én wetsvoorstellen. Tier A.
- **Eerste Kamer** (eerstekamer.nl, één scope per Kamer, terug tot 2015) — op fractieniveau (V/T,
  beide zijden vermeld), inclusief *verworpen*; hamerstukken niet opgenomen. Tier B.
- **Provinciale Staten** (9/12) — **Utrecht** en **Drenthe** (GemeenteOplossingen), **Limburg**,
  **Noord-Brabant** en **Noord-Holland** (iBabs), **Zuid-Holland**, **Fryslân**, **Gelderland** en
  **Overijssel** (Notubiz). Alle tier A (exacte aantallen per lid) behalve Noord-Holland, dat op
  fractieniveau publiceert en alleen aangenomen moties/amendementen.
- **Europees Parlement** (HowTheyVote.eu) — exacte aantallen per Europese fractie, incl.
  *verworpen*, voor de 10e (2024–2029) en 9e (2019–2024) zittingsperiode. Twee weergaven:
  **Europese fracties** en de **Nederlandse afvaardiging** (de 31 NL-leden per Nederlandse partij).
  Tier A.

De collector is multi-vendor / multi-categorie (een adapter per platform: GO / iBabs / Notubiz /
Tweede Kamer OData / Eerste Kamer HTML / HowTheyVote). Hoe betrouwbaar elke bron is, staat in
[coverage.md](coverage.md); of een bron het op dit moment ook echt doet, staat in
[coverage.md#status](coverage.md#status-van-de-bronnen).

Naast de tabel: filters (type, partij, zoeken, uitslag, "alleen omstreden"), vastpinnen,
**CSV-download** van de selectie, en drie analyses (popups): **Overeenkomst** (overeenkomstmatrix
per partij), **Partijprofiel** en **Vergelijken** (twee partijen).

## Hoe het werkt

```
collector (Python)  ->  data/<scope>.json  ->  statische site  ->  GitHub Pages
        ^                 (+ data/catalog.json)                         ^
        └──────────  GitHub Actions (wekelijks) ververst de data  ────────┘
```

- **Geen server, geen database.** De data is een gegenereerd JSON-bestand dat de site inleest.
- De `collector/` heeft een **adapter per platform** (GemeenteOplossingen / iBabs / Tweede Kamer
  OData / Eerste Kamer HTML / HowTheyVote / Notubiz). Hij normaliseert alles naar één schema,
  schrijft een dataset per scope en een `data/catalog.json` die de scopes per categorie (Tweede Kamer
  / Eerste Kamer / Provinciale Staten / Europees Parlement) indexeert.
- De frontend leest `catalog.json` en bouwt daarmee de startpagina (kies categorie → scope). De
  gekozen scope staat in de URL-hash (`#tweede-kamer`, `#provinciale-staten/utrecht`,
  `#europees-parlement/europees-parlement-nl`) → deelbaar.
- De aantallen (`voor` / `tegen` / `onthouden`) staan in de data; V/T wordt in de browser
  afgeleid (`voor > tegen`). Zo blijven afsplitsingen en uitzonderingen zichtbaar.

Technische details en de teruggevonden endpoints: [data-sources.md](data-sources.md).

## Lokaal draaien

```bash
python collector/collect.py      # ververs data/<provincie>.json (alleen stdlib, geen install)
python -m http.server 8000       # bekijk de site op http://localhost:8000
```
> De site moet via een server bekeken worden (niet `index.html` dubbelklikken): browsers
> blokkeren `fetch` van het databestand bij openen via `file://`.

## Documentatie
- [context.md](context.md) — doel, visie, scope en status
- [roadmap.md](roadmap.md) — stappen, beslissingen en de **▶ NEXT** (waar verder te gaan)
- [coverage.md](coverage.md) — wat we hébben per provincie + **betrouwbaarheid** per bron
- [data-sources.md](data-sources.md) — databron, API-endpoints (GO + iBabs + Notubiz) en datamodel
- [provinces.md](provinces.md) — alle 12 provincies: leverancier + haalbaarheid van stemdata
- [outreach.md](outreach.md) — concept-mails (Notubiz-token, griffies) om meer provincies te ontsluiten

## Bron & licentie
**Open data** van het orgaan zelf:
- **Tweede Kamer der Staten-Generaal** (opendata.tweedekamer.nl, OData).
- **Eerste Kamer der Staten-Generaal** (eerstekamer.nl).
- **Provinciale Staten** (Statengriffie): Utrecht (GemeenteOplossingen), Noord-Holland en Limburg (iBabs).
- **Europees Parlement**: hoofdelijke stemmingen via **HowTheyVote.eu** (Open Database License, ODbL),
  met fractie-indeling uit het **EP Open Data Portal**.

Dit project hergebruikt die data (met bronvermelding) en is geen officiële uitgave van de overheid.
