# Roadmap — "Wie heeft wat gestemd?" (multi-province voting overview)

> ## ▶ NEXT (resume here)
> **TARGET — LOCKED (2026-06-12): four categories — ✅ ALL FOUR NOW LIVE (2026-06-13).** The site covers
> four legislative bodies (landing order: national → regional → EU):
> 1. **Tweede Kamer** — ✅ LIVE (Phase 4). ~2,945 stemmingen (groeit wekelijks), OData, per-fractie seat counts incl. verworpen. Tier A.
> 2. **Eerste Kamer** — ✅ LIVE (Phase 5). `data/eerste-kamer.json`, 449 stemmingen (2023–2027). No EK API —
>    per-fractie V/T parsed from the "stemmingen per vergaderdag" HTML (both sides named, no counts → tier B);
>    hamerstukken excluded, hoofdelijke aggregated to fractie. Recipe: data-sources.md §9.
> 3. **Provinciale Staten** — ◑ category LIVE, **9/12 provinces** (Utrecht, Noord-Holland, Limburg,
>    **Noord-Brabant**, Zuid-Holland, Fryslân, Gelderland, Overijssel, **Drenthe**). The 4 Notubiz provinces
>    shipped in Phase 7 (tier A); **Drenthe** landed 2026-07-05 (GO `votings_path` variant); **Noord-Brabant**
>    landed 2026-07-06 (iBabs `Stemmen` field like Limburg — config-only, tier A, 628 items). Remaining growth
>    (Flevoland) below.
> 4. **Europees Parlement** — ✅ LIVE (Phase 6). `data/europees-parlement.json`, 545 votes (2024–2029), by
>    **European political group**. Source = HowTheyVote.eu API (`stats.by_group`, exact per-group MEP counts
>    → tier A), concurrent detail fetch, ODbL. Recipe: data-sources.md §10.
>
> **▶ The locked target is complete.** Remaining work is depth, not new categories:
> - **✅ DONE — Phase 7: `collect_notubiz` adapter (NO TOKEN NEEDED).** Shipped 2026-06-15: events +
>   votings API (`version=1.21`) + portal `vergadering` HTML → **4 provinces, tier A** (exact per-member
>   counts, incl. verworpen): **Zuid-Holland** 1062, **Fryslân** 807, **Gelderland** 429, **Overijssel**
>   549 stemmingen. **Groningen's votings API is empty** (0 across all 38 plenary meetings) → auto-yields 4,
>   not 5 (but Groningen *does* publish votes in its Handelingen PDF — lobby candidate, see below). PS now
>   **3/12 → 7/12**. As-built recipe: data-sources.md §11; reliability: coverage.md.
> - **✅ DONE — griffie lobby → Drenthe** (GO stemgedrag data). Mailed 2026-06-11, nudged 2026-06-29;
>   the Statengriffie had GemeenteOplossingen locate the votes. Turned out the GO votings JSON was live
>   all along at a **different path** (`/Leden/{slug}/votings`, not Utrecht's `/Samenstelling/...`) —
>   so it was config-only: one `votings_path` key + a `classify()` tweak for "Statenstuk" titles.
>   Drenthe = **443 stemmingen, 15 fracties, tier A** (per-fractie member counts). Landed 2026-07-05.
> - **✅ DONE — Noord-Brabant** (iBabs). A lobby mail (2026-07-05) drew a griffie reply pointing to "toon
>   stemmen": NB was a **false negative** — its item detail carries the structured `Stemmen` field (like
>   Limburg), we'd only checked the empty report row / `Stemverhouding`. Shipped 2026-07-06 config-only:
>   **628 stemmingen, 15 fracties, tier A**. Lesson: on iBabs, check **both** `Stemverhouding` and `Stemmen`.
> - **Still open → Flevoland** (`griffie@flevoland.nl`, same GO stemgedrag ask). No reply yet; followed
>   up 2026-06-29. If GO enables/locates its votes too, Flevoland is likewise config-only → PS 10/12.
> - **Groningen, Zeeland — publish-as-data lobby candidates (probed 2026-07-05/06).** Not data-absence
>   dead ends: both *publish* per-fractie votes as **PDF** (Groningen Handelingen — both sides + totals;
>   Zeeland concept-besluitenlijst — fracties named), just not as machine-readable data. Re-probed 2026-07-06:
>   Groningen's Notubiz stemgedrag module is off (API empty + no portal markup), Zeeland's registers incl.
>   the `Stemmen` field are truly empty. Griffie mails sent ([outreach.md](outreach.md) §3). If they publish
>   as data → PS toward 12/12 (with Flevoland).
> - **Optional polish:** ✅ EP **Dutch-delegation breakout** shipped (second EP scope, by national party,
>   with MEP rosters). ✅ EP source attribution → HowTheyVote.eu. TK perf checked = fine (slightly slower
>   first load, no sluggishness after). Pick up gemeenteraden/waterschappen only on demand (parked).
>
> The architecture is proven: catalog (categories→scopes) + frontend landing/routing absorb a new category
> as "feasibility probe → new adapter → catalog entry" (no IA refactor); each is single-scope, opening
> straight to its table.
>
> **Provinciale Staten growth — status:**
> - **Notubiz: DONE (no token needed).** Notubiz declined a token 2026-06-15 (a token alone is
>   insufficient; would also need a rights-bearing account) — but it didn't matter: the data is fully
>   public (events + votings API at `version=1.21` + portal `vergadering` HTML). `collect_notubiz` shipped
>   the same day → 4 provinces live (ZH, Fryslân, Gelderland, Overijssel; Groningen's votings API empty
>   → auto-skipped, but publishes votes in its Handelingen PDF, so it's a lobby candidate). No
>   follow-up to send on the built four; an optional thank-you only.
> - **Griffie mails** ([outreach.md](outreach.md) §2, sent 2026-06-11 to `griffie@flevoland.nl` +
>   `Statengriffie@drentsparlement.nl`). **Drenthe paid off** (live 2026-07-05, GO path variant — see
>   above). **Flevoland still the only open outreach**; nudged 2026-06-29, awaiting reply before the
>   **zomerreces (~mid-July)**. (PDF-parsing rejected: fragile, per-griffie, low ROI.)
>
> **Parked categories (decided NOT to pursue):** gemeenteraden (~340 — fragmented, local, not national
> news, low per-unit salience) and waterschappen (elected but niche/low-profile). Reconsider only on demand.
>
> Frontend shipped beyond v1: category→scope landing + hash routing (deep-linkable/shareable), CSV export
> (atomic columns), matrix min-vote filter + greyed low-n cells, per-scope `granularity`, delegated pins.

> **DONE (Phase 3d):** iBabs adapter (`collect_ibabs`) built; **Noord-Holland** (181 items, faction-
> level, aangenomen only) and **Limburg** (321 items, **per-member counts incl. verworpen**) live as
> provinces 2 & 3. Adapter unions multiple reports per province and supports two vote formats
> (`votes`: `stemverhouding` = NH free-text, `stemmen` = Limburg structured counts). The other two
> iBabs provinces have **no structured vote feed**: **Zeeland** registers are empty; **Noord-Brabant**
> publishes outcome + indieners only. **But (probed 2026-07-05) neither is a data-absence dead end** —
> Zeeland's concept-besluitenlijst PDF names the voting fracties, and NB's verbatim notulen record full
> hoofdelijke stemming per lid. So both are publish-as-data lobby candidates, not impossibilities
> ([outreach.md](outreach.md) §3). Coverage + per-source **reliability**: [coverage.md](coverage.md).

v1 goal: a website where you pick a **province** and see a table — rows = moties,
columns = parties, cells = **V** (green) / **T** (red) / **-** (tie) / blank (afwezig).
Free to build and host. See [context.md](context.md) and [data-sources.md](data-sources.md).

## Architecture (static, free, vendor-agnostic)
No live DB/server. A build-time collector produces normalized static JSON per province;
the site just reads it.

```
 per-vendor adapters                normalized                static site (HTML+JS)
 ┌─ GO     (Utrecht, Drenthe)   ─┐   dataset
 ├─ iBabs  (Noord-Holland, …)   ─┼─▶ data/<province>.json ─▶  table views  ─▶ GitHub Pages
 └─ Notubiz(Overijssel, …)      ─┘   (the "union" step)            ▲
        ▲                                                          │
        └──────  GitHub Actions cron (weekly) re-runs + commits ───┘
```

Why a generated dataset (our "database") is needed even though V/T is just for>against:
1. **Union** of all moties across parties must be computed somewhere (a party absent for a
   motie is omitted from its own list).
2. **Normalization** across GO / iBabs / Notubiz (different JSON shapes).
3. **CORS / politeness / speed** — the browser can't/shouldn't call 12 provincial sites live.

Notes on "no server":
- Hosting serves only files (no server-side compute).
- The dataset is a **data file** (`data/<province>.json`), not a navigable page; it has a
  URL but users never visit it — the table page fetches it via JS.
- The JSON stores **raw counts** (`{agree,disagree,abstain}` per party); V/T is derived in
  the browser. Never store only V/T.
- The collector runs **manually (v1)** or via a free **GitHub Actions cron** that commits
  refreshed JSON — no server we manage.
- v1 reality: **Utrecht only**, but the UI ships with a province selector (only Utrecht
  selectable) so multi-province (v2) drops in without a redesign.

Common normalized schema (draft):
```
province, term, motie_id, date, type (motie|amendement|besluit|...), title, result,
votes: { "<party>": { agree, disagree, abstain } }   # absent party => key missing
```

## Steps

### Phase 0 — Finish scoping
- Map all 12 provinces → vendor + endpoint (table started in data-sources.md §6).
- Lock v1 scope (provinces included, item types included).

### Phase 1 — GO adapter + collector  ✅ DONE (`collector/collect.py`)
1. ✅ Party list from `/api/v2/groups` (type Fractie) + slugify (page mixes people).
2. ✅ Per party: `GET /Samenstelling/{slug}/votings` → per-party counts.
3. ✅ **Union** by `votingId`; cell = counts (missing ⇒ afwezig).
4. ✅ Date via `meetingId → /api/v2/meetings/{id}` (cached); filter to term ≥ 2023-03-29.
5. ✅ Classify type (motie / amendement / besluit / ordevoorstel; handles word + code form).
6. ✅ Writes `data/utrecht.json`. Polite (0.3s delay). Stdlib only.
   → First run: **566 stemmingen, 16 partijen** (motie 320, amendement 179, besluit 65,
     ordevoorstel 2), bereik 2023-05-31 .. 2026-06-03.

### Phase 2 — Frontend  ✅ DONE (`index.html` at repo root)
Served from repo root (GitHub Pages "deploy from branch" only allows root or /docs), loads
`data/utrecht.json`. Implements the locked v1 feature set: province selector, type chips,
party show/hide, search, pin + show-only-pinned, sort, result filter, "alleen omstreden",
raw-numbers toggle, split-vote markers, legend, source links, sticky header + first column.
Vanilla JS/CSS, no dependencies. `.nojekyll` added. Transpose/party-compare view = parked v1.1.

### Phase 3 — More vendors + publish + automate
10. Add iBabs and Notubiz adapters → more provinces, same schema.
11. GitHub Pages hosting; GitHub Actions weekly cron to refresh + commit data.

## v1 UI — feature set (LOCKED selection)
In v1 (curated from the brainstorm):
- **Province selector** — built from `data/provinces.json` (live: Utrecht, Noord-Holland, Limburg).
- **Type filter** — multi-select **chips** (motie / amendement / besluit / ordevoorstel),
  all on by default.
- **Parties** — checklist dropdown to show/hide columns (16 parties).
- **Text search** on title/indiener.
- **Pin** rows → pinned table at top + "toon alleen vastgepind" toggle.
  (Pin, not star. A full motie dropdown would be far too long.)
- **Sort** (date ↑/↓, result) + **filter by result** (aangenomen/verworpen).
- **"Alleen omstreden"** toggle — only stemmingen where parties disagreed.
- **Tooltips** with raw counts + a **raw-numbers toggle** (V/T ↔ "6–0").
- **Legend**, color-blind safe (letter + color), **link to source** per stemming.
- **Highlight split votes** (a fractie not unanimous).
- Party columns ordered by the site's `sortOrder` (already in the data).
- Responsive + sticky first row/column.

Cell display (LOCKED):
- **V** green = `agree > disagree` (voor)
- **T** red  = `disagree > agree` (tegen)
- **O** grey = tie or abstain-majority (onthouden)
- **blank** light-grey = afwezig (party absent for that stemming → not in its data)
- small marker (•) on V/T when the fractie was **not unanimous** (split vote)

Extra views (data already supports these):
- ✅ **Party-agreement matrix** (popup) — parties × parties heatmap, % of stemmingen where
  each pair voted the same. DONE.
- ❌ **Transpose view (moties as columns)** — DROPPED: motie titles are too long to be
  column headers; a single-party view is already possible by deselecting all but one party.
- ✅ **Party profile** (popup) — % on the winning side, voor/tegen/onthouden/afwezig totals,
  and the lone-dissenter list. Party picker + type chips. DONE.
- ✅ **Compare two parties** (popup) — % agreement + list of stemmingen where they differ,
  with V/T/O badges. Two pickers + type chips. DONE.
- ❌ link matrix cell click → open Compare for that pair — **DECIDED AGAINST** (2026-06-13): users may
  click a cell to copy/read the number and would be surprised to be navigated away.

Parked (v1.1 / v2):
- Shareable URL encoding filter state. Member-level detail (privacy: later).
- ✅ CSV download (filtered rows → semicolon CSV + BOM) — DONE.
- Other bodies (Tweede Kamer, etc.).

### Multi-province (Phase 3) — discovery done, see [provinces.md](provinces.md)
3a complete. Key finding: the clean per-party vote API looked **Utrecht-only** (GO stemgedrag
module seemed opt-in; Flevoland/Drenthe GO votes 404'd during discovery). **Corrected 2026-07-05:**
Drenthe's votes were live all along at a *different path* (`/Leden/...` vs Utrecht's
`/Samenstelling/...`) — surfaced via the griffie/GO, now shipped. Flevoland still 404. Vendor split: GO 3,
Notubiz 5, iBabs 4. iBabs + Notubiz are JS SPAs → votes need backend reverse-engineering
(one effort per vendor unlocks its 4–5 provinces); they expose **faction-level** votes
(fine for V/T, degrades "ruwe getallen"/split).
- **3b DONE**: collector has a PROVINCES registry + pluggable vendor adapters; frontend is
  province-driven (selector from `data/provinces.json`, per-province data + huisstijl).
- **3c DONE**: cracked the iBabs vote endpoints (data-sources.md §7).
- **3d DONE**: built the iBabs adapter (`collect_ibabs`) and shipped **Noord-Holland** (2nd
  province). Votes are faction-level (`agree/disagree = 1/0`); NH's motieregister holds
  *aangenomen* moties only (surfaced via `meta.note`).
- **Next**: replicate to the other iBabs provinces — **Limburg** (tier A `Stemmen`) and **Noord-Brabant**
  (tier A `Stemmen`, added 2026-07-06) are **done**; only **Zeeland** remains and its registers are empty
  (publish-as-data lobby, not config) — and/or crack **Notubiz** (5 provinces) once a token arrives.
- **Action — lobby for the easy wins**: e-mailed the Statengriffie of **Flevoland** and **Drenthe**
  (GO provinces) asking them to enable the GO **stemgedrag** module / publish per-party votes as
  open data like Utrecht. **Drenthe delivered (2026-07-05)** — the votes were live at a different path
  all along; config-only, now shipped. **Flevoland still pending.** Confirms the lobby-the-province
  (not GO) approach works. Same ask could apply to Notubiz provinces with the module off.

### Phase 4 — Tweede Kamer + category split  ✅ DONE (2026-06-11)
The first **second category** (legislative body) beyond Provinciale Staten. Realizes the
"pick **category** → pick **scope** → see the table" UX from [context.md](context.md). TK is not a
province, so the frontend's province-only model was generalized into a category→scope **catalog**.
**Shipped:** `collect_tk` adapter → `data/tweede-kamer.json` (~2,945 stemmingen, minified ~3 MB);
`main()` now writes `data/catalog.json` (categories→scopes, replacing `provinces.json`); the
frontend has a home/landing view, a category→scope picker, and URL-hash routing. The 4a/4b/4c notes
below are the as-built record.

**Why TK over the remaining provinces:** clean documented open-data API *with* per-fractie votes
(no scraping), national audience, same normalized schema. Beats PDF-parsing 2 GO provinces and isn't
blocked like Notubiz.

**4a — Probe the API (do FIRST, before any code).**
- Source: **`https://opendata.tweedekamer.nl`** — the official OData v4 / SyncFeed API (no auth, no
  formal token). Vote chain to verify: `Besluit` → `Stemming` (per-fractie) → `Fractie`
  (`ActorFractie` + `FractieZetelAantal` for seat counts), linked to `Zaak`/`Document` (motie /
  amendement / wetsvoorstel) and the `Activiteit`/`Vergadering` for the date.
- Confirm: per-fractie **seat counts** are present (→ granularity `member`, tier A like Utrecht),
  how to scope to the **current term** (post-2025 election), item-type classification, and the
  outcome field (aangenomen/verworpen).
- **Measure data size.** TK volume ≫ a province. The page loads one whole JSON; if `tweede-kamer.json`
  is multi-MB, term-scope hard and/or trim fields (and only then consider per-year splits). Decide
  after measuring — don't pre-optimize.

**4b — IA refactor (independent of the API; can land first).**
- **Catalog data model:** generalize `data/provinces.json` into a catalog of **categories →
  scopes**. Each category = a body (`tweede-kamer`, `provinciale-staten`); each scope flags
  `available` + its data file. TK is a category with a **single** scope.
- **Home view (NOT a separate page):** one `index.html`, with a landing/home *view state* shown when
  no scope is selected. The table + all popups (matrix, partijprofiel, vergelijken) are byte-for-byte
  shared between TK and PS — do **not** fork into two pages.
- **Two-level selector:** category → scope. Scope picker only appears for categories with >1 scope;
  a single-scope category (TK) goes **straight to the table** (no dead-end second click). Moving
  scope selection up to the home view declutters the table header.
- **Hash routing:** selection lives in the URL (`#tk`, `#ps/utrecht`). Delivers three things at once:
  the declutter, **shareable/deep-linkable URLs** (the parked v1.1 feature — now delivered here), and
  **SEO** (distinct URLs per body/scope, compounding the meta/OG work already shipped).

**4c — TK adapter.**
- New adapter (e.g. `collect_tk`) in `collector/collect.py`, writing `data/tweede-kamer.json` in the
  **same normalized schema** (parties = fracties, votes per fractie with seat counts). Register TK in
  the catalog and add it to the weekly GitHub Actions cron.

### Phase 5 — Eerste Kamer  ✅ DONE (2026-06-12)
The revising chamber (Senate, 75 seats, indirectly elected by the Provinciale Staten). Completes the
national parliament (Staten-Generaal). A single-scope category like TK.

**5a — Feasibility probe ✅ DONE (2026-06-12) — verdict: GO, tier B.** Full findings in
[data-sources.md](data-sources.md) §9. Summary:
- **No machine API.** The EK has no OData / opendata host / `/api` / SPARQL — it's a *separate* system
  from the TK gegevensmagazijn. Everything is **server-rendered HTML on `www.eerstekamer.nl`** (PARLIS).
- **Per-fractie positions ARE published**, two ways: (1) `/stemmingen_fractiegewijs` — structured per
  fractie (Voor/Tegen thumb + date + type + result + dossier), no NLP, but the link isn't unique per
  stemming (join ambiguity); (2) the **verslag** chair sentence `"Ik constateer dat de leden van de
  fracties van <VOOR> voor … en … van <TEGEN> ertegen, zodat het is <aangenomen|verworpen>"` — free
  text but **both sides named** (no "overige fracties" inference → more reliable than NH). A prototype
  parse mapped both sides to the 20-fractie universe cleanly.
- **Granularity = faction-level V/T, no seat counts → tier B** (EK votes *bij zitten en opstaan*; no
  tallies). Hamerstukken = uncontested; hoofdelijke (per-member) rare. Volume ≈ **600–700 stemmingen**
  over the term. **Term = current EK, installed 13 June 2023** (scope `>= 2023-06-13`; note EK term ≠ TK term).

**5b — Built `collect_ek` (as-built).** Even cleaner than the probe plan: the
`/stemmingen_per_vergaderdag?filter=alles` pages **embed the structured per-fractie voor/tegen lists
inline** (`<strong>voor:</strong> A, B en C<br><strong>tegen:</strong> …`), so no verslag fetch / free-
text parsing is needed. The adapter pages back to 2023-06-13 (following the site's own "eerdere
stemmingen" link), parses each stemming's voor/tegen, **aggregates hoofdelijke per-member rows to the
fractie**, merges one-member "het lid X" references into their fractie, and **skips hamerstukken** (no
breakdown). Result: `data/eerste-kamer.json` — **449 stemmingen, 21 fracties** (15 landelijke + 6
splinters), types {wetsvoorstel 171, motie 263, overig 15}, incl. verworpen, `granularity: "fractie"`,
tier B. Category `eerste-kamer` (single scope) added to the catalog; the weekly Action picks it up via
the full `collect.py` run. Frontend: generic (no IA change) — added a `.t-overig`/`Overig` type label,
EK SEO meta. `collect.py` gained an `ONLY=<keys>` env switch for fast single-scope re-runs. Recipe +
parser caveats: [data-sources.md](data-sources.md) §9; reliability: [coverage.md](coverage.md).

### Phase 6 — Europees Parlement  ✅ DONE (2026-06-13)
The EU's elected chamber (the EU's democratic-vote layer; the Council = governments, not in scope).
Single-scope category. **Present votes by European political group** (EPP, S&D, Renew, Greens/EFA,
ECR, The Left, PfE, ESN, NI), with the Dutch delegation as an optional breakout — **not Dutch MEPs only**.

**6a — Feasibility probe ✅ DONE (2026-06-13) — verdict: GO, tier A.** Full findings in
[data-sources.md](data-sources.md) §10. Summary:
- **Source = HowTheyVote.eu** (`https://howtheyvote.eu/api/votes`), which compiles the EP's official
  roll-call open data (the EP Open Data Portal serves the same data but in cumbersome RDF/XML). JSON API
  + weekly bulk CSV. License **ODbL 1.0** (attribution + share-alike).
- **`/api/votes/{id}` → `stats.by_group`** gives **exact per-group MEP counts** (FOR/AGAINST/ABSTENTION/
  DID_NOT_VOTE) → maps straight to `{agree,disagree,abstain}` at **group** level → **tier A (exact
  counts)**, granularity `member`. `member_votes` (per-MEP, with country) enables an optional NL breakout.
- **Scope = 10th term, votes `>= 2024-07-16`; 545 `is_main` votes** (498 adopted, 47 rejected) — ~Utrecht
  scale (amendment sub-votes excluded). Only roll-call votes are per-MEP (inherent). Groups change mid-
  term but `stats.by_group` reflects the group at vote time (no first_seen gating needed).

**6b — Built `collect_ep` (as-built).** Pages `/api/votes?page_size=100` to the term boundary, then
fetches each `/api/votes/{id}` for `stats.by_group` → exact per-group `{agree,disagree,abstain}`
(+ `procedure` → item type). The API is ~1.5s/request, so the 545 detail calls run through a stdlib
**`ThreadPoolExecutor` (8 workers)** to keep wall-time ~2 min (sequential would be ~15). Result:
`data/europees-parlement.json` — **545 votes, 9 groups** (EPP, S&D, PfE, ECR, Renew, Greens/EFA, The
Left, ESN, NI), types {wetgeving 183, resolutie 127, initiatiefverslag 118, begroting 30, overig 87},
498 adopted / 47 rejected, `granularity: "member"` (exact counts → tier A). Validated: the Ukraine-
accountability vote shows the coherent mainstream-V / far-left+far-right-T split. Category
`europees-parlement`; weekly Action picks it up via the full run. Frontend (generic): EP
procedure-type labels/badges + the "het Parlement" article fix + EP SEO meta. Recipe + caveats:
[data-sources.md](data-sources.md) §10; reliability: [coverage.md](coverage.md).

**6c — Dutch-delegation breakout (polish, 2026-06-13).** A **second EP scope** "Nederlandse
afvaardiging": the 31 NL MEPs grouped by **national party** (PVV, GL-PvdA, VVD, …) with exact MEP
counts + an MEP roster per party (column tooltip). Built on the same cached vote details (no extra
fetch) via `ep_assemble_nl` (filters `member_votes` country `NLD`). The NL→party map (`EP_NL_PARTY`)
is resolved once from the **EP Open Data Portal** (`NATIONAL_POLITICAL_GROUP` membership; HowTheyVote
lacks it) and WARNs on unmapped ids. EP is now multi-scope (a "Kies een weergave" picker); the
frontend's province-centric copy was generalized via `scopeNoun`. Surfaces Dutch-vs-Euro-group
divergence (e.g. PVV abstaining where PfE carried a vote).

### Phase 7 — Notubiz provinces  ✅ DONE (2026-06-15)
Four more **Provinciale Staten** via one new vendor adapter (`collect_notubiz`) — **no API token needed**.
Not a new category; PS grows **3/12 → 7/12**. Feasibility + as-built recipe: [data-sources.md](data-sources.md) §11.

**7a — Feasibility probe ✅ (2026-06-15) — verdict: public, tier A.** Notubiz declined a token, but the
PS vote data is fully reachable from public surfaces: the events + votings API (`version=1.21`) and the
portal `vergadering` HTML (per-fractie breakdown with exact member counts). The auth-walled
`role_id → fractie` map isn't needed — the portal already names the fractie + members.

**7b — Built `collect_notubiz` (as-built).** Hybrid: the API discovers meetings (filter the plenary
`gremium_id`, `agenda_item_count>0`) and gives each stemming's title/result/`voting_type`; the portal
page gives the per-fractie counts (count the member `<li class="in_favor|against">` rows; `chart_<id>` ==
votings API `id`). Every parsed total is cross-checked against the API's per-member votes (no mismatches).
Result: **Zuid-Holland** 1062, **Fryslân** 807, **Gelderland** 429, **Overijssel** 549 stemmingen — all
tier A (`granularity: "member"`, incl. verworpen + the odd *staken* tie). Item type from `voting_type`
(null for Gelderland / much of ZH → title-code fallback, incl. Frisian "Moasje"/"Amendemint"). Spelling
variants merged (`NOTUBIZ_ALIASES`); non-fractie labels dropped (`NOTUBIZ_SKIP` "Geen partij"); member
names parsed but not stored (party-level, privacy). **Groningen** (also Notubiz) has an **empty votings
API** (0 across all 38 plenary meetings) so the adapter skips it — but it's not a data-absence dead end:
a 2026-07-05 probe found the votes in its Handelingen PDF (lobby candidate, see the NEXT block).
Frontend: generic (no IA change — four new scopes in the catalog,
each with its own huisstijl). The weekly Action picks them up via the full `collect.py` run. Reliability:
[coverage.md](coverage.md).

### Phase 8 — Drenthe (GO, griffie-lobby win)  ✅ DONE (2026-07-05)
The **first province unlocked purely by outreach**, and a reminder that a "votes 404" during discovery
isn't always a dead end. Drenthe runs the same **GemeenteOplossingen** stack as Utrecht; back in Phase 3
its `/Samenstelling/{slug}/votings` returned nothing, so it was filed as "GO stemgedrag module off." The
2026-06-11 griffie mail (+ 2026-06-29 nudge) prompted the Statengriffie to have GO investigate; GO reported
the data was live all along at a **different path** — `/Leden/{slug}/votings` (Utrecht uses
`/Samenstelling/...`). Same JSON schema, so the fix was **config-only**: a `votings_path` key on the
SOURCES entry (default `"Samenstelling"`, Drenthe `"Leden"`) + one `classify()` tweak so "Statenstuk …"
titles map to *besluit* (Drenthe labels its statenvoorstellen that way; 173 would otherwise land in
*overig*). Result: **443 stemmingen, 15 fracties, tier A** (`granularity: "member"`, per-fractie member
counts incl. verworpen). PS **7/12 → 8/12**. Only **Flevoland** (same GO ask, still awaiting reply)
remains of the easy GO wins. Reliability: [coverage.md](coverage.md).

### Phase 9 — Noord-Brabant (iBabs, false-negative recovery)  ✅ DONE (2026-07-06)
The **second province unlocked via outreach — but the data was already there.** A 2026-07-05 publish-as-data
mail drew a griffie reply (Emma Beers) pointing to the "toon stemmen" toggle. NB runs iBabs like Limburg, and
its motie/amendement **item detail** carries the same structured **`Stemmen`** field
(`vote-summary-legend-in-favour/-against`, per-fractie member counts). We'd mis-filed NB as "notulen-only"
because the *report row* (`GetReportData`) and the `Stemverhouding` field are both empty — we never checked the
*other* vote field on the detail page. Fix was **config-only**: a SOURCES entry (`votes: "stemmen"`, Moties
`376cf779-…` + Amendementen `0b5f0bd5-…`) reusing the Limburg parser, plus a CU-SGP alias (NB switched the
combined fractie's spelling from `ChristenUnie/SGP` to `ChristenUnie-SGP` in 2026). Result: **628 stemmingen,
15 fracties, tier A**. PS **8/12 → 9/12**. Lesson: on iBabs, always check **both** `Stemverhouding` *and*
`Stemmen` on the item detail before concluding a province has no structured votes. Reliability:
[coverage.md](coverage.md).

### Phase 10 — Historische termijnen (Tweede/Eerste Kamer, EP)  ✅ DONE (2026-07-07)
Extended the national/EU bodies **back through previous parliamentary terms** — chosen over the
Provinciale-Staten previous cycle because the national sources are cleaner (3 stable APIs vs 12 vendors)
and, crucially, **actually hold the coronaperiode as structured data** (the Notubiz PS provinces recorded
zero structured votes during 2020, so a PS backfill would have a COVID hole). Now covers the coronawet /
avondklok / toeslagenaffaire votes.
- **Model:** one **scope per term** (reuses the category→scope picker as a "Kies een periode" term
  picker). Config-only: `term_bounds(p)` = `[term_start, term_end)`; the current term leaves `term_end`
  open, previous terms set it to the next term's installation. `_TK_TERMS`/`_EK_TERMS`/`_EP_TERMS` append
  the previous-term SOURCES entries programmatically from each body's current entry. **22 SOURCES total.**
- **Adapters:** TK adds one OData date bound; EK and EP were refactored to crawl/fetch their full history
  **once** (cached by base) and slice per term — otherwise every term would re-crawl.
- **What shipped:** TK **2008→now, all 6 previous terms, tier A** (~58 k stemmingen); EK **2019–2023 +
  2015–2019** (tier B); EP **2019–2024** (tier A, Europese-fracties view). ~60 k extra stemmingen.
- **Source limits found:** TK OData floor = **2008** (hard cliff); EK archive reaches only **~mid-2015**
  (2011/2007 terms not served → dropped); EP floor = **2019-07** (HowTheyVote). EP **NL-afvaardiging is
  current-term only** — the historical MEP→partij map isn't built, so we ship only the complete group
  view for 2019–2024 (follow-up: build it from EP Open Data).
- **Size solve (the real one, not "accept it"):** a 4-year TK term is ~14 MB. `write_scope` chunks any
  scope > 5 000 stemmingen into **per-year files + a manifest**; the frontend loads the newest year first
  (~0.8 MB first paint), streams the rest in the background, and adds a **"Periode" (jaar) filter** that
  caps the rendered table while analyses use the whole loaded term. Weekly reruns only rewrite the current
  year's file (no git churn). Verified end-to-end with Playwright. Reliability: [coverage.md](coverage.md).

## Decisions
**Locked**
- Period: **current term per body** for Provinciale Staten (2023–2027). For the national/EU bodies we now
  keep **every past term** as a selectable scope (Phase 10): Tweede Kamer back to 2008, Eerste Kamer to
  ~2015, Europees Parlement to 2019. Each term's boundary is `term_bounds(p)` in its `SOURCES` entry.
  (PS previous cycle deliberately **not** pursued: 4 of 9 live PS provinces recorded no structured votes
  during the coronaperiode, so a PS backfill would have a COVID hole — the national bodies don't.)
- Stack: Python (collector). Frontend: dependency-light HTML/JS.
- Body: Provinciale Staten plenair only (commissies don't hold the votes).
- Source strategy: per-vendor adapters; OpenBesluitvorming only as cross-check/fallback.
- Provinces in v1: **Utrecht only**, UI multi-province-ready (selector offers only Utrecht).
- No server: static hosting + JSON data file (raw counts) + manual/Actions-cron collector.
- Item types: include moties + amendementen + besluiten, with the type multi-select filter.

- Item types: include moties + amendementen + besluiten + ordevoorstellen, type filter (chips).
- Cell display + edge cases: locked (see "v1 UI" above).
- Refresh: **GitHub Actions weekly cron** (Thu 06:00 UTC — day after the usual Wed
  Statenvergadering) + manual dispatch. Live & verified in `.github/workflows/refresh.yml`.
- Privacy: v1 party-level only (no member names). Member-level = personal data, later.
- **Domain**: SETTLED — free `*.github.io`, no custom domain (can revisit later, not planned).
- **Transpose view**: SETTLED — will NOT add; deselecting all-but-one party already gives a
  single-party view, so it's unnecessary (see dropped note above).
- **Category scope**: LOCKED (2026-06-12) to **four** bodies — Tweede Kamer, Eerste Kamer,
  Provinciale Staten, Europees Parlement — **all four now LIVE (2026-06-13)**. Gemeenteraden +
  waterschappen explicitly **parked** (see the NEXT block).

## Cost
€0 with GitHub (repo + Pages + Actions) and a free `*.github.io` domain. Only a custom
domain costs money (optional, later).

## Categories (same architecture) — target set COMPLETE
Target set (LOCKED 2026-06-12, all LIVE 2026-06-13): **Tweede Kamer** ✅, **Eerste Kamer** ✅,
**Provinciale Staten** ◑ (3/12 provinces — growth is the outreach track), **Europees Parlement** ✅
(two views: Europese fracties + Nederlandse afvaardiging). Each = a new adapter feeding the same
frontend (a category/scope in the catalog; the IA absorbed all four with no refactor). **Parked** (not
pursuing now): gemeenteraden (fragmented/local/low-profile) and waterschappen (niche). The Council of
the EU is out of scope (it's governments negotiating, not an elected chamber).
