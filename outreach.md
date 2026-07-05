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

## 3. Publish-as-data lobby — Groningen, Zeeland, Noord-Brabant

> **Basis (probed live 2026-07-05):** these three are **not** data-absence dead ends. Each already
> **publishes** who voted how, but only as **unstructured PDF**, not machine-readable open data:
> - **Groningen** (Notubiz) — votings API empty, but the **Handelingen** name both sides per fractie + totals.
> - **Zeeland** (iBabs) — Stemming/Moties/Amendementen reports empty, but the **concept-besluitenlijst** PDF
>   names the voting fracties per item.
> - **Noord-Brabant** (iBabs) — Moties report = outcome + indieners only; the votes are in the verbatim
>   **notulen** as full **hoofdelijke stemming per lid** (confirmed 2026-07-05 — richest of the three).
>
> So the ask is the same as §2: *publish the per-fractie vote you already record as open data.* Each has a
> **precedent on its own vendor** — cite it.
>
> **✅ All three sent 2026-07-05** (drafts below), to the verified addresses:
> `statengriffie@provinciegroningen.nl` · `statengriffier@zeeland.nl` (note the *-griffier* form) ·
> `statengriffie@brabant.nl`. Cold contacts right before the **zomerreces (~mid-July)** — so expect little
> before September; **nudge late August** if silent (the Drenthe playbook: mail → nudge → result).

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

### 3c. Noord-Brabant (iBabs)
**Confirmed 2026-07-05:** NB's verbatim **notulen** record the **hoofdelijke stemming per lid** (full
member-name voor/tegen lists for contested votes; totals for near-unanimous ones) — the richest of the
three. But the structured Moties report carries only outcome + indieners, so the votes aren't open data.
**To:** `statengriffie@brabant.nl` (✅ **sent 2026-07-05** — address correct).
**Onderwerp:** Verzoek: stemgedrag per fractie als open data publiceren (iBabs stemmingenregister)

> Geachte Statengriffie,
>
> Ik bouw een open, non-commercieel overzicht van het stemgedrag in de Provinciale Staten, en zou
> provincie Noord-Brabant daar graag aan toevoegen.
>
> In uw **notulen** wordt bij hoofdelijke stemmingen precies vastgelegd welke leden voor en tegen
> stemden. Via uw vergaderportaal (iBabs) is dit stemgedrag echter **niet als open data** beschikbaar:
> het motieregister toont alleen de uitslag (aangenomen/verworpen) en de indienende fracties, niet hoe
> elke fractie stemde. Bij provincie Limburg — dat hetzelfde iBabs-systeem gebruikt — is het stemgedrag
> per fractie wél als open data ontsloten, en kan ik het automatisch inlezen.
>
> Zou u het **stemmingenregister** kunnen (laten) vullen / het stemgedrag per fractie als open data
> willen publiceren? De gegevens legt u in de notulen immers al vast; het gaat om het ook als data
> beschikbaar stellen.
>
> Het project is open en non-commercieel; u kunt het hier bekijken:
> – Website: https://carefulcamel61097.github.io/wie-stemde-wat/
> – Broncode: https://github.com/carefulCamel61097/wie-stemde-wat
> (Utrecht, Drenthe, Noord-Holland en Limburg zijn er al in opgenomen — zo ziet het resultaat eruit.)
>
> Met vriendelijke groet,
> [naam]

> **Note (for us, not the mail):** if the lobby stalls, NB is the most parseable of the three — the
> notulen name every member, and NB's **Ledenlijst PS** report maps member → fractie, so a fragile
> parser could yield **tier A** (per-member counts). PDF URL pattern: iBabs global search
> `/Search?q=notulen` → `api1.ibabs.eu/publicdownload.aspx?site=NoordBrabant&id={guid}`.
