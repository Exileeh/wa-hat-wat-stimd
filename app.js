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
  pvv:"PVV", ja21:"JA21", "provinciaal-belang-frysln":"PBF", pvdd:"PvdD", sp:"SP", d66:"D66", fvd:"FvD",
  "steatelid-van-dijk":"Van Dijk", "steatelid-jonker":"Jonker"};
const TYPE_LABEL = {motie:"Motie", amendement:"Amendement", besluit:"Besluit", ordevoorstel:"Ordevoorstel", overig:"Overig"};
const TYPE_PLURAL = {motie:"moties", amendement:"amendementen", besluit:"besluiten", ordevoorstel:"ordevoorstellen", overig:"overige"};
// Frisian document label per type (the portal module is "Moasjes en amendeminten").
const DOC_LABEL = {motie:"Moasje", amendement:"Amendemint"};
// Min. stemmingen a party must have voted on to appear in the Overeenkomst matrix — below this an
// agreement % is noise (a party that voted once is "100% gelijk" with everyone).
const MATRIX_MIN = 5;
// Below this many *shared* stemmingen a pair's agreement % is too noisy to colour confidently.
const MATRIX_PAIR_MIN = 10;

let DATA, ROLES, state, AG = null, ORDER = null, ALLTYPES = null, MTYPES = null, PTYPES = null, CTYPES = null, STYPES = null;
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

async function init(){
  DATA = await (await fetch(DATA_URL)).json();
  ALLTYPES = (DATA.meta.types && DATA.meta.types.length) ? DATA.meta.types.slice() : [...new Set(DATA.moties.map(m => m.type))];
  applyTheme(DATA.meta.style || {});
  state = {
    types: new Set(ALLTYPES),
    parties: new Set(DATA.parties.map(p => p.slug)),
    search: "", result: "all", controversial: false, onlyPinned: false, raw: false,
    sort: "date-desc",
    pinned: new Set(JSON.parse(localStorage.getItem(PIN_KEY) || "[]")),
  };
  renderHeader();
  setupGlobalHandlers();
  buildControls(ALLTYPES);
  updatePartySummary();
  render();
  liveTopUp().catch(e => console.warn("live bijladen mislukt:", e));
}

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
  $("#matrixBtn").onclick = () => {
    if(!MTYPES) MTYPES = new Set(ALLTYPES);
    typeChips($("#matrixTypes"), MTYPES, refreshMatrix);
    refreshMatrix();
    $("#matrixModal").hidden = false;
  };
  $("#profileBtn").onclick = openProfile;
  $("#compareBtn").onclick = openCompare;
  $("#statsBtn").onclick = openStats;
  $("#helpBtn").onclick = () => $("#helpModal").hidden = false;
  $("#legendBtn").onclick = () => $("#legendModal").hidden = false;
  $("#csvBtn").onclick = exportCSV;
  document.querySelectorAll(".modal").forEach(mo => mo.addEventListener("click", e => { if(e.target === mo) mo.hidden = true; }));
  document.querySelectorAll("[data-close]").forEach(btn => btn.onclick = () => { document.getElementById(btn.dataset.close).hidden = true; });
  // Pin toggle via event delegation — one listener instead of one per row.
  $(".wrap").addEventListener("click", e => {
    const b = e.target.closest("button.pin");
    if(!b) return;
    const id = +b.dataset.id;
    state.pinned.has(id) ? state.pinned.delete(id) : state.pinned.add(id);
    localStorage.setItem(PIN_KEY, JSON.stringify([...state.pinned]));
    render();
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
function refreshMatrix(){ AG = computeAgreement(MTYPES); ORDER = clusterOrder(); renderMatrix(); }

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
function clusterOrder(){
  const slugs = Object.keys(AG);
  if(slugs.length < 2) return slugs;
  const dist = (a,b) => { const c = AG[a] && AG[a][b]; return c ? 100 - c.pct : 100; };
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
  $("#profileModal").hidden = false;
}
function profileStats(slug, types){
  let voor=0, tegen=0, onth=0, afw=0, win=0, decided=0;
  const lone = [];
  for(const m of DATA.moties){
    if(!types.has(m.type)) continue;
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
  $("#compareModal").hidden = false;
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
  renderStats();
  $("#statsModal").hidden = false;
}
const svgOpen = (w, h) => `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="grafiek" preserveAspectRatio="xMidYMid meet">`;
const fmtMonth = ym => { const [y, m] = ym.split("-"); return `${["jan","feb","mrt","apr","mei","jun","jul","aug","sep","okt","nov","dec"][+m-1]} ${y}`; };
const legend = items => `<div class="legend-row">${items.map(([c, l]) => `<span><span class="sw" style="background:${c}"></span>${l}</span>`).join("")}</div>`;
const RES_COLOR = {accepted:"var(--c-aangenomen)", rejected:"var(--c-verworpen)", tie:"var(--c-staken)"};
const RES_LABEL = {accepted:"aangenomen", rejected:"verworpen", tie:"staken van stemmen"};
const resKey = m => m.result === "accepted" || m.result === "rejected" ? m.result : "tie";

function renderStats(){
  const ms = DATA.moties.filter(m => STYPES.has(m.type));
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
  $("#chartMonths").innerHTML = chartMonths(ms);
  $("#chartIndieners").innerHTML = chartIndieners(ms);
  $("#chartWinning").innerHTML = chartWinning();
  $("#chartMargins").innerHTML = chartMargins(ms);
}

// 1. Stacked bars per month: aangenomen / verworpen / staken, over the whole term.
function chartMonths(ms){
  if(!ms.length) return `<p class="modal-sub">Geen stemmingen.</p>`;
  const months = [];
  const first = ms.map(m => m.date).sort()[0].slice(0,7), last = new Date().toISOString().slice(0,7);
  for(let y = +first.slice(0,4), mo = +first.slice(5,7); `${y}-${String(mo).padStart(2,"0")}` <= last; ){
    months.push(`${y}-${String(mo).padStart(2,"0")}`); if(++mo > 12){ mo = 1; y++; }
  }
  const agg = Object.fromEntries(months.map(k => [k, {accepted:0, rejected:0, tie:0}]));
  for(const m of ms){ const k = m.date.slice(0,7); if(agg[k]) agg[k][resKey(m)]++; }
  const W = 520, H = 220, L = 34, R = 8, T = 10, B = 34, pw = W - L - R, ph = H - T - B;
  const max = Math.max(1, ...months.map(k => agg[k].accepted + agg[k].rejected + agg[k].tie));
  const step = max > 60 ? 20 : max > 30 ? 10 : 5, ymax = Math.ceil(max/step)*step;
  const bw = pw / months.length, y = v => T + ph - v/ymax*ph;
  let s = svgOpen(W, H);
  for(let v = 0; v <= ymax; v += step) s += `<line class="grid" x1="${L}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}"/><text x="${L-6}" y="${y(v)+4}" text-anchor="end">${v}</text>`;
  months.forEach((k, i) => {
    const a = agg[k]; let base = 0; const x = L + i*bw + 1, w = Math.max(1, bw - 2);
    for(const key of ["accepted","rejected","tie"]){
      const v = a[key]; if(!v) continue;
      const y1 = y(base + v), h = y(base) - y1;
      s += `<rect class="bar" x="${x.toFixed(1)}" y="${y1.toFixed(1)}" width="${w.toFixed(1)}" height="${h.toFixed(1)}" fill="${RES_COLOR[key]}"${base===0?` rx="2"`:""}><title>${fmtMonth(k)}: ${v} ${RES_LABEL[key]} (totaal ${a.accepted+a.rejected+a.tie})</title></rect>`;
      base += v;
    }
    if(k.endsWith("-01") || k.endsWith("-07")) s += `<text x="${(x + w/2).toFixed(1)}" y="${H-B+16}" text-anchor="middle">${fmtMonth(k)}</text>`;
  });
  s += `<line class="axis" x1="${L}" x2="${W-R}" y1="${y(0)}" y2="${y(0)}"/></svg>`;
  return s + legend([[RES_COLOR.accepted,"aangenomen"],[RES_COLOR.rejected,"verworpen"],[RES_COLOR.tie,"staken van stemmen"]]);
}

// 2. Indieners: per fractie the moties/amendementen it (co-)submitted, split by outcome.
function chartIndieners(ms){
  const rows = {};
  let withInd = 0, eligible = 0;
  for(const m of ms){
    if(m.type !== "motie" && m.type !== "amendement") continue;
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
function chartWinning(){
  const list = DATA.parties.map(p => ({slug: p.slug, ...profileStats(p.slug, STYPES)}))
    .filter(r => r.decided >= 5).sort((a,b) => b.winPct - a.winPct || b.decided - a.decided);
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
  return s + `<p class="chart-sub" style="margin-top:6px">Aandeel van de aangenomen/verworpen stemmingen waarin de fractie met de uitslag meestemde; tussen haakjes het aantal. Fracties met minder dan 5 stemmingen zijn weggelaten.</p>`;
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
}

function updatePartySummary(){
  const n = state.parties.size, total = DATA.parties.length;
  $("#psummary").textContent = n===total ? "Alle partijen" : (n===0 ? "Geen partijen" : `${n} van ${total} partijen`);
}

function visibleParties(){ return DATA.parties.filter(p=>state.parties.has(p.slug)); }

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
    "date-desc": (a,b)=> b.date.localeCompare(a.date) || a.title.localeCompare(b.title),
    "date-asc":  (a,b)=> a.date.localeCompare(b.date) || a.title.localeCompare(b.title),
    "result":    (a,b)=> (a.result||"").localeCompare(b.result||"") || b.date.localeCompare(a.date),
  }[state.sort];
  return rows.sort(c);
}

function cellHTML(m, slug, name){
  const v = m.votes[slug];
  const r = cellVerdict(v);
  if(!r) return `<td class="cell afw" title="${esc(name)}: afwezig"></td>`;
  const split = v.agree>0 && v.disagree>0;
  const disp = state.raw ? `${v.agree}-${v.disagree}` : r.label;
  const tip = `${name}: ${v.agree} voor, ${v.disagree} tegen` + (v.abstain?`, ${v.abstain} onthouden`:"") + (split?" (niet unaniem)":"");
  return `<td class="cell ${r.cls}${split&&!state.raw?" split":""}${state.raw?" raw":""}" title="${esc(tip)}">${disp}</td>`;
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
  return `<tr>${first}${vps.map(p=>cellHTML(m,p.slug,p.name)).join("")}</tr>`;
}
function tableHTML(rows, vps){
  if(!rows.length) return `<div class="empty">Geen stemmingen voor deze selectie.</div>`;
  const head = `<thead><tr><th class="onderwerp-h">Onderwerp</th>${
    vps.map(p=>`<th title="${esc(p.name)}">${esc(pLabel(p.slug))}</th>`).join("")}</tr></thead>`;
  return `<div class="table-scroll"><table>${head}<tbody>${rows.map(m=>rowHTML(m,vps)).join("")}</tbody></table></div>`;
}

function render(){
  const vps = visibleParties();
  const all = DATA.moties.filter(passes);
  const pinnedRows = sortRows(DATA.moties.filter(m=>state.pinned.has(m.id)));
  const mainRows = state.onlyPinned ? [] : sortRows(all.filter(m=>!state.pinned.has(m.id)));

  $("#pinnedBlock").innerHTML = pinnedRows.length
    ? `<div class="tbl-title">${ICO("i-pin")} Vastgepind (${pinnedRows.length})</div>${tableHTML(pinnedRows, vps)}`
    : "";
  // Badge on the "Weergave" popover: how many view toggles are active.
  const vb = document.querySelector("summary.viewbtn");
  if(vb) vb.dataset.n = [state.controversial, state.onlyPinned, state.raw].filter(Boolean).length;
  $("#mainBlock").innerHTML = state.onlyPinned
    ? (pinnedRows.length?"":`<div class="empty">Nog niets vastgepind.</div>`)
    : tableHTML(mainRows, vps);

  const shown = (state.onlyPinned?pinnedRows.length:mainRows.length+pinnedRows.length);
  $("#count").textContent = `${shown} van ${DATA.moties.length} stemmingen · ${vps.length} partijen`;
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
  const header = ["Datum","Type","Code","Nr.","Onderwerp","Indieners","Uitslag","Voor","Tegen","Document","Bron", ...vps.map(p => p.name)];
  const lines = [header.map(q).join(",")];
  for(const m of rows){
    const t = splitTitle(m.title);
    lines.push([m.date, TYPE_LABEL[m.type]||m.type, t.code, t.nr, t.subject, (m.indieners||[]).map(pName).join("; "), m.resultLabel||"",
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
const LIVE_ALIASES = {"Partij voor de Dieren":"PvdD"};
const LIVE_SKIP = new Set(["Geen partij","Gedeputeerde Staten"]);
const partySlug = name => { name = LIVE_ALIASES[name] || name; return LIVE_SKIP.has(name) ? null : slugify(name); };
const attr = (item, id) => { const a = (item.attributes||[]).find(x => x.id === id); return a ? a.values.map(v => v.content) : []; };

function matchModuleItem(title, type, candidates){
  const typeOk = c => type === "motie" ? /^(moasje|motie)/.test(c.type) : type === "amendement" ? /^amendem/.test(c.type) : false;
  let cands = candidates.filter(typeOk); if(!cands.length) cands = candidates.slice();
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
      rows.push({id: v.id, date: mt.date, title, type: liveClassify(title, td.voting_type), result, resultLabel,
        source: `${meta.source}/vergadering/${mt.id}`, votes, agendaItem: (v.parent||{}).id,
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
      if(m.type !== "motie" && m.type !== "amendement") continue;
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
  AG = ORDER = null;
  const unknown = rows.reduce((s,r) => s + (r.unknownVotes||0), 0);
  $("#liveNote").hidden = false;
  $("#liveNote").innerHTML = `● <b>${rows.length} stemming${rows.length===1?"":"en"} live opgehaald</b> van Notubiz (${meetings.length} vergadering${meetings.length===1?"":"en"} na ${esc(lastDate)}) — nog niet in de dagelijkse snapshot.`
    + (unknown ? ` ${unknown} individuele stem${unknown===1?"":"men"} van nog onbekende leden ${unknown===1?"is":"zijn"} niet meegeteld.` : "");
  if(newType) buildControls(ALLTYPES);   // a type unseen in the snapshot needs its filter chip
  render();
}

init().catch(e => { document.querySelector(".wrap").innerHTML = `<div class="empty">Kon data niet laden: ${esc(""+e)}<br><small>Draai lokaal met een server (zie README).</small></div>`; });
