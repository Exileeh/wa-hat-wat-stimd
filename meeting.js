/* Wa hat wat stimd? — de pagina van één plenaire vergadering (#vergadering/<id>).

   Deliberately a file of its own: the table and the analyses in app.js do not know about it, and it
   only borrows their helpers (DATA, esc, pName/pLabel, cellVerdict, rowHTML, headHTML, tableOrder,
   svgOpen, the chart functions, formatDateNL, meetingOf, agendaIdOf, agendaLabel). Room to grow:
   notulen, toezeggingen — add a block to render() below and nothing else in the site has to change.

   Sprekers (data/sprekers.json) and the doorzoekbaar transcript (data/transcript/<id>.json) work
   that way: both are fetched lazily and every block degrades to nothing when they are absent, so a
   vergadering without them renders exactly as it did before. See docs/sprekers.md.

   app.js calls MeetingPage.open(mid) from route() and MeetingPage.refresh() after live bijladen. */
const MeetingPage = (() => {
  const el = () => document.getElementById("meetingBody");
  let current = null;          // the meeting id being shown, null when the view is closed
  let picked = null;           // agendapunt ids that count; null = all of them
  let wired = false;

  /* ---- sprekers en transcript (docs/sprekers.md) ----
     Two extra sources, both optional: the page must render exactly as before when they are
     missing. `SPREKERS` (±12 KB, every meeting) is fetched once; the transcript (±300-600 KB) only
     for the vergadering on screen. */
  let SPREKERS = null;         // data/sprekers.json, or false once it turned out not to be there
  let TR = null;               // the transcript on screen
  let trFor = null;            // which meeting TR belongs to, so a stale fetch cannot overwrite it
  let trFailed = false;        // the transcript was announced but could not be fetched
  let q = "";                  // the debate search box
  let limit = 50;              // hits rendered before "toon meer"
  let timer = null;

  // Length-preserving fold, so an index into the folded text also indexes the original. Enough for
  // Frisian and Dutch; NFD would shift every position and break the highlighting.
  const FOLD = {"à":"a","á":"a","â":"a","ä":"a","ã":"a","å":"a","æ":"a","è":"e","é":"e","ê":"e",
                "ë":"e","ì":"i","í":"i","î":"i","ï":"i","ò":"o","ó":"o","ô":"o","ö":"o","õ":"o",
                "ù":"u","ú":"u","û":"u","ü":"u","ý":"y","ÿ":"y","ñ":"n","ç":"c","ø":"o","š":"s"};
  const fold = s => s.toLowerCase().replace(/[^\x00-\x7f]/g, c => FOLD[c] || c);

  const hms = t => `${Math.floor(t/3600)}:${String(Math.floor(t/60)%60).padStart(2,"0")}:${String(t%60).padStart(2,"0")}`;
  const mmss = s => `${Math.floor(s/60)} min`;

  // Rollen are stored lower-case (sprekers.py); only the titles with a proper noun need a map.
  const ROLE_LABEL = {"commissaris van de koning": "Commissaris van de Koning"};
  const roleLabel = r => ROLE_LABEL[r] || (r ? r.charAt(0).toUpperCase() + r.slice(1) : r);

  function loadSprekers(){
    if(SPREKERS !== null) return;
    SPREKERS = false;                                   // don't ask twice while it is in flight
    fetch("data/sprekers.json").then(r => r.ok ? r.json() : null).then(j => {
      if(j && j.meetings){ SPREKERS = j; render(); }
    }).catch(() => {});
  }

  function loadTranscript(mid){
    if(trFor === mid) return;
    trFor = mid; TR = null; trFailed = false;
    const done = ok => { if(trFor === mid && !ok){ trFailed = true; render(); } };
    fetch(`data/transcript/${mid}.json`).then(r => r.ok ? r.json() : null).then(j => {
      if(trFor !== mid) return;                         // another vergadering was opened meanwhile
      if(j && j.cues){
        j.folded = j.cues.map(c => fold(c[1]));         // search once, not on every keystroke
        TR = j;
        render();
      } else done(false);
    }).catch(() => done(false));
  }

  // The spreekmoment a cue falls in: the last one that started at or before it.
  function momentAt(t){
    const ix = TR.index;
    let lo = 0, hi = ix.length - 1, best = null;
    while(lo <= hi){
      const mid = (lo + hi) >> 1;
      if(ix[mid][0] <= t){ best = ix[mid]; lo = mid + 1; } else hi = mid - 1;
    }
    return best && t <= best[1] ? best : null;
  }

  // Escape first, then wrap the matches — `fold` keeps positions, so the raw string can be sliced.
  function mark(raw, needle){
    if(!needle) return esc(raw);
    const hay = fold(raw);
    let out = "", i = 0, k;
    while((k = hay.indexOf(needle, i)) !== -1){
      out += esc(raw.slice(i, k)) + `<mark>${esc(raw.slice(k, k + needle.length))}</mark>`;
      i = k + needle.length;
    }
    return out + esc(raw.slice(i));
  }

  // Pin buttons and the agendapunt filter, both by delegation: the page is rebuilt on every change.
  function wire(){
    if(wired) return;
    wired = true;
    const view = document.getElementById("meetingView");
    if(!view) return;
    view.addEventListener("click", e => {
      const b = e.target.closest("button.pin");
      if(b){ togglePin(+b.dataset.id); return; }
      const chip = e.target.closest(".ag-filter .chip");
      if(chip){ toggleAgenda(chip.dataset.ag === "" ? 0 : +chip.dataset.ag); return; }
      const all = e.target.closest(".ag-filter [data-ag-all]");
      if(all){ picked = null; render(); return; }
      const more = e.target.closest("[data-tr-more]");
      if(more){ limit += 100; renderHits(); }
    });
    // Only the hit list is redrawn while typing, so the caret stays where it is.
    view.addEventListener("input", e => {
      if(e.target.id !== "trQ") return;
      q = e.target.value;
      limit = 50;
      clearTimeout(timer);
      timer = setTimeout(renderHits, 150);
    });
  }

  function open(mid){
    wire();
    const next = Number.isFinite(mid) && mid > 0 ? mid : null;
    if(next !== current){
      picked = null;                      // another vergadering starts with every agendapunt on
      q = ""; limit = 50;
    }
    current = next;
    if(current !== null){ loadSprekers(); loadTranscript(current); }
    render();
  }

  // Never leave the page empty: switching the last agendapunt off turns the filter back to all.
  function toggleAgenda(aid){
    const all = agendas(meetingRows(current)).map(a => a.aid);
    const set = new Set(picked === null ? all : picked);
    set.has(aid) ? set.delete(aid) : set.add(aid);
    picked = set.size === 0 || set.size === all.length ? null : [...set];
    render();
  }
  const keepAgenda = m => picked === null || picked.includes(agendaIdOf(m));

  function refresh(){
    if(current !== null && !document.getElementById("meetingView").hidden) render();
  }

  function render(){
    const box = el();
    if(!box) return;
    const all = current === null ? [] : meetingRows(current);
    if(!all.length){
      document.title = "Vergadering — Wa hat wat stimd?";
      box.innerHTML = `<div class="empty">Geen stemmingen bekend voor deze vergadering.</div>`;
      return;
    }
    // `all` sets the header and the filter, `rows` (the chosen agendapunten) everything below it.
    const rows = all.filter(keepAgenda);
    const date = all.map(m => m.date).sort()[0];
    document.title = `Vergadering ${formatDateNL(date, false)} — Wa hat wat stimd?`;
    box.innerHTML = headerHTML(all, date) + agendaFilterHTML(all) + kpiHTML(rows)
      + sprekersHTML() + zoekHTML() + chartsHTML(rows) + agendaTablesHTML(rows);
  }

  /* ---- blokken ---- */

  function headerHTML(rows, date){
    const src = rows[0].source;
    const pdf = (rows.find(m => m.uitslag) || {}).uitslag;
    return `<div class="meet-head">
      <div>
        <h2>${esc(formatDateNL(date))}</h2>
        <p class="modal-sub">Plenaire vergadering van de ${esc(DATA.meta.body)} van ${esc(DATA.meta.province)} &middot; alle hoofdelijke stemmingen van deze dag.</p>
      </div>
      <p class="meet-links">
        ${src ? `<a class="doclink" href="${esc(src)}" target="_blank" rel="noopener" title="De vergadering op het Statenportaal">${ICO("i-doc")}Statenportaal</a>` : ""}
        ${pdf ? `<a class="doclink" href="${esc(pdf)}" target="_blank" rel="noopener" title="De PDF met de uitslagen van het stemdisplay">${ICO("i-doc")}Útslach stimming (pdf)</a>` : ""}
      </p>
    </div>`;
  }

  function kpiHTML(rows){
    const acc = rows.filter(m => m.result === "accepted").length;
    const byType = {};
    for(const m of rows) byType[m.type] = (byType[m.type] || 0) + 1;
    const points = new Set(rows.map(agendaIdOf)).size;
    const tiles = sortTypes(Object.keys(byType))
      .map(t => `<div class="stat"><div class="num">${byType[t]}</div><div class="lab">${esc(TYPE_PLURAL[t] || t)}</div></div>`).join("");
    return `<div class="stat-grid">
      <div class="stat primary"><div class="num">${rows.length}</div><div class="lab">stemmingen</div></div>
      <div class="stat"><div class="num">${Math.round(100*acc/rows.length)}%</div><div class="lab">aangenomen</div></div>
      ${tiles}
      <div class="stat"><div class="num">${points}</div><div class="lab">agendapunt${points===1?"":"en"}</div></div>
    </div>`;
  }

  // Agendapunten of this meeting, in the order of their number ("2a" after "2"), without one last.
  function agendas(rows){
    const by = new Map();
    for(const m of rows){
      const aid = agendaIdOf(m);
      let a = by.get(aid);
      if(!a) by.set(aid, a = {aid, nr: m.agenda ? m.agenda.nr : "", label: agendaLabel(m), rows: []});
      a.rows.push(m);
    }
    const list = [...by.values()].sort((a,b) =>
      (a.aid === 0) - (b.aid === 0) || collator.compare(a.nr, b.nr) || collator.compare(a.label, b.label));
    for(const a of list) a.rows.sort((x,y) => collator.compare(x.title, y.title));
    return list;
  }

  /* The agendapunten as filter chips: the cijfers, de grafieken and the tabellen below follow the
     selection. Every point is on until one is switched off. */
  function agendaFilterHTML(rows){
    const list = agendas(rows);
    if(list.length < 2) return "";
    const chips = list.map(a => {
      const on = picked === null || picked.includes(a.aid);
      return `<span class="chip${on ? " on" : ""}" data-ag="${a.aid}" role="button" tabindex="0" title="${esc(a.label)}">${esc(a.label)} <span class="chip-n">${a.rows.length}</span></span>`;
    }).join("");
    return `<div class="modal-controls ag-filter">
      <span class="mc-label">Agendapunt:</span><span class="chips">${chips}</span>
      ${picked === null ? "" : `<button class="csvbtn" data-ag-all>Alle agendapunten</button>`}
    </div>`;
  }

  /* Wie was aan het woord — twee ringen naast elkaar.

     Both are part-to-whole at a glance, so each is capped at six segments: more than that and
     adjacent slices stop being tellable apart. The left ring splits the meeting over the fracties
     as a whole and the people with a role (the gedeputeerde alone takes about a fifth, so mixing
     them into one ranking would flatten every fractie); the right ring divides the fracties' own
     share, largest five by name and the rest as one slice.

     Colour is a sequential ramp, not one hue per fractie: the slices are ordered by size and the
     legend names every one of them, so the colour carries magnitude and the text carries identity.
     Fifteen fracties would need fifteen hues nobody can tell apart, and a hue per rank would
     repaint a fractie every time you opened another vergadering. The ramp is defined per theme in
     app.css (--pie-1 … --pie-6, --pie-rest). */
  const PIE_SLOTS = 6;

  // One donut segment. Angles run clockwise from twelve o'clock.
  function arcPath(cx, cy, rIn, rOut, a0, a1){
    const pt = (r, a) => [(cx + r*Math.sin(a)).toFixed(2), (cy - r*Math.cos(a)).toFixed(2)];
    const big = (a1 - a0) > Math.PI ? 1 : 0;
    const [x0,y0] = pt(rOut,a0), [x1,y1] = pt(rOut,a1), [x2,y2] = pt(rIn,a1), [x3,y3] = pt(rIn,a0);
    return `M${x0} ${y0}A${rOut} ${rOut} 0 ${big} 1 ${x1} ${y1}L${x2} ${y2}A${rIn} ${rIn} 0 ${big} 0 ${x3} ${y3}Z`;
  }

  /* `slices` = [{label, title, secs, fill}], biggest first. `centre` is the two lines in the hole. */
  function donutHTML(slices, total, centre){
    const S = 132, cx = S/2, cy = S/2, rOut = S/2 - 2, rIn = rOut*0.58;
    let a = 0, arcs = "";
    // A lone slice has no wedge to draw: a ring is two half arcs, or the path degenerates.
    if(slices.length === 1){
      arcs = `<path d="${arcPath(cx,cy,rIn,rOut,0,Math.PI)}${arcPath(cx,cy,rIn,rOut,Math.PI,2*Math.PI)}" fill="${slices[0].fill}"><title>${esc(slices[0].title)}</title></path>`;
    } else {
      for(const sl of slices){
        const a1 = a + (sl.secs/total)*2*Math.PI;
        arcs += `<path class="pie-seg" d="${arcPath(cx,cy,rIn,rOut,a,Math.min(a1,2*Math.PI))}" fill="${sl.fill}"><title>${esc(sl.title)}</title></path>`;
        a = a1;
      }
    }
    const legend = slices.map(sl =>
      `<li><span class="sw" style="background:${sl.fill}"></span>
        <span class="nm">${esc(sl.label)}</span>
        <span class="pc">${Math.round(100*sl.secs/total)}%</span></li>`).join("");
    return `<div class="pie">
      <svg viewBox="0 0 ${S} ${S}" role="img" aria-label="ringdiagram" preserveAspectRatio="xMidYMid meet">${arcs}
        <text class="pie-mid" x="${cx}" y="${cy-1}" text-anchor="middle">${esc(centre[0])}</text>
        <text class="pie-sub" x="${cx}" y="${cy+12}" text-anchor="middle">${esc(centre[1])}</text>
      </svg>
      <ul class="pie-legend">${legend}</ul>
    </div>`;
  }

  function sprekersHTML(){
    const sp = SPREKERS && SPREKERS.meetings && SPREKERS.meetings[String(current)];
    if(!sp) return "";
    const fr = Object.entries(sp.fracties || {});
    const ro = Object.entries(sp.rollen || {});
    if(!fr.length && !ro.length) return "";
    const frTotal = fr.reduce((a, [, v]) => a + v, 0);
    const total = frTotal + ro.reduce((a, [, v]) => a + v, 0) || 1;
    const ramp = i => `var(--pie-${Math.min(i + 1, PIE_SLOTS)})`;

    // Left: the fracties together against each role, biggest first.
    const wie = [{key: "fracties", label: "Fracties", secs: frTotal},
                 ...ro.map(([k, v]) => ({key: k, label: roleLabel(k), secs: v}))]
      .filter(x => x.secs > 0).sort((a, b) => b.secs - a.secs)
      .map((x, i) => ({...x, fill: ramp(i),
                       title: `${x.label}: ${mmss(x.secs)} — ${Math.round(100*x.secs/total)}% van de vergadering`}));

    // Right: inside the fracties. Five by name, everything else as one slice.
    const top = fr.slice(0, PIE_SLOTS - 1), rest = fr.slice(PIE_SLOTS - 1);
    const restSecs = rest.reduce((a, [, v]) => a + v, 0);
    const binnen = top.map(([slug, secs], i) => ({
      label: pLabel(slug), secs, fill: ramp(i),
      title: `${pName(slug)}: ${mmss(secs)} — ${Math.round(100*secs/frTotal)}% van de spreektijd van de fracties`}));
    if(restSecs > 0) binnen.push({
      label: `Overige ${rest.length} fracties`, secs: restSecs, fill: "var(--pie-rest)",
      title: `${rest.map(([s]) => pName(s)).join(", ")}: samen ${mmss(restSecs)}`});

    return `<section class="chart meet-sprekers"><h3>Wie was aan het woord</h3>
      <p class="chart-sub">Spreektijd volgens de sprekersindex van de griffie: ${sp.momenten} spreekmomenten over ${mmss(sp.indexed)} vergadering.</p>
      <div class="pies">
        <figure>${donutHTML(wie, total, [mmss(total), "totaal"])}
          <figcaption>Fracties tegenover voorzitter en college.</figcaption></figure>
        ${frTotal > 0 ? `<figure>${donutHTML(binnen, frTotal, [mmss(frTotal), "fracties"])}
          <figcaption>De spreektijd van de fracties onderling${rest.length ? `, de kleinste ${rest.length} samengenomen` : ""}.</figcaption></figure>` : ""}
      </div>
    </section>`;
  }

  /* Zoek in het debat. Hits are rendered into #trHits by renderHits(), so typing never rebuilds
     the page and the input keeps focus. */
  function zoekHTML(){
    const sp = SPREKERS && SPREKERS.meetings && SPREKERS.meetings[String(current)];
    if(TR === null){
      const msg = (sp && sp.transcript === false) ? "Voor deze vergadering is geen ondertitelbestand gepubliceerd."
        : trFailed ? "Het transcript van deze vergadering kon niet geladen worden."
        : (sp && sp.transcript) ? "Transcript wordt geladen&hellip;" : null;
      return msg ? `<section class="chart meet-zoek"><h3>Zoek in het debat</h3>
          <p class="chart-sub">${msg}</p></section>` : "";
    }
    return `<section class="chart meet-zoek"><h3>Zoek in het debat</h3>
      <p class="chart-sub">Automatische ondertiteling van ${TR.cues.length.toLocaleString("nl")} fragmenten &mdash;
        de spraakherkenning verhaspelt namen en woorden, dus controleer een citaat in de
        <a href="${esc(TR.source)}" target="_blank" rel="noopener">video</a>
        (<a href="${esc(TR.srt)}" target="_blank" rel="noopener">bronbestand</a>).
        Een treffer linkt naar het begin van het spreekmoment, niet naar de seconde zelf.</p>
      <div class="tr-search"><input id="trQ" type="search" placeholder="Zoek een woord in deze vergadering&hellip;"
        autocomplete="off" value="${esc(q)}" aria-label="Zoek in het transcript"></div>
      <div id="trHits">${hitsHTML()}</div>
    </section>`;
  }

  function hitsHTML(){
    if(!TR) return "";
    const needle = fold(q.trim());
    if(needle.length < 2)
      return `<p class="chart-sub">Typ minstens twee letters.</p>`;
    const hits = [];
    for(let i = 0; i < TR.folded.length; i++) if(TR.folded[i].includes(needle)) hits.push(i);
    if(!hits.length)
      return `<p class="chart-sub">Geen treffers voor &ldquo;${esc(q.trim())}&rdquo; in deze vergadering.</p>`;

    const rows = hits.slice(0, limit).map(i => {
      const [t, text] = TR.cues[i];
      const mom = momentAt(t);
      const sp = mom ? TR.speakers[mom[2]] : null;
      const who = sp ? sp.n : "onbekende spreker";
      const tag = sp ? (sp.p ? pLabel(sp.p) : sp.r) : "";
      const href = mom && mom[3] ? `${TR.source}#si_${mom[3]}` : TR.source;
      return `<li>
        <a class="tr-time" href="${esc(href)}" target="_blank" rel="noopener"
           title="Open de video op dit spreekmoment">${hms(t)}</a>
        <span class="tr-who">${esc(who)}${tag ? ` <span class="tr-tag">${esc(tag)}</span>` : ""}</span>
        <span class="tr-text">${mark(text, needle)}</span>
      </li>`;
    }).join("");

    return `<p class="chart-sub">${hits.length.toLocaleString("nl")} treffer${hits.length === 1 ? "" : "s"}${hits.length > limit ? `, eerste ${limit} getoond` : ""}.</p>
      <ul class="tr-hits">${rows}</ul>
      ${hits.length > limit ? `<button class="csvbtn" data-tr-more>Toon meer</button>` : ""}`;
  }

  function renderHits(){
    const box = document.getElementById("trHits");
    if(box) box.innerHTML = hitsHTML();
  }

  function chartsHTML(rows){
    const ids = new Set(rows.map(m => m.id));
    const keep = m => ids.has(m.id);
    const types = new Set(rows.map(m => m.type));
    return `<div class="charts">
      <section class="chart"><h3>Indieners</h3><p class="chart-sub">Moasjes en amendeminten die een fractie deze vergadering (mede) indiende.</p>${chartIndieners(rows)}</section>
      <section class="chart"><h3>Aan de winnende kant</h3><p class="chart-sub">Hoe vaak een fractie deze vergadering met de uitslag meestemde.</p>${chartWinning(types, keep, 3)}</section>
      <section class="chart"><h3>Hoe omstreden</h3><p class="chart-sub">Verschil tussen voor- en tegenstemmen, van unaniem tot een nipte meerderheid.</p>${chartMargins(rows)}</section>
    </div>`;
  }

  // One table per agendapunt, everything open: this page is the detail view.
  function agendaTablesHTML(rows){
    const vps = visibleParties();
    return agendas(rows).map(a => `<section class="meet-agenda" id="ag-${a.aid}">
      <h3>${esc(a.label)} <span class="grp-n">${a.rows.length} stemming${a.rows.length===1?"":"en"}</span></h3>
      <div class="table-scroll flat"><table>${headHTML(vps)}<tbody>${a.rows.map(m => rowHTML(m, vps)).join("")}</tbody></table></div>
    </section>`).join("");
  }

  return {open, refresh};
})();

// The filter chips are spans, so they need their own keyboard handling.
document.addEventListener("keydown", e => {
  if(e.key !== "Enter" && e.key !== " ") return;
  const chip = e.target.closest ? e.target.closest(".ag-filter .chip") : null;
  if(!chip) return;
  e.preventDefault();
  chip.click();
});

// Classic script: a top-level const is not a property of window, and app.js checks for it there.
window.MeetingPage = MeetingPage;
