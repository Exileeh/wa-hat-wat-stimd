# Phase 3a — Province discovery & feasibility (all 12)

Goal: map every Provinciale Staten portal to its software vendor and determine whether
**per-party vote results** are publicly retrievable, and how. Verified June 2026 by web
research + live probing (curl with a browser UA; Notubiz/iBabs block plain bots).

## Vendor map (all 12 provinces)

| Province | PS portal | Vendor | Per-party votes? |
|---|---|---|---|
| **Utrecht** | stateninformatie.provincie-utrecht.nl | **GO** | ✅ **clean JSON API** (done) |
| Flevoland | stateninformatie.flevoland.nl | GO | ❌ structured votes 404; besluitenlijst PDF only — griffie lobby |
| **Drenthe** | drentsparlement.nl | GO | ✅ **done** — GO JSON at `/Leden/…` (not `/Samenstelling/…`); tier A (443 items) |
| **Fryslân** | fryslan.stateninformatie.nl | Notubiz (org 822) | ✅ **done** — collect_notubiz, tier A |
| Groningen | groningen.stateninformatie.nl (+ iBabs portal) | Notubiz (org 1396) | ⚠️ votings API empty; **Handelingen PDF names both sides + totals** (probed 2026-07-05) |
| **Gelderland** | gelderland.stateninformatie.nl | Notubiz (org 1769) | ✅ **done** — collect_notubiz, tier A |
| **Zuid-Holland** | pzh.notubiz.nl | Notubiz | ✅ **done** — collect_notubiz, tier A |
| **Overijssel** | overijssel.notubiz.nl | Notubiz | ✅ **done** — collect_notubiz, tier A |
| **Noord-Holland** | noordholland.bestuurlijkeinformatie.nl | **iBabs** | ✅ **done** (adapter; 141 moties + 40 amendementen, aangenomen only) |
| **Limburg** | limburg.bestuurlijkeinformatie.nl | **iBabs** | ✅ **done** — "Stemmen" field, **per-member counts + verworpen** (321 items) |
| Noord-Brabant | noordbrabant.bestuurlijkeinformatie.nl | iBabs | ⚠️ Moties report = outcome + indieners only; verbatim **notulen** = full **hoofdelijke stemming per lid** (confirmed 2026-07-05) |
| Zeeland | zeeland.bestuurlijkeinformatie.nl | iBabs | ⚠️ structured reports empty; **concept-besluitenlijst PDF names voting fracties** (probed 2026-07-05) |

**Vendor split:** GO = 3 (Utrecht, Flevoland, Drenthe) · Notubiz = 5 (Fryslân, Groningen,
Gelderland, Zuid-Holland, Overijssel) · iBabs = 4 (Noord-Holland, Limburg, Noord-Brabant, Zeeland).
Note: `{x}.stateninformatie.nl` (shared subdomain) = **Notubiz**, NOT GO. GO uses
province-specific domains and shows "een oplossing van GO" / `gemeenteoplossingen` in source.

## The decisive finding (Phase 3a) — later partly overturned
At discovery, **the clean per-party vote API looked unique to Utrecht.** GO's "stemgedrag" module
seemed opt-in; probing Flevoland, the GO **`/api/v2`** existed (meetings, groups/parties) but
`/Samenstelling` and every `/votings` path returned **404**. So "other GO provinces are basically
free" read as **wrong** — every province except Utrecht needed real work.

**Update 2026-07-05:** that was too pessimistic. **Drenthe** turned out to serve the *same* GO votes
JSON at a **different path** (`/Leden/{slug}/votings`) — now shipped, tier A. And a live probe showed
the three iBabs/Notubiz "dead ends" (Groningen, Noord-Brabant, Zeeland) all *do* publish per-fractie
votes — in **PDF** (Handelingen / besluitenlijst / notulen), just not as machine-readable data. So the
gap for the four not-live provinces is **open-data publishing, not data absence** → griffie/publish-as-
data lobby (Groningen, Zeeland, Noord-Brabant, Flevoland). See [outreach.md](outreach.md) §3 and
[coverage.md](coverage.md).

## Feasibility by vendor (one adapter unlocks all its provinces)

- **GO – Utrecht** ✅ Done. Clean JSON, per-**member** counts.
- **GO – Flevoland, Drenthe** ❌ Hard. Structure via `/api/v2`, but votes live only in
  besluitenlijst **PDFs** → PDF parsing. Or lobby the province to enable the GO stemgedrag
  module (then our existing adapter would just work). Low priority.
- **iBabs (4)** ⚠️ Feasible, medium effort. Publieksportaal is a **JS SPA** (`/Reports/Details/{guid}`
  renders "Loading" in raw HTML); votes load from a backend API that must be reverse-engineered
  (browser devtools). Votes are **faction-level** (which parties voted voor/tegen), **no
  per-member counts**. Zeeland has an explicit **Stemming** report — best entry point.
- **Notubiz (5)** ⚠️ Feasible, medium/uncertain effort, **biggest payoff**. JS SPA + an XML/JSON
  API at `api.notubiz.nl` (organisations/events), but vote breakdown isn't in the basic meeting
  endpoints — needs deeper reverse-engineering (the rendered `/vergadering/{id}` page's calls, or
  besluitenlijst docs). Votes are **faction-level**. Gelderland specifically only exposes
  adopted/rejected status (stemgedrag module off).

## Granularity note (matters for our data model)
Utrecht gives per-member counts (`{agree:6,disagree:0}`). iBabs/Notubiz expose **faction-level**
voor/tegen only. That's **fine for our V/T overview** (we only need "party mostly voor/tegen"),
but for those provinces the **"ruwe getallen"** and **split-vote** features would degrade (no
counts) — store as agree/disagree = 1/0 and disable those toggles per-province.

## Recommended approach
1. **3b — Generalize** the collector to config-driven multi-province (vendor + base + style per
   province) + frontend plumbing (province selector, `data/<prov>.json`, per-province huisstijl).
   No new votes yet — just make Utrecht load through the generic path.
2. **3c — Pick ONE vendor to crack next.** Recommendation: **Notubiz** (5 provinces, biggest reach)
   or **iBabs starting from Zeeland's Stemming report** (cleaner entry). Reverse-engineer the vote
   source via browser devtools, build the adapter, add all that vendor's provinces.
3. **3d — The other SPA vendor.**
4. **GO Flevoland/Drenthe** — defer (PDF parsing) or lobby for the stemgedrag module.

Each vendor adapter is a one-time reverse-engineering effort (like Utrecht's GO was) that then
unlocks 4–5 provinces at once.

## 3c spike findings (Notubiz vs iBabs) — IMPORTANT

Spiked both SPA vendors. Result flips the recommendation: **iBabs is the better target for
per-party votes, despite fewer provinces.**

### Notubiz (5 provinces) — clean API, but per-party is GATED
- Public JSON API works with `&format=json&version=…`. Per-meeting votings:
  `GET https://api.notubiz.nl/agenda_items/votings?format=json&version=1.25.11&organisation_id={ORG}&meeting_id={ID}`
  → per voting: `type_data.title`, `voting_type`, `voting_result` (adopted/rejected/withdrawn/equal),
  and `votes: [{role_id, vote: in_favor|against|absent|abstained|blank}]`.
- **Blocker:** votes are keyed by **`role_id` (individual statenlid), not party.** The
  `role_id → party` map lives only in `/roles?...&field_id=105`, which is **auth-gated**
  ("Insufficient rights"). The public `/parties/{org}` endpoint uses *person* ids that have
  **zero overlap** with `role_id`. So per-party is NOT retrievable anonymously.
- ⇒ Notubiz per-party needs either **(a) a Notubiz API token** (outreach — would unlock all 5
  provinces cleanly), or **(b) PDF besluitenlijst parsing**. Outcome + numeric tally ARE public.

### iBabs (4 provinces) — per-FRACTIE natively (no mapping problem)
- The publieksportaal renders votes **already grouped by fractie** (e.g. Noord-Holland motie:
  "Tegen: VVD, JA21, PVV, FvD, SP, 50plus / Voor: Overige fracties"). That's exactly our model —
  **no role_id→party bridge needed.**
- Data loads via the SPA endpoint **`/Reports/GetReportData`** (+ `/Reports/Item/{guid}`). Exact
  call params/POST body still need reverse-engineering (GET 404s; POST redirects → needs the right
  body, likely reportId + filters + an antiforgery token). That's the remaining work.

### Updated recommendation
1. **Build iBabs first** — it gives per-fractie votes directly (sidesteps Notubiz's exact blocker).
   Crack `/Reports/GetReportData` → adapter → 4 provinces (Noord-Holland, Limburg, Noord-Brabant,
   Zeeland; Zeeland also has a dedicated Stemming report).
   - ✅ **DONE**: `collect_ibabs` built & shipped on **Noord-Holland** (data-sources.md §7).
     Remaining iBabs provinces are config-only (report GUID + huisstijl + any local fracties).
2. **In parallel, request a Notubiz open-data API token** (outreach). If granted, the Notubiz
   adapter becomes clean and unlocks the other 5 provinces. Token is the cheapest unlock for the
   biggest group.
3. GO Flevoland/Drenthe — still lobby the griffie to enable the stemgedrag module (config-only).
