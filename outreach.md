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

## 3. (optional) Notubiz provinces with stemgedrag module off
Gelderland publicly shows only aangenomen/verworpen status (stemgedrag module off). The same
griffie ask as #2 could apply — but the Notubiz **token** (#1) is the more general unlock.
