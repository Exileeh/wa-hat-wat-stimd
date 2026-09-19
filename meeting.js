/* Wa hat wat stimd? — de pagina van één plenaire vergadering (#vergadering/<id>).

   Deliberately a file of its own: the table and the analyses in app.js do not know about it, and it
   only borrows their helpers (DATA, esc, pName/pLabel, cellVerdict, rowHTML, headHTML, tableOrder,
   the chart functions, formatDateNL, meetingOf, agendaIdOf, agendaLabel). Room to grow: notulen,
   sprekers, toezeggingen, a link to the video — add a block to render() below and nothing else in
   the site has to change.

   app.js calls MeetingPage.open(mid) from route() and MeetingPage.refresh() after live bijladen. */
const MeetingPage = (() => {
  const el = () => document.getElementById("meetingBody");
  let current = null;          // the meeting id being shown, null when the view is closed
  let wired = false;

  // The pin buttons on this page are the same buttons as in the table.
  function wire(){
    if(wired) return;
    wired = true;
    const view = document.getElementById("meetingView");
    if(!view) return;
    view.addEventListener("click", e => {
      const b = e.target.closest("button.pin");
      if(b) togglePin(+b.dataset.id);
    });
  }

  function open(mid){
    wire();
    current = Number.isFinite(mid) && mid > 0 ? mid : null;
    render();
  }

  function refresh(){
    if(current !== null && !document.getElementById("meetingView").hidden) render();
  }

  function render(){
    const box = el();
    if(!box) return;
    const rows = current === null ? [] : meetingRows(current);
    if(!rows.length){
      document.title = "Vergadering — Wa hat wat stimd?";
      box.innerHTML = `<div class="empty">Geen stemmingen bekend voor deze vergadering.</div>`;
      return;
    }
    const date = rows.map(m => m.date).sort()[0];
    document.title = `Vergadering ${formatDateNL(date, false)} — Wa hat wat stimd?`;
    box.innerHTML = headerHTML(rows, date) + kpiHTML(rows) + agendaNavHTML(rows)
      + chartsHTML(rows) + agendaTablesHTML(rows);
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

  function agendaNavHTML(rows){
    const list = agendas(rows);
    if(list.length < 2) return "";
    return `<nav class="agenda-nav" aria-label="Agendapunten">${
      list.map(a => `<a href="#vergadering/${current}" data-ag="${a.aid}">${esc(a.label)} <span class="grp-n">${a.rows.length}</span></a>`).join("")}</nav>`;
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

// The agenda navigation scrolls instead of following the (identical) hash.
document.addEventListener("click", e => {
  const a = e.target.closest ? e.target.closest(".agenda-nav a[data-ag]") : null;
  if(!a) return;
  e.preventDefault();
  const s = document.getElementById(`ag-${a.dataset.ag}`);
  if(s) s.scrollIntoView({behavior: "smooth", block: "start"});
});

// Classic script: a top-level const is not a property of window, and app.js checks for it there.
window.MeetingPage = MeetingPage;
