# Data sources & API findings

Everything below was verified live against
`https://www.stateninformatie.provincie-utrecht.nl` (June 2026). All endpoints are
**public, no authentication, JSON**.

## 1. The platform
- The site runs on **GemeenteOplossingen (GO)** — footer: "een oplossing van GO".
- Voting is GO's **"GO. stemgedrag"** module: it reads the digital voting boxes from
  meetings and publishes the results.
- Data owner = **Provincie Utrecht / Statengriffie**; GO = vendor/host/processor.
- Utrecht's Open Data statement: https://www.stateninformatie.provincie-utrecht.nl/over-deze-site/Open-Data
  ("all data … retrievable without restrictions").

## 2. Two layers of API

### (a) The *documented* Open (Raads/Staten)Informatie API — structure, NOT votes
- Base: `https://www.stateninformatie.provincie-utrecht.nl/api/v2/`
- This follows the national **VNG Open Raads-/Stateninformatie** spec
  (docs: http://docs.openraadsinformatie.nl/ ; spec: https://github.com/VNG-Realisatie/ODS-Open-Raadsinformatie).
- Response envelope: `{"status":"OK","code":200,"messages":[],"result":{...}}`
- Useful endpoints (verified):
  - `GET /api/v2/meetings?limit=&offset=` — meetings (totalCount ~1788).
    Each: `id, date, startTime, dmu{id,name}, location, url`.
  - `GET /api/v2/meetings/{id}` — single meeting (note: does **not** inline agenda items).
  - `GET /api/v2/dmus` — *organen* (PS + committees), e.g. `14 = Provinciale Staten`.
  - `GET /api/v2/groups?limit=60` — fracties + other bodies. `type:"Fractie"` = parties.
  - `GET /api/v2/events`, `/documents`, `/persons`, `/attachments`, `/positions`, `/roles`.
- **This documented API exposes meetings/documents/people/orgs but has NO votings/
  stemming endpoint.** That's why it looked like the votes weren't available.

### (b) The website's own AJAX endpoints — these DO have the votes
These power the site's UI. Undocumented in the open-data spec, but fully public.
Discovered by reading the site JS
(`/site/default2020/script/employees/votings.js` and `components/VotingModal.js`).
A code comment in `votings.js` even grumbles "seems like bad API design" — i.e. these
are internal endpoints, not a deliberate secret.

**Best building block — per party, all moties (clean structured JSON):**
```
GET /Samenstelling/{party-slug}/votings
```
Example: `/Samenstelling/bbb/votings`. Returns `items` keyed by year; each entry:
```json
{
  "votingId": 28163,
  "description": "M26-40a Van begroten naar realiseren, ingediend door UtrechtNu! & SGP",
  "documentId": 64815, "meetingItemId": 25015, "meetingId": 11125,
  "voteResult": {
    "name": "accepted", "label": "Aangenomen",
    "voteCounts": { "agree": 6, "disagree": 0, "absent": 0, "abstain": 0 }
  }
}
```
Here `voteCounts` is **this party's own** vote split (BBB: 6 voor, 0 tegen → "voor").
`updatedAt` gives the date. No HTML parsing needed.

> **Path varies per GO install (found 2026-07-05).** Utrecht serves this at
> `/Samenstelling/{slug}/votings`; **Drenthe** (`drentsparlement.nl`, same GO stack) serves the
> *identical* JSON at `/Leden/{slug}/votings`. During Phase-3 discovery Drenthe's `/Samenstelling/...`
> returned nothing, so it was wrongly filed as "stemgedrag module off." It wasn't — just a different
> route. The collector now takes a per-source `votings_path` (default `"Samenstelling"`, Drenthe
> `"Leden"`). If a GO province looks empty, try `/Leden/...` before concluding the votes are unpublished.
> (Surfaced by the Statengriffie/GemeenteOplossingen after the griffie lobby — see roadmap Phase 8.)

**Cross-party detail for a single motie (the "i" popup):**
```
GET /vergaderingen/stemmingen/{type}/{ref}
    type ∈ { document | agendapunt | vergadering }   (ref = documentId / meetingItemId / meetingId)
```
Example: `/vergaderingen/stemmingen/document/64815`. Returns:
- `groups[]` — all fracties/bodies (id, name)
- `votes[]` — each: `votingId, title, result, voteResult{agree,disagree,abstain,absent}`
  (overall totals, structured) **plus** `voteResultHtml` (rendered per-party table — HTML only).
- ⚠️ In this endpoint the *per-party* breakdown is only inside `voteResultHtml`. For
  structured per-party data prefer endpoint (a) above per party instead of parsing HTML.

Other party AJAX tabs (same pattern): `/Samenstelling/{slug}/activities`,
`/Samenstelling/{slug}/speakerfragments`, `/Samenstelling/{slug}/{year}`.

### Completeness model (VERIFIED — important)
The breakdown is recorded **per individual member** (the popup lists each member by name
plus the party totals) → voting is captured at member level (digital voting boxes /
hoofdelijke registratie).

For motie `document/64815` the breakdown listed **14 parties / 44 seats**, but PS Utrecht
has **49 seats**. Parties that were entirely absent (e.g. PVV, JA21) **do not appear at
all** — neither in that motie's breakdown nor (by the same logic) in their own
`/votings` list.

Consequences for our data model:
- **No single party endpoint is a complete motie list.** Build the master motie list as
  the **UNION of `votingId` across ALL parties' `/votings`** (a motie always has ≥1 party
  present, so the union is complete).
- A motie present in the union but absent from party P's list ⇒ **P was afwezig** for it
  (render blank/grey).
- Per-member absence within a present party is captured by a reduced `(N personen)` /
  lower counts. Abstentions are captured by `voteCounts.abstain`.
- `votingId` is the stable global key (same id appears in the party list and the
  cross-party detail). `documentId`/`meetingItemId`/`meetingId` also link out.
- For accurate **dates**, map each entry's `meetingId` → `GET /api/v2/meetings/{id}.date`
  (the `updatedAt` field is only an approximation).

## 3. Fracties (parties) — group ids (type "Fractie")
Slugs for the `/Samenstelling/{slug}/votings` call are the lowercased site slugs
(e.g. `bbb`, `vvd`, `groenlinks`, `d66`, `volt`, `pvdd`/"partij-voor-de-dieren" — to verify).

| id | party |
|----|-------|
| 443 | BBB |
| 164 | VVD |
| 165 | GroenLinks |
| 167 | D66 |
| 168 | CDA |
| 163 | PvdA |
| 169 | SP |
| 170 | ChristenUnie |
| 171 | Partij voor de Dieren |
| 172 | PVV |
| 166 | SGP |
| 173 | 50PLUS |
| 265 | Forum voor Democratie |
| 266 | DENK |
| 365 | JA21 |
| 444 | Volt |
| 539 | UtrechtNu! |
| 436 | BVNL |
| 425 | Socialisten Utrecht |
| 357 | Lijst Bittich |
| 358 | Onafhankelijke Statenfractie Utrecht |
| 390 | Gedeputeerde Staten (not a real fractie) |

(Current vs historical parties differ per period; the `/votings` data spans many years.)

## 4. Alternative source (not chosen)
- **Open Raadsinformatie / OpenBesluitvorming** (Open State Foundation + VNG):
  https://zoek.openraadsinformatie.nl/ , https://openbesluitvorming.nl/ — has a public
  (Elasticsearch) API and indexes moties/voting nationally. UI not ideal; Utrecht's own
  API is more direct, so we use that.

## 5. Build plan (no scraping)
1. Get the list of party slugs (from `/Samenstelling` page or the table above).
2. For each party: `GET /Samenstelling/{slug}/votings` → collect every motie with that
   party's `voteCounts`.
3. Merge per motie (key on `votingId` / `documentId`) into a matrix:
   rows = moties (date, code like "M26-40a", description, overall result),
   columns = parties, cell = *voor* / *tegen* / *onthouden* / *afwezig* / split.
   - "mostly voor" = agree > disagree; "mostly tegen" = disagree > agree.
4. Export as CSV and/or a Markdown table and/or a small static HTML page.
5. Be polite: cache responses, add a small delay between requests.

## Quick test commands (PowerShell)
```powershell
# one party, all moties
Invoke-RestMethod "https://www.stateninformatie.provincie-utrecht.nl/Samenstelling/bbb/votings"

# one motie, all parties (overall totals + HTML breakdown)
Invoke-RestMethod "https://www.stateninformatie.provincie-utrecht.nl/vergaderingen/stemmingen/document/64815"
```

## 6. Multi-province / multi-vendor (scope change)
Provinces do NOT share one platform. There is no uniform endpoint across all 12.
Known so far (to be completed for all 12):

| Province | Vendor | Portal (example) |
|----------|--------|------------------|
| Utrecht | **GO** ✅ | stateninformatie.provincie-utrecht.nl |
| Flevoland | **GO** (votes 404 — griffie lobby) | (GO — reuse our adapter) |
| Noord-Holland | **iBabs** ✅ | noordholland.bestuurlijkeinformatie.nl |
| Limburg | **iBabs** ✅ | limburg.bestuurlijkeinformatie.nl |
| Noord-Brabant | **iBabs** ✅ (`Stemmen` field, like Limburg) | noordbrabant.bestuurlijkeinformatie.nl |
| Zeeland | **iBabs** (registers empty; votes in PDF) | zeeland.bestuurlijkeinformatie.nl |
| Zuid-Holland | **Notubiz** ✅ | pzh.notubiz.nl |
| Fryslân | **Notubiz** ✅ | fryslan.notubiz.nl |
| Gelderland | **Notubiz** ✅ | gelderland.notubiz.nl |
| Overijssel | **Notubiz** ✅ | overijssel.notubiz.nl |
| Groningen | **Notubiz** (votings API empty; votes in Handelingen PDF) | groningen.notubiz.nl |
| Drenthe | **GO** ✅ (path variant `/Leden/...`) | drentsparlement.nl |

⇒ Architecture: **one adapter per vendor** (GO / iBabs / Notubiz), each normalizing to a
common schema. Our Utrecht reverse-engineering = the **GO adapter**, now serving **Utrecht +
Drenthe** (Drenthe via the `/Leden/...` path variant — see §2b). Flevoland is the same software;
still awaiting the griffie to enable/locate its votes.

- **iBabs**: has an API + open data (data.overheid.nl "ibabs-online"). Adapter TODO.
- **Notubiz**: public API at `api.notubiz.nl` (no formal public docs). **BUILT — no token needed**
  (`collect_notubiz`, 2026-06-15): events + votings API + portal HTML → **Zuid-Holland, Fryslân,
  Gelderland, Overijssel** (tier A). **Groningen** is a dead end (no per-stemming votings). Recipe + as-
  built in **§11**.

### Unified national source (fallback, NOT primary)
**OpenBesluitvorming / Open Stateninformatie** (Open State Foundation + VNG):
- ElasticSearch API: `https://api.openraadsinformatie.nl/v1/elastic/`
- Aggregates ~294 municipalities + **only 6 provinces**; standardized schema.
- BUT provincial **vote/stemming** coverage is historically weak (Open State:
  "regional voting records untraceable"). Good for documents, unreliable for votes.
- Use as a cross-check / fallback, not the source of the vote data.

## 7. iBabs adapter — endpoints (CRACKED, Noord-Holland)
The iBabs publieksportaal (`{prov}.bestuurlijkeinformatie.nl`) is an ASP.NET SPA with a
DataTables server-side table. Per-fractie votes ARE retrievable (no auth):

- **Reports list / GUIDs**: `GET /Reports` → each report = `/Reports/Details/{guid}`.
  NH **Moties** report = `84a8ac43-1424-48a9-8a1a-0c0bbcdfd8ed`; Zeeland **Stemming** report =
  `8f77ee0a-822e-4cbe-8acc-7ff35488c8ac`.
- **Motie list (clean JSON)**:
  `POST /Reports/GetReportData/{reportGuid}` — body `draw=1&start=0&length=1000`,
  header `X-Requested-With: XMLHttpRequest`. (GUID is in the PATH; GET 404s; must be POST.)
  Returns `{draw, recordsTotal, data:[ {DT_RowId, identity, ingediendindatum (dd-mm-yyyy),
  motienummer, title, fracties (=INDIENERS, not votes), status, behandelenin} ]}`.
- **Per-fractie votes**: `GET /Reports/Item/{DT_RowId}` → server-rendered HTML with a
  **"Stemverhouding"** field, e.g. `Tegen: VVD /BBB /JA21. Voor: overige fracties (X afwezig).`

Stemverhouding parsing notes (free text — handle all):
- `Unaniem` → all parties voor.
- `Tegen: A /B /C. Voor: overige fracties.` (and the reverse) → one side listed, other = the rest.
- separators vary: `/`, `/ `, `, `. Names: VVD, BBB, JA21, PVV, FvD, PvdD, SP, 50PLUS, Volt,
  ChristenUnie/CU, GroenLinks, PvdA, D66, …  (need an abbreviation→canonical map).
- `(… afwezig)` notes → afwezig fractions (exclude from "overige fracties").
- **"overige fracties" must be expanded vs the council composition** → scope to current term and
  build the party universe from the data (+ the report's `fracties` filter options). Composition
  changes across terms, so a static all-time union is wrong — term-scope it.
- Granularity = per-fractie V/T only (no counts) → store agree/disagree = 1/0; "ruwe getallen"
  and split-vote degrade gracefully for iBabs provinces.

### Implementation notes (Noord-Holland — adapter BUILT, `collect_ibabs`)
What the live build surfaced beyond the recipe above:
- **Date**: the detail page has a `Datum PS` field (dd-mm-yyyy) = the plenary vote date — use it
  for term-scoping (`>= 2023-03-29`), not the list's `ingediendindatum`. Pre-fetch only rows
  with `ingediendindatum` year `>= term-1` to avoid pulling all ~800 detail pages.
- **Multiple reports**: `GET /Reports` lists several (Moties, **Amendementen**, Ingekomen stukken,
  Toezeggingen, Schriftelijke/Technische vragen, …). Only **Moties** + **Amendementen** carry a
  Stemverhouding. The adapter takes a `reports: [{guid, type}]` list and unions them (each report
  gets its own `id_base` since the `identity` counter restarts per report). NH ships moties +
  amendementen (141 + 40 in-term).
- **Scope — only adopted items**: both registers are *afdoening*-trackers → **only `Aangenomen`
  moties/amendementen** (every in-term row, no verworpen). So the **niet-aangenomen** moties/
  amendementen are NOT published per-fractie anywhere on the portal — they'd only be in the
  besluitenlijst/notulen PDFs. Disclosed to users via `meta.note`. (Zeeland's dedicated "Stemming"
  report may include rejected too — check when adding it.)
- **Result source differs per report**: the Moties list row has a `status` field; the Amendementen
  list/detail has **none** — the outcome sits in the *attachment filename* ("A8-2026 **AANGENOMEN** …").
  Parse that keyword. **Do NOT derive the result from the vote tally** — we count *fracties*, not
  *zetels*, so a close vote (e.g. 8 small parties tegen vs 7 large voor) flips the wrong way.
- **UA**: the collector's plain UA works against iBabs (HTTP 200) — no browser spoofing needed
  in GitHub Actions; POST `GetReportData` needs `Content-Type: application/x-www-form-urlencoded`.
- **Free-text quirks the parser must handle** (all real, in-term):
  - `Tegen: JA 21 /PVV /50PLUS` — abbreviations with stray spaces ("JA 21" → JA21).
  - separators mix `/`, `, `, ` en `, and even **space-only** ("Tegen: PVV FvD") → tokenize
    space lists greedily, longest-alias-first, so "Fractie De Weerdt" stays whole.
  - **glued labels**: `…FvD, SPVerdeeld gestemd: VVD, PvdAVoor: Overige fracties` — un-glue with
    a regex that inserts a space before `Voor/Tegen/Afwezig:` / `Verdeeld gestemd:` stuck to a name.
  - **`Verdeeld gestemd:` clause** = fracties that split their own vote → store `agree==disagree`
    (renders as "O" + split-dot).
- **"overige fracties" expansion** = term party universe (built data-driven from every explicitly
  named fractie) **minus afwezig minus split**. Composition shifts *within* a term too: gate each
  fractie by a `first_seen` date (earliest time it's named on a side, noted afwezig, or appears as
  indiener) so a mid-term splinter (NH's **Fractie De Weerdt**) isn't back-filled into older moties.
- **Frontend contract**: `id` must be a number (the table coerces `+dataset.id` for pinning) →
  use the list `identity` int. Pick the huisstijl `accent` from `/Base/SiteCss` `--button-color`
  (NH = `#2891e0`). Party slugs reuse the existing `ABBR` map where they slugify the same.

### Other iBabs provinces (probed)
Not every iBabs portal is like NH — the vote *format* varies. **Limburg and Noord-Brabant** both serve the
structured `Stemmen` field (tier A, built); **Zeeland**'s registers are empty (its votes are PDF-only):
- **Limburg** — Detail pages have a structured **"Stemmen"** field (not "Stemverhouding"):
  `<div class="vote-summary-legend-{in-favour|against}"><div class="text">Fractie (Statenleden) (N), …</div>`
  — i.e. **per-fractie member counts** for the voor and tegen sides (tier A, like Utrecht). A fractie on
  both sides = a real split. The register **includes verworpen** (status field:
  Aangenomen/Verworpen/Ingetrokken/Aangehouden). Date = list `datum`. 321 in-term items (271 moties + 50
  amendementen). Moties decided *bij acclamatie* (no hoofdelijke stemming) have an empty Stemmen field →
  skipped. Reports: Moties `0493fdd4-…`, Amendementen `34a4e0ce-…`. Handled by `votes: "stemmen"`.
- **Noord-Brabant** — ✅ **built 2026-07-06, same `Stemmen` path as Limburg.** The Moties *report row*
  (`GetReportData`, report `376cf779-…`) has status (incl. verworpen) + **indienende** fracties but no
  votes, and the detail's `Stemverhouding` field is empty — which is why NB was *first* mis-filed as
  "notulen-only". But the **item detail** carries the populated **`Stemmen`** field (behind the portal's
  "toon stemmen" toggle) with per-fractie member counts, identical markup to Limburg → the existing parser
  reads it verbatim. The griffie (Emma Beers) flagged this on 2026-07-06 in reply to the lobby mail.
  Reports: Moties `376cf779-…`, Amendementen `0b5f0bd5-…`. **628 stemmingen (534 + 94), 15 fracties, tier A.**
  One quirk: NB records the combined CU-SGP fractie as `ChristenUnie/SGP` (until 2025) then `ChristenUnie-SGP`
  (from 2026) → merged via an `IBABS_ALIASES` entry. The verbatim notulen (full member-name roll-call) exist
  too but are no longer needed.
  > **⚠️ Lesson:** on iBabs, a province can populate *either* `Stemverhouding` (free text, NH) *or* `Stemmen`
  > (structured, Limburg/NB) — and the *report row* shows neither. Always check **both** fields on the item
  > detail before concluding "no structured votes". NB was a false negative for exactly this reason.
- **Zeeland** — all three registers (Moties `e34a898a-…`, Amendementen `6dafaa63-…`, **Stemming**
  `8f77ee0a-…`) return **0 rows** (recordsTotal 0) — re-checked 2026-07-06 incl. the `Stemmen` field, so
  this is *not* the NB mistake; the registers are genuinely unpopulated. But the **concept-besluitenlijst**
  PDF (attached to the next PS agenda as "Vaststellen concept-besluitenlijst van de Statenvergadering op …")
  *does* name the votes per item: e.g. *"aangenomen met de stemmen van de aanwezige leden van de fracties van
  BBB, CDA, CU, D66, PvdA-GL, PVV, SGP en VVD voor"*. One-side-named (NH-style, tier B), parseable but fragile.
  Fetch: agenda → besluitenlijst `documentId` → `/Document/View/{id}` (PDF).

> **Remaining open-data gaps (probed 2026-07-05/06).** Zeeland (iBabs, registers empty) *and* Groningen
> (Notubiz — votings API empty *and* no per-fractie markup in the portal render, re-probed 2026-07-06 across
> 5 meetings: stemgedrag module off; its **Handelingen** name both sides + totals) publish per-fractie votes
> only as **unstructured PDF**. So the fix is a *publish-as-data* ask to the griffie (like Drenthe), not
> PDF-scraping — though scraping is a possible fragile fallback. **Noord-Brabant was on this list until
> 2026-07-06**, when its `Stemmen` field turned up → now built, tier A. See [outreach.md](outreach.md) §3.

⇒ The adapter now branches on a province `votes` format: `"stemverhouding"` (NH free-text,
faction-level, inference) vs `"stemmen"` (Limburg structured, per-member counts, exact).

### HTML parsing is fragile — avoid it
The per-motie `voteResultHtml` is rendered HTML (per-member rows). A quick parse already
mis-read the proposer's row. **Prefer the structured `/Samenstelling/{party}/votings`
JSON** (clean per-party counts) over scraping the popup HTML.

## 8. Tweede Kamer — OData API (CRACKED, verified 2026-06-11)
The Tweede Kamer publishes a first-class **OData v4** open-data API. No auth, no token, JSON,
and it carries **per-fractie votes with exact seat counts** → tier A (like Utrecht/Limburg),
*incl. verworpen*. Far cleaner than any provincial portal. This is a **new category**, not a
province (see roadmap Phase 4).

- **Base:** `https://gegevensmagazijn.tweedekamer.nl/OData/v4/2.0/`
  (service doc lists entity sets; `$metadata` has the full schema). Append `&$format=json`.
- **UA:** plain works (no browser spoof needed) — fine for GitHub Actions.

### The vote chain
```
Stemming ──Besluit_Id──▶ Besluit ──Agendapunt──▶ Agendapunt ──Activiteit_Id──▶ Activiteit
   │                        │                                                      └─ Datum (vote date)
   │                        └──Zaak[] (the motie/amendement/wetsvoorstel)
   └─ per-fractie vote row
```
- **`Stemming`** (one row per fractie per besluit): `Soort` (`Voor` | `Tegen` | `Niet deelgenomen` |
  null), **`FractieGrootte`** (seat count → exact tallies), `ActorFractie` (display name AT vote
  time), `Fractie_Id`, `Besluit_Id`. `Persoon_Id` is set only for the rare hoofdelijke (per-person)
  votes — for fractie votes it's null.
- **`Besluit`**: `BesluitSoort` (outcome, see below), `BesluitTekst` ("Aangenomen."), `Agendapunt_Id`.
- **`Zaak`** (besluit→Zaak is a *collection* nav): `Soort` (`Motie` | `Amendement` | `Wetgeving` | …),
  `Nummer` ("2024Z15642"), `Onderwerp` (readable title "Motie van het lid X over Y"), `Vergaderjaar`.
- **`Activiteit`** (via `Agendapunt`): `Soort` "Stemmingen", **`Datum`** = the plenary vote date.

### Efficient fetch (≈12 requests, not 3k)
OData `$expand` inlines children, and nested navigation is **filterable**. One paged query pulls
everything:
```
GET /Besluit
  ?$filter=startswith(BesluitSoort,'Stemmen')
           and Agendapunt/Activiteit/Datum ge 2025-11-13T00:00:00Z
           and Stemming/any()
           and Zaak/any(z: z/Soort eq 'Motie' or z/Soort eq 'Amendement' or z/Soort eq 'Wetgeving')
  &$expand=Stemming($select=ActorFractie,Soort,FractieGrootte),
           Zaak($select=Nummer,Soort,Onderwerp),
           Agendapunt($expand=Activiteit($select=Datum))
  &$select=Id,BesluitSoort,BesluitTekst
  &$format=json
```
Server **page cap = 250 rows**; follow `@odata.nextLink` until absent. (`@odata.count` via
`$count=true` for totals.)

### Scope, outcomes, mapping (decisions)
- **Current term = on/after `2025-11-13`** (first stemming of the Kamer installed after the
  29 Oct 2025 election; constituerende vergadering 12 Nov 2025). The *old* Kamer kept voting between
  election day and installation — date-gating at 11-13 excludes those old-composition votes and keeps
  fractie sizes consistent. Consistent with the locked "current term only" decision.
- **Volume (verified 2026-06-11):** 3,450 `Stemmen*` besluiten since term start; of those **3,009 have
  a real roll-call** (`Stemming/any()`), **2,945** of which link to a Motie/Amendement/Wetgeving — that
  is our keepable set. (Moties 2,884 · amendementen 418 · wetgeving 64 across the term.) ~6 MB pretty
  → **write `tweede-kamer.json` compact (~3 MB)**. Frontend perf with ~3k rows × ~18 cols is a watch
  item (provinces are 181–566 rows); revisit virtualization/pagination if sluggish.
- **Keep only roll-call besluiten** (`Stemming/any()`). The many non-vote `BesluitSoort` values
  (`aangehouden`, `ingetrokken`, `uitstellen`, `vervallen`, **`zonder stemming aannemen`**) have no
  `Stemming` rows and drop out naturally — don't rely on the label, rely on the presence of votes.
- **Outcome** from `BesluitSoort`: `Stemmen - aangenomen|goedgekeurd|vastgesteld` → accepted;
  `Stemmen - verworpen|niet aangenomen` → rejected; `Stemmen - gestaakt` → tie (staking van stemmen).
- **Vote → counts:** `Voor` → `agree += FractieGrootte`, `Tegen` → `disagree += FractieGrootte`,
  `Niet deelgenomen`/null → abstain/absent. A fractie with both Voor and Tegen rows = a real split.
  Self-contained per besluit (no "overige fracties" inference) → granularity `member`, tier A.
- **Mid-term composition quirks** (handle/note, not blocking): `ActorFractie` is the name *at vote
  time*, so renames create separate columns — e.g. **GroenLinks-PvdA → "Progressief Nederland" (PRO)
  on 2026-06-09**; splinters **Groep Markuszower** (PVV, 2026-01-20) and **Keijzer**/"Lid Keijzer"
  (BBB, 2026-02-24). A small alias map can merge a pure rename (GL-PvdA ↔ PRO) into one column.
  `Fractie.AantalZetels` reflects *current* seats (post-splinter), so prefer the per-vote
  `FractieGrootte`, never the Fractie table, for tallies.

## 9. Eerste Kamer — HTML only (PROBED 2026-06-12, feasibility = GO, tier B)
The Eerste Kamer is a **separate system** from the TK OData and has **no machine API**: no
`gegevensmagazijn.eerstekamer.nl` / `opendata.eerstekamer.nl` host (DNS fails), no `/api`, no
OData, no SPARQL on the site. Everything is **server-rendered HTML on `www.eerstekamer.nl`** (the
PARLIS CMS). Per-fractie positions ARE published though — verified live. Granularity = **faction-
level V/T, NO seat counts** (EK votes *bij zitten en opstaan* — the chair declares the result, no
tallies; exact numbers only on a rare *hoofdelijke* stemming) → **tier B** (like Noord-Holland, but
see below: both sides are named explicitly, so NO "overige fracties" inference → more reliable than NH).
- **UA:** browser User-Agent works; plain may be throttled — send a browser UA (GitHub Actions OK).
- **Fracties (current EK term, 2023–2027): 20** — the 13 landelijke (VVD, GroenLinks-PvdA, BBB, D66,
  PVV, CDA, SP, ChristenUnie, PvdD, JA21, SGP, Volt, FVD, OPNL, 50PLUS) plus EK splinter fracties
  (Fractie-Beukering, -Van Gasteren, -Van de Sanden, -Visseren-Hamakers, -Walenkamp). Display name =
  `<X>-fractie`; slug at `/fractie/<slug>` (e.g. `/fractie/volt`, `/fractie/partij_voor_de_vrijheid`).

### Two HTML surfaces carry the per-fractie vote
1. **`/stemmingen_fractiegewijs`** — *structured, no NLP.* One collapsible section **per fractie**;
   a summary votebox (all-time `Voor / Tegen / Verdeeld` totals) + a `<ul class="stemlijst">` listing
   **every item that fractie voted on**, each `<li>` carrying: a thumb img `alt="Voor"|"Tegen"` (the
   fractie's position), the date (link), the type+result in parens (`(Hamerstuk)`,
   `(Stemming bij zitten en opstaan, aangenomen|verworpen)`), the title, and the dossier link
   (`/wetsvoorstel/36264_…` or `/kamerstukdossier/…`). **Paginated ~500 items/section.** Pro: no
   free-text parsing. Con: the link is the day's verslagdeel, **not unique per stemming** — two
   stemmingen under the same dossier/day/result (e.g. an amendement + the wetsvoorstel) are hard to
   tell apart → join-key ambiguity.
2. **The verslag page** (`/verslagdeel/{yyyymmdd}/{slug}` or `/id/{vid}/verslagdeel/…`) — *free-text,
   but both sides named.* Contains one chair sentence **per stemming**:
   `"Ik constateer dat de leden van de fracties van <VOOR-lijst> voor … hebben gestemd en de leden van
   de fracties van <TEGEN-lijst> ertegen, zodat het is <aangenomen|verworpen>."` Both sides enumerated
   (no "overige fracties" guess). A prototype parser mapped all sides to the 20-fractie universe
   cleanly (only fix needed: don't strip "de/het" inside names like *Fractie-Van de Sanden*).

### Vote types & volume
- **Hamerstuk** = passed without a vote (no objection) → uncontested, all fracties effectively voor.
- **Stemming bij zitten en opstaan** = the real (contested) votes; per-fractie split recorded (no counts).
- **Hoofdelijke stemming** = rare, per-member by name (aggregate to fractie; best-effort).
- **Index page:** `/stemmingen_per_vergaderdag?filter=alles` lists each stemming as a row (date, title,
  type, result, link), **paginated 25/page** via `start_006=` + `dlastinprev=YYYY-MM-DD`. Recent sample:
  ~25 stemmingen / 6 weeks (16 zitten-en-opstaan + 5 hamerstuk per page) → est. **~600–700 stemmingen
  over the 2023–2027 term** (between NH's 181 and Utrecht's 566 in scale — fine for the frontend).
- **Term boundary:** current EK installed **13 June 2023** (elected by the March 2023 PS). Scope votes
  `>= 2023-06-13`. (Note: EK term ≠ TK term — TK is 2025–heden, EK is 2023–2027.)
- **Item types:** wetsvoorstellen, moties, amendementen (+ brieven/overig — classify from the dossier link).

### Recommended build (collect_ek)
**Stemming-first** (preserves unique identity + metadata): walk `/stemmingen_per_vergaderdag?filter=alles`
pages back to 2023-06-13 → per row get date/title/dossier/type/result; for **zitten-en-opstaan** rows
fetch the verslag and parse the matching `Ik constateer …` sentence (both sides → per-fractie V/T);
**hamerstuk** rows = unanimous voor (or mark uncontested). Write `data/eerste-kamer.json` (same schema,
votes per fractie `agree/disagree = 1/0`, `granularity: "fractie"`), category `eerste-kamer`, single
scope. Parser caveats to handle: leading "de/het" inside fractie names, separator variants
(`,` / ` en `), splinter `first_seen` gating, hoofdelijke (per-member) rare case. Tier B → set
`meta.note` like NH; document in [coverage.md](coverage.md).

## 10. Europees Parlement — HowTheyVote.eu API (CRACKED, verified 2026-06-13, feasibility = GO, tier A)
The EP publishes per-MEP **roll-call votes** (RCV) as open data, but the official EP Open Data Portal
(`data.europarl.europa.eu/api/v2/`) serves them per-sitting in cumbersome RDF/XML. **HowTheyVote.eu**
compiles the same official data into a clean JSON API *and* weekly bulk CSV, **with per-group tallies
already aggregated** — far easier. We use HowTheyVote as the source and attribute both it and the EP.
- **License:** Open Database License (**ODbL 1.0**) + Database Contents License (DbCL 1.0) — free to
  use with **attribution + share-alike**. Our derived `data/europees-parlement.json` is published openly
  under the same; `meta.license` credits HowTheyVote.eu + the European Parliament.
- **UA:** browser UA works (plain may 000 on the apex `api.` host; use `https://howtheyvote.eu/api/...`).
- **Unit = European political group** (not individual MEPs, not Dutch-only): EPP, S&D, Renew,
  Greens/EFA (`GREEN_EFA`), ECR, PfE (`PFE`), The Left (`GUE_NGL`), ESN, NI. The schema's "parties" = groups.

### Endpoints
- **List:** `GET /api/votes?page_size=100&page=N` — paged, **newest first**, `is_main` votes only
  (the final vote per file; amendment/procedural sub-votes are excluded from this list). Envelope:
  `{total, page, page_size, has_next, results:[…]}`. Each result: `id, is_main, timestamp,
  display_title, reference, result, description, …`. Spans the **9th + 10th terms (2019→present)** →
  must date-filter (see scope). `is_main` query param is **not** honoured — rely on the list default.
- **Detail:** `GET /api/votes/{id}` — adds `stats` and `member_votes`:
  - `stats.by_group[]` = `{group:{code,short_label}, stats:{FOR,AGAINST,ABSTENTION,DID_NOT_VOTE}}` —
    **exact MEP counts per group** → maps to our `{agree=FOR, disagree=AGAINST, abstain=ABSTENTION}`.
    A group split across FOR/AGAINST is a real split (counts present → tier A, like TK seat counts).
  - `member_votes[]` = `{member:{full_name, country{code}, group{code}}, position}` — per-MEP, with
    **country** → enables an optional **Dutch-delegation breakout** later (v2; not needed for v1).
  - `procedure` → procedure type (COD/RSP/INI/NLE/BUD/DEC/…) for item-type classification.
- **Bulk (alternative):** GitHub releases `HowTheyVote/data` (weekly tag), `votes.csv.gz` (~750 KB,
  all 24k roll-calls incl. `is_main`, `count_*` totals, `procedure_type`, `result`), plus
  `member_votes.csv.gz` (~64 MB), `members`, `groups`, `group_memberships`. The CSVs have **no
  pre-aggregated per-group tallies** (that's API-only), so for group counts the API `stats.by_group`
  is the path of least resistance; the bulk file is a fallback for the vote list/metadata.

### Scope, volume, outcomes
- **Current term = 10th EP, votes on/after `2024-07-16`** (first sitting after the June 2024 election).
  Date-filter the list (it includes the 9th term back to 2019).
- **Volume (verified 2026-06-13):** **545 `is_main` votes this term** (498 ADOPTED, 47 REJECTED) — about
  Utrecht scale; small data (~9 group columns). (5,036 total roll-calls incl. amendments — we keep only
  `is_main`.) `result`: `ADOPTED` → accepted, `REJECTED` → rejected.
- **Caveats:** only **roll-call** votes are recorded per-MEP (show-of-hands aren't published — inherent,
  like every source here). Group membership shifts mid-term, but `stats.by_group` already reflects the
  group **at vote time**, so no first_seen gating is needed. HowTheyVote covers the 9th term onward only
  (irrelevant — we want the 10th).

### Build (collect_ep) — AS BUILT
`ep_load(base, term_start)` pages `/api/votes?page_size=100` until `timestamp < 2024-07-16` (~6 pages →
545 votes), then fetches each `/api/votes/{id}` via a **`ThreadPoolExecutor` (8 workers)** (the API is
~1.5s/request; sequential would be ~15 min). The fetched details are **cached per `base`** so both EP
scopes reuse one fetch. Two assemblers over the same details:
- **`ep_assemble_groups`** → `stats.by_group` → per-group `{agree,disagree,abstain}` (exact MEP counts),
  parties = `EP_GROUPS`. Writes `data/europees-parlement.json`. `granularity: "member"`, tier A.
- **`ep_assemble_nl`** → filters `member_votes` to `country.code == "NLD"`, groups by **national party**
  (`EP_NL_PARTY`), exact per-party counts, and attaches a **`members` roster** (MEP names) per party.
  Writes `data/europees-parlement-nl.json`. Column order = `EP_NL_ORDER` (2024 seats).

Both are scopes of the `europees-parlement` category (so the frontend shows a "Kies een weergave"
picker: *Europese fracties* / *Nederlandse afvaardiging*). `meta.sourceName = "HowTheyVote.eu"` +
`meta.license` = ODbL/HowTheyVote+EP.

#### NL MEP → national party map (`EP_NL_PARTY`)
HowTheyVote's member object has the **Euro-group + country but not the national party**, so the map is
resolved **once** from the **EP Open Data Portal** (IDs match HowTheyVote's):
`GET /api/v2/meps/show-current?limit=900` (filter `api:country-of-representation == "NL"` → the 31 MEP
ids) → for each, `GET /api/v2/meps/{id}` → the `hasMembership` entry whose `membershipClassification`
ends `NATIONAL_POLITICAL_GROUP` and has no `endDate` → its `organization` (`org/NNNN`) →
`GET /api/v2/corporate-bodies/{NNNN}` whose `label` is the party **abbreviation** (e.g. `VVD`).
Add former MEPs (who voted earlier in the term) the same way. The collector **WARNs** on any NL MEP id
not in the map, so by-election replacements are easy to spot and top up.

## 11. Notubiz — public API + portal HTML (BUILT 2026-06-15, no token, tier A, 4 provinces)
**Context:** Notubiz declined an API token (2026-06-15: a token alone is insufficient — it would also
need a rights-bearing *account* they can't provide). **It doesn't matter** — the live probe proved the
PS vote data is fully reachable from **public** surfaces. Verified on **Provincie Zuid-Holland**
(org `3868`); the same structure should hold for all 5 Notubiz PS provinces (Fryslân, Groningen,
Gelderland, Zuid-Holland, Overijssel — only the portal *slug* differs per org).

Three public calls, no auth:
1. **Organisation id**: `GET api.notubiz.nl/organisations` → find `Provincie <X>` (ZH = `3868`).
2. **Meetings**: `GET api.notubiz.nl/events?organisation_id=<id>&date_from=YYYY-MM-DD%20HH:MM:SS&date_to=...&page=1&format=json&version=1.21`.
   - **`version=1.21` is mandatory** — `version=1.10.0` silently rejects every param ("Zonder
     parameters kunnen er geen resultaten getoond worden"). `date_from`/`date_to` must be the exact
     format `2005-12-30 01:02:03` (URL-encode the space).
   - Response: `{pagination, events:[…]}`. Each event has `gremium.id`, `event_type_data.agenda_item_count`,
     `attributes` (id 1 = title), `plannings[0].start_date`. **Filter `gremium.id` to the plenary
     "Provinciale Staten" gremium** — list gremia via `GET api.notubiz.nl/organisations/<id>/gremia?format=json&version=1.21`
     (the name field is `title`); ZH plenary = **`11157`**. (Other gremia are commissies — no plenary votes.)
   - Meeting detail `GET api.notubiz.nl/events/meetings/<mid>?format=json&version=1.21` carries the
     public portal `url` (e.g. `https://pzh.notubiz.nl/vergadering/1253777/…`) → gives the **portal slug**.
3. **Votes (public, structured)**: `GET api.notubiz.nl/agenda_items/votings?meeting_id=<mid>&format=json&version=1.21`
   → `{votings:[{type_data:{voting_id, title, voting_result(accepted|rejected), votes:[{role_id, vote(in_favor|against)}]}, id}]}`.
   This is **per-member (hoofdelijk)** with `role_id` only — no names, no fractie.

**The `role_id → fractie` join** is auth-walled (`/roles?organisation_id=…` → "Insufficient rights to
query roles"; `/roles/<id>` → "Zonder authenticatie token") — exactly what Notubiz described. **But it
isn't needed:** the **public portal page** `https://<slug>.notubiz.nl/vergadering/<mid>/<naam>` renders,
per stemming:
- a Google-charts pie with **exact counts** (`['tegen (46x)',46],['voor (3x)',3]`) and the result
  (`title: 'Resultaat: verworpen'`), inside a `drawChart()` for `document.getElementById('chart_<voting_id>')`
  — **`chart_<voting_id>` matches the API's `voting_id`/`id`**, so HTML blocks join to API votings 1:1;
- immediately after each chart: the **per-fractie breakdown with member names**, as repeating
  `<vote> <FRACTIE> Leden: <Name> <Name> …` runs (e.g. `tegen BBB Leden: R.A.H. Kaijser H. Looij …` /
  `voor CDA Leden: …`). One vergadering page contains *all* stemmingen of that meeting (17 on 2025-01-29).

### Build (collect_notubiz) — AS BUILT (2026-06-15, 4 provinces live, tier A)
Built as a **hybrid**: the API drives discovery + metadata, the portal HTML gives the per-fractie counts.
`collect_notubiz(p)` (config per province: `organisation_id`, plenary `gremium_id`, portal `slug`,
`term_start`):
1. **Discover** — page the events API (`version=1.21`, term window) and keep events whose `gremium.id`
   is the plenary gremium **and** `event_type_data.agenda_item_count > 0` (drops recesses). → `(mid, date)`.
2. **Per meeting** — votings API → each stemming's `id`, `title`, `voting_result`, `voting_type`, and
   per-member `votes`; portal `vergadering/<mid>` page → `notubiz_parse_meeting` extracts, per stemming,
   `{fractie: {agree,disagree}}` by counting the member `<li class="in_favor|against">` rows inside each
   `<li>FRACTIE<ul>…</ul></li>` under the `votes_parties` block. Join HTML↔API by `chart_<id> == votings id`.
3. **Cross-check** the parsed per-fractie totals against the API's own per-member votes (WARN on mismatch
   — none in the current data); skip any voting with no portal chart (acclamatie / no roll-call → the API
   also returns it with 0 votes + null result).

Key facts the build pinned down (vs the recipe above):
- **`chart_<id>` matches the votings API `id`, NOT `voting_id`** — the join key is `id`.
- The portal markup is **structured, not free text**: `votes_list against|in_favor|divided` sides, each a
  `<ul>` of `<li>FRACTIE<ul><li>Leden:</li><li class="in_favor|against">Name</li>…</ul></li>`. Counting
  the member `<li>` classes gives exact tallies; a fractie under `divided` (or with mixed member classes)
  is a real split. (No need for the `Leden:` text runs or the chart `[...]` arrays — those only confirm.)
- **Result** from `voting_result`: `adopted`→accepted, `rejected`→rejected, `equal`→tie (staken).
- **Item type** from `voting_type` (`motion`/`amendment`/`council_proposal`/`initiative_proposal`) where
  present, else from the title — codes differ per province ("M 1567"/"A 873"/"SV …" ZH, "26M45" Gelderland,
  "PS26-M52"/"PS26-MV9" Overijssel) and are **Frisian** on Fryslân ("Moasje"/"Amendemint"). `voting_type`
  is fully populated for Fryslân/Overijssel, **null for all of Gelderland** and ~⅓ of ZH → the title
  fallback matters.
- **UA:** the collector's normal identifying UA works (only an *empty* UA gets 403) — no browser spoof
  needed in GitHub Actions; the portal serves full HTML even with `Accept: application/json`.
- **Composition:** merge spelling variants / pure renames into one column (`NOTUBIZ_ALIASES`: ZH
  GroenLinks-PvdA↔PRO, "Partij voor de Dieren"↔PvdD); drop non-fractie labels (`NOTUBIZ_SKIP`: "Geen
  partij" = a member mid-afsplitsing). One-person afsplitsingen keep their own named column.
- **Privacy:** member names are parsed but **not stored** — the dataset is party-level (counts only).

**Live (4):** Zuid-Holland (org 3868, gremium 11157, `pzh`) 1062 · Fryslân (822, 430, `fryslan`) 807 ·
Gelderland (1769, 2437, `gelderland`) 429 · Overijssel (1750, 2229, `overijssel`) 549 — all tier A,
`granularity: "member"`, incl. verworpen. **Groningen (1396, gremium 887, `groningen`)** returns **0
votings** across its plenary meetings — the Notubiz stemgedrag/votings module isn't populated, so the
adapter finds nothing. **Re-probed 2026-07-06** (5 recent meetings): the votings API is empty *and* the
portal `vergadering` pages (fully server-rendered, 125–558 KB) contain **zero** `chart_`/`votes_parties`
per-fractie markup — confirming the module is simply off, not a parse miss. **But it is not a data-absence
dead end:** the per-fractie votes are in Groningen's **Handelingen** (verbatim report, a meeting document —
e.g. doc id 16210480 for PS 24-9-2025), naming *both* sides by fractie **with totals** ("Voor deze motie
hebben gestemd … tegen hebben gestemd … 30 stemmen voor, 9 stemmen tegen"). So the fix is a publish-as-data
ask (enable the module — the 4 live Notubiz provinces already expose it) or fragile Handelingen-PDF parsing.
So Notubiz auto-yields 4, not 5. PS reached **8/12** after Drenthe (GO path variant, 2026-07-05) and
**9/12** after Noord-Brabant (iBabs `Stemmen` field, 2026-07-06; see §7 + roadmap Phases 8–9). Groningen is
a lobby candidate — see [outreach.md](outreach.md) §3.

## 12. Historische termijnen — multi-term model + per-year chunking (BUILT 2026-07-07)

The national/EU bodies (TK, EK, EP) keep **one scope per parliamentary term** — the previous terms are
config-only additions that reuse the current-term adapters. Chosen over a Provinciale-Staten previous
cycle because these three sources are clean/stable *and* actually hold the coronaperiode as structured
data (probed: the Notubiz PS provinces recorded **0** structured votes in 2020, so a PS backfill would
have a COVID hole; TK 2020 alone has **4 155** roll-call votes).

- **`term_bounds(p)` = `[term_start, term_end)`**; the current term omits `term_end` (open). Previous
  terms set it to the *next* term's installation date. `in_term(d, ts, te)` gates every adapter's date
  filter. Previous-term SOURCES entries are appended programmatically (`_TK_TERMS`/`_EK_TERMS`/`_EP_TERMS`
  + `_derive_terms()`) from each body's current entry, so shared fields aren't repeated. **22 SOURCES.**
- **Per-body reach (hard limits, probed):**
  - **TK (OData):** roll-call `Stemming` data has a **hard floor at 2008** (2004/2006 = 0 rows; 2008 =
    1 145, then full). Terms: 2008→now. Just add `and Agendapunt/Activiteit/Datum lt {term_end}`.
  - **EK (eerstekamer.nl):** the "stemmingen per vergaderdag" *eerdere stemmingen* chain ends at
    **~mid-2015** (crawl: 145 pages, 1 477 raw stemmingen, then no older link). So only 2015–2019 and
    2019–2023 are served; 2011/2007 aren't advertised. `collect_ek` now crawls the **whole** history
    **once** (`ek_load`, cached by base, down to `ek_floor()`) and each term slices it — not 5× re-crawls.
  - **EP (HowTheyVote):** `/api/votes` holds the **9th term onward (from 2019-07-18)** — no pre-2019
    data (oldest vote confirmed 2019-07-18). `ep_load` now fetches down to `ep_floor()` once (all metas +
    details, cached) and each term/breakdown slices it. **NL-afvaardiging is current-term only:**
    `EP_NL_PARTY` maps 10th-term MEP ids; 22 of the 9th-term NL MEPs are unmapped, so 2019–2024 ships the
    complete **Europese-fracties** view only (TODO: build the historical map from EP Open Data's
    `NATIONAL_POLITICAL_GROUP` membership per term).
- **Chunking (the size solve).** A 4-year TK term ≈ **14 MB / ~14 k stemmingen** — too big for one file
  and one `render()`. `write_scope(key, out, compact)` splits any scope **> `CHUNK_MIN` (5 000)** into
  `data/{key}.{year}.json` (one per calendar year, newest first) + a manifest `data/{key}.json`
  (`{meta, parties, chunked:true, chunks:[{year,count,file}]}`; `meta.types` carries the full type set so
  the filter chips are complete before every chunk loads). Small scopes stay a single `{key}.json`.
  Stale chunk files are cleaned up when a scope shrinks/unchunks. **Frontend:** `openScope` detects the
  manifest, loads the **newest year first** (fast ~0.8 MB paint), then `loadRemainingChunks` streams the
  rest and merges into `DATA.moties`; a **"Periode" (jaar) `<select>`** (only shown for chunked scopes,
  default = newest year) caps the rendered table via `passes()` while the matrix/profiel/vergelijk
  analyses use the whole loaded term. Wins: fast first paint, per-year CDN caching, and weekly reruns
  only rewrite the current year's file (no multi-MB git churn). Verified end-to-end with Playwright.
