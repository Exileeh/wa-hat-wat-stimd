/* Wa hat wat stimd? — stemgedrag in de Provinciale Staten van Fryslân.
   Vanilla JS, no dependencies. Reads data/fryslan.json (daily snapshot) and data/roles.json, then
   tops the snapshot up live from api.notubiz.nl for meetings newer than the snapshot. */

const DATA_URL = "data/fryslan.json";
const ROLES_URL = "data/roles.json";
const NOTUBIZ_API = "https://api.notubiz.nl";
const API_VERSION = "1.21";
const LIVE_MAX_MEETINGS = 10;   // protect the API: never crawl more than this many new meetings per visit

const PIN_KEY = "wsw_pinned_fryslan";
// Short column labels where the fractie name is long.
const ABBR = {bbb:"BBB", pvda:"PvdA", cda:"CDA", fnp:"FNP", grienlinks:"GL", vvd:"VVD", christenunie:"CU",
  pvv:"PVV", ja21:"JA21", "provinciaal-belang-frysln":"PBF", pvdd:"PvdD", sp:"SP", d66:"D66",
  "van-dijk-fvd":"Van Dijk", "steatelid-jonker":"Jonker"};
const TYPE_LABEL = {motie:"Motie", frjemd:"Moasje frjemd", amendement:"Amendement", besluit:"Besluit", ordevoorstel:"Ordevoorstel", overig:"Overig"};
const TYPE_PLURAL = {motie:"moties", frjemd:"moasjes frjemd", amendement:"amendementen", besluit:"besluiten", ordevoorstel:"ordevoorstellen", overig:"overige"};
// Reading order of the type chips/tiles (the collector sorts the list alphabetically).
const TYPE_ORDER = ["motie", "frjemd", "amendement", "besluit", "ordevoorstel", "overig"];
// Frisian document label per type (the portal module is "Moasjes en amendeminten").
const DOC_LABEL = {motie:"Moasje", frjemd:"Moasje", amendement:"Amendemint"};
// How much better the best coalition|oppositie cut must be than the best cut elsewhere in the row
// before the table draws the line (percentage points of agreement).
const SEAM_MIN_LEAD = 3;
// Min. stemmingen a party must have voted on to appear in the Overeenkomst matrix — below this an
// agreement % is noise (a party that voted once is "100% gelijk" with everyone).
const MATRIX_MIN = 5;
// Below this many *shared* stemmingen a pair's agreement % is too noisy to colour confidently.
const MATRIX_PAIR_MIN = 10;

let DATA, ROLES, state, TABLE_ORDER = null, AG = null, ORDER = null, ALLTYPES = null, MTYPES = null, PTYPES = null, CTYPES = null, STYPES = null;
const $ = s => document.querySelector(s);
const esc = s => (s == null ? "" : String(s)).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const pName = slug => { const p = DATA.parties.find(x => x.slug === slug); return p ? p.name : (ABBR[slug] || slug); };
const pLabel = slug => ABBR[slug] || pName(slug);

// Source (meeting page) + document (Moasje PDF) links, used in the table and the popup lists.
const srcLink = m => m.source ? ` <a class="ext" href="${esc(m.source)}" target="_blank" rel="noopener" title="Bekijk de vergadering op het Notubiz-portaal">&#8599;</a>` : "";
const ICO = id => `<svg class="ico" aria-hidden="true"><use href="#${id}"/></svg>`;
const docLink = m => m.document
  ? `<a class="doclink" href="${esc(m.document)}" target="_blank" rel="noopener" title="${esc(m.documentTitle || "Open het document")} (PDF)">${ICO("i-doc")}${DOC_LABEL[m.type] || "Document"}</a>`
  : "";
const indienersText = m => (m.indieners && m.indieners.length) ? m.indieners.map(pLabel).join(", ") : "";

/* ---- Vergaderingen en agendapunten ----
   Every stemming carries `meetingId` and (nearly always) `agenda` {id, nr, title}; older snapshots
   and live rows without an agenda fall back on the meeting id in `source`. The table groups on
   these two keys, the meeting page (meeting.js) uses the same helpers. */
const MONTHS_NL = ["januari","februari","maart","april","mei","juni","juli","augustus","september","oktober","november","december"];
const DAYS_NL = ["zondag","maandag","dinsdag","woensdag","donderdag","vrijdag","zaterdag"];
function formatDateNL(iso, withDay = true){
  const d = new Date(`${iso}T12:00:00`);
  if(isNaN(d)) return iso;
  const long = `${d.getDate()} ${MONTHS_NL[d.getMonth()]} ${d.getFullYear()}`;
  return withDay ? `${DAYS_NL[d.getDay()]} ${long}` : long;
}
const meetingOf = m => m.meetingId || +((String(m.source || "").match(/vergadering\/(\d+)/) || [0, 0])[1]);
const agendaIdOf = m => (m.agenda && m.agenda.id) || 0;
const agendaLabel = m => m.agenda ? `${m.agenda.nr} · ${m.agenda.title}` : "Zonder agendapunt";
const mKey = mid => `m:${mid}`;
const aKey = (mid, aid) => `a:${mid}:${aid}`;
const collator = new Intl.Collator("nl", {numeric: true, sensitivity: "base"});
const meetingRows = mid => DATA.moties.filter(m => meetingOf(m) === mid);

async function init(){
  DATA = await (await fetch(DATA_URL)).json();
  ALLTYPES = sortTypes((DATA.meta.types && DATA.meta.types.length) ? DATA.meta.types.slice() : [...new Set(DATA.moties.map(m => m.type))]);
  applyTheme(DATA.meta.style || {});
  state = {
    types: new Set(ALLTYPES),
    parties: new Set(DATA.parties.map(p => p.slug)),
    search: "", result: "all", controversial: false, onlyPinned: false, raw: false, cluster: true,
    sort: "date-desc",
    open: new Set(),   // expanded accordion keys: "m:<meetingId>" and "a:<meetingId>:<agendaId>"
    pinned: new Set(JSON.parse(localStorage.getItem(PIN_KEY) || "[]")),
  };
  renderHeader();
  setupGlobalHandlers();
  buildControls(ALLTYPES);
  updatePartySummary();
  render();
  window.addEventListener("hashchange", route);
  route();
  liveTopUp().catch(e => console.warn("live bijladen mislukt:", e));
}

// Chips and tiles read best in a fixed order; the collector writes meta.types alphabetically.
const sortTypes = ts => ts.slice().sort((a, b) => (TYPE_ORDER.indexOf(a) + 1 || 99) - (TYPE_ORDER.indexOf(b) + 1 || 99) || a.localeCompare(b));

function applyTheme(style){
  document.documentElement.style.setProperty("--accent", style.accent || "#c8102e");
}

function renderHeader(){
  const meta = DATA.meta;
  const srcName = `${esc(meta.body)}, provincie ${esc(meta.province)}`;
  $("#src").innerHTML = `Bron: <a href="${esc(meta.source)}" target="_blank" rel="noopener">${srcName}</a> · open data · periode ${esc(meta.term)} · bijgewerkt ${esc(meta.generated_at.slice(0,10))}`;
  $("#helpSource").innerHTML = `Open data van de <a href="${esc(meta.source)}" target="_blank" rel="noopener">${srcName}</a> (Notubiz vergaderportaal), periode ${esc(meta.term)}, dagelijks bijgewerkt.`
    + (meta.note ? ` ${esc(meta.note)}` : "");
  // The stale notice: shown only once the snapshot is older than meta.noticeAfterDays. The
  // collector keeps the last good file when it cannot reach the source, so age is the signal.
  const ageDays = (Date.now() - Date.parse(meta.generated_at)) / 86400e3;
  const issue = meta.knownIssue && ageDays > (meta.noticeAfterDays || 14) ? meta.knownIssue : null;
  $("#staleNote").hidden = !issue;
  if(issue) $("#staleNote").innerHTML = `⚠️ ${esc(issue)} <b>Laatste verversing: ${esc(meta.generated_at.slice(0,10))}.</b>`;
}

/* ---- Views (tabs) ---- */
const VIEWS = {
  table:   {hash: "",              open: null},
  stats:   {hash: "statistieken",  open: () => openStats()},
  matrix:  {hash: "overeenkomst",  open: () => openMatrix()},
  profile: {hash: "partijprofiel", open: () => openProfile()},
  compare: {hash: "vergelijken",   open: () => openCompare()},
  // No tab of its own: reached from a vergadering-regel in the table or straight from a URL.
  meeting: {hash: "vergadering",   open: arg => MeetingPage.open(+arg)},
};
function route(){
  const raw = decodeURIComponent(location.hash.replace(/^#\/?/, "")).trim();
  const [head, ...rest] = raw.split("/");
  const h = head.toLowerCase();
  const name = Object.keys(VIEWS).find(k => VIEWS[k].hash === h) || "table";
  showView(name, rest.join("/"));
}
const BASE_TITLE = document.title;
function showView(name, arg){
  const v = VIEWS[name];
  if(name !== "meeting") document.title = BASE_TITLE;   // the meeting page names itself
  if(v.open) v.open(arg);
  for(const k of Object.keys(VIEWS)){
    const panel = document.getElementById(`${k}View`);
    if(panel) panel.hidden = k !== name;
  }
  document.querySelectorAll(".view-tab[data-view]").forEach(b => {
    const on = b.dataset.view === name;
    b.classList.toggle("on", on);
    if(on) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current");
  });
  if(name !== "table") window.scrollTo({top: 0});
}
function openMatrix(){
  if(!MTYPES) MTYPES = new Set(ALLTYPES);
  typeChips($("#matrixTypes"), MTYPES, refreshMatrix);
  refreshMatrix();
}

function setupGlobalHandlers(){
  // Popovers (partijen, weergave) close on a click outside or Escape.
  document.addEventListener("click", e => {
    document.querySelectorAll("details.pop[open]").forEach(d => { if(!d.contains(e.target)) d.open = false; });
  });
  document.addEventListener("keydown", e => {
    if(e.key === "Escape"){
      document.querySelectorAll("details.pop[open]").forEach(d => d.open = false);
      document.querySelectorAll(".modal").forEach(mo => mo.hidden = true);
    }
  });
  // The analyses are tabs (views); the URL hash carries the active one so every view is linkable.
  document.querySelectorAll(".view-tab[data-view]").forEach(b => b.onclick = () => { location.hash = VIEWS[b.dataset.view].hash; });
  $("#helpBtn").onclick = () => $("#helpModal").hidden = false;
  $("#legendBtn").onclick = () => $("#legendModal").hidden = false;
  $("#csvBtn").onclick = exportCSV;
  document.querySelectorAll(".modal").forEach(mo => mo.addEventListener("click", e => { if(e.target === mo) mo.hidden = true; }));
  document.querySelectorAll("[data-close]").forEach(btn => btn.onclick = () => { document.getElementById(btn.dataset.close).hidden = true; });
  // Pin toggle and accordion toggle via event delegation — one listener instead of one per row.
  $(".wrap").addEventListener("click", e => {
    const b = e.target.closest("button.pin");
    if(b){ togglePin(+b.dataset.id); return; }
    const g = e.target.closest("tr.grp");
    if(g && !e.target.closest("a")) toggleGroup(g.dataset.key);
  });
  $(".wrap").addEventListener("keydown", e => {
    if(e.key !== "Enter" && e.key !== " ") return;
    const g = e.target.closest && e.target.closest("tr.grp");
    if(!g) return;
    e.preventDefault();
    toggleGroup(g.dataset.key);
  });
}

// Shared type-filter chips for the popups ("Tel mee").
function typeChips(el, set, cb){
  el.innerHTML = ALLTYPES.map(t => `<span class="chip${set.has(t)?" on":""}" data-type="${t}">${TYPE_LABEL[t]||t}</span>`).join("");
  el.onclick = e => {
    const c = e.target.closest(".chip"); if(!c) return;
    const t = c.dataset.type;
    if(set.has(t)){ if(set.size === 1) return; set.delete(t); } else set.add(t);
    c.classList.toggle("on"); cb();
  };
}

/* ---- Overeenkomst (agreement matrix) ---- */
function refreshMatrix(){ AG = computeAgreement(MTYPES); ORDER = seriate(AG); renderMatrix(); }

function computeAgreement(types){
  const counts = {};
  const vd = DATA.moties.filter(m => types.has(m.type)).map(m => {
    const o = {};
    for(const p of DATA.parties){
      const r = cellVerdict(m.votes[p.slug]);
      if(r){ o[p.slug] = r.label; counts[p.slug] = (counts[p.slug]||0) + 1; }
    }
    return o;
  });
  const ps = DATA.parties.filter(p => (counts[p.slug]||0) >= MATRIX_MIN);
  const M = {};
  for(const a of ps){ M[a.slug] = {};
    for(const b of ps){
      if(a.slug === b.slug){ M[a.slug][b.slug] = null; continue; }
      let same = 0, tot = 0;
      for(const v of vd){
        if(v[a.slug] !== undefined && v[b.slug] !== undefined){ tot++; if(v[a.slug] === v[b.slug]) same++; }
      }
      M[a.slug][b.slug] = tot ? {pct: Math.round(100*same/tot), n: tot} : null;
    }
  }
  return M;
}
// Seriation: average-linkage clustering so similar-voting parties end up adjacent.
function seriate(M){
  const slugs = Object.keys(M);
  if(slugs.length < 2) return slugs;
  const dist = (a,b) => { const c = M[a] && M[a][b]; return c ? 100 - c.pct : 100; };
  let cl = slugs.map(s => ({m:[s]}));
  const cd = (c1,c2) => { let s=0,n=0; for(const a of c1.m) for(const b of c2.m){ s+=dist(a,b); n++; } return s/n; };
  while(cl.length > 1){
    let bi=0, bj=1, best=Infinity;
    for(let i=0;i<cl.length;i++) for(let j=i+1;j<cl.length;j++){ const d=cd(cl[i],cl[j]); if(d<best){best=d;bi=i;bj=j;} }
    const A=cl[bi], B=cl[bj];
    const aF=A.m[0], aL=A.m[A.m.length-1], bF=B.m[0], bL=B.m[B.m.length-1];
    const opts = [[0,0,dist(aL,bF)],[0,1,dist(aL,bL)],[1,0,dist(aF,bF)],[1,1,dist(aF,bL)]].sort((x,y)=>x[2]-y[2]);
    const ma = opts[0][0] ? [...A.m].reverse() : A.m;
    const mb = opts[0][1] ? [...B.m].reverse() : B.m;
    cl = cl.filter((_,k)=>k!==bi && k!==bj); cl.push({m:[...ma,...mb]});
  }
  return cl[0].m;
}
function renderMatrix(){
  const order = ORDER || Object.keys(AG);
  const name = pName, lbl = pLabel;
  const head = `<tr><th></th>${order.map(s=>`<th title="${esc(name(s))}">${esc(lbl(s))}</th>`).join("")}</tr>`;
  const rows = order.map(a => `<tr><th class="rowh" title="${esc(name(a))}">${esc(lbl(a))}</th>${
    order.map(b => {
      const c = AG[a][b];
      if(c === null) return `<td class="diag">&ndash;</td>`;
      if(!c) return `<td class="na" title="geen gezamenlijke stemmingen">&middot;</td>`;
      if(c.n < MATRIX_PAIR_MIN) return `<td class="lown" title="${esc(name(a))} &amp; ${esc(name(b))}: ${c.pct}% gelijk — slechts ${c.n} gezamenlijke stemming${c.n===1?"":"en"}, te weinig voor een betrouwbaar percentage">${c.pct}</td>`;
      return `<td style="background:hsl(${Math.round(c.pct*1.35)},70%,72%)" title="${esc(name(a))} &amp; ${esc(name(b))}: ${c.pct}% gelijk (${c.n} stemmingen)">${c.pct}</td>`;
    }).join("")}</tr>`).join("");
  const excluded = DATA.parties.filter(p => !(p.slug in AG));
  const note = excluded.length
    ? `<p class="modal-sub" style="margin-top:10px">Niet getoond (minder dan ${MATRIX_MIN} stemmingen): ${excluded.map(p => esc(p.name)).join(", ")}.</p>`
    : "";
  $("#matrixBody").innerHTML = `<table class="matrix"><thead>${head}</thead><tbody>${rows}</tbody></table>${note}`;
}

/* ---- Partijprofiel ---- */
function openProfile(){
  if(!PTYPES){
    PTYPES = new Set(ALLTYPES);
    $("#profileParty").innerHTML = DATA.parties.map(p => `<option value="${p.slug}">${esc(p.name)}</option>`).join("");
    $("#profileParty").onchange = renderProfile;
  }
  typeChips($("#profileTypes"), PTYPES, renderProfile);
  renderProfile();
}
function profileStats(slug, types, keep){
  let voor=0, tegen=0, onth=0, afw=0, win=0, decided=0;
  const lone = [];
  for(const m of DATA.moties){
    if(!types.has(m.type)) continue;
    if(keep && !keep(m)) continue;
    const v = m.votes[slug];
    if(!v){ afw++; continue; }
    const r = cellVerdict(v);
    if(r.label === "V") voor++; else if(r.label === "T") tegen++; else onth++;
    if(r.label !== "O" && (m.result === "accepted" || m.result === "rejected")){
      decided++;
      if((r.label === "V" && m.result === "accepted") || (r.label === "T" && m.result === "rejected")) win++;
    }
    if(r.label !== "O"){
      let same=0, opposite=0;
      for(const p of DATA.parties){
        if(p.slug === slug) continue;
        const ov = m.votes[p.slug]; if(!ov) continue;
        const orr = cellVerdict(ov);
        if(orr.label === r.label) same++;
        else if(orr.label !== "O") opposite++;
      }
      if(same === 0 && opposite > 0) lone.push(m);
    }
  }
  return {voor, tegen, onth, afw, win, decided, winPct: decided ? Math.round(100*win/decided) : null, lone};
}
function renderProfile(){
  const slug = $("#profileParty").value;
  const st = profileStats(slug, PTYPES);
  const lone = st.lone.slice().sort((a,b) => b.date.localeCompare(a.date));
  $("#profileBody").innerHTML = `
    <div class="stat-grid">
      <div class="stat primary"><div class="num">${st.winPct===null?"&ndash;":st.winPct+"%"}</div><div class="lab">aan de winnende kant<br>(${st.decided} beslissende)</div></div>
      <div class="stat"><div class="num">${st.voor}</div><div class="lab">voor</div></div>
      <div class="stat"><div class="num">${st.tegen}</div><div class="lab">tegen</div></div>
      <div class="stat"><div class="num">${st.onth}</div><div class="lab">onthouden</div></div>
      <div class="stat"><div class="num">${st.afw}</div><div class="lab">afwezig</div></div>
    </div>
    <h3 class="section">Als enige tegen de rest in (${lone.length})</h3>
    ${lone.length ? `<div class="scrollbox"><table class="list"><thead><tr><th>Datum</th><th>Onderwerp</th><th>Stem</th></tr></thead><tbody>${
      lone.map(m => { const r = cellVerdict(m.votes[slug]);
        return `<tr><td>${m.date}</td><td>${esc(m.title)} ${docLink(m)}${srcLink(m)}</td><td><span class="vbadge ${r.cls}">${r.label}</span></td></tr>`; }).join("")
    }</tbody></table></div>` : `<p class="modal-sub">Geen stemmingen waarbij ${esc(pName(slug))} als enige tegen de rest in stemde (binnen deze types).</p>`}
  `;
}

/* ---- Vergelijken ---- */
function openCompare(){
  if(!CTYPES){
    CTYPES = new Set(ALLTYPES);
    const opts = DATA.parties.map(p => `<option value="${p.slug}">${esc(p.name)}</option>`).join("");
    $("#cmpA").innerHTML = opts; $("#cmpB").innerHTML = opts;
    if(DATA.parties.length > 1) $("#cmpB").selectedIndex = 1;
    $("#cmpA").onchange = renderCompare; $("#cmpB").onchange = renderCompare;
  }
  typeChips($("#compareTypes"), CTYPES, renderCompare);
  renderCompare();
}
function renderCompare(){
  const a = $("#cmpA").value, b = $("#cmpB").value;
  if(a === b){ $("#compareBody").innerHTML = `<p class="modal-sub">Kies twee verschillende partijen.</p>`; return; }
  let agree = 0; const rows = [];
  for(const m of DATA.moties){
    if(!CTYPES.has(m.type)) continue;
    const va = m.votes[a], vb = m.votes[b]; if(!va || !vb) continue;
    const ra = cellVerdict(va), rb = cellVerdict(vb);
    if(ra.label === rb.label) agree++; else rows.push({m, ra, rb});
  }
  rows.sort((x,y) => y.m.date.localeCompare(x.m.date));
  const tot = agree + rows.length;
  $("#compareBody").innerHTML = `
    <p class="cmp-summary"><b>${esc(pName(a))}</b> en <b>${esc(pName(b))}</b> stemden
      <b>${tot?Math.round(100*agree/tot):0}% gelijk</b> &mdash; ${agree} gelijk, <b>${rows.length} verschillend</b> (van ${tot} gezamenlijke stemmingen).</p>
    ${rows.length ? `<div class="scrollbox"><table class="list"><thead><tr><th>Datum</th><th>Onderwerp</th><th>${esc(pLabel(a))}</th><th>${esc(pLabel(b))}</th></tr></thead><tbody>${
      rows.map(({m,ra,rb}) => `<tr><td>${m.date}</td><td>${esc(m.title)} ${docLink(m)}${srcLink(m)}</td><td><span class="vbadge ${ra.cls}">${ra.label}</span></td><td><span class="vbadge ${rb.cls}">${rb.label}</span></td></tr>`).join("")
    }</tbody></table></div>` : `<p class="modal-sub">Geen stemmingen waarbij ze verschillend stemden (binnen deze types).</p>`}
  `;
}

/* ---- Statistieken (dashboard) ---- */
function openStats(){
  if(!STYPES) STYPES = new Set(ALLTYPES);
  typeChips($("#statsTypes"), STYPES, renderStats);
  buildMeetingPicker();
  renderStats();
}

/* The vergadering filter: every meeting on by default. SMEETINGS holds the meeting ids that count;
   it survives a rebuild (after live bijladen new meetings arrive switched on). */
let SMEETINGS = null;
function allMeetings(){
  const byId = new Map();
  for(const m of DATA.moties){
    const mid = meetingOf(m);
    const g = byId.get(mid);
    if(g) g.n++; else byId.set(mid, {mid, date: m.date, n: 1});
  }
  return [...byId.values()].sort((a,b) => b.date.localeCompare(a.date) || b.mid - a.mid);
}
function buildMeetingPicker(){
  const list = allMeetings();
  if(!SMEETINGS) SMEETINGS = new Set(list.map(g => g.mid));
  else for(const g of list) if(!SMEETINGS.has(g.mid) && !SM_SEEN.has(g.mid)) SMEETINGS.add(g.mid);
  for(const g of list) SM_SEEN.add(g.mid);
  $("#smList").innerHTML = list.map(g =>
    `<label><input type="checkbox" data-mid="${g.mid}"${SMEETINGS.has(g.mid) ? " checked" : ""}> ${esc(formatDateNL(g.date, false))} <span class="pp-n">${g.n}</span></label>`).join("");
  $("#smList").onchange = e => {
    const mid = +e.target.dataset.mid;
    e.target.checked ? SMEETINGS.add(mid) : SMEETINGS.delete(mid);
    updateMeetingSummary(list);
    renderStats();
  };
  $("#smAll").onclick = () => setAllMeetings(list, true);
  $("#smNone").onclick = () => setAllMeetings(list, false);
  updateMeetingSummary(list);
}
const SM_SEEN = new Set();
function setAllMeetings(list, on){
  SMEETINGS = new Set(on ? list.map(g => g.mid) : []);
  $("#smList").querySelectorAll("input").forEach(i => { i.checked = on; });
  updateMeetingSummary(list);
  renderStats();
}
function updateMeetingSummary(list){
  const n = SMEETINGS.size, total = list.length;
  $("#smSummary").textContent = n === total ? "Alle vergaderingen"
    : n === 0 ? "Geen vergaderingen" : `${n} van ${total} vergaderingen`;
}
const statsKeep = m => SMEETINGS.has(meetingOf(m));
const svgOpen = (w, h) => `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="grafiek" preserveAspectRatio="xMidYMid meet">`;
const legend = items => `<div class="legend-row">${items.map(([c, l]) => `<span><span class="sw" style="background:${c}"></span>${l}</span>`).join("")}</div>`;
const RES_COLOR = {accepted:"var(--c-aangenomen)", rejected:"var(--c-verworpen)", tie:"var(--c-staken)"};
const RES_LABEL = {accepted:"aangenomen", rejected:"verworpen", tie:"staken van stemmen"};
const resKey = m => m.result === "accepted" || m.result === "rejected" ? m.result : "tie";

function renderStats(){
  const ms = DATA.moties.filter(m => STYPES.has(m.type) && statsKeep(m));
  const acc = ms.filter(m => m.result === "accepted").length;
  const byType = {}; for(const m of ms) byType[m.type] = (byType[m.type]||0) + 1;
  const meetings = new Set(ms.map(m => m.source)).size;
  const dates = ms.map(m => m.date).sort();
  $("#statsKpis").innerHTML = `
    <div class="stat primary"><div class="num">${ms.length}</div><div class="lab">stemmingen</div></div>
    <div class="stat"><div class="num">${ms.length ? Math.round(100*acc/ms.length) : 0}%</div><div class="lab">aangenomen</div></div>
    ${ALLTYPES.map(t => `<div class="stat"><div class="num">${byType[t]||0}</div><div class="lab">${esc(TYPE_PLURAL[t]||t)}</div></div>`).join("")}
    <div class="stat"><div class="num">${meetings}</div><div class="lab">vergaderingen</div></div>
    <div class="stat"><div class="num" style="font-size:16px;padding-top:4px">${dates.length ? esc(dates[dates.length-1]) : "&ndash;"}</div><div class="lab">laatste stemming</div></div>`;
  $("#chartMeetings").innerHTML = chartMeetings(ms);
  $("#chartIndieners").innerHTML = chartIndieners(ms);
  $("#chartWinning").innerHTML = chartWinning(STYPES, statsKeep);
  $("#chartMargins").innerHTML = chartMargins(ms);
}

/* 1. Stacked bars per vergadering: aangenomen / verworpen / staken. Each bar links to that
      meeting on the Statenportaal, so a striking vergadering is one click from its notulen. */
function chartMeetings(ms){
  if(!ms.length) return `<p class="modal-sub">Geen stemmingen.</p>`;
  const byId = new Map();
  for(const m of ms){
    const mid = meetingOf(m);
    let g = byId.get(mid);
    if(!g) byId.set(mid, g = {mid, date: m.date, source: m.source, accepted:0, rejected:0, tie:0, n:0});
    g[resKey(m)]++; g.n++;
  }
  const gs = [...byId.values()].sort((a,b) => a.date.localeCompare(b.date) || a.mid - b.mid);
  const W = 520, H = 220, L = 34, R = 8, T = 10, B = 34, pw = W - L - R, ph = H - T - B;
  const max = Math.max(1, ...gs.map(g => g.n));
  const step = max > 60 ? 20 : max > 30 ? 10 : 5, ymax = Math.ceil(max/step)*step;
  const bw = pw / gs.length, y = v => T + ph - v/ymax*ph;
  let s = svgOpen(W, H);
  for(let v = 0; v <= ymax; v += step) s += `<line class="grid" x1="${L}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}"/><text x="${L-6}" y="${y(v)+4}" text-anchor="end">${v}</text>`;
  let lastYear = null;
  gs.forEach((g, i) => {
    const x = L + i*bw + 1, w = Math.max(1, bw - 2);
    const parts = ["accepted","rejected","tie"].filter(k => g[k])
      .map(k => `${g[k]} ${RES_LABEL[k]}`).join(", ");
    const tip = `${formatDateNL(g.date, false)}: ${g.n} stemming${g.n===1?"":"en"} — ${parts}. Klik voor de vergadering op het Statenportaal.`;
    s += `<a href="${esc(g.source || "")}" target="_blank" rel="noopener"><title>${esc(tip)}</title>`;
    let base = 0;
    for(const key of ["accepted","rejected","tie"]){
      const v = g[key]; if(!v) continue;
      const y1 = y(base + v), h = y(base) - y1;
      s += `<rect class="bar" x="${x.toFixed(1)}" y="${y1.toFixed(1)}" width="${w.toFixed(1)}" height="${h.toFixed(1)}" fill="${RES_COLOR[key]}"${base===0?` rx="2"`:""}/>`;
      base += v;
    }
    // A hit area over the whole column, so a thin bar is still easy to click.
    s += `<rect class="hit" x="${x.toFixed(1)}" y="${T}" width="${w.toFixed(1)}" height="${ph.toFixed(1)}" fill="transparent"/></a>`;
    const year = g.date.slice(0,4);
    if(year !== lastYear){ lastYear = year; s += `<text x="${(x + w/2).toFixed(1)}" y="${H-B+16}" text-anchor="middle">${year}</text>`; }
  });
  s += `<line class="axis" x1="${L}" x2="${W-R}" y1="${y(0)}" y2="${y(0)}"/></svg>`;
  return s + legend([[RES_COLOR.accepted,"aangenomen"],[RES_COLOR.rejected,"verworpen"],[RES_COLOR.tie,"staken van stemmen"]])
    + `<p class="chart-sub" style="margin-top:6px">Eén balk per plenaire vergadering (${gs.length} in deze selectie), oudste links.</p>`;
}

// 2. Indieners: per fractie the moties/amendementen it (co-)submitted, split by outcome.
function chartIndieners(ms){
  const rows = {};
  let withInd = 0, eligible = 0;
  for(const m of ms){
    if(m.type !== "motie" && m.type !== "frjemd" && m.type !== "amendement") continue;
    eligible++;
    if(!m.indieners || !m.indieners.length) continue;
    withInd++;
    for(const s of m.indieners){ const r = rows[s] || (rows[s] = {accepted:0, rejected:0, tie:0}); r[resKey(m)]++; }
  }
  const list = Object.entries(rows).map(([s, r]) => ({slug:s, ...r, n: r.accepted + r.rejected + r.tie}))
    .sort((a,b) => b.n - a.n || a.slug.localeCompare(b.slug));
  if(!list.length) return `<p class="modal-sub">Geen moties of amendementen met bekende indieners in deze selectie.</p>`;
  const W = 520, rowH = 22, L = 74, R = 96, T = 6, H = T + list.length*rowH + 8, pw = W - L - R;
  const max = list[0].n;
  let s = svgOpen(W, H);
  list.forEach((r, i) => {
    const yy = T + i*rowH; let x = L;
    s += `<g class="row"><text class="lbl" x="${L-8}" y="${yy+15}" text-anchor="end">${esc(pLabel(r.slug))}</text>`;
    for(const key of ["accepted","rejected","tie"]){
      const v = r[key]; if(!v) continue;
      const w = v/max*pw;
      s += `<rect class="bar" x="${x.toFixed(1)}" y="${yy+3}" width="${w.toFixed(1)}" height="${rowH-6}" fill="${RES_COLOR[key]}"><title>${esc(pName(r.slug))}: ${v} ${RES_LABEL[key]} van ${r.n} (mede)ingediend</title></rect>`;
      x += w;
    }
    s += `<text class="val" x="${(x+6).toFixed(1)}" y="${yy+15}">${r.n} · ${Math.round(100*r.accepted/r.n)}% aangenomen</text></g>`;
  });
  s += `</svg>`;
  return s + legend([[RES_COLOR.accepted,"aangenomen"],[RES_COLOR.rejected,"verworpen"],[RES_COLOR.tie,"staken"]])
    + `<p class="chart-sub" style="margin-top:6px">Een motie met meerdere indieners telt bij elke indiener mee. Indieners bekend voor ${withInd} van ${eligible} moties en amendementen.</p>`;
}

// 3. Percentage of decided votes each fractie cast on the winning side.
function chartWinning(types, keep, minDecided = 5){
  const list = DATA.parties.map(p => ({slug: p.slug, ...profileStats(p.slug, types, keep)}))
    .filter(r => r.decided >= minDecided).sort((a,b) => b.winPct - a.winPct || b.decided - a.decided);
  if(!list.length) return `<p class="modal-sub">Te weinig stemmingen.</p>`;
  const W = 520, rowH = 22, L = 74, R = 78, T = 6, H = T + list.length*rowH + 8, pw = W - L - R;
  let s = svgOpen(W, H);
  for(const v of [25, 50, 75, 100]) s += `<line class="grid" x1="${L + v/100*pw}" x2="${L + v/100*pw}" y1="${T}" y2="${H-8}"/>`;
  list.forEach((r, i) => {
    const yy = T + i*rowH, w = r.winPct/100*pw;
    s += `<g class="row"><text class="lbl" x="${L-8}" y="${yy+15}" text-anchor="end">${esc(pLabel(r.slug))}</text>
      <rect class="bar" x="${L}" y="${yy+3}" width="${w.toFixed(1)}" height="${rowH-6}" rx="3" fill="var(--accent)"><title>${esc(pName(r.slug))}: ${r.win} van ${r.decided} beslissende stemmingen aan de winnende kant (${r.winPct}%)</title></rect>
      <text class="val" x="${(L+w+6).toFixed(1)}" y="${yy+15}">${r.winPct}% <tspan style="font-weight:400;fill:var(--muted)">(${r.decided})</tspan></text></g>`;
  });
  s += `</svg>`;
  return s + `<p class="chart-sub" style="margin-top:6px">Aandeel van de aangenomen/verworpen stemmingen waarin de fractie met de uitslag meestemde; tussen haakjes het aantal. Fracties met minder dan ${minDecided} beslissende stemmingen zijn weggelaten.</p>`;
}

// 4. How contested: distribution of the margin |voor − tegen|, from unanimous to razor-thin.
const MARGIN_BUCKETS = [
  {key:"unaniem",   label:"unaniem",           test:(a,d) => (a===0) !== (d===0)},
  {key:"ruim",      label:"ruim (≥ 20)",        test:(a,d) => Math.abs(a-d) >= 20},
  {key:"duidelijk", label:"duidelijk (10–19)",  test:(a,d) => Math.abs(a-d) >= 10},
  {key:"krap",      label:"krap (4–9)",         test:(a,d) => Math.abs(a-d) >= 4},
  {key:"nipt",      label:"nipt (1–3)",         test:(a,d) => Math.abs(a-d) >= 1},
  {key:"staken",    label:"staken (0)",         test:() => true},
];
const marginBucket = m => { const a = m.totals ? m.totals.agree : 0, d = m.totals ? m.totals.disagree : 0; return MARGIN_BUCKETS.find(b => b.test(a, d)); };
function chartMargins(ms){
  if(!ms.length) return `<p class="modal-sub">Geen stemmingen.</p>`;
  const counts = Object.fromEntries(MARGIN_BUCKETS.map(b => [b.key, 0]));
  for(const m of ms) counts[marginBucket(m).key]++;
  const W = 520, H = 200, L = 34, R = 8, T = 10, B = 40, pw = W - L - R, ph = H - T - B;
  const max = Math.max(1, ...Object.values(counts));
  const step = max > 200 ? 100 : max > 100 ? 50 : max > 40 ? 20 : 10, ymax = Math.ceil(max/step)*step;
  const bw = pw / MARGIN_BUCKETS.length, y = v => T + ph - v/ymax*ph;
  let s = svgOpen(W, H);
  for(let v = 0; v <= ymax; v += step) s += `<line class="grid" x1="${L}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}"/><text x="${L-6}" y="${y(v)+4}" text-anchor="end">${v}</text>`;
  MARGIN_BUCKETS.forEach((b, i) => {
    const v = counts[b.key], x = L + i*bw + bw*0.15, w = bw*0.7;
    s += `<rect class="bar" x="${x.toFixed(1)}" y="${y(v).toFixed(1)}" width="${w.toFixed(1)}" height="${(y(0)-y(v)).toFixed(1)}" rx="3" fill="var(--accent)"><title>${b.label}: ${v} stemmingen (${Math.round(100*v/ms.length)}%)</title></rect>
      <text class="val" x="${(x+w/2).toFixed(1)}" y="${(y(v)-4).toFixed(1)}" text-anchor="middle">${v}</text>
      <text x="${(x+w/2).toFixed(1)}" y="${H-B+16}" text-anchor="middle">${b.label.split(" ")[0]}</text>
      <text x="${(x+w/2).toFixed(1)}" y="${H-B+29}" text-anchor="middle">${esc(b.label.includes("(") ? b.label.slice(b.label.indexOf("(")) : "")}</text>`;
  });
  s += `<line class="axis" x1="${L}" x2="${W-R}" y1="${y(0)}" y2="${y(0)}"/></svg>`;
  const krap = ms.filter(m => m.totals && m.totals.agree !== m.totals.disagree && m.totals.agree && m.totals.disagree)
    .sort((a,b) => Math.abs(a.totals.agree-a.totals.disagree) - Math.abs(b.totals.agree-b.totals.disagree) || b.date.localeCompare(a.date)).slice(0,5);
  return s + `<h4 style="margin:10px 0 2px;font-size:12.5px">De 5 krapste stemmingen</h4><ul class="krap-list">${
    krap.map(m => `<li><span class="d">${m.date}</span><span>${esc(m.title)} ${docLink(m)}${srcLink(m)}</span><span class="m ${m.result==="accepted"?"r-accepted":"r-rejected"}">${m.totals.agree}–${m.totals.disagree}</span></li>`).join("")}</ul>`;
}

/* ---- Controls, filtering, table ---- */
function buildControls(types){
  $("#typeChips").innerHTML = types.map(t=>`<span class="chip on" data-type="${t}">${TYPE_LABEL[t]||t}</span>`).join("");
  $("#typeChips").onclick = e => {
    const c = e.target.closest(".chip"); if(!c) return;
    const t = c.dataset.type;
    state.types.has(t) ? state.types.delete(t) : state.types.add(t);
    c.classList.toggle("on"); render();
  };
  $("#pList").innerHTML = DATA.parties.map(p=>
    `<label><input type="checkbox" data-slug="${p.slug}" checked> ${esc(p.name)}</label>`).join("");
  $("#pList").onchange = e => {
    const s = e.target.dataset.slug;
    e.target.checked ? state.parties.add(s) : state.parties.delete(s);
    updatePartySummary(); render();
  };
  $("#pAll").onclick = ()=>{ DATA.parties.forEach(p=>state.parties.add(p.slug)); $("#pList").querySelectorAll("input").forEach(i=>i.checked=true); updatePartySummary(); render(); };
  $("#pNone").onclick = ()=>{ state.parties.clear(); $("#pList").querySelectorAll("input").forEach(i=>i.checked=false); updatePartySummary(); render(); };

  let searchTimer;
  $("#search").oninput = e => {
    state.search = e.target.value.toLowerCase().trim();
    clearTimeout(searchTimer);
    searchTimer = setTimeout(render, 150);
  };
  $("#result").onchange = e => { state.result = e.target.value; render(); };
  $("#sort").onchange = e => { state.sort = e.target.value; render(); };
  $("#controversial").onchange = e => { state.controversial = e.target.checked; render(); };
  $("#onlyPinned").onchange = e => { state.onlyPinned = e.target.checked; render(); };
  $("#raw").onchange = e => { state.raw = e.target.checked; render(); };
  $("#clusterCols").onchange = e => { state.cluster = e.target.checked; render(); };
}

function updatePartySummary(){
  const n = state.parties.size, total = DATA.parties.length;
  $("#psummary").textContent = n===total ? "Alle partijen" : (n===0 ? "Geen partijen" : `${n} van ${total} partijen`);
}

// Column order for the table. Clustered: parties that vote alike sit together (agreement over
// every stemming, same method as the Overeenkomst view); `sep` is the slug before which the two
// two least-agreeing blocks meet — in practice the coalition/opposition seam. Parties with too few
// votes for a reliable agreement keep their size order at the end.
function tableOrder(){
  if(TABLE_ORDER) return TABLE_ORDER;
  const M = computeAgreement(new Set(ALLTYPES));
  const order = seriate(M);
  // The seam: cut the seriated row into two blocks where agreement within the blocks is highest
  // relative to agreement across them (blocks of at least two parties).
  const pct = (a, b) => { const c = M[a] && M[a][b]; return c ? c.pct : null; };
  const avg = pairs => { const v = pairs.map(([a,b]) => pct(a,b)).filter(x => x !== null); return v.length ? v.reduce((s,x)=>s+x,0)/v.length : 0; };
  const within = xs => avg(xs.flatMap((a,i) => xs.slice(i+1).map(b => [a,b])));
  const scores = [];
  for(let k = 2; k <= order.length - 2; k++){
    const L = order.slice(0,k), R = order.slice(k);
    scores.push({k, score: (within(L) + within(R))/2 - avg(L.flatMap(a => R.map(b => [a,b])))});
  }
  // Only draw the line where the fracties really fall into two blocks. When the best cut barely
  // beats a cut somewhere else entirely (2023-2027: 22.6 against 21.5), the Staten are a gradient,
  // not two camps, and a line would suggest a divide that is not in the data.
  const ranked = scores.slice().sort((a,b) => b.score - a.score);
  const bestCut = ranked[0];
  const rival = ranked.find(c => bestCut && Math.abs(c.k - bestCut.k) > 1);
  const sep = bestCut && (!rival || bestCut.score - rival.score >= SEAM_MIN_LEAD) ? order[bestCut.k] : null;
  const rest = DATA.parties.map(p => p.slug).filter(s => !(s in M));
  TABLE_ORDER = {order: [...order, ...rest], sep};
  return TABLE_ORDER;
}
function visibleParties(){
  const vis = DATA.parties.filter(p=>state.parties.has(p.slug));
  if(!state.cluster) return vis;
  const {order, sep} = tableOrder();
  const rank = Object.fromEntries(order.map((s,i) => [s,i]));
  return vis.slice().sort((a,b) => (rank[a.slug] ?? 99) - (rank[b.slug] ?? 99))
            .map(p => p.slug === sep ? {...p, sep: true} : p);
}

function cellVerdict(v){ // returns {cls,label} or null for afwezig
  if(!v) return null;
  if(v.agree>v.disagree) return {cls:"voor",label:"V"};
  if(v.disagree>v.agree) return {cls:"tegen",label:"T"};
  return {cls:"neutraal",label:"O"};
}
function isControversial(m){
  let hasV=false,hasT=false;
  for(const p of visibleParties()){
    const r = cellVerdict(m.votes[p.slug]); if(!r) continue;
    if(r.label==="V") hasV=true; else if(r.label==="T") hasT=true;
    if(hasV&&hasT) return true;
  }
  return false;
}
function passes(m){
  if(!state.types.has(m.type)) return false;
  if(state.result!=="all" && m.result!==state.result) return false;
  if(state.search){
    const hay = (m.title + " " + indienersText(m) + " " + (m.indieners||[]).map(pName).join(" ")).toLowerCase();
    if(!hay.includes(state.search)) return false;
  }
  if(state.controversial && !isControversial(m)) return false;
  return true;
}
function sortRows(rows){
  const c = {
    "date-desc": (a,b)=> b.date.localeCompare(a.date) || collator.compare(a.title, b.title),
    "date-asc":  (a,b)=> a.date.localeCompare(b.date) || collator.compare(a.title, b.title),
  }[state.sort] || ((a,b)=> b.date.localeCompare(a.date));
  return rows.sort(c);
}

// A filter (not a type chip) is active: groups with hits open themselves so the hits are visible.
const filterActive = () => !!state.search || state.result !== "all" || state.controversial;

/* Rows -> [{mid, date, source, n, agendas:[{aid, nr, label, rows}]}], meetings in the chosen date
   order, agendapunten by their number ("2a" sorts after "2"), "Zonder agendapunt" last. */
function groupRows(rows){
  const asc = state.sort === "date-asc";
  const byMeeting = new Map();
  for(const m of rows){
    const mid = meetingOf(m);
    let g = byMeeting.get(mid);
    if(!g) byMeeting.set(mid, g = {mid, date: m.date, source: m.source, n: 0, ag: new Map()});
    if(m.date < g.date) g.date = m.date;
    g.n++;
    const aid = agendaIdOf(m);
    let a = g.ag.get(aid);
    if(!a) g.ag.set(aid, a = {aid, nr: m.agenda ? m.agenda.nr : "", label: agendaLabel(m), rows: []});
    a.rows.push(m);
  }
  const groups = [...byMeeting.values()].sort((a,b) =>
    (asc ? a.date.localeCompare(b.date) : b.date.localeCompare(a.date)) || a.mid - b.mid);
  for(const g of groups){
    g.agendas = [...g.ag.values()].sort((a,b) =>
      (a.aid === 0) - (b.aid === 0) || collator.compare(a.nr, b.nr) || collator.compare(a.label, b.label));
    for(const a of g.agendas) a.rows.sort((x,y) => collator.compare(x.title, y.title));
    delete g.ag;
  }
  return groups;
}

function cellHTML(m, slug, name, sep){
  const v = m.votes[slug];
  const r = cellVerdict(v);
  const sc = sep ? " sep" : "";
  if(!r) return `<td class="cell afw${sc}" title="${esc(name)}: afwezig (deed niet mee aan deze stemming)">A</td>`;
  const split = v.agree>0 && v.disagree>0;
  const disp = state.raw ? `${v.agree}-${v.disagree}` : r.label;
  const tip = `${name}: ${v.agree} voor, ${v.disagree} tegen` + (v.abstain?`, ${v.abstain} onthouden`:"") + (split?" (niet unaniem)":"");
  return `<td class="cell ${r.cls}${sc}${split&&!state.raw?" split":""}${state.raw?" raw":""}" title="${esc(tip)}">${disp}</td>`;
}
function rowHTML(m, vps){
  const pinned = state.pinned.has(m.id);
  const res = m.resultLabel ? `<span class="res r-${m.result||"tie"}">${esc(m.resultLabel)}</span>` : "";
  const live = m.live ? `<span class="badge-live" title="Live opgehaald van Notubiz — nog niet in de dagelijkse snapshot">live</span>` : "";
  const ind = indienersText(m);
  const first = `<td class="onderwerp"><div class="ond-row">
      <button class="pin${pinned?" on":""}" data-id="${m.id}" title="${pinned?"Losmaken":"Vastpinnen"}" aria-label="${pinned?"Losmaken":"Vastpinnen"}">${ICO("i-pin")}</button>
      <div><div class="titel">${esc(m.title)}${srcLink(m)}${live}</div>
      <div class="meta"><span>${m.date}</span><span class="type t-${m.type}">${TYPE_LABEL[m.type]||m.type}</span>${res}${docLink(m)}${ind?`<span class="indieners" title="Indieners">${esc(ind)}</span>`:""}</div></div>
    </div></td>`;
  return `<tr>${first}${vps.map(p=>cellHTML(m,p.slug,p.name,p.sep)).join("")}${PAD_CELL}</tr>`;
}
const PAD_CELL = `<td class="pad"></td>`;
function headHTML(vps){
  return `<thead><tr><th class="onderwerp-h">Onderwerp</th>${
    vps.map(p => {
      // Only an abbreviated header gets a tooltip (and with it the help cursor): on "PVV" the
      // tooltip would just repeat the header.
      const lbl = pLabel(p.slug);
      const tip = lbl === p.name ? "" : ` title="${esc(p.name)}"`;
      return `<th${p.sep?' class="sep"':""}${tip}>${esc(lbl)}</th>`;
    }).join("")}<th class="pad" aria-hidden="true"></th></tr></thead>`;
}
function tableHTML(rows, vps){
  if(!rows.length) return `<div class="empty">Geen stemmingen voor deze selectie.</div>`;
  return `<div class="table-scroll"><table>${headHTML(vps)}<tbody>${rows.map(m=>rowHTML(m,vps)).join("")}</tbody></table></div>`;
}

// One table, three kinds of row: vergadering, agendapunt, stemming. A collapsed group does not
// render its children, so a folded table stays small however many stemmingen it holds.
const CARET = `<span class="caret" aria-hidden="true"></span>`;
function grpRowHTML(cls, key, open, span, inner){
  return `<tr class="grp ${cls}${open?" open":""}" data-key="${esc(key)}" tabindex="0" role="button" aria-expanded="${open}">
    <td colspan="${span}"><div class="grp-row">${CARET}${inner}</div></td></tr>`;
}
function groupedHTML(groups, vps, forceOpen){
  if(!groups.length) return `<div class="empty">Geen stemmingen voor deze selectie.</div>`;
  const span = vps.length + 2;   // onderwerp + fracties + de lege opvulkolom
  let body = "", anyRows = false;
  for(const g of groups){
    const key = mKey(g.mid), open = forceOpen || state.open.has(key);
    body += grpRowHTML("grp-m", key, open, span,
      `<span class="grp-title">${esc(formatDateNL(g.date))}</span>
       <span class="grp-n">${g.n} stemming${g.n===1?"":"en"}</span>
       <span class="grp-links"><a class="meetlink" href="#vergadering/${g.mid}" title="Alles over deze vergadering">${ICO("i-chart")}Vergadering</a>${srcLink(g)}</span>`);
    if(!open) continue;
    for(const a of g.agendas){
      const akey = aKey(g.mid, a.aid), aopen = forceOpen || state.open.has(akey);
      body += grpRowHTML("grp-a", akey, aopen, span,
        `<span class="grp-title">${esc(a.label)}</span><span class="grp-n">${a.rows.length}</span>`);
      if(aopen){ body += a.rows.map(m => rowHTML(m, vps)).join(""); anyRows = true; }
    }
  }
  // With everything folded the party columns are empty, so their header would name columns that
  // show nothing; it comes back the moment a wurklistpunt is open.
  return `<div class="table-scroll"><table>${anyRows ? headHTML(vps) : ""}<tbody>${body}</tbody></table></div>`;
}

function togglePin(id){
  state.pinned.has(id) ? state.pinned.delete(id) : state.pinned.add(id);
  localStorage.setItem(PIN_KEY, JSON.stringify([...state.pinned]));
  render();
  if(window.MeetingPage) MeetingPage.refresh();
}
// Folding a vergadering also forgets its agendapunten, so reopening it starts folded again.
function toggleGroup(key){
  if(state.open.has(key)){
    state.open.delete(key);
    if(key.startsWith("m:")) for(const k of [...state.open]) if(k.startsWith(`a:${key.slice(2)}:`)) state.open.delete(k);
  }else{
    state.open.add(key);
  }
  render();
}

function render(){
  const vps = visibleParties();
  const all = DATA.moties.filter(passes);
  const pinnedRows = sortRows(DATA.moties.filter(m=>state.pinned.has(m.id)));
  const mainRows = state.onlyPinned ? [] : all.filter(m=>!state.pinned.has(m.id));
  const groups = groupRows(mainRows);

  $("#pinnedBlock").innerHTML = pinnedRows.length
    ? `<div class="tbl-title">${ICO("i-pin")} Vastgepind (${pinnedRows.length})</div>${tableHTML(pinnedRows, vps)}`
    : "";
  // Badge on the "Weergave" popover: how many view toggles are active.
  const vb = document.querySelector("summary.viewbtn");
  if(vb) vb.dataset.n = [state.controversial, state.onlyPinned, state.raw].filter(Boolean).length;
  $("#mainBlock").innerHTML = state.onlyPinned
    ? (pinnedRows.length?"":`<div class="empty">Nog niets vastgepind.</div>`)
    : groupedHTML(groups, vps, filterActive());

  const shown = (state.onlyPinned?pinnedRows.length:mainRows.length+pinnedRows.length);
  const nm = groups.length;
  $("#count").textContent = `${shown} van ${DATA.moties.length} stemmingen · ${nm} vergadering${nm===1?"":"en"} · ${vps.length} partijen`;
}

// Split a Frisian title into number, indieners-in-title and subject for the CSV.
function splitTitle(title){
  title = title || "";
  let m = title.match(/^((?:Moasje|Amendemint|Motie|Amendement)\s*(?:frjemd|fremd)?)\s*\(?([\dA-Z-]+)?\)?\s*(?:\(([^)]*)\))?\s*:?\s*(.*)$/i);
  if(m) return {code: m[1].trim(), nr: m[2] || "", subject: m[4].trim()};
  return {code: "", nr: "", subject: title};
}

// Download the currently filtered/sorted stemmingen as CSV — one column per metadata field and one
// per party. Every party always gets a cell (empty if afwezig) so V/T never shift columns.
function exportCSV(){
  const vps = DATA.parties;   // every party as a column, regardless of show/hide
  const base = DATA.moties.filter(passes);
  const rows = sortRows((state.onlyPinned ? base.filter(m => state.pinned.has(m.id)) : base).slice());
  const q = s => { s = (s==null ? "" : String(s)); return /[",\n\r]/.test(s) ? `"${s.replace(/"/g,'""')}"` : s; };
  const cellVal = v => {
    const r = cellVerdict(v);
    if(!r) return "";
    if(state.raw) return `${v.agree}-${v.disagree}`;
    return r.label;
  };
  const header = ["Datum","VergaderingId","Agendapunt","Type","Code","Nr.","Onderwerp","Indieners","Uitslag","Voor","Tegen","Document","Bron", ...vps.map(p => p.name)];
  const lines = [header.map(q).join(",")];
  for(const m of rows){
    const t = splitTitle(m.title);
    lines.push([m.date, meetingOf(m) || "", m.agenda ? `${m.agenda.nr} ${m.agenda.title}` : "",
                TYPE_LABEL[m.type]||m.type, t.code, t.nr, t.subject, (m.indieners||[]).map(pName).join("; "), m.resultLabel||"",
                m.totals ? m.totals.agree : "", m.totals ? m.totals.disagree : "", m.document||"", m.source||"",
                ...vps.map(p => cellVal(m.votes[p.slug]))].map(q).join(","));
  }
  const blob = new Blob(["﻿" + lines.join("\r\n")], {type:"text/csv;charset=utf-8"});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `wa-hat-wat-stimd_fryslan_${DATA.meta.generated_at.slice(0,10)}.csv`;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

/* ---- Live top-up from api.notubiz.nl ------------------------------------------------------------
   The daily snapshot can lag (Notubiz blocks GitHub's cloud runners). api.notubiz.nl allows
   cross-origin reads, so the browser asks it for plenary meetings held after the snapshot, fetches
   their votings and aggregates the per-member votes to fracties with data/roles.json. Rows found
   this way are badged "live". The portal page (which names members) is never fetched here. */
const apiUrl = (path, params) => `${NOTUBIZ_API}/${path}?${new URLSearchParams({...params, format:"json", version: API_VERSION})}`;
const fetchJSON = async url => { const r = await fetch(url); if(!r.ok) throw new Error(`${r.status} ${url}`); return r.json(); };

// JS ports of the collector's classification, so live rows are typed exactly like snapshot rows.
function liveClassify(title, votingType){
  // A "Moasje frjemd" is filed by the API as a plain motion (sometimes even as a proposal); the
  // title is the only reliable signal, so it is checked first. Mirrors collect.notubiz_classify.
  if(/^\s*(?:\d+[a-z]?\s+)?(?:moasje|moasie|motie)\s*(?:frjemd|fremd)\b/i.test(title||"")) return "frjemd";
  const vt = (votingType||"").toLowerCase();
  if(vt === "motion") return "motie";
  if(vt === "amendment") return "amendement";
  if(vt === "council_proposal" || vt === "initiative_proposal") return "besluit";
  const low = (title||"").replace(/\s+/g," ").trim().toLowerCase();
  if(low.includes("ordevoorstel") || low.includes("oarderfoarstel")) return "ordevoorstel";
  if(low.includes("amendement") || low.includes("amendemint")) return "amendement";
  if(low.includes("motie") || low.includes("moasje") || low.includes("moasie")) return "motie";
  if(low.includes("statenvoorstel") || low.includes("besluit") || low.includes("voordracht") || low.includes("voarstel")) return "besluit";
  return "overig";
}
function liveResult(s){
  s = (s||"").toLowerCase();
  if(s === "adopted" || s === "accepted") return ["accepted","Aangenomen"];
  if(s === "rejected") return ["rejected","Verworpen"];
  if(["equal","tie","tied","staken"].includes(s)) return ["tie","Staken van stemmen"];
  return [null, null];
}
const normText = s => (s||"").normalize("NFKD").replace(/[̀-ͯ]/g,"").toLowerCase().replace(/[^a-z0-9 ]+/g," ");
const titleTokens = s => new Set(normText(s).split(" ").filter(t => t.length > 2));
function titleNumber(title){
  const m = (title||"").replace(/^\s*\d+\s+/,"").match(/^\s*(?:moasje|moasie|amendemint|motie|amendement)\s*(?:frjemd|fremd)?\s*\(?(?:\d+-[MA]-)?0*(\d+)\)?/i);
  return m ? m[1] : null;
}
const slugify = name => name.toLowerCase().replace(/[^a-z0-9\s-]/g,"").trim().replace(/\s+/g,"-");
const LIVE_ALIASES = {"Partij voor de Dieren":"PvdD", "FVD":"Van Dijk (FvD)", "Steatelid Van Dijk":"Van Dijk (FvD)"};
const LIVE_SKIP = new Set(["Geen partij","Gedeputeerde Staten"]);
const partySlug = name => { name = LIVE_ALIASES[name] || name; return LIVE_SKIP.has(name) ? null : slugify(name); };
const attr = (item, id) => { const a = (item.attributes||[]).find(x => x.id === id); return a ? a.values.map(v => v.content) : []; };

function matchModuleItem(title, type, candidates){
  const typeOk = c => (type === "motie" || type === "frjemd") ? /^(moasje|motie)/.test(c.type) : type === "amendement" ? /^amendem/.test(c.type) : false;
  let cands = candidates.filter(typeOk); if(!cands.length) cands = candidates.slice();
  if(type === "frjemd"){ const fr = cands.filter(c => /frjemd|fremd/.test(c.type)); if(fr.length) cands = fr; }
  if(!cands.length) return null;
  const n = titleNumber(title);
  if(n){
    const byN = cands.filter(c => c.number === n || titleNumber(c.title) === n);
    if(byN.length === 1) return byN[0];
    if(byN.length) cands = byN;
  }
  const want = titleTokens(title);
  const scored = cands.map(c => [[...want].filter(t => titleTokens(c.title).has(t)).length, c]).sort((a,b) => b[0]-a[0]);
  if(scored.length && scored[0][0] >= 2 && (scored.length === 1 || scored[0][0] > scored[1][0])) return scored[0][1];
  return null;
}

/* {agenda item id: {id, nr, title}} of one meeting — the votings' parent.id points at these.
   Port of collect.notubiz_meeting_detail; a failure only costs the grouping of those rows. */
async function fetchAgenda(mid){
  const data = await fetchJSON(apiUrl(`events/meetings/${mid}`, {})).catch(() => null);
  const out = {};
  (function walk(items){
    for(const it of items || []){
      const td = it.type_data || {};
      const nr = String(td.title_prefix || "").trim();
      const a = (td.attributes || []).find(x => x.id === 1 && x.value);
      const title = a ? String(a.value).replace(/\s+/g, " ").trim() : "";
      if(nr && title && it.id) out[it.id] = {id: it.id, nr, title};
      walk(it.agenda_items);
    }
  })(((data || {}).meeting || {}).agenda_items);
  return out;
}

async function liveTopUp(){
  const meta = DATA.meta;
  if(!meta.organisationId || !meta.gremiumId) return;
  const known = new Set(DATA.moties.map(m => m.source));
  const lastDate = DATA.moties.map(m => m.date).sort().pop() || meta.term.slice(0,4) + "-01-01";
  const from = new Date(Date.parse(lastDate) + 86400e3).toISOString().slice(0,10);
  const today = new Date().toISOString().slice(0,10);
  if(from > today) return;
  const ev = await fetchJSON(apiUrl("events", {organisation_id: meta.organisationId, date_from: `${from} 00:00:00`, date_to: `${today} 23:59:59`, page: 1}));
  const meetings = (ev.events||[])
    .filter(e => (e.gremium||{}).id === meta.gremiumId && (e.event_type_data||{}).agenda_item_count)
    .map(e => ({id: e.id, date: ((e.plannings||[{}])[0].start_date||"").slice(0,10)}))
    .filter(e => e.id && /^\d{4}-\d{2}-\d{2}$/.test(e.date) && e.date <= today && !known.has(`${meta.source}/vergadering/${e.id}`))
    .sort((a,b) => a.date.localeCompare(b.date)).slice(-LIVE_MAX_MEETINGS);
  if(!meetings.length) return;
  ROLES = ROLES || await fetchJSON(ROLES_URL).catch(() => ({roles:{}}));
  const roles = ROLES.roles || {};
  const rows = [];
  const seen = new Set(DATA.moties.map(m => m.id));
  for(const mt of meetings){
    mt.agenda = await fetchAgenda(mt.id);
    const vd = await fetchJSON(apiUrl("agenda_items/votings", {meeting_id: mt.id})).catch(() => null);
    for(const v of (vd && vd.votings) || []){
      const td = v.type_data || {}, votesIn = td.votes || [];
      if(!votesIn.length || seen.has(v.id)) continue;
      const [result, resultLabel] = liveResult(td.voting_result);
      if(!result) continue;   // withdrawn / not voted on
      const votes = {}; let unknown = 0;
      for(const x of votesIn){
        if(x.vote === "absent") continue;
        const slug = roles[String(x.role_id)];
        if(!slug){ unknown++; continue; }
        const c = votes[slug] || (votes[slug] = {agree:0, disagree:0, abstain:0});
        if(x.vote === "in_favor") c.agree++; else if(x.vote === "against") c.disagree++; else c.abstain++;
      }
      if(!Object.keys(votes).length) continue;
      const title = (td.title||"").trim();
      rows.push({id: v.id, date: mt.date, meetingId: mt.id, title, type: liveClassify(title, td.voting_type), result, resultLabel,
        source: `${meta.source}/vergadering/${mt.id}`, votes, agenda: mt.agenda ? mt.agenda[(v.parent||{}).id] : undefined,
        agendaItem: (v.parent||{}).id,
        totals: {agree: Object.values(votes).reduce((s,c)=>s+c.agree,0), disagree: Object.values(votes).reduce((s,c)=>s+c.disagree,0)},
        live: true, unknownVotes: unknown});
    }
  }
  if(!rows.length) return;
  // Documents + indieners: the module list is large (~3.5 MB), so only fetched when there is something new.
  try{
    const [mod, parties] = await Promise.all([
      fetchJSON(apiUrl(`modules/${meta.moduleId || 6}/items`, {organisation_id: meta.organisationId})),
      fetchJSON(apiUrl(`organisations/${meta.organisationId}/parties`, {}))]);
    const names = Object.fromEntries((parties.parties||[]).map(p => [p.id, p.name]));
    const byAgenda = {}, byDate = {};
    for(const it of mod.items||[]){
      const doc = (attr(it, 2).find(d => d && d.document) || {}).document;
      const rec = {title: attr(it,1)[0]||"", type: ((attr(it,45)[0]||"")+"").trim().toLowerCase(), date: (attr(it,15)[0]||"").slice(0,10),
        number: String(attr(it,26)[0]||"").replace(/^0+/,""), parties: attr(it,37).filter(x => typeof x === "number"),
        document: doc && doc.id ? {id: doc.id, title: doc.title || attr(it,1)[0] || ""} : null};
      for(const ag of attr(it,54)) if(typeof ag === "number") (byAgenda[ag] = byAgenda[ag] || []).push(rec);
      if(rec.date) (byDate[rec.date] = byDate[rec.date] || []).push(rec);
    }
    for(const m of rows){
      if(m.type !== "motie" && m.type !== "frjemd" && m.type !== "amendement") continue;
      const rec = matchModuleItem(m.title, m.type, byAgenda[m.agendaItem]||[]) || matchModuleItem(m.title, m.type, byDate[m.date]||[]);
      if(!rec) continue;
      if(rec.document){
        m.document = `${meta.source}/document/${rec.document.id}/1/${encodeURIComponent((rec.document.title||"document").trim().replace(/\s+/g,"+")).replace(/%2B/g,"+")}`;
        m.documentTitle = rec.document.title;
      }
      const ind = []; for(const pid of rec.parties){ const s = partySlug(names[pid]||""); if(s && !ind.includes(s)) ind.push(s); }
      if(ind.length) m.indieners = ind;
    }
  }catch(e){ console.warn("module items niet geladen:", e); }
  DATA.moties.push(...rows);
  let newType = false;
  for(const t of new Set(rows.map(r => r.type))) if(!ALLTYPES.includes(t)){ ALLTYPES.push(t); state.types.add(t); newType = true; }
  if(newType) ALLTYPES = sortTypes(ALLTYPES);
  AG = ORDER = TABLE_ORDER = null;
  const unknown = rows.reduce((s,r) => s + (r.unknownVotes||0), 0);
  $("#liveNote").hidden = false;
  $("#liveNote").innerHTML = `● <b>${rows.length} stemming${rows.length===1?"":"en"} live opgehaald</b> van Notubiz (${meetings.length} vergadering${meetings.length===1?"":"en"} na ${esc(lastDate)}) — nog niet in de dagelijkse snapshot.`
    + (unknown ? ` ${unknown} individuele stem${unknown===1?"":"men"} van nog onbekende leden ${unknown===1?"is":"zijn"} niet meegeteld.` : "");
  if(newType) buildControls(ALLTYPES);   // a type unseen in the snapshot needs its filter chip
  if(SMEETINGS) buildMeetingPicker();    // new vergaderingen join the stats filter switched on
  render();
  if(window.MeetingPage) MeetingPage.refresh();
}

init().catch(e => { document.querySelector(".wrap").innerHTML = `<div class="empty">Kon data niet laden: ${esc(""+e)}<br><small>Draai lokaal met een server (zie README).</small></div>`; });
