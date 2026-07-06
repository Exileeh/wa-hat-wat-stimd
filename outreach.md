# Outreach — draft e-mails to unlock more provinces

Two low-cost asks that could turn hard provinces into easy ones. See [provinces.md](provinces.md)
for why. Both are about **open data**, so there's good precedent (Utrecht already does this).

---

## 1. Notubiz — request an open-data API token
> **✅ Sent 2026-06-10.** Awaiting reply. If granted, build the Notubiz adapter (see roadmap NEXT).
> **Follow-up:** if silent by **~17 June** (≈1 week), send the nudge below. A company support inbox
> usually moves within days, so a short reminder mostly serves to surface a filtered/missed mail.
>
> _Reminder draft (reply on the original thread, keeping the first mail quoted below):_
> > Beste Notubiz,
> >
> > Vorige week (10 juni) stuurde ik onderstaand verzoek om een open-data API-token voor de stemdata
> > van de Provinciale Staten. Ik begrijp dat het druk kan zijn — zou u kunnen laten weten of dit
> > mogelijk is, of mij naar de juiste persoon kunnen verwijzen? Alvast dank!
> >
> > Met vriendelijke groet, [naam]

**Unlocks (if granted):** Fryslân, Groningen, Gelderland, Zuid-Holland, Overijssel (5 provinces).
**Why:** `api.notubiz.nl/agenda_items/votings` already gives outcomes + roll-call publicly, but
votes are keyed by `role_id` and the `role_id → fractie` map sits behind the auth-gated `/roles`
endpoint. A token lets us group votes per party.

**To:** Notubiz support / open data (info@notubiz.nl)
**Onderwerp:** Verzoek om API-token voor open stemdata (Provinciale Staten)

> Beste Notubiz,
>
> Ik bouw een open, non-commercieel overzicht van het stemgedrag **per fractie** in de
> Provinciale Staten (open data, gratis toegankelijk). Via `api.notubiz.nl/agenda_items/votings`
> kan ik de uitslagen en de hoofdelijke stemmingen (`role_id` + stem) ophalen, maar de koppeling
> `role_id → fractie` zit achter het `/roles`-endpoint, dat authenticatie vereist.
>
> Zouden jullie mij een API-token kunnen verstrekken voor open-data gebruik, zodat ik
> `/roles` (`field_id=105`, per `meeting_id`) kan opvragen om de stemmen per fractie te groeperen?
> Het gaat om de provincies die op jullie platform draaien: Fryslân, Groningen, Gelderland,
> Zuid-Holland en Overijssel.
>
> Het project is open en non-commercieel; u kunt het hier bekijken:
> – Website: https://carefulcamel61097.github.io/wie-stemde-wat/
> – Broncode: https://github.com/carefulCamel61097/wie-stemde-wat
> (Provincie Utrecht, Noord-Holland en Limburg zijn er al in opgenomen.)
>
> Alvast hartelijk dank,
> [naam]

> **Tip:** de twee links (website + repo) zijn het overtuigendst — ze laten zien dat het een echt,
> open, non-commercieel project is. Dat helpt meer dan alleen het technische endpoint. Vul je eigen
> naam in bij `[naam]`.

---

## 2. Statengriffie Flevoland & Drenthe — enable the GO stemgedrag module
> **✅ DRENTHE DONE (live 2026-07-05).** Mailed 2026-06-11, nudged 2026-06-29; the Statengriffie had
> GemeenteOplossingen investigate. Verdict: the votes were **published all along, at a different path**
> (`/Leden/{slug}/votings`, not Utrecht's `/Samenstelling/...`) — so no module toggle was even needed;
> config-only on our side. Drenthe = 443 stemmingen, 15 fracties, tier A. See data-sources.md §2b + roadmap Phase 8.
>
> **⏳ FLEVOLAND — still the only open outreach.** `griffie@flevoland.nl`, mailed 2026-06-11, followed up
> 2026-06-29, no reply. Same GO ask. **Given Drenthe: explicitly ask them to have GO check the `/Leden/...`
> path** — the votes may already exist there. Get any reply moving **before the zomerreces (~mid-July)**;
> after that, expect nothing until late Aug/Sept.
>
> _Reminder draft (reply on each original thread):_
> > Geachte Statengriffie,
> >
> > Op 11 juni stuurde ik onderstaand verzoek over het publiceren van het stemgedrag per fractie als
> > open data (zoals provincie Utrecht dat doet). Zou u kunnen aangeven of dit haalbaar is, of mij
> > naar de juiste collega kunnen verwijzen? Met het oog op het naderende zomerreces hoor ik het
> > graag. Bij voorbaat dank.
> >
> > Met vriendelijke groet, [naam]
> >
> > _(Drenthe: "Provinciale Staten" eventueel vervangen door "het Drents Parlement".)_

**Unlocks (if done):** Flevoland (config-only — zero extra code for us). **Drenthe already unlocked.**
**Why:** Both run GemeenteOplossingen and expose the GO `/api/v2` (structure). We assumed the
**stemgedrag** votes weren't published because `/Samenstelling/{fractie}/votings` 404'd — but **Drenthe
proved that was a path issue, not a missing module**: its votes live at `/Leden/{fractie}/votings`. So
for Flevoland, the ask is really "please have GO confirm the votings path / enable the data." Utrecht
(`/Samenstelling/...`) and now Drenthe (`/Leden/...`) are both clear precedents.

**To:** Flevoland → `griffie@flevoland.nl` · Drenthe → `Statengriffie@drentsparlement.nl`
(✔ verified 2026-06-11. NB: the obvious guesses `statengriffie@flevoland.nl` and
`statengriffie@drenthe.nl` both **bounce** — Flevoland's griffie mailbox is `griffie@…` and
Drenthe brands its PS as the *Drents Parlement*, so its griffie lives on `@drentsparlement.nl`.)
**Onderwerp:** Verzoek: stemgedrag per fractie als open data publiceren (zoals provincie Utrecht)

> Geachte Statengriffie,
>
> Provincie Utrecht publiceert via haar stateninformatiesysteem (GemeenteOplossingen) het
> **stemgedrag per fractie** als open data — per motie/amendement is zichtbaar welke fractie voor
> of tegen stemde. Bij uw provincie is de GemeenteOplossingen-API wel beschikbaar, maar de
> **'stemgedrag'-module** lijkt niet ingeschakeld, waardoor de stemmingen niet als open data
> beschikbaar zijn.
>
> Zou u de stemgedrag-module kunnen (laten) inschakelen, of de stemmingen anderszins als open
> data willen publiceren? Ik bouw een open, non-commercieel overzicht van het stemgedrag in de
> Provinciale Staten en zou uw provincie daar graag aan toevoegen.
>
> Het project is open en non-commercieel; u kunt het hier bekijken:
> – Website: https://carefulcamel61097.github.io/wie-stemde-wat/
> – Broncode: https://github.com/carefulCamel61097/wie-stemde-wat
> (Provincie Utrecht, Noord-Holland en Limburg zijn er al in opgenomen — zo ziet het resultaat eruit.)
>
> Met vriendelijke groet,
> [naam]

> **Tip:** stuur aparte mails (Flevoland → `griffie@flevoland.nl`, Drenthe →
> `Statengriffie@drentsparlement.nl` — beide geverifieerd 2026-06-11). Vul je eigen naam in bij
> `[naam]`. De live links + de drie reeds opgenomen provincies zijn het overtuigendst — ze laten
> zien dat het een echt, werkend project is. (Voor Drenthe kun je "Provinciale Staten" in de mail
> eventueel vervangen door "het Drents Parlement".)

---

## 3. Publish-as-data lobby — Groningen & Zeeland  (Noord-Brabant ✅ resolved)

> **Basis (probed live 2026-07-05/06):** these publish who voted how, but only as **unstructured PDF**,
> not machine-readable open data:
> - **Groningen** (Notubiz) — votings API empty *and* portal render has no per-fractie markup (stemgedrag
>   module off; re-probed 2026-07-06), but the **Handelingen** name both sides per fractie + totals.
> - **Zeeland** (iBabs) — Stemming/Moties/Amendementen reports all 0 rows incl. the `Stemmen` field
>   (re-probed 2026-07-06 — genuinely empty), but the **concept-besluitenlijst** PDF names the voting fracties.
>
> So the ask is the same as §2: *publish the per-fractie vote you already record as open data.* Each has a
> **precedent on its own vendor** — cite it.
>
> **✅ Noord-Brabant is resolved — no lobby needed.** The mail was sent 2026-07-05, but the griffie (Emma
> Beers) replied 2026-07-06 that the votes are *already* in the portal behind "toon stemmen". They were
> right: NB is iBabs like Limburg, and its item detail carries the structured **`Stemmen`** field
> (per-fractie member counts) — we'd mis-filed it as notulen-only. **Shipped 2026-07-06 as tier A,
> config-only (628 items).** See §3c below and provinces.md. *(A short thank-you reply is warranted — see
> the draft at the end of §3c.)*
>
> **Groningen & Zeeland:** ✅ sent 2026-07-05 to `statengriffie@provinciegroningen.nl` ·
> `statengriffier@zeeland.nl` (note the *-griffier* form). Cold contacts right before the **zomerreces
> (~mid-July)** — expect little before September; **nudge late August** if silent (Drenthe playbook: mail →
> nudge → result). NB's outcome is a useful nudge point: for Zeeland especially, "please populate the
> `Stemmen` field like Noord-Brabant and Limburg do" is now a same-vendor, same-field precedent.

### 3a. Groningen (Notubiz)
**To:** `statengriffie@provinciegroningen.nl` (✅ **sent 2026-07-05** — address correct).
**Onderwerp:** Verzoek: stemgedrag per fractie als open data publiceren (Notubiz stemgedrag-module)

> Geachte Statengriffie,
>
> Ik bouw een open, non-commercieel overzicht van het stemgedrag in de Provinciale Staten, en zou
> provincie Groningen daar graag aan toevoegen.
>
> In de **Handelingen** van uw Statenvergaderingen staat per motie/amendement keurig vermeld welke
> fracties voor en tegen stemden, met de aantallen. Diezelfde gegevens zijn via uw
> vergaderportaal (Notubiz) echter **niet als open data** beschikbaar: de stemmingen-API levert voor
> Groningen geen resultaten, terwijl dat bij andere Notubiz-provincies (Zuid-Holland, Gelderland,
> Fryslân, Overijssel) wél het geval is — daar kan ik het stemgedrag automatisch inlezen.
>
> Zou u de **stemgedrag-/stemmingenmodule** in Notubiz kunnen (laten) inschakelen, zodat de stemmingen
> die u toch al vastlegt ook als open data beschikbaar komen? Voor u is het naar verwachting een
> kwestie van publiceren; het werk van registreren doet u immers al.
>
> Het project is open en non-commercieel; u kunt het hier bekijken:
> – Website: https://carefulcamel61097.github.io/wie-stemde-wat/
> – Broncode: https://github.com/carefulCamel61097/wie-stemde-wat
> (Utrecht, Drenthe, Noord-Holland, Limburg en vier Notubiz-provincies zijn er al in opgenomen.)
>
> Met vriendelijke groet,
> [naam]

### 3b. Zeeland (iBabs)
**To:** `statengriffier@zeeland.nl` (✅ **sent 2026-07-05**. NB: it's `statengriffie**r**@zeeland.nl`
— the *-griffier* form, not `statengriffie@…` which was the wrong guess.)
**Onderwerp:** Verzoek: stemgedrag per fractie als open data publiceren (iBabs stemmingenregister)

> Geachte Statengriffie,
>
> Ik bouw een open, non-commercieel overzicht van het stemgedrag in de Provinciale Staten, en zou
> provincie Zeeland daar graag aan toevoegen.
>
> In de **concept-besluitenlijst** van uw Statenvergaderingen staat per motie/amendement/voorstel
> vermeld welke fracties voor stemden (bijvoorbeeld: *"aangenomen met de stemmen van de aanwezige leden
> van de fracties van BBB, CDA, CU, D66, PvdA-GL, PVV, SGP en VVD voor"*). Via uw vergaderportaal
> (iBabs) is dit stemgedrag echter **niet als open data** beschikbaar: de registers Moties,
> Amendementen en **Stemming** zijn leeg. Bij provincie Limburg — dat hetzelfde iBabs-systeem gebruikt —
> is het stemgedrag per fractie wél als open data ontsloten, en kan ik het automatisch inlezen.
>
> Zou u het **stemmingenregister** kunnen (laten) vullen / het stemgedrag per fractie als open data
> willen publiceren? De gegevens legt u in de besluitenlijst immers al vast; het gaat om het ook als
> data beschikbaar stellen.
>
> Het project is open en non-commercieel; u kunt het hier bekijken:
> – Website: https://carefulcamel61097.github.io/wie-stemde-wat/
> – Broncode: https://github.com/carefulCamel61097/wie-stemde-wat
> (Utrecht, Drenthe, Noord-Holland en Limburg zijn er al in opgenomen — zo ziet het resultaat eruit.)
>
> Met vriendelijke groet,
> [naam]

### 3c. Noord-Brabant (iBabs) — ✅ RESOLVED, no lobby needed

**Outcome (2026-07-06):** the lobby mail (sent 2026-07-05 to `statengriffie@brabant.nl`) got a reply from
the Statengriffie (**Emma Beers**): *"Op ons Stateninformatiesysteem zijn de hoofdelijke stemmingen
inzichtelijk … Door bij de stemuitslag te klikken op 'toon stemmen' zijn de stemmen van afzonderlijke
Statenleden in te zien."* She was right. NB is iBabs like Limburg, and the motie/amendement **item detail**
(not the report row) carries the structured **`Stemmen`** field — `vote-summary-legend-in-favour/-against`
with per-fractie member counts, exactly what the Limburg parser already reads. Our earlier "notulen-only"
verdict was a false negative: the *report row* and the `Stemverhouding` field are empty, but the `Stemmen`
field (behind "toon stemmen") is fully populated.

**Shipped 2026-07-06, config-only:** SOURCES entry (`vendor: ibabs`, `votes: stemmen`, Moties report
`376cf779-…` + Amendementen `0b5f0bd5-…`) → **628 stemmingen (534 moties + 94 amendementen), 15 fracties,
tier A** (per-member counts, incl. verworpen). One data fix: NB records the combined CU-SGP fractie as
`ChristenUnie/SGP` until 2025 and `ChristenUnie-SGP` from 2026 — merged via an alias.

**Lesson:** on iBabs, check **both** vote fields on the item detail — `Stemverhouding` (free text, NH) *and*
`Stemmen` (structured, Limburg/NB) — not just the report row. This is worth re-checking on any future iBabs
province before concluding "no structured votes".

> **Thank-you reply to Emma Beers — ✅ sent 2026-07-06** (reply on the same thread). Graceful close: confirmed
> the tip worked and that NB is now included — which also quietly reinforces the "publish as data" point for Zeeland.
>
> > Geachte mevrouw Beers,
> >
> > Hartelijk dank voor uw reactie en de tip. U heeft gelijk — via "toon stemmen" bij de stemuitslag zijn
> > de stemmen per Statenlid inderdaad in te zien, en het blijkt dat die per fractie ook als gestructureerde
> > data in het portaal beschikbaar zijn. Ik heb provincie Noord-Brabant daarmee inmiddels aan het overzicht
> > kunnen toevoegen: het stemgedrag per fractie op alle moties en amendementen van deze Statenperiode wordt
> > nu automatisch ingelezen.
> >
> > U kunt het resultaat hier bekijken: https://carefulcamel61097.github.io/wie-stemde-wat/
> >
> > Nogmaals dank voor het meedenken.
> >
> > Met vriendelijke groet,
> > [naam]

> **Note (superseded):** the old fallback plan — parse the verbatim notulen (member-name roll-call) and map
> member → fractie via NB's **Ledenlijst PS** report — is no longer needed now that the `Stemmen` field
> gives the same tier A directly. Kept for reference only.
