# Coverage & reliability — what we actually have

What's **live in the dataset** today, how it was obtained, and **how much to trust it**. This is
the "things we DO have" companion to [provinces.md](provinces.md) (feasibility for the rest),
[outreach.md](outreach.md) (who to ask), and [roadmap.md](roadmap.md) (the plan).

> Reliability is the easy thing to forget: every province shows the same green **V** / red **T**,
> but one is read from exact per-member counts and another is *inferred* from parsed free text.
> The column below says which.

## Coverage table

| Scope | Category | Vendor | Method | Granularity | Item types | Items | Scope of items | Reliability |
|---|---|---|---|---|---|---|---|---|
| **Tweede Kamer** | Tweede Kamer | TK OData | clean OData v4 API | per **fractie** (zetels) | motie, amendement, wetsvoorstel | 2945 | **aangenomen + verworpen** | **A — exact** |
| **Eerste Kamer** | Eerste Kamer | eerstekamer.nl | HTML structured parse | per **fractie** (V/T only) | wetsvoorstel, motie, overig | 449 | **aangenomen + verworpen** | **B — parsed (beide zijden vermeld)** |
| **Europees Parlement — Europese fracties** | Europees Parlement | HowTheyVote.eu API | clean JSON API | per **fractie** (MEP-aantallen) | wetgeving, resolutie, initiatiefverslag, begroting | 545 | **aangenomen + verworpen** | **A — exact** |
| **Europees Parlement — Nederlandse afvaardiging** | Europees Parlement | HowTheyVote API + EP Open Data | JSON API + portal map | per **NL-partij** (MEP-aantallen) | idem | 545 | **aangenomen + verworpen** | **A — exact** |
| **Utrecht** | Prov. Staten | GO | clean JSON API | per **member** (counts) | motie, amendement, besluit, ordevoorstel | 566 | all (aangenomen + verworpen) | **A — exact** |
| **Drenthe** | Prov. Staten | GO | clean JSON API | per **member** (counts) | motie, amendement, besluit | 443 | **aangenomen + verworpen** | **A — exact** |
| **Limburg** | Prov. Staten | iBabs | HTML structured parse | per **member** (counts) | motie, amendement | 321 | **aangenomen + verworpen** | **A — exact** |
| **Noord-Holland** | Prov. Staten | iBabs | HTML free-text parse | per **fractie** (V/T only) | motie, amendement | 181 | **aangenomen only** | **B — parsed/inferred** |
| **Zuid-Holland** | Prov. Staten | Notubiz | API + portal HTML parse | per **member** (counts) | motie, amendement, besluit, ordevoorstel | 1062 | **aangenomen + verworpen** | **A — exact** |
| **Fryslân** | Prov. Staten | Notubiz | API + portal HTML parse | per **member** (counts) | motie, amendement, besluit | 807 | **aangenomen + verworpen** | **A — exact** |
| **Gelderland** | Prov. Staten | Notubiz | API + portal HTML parse | per **member** (counts) | motie, amendement, besluit, ordevoorstel | 429 | **aangenomen + verworpen** | **A — exact** |
| **Overijssel** | Prov. Staten | Notubiz | API + portal HTML parse | per **member** (counts) | motie, amendement, besluit | 549 | **aangenomen + verworpen** | **A — exact** |

(Counts as of the last refresh; the weekly Action keeps them current. TK = current term, 2025–heden.)

> **Provinciale Staten: 8/12 live** (Utrecht, Noord-Holland, Limburg, Zuid-Holland, Fryslân,
> Gelderland, Overijssel, **Drenthe**). The 4 Notubiz provinces above are **tier A** — the portal records
> each vote hoofdelijk (per member), so we aggregate exact per-fractie counts. **Drenthe** (added
> 2026-07-05) is GO like Utrecht — tier A per-member counts — reached via the `/Leden/...` votings path
> after the griffie lobby (see §2b in data-sources.md). The remaining four (Groningen, Noord-Brabant,
> Zeeland, Flevoland) are **not data-absence dead ends** — see the callout below.

> **The four not-yet-live provinces all *record* per-fractie votes; the gap is machine-readability, not
> secrecy** (probed live 2026-07-05). **Groningen** (Notubiz) — the votings API is empty, but the
> **Handelingen** (verbatim report) name both sides per fractie **with totals**. **Zeeland** (iBabs) — the
> structured reports (Moties/Amendementen/Stemming) are all empty, but the **concept-besluitenlijst** PDF
> names the voting fracties per item ("aangenomen met de stemmen van de fracties van … voor"). **Noord-
> Brabant** (iBabs) — the Moties report gives only outcome + *indienende* fracties; the verbatim **notulen**
> record full **hoofdelijke stemming per lid** (member-name voor/tegen lists) — richest of the three.
> **Flevoland** (GO) — awaiting the griffie lobby. So all four are candidates for the *publish-as-data*
> lobby (the Drenthe path), or fragile PDF-parsing as a last resort. See [outreach.md](outreach.md) §3.

> Note: vendor ≠ reliability. Both Limburg and Noord-Holland run iBabs, but Limburg's portal
> publishes structured per-member vote counts (tier A) while NH publishes only free-text faction
> outcomes (tier B). The portal's *vote format* decides the tier, not the vendor.

## Reliability tiers

How directly the published data maps to what we display, and how much we infer.

- **A — exact (structured source).** The source gives the vote itself as structured data; we
  normalize, we don't interpret. Exact counts and real split votes; minimal inference.
  *Tweede Kamer* (OData `Stemming` — per-fractie `Soort` + `FractieGrootte` seat counts),
  *Europees Parlement* (HowTheyVote.eu `stats.by_group` — exact per-group MEP counts FOR/AGAINST/
  ABSTENTION; a group split across FOR/AGAINST is a real split), *Utrecht* and *Drenthe* (GO JSON,
  per-member tallies), *Limburg* (iBabs "Stemmen" field — per-fractie member counts for the voor/tegen sides) and
  the **four Notubiz provinces** (*Zuid-Holland, Fryslân, Gelderland, Overijssel* — the portal lists
  every member's own voor/tegen vote, so counts and intra-fractie splits are exact).
- **B — parsed / inferred (semi-structured source).** The outcome is published, but as text/HTML we
  must parse, and (for NH) part of the result is *computed* rather than stated. Correct for "which
  fractie voted voor/tegen" on the items present, with the caveats below. *Noord-Holland* (iBabs
  "Stemverhouding" — one side named + "overige fracties" inferred) and *Eerste Kamer* (eerstekamer.nl
  HTML — **both** sides named, so nothing inferred, but no seat counts). Both are faction-level V/T.
- **C — derived / unavailable (not implemented).** Votes exist only as **unstructured PDF prose**, not
  machine-readable. This is where **Groningen** (Notubiz Handelingen — both sides + totals), **Zeeland**
  (iBabs concept-besluitenlijst — voting fracties named), **Noord-Brabant** (verbatim notulen — full
  member-name roll-call) and **Flevoland** (GO besluitenlijsten) sit today — the votes *are* published, just not as data (probed
  2026-07-05). Drenthe was here too until 2026-07-05, when its structured votes surfaced at the `/Leden/...`
  path → now tier A. Parsing these PDFs is possible (Zeeland NH-style tier B; Groningen richer but verbatim)
  yet fragile/per-province, so it's deprioritized in favour of the publish-as-data lobby. The Notubiz
  `role_id → fractie` API map *is* auth-gated, but it turned out we don't need it — the four live Notubiz
  portals already name the fractie + members (tier A; §11). **Nothing in the shipped dataset is tier C** —
  tier C describes the four not-yet-collected provinces.

## Per-scope caveats (what could be wrong, and why)

### Tweede Kamer — tier A
- Votes come straight from the OData `Stemming` entity: per fractie a `Soort` (Voor/Tegen/Niet
  deelgenomen) and `FractieGrootte` (seat count). Exact tallies, self-contained per besluit — nothing
  inferred (unlike NH). Includes **verworpen**. We keep only besluiten with an actual roll-call
  (`Stemming/any()`), so items decided *zonder stemming* / aangehouden / ingetrokken drop out.
- **Three vote shapes, one counting rule** (verified — each besluit's seats sum to ≤150):
  a *block* vote = one row per fractie (use `FractieGrootte`); a *hoofdelijke* stemming = one row
  **per member** (each carries the full fractie size — count 1 per row, not the size); *block +
  aantekening* = a block row plus per-member rows for deviating members (count the members as 1 and
  subtract them from the block, so they aren't double-counted). A fractie whose members split on a
  hoofdelijke vote correctly shows a real split (V + dot, or O).
- **Rare upstream inconsistencies.** The official `BesluitSoort` is the source of truth for the
  outcome and we mirror it; on ~1 item in ~3,000 it disagrees with the seat tally (e.g. a motie
  marked *aangenomen* that tallies 71–79). We don't "correct" the source — the per-fractie positions
  are still shown verbatim. 75–75 ties recorded as *verworpen* are genuine, not errors.
- **Term scope:** current Kamer only (votes on/after 2025-11-13, the first stemming after the Oct 2025
  election). Old-composition votes cast before installation are excluded so fractie sizes stay consistent.
- **Mid-term composition:** `ActorFractie` is the name *at vote time*. We merge the pure rename
  GroenLinks-PvdA → "Progressief Nederland" into one column; splinters (Groep Markuszower, Keijzer)
  are their own columns — accurate, if visually busier. `Persoon_Id`-level (hoofdelijke) votes aren't
  split out; we aggregate to the fractie.
- **Volume:** ~2,945 stemmingen → the data file is ~3 MB (written minified) and the table renders
  ~3k rows × ~18 columns. Watch frontend performance; revisit pagination/virtualization if it drags.

### Europees Parlement — tier A (exact per-group counts)
The unit is the **European political group** (EPP, S&D, PfE, ECR, Renew, Greens/EFA, The Left, ESN,
NI), not individual MEPs or Dutch MEPs only. Source: HowTheyVote.eu `stats.by_group` (see
[data-sources.md](data-sources.md) §10), which compiles the EP's official roll-call open data.
1. **Exact counts.** Each group's FOR/AGAINST/ABSTENTION MEP counts are given verbatim, so tallies and
   intra-group splits (a group voting partly FOR, partly AGAINST) are real — `granularity: "member"`.
2. **Roll-call votes only.** Only votes taken by roll call are recorded per-MEP; show-of-hands votes
   aren't published per group anywhere (inherent to the EP, like every source here). We keep only the
   **`is_main`** (final) votes per file — amendment/procedural sub-votes are excluded.
3. **Group at vote time.** `stats.by_group` reflects each MEP's group on the vote date, so a mid-term
   group switch is handled upstream — no inference on our side.
4. **Term:** current (10th) EP, votes on/after 2024-07-16. (Differs from the TK and EK terms.) Includes
   **verworpen** (47 of 545).
5. **Licence/attribution:** HowTheyVote.eu data is ODbL; `meta.license` credits HowTheyVote.eu + the
   European Parliament.
6. **Two views (scopes).** *Europese fracties* (by Euro-group) and *Nederlandse afvaardiging* (the 31
   NL MEPs grouped by **national party** — PVV, GL-PvdA, VVD, …, with exact MEP counts + an MEP roster
   per party in the column tooltip). The NL party mapping comes from the **EP Open Data Portal**
   (`NATIONAL_POLITICAL_GROUP` membership; HowTheyVote lacks it) — a static map topped up on a WARN.
   This surfaces where a Dutch party diverges from its Euro-group (e.g. PVV abstaining on a vote PfE
   carried). Same vote set and tier (A) as the group view.

### Eerste Kamer — tier B (faction-level, but both sides stated)
The Senate has **no machine API** (see [data-sources.md](data-sources.md) §9); we parse the per-fractie
voor/tegen lists embedded in the "stemmingen per vergaderdag" HTML pages. More reliable than NH (both
sides are named, so nothing is inferred), but less than the tier-A sources (no seat counts).
1. **No exact counts.** The EK votes *bij zitten en opstaan* — only a per-fractie voor/tegen, no
   tallies. Stored `1–0`; the UI reads `granularity: "fractie"` and hides "ruwe getallen". Agreement %s
   weight every fractie equally (not by zetels).
2. **Both sides named — no "overige fracties" inference** (unlike NH). The voor and tegen fractie lists
   are published in full, so the matrix is read directly, not computed.
3. **Hamerstukken are excluded.** Items passed *zonder stemming* (hamerstuk) carry no voor/tegen
   breakdown (only an optional "aantekening gevraagd") and are skipped — consistent with keeping only
   real roll-calls (as for the TK). So the dataset is the **contested** votes, incl. **verworpen**.
4. **Hoofdelijke (per-member) votes are aggregated to the fractie.** Those rare votes list individual
   senators (`Naam (Fractie)`); we roll them up to the fractie (a fractie split across members → O +
   split). Member-level counts are not retained (faction-level by design).
5. **Splinter fracties** (Fractie-Beukering, -Van de Sanden, -Visseren-Hamakers, -Walenkamp, -Kemperman,
   -Van Gasteren) appear as their own columns when named; one-member references ("het lid X") are merged
   into the matching fractie. **Term:** current EK (installed 13 June 2023) — note this differs from the
   TK term (2025–heden).

### Utrecht — tier A
- The dataset mirrors the GO stemgedrag module. The main residual risk is upstream: if a vote was
  mis-recorded in the source, we faithfully reproduce it. Dates are resolved via `meetingId`.
- Practically nothing is inferred on our side.

### Drenthe — tier A
- Same GO stemgedrag module and adapter as Utrecht, so the same "mirrors the source, nothing inferred"
  guarantee holds — reached via the `/Leden/{slug}/votings` path (Utrecht uses `/Samenstelling/...`;
  see data-sources.md §2b). Per-member voor/tegen counts, incl. verworpen. Added 2026-07-05.
- Type labels: Drenthe titles its statenvoorstellen "Statenstuk YYYY-NN; …" → classified as *besluit*
  (added to the shared `classify()`). Moties/amendementen use "M …"/"A …" codes with the words spelled
  out. One item (0.2%) stays *overig* — a source typo ("Staenstuk", missing a t) not worth special-casing.
- Column universe: only groups typed `Fractie` in the GO `groups` API that actually cast votes appear;
  the role-typed pseudo-fracties (Voorzitter, Gedeputeerde, …) drop out for want of votings data.

### Limburg — tier A
- The "Stemmen" field lists each fractie with its member count on the voor and tegen sides, so
  counts and splits are exact (27 in-term moties have a real fractie split). **Includes verworpen**
  moties and amendementen — the only iBabs province so far with rejected items.
- The one gap: moties/amendementen decided **without a hoofdelijke stemming** (bij acclamatie /
  handopsteken) carry no per-fractie tally and are skipped. In practice this only drops the
  ingetrokken/aangehouden items; essentially all *decided* moties have a recorded breakdown.
- Local fracties (LOKAAL-LIMBURG, Horizon, oos limburg, SVL) pass through un-aliased.

### Zuid-Holland, Fryslân, Gelderland, Overijssel (Notubiz) — tier A
The four Notubiz provinces share one adapter (`collect_notubiz`); see [data-sources.md](data-sources.md)
§11. No API token is needed: the public events + votings API (`version=1.21`) discovers the plenary
meetings and gives each stemming's title/result, and the public **portal** vergadering page carries the
per-fractie breakdown with exact member counts.
1. **Exact per-member counts.** The portal lists each fractie with its members tagged voor/against; we
   count them, so tallies and intra-fractie splits are real — `granularity: "member"`. The `chart_<id>`
   div joins 1:1 to the votings API `id`, and we **cross-check** every parsed total against the API's
   own per-member votes (the collector WARNs on any mismatch; none in the current data).
2. **Includes verworpen** (and the occasional *staken van stemmen* → tie). The dataset is the items
   that went to a **hoofdelijke stemming**.
3. **Items without a roll-call are skipped.** Agenda votings decided *bij acclamatie* / without a
   recorded hoofdelijke stemming carry no per-fractie breakdown (the API returns them with no votes and
   no result) and drop out — consistent with Limburg/EK. Members who didn't take part in a stemming
   aren't in its tally.
4. **Item type** comes from the API's `voting_type` (motion/amendment/council_proposal) where present,
   else from the title's code prefix — which differs per province ("M 1567"/"A 873"/"SV …" ZH,
   "26M45" Gelderland, "PS26-M52"/"PS26-MV9" Overijssel) or Frisian on Fryslân ("Moasje"/"Amendemint").
5. **Mid-term composition.** Spelling variants / pure renames are merged into one column (ZH:
   GroenLinks-PvdA ↔ "PRO"; "Partij voor de Dieren" ↔ "PvdD"); fracties that genuinely existed
   separately before a merger are kept separate. One-person afsplitsingen are their own named columns
   (Fryslân "Steatelid Van Dijk"/"Jonker", Gelderland "Groep Roerdink"/"Claassen"); a non-fractie label
   ("Geen partij" — a member mid-afsplitsing with no fractie yet) is dropped, not shown as a party.
6. **Coverage starts when the portal does.** Gelderland's published votings begin 2024-01-31 (no
   per-fractie charts for its 2023 plenary meetings); the others reach back to term start (April 2023).
7. **Personal data.** Votes are recorded per member, but the dataset is kept **party-level** (member
   names are not stored) — consistent with the v1 privacy stance.

### Noord-Holland — tier B
Reliable for the headline question ("did fractie X vote voor or tegen this adopted motie?"), but
know these limits before trusting an exact figure:
1. **No exact counts.** Votes are stored `1–0` per fractie. The UI reads `meta.granularity:
   "fractie"` and **hides the "ruwe getallen" toggle** (and describes cells in words, not "1 voor
   0 tegen") so the missing counts aren't shown as if real. Agreement %s weight every fractie
   equally (not by zetels).
2. **"Overige fracties" is inferred, not stated.** The losing side is named; the winning side is
   "overige fracties", which we expand against a *computed* party universe (built from the data)
   minus afwezig/split, with a `first_seen` gate for mid-term splinters. This is the layer most
   likely to hide a subtle error — it's an assumption about who was in the room.
3. **Free-text parsing.** Stemverhouding is inconsistent prose (glued labels, stray spaces,
   "Verdeeld gestemd:" clauses). The parser handles every form seen so far; a *novel* phrasing
   could be mis-read or skipped (the collector logs "no parseable vote" counts — watch them).
4. **Splits/abstentions are lossy.** A split shows only when the portal writes "Verdeeld gestemd";
   abstentions aren't represented at fractie level.
5. **Adopted only.** The iBabs registers track *aangenomen* moties/amendementen — **verworpen items
   are absent entirely** (not published per-fractie anywhere on the portal; see the gap below).

## Known gaps to revisit
- **Niet-aangenomen items (some iBabs provinces).** Limburg publishes verworpen items; **Noord-Holland
  does not** (its registers are adopted-only — rejected ones live only in besluitenlijst/notulen PDFs).
  So the gap is portal-specific, not vendor-wide.
- **Faction-level provinces lose "ruwe getallen" / exact splits** — inherent to iBabs *free-text*
  provinces (NH). The Notubiz provinces are the opposite: per-member counts, so tier A.
- **The four not-live provinces publish votes only as PDF (probed 2026-07-05, corrects earlier "dead
  end" wording).** **Zeeland**'s structured Stemming/Moties/Amendementen reports are empty, but its
  **concept-besluitenlijst** PDF names the voting fracties per item. **Groningen**'s Notubiz votings API
  is empty, but its **Handelingen** name both sides + totals. **Noord-Brabant**'s Moties report is
  outcome + indieners only; its verbatim **notulen** record full **hoofdelijke stemming per lid**
  (member-name roll-call, confirmed). **Flevoland** (GO) is the griffie-lobby case. None is a data-absence dead end — the votes
  are recorded and public, just not machine-readable → publish-as-data lobby (see [outreach.md](outreach.md)
  §3), with fragile PDF-parsing as a fallback.
- **Spot-checking.** Tier-B data isn't self-verifying; eyeball a few moties against the portal after
  big parser changes. Method per source is in [data-sources.md](data-sources.md).
