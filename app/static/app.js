"use strict";

/* FinApp frontend. Alle berekeningen gebeuren hier of in de lokale server. */

const S = {
  data: null,
  tab: "overview",
  period: "12",
  txFilter: { q: "", cat: "", source: "", flow: "", fixedOnly: false, limit: 300 },
  applyToMerchant: true,
  showInactive: false,
};

const EUR = new Intl.NumberFormat("nl-NL", { style: "currency", currency: "EUR" });
const EUR0 = new Intl.NumberFormat("nl-NL", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
const MONTHS = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"];

const $ = (sel, el = document) => el.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const eur = (cents, round) => (round ? EUR0 : EUR).format((cents || 0) / 100);
const fmtDate = (iso) => { if (!iso) return ""; const [y, m, d] = iso.split("-"); return `${+d} ${MONTHS[+m - 1]} ${y}`; };
const monthKey = (iso) => iso.slice(0, 7);
const monthLabel = (k) => { const [y, m] = k.split("-"); return `${MONTHS[+m - 1]} '${y.slice(2)}`; };

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove("show"), 2600);
}

async function api(path, body, headers = {}) {
  const opt = body === undefined ? {} : {
    method: "POST",
    headers: Object.assign({ "X-FinApp": "1" }, body instanceof Blob ? {} : { "Content-Type": "application/json" }, headers),
    body: body instanceof Blob ? body : JSON.stringify(body),
  };
  const r = await fetch(path, opt);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || "Er ging iets mis");
  return j;
}

async function reload() {
  S.data = await api("/api/data");
  buildPeriodSelect();
  render();
}

/* ------------------------------------------------------------ periode */

function addMonths(key, n) {
  let [y, m] = key.split("-").map(Number);
  m += n;
  while (m < 1) { m += 12; y--; }
  while (m > 12) { m -= 12; y++; }
  return `${y}-${String(m).padStart(2, "0")}`;
}

function monthsBetween(a, b) {
  const out = [];
  for (let k = a; k <= b; k = addMonths(k, 1)) out.push(k);
  return out;
}

function buildPeriodSelect() {
  const sel = $("#period");
  const d = S.data;
  const opts = [["3", "Laatste 3 maanden"], ["6", "Laatste 6 maanden"], ["12", "Laatste 12 maanden"], ["24", "Laatste 24 maanden"], ["all", "Alles"]];
  if (d.end_date) {
    const years = new Set(d.transactions.map((t) => t.date.slice(0, 4)));
    [...years].sort().reverse().forEach((y) => opts.push(["y" + y, "Jaar " + y]));
  }
  sel.innerHTML = opts.map(([v, l]) => `<option value="${v}">${l}</option>`).join("");
  if (!opts.some((o) => o[0] === S.period)) S.period = "12";
  sel.value = S.period;
}

/* Bepaalt welke maanden meetellen. De lopende (onvolledige) laatste maand telt
   niet mee in gemiddelden, anders drukt hij het maandgemiddelde. */
function periodRange() {
  const d = S.data;
  if (!d.end_date) return null;
  const allTx = d.transactions;
  const firstKey = monthKey(allTx[allTx.length - 1].date);
  const end = d.end_date;
  const endKey = monthKey(end);
  const lastDay = new Date(+end.slice(0, 4), +end.slice(5, 7), 0).getDate();
  const endComplete = +end.slice(8, 10) >= lastDay - 2;
  const lastFull = endComplete ? endKey : addMonths(endKey, -1);
  let from, to;
  if (S.period.startsWith("y")) {
    const y = S.period.slice(1);
    from = `${y}-01`; to = `${y}-12` < lastFull ? `${y}-12` : lastFull;
  } else if (S.period === "all") {
    from = firstKey; to = lastFull;
  } else {
    to = lastFull; from = addMonths(to, -(+S.period) + 1);
    if (from < firstKey) from = firstKey;
  }
  if (to < from) { to = endKey; from = endKey; }
  return { from, to, months: monthsBetween(from, to), endKey, partialExcluded: !endComplete };
}

function inRange(t, r) { const k = monthKey(t.date); return k >= r.from && k <= r.to; }

/* ------------------------------------------------------------ helpers */

function catMeta() {
  const m = {};
  S.data.categories.forEach((c) => (m[c.name] = c));
  return m;
}

function coverageText() {
  const s = S.data.sources;
  const parts = [];
  if (s.bank) parts.push(`Bank ${fmtDate(s.bank.from)} t/m ${fmtDate(s.bank.to)}`);
  if (s.amex) parts.push(`Amex ${fmtDate(s.amex.from)} t/m ${fmtDate(s.amex.to)}`);
  return parts.join(" · ") || "Nog geen gegevens geïmporteerd";
}

function coverageWarnings(r) {
  const s = S.data.sources, w = [];
  if (!s.bank || !s.amex) {
    if (s.bank && !s.amex) w.push("Er zijn nog geen Amex-transacties geïmporteerd; creditcarduitgaven ontbreken.");
    if (s.amex && !s.bank) w.push("Er zijn nog geen banktransacties geïmporteerd.");
    return w;
  }
  const f = r.from, t = r.to;
  for (const [name, src] of [["Amex", s.amex], ["Bank", s.bank]]) {
    if (monthKey(src.from) > f) w.push(`${name}-gegevens beginnen pas op ${fmtDate(src.from)}; maanden daarvoor zijn onvolledig.`);
    if (monthKey(src.to) < t) w.push(`${name}-gegevens lopen tot ${fmtDate(src.to)}; latere maanden zijn onvolledig.`);
  }
  return w;
}

/* ------------------------------------------------------------ render */

function render() {
  $("#coverage").textContent = coverageText();
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === S.tab));
  document.querySelectorAll(".tab").forEach((s) => s.classList.toggle("active", s.id === "tab-" + S.tab));
  const empty = !S.data.transactions.length;
  $("#period").disabled = empty;
  if (empty && !["import", "settings"].includes(S.tab)) {
    $("#tab-" + S.tab).innerHTML = `<div class="panel empty"><strong>Nog geen transacties</strong>
      Importeer eerst je exports van de bank en American Express.<br><br>
      <button class="primary" data-goto="import">Naar importeren</button></div>`;
    return;
  }
  ({ overview: renderOverview, trends: renderTrends, projects: renderProjects, networth: renderNetworth, fixed: renderFixed, tx: renderTx, import: renderImport, settings: renderSettings })[S.tab]();
}

/* ---------- Overzicht */

function renderOverview() {
  const r = periodRange();
  const meta = catMeta();
  const nMonths = r.months.length;
  const inPeriod = S.data.transactions.filter((t) => inRange(t, r));
  const txs = inPeriod.filter((t) => !t.excluded);
  const excl = inPeriod.filter((t) => t.excluded && t.kind !== "transfer");

  const monthly = {};
  r.months.forEach((k) => (monthly[k] = { fixed: 0, var: 0, income: 0 }));
  const byCat = {};
  let exp = 0, inc = 0;
  for (const t of txs) {
    const m = monthly[monthKey(t.date)];
    if (t.kind === "expense") {
      const v = -t.amount;
      exp += v;
      if (t.group) m.fixed += v; else m.var += v;
      const c = (byCat[t.category] = byCat[t.category] || { total: 0, fixed: 0 });
      c.total += v;
      if (t.group) c.fixed += v;
    } else if (t.kind === "income") {
      inc += t.amount;
      m.income += t.amount;
    }
  }
  const active = S.data.recurring.filter((x) => x.active);
  const fixedNow = active.reduce((a, x) => a + x.monthly, 0);
  const avgExp = exp / nMonths, avgInc = inc / nMonths;

  const warns = coverageWarnings(r);
  const periodTxt = `${monthLabel(r.from)} t/m ${monthLabel(r.to)} (${nMonths} ${nMonths === 1 ? "maand" : "maanden"})` +
    (r.partialExcluded ? `, lopende maand ${monthLabel(r.endKey)} niet meegeteld` : "");

  const cats = Object.entries(byCat).filter(([, v]) => v.total > 0).sort((a, b) => b[1].total - a[1].total);
  const maxCat = cats.length ? cats[0][1].total : 1;

  $("#tab-overview").innerHTML = `
    ${warns.map((w) => `<div class="notice">${esc(w)}</div>`).join("")}
    ${excl.length ? `<div class="notice info">${excl.length} ${excl.length === 1 ? "post" : "posten"} (${eur(-excl.reduce((a, t) => a + t.amount, 0))}) uitgesloten van deze cijfers.
      <button class="link small" data-showexcluded="1">Bekijken</button></div>` : ""}
    <div class="kpis">
      <div class="kpi accent"><div class="l">Vaste lasten per maand</div><div class="v">${eur(fixedNow, 1)}</div>
        <div class="h">${active.length} actieve posten, ${eur(active.reduce((a, x) => a + x.yearly, 0), 1)} per jaar</div></div>
      <div class="kpi"><div class="l">Gem. uitgaven per maand</div><div class="v">${eur(avgExp, 1)}</div>
        <div class="h">${eur(avgExp * 12, 1)} per jaar, excl. overboekingen</div></div>
      <div class="kpi"><div class="l">Gem. inkomsten per maand</div><div class="v">${eur(avgInc, 1)}</div>
        <div class="h">${eur(avgInc * 12, 1)} per jaar</div></div>
      <div class="kpi"><div class="l">Gem. overschot per maand</div><div class="v ${avgInc - avgExp < 0 ? "neg" : ""}">${eur(avgInc - avgExp, 1)}</div>
        <div class="h">${eur((avgInc - avgExp) * 12, 1)} per jaar</div></div>
    </div>
    <div class="grid2">
      <div class="panel">
        <h2>Uitgaven per maand</h2>
        <div class="legend"><span><i style="background:var(--fixed)"></i>Vaste lasten</span><span><i style="background:var(--var)"></i>Variabel</span></div>
        ${monthChart(r.months, monthly)}
        <p class="muted" style="font-size:12px;margin:8px 0 0">${esc(periodTxt)}</p>
        ${yearTable()}
      </div>
      <div class="panel">
        <h2>Per categorie <span class="muted" style="font-weight:400;font-size:12.5px">gemiddeld</span></h2>
        <div class="catlist">
          <div class="catrow cathdr"><div></div><div></div><div class="catval">per maand</div><div class="catval">per jaar</div></div>
          ${cats.map(([name, v]) => {
            const col = (meta[name] || {}).color || "#999";
            const wT = (v.total / maxCat) * 100, wF = (v.fixed / maxCat) * 100;
            return `<div class="catrow" data-cat="${esc(name)}" title="${esc(name)}: ${eur(v.total / nMonths)} per maand, waarvan ${eur(v.fixed / nMonths)} vast">
              <div class="catname"><span class="dot" style="background:${col}"></span>${esc(name)}</div>
              <div class="cattrack"><span style="width:${wF}%;background:${col}"></span><span style="width:${wT - wF}%;background:${col};opacity:.45"></span></div>
              <div class="catval num">${eur(v.total / nMonths, 1)}</div>
              <div class="catval num muted">${eur((v.total / nMonths) * 12, 1)}</div></div>`;
          }).join("") || '<p class="muted">Geen uitgaven in deze periode.</p>'}
        </div>
        <p class="muted" style="font-size:12px;margin:12px 0 0">Donker deel = vaste lasten. Klik op een categorie voor de transacties.</p>
      </div>
    </div>`;
}

/* Totalen per kalenderjaar (alle geïmporteerde gegevens, zonder de lopende
   maand en zonder uitgesloten posten). */
function yearTable() {
  const d = S.data;
  if (!d.end_date) return "";
  const end = d.end_date;
  const lastDay = new Date(+end.slice(0, 4), +end.slice(5, 7), 0).getDate();
  const lastFull = +end.slice(8, 10) >= lastDay - 2 ? monthKey(end) : addMonths(monthKey(end), -1);
  const yrs = {};
  for (const t of d.transactions) {
    const mk = monthKey(t.date);
    if (mk > lastFull || t.excluded) continue;
    const y = (yrs[t.date.slice(0, 4)] = yrs[t.date.slice(0, 4)] || { fixed: 0, var: 0, inc: 0, months: new Set() });
    y.months.add(mk);
    if (t.kind === "expense") { if (t.group) y.fixed -= t.amount; else y.var -= t.amount; }
    else if (t.kind === "income") y.inc += t.amount;
  }
  const rows = Object.keys(yrs).sort().reverse();
  if (!rows.length) return "";
  return `<h3 style="margin-top:22px">Per kalenderjaar</h3>
    <table class="years">
      <tr><th>Jaar</th><th class="num">Vaste lasten</th><th class="num">Variabel</th><th class="num">Uitgaven</th><th class="num">Inkomsten</th><th class="num">Overschot</th></tr>
      ${rows.map((k) => {
        const y = yrs[k], n = y.months.size, exp = y.fixed + y.var;
        const partial = n < 12 ? ` <span class="muted" style="font-size:12px">(${n} mnd)</span>` : "";
        return `<tr><td>${k}${partial}</td><td class="num">${eur(y.fixed, 1)}</td><td class="num">${eur(y.var, 1)}</td>
          <td class="num"><strong>${eur(exp, 1)}</strong></td><td class="num">${eur(y.inc, 1)}</td>
          <td class="num ${y.inc - exp < 0 ? "neg" : "pos"}">${eur(y.inc - exp, 1)}</td></tr>`;
      }).join("")}
    </table>
    <p class="muted" style="font-size:12px;margin:6px 0 0">Werkelijke totalen; onvolledige jaren tellen alleen de maanden met gegevens.</p>`;
}

function monthChart(months, data) {
  const W = 640, H = 240, pl = 52, pb = 26, pt = 10, pr = 8;
  const vals = months.map((k) => data[k].fixed + data[k].var);
  const max = Math.max(1, ...vals);
  const step = niceStep(max / 4);
  const top = Math.ceil(max / step) * step;
  const cw = (W - pl - pr) / months.length;
  const bw = Math.max(3, Math.min(34, cw * 0.66));
  const y = (v) => pt + (H - pt - pb) * (1 - v / top);
  let s = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Uitgaven per maand">`;
  for (let v = 0; v <= top; v += step) {
    s += `<line class="gridline" x1="${pl}" x2="${W - pr}" y1="${y(v)}" y2="${y(v)}"/>`;
    s += `<text x="${pl - 6}" y="${y(v) + 4}" text-anchor="end">${esc(EUR0.format(v / 100))}</text>`;
  }
  const every = Math.ceil(months.length / 12);
  months.forEach((k, i) => {
    const x = pl + cw * i + (cw - bw) / 2;
    const f = data[k].fixed, v = data[k].var;
    s += `<g class="hover" data-month="${k}"><title>${monthLabel(k)}: ${eur(f + v)} (vast ${eur(f)}, variabel ${eur(v)})</title>`;
    s += `<rect class="bar-fixed" x="${x}" y="${y(f)}" width="${bw}" height="${Math.max(0, y(0) - y(f))}" rx="2"/>`;
    s += `<rect class="bar-var" x="${x}" y="${y(f + v)}" width="${bw}" height="${Math.max(0, y(f) - y(f + v))}" rx="2"/></g>`;
    if (i % every === 0) s += `<text x="${x + bw / 2}" y="${H - 8}" text-anchor="middle">${monthLabel(k)}</text>`;
  });
  return s + "</svg>";
}

function niceStep(raw) {
  const p = Math.pow(10, Math.floor(Math.log10(Math.max(raw, 1))));
  for (const m of [1, 2, 2.5, 5, 10]) if (raw <= m * p) return m * p;
  return 10 * p;
}

/* ---------- Trends */

/* Som per maand van transacties die aan f voldoen (uitgaven positief). */
function monthSums(months, f, sign = -1) {
  const out = {};
  months.forEach((k) => (out[k] = 0));
  for (const t of S.data.transactions) {
    if (t.excluded) continue;
    const k = monthKey(t.date);
    if (k in out && f(t)) out[k] += sign * t.amount;
  }
  return out;
}

function axisScale(max) {
  const step = niceStep(Math.max(max, 1) / 4);
  return { step, top: Math.ceil(Math.max(max, 1) / step) * step };
}

/* Staafgrafiek met 1 of 2 series naast elkaar, optioneel een gemiddeldelijn. */
function barChart(months, series, opts = {}) {
  const W = opts.w || 640, H = opts.h || 230, pl = 56, pb = 26, pt = 12, pr = opts.avg != null ? 58 : 8;
  const max = Math.max(1, ...series.flatMap((s) => months.map((k) => s.data[k])));
  const { step, top } = axisScale(max);
  const y = (v) => pt + (H - pt - pb) * (1 - Math.max(0, v) / top);
  const cw = (W - pl - pr) / months.length;
  const gap = 2, n = series.length;
  const bw = Math.max(3, Math.min(n > 1 ? 16 : 30, (cw * 0.72 - gap * (n - 1)) / n));
  let s = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${esc(opts.label || "")}">`;
  for (let v = 0; v <= top; v += step) {
    s += `<line class="gridline" x1="${pl}" x2="${W - pr}" y1="${y(v)}" y2="${y(v)}"/>`;
    s += `<text x="${pl - 6}" y="${y(v) + 4}" text-anchor="end">${esc(EUR0.format(v / 100))}</text>`;
  }
  const every = Math.ceil(months.length / 12);
  months.forEach((k, i) => {
    const x0 = pl + cw * i + (cw - (bw * n + gap * (n - 1))) / 2;
    const tip = opts.tip ? opts.tip(k) : `${monthLabel(k)}: ` + series.map((se) => `${se.name} ${eur(se.data[k])}`).join(", ");
    s += `<g class="hover"><title>${esc(tip)}</title>`;
    s += `<rect x="${pl + cw * i}" y="${pt}" width="${cw}" height="${H - pt - pb}" fill="transparent"/>`;
    series.forEach((se, j) => {
      const v = se.data[k], x = x0 + j * (bw + gap);
      const h = Math.max(0, y(0) - y(v));
      if (h > 0) s += `<path class="${se.cls}"${se.color ? ` style="fill:${se.color}"` : ""} d="${roundTop(x, y(v), bw, h)}"/>`;
    });
    s += `</g>`;
    if (i % every === 0) s += `<text x="${pl + cw * i + cw / 2}" y="${H - 8}" text-anchor="middle">${monthLabel(k)}</text>`;
  });
  if (opts.avg != null) {
    s += `<line class="avgline" x1="${pl}" x2="${W - pr}" y1="${y(opts.avg)}" y2="${y(opts.avg)}"/>`;
    s += `<text class="avglabel" x="${W - pr + 6}" y="${y(opts.avg) - 2}">gem.</text>`;
    s += `<text class="avglabel" x="${W - pr + 6}" y="${y(opts.avg) + 11}">${esc(EUR0.format(opts.avg / 100))}</text>`;
  }
  return s + "</svg>";
}

/* Staaf met afgeronde bovenhoeken (4px), vlak op de basislijn. */
function roundTop(x, y, w, h) {
  const r = Math.min(4, w / 2, h);
  return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
}

function renderTrends() {
  const r = periodRange();
  const months = r.months, n = months.length;
  const meta = catMeta();

  // 1. Inkomsten tegenover uitgaven
  const inc = monthSums(months, (t) => t.kind === "income", 1);
  const exp = monthSums(months, (t) => t.kind === "expense");
  const totInc = months.reduce((a, k) => a + inc[k], 0), totExp = months.reduce((a, k) => a + exp[k], 0);
  const rate = totInc > 0 ? Math.round(((totInc - totExp) / totInc) * 100) : 0;

  // 2. Categorie door de tijd
  const expenseCats = S.data.categories.filter((c) => c.kind === "expense").map((c) => c.name);
  const totals = {};
  for (const t of S.data.transactions)
    if (!t.excluded && t.kind === "expense" && months.includes(monthKey(t.date))) totals[t.category] = (totals[t.category] || 0) - t.amount;
  const ranked = expenseCats.filter((c) => totals[c] > 0).sort((a, b) => totals[b] - totals[a]);
  if (!S.trendCat || !ranked.includes(S.trendCat)) S.trendCat = ranked.find((c) => c !== "Wonen") || ranked[0];
  const cat = S.trendCat;
  const catData = cat ? monthSums(months, (t) => t.category === cat && t.kind === "expense") : {};
  const catAvg = cat ? months.reduce((a, k) => a + catData[k], 0) / n : 0;
  const col = (meta[cat] || {}).color || "#888";

  // 3. Vergelijking met dezelfde periode een jaar eerder
  const prev = months.map((k) => addMonths(k, -12));
  const prevSet = new Set(prev), curSet = new Set(months);
  const cmp = {};
  for (const t of S.data.transactions) {
    if (t.excluded || t.kind !== "expense") continue;
    const k = monthKey(t.date);
    const side = curSet.has(k) ? "cur" : prevSet.has(k) ? "prev" : null;
    if (!side) continue;
    const c = (cmp[t.category] = cmp[t.category] || { cur: 0, prev: 0 });
    c[side] -= t.amount;
  }
  const src = S.data.sources;
  const covered = (s) => !s || monthKey(s.from) <= prev[0];
  const prevWarn = [];
  if (!covered(src.bank)) prevWarn.push(`bank vanaf ${fmtDate(src.bank.from)}`);
  if (!covered(src.amex)) prevWarn.push(`Amex vanaf ${fmtDate(src.amex.from)}`);
  const rows = Object.entries(cmp).map(([c, v]) => ({ c, ...v, d: v.cur - v.prev }))
    .filter((x) => Math.abs(x.d) >= 100).sort((a, b) => Math.abs(b.d) - Math.abs(a.d)).slice(0, 12);
  const maxD = Math.max(1, ...rows.map((x) => Math.abs(x.d)));
  const sumCur = Object.values(cmp).reduce((a, v) => a + v.cur, 0), sumPrev = Object.values(cmp).reduce((a, v) => a + v.prev, 0);
  const pct = (a, b) => (b > 0 ? `${a >= b ? "+" : ""}${Math.round(((a - b) / b) * 100)}%` : "nieuw");

  $("#tab-trends").innerHTML = `
    <div class="panel">
      <div class="row" style="justify-content:space-between;align-items:baseline">
        <h2 style="margin:0">Inkomsten en uitgaven</h2>
        <span class="muted" style="font-size:13px">${monthLabel(r.from)} t/m ${monthLabel(r.to)}</span>
      </div>
      <div class="kpis" style="grid-template-columns:repeat(4,1fr);margin:14px 0 10px">
        <div class="kpi"><div class="l">Inkomsten</div><div class="v" style="font-size:20px">${eur(totInc, 1)}</div></div>
        <div class="kpi"><div class="l">Uitgaven</div><div class="v" style="font-size:20px">${eur(totExp, 1)}</div></div>
        <div class="kpi"><div class="l">Overschot</div><div class="v ${totInc - totExp < 0 ? "neg" : ""}" style="font-size:20px">${eur(totInc - totExp, 1)}</div></div>
        <div class="kpi"><div class="l">Spaarpercentage</div><div class="v" style="font-size:20px">${rate}%</div><div class="h">overschot als deel van inkomsten</div></div>
      </div>
      <div class="legend"><span><i class="sw-inc"></i>Inkomsten</span><span><i class="sw-exp"></i>Uitgaven</span></div>
      ${barChart(months, [{ name: "inkomsten", data: inc, cls: "bar-inc" }, { name: "uitgaven", data: exp, cls: "bar-exp" }], {
        label: "Inkomsten en uitgaven per maand", w: 1120, h: 280,
        tip: (k) => `${monthLabel(k)}: inkomsten ${eur(inc[k])}, uitgaven ${eur(exp[k])}, overschot ${eur(inc[k] - exp[k])}` +
          (inc[k] > 0 ? ` (${Math.round(((inc[k] - exp[k]) / inc[k]) * 100)}%)` : ""),
      })}
      <p class="muted" style="font-size:12px;margin:8px 0 0">Beweeg over een maand voor het overschot. Uitgesloten posten (auto, schenkingen) tellen niet mee.</p>
    </div>

    <div class="grid2">
      <div class="panel">
        <div class="row" style="justify-content:space-between">
          <h2 style="margin:0">Categorie door de tijd</h2>
          <select id="trend-cat">${ranked.map((c) => `<option ${c === cat ? "selected" : ""}>${esc(c)}</option>`).join("")}</select>
        </div>
        <p class="muted" style="font-size:12.5px;margin:6px 0 10px">${cat ? `Gemiddeld ${eur(catAvg, 1)} per maand, ${eur(catAvg * 12, 1)} per jaar` : ""}</p>
        ${cat ? barChart(months, [{ name: cat, data: catData, cls: "bar-cat", color: col }], { label: cat + " per maand", avg: catAvg, h: 210 }) : ""}
        <p style="margin:8px 0 0"><button class="link small" data-cat="${esc(cat || "")}">Transacties bekijken</button></p>
      </div>

      <div class="panel">
        <h2>Vergeleken met een jaar eerder</h2>
        <p class="muted" style="font-size:12.5px;margin:-4px 0 10px">${monthLabel(r.from)} t/m ${monthLabel(r.to)} tegenover ${monthLabel(prev[0])} t/m ${monthLabel(prev[prev.length - 1])}.
          Totaal ${eur(sumCur, 1)} tegenover ${eur(sumPrev, 1)} (${pct(sumCur, sumPrev)}).</p>
        ${prevWarn.length ? `<div class="notice">De vergelijkingsperiode is onvolledig (${esc(prevWarn.join(", "))}); verschillen kunnen vertekend zijn.</div>` : ""}
        <div class="legend"><span><i class="sw-exp"></i>Meer uitgegeven</span><span><i class="sw-inc"></i>Minder uitgegeven</span></div>
        <table class="cmp">
          <tr><th>Categorie</th><th class="num">Jaar eerder</th><th class="num">Nu</th><th style="width:34%">Verschil</th></tr>
          ${rows.map((x) => {
            const w = (Math.abs(x.d) / maxD) * 50;
            const bar = x.d >= 0
              ? `<span class="dbar up" style="left:50%;width:${w}%"></span>`
              : `<span class="dbar down" style="left:${50 - w}%;width:${w}%"></span>`;
            return `<tr class="catlink" data-cat="${esc(x.c)}" title="${esc(x.c)}: ${eur(x.prev)} → ${eur(x.cur)}">
              <td><span class="dot" style="background:${(meta[x.c] || {}).color || "#999"}"></span>${esc(x.c)}</td>
              <td class="num muted">${eur(x.prev, 1)}</td><td class="num">${eur(x.cur, 1)}</td>
              <td><div class="dtrack"><span class="dmid"></span>${bar}</div>
                <div class="dval ${x.d >= 0 ? "up" : "down"}">${x.d >= 0 ? "+" : "−"}${eur(Math.abs(x.d), 1).replace("-", "")} · ${pct(x.cur, x.prev)}</div></td></tr>`;
          }).join("") || '<tr><td colspan="4" class="muted">Geen noemenswaardige verschillen.</td></tr>'}
        </table>
      </div>
    </div>
    ${yearReview()}`;
}


/* ---------- Labels (projecten en reizen) */

function labelMap() {
  const m = {};
  (S.data.labels || []).forEach((l) => (m[l.id] = l));
  return m;
}

function labelChips(t) {
  const m = labelMap();
  return (t.labels || []).filter((id) => m[id]).map((id) =>
    `<span class="tag label" style="--lc:${m[id].color}" data-labelfilter="${id}" title="Toon alle transacties met dit label">${esc(m[id].name)}</span>`).join("");
}

/* Netto kosten van een label: uitgaven min terugbetalingen, overboekingen
   en inkomsten tellen niet mee. Uitgesloten posten tellen hier wel mee. */
function labelStats(id) {
  const txs = S.data.transactions.filter((t) => (t.labels || []).includes(id));
  const cost = txs.filter((t) => t.kind === "expense").reduce((a, t) => a - t.amount, 0);
  const refunds = txs.filter((t) => t.kind === "income" && t.category === "Terugbetalingen (Tikkie e.d.)").reduce((a, t) => a + t.amount, 0);
  const byCat = {};
  txs.filter((t) => t.kind === "expense").forEach((t) => (byCat[t.category] = (byCat[t.category] || 0) - t.amount));
  const dates = txs.map((t) => t.date).sort();
  return { txs, cost, refunds, net: cost - refunds, byCat, from: dates[0], to: dates[dates.length - 1] };
}

function renderProjects() {
  const labels = S.data.labels || [];
  const meta = catMeta();
  const vacs = S.data.vacations || [];
  const cards = labels.map((l) => ({ l, s: labelStats(l.id) })).sort((a, b) => (b.s.to || "").localeCompare(a.s.to || ""));
  $("#tab-projects").innerHTML = `
    <div class="grid2">
      <div>
        ${cards.length ? cards.map(({ l, s }) => {
          const cats = Object.entries(s.byCat).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]);
          const tot = cats.reduce((a, [, v]) => a + v, 0) || 1;
          return `<div class="panel project">
            <div class="row" style="justify-content:space-between;align-items:baseline">
              <h2 style="margin:0"><span class="dot" style="background:${l.color}"></span>${esc(l.name)}</h2>
              <div class="v num" style="font-size:20px;font-weight:650">${eur(s.net, 1)}</div>
            </div>
            <p class="muted" style="font-size:12.5px;margin:4px 0 10px">${s.txs.length} transacties${s.from ? ` · ${fmtDate(s.from)} t/m ${fmtDate(s.to)}` : ""}${s.refunds ? ` · ${eur(s.refunds)} terugontvangen` : ""}</p>
            ${cats.length ? `<div class="stackbar">${cats.map(([c, v]) => `<span style="width:${(v / tot) * 100}%;background:${(meta[c] || {}).color || "#999"}" title="${esc(c)}: ${eur(v)}"></span>`).join("")}</div>
            <div class="stacklegend">${cats.slice(0, 6).map(([c, v]) => `<span><i style="background:${(meta[c] || {}).color || "#999"}"></i>${esc(c)} ${eur(v, 1)}</span>`).join("")}</div>` : '<p class="muted">Nog geen uitgaven met dit label.</p>'}
            <div class="row" style="margin-top:10px;gap:14px">
              <button class="link small" data-labelfilter="${l.id}">Transacties bekijken</button>
              <button class="link small" data-renamelabel="${l.id}">Hernoemen</button>
              <button class="link small" data-dellabel="${l.id}">Verwijderen</button>
            </div>
          </div>`;
        }).join("") : `<div class="panel empty"><strong>Nog geen labels</strong>Maak rechts een label aan, bijvoorbeeld voor een reis of de auto.</div>`}
      </div>
      <div>
        <div class="panel">
          <h2>Nieuw label</h2>
          <div class="row">
            <input type="text" id="l-name" placeholder="Bijv. Zuid-Afrika 2026" style="flex:1;min-width:160px">
            <button class="primary" data-addlabel="1">Aanmaken</button>
          </div>
          ${vacs.length ? `<label class="muted" style="font-size:12.5px;display:block;margin-top:10px">Meteen vullen met de betalingen ter plaatse uit een vakantieperiode (optioneel)</label>
          <select id="l-vac" style="margin-top:4px"><option value="">Geen</option>${vacs.map((v) => `<option value="${esc(v.name)}">${esc(v.name)} (${fmtDate(v.start)} t/m ${fmtDate(v.end)})</option>`).join("")}</select>` : ""}
        </div>
        <div class="panel">
          <h2>Zo werkt het</h2>
          <ol class="steps">
            <li>Maak een label aan voor een reis of project.</li>
            <li>Ga naar <em>Transacties</em>, zoek bijvoorbeeld op "riksja" of kies <em>Alles</em> als periode, vink de transacties aan en kies <em>Label toekennen</em>.</li>
            <li>Een transactie kan meerdere labels hebben, en een label staat los van de categorie.</li>
          </ol>
          <p class="muted" style="font-size:12.5px">Het totaal is uitgaven min terugbetalingen (zoals Tikkies). Uitgesloten posten tellen hier wel mee, zodat bijvoorbeeld een label "Auto" ook de aankoop bevat.</p>
        </div>
      </div>
    </div>`;
}

/* ---------- Vermogen */

function valueAt(valuations, day) {
  let v = null;
  for (const x of valuations) if (x.date <= day) v = x.value;
  return v;
}

function monthEnd(k) {
  const [y, m] = k.split("-").map(Number);
  return `${k}-${String(new Date(y, m, 0).getDate()).padStart(2, "0")}`;
}

function renderNetworth() {
  const nw = S.data.networth || { accounts: [], assets: [] };
  const today = new Date().toISOString().slice(0, 10);
  const accts = nw.accounts || [], assets = nw.assets || [];
  const mbal = (S.data.mortgage || {}).monthly_balance || {};
  const hasMort = Object.keys(mbal).length > 0;
  // maandreeks: vanaf het eerste bekende punt
  const starts = [...accts.map((a) => Object.keys(a.monthly)[0]), ...assets.filter((a) => a.valuations.length).map((a) => a.valuations[0].date.slice(0, 7))].filter(Boolean).sort();
  const firstAll = [...accts.map((a) => Object.keys(a.monthly)[0]), ...(hasMort ? [Object.keys(mbal).sort()[0]] : []), ...assets.filter((a) => a.valuations.length).map((a) => a.valuations[0].date.slice(0, 7))].filter(Boolean).sort().pop();
  const months = starts.length ? monthsBetween(firstAll, today.slice(0, 7)) : [];
  const series = months.map((k) => {
    const day = k === today.slice(0, 7) ? today : monthEnd(k);
    let assetsSum = 0, debt = 0;
    accts.forEach((a) => (assetsSum += a.monthly[k] || 0));
    if (hasMort) debt += mbal[k] || 0;
    assets.forEach((a) => {
      const v = valueAt(a.valuations, day);
      if (v == null) return;
      if (a.side === "schuld") debt += v; else assetsSum += v;
    });
    return { k, assetsSum, debt, net: assetsSum - debt };
  });
  const last = series[series.length - 1];
  const yearAgo = series.find((s) => s.k === addMonths(today.slice(0, 7), -12));
  const nowRows = [
    ...accts.map((a) => ({ name: "Betaalrekening " + a.account.slice(-4), side: "bezit", value: a.monthly[today.slice(0, 7)] ?? Object.values(a.monthly).pop(), date: a.anchor_date, auto: true })),
    ...(hasMort ? [{ name: "Hypotheek (berekend)", side: "schuld", value: mbal[today.slice(0, 7)] ?? Object.values(mbal).pop(), date: today, auto: true }] : []),
    ...assets.map((a) => ({ id: a.id, name: a.name, side: a.side, value: valueAt(a.valuations, today), date: (a.valuations[a.valuations.length - 1] || {}).date, vals: a.valuations })),
  ];
  const needBalances = !accts.length && S.data.sources.bank;

  $("#tab-networth").innerHTML = `
    ${needBalances ? `<div class="notice">Het saldo van je betaalrekening is nog niet bekend. Importeer je laatste CAMT.053-bestand van Van Lanschot nog een keer (tabblad Importeren); dubbele transacties worden overgeslagen, maar het eindsaldo wordt dan opgeslagen.</div>` : ""}
    <div class="kpis" style="grid-template-columns:repeat(3,1fr)">
      <div class="kpi accent"><div class="l">Netto vermogen</div><div class="v">${last ? eur(last.net, 1) : "–"}</div>
        <div class="h">${yearAgo && last ? `${last.net - yearAgo.net >= 0 ? "+" : "−"}${eur(Math.abs(last.net - yearAgo.net), 1)} t.o.v. een jaar geleden` : "bezittingen min schulden"}</div></div>
      <div class="kpi"><div class="l">Bezittingen</div><div class="v">${last ? eur(last.assetsSum, 1) : "–"}</div></div>
      <div class="kpi"><div class="l">Schulden</div><div class="v">${last ? eur(last.debt, 1) : "–"}</div></div>
    </div>
    <div class="grid2">
      <div class="panel">
        <h2>Netto vermogen per maand</h2>
        ${series.length > 1 ? lineChart(series) : `<p class="muted">${assets.length
          ? `Er is nog maar één meetpunt. Voer bij <em>bijwerken</em> ook een eerdere waarde in (bijvoorbeeld per 1 januari) voor elke post, dan verschijnt hier het verloop.`
          : "Voeg bezittingen en schulden toe om het verloop te zien."}</p>`}
        <p class="muted" style="font-size:12px;margin:8px 0 0">Tussen twee waarderingen geldt steeds de laatst ingevoerde waarde. De grafiek begint bij de maand waarin alle posten een waarde hebben.
          Het betaalrekeningsaldo is teruggerekend vanaf het laatste eindsaldo in je bankexport.</p>
      </div>
      <div>
        <div class="panel">
          <h2>Bezittingen en schulden</h2>
          <table class="nw">
            <tr><th>Post</th><th class="num">Waarde</th><th>Bijgewerkt</th><th></th></tr>
            ${nowRows.map((r) => `<tr>
              <td>${esc(r.name)} <span class="tag ${r.side === "schuld" ? "warn" : ""}">${r.side}</span>${r.auto ? '<span class="tag">automatisch</span>' : ""}</td>
              <td class="num">${r.value != null ? (r.side === "schuld" ? "−" : "") + eur(r.value, 1) : "–"}</td>
              <td class="muted" style="font-size:12.5px">${r.date ? fmtDate(r.date) : ""}</td>
              <td class="num">${r.auto ? "" : `<button class="link small" data-editasset="${r.id}">bijwerken</button>`}</td></tr>
              ${!r.auto && S.editAsset === r.id ? `<tr class="editrow"><td colspan="4">
                <div class="row">
                  <input type="text" id="a-val" placeholder="Waarde, bijv. 125.000" style="width:150px">
                  <input type="date" id="a-date" value="${today}">
                  <button class="primary" data-savevalue="${r.id}">Opslaan</button>
                  <button class="link small" data-delasset="${r.id}">post verwijderen</button>
                </div>
                ${r.vals.length ? `<div class="muted" style="font-size:12px;margin-top:8px">Eerdere waarden: ${r.vals.slice().reverse().map((v) =>
                  `${fmtDate(v.date)} ${eur(v.value, 1)} <button class="link small" data-delvalue="${r.id}" data-date="${v.date}" title="Verwijderen">×</button>`).join(" · ")}</div>` : ""}
              </td></tr>` : ""}`).join("")}
          </table>
        </div>
        <div class="panel">
          <h2>Post toevoegen</h2>
          <div class="row">
            <input type="text" id="n-name" placeholder="Bijv. Evi beleggingen" style="flex:1;min-width:150px">
            <select id="n-side"><option value="bezit">Bezit</option><option value="schuld">Schuld</option></select>
          </div>
          <div class="row" style="margin-top:8px">
            <input type="text" id="n-val" placeholder="Huidige waarde" style="width:150px">
            <input type="date" id="n-date" value="${today}">
            <button class="primary" data-addasset="1">Toevoegen</button>
          </div>
          <p class="muted" style="font-size:12.5px;margin-bottom:0">Bijvoorbeeld: spaarrekening en Evi-rekening (bezit), de woning tegen de WOZ- of taxatiewaarde (bezit). De hypotheek voer je hieronder in per leningdeel.
            Oudere waarden kun je ook invoeren met een eerdere datum, dan loopt de grafiek verder terug.</p>
        </div>
      </div>
    </div>
    ${mortgagePanel()}`;
}


/* ---------- Hypotheek */

const KIND_LABEL = { annuitair: "Annuïtair", lineair: "Lineair", aflossingsvrij: "Aflossingsvrij" };
const pctFmt = (r) => String(r).replace(".", ",") + "%";

function mortgagePanel() {
  const m = S.data.mortgage || { parts: [] };
  const st = S.data.settings || {};
  const parts = m.parts || [];
  const today = new Date().toISOString().slice(0, 10);
  const tot = (f) => parts.reduce((a, p) => a + (p[f] || 0), 0);
  const edit = S.editPart ? parts.find((p) => p.id === S.editPart) : null;
  const form = (p) => `
    <div class="mform">
      <input type="text" id="m-name" placeholder="Naam, bijv. Leningdeel 1" value="${esc(p ? p.name : "")}">
      <input type="text" id="m-principal" placeholder="Hoofdsom, bijv. 250.000" value="${p ? (p.principal / 100).toLocaleString("nl-NL") : ""}">
      <input type="text" id="m-rate" placeholder="Rente %, bijv. 3,85" value="${p ? String(p.rate).replace(".", ",") : ""}">
      <input type="text" id="m-years" placeholder="Looptijd (jaren)" value="${p ? p.term_months / 12 : "30"}">
      <label class="muted" style="font-size:12px">Ingangsdatum <input type="date" id="m-start" value="${p ? p.start : ""}"></label>
      <select id="m-kind">${Object.entries(KIND_LABEL).map(([k, l]) => `<option value="${k}" ${p && p.kind === k ? "selected" : ""}>${l}</option>`).join("")}</select>
      <button class="primary" data-savepart="${p ? p.id : "new"}">${p ? "Opslaan" : "Leningdeel toevoegen"}</button>
      ${p ? `<button class="link small" data-canceledit="1">annuleren</button>` : ""}
    </div>`;

  return `<div class="panel">
    <div class="row" style="justify-content:space-between;align-items:baseline">
      <h2 style="margin:0">Hypotheek</h2>
      ${parts.length ? `<span class="muted" style="font-size:13px">restschuld nu <strong style="color:var(--ink)">${eur(tot("balance_now"), 1)}</strong></span>` : ""}
    </div>
    ${parts.length ? `
    <div class="kpis" style="grid-template-columns:repeat(4,1fr);margin:14px 0">
      <div class="kpi"><div class="l">Maandlast (bruto)</div><div class="v" style="font-size:20px">${eur(tot("payment_now"), 1)}</div><div class="h">deze maand</div></div>
      <div class="kpi"><div class="l">Waarvan rente</div><div class="v" style="font-size:20px">${eur(tot("interest_now"), 1)}</div><div class="h">${eur(tot("interest_year"), 1)} dit jaar</div></div>
      <div class="kpi"><div class="l">Waarvan aflossing</div><div class="v" style="font-size:20px">${eur(tot("repayment_now"), 1)}</div><div class="h">${eur(tot("repayment_year"), 1)} dit jaar</div></div>
      <div class="kpi"><div class="l">Oorspronkelijk</div><div class="v" style="font-size:20px">${eur(tot("principal"), 1)}</div><div class="h">${eur(tot("principal") - tot("balance_now"), 1)} afgelost</div></div>
    </div>
    <table class="parts">
      <tr><th>Leningdeel</th><th>Vorm</th><th class="num">Rente</th><th class="num">Hoofdsom</th><th class="num">Restschuld</th><th>Looptijd</th><th></th></tr>
      ${parts.map((p) => `<tr>
        <td><strong>${esc(p.name)}</strong></td><td>${KIND_LABEL[p.kind]}</td>
        <td class="num">${pctFmt(p.rate_now)}</td><td class="num">${eur(p.principal, 1)}</td><td class="num">${eur(p.balance_now ?? p.principal, 1)}</td>
        <td class="muted" style="font-size:12.5px">${fmtDate(p.start)} t/m ${p.end_month ? monthLabel(p.end_month) : "–"}</td>
        <td class="num"><button class="link small" data-partdetail="${p.id}">${S.partDetail === p.id ? "sluiten" : "details"}</button></td></tr>
        ${S.partDetail === p.id ? `<tr class="editrow"><td colspan="7">
          <div class="grid2" style="gap:18px">
            <div>
              <h3 style="margin-top:4px">Renteherzieningen</h3>
              ${p.rates.length ? p.rates.map((r) => `<div>${fmtDate(r.date)}: ${pctFmt(r.rate)} <button class="link small" data-delrate="${p.id}" data-date="${r.date}">×</button></div>`).join("") : '<p class="muted" style="font-size:12.5px;margin:0">Nog geen; de rente is sinds de start ' + pctFmt(p.rate) + '.</p>'}
              <div class="row" style="margin-top:8px"><input type="date" id="r-date-${p.id}" aria-label="Ingangsdatum nieuwe rente">
                <input type="text" id="r-rate-${p.id}" placeholder="Nieuwe rente %" style="width:120px"><button data-addrate="${p.id}">Toevoegen</button></div>
            </div>
            <div>
              <h3 style="margin-top:4px">Correcties restschuld</h3>
              ${p.corrections.length ? p.corrections.map((c) => `<div>${fmtDate(c.date)}: ${eur(c.balance, 1)} <button class="link small" data-delcorr="${p.id}" data-date="${c.date}">×</button></div>`).join("") : '<p class="muted" style="font-size:12.5px;margin:0">Bijvoorbeeld de restschuld uit het jaaroverzicht, of na een extra aflossing.</p>'}
              <div class="row" style="margin-top:8px"><input type="date" id="c-date-${p.id}" value="${today}" aria-label="Datum">
                <input type="text" id="c-bal-${p.id}" placeholder="Restschuld" style="width:120px"><button data-addcorr="${p.id}">Toevoegen</button></div>
            </div>
          </div>
          <div class="row" style="margin-top:12px;gap:16px">
            <button class="link small" data-editpart="${p.id}">Gegevens wijzigen</button>
            <button class="link small" data-delpart="${p.id}">Leningdeel verwijderen</button>
          </div>
        </td></tr>` : ""}`).join("")}
    </table>` : `<p class="muted" style="font-size:13px">Voer je hypotheek in per leningdeel. De restschuld wordt per maand berekend en telt mee als schuld in je vermogen.</p>`}
    <h3>${edit ? "Leningdeel wijzigen" : "Leningdeel toevoegen"}</h3>
    ${form(edit)}
    ${parts.length ? `<h3>Maandtermijn splitsen</h3>
    <label style="display:flex;gap:8px;align-items:flex-start;font-size:13px">
      <input type="checkbox" id="m-split" ${st.mortgage_split ? "checked" : ""} style="margin-top:3px">
      <span>Splits de hypotheekbetaling op je rekening in rente (blijft een uitgave onder <em>Wonen</em>) en aflossing (vermogensopbouw, telt niet mee als uitgave).
      Herkend aan de tekst <input type="text" id="m-match" value="${esc(st.mortgage_match || "HYPOTHE")}" style="width:110px;padding:2px 6px"> in de omschrijving.
      <button class="link small" data-savemsettings="1">opslaan</button></span>
    </label>` : ""}
  </div>`;
}

function lineChart(series) {
  const W = 640, H = 240, pl = 64, pb = 26, pt = 12, pr = 12;
  const vals = series.map((s) => s.net);
  let lo = Math.min(0, ...vals), hi = Math.max(1, ...vals);
  const step = niceStep((hi - lo) / 4);
  lo = Math.floor(lo / step) * step; hi = Math.ceil(hi / step) * step;
  const x = (i) => pl + ((W - pl - pr) * i) / Math.max(1, series.length - 1);
  const y = (v) => pt + (H - pt - pb) * (1 - (v - lo) / (hi - lo));
  let s = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Netto vermogen per maand">`;
  for (let v = lo; v <= hi; v += step) {
    s += `<line class="gridline" x1="${pl}" x2="${W - pr}" y1="${y(v)}" y2="${y(v)}"/>`;
    s += `<text x="${pl - 6}" y="${y(v) + 4}" text-anchor="end">${esc(EUR0.format(v / 100))}</text>`;
  }
  s += `<path class="nwline" d="${series.map((p, i) => `${i ? "L" : "M"}${x(i)},${y(p.net)}`).join("")}"/>`;
  const every = Math.ceil(series.length / 10);
  series.forEach((p, i) => {
    s += `<g class="hover"><title>${monthLabel(p.k)}: ${eur(p.net)} (bezit ${eur(p.assetsSum)}, schuld ${eur(p.debt)})</title>
      <rect x="${x(i) - (W - pl - pr) / series.length / 2}" y="${pt}" width="${(W - pl - pr) / series.length}" height="${H - pt - pb}" fill="transparent"/>
      <circle class="nwdot" cx="${x(i)}" cy="${y(p.net)}" r="${series.length > 24 ? 0 : 3}"/></g>`;
    if (i % every === 0) s += `<text x="${x(i)}" y="${H - 8}" text-anchor="middle">${monthLabel(p.k)}</text>`;
  });
  return s + "</svg>";
}

/* ---------- Jaaroverzicht (in Trends) */

function yearReview() {
  const years = [...new Set(S.data.transactions.map((t) => t.date.slice(0, 4)))].sort().reverse();
  if (!years.length) return "";
  if (!S.reviewYear || !years.includes(S.reviewYear)) S.reviewYear = years[0];
  const Y = S.reviewYear;
  const meta = catMeta();
  const tx = S.data.transactions.filter((t) => t.date.startsWith(Y) && !t.excluded);
  const exp = tx.filter((t) => t.kind === "expense"), inc = tx.filter((t) => t.kind === "income");
  const E = exp.reduce((a, t) => a - t.amount, 0), I = inc.reduce((a, t) => a + t.amount, 0);
  const months = [...new Set(tx.map((t) => monthKey(t.date)))].sort();
  const perMonth = {};
  exp.forEach((t) => (perMonth[monthKey(t.date)] = (perMonth[monthKey(t.date)] || 0) - t.amount));
  const mSorted = Object.entries(perMonth).sort((a, b) => b[1] - a[1]);
  const merch = {};
  exp.forEach((t) => {
    const k = t.merchant_key;
    const m = (merch[k] = merch[k] || { name: t.counterparty, n: 0, s: 0, cat: t.category });
    m.n++; m.s -= t.amount;
  });
  const topMerch = Object.values(merch).sort((a, b) => b.s - a.s).slice(0, 10);
  const topTx = exp.filter((t) => !t.group).sort((a, b) => a.amount - b.amount).slice(0, 8);
  // stijgers en dalers t.o.v. vorig jaar, over dezelfde maanden
  const prevY = String(+Y - 1);
  const mset = new Set(months.map((k) => k.slice(5)));
  const catNow = {}, catPrev = {};
  exp.forEach((t) => (catNow[t.category] = (catNow[t.category] || 0) - t.amount));
  S.data.transactions.filter((t) => t.date.startsWith(prevY) && !t.excluded && t.kind === "expense" && mset.has(t.date.slice(5, 7)))
    .forEach((t) => (catPrev[t.category] = (catPrev[t.category] || 0) - t.amount));
  const hasPrev = Object.keys(catPrev).length > 0;
  const deltas = Object.keys({ ...catNow, ...catPrev }).map((c) => ({ c, d: (catNow[c] || 0) - (catPrev[c] || 0) }));
  const up = deltas.filter((x) => x.d > 0).sort((a, b) => b.d - a.d).slice(0, 4);
  const down = deltas.filter((x) => x.d < 0).sort((a, b) => a.d - b.d).slice(0, 4);
  const labelsY = (S.data.labels || []).map((l) => ({ l, s: labelStats(l.id) })).filter(({ s }) => s.from && s.from.startsWith(Y) || (s.to && s.to.startsWith(Y)));

  return `<div class="panel">
    <div class="row" style="justify-content:space-between">
      <h2 style="margin:0">Jaaroverzicht</h2>
      <select id="review-year">${years.map((y) => `<option ${y === Y ? "selected" : ""}>${y}</option>`).join("")}</select>
    </div>
    <p class="muted" style="font-size:12.5px;margin:6px 0 12px">${months.length < 12 ? `Gegevens over ${months.length} maanden (${monthLabel(months[0])} t/m ${monthLabel(months[months.length - 1])}). ` : ""}Uitgesloten posten tellen niet mee.</p>
    <div class="kpis" style="grid-template-columns:repeat(4,1fr)">
      <div class="kpi"><div class="l">Uitgaven</div><div class="v" style="font-size:20px">${eur(E, 1)}</div></div>
      <div class="kpi"><div class="l">Inkomsten</div><div class="v" style="font-size:20px">${eur(I, 1)}</div></div>
      <div class="kpi"><div class="l">Overschot</div><div class="v" style="font-size:20px">${eur(I - E, 1)}</div><div class="h">${I > 0 ? Math.round(((I - E) / I) * 100) + "% van de inkomsten" : ""}</div></div>
      <div class="kpi"><div class="l">Duurste maand</div><div class="v" style="font-size:20px">${mSorted[0] ? monthLabel(mSorted[0][0]) : "–"}</div>
        <div class="h">${mSorted[0] ? eur(mSorted[0][1], 1) + (mSorted.length > 1 ? ` · zuinigste: ${monthLabel(mSorted[mSorted.length - 1][0])} ${eur(mSorted[mSorted.length - 1][1], 1)}` : "") : ""}</div></div>
    </div>
    <div class="grid3">
      <div>
        <h3>Meeste uitgegeven bij</h3>
        <table class="compact">${topMerch.map((m, i) => `<tr><td class="muted num" style="width:22px;text-align:left">${i + 1}</td>
          <td><span class="dot" style="background:${(meta[m.cat] || {}).color || "#999"}"></span>${esc(m.name)} <span class="muted" style="font-size:12px">${m.n}×</span></td>
          <td class="num">${eur(m.s, 1)}</td></tr>`).join("")}</table>
      </div>
      <div>
        <h3>Grootste eenmalige uitgaven</h3>
        <table class="compact">${topTx.map((t) => `<tr><td class="muted" style="font-size:12.5px;white-space:nowrap">${fmtDate(t.date)}</td>
          <td>${esc(t.counterparty)}</td><td class="num">${eur(-t.amount, 1)}</td></tr>`).join("")}</table>
      </div>
      <div>
        <h3>Ten opzichte van ${prevY}</h3>
        ${hasPrev ? `<table class="compact">
          ${up.map((x) => `<tr><td>${esc(x.c)}</td><td class="num up-txt">+${eur(x.d, 1)}</td></tr>`).join("")}
          ${down.map((x) => `<tr><td>${esc(x.c)}</td><td class="num down-txt">−${eur(-x.d, 1)}</td></tr>`).join("")}
        </table><p class="muted" style="font-size:12px">Zelfde maanden vergeleken. Let op: onvolledige gegevens in ${prevY} vertekenen dit.</p>`
        : `<p class="muted">Geen gegevens over ${prevY}.</p>`}
        ${labelsY.length ? `<h3>Projecten</h3><table class="compact">${labelsY.map(({ l, s }) => `<tr><td><span class="dot" style="background:${l.color}"></span>${esc(l.name)}</td><td class="num">${eur(s.net, 1)}</td></tr>`).join("")}</table>` : ""}
      </div>
    </div>
  </div>`;
}

/* ---------- Vaste lasten */

function renderFixed() {
  const meta = catMeta();
  const all = S.data.recurring;
  const active = all.filter((x) => x.active);
  const inactive = all.filter((x) => !x.active);
  const total = active.reduce((a, x) => a + x.monthly, 0);
  const totalYear = active.reduce((a, x) => a + x.yearly, 0);
  const main = mainCardholder();

  const groups = {};
  active.forEach((x) => (groups[x.category] = groups[x.category] || []).push(x));
  const order = Object.keys(groups).sort((a, b) =>
    groups[b].reduce((s, x) => s + x.monthly, 0) - groups[a].reduce((s, x) => s + x.monthly, 0));

  const row = (x) => `<tr class="${x.active ? "" : "inactive"}">
      <td>${esc(x.name)}${x.cardholder && x.source === "amex" && x.cardholder !== main ? `<span class="tag">${esc(x.cardholder)}</span>` : ""}${x.manual ? '<span class="tag">handmatig</span>' : ""}
        <div class="desc">${x.source === "amex" ? "Amex" : "Bank"} · ${x.count}× sinds ${fmtDate(x.first)}</div></td>
      <td>${esc(x.period)}</td>
      <td class="num">${eur(x.amount)}</td>
      <td class="num">${eur(x.monthly)}</td>
      <td class="num">${eur(x.yearly)}</td>
      <td class="num">${fmtDate(x.last)}</td>
      <td class="num"><button class="link small" data-notfixed="${esc(x.key)}" title="Dit is geen vaste last">niet vast</button></td>
    </tr>`;
  const head = `<tr><th>Omschrijving</th><th>Frequentie</th><th class="num">Bedrag</th><th class="num">Per maand</th><th class="num">Per jaar</th><th class="num">Laatst</th><th></th></tr>`;

  const excluded = S.data.excluded_recurring;

  $("#tab-fixed").innerHTML = `
    <div class="kpis" style="grid-template-columns:repeat(3,1fr)">
      <div class="kpi accent"><div class="l">Totaal per maand</div><div class="v">${eur(total)}</div></div>
      <div class="kpi"><div class="l">Totaal per jaar</div><div class="v">${eur(totalYear)}</div></div>
      <div class="kpi"><div class="l">Actieve posten</div><div class="v">${active.length}</div><div class="h">${inactive.length} beëindigd</div></div>
    </div>
    <div class="notice info">Automatisch herkend op basis van regelmaat en bedrag. Klopt iets niet, klik dan op <em>niet vast</em>;
      een gemiste vaste last voeg je toe via het tabblad Transacties. Jaarlasten worden pas herkend als ze minstens twee keer voorkomen.</div>
    <div class="panel">
      <div class="row" style="justify-content:space-between;margin-bottom:6px"><h2 style="margin:0">Actieve vaste lasten</h2>
        <button data-export="1">Exporteer als CSV</button></div>
      <table>${head}
        ${order.map((cat) => {
          const items = groups[cat];
          const sum = items.reduce((s, x) => s + x.monthly, 0);
          const sumY = items.reduce((s, x) => s + x.yearly, 0);
          const col = (meta[cat] || {}).color || "#999";
          return `<tr class="cathead"><td colspan="3"><span class="dot" style="background:${col}"></span>${esc(cat)}</td>
            <td class="num">${eur(sum)}</td><td class="num">${eur(sumY)}</td><td colspan="2"></td></tr>` + items.map(row).join("");
        }).join("") || '<tr><td colspan="7" class="muted">Nog geen vaste lasten herkend. Importeer bij voorkeur minstens 3 maanden.</td></tr>'}
      </table>
    </div>
    ${inactive.length ? `<div class="panel"><div class="row" style="justify-content:space-between">
        <h2 style="margin:0">Beëindigd <span class="muted" style="font-weight:400;font-size:12.5px">niet meer gezien in de verwachte termijn</span></h2>
        <button class="link" data-toggleinactive="1">${S.showInactive ? "Verbergen" : "Tonen"}</button></div>
        ${S.showInactive ? `<table>${head}${inactive.map(row).join("")}</table>` : ""}</div>` : ""}
    ${excluded.length ? `<div class="panel"><h2>Handmatig uitgesloten</h2>
        ${excluded.map((k) => `<div class="row" style="margin-bottom:4px"><span class="mono">${esc(prettyKey(k))}</span>
          <button class="link small" data-restore="${esc(k)}">terugzetten</button></div>`).join("")}</div>` : ""}`;
}

function mainCardholder() {
  const c = {};
  S.data.transactions.forEach((t) => { if (t.cardholder) c[t.cardholder] = (c[t.cardholder] || 0) + 1; });
  return Object.keys(c).sort((a, b) => c[b] - c[a])[0] || "";
}

function prettyKey(k) {
  if (k.startsWith("INC|")) {
    const t = S.data.transactions.find((x) => x.merchant_key === k.split("|").slice(0, 3).join("|"));
    return (t ? t.counterparty : "Incasso") + (k.split("|").length > 3 ? " (" + k.split("|")[3] + ")" : "");
  }
  return k.replace("|", " · € ");
}

function exportFixedCsv() {
  const rows = [["Omschrijving", "Categorie", "Frequentie", "Bedrag", "Per maand", "Per jaar", "Laatst", "Bron"]];
  S.data.recurring.filter((x) => x.active).forEach((x) =>
    rows.push([x.name, x.category, x.period, (x.amount / 100).toFixed(2).replace(".", ","),
      (x.monthly / 100).toFixed(2).replace(".", ","), (x.yearly / 100).toFixed(2).replace(".", ","), x.last, x.source]));
  const csv = rows.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(";")).join("\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" }));
  a.download = `vaste-lasten-${S.data.end_date}.csv`;
  a.click();
}

/* ---------- Transacties */

function renderTx() {
  const f = S.txFilter;
  const r = periodRange();
  const cats = S.data.categories;
  const q = f.q.trim().toLowerCase();
  let list = f.label ? S.data.transactions.filter((t) => (t.labels || []).includes(+f.label))
    : S.data.transactions.filter((t) => monthKey(t.date) >= r.from && monthKey(t.date) <= r.endKey);
  S.sel = S.sel || new Set();
  const labels = S.data.labels || [];
  if (f.cat) list = list.filter((t) => t.category === f.cat);
  if (f.source) list = list.filter((t) => t.source === f.source);
  if (f.flow === "out") list = list.filter((t) => t.amount < 0);
  if (f.flow === "in") list = list.filter((t) => t.amount > 0);
  if (f.fixedOnly) list = list.filter((t) => t.group);
  if (f.flow === "excl") list = list.filter((t) => t.excluded);
  if (q) list = list.filter((t) => (t.counterparty + " " + t.description + " " + (t.cardholder || "")).toLowerCase().includes(q));
  const sum = list.reduce((a, t) => a + t.amount, 0);
  const shown = list.slice(0, f.limit);
  S.txList = list;
  const main = mainCardholder();
  const catOpts = (sel) => cats.map((c) => `<option ${c.name === sel ? "selected" : ""}>${esc(c.name)}</option>`).join("");

  $("#tab-tx").innerHTML = `
    <div class="panel">
      <div class="filters">
        <input type="search" id="f-q" placeholder="Zoek op naam of omschrijving" value="${esc(f.q)}">
        <select id="f-cat"><option value="">Alle categorieën</option>${cats.map((c) => `<option ${c.name === f.cat ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select>
        <select id="f-source"><option value="">Bank en Amex</option><option value="bank" ${f.source === "bank" ? "selected" : ""}>Bank</option><option value="amex" ${f.source === "amex" ? "selected" : ""}>Amex</option></select>
        <select id="f-flow"><option value="">In en uit</option><option value="out" ${f.flow === "out" ? "selected" : ""}>Alleen uitgaand</option><option value="in" ${f.flow === "in" ? "selected" : ""}>Alleen inkomend</option><option value="excl" ${f.flow === "excl" ? "selected" : ""}>Uitgesloten van gemiddelden</option></select>
        ${labels.length ? `<select id="f-label"><option value="">Alle labels</option>${labels.map((l) => `<option value="${l.id}" ${+f.label === l.id ? "selected" : ""}>${esc(l.name)}</option>`).join("")}</select>` : ""}
        <label><input type="checkbox" id="f-fixed" ${f.fixedOnly ? "checked" : ""}> alleen vaste lasten</label>
        <span class="count">${list.length} transacties · saldo ${eur(sum)}</span>
      </div>
      <label class="muted" style="font-size:12.5px;display:flex;gap:6px;align-items:center;margin-bottom:10px">
        <input type="checkbox" id="f-apply" ${S.applyToMerchant ? "checked" : ""}>
        Categoriewijziging geldt voor alle transacties van dezelfde tegenpartij (ook toekomstige)</label>
      ${f.label ? `<div class="notice info">Transacties met label <strong>${esc((labelMap()[+f.label] || {}).name || "")}</strong>, over alle periodes. <button class="link small" data-clearlabel="1">Filter wissen</button></div>` : ""}
      ${labels.length ? `<div class="bulkbar ${S.sel.size ? "active" : ""}">
        <span>${S.sel.size ? `${S.sel.size} geselecteerd` : "Vink transacties aan om een label toe te kennen"}</span>
        <select id="bulk-label">${labels.map((l) => `<option value="${l.id}">${esc(l.name)}</option>`).join("")}</select>
        <button data-bulklabel="add" ${S.sel.size ? "" : "disabled"}>Label toekennen</button>
        <button data-bulklabel="remove" ${S.sel.size ? "" : "disabled"}>Label verwijderen</button>
        ${S.sel.size ? '<button class="link small" data-clearsel="1">selectie wissen</button>' : ""}
      </div>` : `<p class="muted" style="font-size:12.5px">Tip: maak bij <em>Projecten</em> een label aan om transacties te groeperen per reis of project.</p>`}
      <table>
        <tr>${labels.length ? `<th style="width:26px"><input type="checkbox" id="sel-all" title="Alle ${list.length} gefilterde transacties selecteren" ${list.length && list.every((t) => S.sel.has(t.uid)) ? "checked" : ""}></th>` : ""}<th>Datum</th><th>Omschrijving</th><th>Categorie</th><th class="num">Bedrag</th><th></th></tr>
        ${shown.map((t) => `<tr>
          ${labels.length ? `<td>${t.synthetic ? "" : `<input type="checkbox" class="selbox" data-sel="${esc(t.uid)}" ${S.sel.has(t.uid) ? "checked" : ""}>`}</td>` : ""}
          <td class="num" style="text-align:left">${fmtDate(t.date)}</td>
          <td>${esc(t.counterparty || "(onbekend)")}
            <span class="tag">${t.source === "amex" ? "Amex" + (t.cardholder && t.cardholder !== main ? " · " + esc(t.cardholder) : "") : esc(t.tx_type || "bank")}</span>
            ${t.group ? '<span class="tag fixed">vast</span>' : ""}
            ${t.excluded ? '<span class="tag warn">uitgesloten</span>' : ""}
            ${t.reason.startsWith("vakantie") ? `<span class="tag">${esc(t.reason)}</span>` : ""}
            ${labelChips(t)}
            ${t.synthetic ? '<span class="tag">berekend deel van de termijn</span>' : ""}
            ${t.split_repayment ? `<span class="tag" title="Totale termijn ${eur(t.orig_amount)}">rente e.d.; ${eur(t.split_repayment)} aflossing apart</span>` : ""}
            <div class="desc" title="${esc(t.description)}">${esc(t.description)}${t.foreign_amt ? " · " + esc(t.foreign_amt) : ""}</div></td>
          <td>${t.synthetic ? `<span class="muted" style="font-size:12.5px">${esc(t.category)}</span>`
            : `<select data-uid="${esc(t.uid)}" title="Bron: ${esc(t.reason)}">${catOpts(t.category)}</select>`}</td>
          <td class="num ${t.amount > 0 ? "pos" : "neg"}">${eur(t.amount)}</td>
          <td class="num actions">${t.synthetic ? "" : t.amount < 0 && t.kind === "expense"
            ? (t.group ? `<button class="link small" data-notfixed="${esc(t.group)}">niet vast</button>`
                       : `<button class="link small" data-markfixed="${esc(t.merchant_key)}" title="Markeer deze tegenpartij als vaste last">vast?</button>`)
            : ""}${t.kind !== "transfer" && !t.excluded_by_category
            ? `<button class="link small" data-exclude="${esc(t.uid)}" data-state="${t.excluded ? 0 : 1}"
                 title="${t.excluded ? "Weer meetellen in overzicht en gemiddelden" : "Eenmalige grote post: niet meetellen in overzicht en gemiddelden"}">${t.excluded ? "meetellen" : "uitsluiten"}</button>`
            : ""}</td>
        </tr>`).join("")}
      </table>
      ${list.length > shown.length ? `<p style="text-align:center"><button data-more="1">Toon meer (${list.length - shown.length} resterend)</button></p>` : ""}
    </div>`;
}

/* ---------- Importeren */

function renderImport() {
  const imps = S.data.imports;
  $("#tab-import").innerHTML = `
    <div class="grid2">
      <div>
        <label class="drop" id="drop">
          <strong>Sleep je exportbestanden hierheen</strong>
          of klik om bestanden te kiezen (CAMT.053 .xml van de bank, .csv van American Express)
          <input type="file" id="file" multiple accept=".xml,.csv" hidden>
        </label>
        <div id="import-result" style="margin-top:14px"></div>
      </div>
      <div class="panel">
        <h2>Exports ophalen</h2>
        <ol class="steps">
          <li><strong>Van Lanschot:</strong> transacties downloaden in het formaat <em>CAMT.053</em> (.xml). Periodes mogen overlappen; dubbele transacties worden automatisch overgeslagen.</li>
          <li><strong>American Express:</strong> Overzichten &amp; Transacties, kies per jaar of per periode en download als <em>CSV</em>.</li>
          <li>Importeer daarna maandelijks de nieuwe periode. De bestanden zelf worden niet bewaard, alleen de transacties.</li>
        </ol>
        <p class="muted" style="font-size:12.5px">De Amex-aflossing op je bankrekening wordt automatisch als <em>Creditcard aflossing</em> uitgesloten, zodat creditcarduitgaven niet dubbel tellen. De ICS-aflossing telt wel mee als uitgave, omdat je de ICS-details niet importeert.</p>
      </div>
    </div>
    <div class="panel">
      <h2>Importgeschiedenis</h2>
      ${imps.length ? `<table><tr><th>Bestand</th><th>Bron</th><th>Periode</th><th class="num">Nieuw</th><th class="num">Dubbel</th><th>Geïmporteerd</th><th></th></tr>
        ${imps.map((i) => `<tr><td class="mono">${esc(i.filename)}</td><td>${i.source === "amex" ? "Amex" : "Bank"}</td>
          <td>${fmtDate(i.date_from)} t/m ${fmtDate(i.date_to)}</td><td class="num">${i.added}</td><td class="num">${i.duplicates}</td>
          <td>${esc(i.imported_at.replace("T", " "))}</td>
          <td class="num"><button class="link small" data-delimport="${i.id}" title="Verwijdert de transacties die met deze import zijn toegevoegd">verwijderen</button></td></tr>`).join("")}
        </table>` : '<p class="muted">Nog niets geïmporteerd.</p>'}
    </div>`;

  const drop = $("#drop"), input = $("#file");
  ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
  drop.addEventListener("drop", (e) => importFiles(e.dataTransfer.files));
  input.addEventListener("change", () => importFiles(input.files));
}

async function importFiles(files) {
  const out = [];
  for (const f of files) {
    try {
      const r = await api("/api/import", f, { "X-Filename": encodeURIComponent(f.name) });
      out.push(`<div class="notice info"><strong>${esc(f.name)}</strong>: ${r.added} nieuw, ${r.duplicates} al aanwezig
        (${r.source === "amex" ? "Amex" : "bank"}, ${fmtDate(r.from)} t/m ${fmtDate(r.to)})</div>`);
    } catch (e) {
      out.push(`<div class="notice"><strong>${esc(f.name)}</strong>: ${esc(e.message)}</div>`);
    }
  }
  await reload();
  const box = $("#import-result");
  if (box) box.innerHTML = out.join("");
}

/* ---------- Instellingen */

function renderSettings() {
  const st = S.data.settings;
  const suggestions = ownAccountSuggestions();
  $("#tab-settings").innerHTML = `
    <div class="grid2">
      <div class="panel">
        <h2>Eigen rekeningen</h2>
        <p class="muted" style="font-size:13px;margin-top:-4px">Overboekingen naar en van deze rekeningen (spaarrekening, gezamenlijke rekening) tellen niet mee als uitgave of inkomsten.</p>
        <label class="muted" style="font-size:12.5px">IBAN's, één per regel</label>
        <textarea id="s-ibans">${esc(st.own_ibans.join("\n"))}</textarea>
        ${suggestions.length ? `<p class="muted" style="font-size:12.5px;margin:8px 0 4px">Grote overboekingen gevonden naar:</p>
          ${suggestions.map((s) => `<div class="row" style="margin-bottom:3px"><span class="mono">${esc(s.iban)}</span>
            <span class="muted" style="font-size:12.5px">${esc(s.name)} · ${eur(s.total, 1)}</span>
            <button class="link small" data-addiban="${esc(s.iban)}">toevoegen</button></div>`).join("")}` : ""}
        <label class="muted" style="font-size:12.5px;display:block;margin-top:12px">Namen van eigen rekeninghouders (optioneel), één per regel</label>
        <textarea id="s-names" style="min-height:60px">${esc(st.own_names.join("\n"))}</textarea>
        <p style="margin-bottom:0"><button class="primary" data-savesettings="1">Opslaan</button></p>
      </div>
      <div class="panel">
        <h2>Vakantieperiodes</h2>
        <p class="muted" style="font-size:13px;margin-top:-4px">Pinbetalingen, geldopnames en buitenlandse Amex-betalingen in deze periodes gaan naar
          <em>Reizen &amp; vakantie</em>. Vaste lasten, abonnementen en overboekingen blijven ongemoeid, en je eigen aanpassingen gaan altijd voor.</p>
        ${(S.data.vacations || []).length ? `<table style="margin-bottom:12px">
          <tr><th>Naam</th><th>Periode</th><th class="num">Verplaatst</th><th></th></tr>
          ${S.data.vacations.map((v) => `<tr><td>${esc(v.name)}</td><td>${fmtDate(v.start)} t/m ${fmtDate(v.end)}</td>
            <td class="num">${v.count}</td><td class="num"><button class="link small" data-delvacation="${v.id}">verwijderen</button></td></tr>`).join("")}
        </table>` : ""}
        <div class="row">
          <input type="text" id="v-name" placeholder="Naam, bijv. Zuid-Afrika" style="flex:1;min-width:140px">
          <input type="date" id="v-start" aria-label="Van">
          <input type="date" id="v-end" aria-label="Tot en met">
          <button data-addvacation="1">Toevoegen</button>
        </div>
        <h3>Categorie toevoegen</h3>
        <div class="row">
          <input type="text" id="c-name" placeholder="Naam">
          <select id="c-kind"><option value="expense">Uitgave</option><option value="income">Inkomsten</option><option value="transfer">Overboeking (telt niet mee)</option></select>
          <button data-addcat="1">Toevoegen</button>
        </div>
        <h3>Opslag</h3>
        <p class="muted" style="font-size:13px">Database: <span class="mono">${esc(S.data.db_path)}</span><br>
          Maak hier af en toe een back-up van. De app verstuurt niets naar internet en luistert alleen op je eigen computer.</p>
        <h3>Herkenningsregels</h3>
        <p class="muted" style="font-size:13px">De standaardregels staan in <span class="mono">rules.py</span>. Wijzigingen die je hier in de app maakt (per transactie of per tegenpartij) gaan altijd voor.</p>
      </div>
    </div>`;
}

function ownAccountSuggestions() {
  const own = new Set(S.data.settings.own_ibans);
  const skip = new Set(S.data.transactions
    .filter((t) => t.counterparty_iban && (t.category === "Salaris" || t.kind === "transfer"))
    .map((t) => t.counterparty_iban));
  const agg = {};
  for (const t of S.data.transactions) {
    const ib = t.counterparty_iban;
    if (t.source !== "bank" || !ib || own.has(ib) || skip.has(ib)) continue;
    if (t.tx_type !== "overboeking" || Math.abs(t.amount) < 100000) continue;
    const a = (agg[ib] = agg[ib] || { iban: ib, name: t.counterparty, total: 0 });
    a.total += Math.abs(t.amount);
  }
  return Object.values(agg).sort((a, b) => b.total - a.total).slice(0, 5);
}

/* ------------------------------------------------------------ events */

document.addEventListener("click", async (e) => {
  const b = e.target.closest("button, .catrow, .catlink, .tag.label, g.hover");
  if (!b) return;
  try {
    if (b.dataset.tab) { S.tab = b.dataset.tab; render(); }
    else if (b.dataset.goto) { S.tab = b.dataset.goto; render(); }
    else if (b.dataset.cat) {
      Object.assign(S.txFilter, { cat: b.dataset.cat, q: "", source: "", flow: "", fixedOnly: false, limit: 300 });
      S.tab = "tx"; render();
    }
    else if (b.dataset.more) { S.txFilter.limit += 500; renderTx(); }
    else if (b.dataset.notfixed) { await api("/api/recurring", { key: b.dataset.notfixed, state: "no" }); toast("Gemarkeerd als geen vaste last"); await reload(); }
    else if (b.dataset.markfixed) { await api("/api/recurring", { key: b.dataset.markfixed, state: "yes" }); toast("Gemarkeerd als vaste last"); await reload(); }
    else if (b.dataset.restore) { await api("/api/recurring", { key: b.dataset.restore, state: "auto" }); toast("Teruggezet"); await reload(); }
    else if (b.dataset.toggleinactive) { S.showInactive = !S.showInactive; renderFixed(); }
    else if (b.dataset.export) exportFixedCsv();
    else if (b.dataset.delimport) {
      if (!confirm("De transacties uit deze import verwijderen?")) return;
      const r = await api("/api/delete_import", { id: +b.dataset.delimport });
      toast(`${r.deleted} transacties verwijderd`); await reload();
    }
    else if (b.dataset.addiban) {
      const ta = $("#s-ibans");
      ta.value = (ta.value.trim() + "\n" + b.dataset.addiban).trim();
    }
    else if (b.dataset.savesettings) {
      await api("/api/settings", { own_ibans: $("#s-ibans").value.split("\n"), own_names: $("#s-names").value.split("\n") });
      toast("Instellingen opgeslagen"); await reload();
    }
    else if (b.dataset.exclude) {
      await api("/api/exclude", { uid: b.dataset.exclude, exclude: b.dataset.state === "1" });
      toast(b.dataset.state === "1" ? "Uitgesloten van overzicht en gemiddelden" : "Telt weer mee"); await reload();
    }
    else if (b.dataset.showexcluded) {
      Object.assign(S.txFilter, { cat: "", q: "", source: "", flow: "excl", fixedOnly: false, limit: 300 });
      S.tab = "tx"; render();
    }
    else if (b.dataset.addvacation) {
      await api("/api/vacations", { action: "add", name: $("#v-name").value, start: $("#v-start").value, end: $("#v-end").value });
      toast("Vakantieperiode toegevoegd"); await reload();
    }
    else if (b.dataset.delvacation) {
      await api("/api/vacations", { action: "delete", id: +b.dataset.delvacation });
      toast("Vakantieperiode verwijderd"); await reload();
    }
    else if (b.dataset.labelfilter) {
      Object.assign(S.txFilter, { cat: "", q: "", source: "", flow: "", fixedOnly: false, limit: 300, label: b.dataset.labelfilter });
      S.tab = "tx"; render();
    }
    else if (b.dataset.clearlabel) { S.txFilter.label = ""; renderTx(); }
    else if (b.dataset.clearsel) { S.sel.clear(); renderTx(); }
    else if (b.dataset.bulklabel) {
      const r = await api("/api/tx_labels", { label_id: +$("#bulk-label").value, uids: [...S.sel], action: b.dataset.bulklabel });
      toast(`${r.count} transacties ${b.dataset.bulklabel === "add" ? "gelabeld" : "ontdaan van label"}`);
      S.sel.clear(); await reload();
    }
    else if (b.dataset.addlabel) {
      const r = await api("/api/labels", { action: "add", name: $("#l-name").value });
      const vac = $("#l-vac") && $("#l-vac").value;
      if (vac) {
        const uids = S.data.transactions.filter((t) => t.reason === "vakantie: " + vac).map((t) => t.uid);
        await api("/api/tx_labels", { label_id: r.id, uids, action: "add" });
        toast(`Label aangemaakt met ${uids.length} transacties`);
      } else toast("Label aangemaakt");
      await reload();
    }
    else if (b.dataset.renamelabel) {
      const l = labelMap()[+b.dataset.renamelabel];
      const name = prompt("Nieuwe naam", l.name);
      if (name) { await api("/api/labels", { action: "rename", id: l.id, name }); await reload(); }
    }
    else if (b.dataset.dellabel) {
      if (!confirm("Dit label verwijderen? De transacties zelf blijven bestaan.")) return;
      await api("/api/labels", { action: "delete", id: +b.dataset.dellabel }); toast("Label verwijderd"); await reload();
    }
    else if (b.dataset.editasset) { S.editAsset = S.editAsset === +b.dataset.editasset ? null : +b.dataset.editasset; renderNetworth(); }
    else if (b.dataset.savevalue) {
      await api("/api/assets", { action: "value", id: +b.dataset.savevalue, value: $("#a-val").value, date: $("#a-date").value });
      S.editAsset = null; toast("Waarde opgeslagen"); await reload();
    }
    else if (b.dataset.delvalue) {
      await api("/api/assets", { action: "delvalue", id: +b.dataset.delvalue, date: b.dataset.date }); await reload();
    }
    else if (b.dataset.delasset) {
      if (!confirm("Deze post en alle waarden verwijderen?")) return;
      await api("/api/assets", { action: "delete", id: +b.dataset.delasset }); S.editAsset = null; await reload();
    }
    else if (b.dataset.addasset) {
      await api("/api/assets", { action: "add", name: $("#n-name").value, side: $("#n-side").value, value: $("#n-val").value, date: $("#n-date").value });
      toast("Post toegevoegd"); await reload();
    }
    else if (b.dataset.savepart) {
      const body = { name: $("#m-name").value, principal: $("#m-principal").value, rate: $("#m-rate").value,
        years: $("#m-years").value, start: $("#m-start").value, kind: $("#m-kind").value };
      if (b.dataset.savepart === "new") await api("/api/mortgage", { action: "add_part", ...body });
      else await api("/api/mortgage", { action: "update_part", id: +b.dataset.savepart, ...body });
      S.editPart = null; toast("Leningdeel opgeslagen"); await reload();
    }
    else if (b.dataset.canceledit) { S.editPart = null; renderNetworth(); }
    else if (b.dataset.editpart) { S.editPart = +b.dataset.editpart; renderNetworth(); }
    else if (b.dataset.partdetail) { S.partDetail = S.partDetail === +b.dataset.partdetail ? null : +b.dataset.partdetail; renderNetworth(); }
    else if (b.dataset.delpart) {
      if (!confirm("Dit leningdeel verwijderen, inclusief renteherzieningen en correcties?")) return;
      await api("/api/mortgage", { action: "delete_part", id: +b.dataset.delpart }); S.partDetail = null; await reload();
    }
    else if (b.dataset.addrate) {
      const id = b.dataset.addrate;
      await api("/api/mortgage", { action: "add_rate", id: +id, date: $("#r-date-" + id).value, rate: $("#r-rate-" + id).value });
      toast("Renteherziening toegevoegd"); await reload();
    }
    else if (b.dataset.delrate) { await api("/api/mortgage", { action: "del_rate", id: +b.dataset.delrate, date: b.dataset.date }); await reload(); }
    else if (b.dataset.addcorr) {
      const id = b.dataset.addcorr;
      await api("/api/mortgage", { action: "add_corr", id: +id, date: $("#c-date-" + id).value, balance: $("#c-bal-" + id).value });
      toast("Correctie toegevoegd"); await reload();
    }
    else if (b.dataset.delcorr) { await api("/api/mortgage", { action: "del_corr", id: +b.dataset.delcorr, date: b.dataset.date }); await reload(); }
    else if (b.dataset.savemsettings) {
      await api("/api/mortgage", { action: "settings", split: $("#m-split").checked, match: $("#m-match").value });
      toast("Instelling opgeslagen"); await reload();
    }
    else if (b.dataset.addcat) {
      await api("/api/categories", { name: $("#c-name").value, kind: $("#c-kind").value });
      toast("Categorie toegevoegd"); await reload();
    }
  } catch (err) { toast(err.message); }
});

document.addEventListener("change", async (e) => {
  const el = e.target;
  const f = S.txFilter;
  try {
    if (el.id === "period") { S.period = el.value; render(); }
    else if (el.id === "trend-cat") { S.trendCat = el.value; renderTrends(); }
    else if (el.id === "f-cat") { f.cat = el.value; f.limit = 300; renderTx(); }
    else if (el.id === "f-source") { f.source = el.value; f.limit = 300; renderTx(); }
    else if (el.id === "f-flow") { f.flow = el.value; f.limit = 300; renderTx(); }
    else if (el.id === "f-fixed") { f.fixedOnly = el.checked; renderTx(); }
    else if (el.id === "f-label") { f.label = el.value; f.limit = 300; renderTx(); }
    else if (el.id === "review-year") { S.reviewYear = el.value; renderTrends(); }
    else if (el.id === "sel-all") { (S.txList || []).forEach((t) => (el.checked ? S.sel.add(t.uid) : S.sel.delete(t.uid))); renderTx(); }
    else if (el.dataset.sel) { el.checked ? S.sel.add(el.dataset.sel) : S.sel.delete(el.dataset.sel); renderTx(); }
    else if (el.id === "f-apply") { S.applyToMerchant = el.checked; }
    else if (el.dataset.uid) {
      await api("/api/categorize", { uid: el.dataset.uid, category: el.value, scope: S.applyToMerchant ? "merchant" : "tx" });
      toast(S.applyToMerchant ? "Categorie aangepast voor deze tegenpartij" : "Categorie aangepast");
      await reload();
    }
  } catch (err) { toast(err.message); }
});

let qTimer;
document.addEventListener("input", (e) => {
  if (e.target.id !== "f-q") return;
  clearTimeout(qTimer);
  qTimer = setTimeout(() => {
    S.txFilter.q = e.target.value; S.txFilter.limit = 300;
    renderTx();
    const i = $("#f-q"); i.focus(); i.setSelectionRange(i.value.length, i.value.length);
  }, 200);
});

reload().catch((e) => {
  document.querySelector("main").innerHTML = `<div class="panel empty"><strong>Kan de gegevens niet laden</strong>${esc(e.message)}</div>`;
});
