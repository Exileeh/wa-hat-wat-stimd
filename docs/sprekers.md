# Sprekers en transcripten per vergadering

**Status: gebouwd op 19 september 2026** (`collector/sprekers.py`, de blokken in `meeting.js`).
Dit document beschrijft de bron, het datamodel en de keuzes die eraan ten grondslag liggen. Alle
cijfers komen uit de eerste volledige run over de hele termijn.

De site laat nu zien *hoe* fracties stemden, maar niets over het debat dat eraan voorafging. Twee
wensen:

1. Een vergadering openen en zien **welke fractie het meest aan het woord was**.
2. Op een woord zoeken en **alle treffers krijgen met het tijdstip in de video**, zodat je het zelf
   kunt opzoeken.

Wens 2 koppelt een treffer bewust *niet* aan een motie — zie §6.

## 1. Wat de bron biedt

Alles staat in de portaalpagina die `collect.py` al ophaalt, plus één extra bestand per vergadering.

| Doel | Vindplaats | Opmerkingen |
|---|---|---|
| Sprekersindex | `https://fryslan.notubiz.nl/vergadering/<mid>`, per agendapunt een `<ul class="speakers_indexations">` | Per spreekmoment een `<li class="speaker_index" id="si_<n>" data-si_id data-speaker_id data-start_offset data-end_offset>`, met in de knoptekst `spreker: Naam (fractie of rol)`. Door de griffie onderhouden, niet door spraakherkenning geraden. **Kost nul extra requests**: deze HTML wordt al opgehaald voor `notubiz_parse_meeting()`. |
| Transcript | Dezelfde HTML, JW Player-config: `subtitles_file: "https://fryslan.notubiz.nl/media/subtitles/<naam>.srt"` | Geldige UTF-8 zonder BOM. Automatische spraakherkenning. De bestandsnaam is **niet** af te leiden uit het vergader-id en moet uit de HTML komen. Eén extra GET per vergadering. |
| Video-deeplink | `https://fryslan.notubiz.nl/vergadering/<mid>#si_<n>` | Opent de vergadering, markeert dat spreekmoment en spoelt de speler ernaartoe. Zie §2. |
| Sprekerslijst | Dezelfde HTML, `<div id="speakers">` | Naam, fractie en pasfoto-URL per spreker. Niet strikt nodig: naam en fractie staan ook in de index zelf. |

De `.srt` gaat via de gewone `http()` uit `collect.py` en dus automatisch door de relay uit
[notubiz.md §4](notubiz.md). Met circa 650 KB blijft zo'n bestand ruim onder de 4,5 MB waarboven de
relay in stukken moet antwoorden.

**Dekking.** Alle 45 vergaderingen sinds 29 maart 2023 hebben een sprekersindex én een
ondertitelbestand, van 4 spreekmomenten (een korte installatievergadering) tot 799. Geen enkel gat
groter dan 5 s tussen opeenvolgende spreekmomenten: de index dekt de hele vergadering. Achter de
naam staat tussen haakjes de fractie of de rol — `(BBB)`, `(gedeputeerde)`, `(voorzitter)`,
`(commissaris van de Koning)`.

Een `.srt` telt 500 tot 9 600 cues. Een cue-tijdstip valt in precies één spreekmoment, dus de
koppeling is een simpele intervalzoekactie; per vergadering landt **98 tot 100 %** van de cues
binnen een spreekmoment.

## 2. De deeplink naar de video

Het portaal spoelt de speler op basis van de URL-hash:

```js
$(window).hashchange(function() {
    $(location.hash).addClass('highlight');
    if ($(location.hash).data('start_offset') != undefined) {
        media_seek($(location.hash).data('start_offset'));
    }
});
$(window).hashchange();          // direct aangeroepen, dus werkt ook bij het laden van de pagina
```

Elk `<li id="si_<n>">` draagt een `data-start_offset`, dus `…/vergadering/1394293#si_32544285`
springt naar dat spreekmoment.

Dit is de **fijnste granulariteit die er is**. Naar een willekeurige seconde linken kan niet: de
handler leest de offset van een bestaand element, er is geen tijdparameter. Een spreekmoment kan
enkele minuten duren.

Gevolg voor de site: toon het exacte tijdstip van de cue als tekst, en laat de link naar het begin
van het spreekmoment springen. Benoem dat verschil, anders lijkt de link kapot.

## 3. Datamodel

Twee nieuwe bestanden naast `fryslan.json` en `roles.json`.

**`data/sprekers.json`** — alle vergaderingen in één bestand, 23 KB voor alle 45. Klein genoeg om
altijd mee te laden.

```jsonc
{
  "generated_at": "…",
  "meetings": {
    "1488191": {
      "indexed": 26609,                                  // seconden die de index beslaat
      "fracties": { "bbb": 2940, "pvdd": 2520, … },      // seconden per fractie-slug
      "rollen":   { "gedeputeerde": 5220, "voorzitter": 2760, … },
      "momenten": 602
    }
  }
}
```

Fracties en rollen staan **strikt gescheiden**. De gedeputeerde is met 19 tot 23 % de grootste
enkele spreker en zou een vergelijking tussen fracties anders platslaan. Gemeten verdeling voor
06-05-2026: gedeputeerde 19 %, BBB 11 %, voorzitter 10 %, PvdD 9 %, GrienLinks 8 %.

**`data/transcript/<meetingId>.json`** — per vergadering, lui geladen. 14 MB voor alle 45 samen,
dus gemiddeld ruim 300 KB; de grootste vergadering komt op 479 KB. GitHub Pages serveert ze
gzipped, wat daar grofweg een derde van maakt.

```jsonc
{
  "meetingId": 1488191,
  "srt":    "https://fryslan.notubiz.nl/media/subtitles/…srt",   // bron, voor verificatie
  "source": "https://fryslan.notubiz.nl/vergadering/1488191",    // basis voor de deeplink
  "speakers": { "238949": {"n": "Keuning, C. (Cor)", "p": "bbb"} },
  "index":  [[675, 813, "238949", 32544312], …],   // start, eind, speaker_id, si_id
  "cues":   [[675, "…en dat is kalk inzetten."], …]
}
```

Een cue draagt alleen tijd en tekst. Spreker en `si_id` leidt de browser af met een binaire
zoekactie op `index`, zodat die velden niet 7 500 keer herhaald worden.

Slugs lopen via het bestaande `party_slug()` en `NOTUBIZ_ALIASES`, zodat "Partij voor de Dieren"
ook hier `pvdd` wordt en de kolommen overeenkomen met `fryslan.json`.

**Namen wél opslaan.** Dat wijkt af van `roles.json`, waar namen bewust ontbreken — daar zijn ze
*afgeleid* uit stempatronen en dus onze eigen gok. Sprekersnamen liggen anders: de griffie
publiceert ze zelf, bij naam, op het portaal. Ze opslaan voegt niets toe wat er niet al openbaar
staat, en zonder naam is een citaat onbruikbaar.

## 4. De collector

**`collector/sprekers.py`.** Een eigen module, net als `uitslag_pdf.py`, zodat `collect.py` niet
verder groeit. Stdlib-only, geen nieuwe dependencies:

* `parse_indexations(html)` → `[(start, end, speaker_id, si_id, naam, fractie_of_rol)]`
* `subtitle_url(html)` → de `.srt`-URL of `None`
* `parse_srt(text)` → `[(start, tekst)]`
* `aggregate(index)` → seconden per fractie en per rol, via `party_slug()`

**In `collect.py`:** `collect_sprekers()` draait per vergadering. De portaalpagina wordt nu voor
**elke** vergadering opgehaald — voorheen alleen als er digitale stemmingen waren — zodat ook de
vergaderingen die alleen een Útslach-PDF hebben hun sprekers krijgen. Die ene fetch voedt zowel
`notubiz_parse_meeting()` als `parse_indexations()`; alleen de `.srt` is een extra download.
`meta.counts.transcripts` telt de weggeschreven transcripten.

**Regressiebescherming.** Transcripten zijn aanvullend en mogen een run nooit rood maken. Een
ontbrekende of onbereikbare `.srt` slaat die vergadering over en laat een bestaand bestand staan.
De `lost_data()`-logica blijft alleen over `moties` gaan.

**Staging.** `refresh-local.ps1` en de commit-stap in `.github/workflows/refresh.yml` stageren
expliciet één voor één; `data/sprekers.json` en `data/transcript` staan er nu bij. Vergeet dat niet
als er ooit een databestand bij komt, anders wordt het stil nooit gecommit.

## 5. De frontend

Vanilla, geen build-stap, geen dependencies — string-templates met `esc()`, zoals de rest.

Alles zit in `meeting.js`, als twee blokken in `render()`. Beide verdwijnen vanzelf als hun data
ontbreekt, dus een vergadering zonder index of transcript rendert precies zoals voorheen.

* Bij `open(mid)` het transcript lui en faalveilig ophalen. Ontbreekt het bestand, dan rendert de
  vergadering precies zoals nu, met een korte melding in plaats van de nieuwe blokken.
* Blok **"Wie was aan het woord"**: horizontale balken per fractie, in dezelfde met de hand
  geschreven SVG-stijl als `chartIndieners()` in `app.js`. Daaronder, apart en kleiner, de rollen.
* Blok **"Zoek in het debat"**: invoerveld, gedempt op 150 ms zoals het bestaande zoekveld. Toont
  **alle** treffers, chronologisch. Per treffer het tijdstip als `u:mm:ss`, naam en fractiechip van
  de spreker, de cue-tekst met de zoekterm gemarkeerd, en de deeplink uit §2. Aantal treffers
  erboven, en een "toon meer"-knop zodat een heel algemene term de pagina niet vult.
* **Diacriticvouwing.** Het zoekveld in `app.js` doet een kale `includes()` zonder vouwing; voor
  Friese tekst met `â û ô` is dat te beperkt. `fold()` in `meeting.js` mapt per teken, dus de
  lengte blijft gelijk en een positie in de gevouwen tekst wijst ook de originele tekst aan. Dat is
  wat de markering laat werken: zoeken op `buten` markeert `bûten`. NFD zou elke positie
  verschuiven.

**Eerlijk labelen.** De transcripten zijn automatische spraakherkenning van wisselende kwaliteit:
namen worden verhaspeld, Fries en Nederlands lopen door elkaar. Het portaal zegt zelf dat de
ondertiteling "noch net alle wurden" herkent. Dat staat als ondertitel boven het zoekblok, met een
link naar de bron-`.srt` en naar de video, zodat elke treffer na te trekken is — en met de
vermelding dat de deeplink naar het begin van het spreekmoment springt, niet naar de seconde zelf.

## 6. Bewust buiten scope: een treffer aan een motie koppelen

Onderzocht en bewust niet gedaan. Hier vastgelegd zodat niemand het opnieuw probeert.

* **Agendapunt-offsets zijn te grof.** Bij 06-05-2026 hangen 35 stemmingen aan één agendapunt
  (`10204740`) dat van 2 004 s tot 25 200 s loopt, ruim zes uur.
* **Per-motie offsets bestaan, maar zijn nep.** Elke motie is een eigen sub-agendapunt, en het id
  daarvan is gelijk aan het stemming-id — dat is bruikbaar. De offsets zijn alleen
  volgnummer-plaatshouders van precies één seconde: `1971-1972`, `1972-1973`, enzovoort.
* **Motienummers worden niet als cijfer uitgesproken.** Sprekers zeggen "drieendertig", niet "33".
  Zoeken op `moasje \d+` geeft nul treffers in een heel transcript.

Titel-tokenoverlap werkte in een prototype redelijk — 25 van de 34 moties kregen minstens één
treffer bij twee gedeelde onderscheidende woorden, en moties blijken bij de stemronde hardop
voorgelezen te worden ("en dat is kalk inzetten", "Ja grip op borging"). Maar dat levert een
waarschijnlijkheid op, geen feit, en dat is niet wat deze feature moet beloven. De treffer met het
tijdstip is genoeg: de lezer kijkt zelf.

## 7. Openstaande punten

* **Dekking is volledig.** Alle 45 vergaderingen sinds 29 maart 2023 hebben zowel een
  sprekersindex als een ondertitelbestand — ook de vergaderingen waarvan de stemmingen alleen in de
  Útslach-PDF staan. Per vergadering valt 98 tot 100 % van de cues binnen een spreekmoment.
* **Gebruiksvoorwaarden.** Het bulk-downloaden en herpubliceren van ondertitelbestanden van Notubiz
  is niet getoetst. Dit hoort langs iemand die daarover kan beslissen voordat de transcripten
  publiek in de repo staan.
* **Repo-omvang** groeit met 14 MB aan transcripten. Bij elke run worden ze opnieuw geschreven;
  alleen gewijzigde bestanden leveren een nieuwe blob op, dus dat blijft in de praktijk beperkt.
* **Geen CORS op het portaal.** `fryslan.notubiz.nl` stuurt geen `Access-Control-Allow-Origin`,
  gecontroleerd op zowel de vergaderpagina als de `.srt`. De browser kan transcripten dus niet zelf
  ophalen; ze moeten uit de repo komen. Het live bijladen uit `app.js` (`liveTopUp`) werkt hier
  niet: een nieuwe vergadering krijgt pas een transcript bij de volgende collector-run.

## 8. Bouw en verificatie

Gebouwd in drie stappen: dit document, daarna `sprekers.py` met `data/sprekers.json` en het blok
"Wie was aan het woord", ten slotte de transcripten en het zoekblok.

**Tests** (`collector/test_sprekers.py`, stdlib `unittest`, netwerkvrij, in de stijl van
`test_collect.py`): een HTML-fragment met twee `speaker_index`-items geeft de juiste tuples en
splitst fractie van rol; `subtitle_url()` vindt de URL en geeft `None` als er geen ondertitel is;
een `.srt`-fragment met een cue van twee regels wordt goed gelezen; een cue precies op een grens en
een cue in een gat geven het verwachte resultaat; `aggregate()` telt "Partij voor de Dieren" op bij
`pvdd` en laat een rol niet tussen de fracties belanden.

**Verificatie**, op een verbinding die de bron bereikt:

```
python -m unittest discover -s collector
python collector/collect.py
```

De run van 19 september 2026 gaf 913 stemmingen (ongewijzigd) en 45 vergaderingen met een index,
alle 45 met transcript. Daarna in de browser, op `#vergadering/1488191`:

* De balkgrafiek geeft gedeputeerde 19 %, BBB 11 %, voorzitter 10 %, PvdD 9 %.
* Zoeken op `kalk` geeft 11 treffers; de eerste staat op 5:06:23 bij Oenema (JA21) en linkt naar
  `…/vergadering/1488191#si_33033664`.
* Zoeken op `buten` zónder dakje vindt `bûten` en markeert het woord mét dakje — de test van de
  lengtebehoudende `fold()`.
* Zoeken op `stikstof` geeft 231 treffers, waarvan 50 getoond met een "toon meer"-knop.
* Eén letter geeft "typ minstens twee letters", een onzinwoord geeft netjes geen treffers.
