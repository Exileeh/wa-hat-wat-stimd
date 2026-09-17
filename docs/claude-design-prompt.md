# Prompt voor Claude Design — herontwerp "Wa hat wat stimd?"

> Plak de tekst hieronder in Claude Design en voeg `index.html`, `app.css` en (ter referentie)
> `app.js` uit deze repo toe. Het resultaat (HTML + CSS) wordt daarna weer in deze repo gezet;
> `app.js` blijft ongewijzigd en verwacht de hieronder genoemde element-id's en klassen.

---

## Wat het is

**Wa hat wat stimd?** is een statische, open-data website die per stemming in de **Provinciale
Staten van Fryslân** laat zien hoe elke fractie stemde. Eén tabel: rijen = stemmingen (moasjes,
amendeminten, besluiten), kolommen = 15 fracties, cellen = **V** (voor, groen), **T** (tegen,
rood), **O** (onthouden/staken, grijs) of leeg (afwezig). Publiek: geïnteresseerde burgers,
journalisten, Statenleden en griffiemedewerkers. Toon: neutraal, betrouwbaar, journalistiek — een
naslagwerk, geen campagnesite. Nederlands als interfacetaal; de titels van stemmingen zijn Frysk.

Ontwerp een nieuwe visuele laag (HTML + CSS) voor deze pagina. **Alle functionaliteit blijft**;
het JavaScript (`app.js`) is af en hangt aan vaste id's/klassen. Wat je vrij mag herontwerpen:
typografie, kleurgebruik, spacing, componentvormgeving, koppen, iconen, lege staten, responsive
gedrag. Wat vast ligt: de structuur van id's en klassen hieronder, de teksten (mogen wel anders
gezet worden) en dat het een enkele pagina blijft zonder frameworks.

## Sfeer en huisstijl

- Fryslân: accentkleur **pompeblêd-rood `#c8102e`**, donkere header `#2a0a0c`. Mag rustiger
  ingezet worden dan nu (nu is de header een vol donker vlak).
- Stemkleuren zijn semantisch en moeten herkenbaar blijven: voor = groen, tegen = rood, neutraal =
  grijs, afwezig = zeer licht/leeg. Huidige waarden: `--voor:#8fd3a6`, `--tegen:#f59a9a`,
  `--neutraal:#d7d4cd`, `--afw:#eceae5`; grafiekseries `--c-aangenomen:#3f9d5f`,
  `--c-verworpen:#c8102e`, `--c-staken:#8a8794`. Kleur nooit als enige drager: labels blijven.
- Referenties in geest: NOS/NRC datavisualisatie, Open State Foundation, overheidsstijl (Rijkshuisstijl)
  maar niet officieel — het is geen uitgave van de provincie.
- Lettertype: systeemfonts of één webfont (Google Fonts toegestaan). Tabel moet compact en scanbaar
  blijven (13–14 px in de tabel is normaal).

## Anatomie van de pagina (volgorde behouden)

1. **Header** `header.top`: titel `h1` "Wa hat wat stimd<span class="q">?</span>" (het vraagteken in
   accentkleur), lead `#appLead`, bronregel `#src` (JS vult: "Bron: … · open data · periode 2023-2027
   · bijgewerkt 2026-09-17"), twee meldingen die meestal verborgen zijn: `#staleNote.staleNote`
   (waarschuwing: data verouderd) en `#liveNote.liveNote` (succes: "N stemmingen live opgehaald…").
   Knop `#helpBtn.helpbtn` "ⓘ Uitleg".
2. **Filterbalk** `.controls` (sticky bovenaan): rij 1 met `label.field` velden — zoekveld
   `input#search`, partijkiezer `details.parties` met `summary#psummary` en paneel `.ppanel`
   (`#pAll`, `#pNone`, `#pList` met checkboxes), selects `#result` en `#sort`. Rij 2
   `.controls-row-2`: toggles `#controversial`, `#onlyPinned`, `#raw` (met `.help-q` tooltips) en
   `.actions` met vier primaire knoppen `.bigbtn`: `#statsBtn` Statistieken, `#matrixBtn`
   Overeenkomst, `#profileBtn` Partijprofiel, `#compareBtn` Vergelijken.
3. **Tabel-toolbar** `.tbl-toolbar`: titel "Stemmingen", type-chips `#typeChips` (`.chip`, actief
   `.chip.on`), rechts `#count` ("836 van 836 stemmingen · 15 partijen"), `#csvBtn.csvbtn`,
   `#legendBtn.iconbtn`.
4. **Tabellen** in `.wrap`: `#pinnedBlock` (optioneel, kop `.tbl-title` "📌 Vastgepind") en
   `#mainBlock`. JS rendert `.table-scroll > table` met sticky `thead` en sticky eerste kolom.
   Eerste cel `td.onderwerp` bevat `.ond-row`: pin-knop `button.pin` (`.on` als vastgepind),
   `.titel` (titel + `a.ext` ↗ naar de vergadering + evt. `.badge-live`), en `.meta` met datum,
   type-pil `.type.t-motie|.t-amendement|.t-besluit`, uitslag `.res.r-accepted|.r-rejected|.r-tie`,
   documentlink `a.doclink` ("📄 Moasje" / "📄 Amendemint") en indieners `.indieners`.
   Stemcellen: `td.cell.voor|.tegen|.neutraal|.afw`, modifier `.split` (stip: fractie niet unaniem)
   en `.raw` (toont "14-0" i.p.v. V). Lege staat: `.empty`.
5. **Footer** `.foot`: bron/broncode.
6. **Modals** `.modal > .modal-card` (`.wide` voor statistieken), kop `.modal-head h2`, sluitknop
   `.modal-close[data-close]`, intro `.modal-sub`, filterrij `.modal-controls` met chips
   (`#statsTypes`, `#matrixTypes`, `#profileTypes`, `#compareTypes`) en selects (`#profileParty`,
   `#cmpA`, `#cmpB`). Inhoud die JS vult:
   - `#statsModal`: KPI-tegels `#statsKpis.stat-grid > .stat` (`.stat.primary`, `.num`, `.lab`),
     daarna `.charts` (2×2 grid, op mobiel 1 kolom) met vier `section.chart` (h3, `.chart-sub`,
     container `#chartMonths`, `#chartIndieners`, `#chartWinning`, `#chartMargins`). Grafieken zijn
     inline SVG met klassen `rect.bar`, `.grid`, `.axis`, `text.lbl`, `text.val`, legenda
     `.legend-row .sw`, lijst `.krap-list`.
   - `#matrixModal`: `#matrixBody` met `table.matrix` (`th.rowh`, `td.diag`, `td.na`, `td.lown`,
     celkleur inline via hsl) en `.matrix-legend .bar`.
   - `#profileModal`: `#profileBody` met `.stat-grid` en `.scrollbox > table.list`, badges `.vbadge.voor|.tegen|.neutraal`.
   - `#compareModal`: `#compareBody` met `.cmp-summary` en `table.list`.
   - `#helpModal` (`.help`, `h3.section`, `ul.legenda`, `.help-list`, `.swatch.afw`, `.splitdot`)
     en `#legendModal`.

## Teksten (behouden, zetwerk vrij)

Alle zichtbare copy staat in `index.html`; Nederlands, met Fryske termen "moasje" en
"amendemint" waar het over het document gaat. Voorbeelden: "Zoek op onderwerp of indiener…",
"Alleen omstreden", "Ruwe getallen", "Alle partijen", "Aangenomen"/"Verworpen", "Tel mee:",
"aan de winnende kant", "De 5 krapste stemmingen". Datums als `2026-05-06` mogen als
"6 mei 2026" gezet worden via CSS niet — dus laat ze staan.

## Eisen

- **Geen frameworks, geen build**: één `index.html` + één `app.css`, vanilla. Externe fonts alleen
  via Google Fonts. Emoji-iconen mogen vervangen worden door inline SVG-iconen.
- **Responsive** tot 400 px: filterbalk wrapt/stapelt, tabel scrollt horizontaal binnen
  `.table-scroll` met sticky eerste kolom, modals passen in het scherm, charts-grid wordt 1 kolom.
- **Toegankelijk**: contrast ≥ 4.5:1 voor tekst, zichtbare focusstijl (`:focus-visible`), de V/T/O
  letters blijven in de cellen staan (kleur is niet de enige informatiedrager), `title`-tooltips
  blijven werken.
- **Dichtheid**: 836 rijen × 15 kolommen; rijen ≈ 40–48 px, cellen 42 px breed, eerste kolom
  300–440 px op desktop, 170–220 px op mobiel.
- `[hidden]` moet echt verbergen (modals, meldingen). `#home` bestaat niet meer; er is één view.
- Lever op: nieuwe `index.html` (zelfde id's/klassen, `<script src="app.js">` onderaan) en `app.css`.
  Kort toelichten welke klassen nieuw zijn zodat `app.js` er eventueel op aangesloten kan worden.
