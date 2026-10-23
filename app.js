/* "Who Should Get the Coupon?" dashboard.
   Reads window.DASHBOARD_DATA, which run_pipeline.py writes to assets/data.js.
   No libraries: charts are plain SVG so they follow the page's light and dark themes. */
(function () {
  "use strict";

  const D = window.DASHBOARD_DATA;
  if (!D) {
    const err = document.getElementById("load-error");
    if (err) err.hidden = false;
    return;
  }

  /* ------------------------------------------------------------------ formatting */
  const pct = (x, d = 1) => `${(x * 100).toFixed(d)}%`;
  const pct0 = (x) => `${Math.round(x * 100)}%`;
  const int = (x) => Math.round(x).toLocaleString("en-US");
  const money = (x, d = 0) => {
    const f = 10 ** d;
    const r = Math.round(x * f) / f;
    const s = Math.abs(r).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
    return (r < 0 ? "−$" : "$") + s;
  };
  const moneyCompact = (x) => {
    const a = Math.abs(x);
    const sign = x < 0 ? "−" : "";
    if (a >= 1e6) return `${sign}$${(a / 1e6).toFixed(a >= 1e7 ? 0 : 1)}M`;
    if (a >= 1e3) return `${sign}$${(a / 1e3).toFixed(a >= 1e4 ? 0 : 1)}K`;
    return `${sign}$${Math.round(a)}`;
  };
  const utc = (s) => new Date(`${s}T00:00:00Z`);
  const fmtDay = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
  const fmtMonDay = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
  const fmtMonYear = new Intl.DateTimeFormat("en-US", { month: "short", year: "numeric", timeZone: "UTC" });
  const fmtMonthLong = new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric", timeZone: "UTC" });

  /* ------------------------------------------------------------------ DOM helpers */
  const SVGNS = "http://www.w3.org/2000/svg";
  function svg(tag, attrs, parent) {
    const e = document.createElementNS(SVGNS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function el(tag, className, text, parent) {
    const e = document.createElement(tag);
    if (className) e.className = className;
    if (text !== undefined && text !== null) e.textContent = text;
    if (parent) parent.appendChild(e);
    return e;
  }
  /* Re-render a chart whenever its container changes width, and once more when the web fonts
     arrive (label positions depend on text width). */
  const mounted = [];
  function mount(host, render) {
    let last = 0;
    const run = (w) => {
      if (w > 0 && Math.abs(w - last) > 1) {
        last = w;
        render(w);
      }
    };
    if ("ResizeObserver" in window) {
      new ResizeObserver((entries) => run(Math.round(entries[0].contentRect.width))).observe(host);
    } else {
      window.addEventListener("resize", () => run(host.clientWidth));
    }
    run(host.clientWidth);
    const handle = { refresh: () => { last = 0; run(host.clientWidth); } };
    mounted.push(handle);
    return handle;
  }
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(() => mounted.forEach((h) => h.refresh()));
  }
  function simpleTable(container, headers, rows) {
    const t = document.createElement("table");
    t.className = "simple";
    const hr = t.createTHead().insertRow();
    headers.forEach((h, i) => {
      const th = el("th", i ? "num" : "", h, hr);
      th.scope = "col";
    });
    const body = t.createTBody();
    rows.forEach((r) => {
      const tr = body.insertRow();
      r.forEach((c, i) => {
        const cell = el(i ? "td" : "th", i ? "num" : "", c, tr);
        if (!i) cell.scope = "row";
      });
    });
    container.replaceChildren(t);
  }
  function niceTicks(min, max, count) {
    const span = max - min || 1;
    const raw = span / count;
    const mag = 10 ** Math.floor(Math.log10(raw));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= count) || 10 * mag;
    const lo = Math.floor(min / step) * step;
    const hi = Math.ceil(max / step) * step;
    const ticks = [];
    for (let v = lo; v <= hi + step / 2; v += step) ticks.push(Math.abs(v) < step / 1e6 ? 0 : v);
    return ticks;
  }

  /* ------------------------------------------------------------------ derived numbers */
  const K = D.kpis;
  const M = D.model;
  const typeA = D.types.find((t) => t.type === "Type A");
  const mass = D.types.filter((t) => t.type !== "Type A").reduce(
    (a, t) => ({ campaigns: a.campaigns + t.campaigns, mailings: a.mailings + t.mailings, redeemers: a.redeemers + t.redeemers }),
    { campaigns: 0, mailings: 0, redeemers: 0 });
  mass.rate = mass.redeemers / mass.mailings;
  const sig = D.signals;
  const segBy = Object.fromEntries(D.segments.segments.map((s) => [s.key, s]));
  const sub = D.subsidy;
  const disc = D.simulator.discount_basis;
  const boot = M.bootstrap;
  const gap30 = M.reach.model["30"] - M.reach.rule["30"];

  const bind = {
    campaigns: String(K.campaigns),
    households: int(K.households_in_study),
    mailings: int(K.mailings),
    couponsRedeemed: int(K.coupons_redeemed),
    transactions: `${(K.transactions / 1e6).toFixed(2)} million`,
    transactionsCompact: `${(K.transactions / 1e6).toFixed(2)}M`,
    noRedemption: pct0(K.no_redemption_share),
    noRedemptionCount: int(K.mailings - K.redeeming_mailings),
    campaignSpan: `${fmtMonYear.format(utc(K.first_campaign_start))} to ${fmtMonYear.format(utc(K.last_campaign_end))}`,
    reach30: pct0(M.reach.model["30"]),
    reach30Exact: pct(M.reach.model["30"]),
    rule30: pct0(M.reach.rule["30"]),
    rule30Exact: pct(M.reach.rule["30"]),
    reach30Ci: `${pct0(boot.model.reach_ci[0])} to ${pct0(boot.model.reach_ci[1])}`,
    liftOverRule: `+${(gap30 * 100).toFixed(1)}`,
    liftOverRuleRound: String(Math.round(gap30 * 100)),
    liftCi: `+${(boot.model_minus_rule.reach_ci[0] * 100).toFixed(1)} to +${(boot.model_minus_rule.reach_ci[1] * 100).toFixed(1)} points`,
    aucModel: M.test_auc.model.toFixed(2),
    aucRule: M.test_auc.rule.toFixed(2),
    aucLogistic: M.test_auc.logistic.toFixed(2),
    typeARate: pct(typeA.rate),
    typeACampaigns: String(typeA.campaigns),
    typeAMailings: int(typeA.mailings),
    massRate: pct(mass.rate),
    massCampaigns: String(mass.campaigns),
    massMailings: int(mass.mailings),
    typeRatio: `${(typeA.rate / mass.rate).toFixed(1)}×`,
    testStartLong: fmtDay.format(utc(D.meta.test_start)),
    testStartMonth: fmtMonthLong.format(utc(D.meta.test_start)),
    signalRows: int(sig.rows),
    matchedTop: pct(sig.matched_with_coupon[sig.matched_with_coupon.length - 1].rate),
    matchedZero: pct(sig.matched_with_coupon[0].rate),
    spendCut: `${money(D.segments.spend_cut)} a week`,
    segLoyal: pct(segBy.loyal.rate),
    segBudget: pct(segBy.budget.rate),
    trainCampaigns: String(M.train_campaigns.length),
    testCampaigns: String(M.test_campaigns.length),
    testHouseholds: int(M.test_households),
    testRedeemers: int(M.test_redeemers),
    byTypeA: `${pct(M.by_type.personalised.reach30_model)} (rule ${pct(M.by_type.personalised.reach30_rule)})`,
    byTypeMass: `${pct(M.by_type.mass.reach30_model)} (rule ${pct(M.by_type.mass.reach30_rule)})`,
    baseRate: pct(M.base_rate),
    discountPerCoupon: money(disc.avg_discount_per_coupon, 2),
    couponsPerRedeemer: disc.avg_coupons_per_redeeming_household.toFixed(2),
    subsidyBefore: pct0(sub.share_bought_before),
    subsidyRecent: pct0(sub.share_bought_recent),
    subsidyChecked: int(sub.redemptions_checked),
    narrowBefore: pct0(sub.narrow_share_bought_before),
    txStart: fmtDay.format(utc(K.transactions_start)),
    txEnd: fmtDay.format(utc(K.transactions_end)),
    generated: fmtDay.format(utc(D.meta.generated)),
  };
  document.querySelectorAll("[data-k]").forEach((node) => {
    const v = bind[node.dataset.k];
    if (v !== undefined) node.textContent = v;
  });

  /* ------------------------------------------------------------------ line chart */
  function lineChart(host, o) {
    return mount(host, (W) => {
      host.replaceChildren();
      const H = o.height || 320;
      const m = { t: 30, r: o.right || 30, b: 44, l: o.left || 48 };
      const iw = Math.max(40, W - m.l - m.r);
      const ih = H - m.t - m.b;
      const xs = (v) => m.l + ((v - o.xMin) / (o.xMax - o.xMin)) * iw;
      const ys = (v) => m.t + (1 - (v - o.yMin) / (o.yMax - o.yMin)) * ih;
      const root = svg("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, class: "viz", role: "img", "aria-label": o.ariaLabel });
      host.appendChild(root); /* in the page early so labels can be measured */

      svg("text", { x: 0, y: 12, class: "axis-title" }, root).textContent = o.yTitle;
      o.yTicks.forEach((t) => {
        const y = ys(t);
        svg("line", { x1: m.l, x2: m.l + iw, y1: y, y2: y, class: t === 0 ? "axis-line" : "grid-line" }, root);
        const tx = svg("text", { x: m.l - 8, y, class: "tick", "text-anchor": "end", "dominant-baseline": "middle" }, root);
        tx.textContent = o.yFmt(t);
      });
      o.xTicks.forEach((t) => {
        const anchor = t === o.xMin ? "start" : t === o.xMax ? "end" : "middle";
        const tx = svg("text", { x: xs(t), y: m.t + ih + 18, class: "tick", "text-anchor": anchor }, root);
        tx.textContent = o.xFmt(t);
      });
      svg("text", { x: m.l + iw / 2, y: H - 4, class: "axis-title", "text-anchor": "middle" }, root).textContent = o.xTitle;

      if (o.refX !== undefined) {
        const x = xs(o.refX);
        svg("line", { x1: x, x2: x, y1: m.t, y2: m.t + ih, class: "ref-line" }, root);
        svg("text", { x: x + 6, y: m.t + 12, class: "ref-label" }, root).textContent = o.refLabel;
      }

      o.series.forEach((s) => {
        const d = s.values.map((v, i) => `${i ? "L" : "M"}${xs(o.x[i]).toFixed(1)},${ys(v).toFixed(1)}`).join("");
        svg("path", { d, class: `series-line ${s.cls}` }, root);
      });

      /* direct labels: values at the one x the story is about, set to the left of the
         dots where a rising curve leaves empty space */
      if (o.labelAtIndex !== undefined) {
        const i = o.labelAtIndex;
        const items = o.series.map((s) => ({ s, y: ys(s.values[i]) })).sort((a, b) => a.y - b.y);
        for (let k = 1; k < items.length; k++) {
          const prev = items[k - 1].ly ?? items[k - 1].y;
          if (items[k].y - prev < 15) items[k].ly = prev + 15;
        }
        items.forEach((it) => {
          const x = xs(o.x[i]);
          svg("circle", { cx: x, cy: it.y, r: 4.5, class: `mk ${it.s.cls}` }, root);
          /* "below-right" tucks a label under its own rising curve, clear of the curve above it */
          const br = it.s.labelPos === "below-right";
          const t = svg("text", {
            x: br ? x + 10 : x - 10, y: br ? it.y + 18 : (it.ly ?? it.y) - 6,
            class: "direct-label", "text-anchor": br ? "start" : "end",
          }, root);
          t.textContent = `${o.valueFmt(it.s.values[i])} `;
          const nm = svg("tspan", { class: "name" }, t);
          nm.textContent = it.s.short || it.s.label;
          /* on narrow charts a left-hand label can run past the y-axis: keep just the value */
          if (!br && t.getBBox().x < m.l + 2) nm.remove();
        });
      }

      /* highlighted points (e.g. best depth); on narrow charts the labels would sit on the
         curves, so only the dots stay and the plan card carries the numbers */
      (o.markers || []).forEach((mk) => {
        const x = xs(mk.x);
        const y = ys(mk.y);
        svg("circle", { cx: x, cy: y, r: 5, class: `mk ${mk.cls}` }, root);
        if (mk.label && iw >= 480) {
          const above = mk.position !== "below";
          let anchor = "middle";
          if (x < m.l + 60) anchor = "start";
          if (x > m.l + iw - 60) anchor = "end";
          const t = svg("text", { x, y: above ? y - 11 : y + 20, class: "direct-label", "text-anchor": anchor }, root);
          t.textContent = mk.label;
        }
      });

      /* hover + keyboard layer */
      const cross = svg("line", { y1: m.t, y2: m.t + ih, x1: 0, x2: 0, class: "crosshair", visibility: "hidden" }, root);
      const dots = o.series.map((s) => svg("circle", { r: 4, class: `mk ${s.cls}`, visibility: "hidden" }, root));
      const overlay = svg("rect", { x: m.l, y: m.t, width: iw, height: ih, class: "overlay", tabindex: "0", "aria-label": o.overlayLabel }, root);
      const tip = el("div", "tooltip", null, host);
      tip.hidden = true;
      let idx = null;
      const n = o.x.length;
      const nearest = (v) => Math.max(0, Math.min(n - 1, Math.round(((v - o.xMin) / (o.xMax - o.xMin)) * (n - 1))));

      function show(i) {
        idx = Math.max(0, Math.min(n - 1, i));
        const x = xs(o.x[idx]);
        cross.setAttribute("x1", x);
        cross.setAttribute("x2", x);
        cross.setAttribute("visibility", "visible");
        o.series.forEach((s, k) => {
          dots[k].setAttribute("cx", x);
          dots[k].setAttribute("cy", ys(s.values[idx]));
          dots[k].setAttribute("visibility", "visible");
        });
        tip.replaceChildren();
        el("div", "tt-title", o.tooltipTitle(o.x[idx]), tip);
        o.series.forEach((s) => {
          const row = el("div", "tt-row", null, tip);
          el("span", `tt-key k-${s.cls}`, null, row);
          el("span", "tt-val", o.valueFmt(s.values[idx]), row);
          el("span", "tt-name", s.label, row);
        });
        tip.hidden = false;
        const tw = tip.offsetWidth;
        let left = x + 14;
        if (left + tw > W) left = x - 14 - tw;
        tip.style.left = `${Math.max(0, left)}px`;
        tip.style.top = `${m.t + 6}px`;
      }
      function hide() {
        idx = null;
        cross.setAttribute("visibility", "hidden");
        dots.forEach((d) => d.setAttribute("visibility", "hidden"));
        tip.hidden = true;
      }
      const fromEvent = (e) => {
        const r = root.getBoundingClientRect();
        return o.xMin + ((e.clientX - r.left - m.l) / iw) * (o.xMax - o.xMin);
      };
      overlay.addEventListener("pointermove", (e) => show(nearest(fromEvent(e))));
      overlay.addEventListener("pointerdown", (e) => show(nearest(fromEvent(e))));
      overlay.addEventListener("pointerleave", hide);
      overlay.addEventListener("focus", () => show(idx === null ? (o.focusIndex || 0) : idx));
      overlay.addEventListener("blur", hide);
      overlay.addEventListener("keydown", (e) => {
        const step = e.shiftKey ? 10 : 1;
        if (e.key === "ArrowRight" || e.key === "ArrowUp") show((idx ?? 0) + step);
        else if (e.key === "ArrowLeft" || e.key === "ArrowDown") show((idx ?? 0) - step);
        else if (e.key === "Home") show(0);
        else if (e.key === "End") show(n - 1);
        else if (e.key === "Escape") { hide(); overlay.blur(); return; }
        else return;
        e.preventDefault();
      });
    });
  }

  function legend(ul, items) {
    ul.replaceChildren();
    items.forEach((it) => {
      const li = el("li", "", null, ul);
      el("span", `${it.shape === "rect" ? "key-rect" : "key-line"} k-${it.cls}`, null, li);
      li.appendChild(document.createTextNode(it.label));
    });
  }

  /* ------------------------------------------------------------------ column chart (ordinal buckets) */
  function columnChart(host, data, opts) {
    mount(host, (W) => {
      host.replaceChildren();
      const H = 236;
      const m = { t: 26, r: 6, b: 48, l: 40 };
      const iw = Math.max(40, W - m.l - m.r);
      const ih = H - m.t - m.b;
      const ys = (v) => m.t + (1 - v / opts.yMax) * ih;
      const root = svg("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, class: "viz", role: "img", "aria-label": opts.ariaLabel });
      for (let t = 0; t <= opts.yMax + 1e-9; t += opts.yStep) {
        const y = ys(t);
        svg("line", { x1: m.l, x2: m.l + iw, y1: y, y2: y, class: t === 0 ? "axis-line" : "grid-line" }, root);
        svg("text", { x: m.l - 8, y, class: "tick", "text-anchor": "end", "dominant-baseline": "middle" }, root).textContent = pct0(t);
      }
      const slot = iw / data.length;
      const bw = Math.min(24, slot * 0.5);
      host.appendChild(root);
      const tip = el("div", "tooltip", null, host);
      tip.hidden = true;
      data.forEach((d, i) => {
        const cx = m.l + slot * (i + 0.5);
        const x0 = cx - bw / 2;
        const x1 = cx + bw / 2;
        const y = ys(d.rate);
        const y0 = ys(0);
        const r = Math.min(4, (y0 - y) / 2, bw / 2);
        const path = `M${x0},${y0}V${y + r}Q${x0},${y} ${x0 + r},${y}H${x1 - r}Q${x1},${y} ${x1},${y + r}V${y0}Z`;
        const col = svg("path", { d: path, class: `col o${i + 1}` }, root);
        svg("text", { x: cx, y: y - 7, class: "col-label", "text-anchor": "middle" }, root).textContent = pct(d.rate);
        svg("text", { x: cx, y: y0 + 18, class: "tick", "text-anchor": "middle" }, root).textContent = d.label;
        const hit = svg("rect", {
          x: m.l + slot * i, y: m.t, width: slot, height: ih + 24, class: "hit", tabindex: "0",
          "aria-label": `${opts.xName} ${d.label}: ${pct(d.rate)} redeemed, ${int(d.n)} mailings`,
        }, root);
        const on = () => {
          col.classList.add("is-hover");
          tip.replaceChildren();
          el("div", "tt-title", `${opts.xName}: ${d.label}`, tip);
          const row = el("div", "tt-row", null, tip);
          el("span", "tt-key k-s1", null, row);
          el("span", "tt-val", pct(d.rate), row);
          el("span", "tt-name", "redeemed", row);
          el("div", "tt-name", `${int(d.redeemers)} of ${int(d.n)} mailings`, tip);
          tip.hidden = false;
          const tw = tip.offsetWidth;
          let left = cx + bw / 2 + 8;
          if (left + tw > W) left = cx - bw / 2 - 8 - tw;
          tip.style.left = `${Math.max(0, left)}px`;
          tip.style.top = `${Math.max(0, y - 10)}px`;
        };
        const off = () => { col.classList.remove("is-hover"); tip.hidden = true; };
        hit.addEventListener("pointerenter", on);
        hit.addEventListener("pointerleave", off);
        hit.addEventListener("focus", on);
        hit.addEventListener("blur", off);
      });
      svg("text", { x: m.l + iw / 2, y: H - 4, class: "axis-title", "text-anchor": "middle" }, root).textContent = opts.xTitle;
    });
  }

  /* ------------------------------------------------------------------ tracker */
  const camps = D.campaigns.map((c) => ({ ...c, personalised: c.type === "Type A", s: utc(c.start), e: utc(c.end) }));
  const t0 = Math.min(...camps.map((c) => c.s));
  const t1 = Math.max(...camps.map((c) => c.e));
  const pos = (d) => ((d - t0) / (t1 - t0)) * 100;
  const rateMax = Math.ceil(Math.max(...camps.map((c) => c.rate)) * 20) / 20;
  const testPos = pos(utc(D.meta.test_start));
  const trackerState = { filter: "all", sort: "start" };

  (function axis() {
    const ax = document.getElementById("timeline-axis");
    const ticks = [];
    const first = new Date(t0);
    let y = first.getUTCFullYear();
    let mo = Math.ceil((first.getUTCMonth() + (first.getUTCDate() > 1 ? 1 : 0)) / 3) * 3;
    for (;;) {
      if (mo >= 12) { mo -= 12; y += 1; }
      const d = Date.UTC(y, mo, 1);
      if (d > t1) break;
      ticks.push(d);
      mo += 3;
    }
    ticks.forEach((d, i) => {
      const dt = new Date(d);
      const label = dt.getUTCMonth() === 0 ? fmtMonYear.format(dt) : new Intl.DateTimeFormat("en-US", { month: "short", timeZone: "UTC" }).format(dt);
      const s = el("span", i === 0 && pos(d) < 6 ? "first" : pos(d) > 94 ? "last" : "", label, ax);
      s.style.left = `${pos(d)}%`;
    });
  })();

  function dateRange(c) {
    const sameYear = c.s.getUTCFullYear() === c.e.getUTCFullYear();
    return sameYear
      ? `${fmtMonDay.format(c.s)} – ${fmtDay.format(c.e)}`
      : `${fmtDay.format(c.s)} – ${fmtDay.format(c.e)}`;
  }
  function roleChip(role) {
    if (role === "train") return ["Train", "chip"];
    if (role === "test") return ["Test", "chip chip-test"];
    return ["Not used", "chip chip-unused"];
  }
  function renderTracker() {
    const body = document.getElementById("tracker-body");
    let rows = camps.filter((c) => trackerState.filter === "all"
      || (trackerState.filter === "personalised" ? c.personalised : !c.personalised));
    const by = {
      start: (a, b) => a.s - b.s || a.id - b.id,
      rate: (a, b) => b.rate - a.rate,
      households: (a, b) => b.households - a.households,
    }[trackerState.sort];
    rows = rows.slice().sort(by);
    body.replaceChildren(...rows.map((c) => {
      const tr = document.createElement("tr");
      const th = el("th", "", null, tr);
      th.scope = "row";
      el("span", "camp-id", `#${c.id}`, th);
      const ty = el("span", "camp-type", null, th);
      el("span", `dot ${c.personalised ? "dot-targeted" : "dot-mass"}`, null, ty).setAttribute("aria-hidden", "true");
      ty.appendChild(document.createTextNode(`${c.personalised ? "Personalised" : "Mass"} · ${c.type.replace("Type ", "")}`));

      el("td", "num", int(c.households), tr);

      const rt = el("td", "", null, tr);
      const rw = el("div", "rate", null, rt);
      const trk = el("span", "rate-track", null, rw);
      trk.setAttribute("aria-hidden", "true");
      el("span", "rate-bar", null, trk).style.width = `${(c.rate / rateMax) * 100}%`;
      el("span", "rate-val", pct(c.rate), rw);

      const dates = el("td", "", null, tr);
      el("span", "dates", dateRange(c), dates);
      el("span", "days", `${c.days} days`, dates);

      const tl = el("td", "col-timeline", null, tr);
      const line = el("span", "tl-test", null, tl);
      line.setAttribute("aria-hidden", "true");
      line.style.left = `calc(14px + (100% - 28px) * ${(testPos / 100).toFixed(4)})`;
      const track = el("div", "tl", null, tl);
      track.setAttribute("aria-hidden", "true");
      const bar = el("span", `tl-bar${c.personalised ? " targeted" : ""}`, null, track);
      bar.style.left = `${pos(c.s)}%`;
      bar.style.width = `${pos(c.e) - pos(c.s)}%`;

      el("td", "num", int(c.coupons), tr);
      const [label, cls] = roleChip(c.role);
      const roleCell = el("td", "", null, tr);
      const chip = el("span", cls, label, roleCell);
      if (c.role.startsWith("not used")) chip.title = c.role.replace("not used: ", "");
      return tr;
    }));
    const hh = rows.reduce((a, c) => a + c.households, 0);
    const rd = rows.reduce((a, c) => a + c.redeemers, 0);
    document.getElementById("tracker-summary").textContent =
      `${rows.length} campaigns · ${int(hh)} mailings · ${pct(rd / hh)} redeemed`;
  }
  document.querySelectorAll("[data-filter]").forEach((b) => b.addEventListener("click", () => {
    trackerState.filter = b.dataset.filter;
    document.querySelectorAll("[data-filter]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    renderTracker();
  }));
  document.getElementById("tracker-sort").addEventListener("change", (e) => {
    trackerState.sort = e.target.value;
    renderTracker();
  });
  renderTracker();

  /* ------------------------------------------------------------------ drivers */
  const sigMax = Math.ceil(Math.max(...[...sig.matched_with_coupon, ...sig.prior_redemptions, ...sig.coupon_habit].map((d) => d.rate)) * 10) / 10;
  columnChart(document.getElementById("chart-matched"), sig.matched_with_coupon, {
    yMax: sigMax, yStep: 0.1, xName: "Matching coupons", xTitle: "Coupons matching products bought with a coupon",
    ariaLabel: `Redemption rate rises from ${pct(sig.matched_with_coupon[0].rate)} with no matching coupons to ${pct(sig.matched_with_coupon[3].rate)} with four or more`,
  });
  columnChart(document.getElementById("chart-prior"), sig.prior_redemptions, {
    yMax: sigMax, yStep: 0.1, xName: "Past coupons redeemed", xTitle: "Campaign coupons redeemed before",
    ariaLabel: `Redemption rate rises from ${pct(sig.prior_redemptions[0].rate)} for households with no past redemptions to ${pct(sig.prior_redemptions[3].rate)} for six or more`,
  });
  columnChart(document.getElementById("chart-habit"), sig.coupon_habit, {
    yMax: sigMax, yStep: 0.1, xName: "Items bought with a coupon", xTitle: "Share of items bought with a coupon",
    ariaLabel: `Redemption rate rises from ${pct(sig.coupon_habit[0].rate)} for households that never use coupons to ${pct(sig.coupon_habit[3].rate)} for the heaviest users`,
  });

  (function matrix() {
    const host = document.getElementById("segment-matrix");
    const ranked = D.segments.segments.slice().sort((a, b) => a.rate - b.rate);
    const level = (s) => ranked.indexOf(s) + 1;
    const cell = (s) => {
      const c = el("div", `mx-cell seq-${level(s)}`);
      c.setAttribute("role", "group");
      c.setAttribute("aria-label", `${s.name}: ${pct(s.rate)} redeemed, ${pct0(s.share)} of mailings`);
      el("div", "mx-name", s.name, c);
      const r = el("div", "mx-rate", pct(s.rate), c);
      el("small", "", " redeemed", r);
      const sh = el("div", "mx-share", null, c);
      el("span", "", `${pct0(s.share)} of mailings`, sh);
      el("span", "", `${money(s.spend_per_week)} spend a week`, sh);
      return c;
    };
    host.replaceChildren(
      el("div", "mx-ylab", "Spend above median"), cell(segBy.loyal), cell(segBy.engaged),
      el("div", "mx-ylab", "Spend below median"), cell(segBy.light), cell(segBy.budget),
      el("div", ""), el("div", "mx-xlab", "Rarely use coupons"), el("div", "mx-xlab", "Use coupons more than most"),
    );
  })();

  simpleTable(document.getElementById("drivers-table"), ["Signal and group", "Mailings", "Redeemed", "Rate"], [
    ...sig.matched_with_coupon.map((d) => [`Matching coupons bought with a coupon: ${d.label}`, int(d.n), int(d.redeemers), pct(d.rate)]),
    ...sig.prior_redemptions.map((d) => [`Past coupons redeemed: ${d.label}`, int(d.n), int(d.redeemers), pct(d.rate)]),
    ...sig.coupon_habit.map((d) => [`Items bought with a coupon: ${d.label}`, int(d.n), int(d.redeemers), pct(d.rate)]),
    ...D.segments.segments.map((s) => [`Segment: ${s.name}`, int(s.n), int(Math.round(s.n * s.rate)), pct(s.rate)]),
  ]);

  /* ------------------------------------------------------------------ targeting */
  const gainsSeries = [
    { key: "model", label: "Model (LightGBM)", short: "model", values: M.curves.model, cls: "s1" },
    { key: "rule", label: "Simple rule", short: "rule", values: M.curves.rule, cls: "s2", labelPos: "below-right" },
    { key: "random", label: "Random mailing", short: "random", values: M.curves.random, cls: "s0" },
  ];
  legend(document.getElementById("gains-legend"), gainsSeries);
  lineChart(document.getElementById("chart-gains"), {
    x: M.depths, xMin: 0, xMax: 1, yMin: 0, yMax: 1,
    xTicks: [0, 0.2, 0.4, 0.6, 0.8, 1], yTicks: [0, 0.2, 0.4, 0.6, 0.8, 1],
    xFmt: pct0, yFmt: pct0, valueFmt: (v) => pct(v),
    xTitle: "Share of households mailed, best-ranked first", yTitle: "Share of redeemers reached",
    series: gainsSeries, refX: 0.3, refLabel: "Top 30%", labelAtIndex: 30, focusIndex: 30,
    height: 350,
    tooltipTitle: (x) => `Mail the top ${pct0(x)}`,
    ariaLabel: `Mailing the top 30% reaches ${pct(M.reach.model["30"])} of redeemers with the model, ${pct(M.reach.rule["30"])} with the simple rule and 30% at random`,
    overlayLabel: "Gains chart. Use the left and right arrow keys to move along the curve.",
  });
  simpleTable(document.getElementById("gains-table"), ["Households mailed", "Model", "Simple rule", "Random"],
    [10, 20, 30, 40, 50, 60, 70, 80, 90, 100].map((p) => [`Top ${p}%`, pct(M.curves.model[p]), pct(M.curves.rule[p]), pct(M.curves.random[p])]));

  (function profile() {
    const t = document.getElementById("profile-table");
    const a = M.top20;
    const b = M.rest;
    const hr = t.createTHead().insertRow();
    ["", "Model's top 20%", "Everyone else"].forEach((h, i) => { const th = el("th", i ? "num" : "", h, hr); th.scope = "col"; });
    const body = t.createTBody();
    [
      ["Redeemed this campaign", pct(a.rate), pct(b.rate)],
      ["Had redeemed a campaign coupon before", pct(a.has_redeemed_before), pct(b.has_redeemed_before)],
      ["Matching coupons bought with a coupon (average)", a.matched_with_coupon.toFixed(1), b.matched_with_coupon.toFixed(1)],
      ["Items bought with any coupon", pct(a.coupon_line_rate), pct(b.coupon_line_rate)],
      ["Weekly spend", money(a.spend_per_week), money(b.spend_per_week)],
      ["Households", int(a.households), int(b.households)],
    ].forEach((r) => {
      const tr = body.insertRow();
      const th = el("th", "", r[0], tr);
      th.scope = "row";
      el("td", "num", r[1], tr);
      el("td", "num", r[2], tr);
    });
  })();

  (function importance() {
    const host = document.getElementById("importance-bars");
    host.replaceChildren(...M.importance_groups.map((g) => {
      const row = el("div", "hbar");
      el("span", "hbar-label", g.name, row);
      el("span", "hbar-val", String(Math.round(g.relative * 100)), row);
      const track = el("div", "hbar-track", null, row);
      track.setAttribute("aria-hidden", "true");
      el("div", "hbar-fill", null, track).style.width = `${Math.max(1, g.relative * 100)}%`;
      return row;
    }));
  })();

  (function modelTable() {
    const t = document.getElementById("model-table");
    const hr = t.createTHead().insertRow();
    ["Approach", "Training (cross-validated)", "Test campaigns"].forEach((h, i) => { const th = el("th", i ? "num" : "", h, hr); th.scope = "col"; });
    const body = t.createTBody();
    [
      ["Simple rule", M.cv_auc.rule, M.test_auc.rule],
      ["Logistic regression", M.cv_auc.logistic, M.test_auc.logistic],
      [`LightGBM${M.chosen === "lightgbm" ? " (chosen)" : ""}`, M.cv_auc.lightgbm, M.test_auc.lightgbm],
    ].forEach((r) => {
      const tr = body.insertRow();
      const th = el("th", "", r[0], tr);
      th.scope = "row";
      el("td", "num", r[1].toFixed(3), tr);
      el("td", "num", r[2].toFixed(3), tr);
    });
  })();

  /* ------------------------------------------------------------------ simulator */
  const SD = D.simulator.defaults;
  const inputs = {
    audience: document.getElementById("in-audience"),
    send: document.getElementById("in-send"),
    discount: document.getElementById("in-discount"),
    profit: document.getElementById("in-profit"),
    incr: document.getElementById("in-incr"),
  };
  const outputs = {
    audience: [document.getElementById("out-audience"), (v) => int(v)],
    send: [document.getElementById("out-send"), (v) => money(v, 2)],
    discount: [document.getElementById("out-discount"), (v) => money(v, 2)],
    profit: [document.getElementById("out-profit"), (v) => money(v, 2)],
    incr: [document.getElementById("out-incr"), (v) => pct0(v)],
  };
  function setDefaults() {
    inputs.audience.value = SD.audience;
    inputs.send.value = SD.send_cost;
    inputs.discount.value = SD.discount;
    inputs.profit.value = SD.extra_profit;
    inputs.incr.value = SD.incremental;
  }
  const curveSet = { model: M.curves.model, rule: M.curves.rule, random: M.curves.random };
  function simulate() {
    const p = {
      N: +inputs.audience.value, c: +inputs.send.value, disc: +inputs.discount.value,
      m: +inputs.profit.value, inc: +inputs.incr.value,
    };
    const value = p.inc * p.m - p.disc;
    const r = M.base_rate;
    const res = {};
    for (const k in curveSet) {
      const prof = M.depths.map((d, i) => p.N * r * curveSet[k][i] * value - p.N * d * p.c);
      let bi = 0;
      prof.forEach((v, i) => { if (v > prof[bi]) bi = i; });
      res[k] = { prof, bi, best: prof[bi], depth: M.depths[bi], redeemers: p.N * r * curveSet[k][bi] };
    }
    return { p, value, res, everyone: res.model.prof[M.depths.length - 1] };
  }
  const profitSeries = [
    { key: "model", label: "Model", cls: "s1" },
    { key: "rule", label: "Simple rule", cls: "s2" },
    { key: "random", label: "Random mailing", cls: "s0" },
  ];
  legend(document.getElementById("profit-legend"), profitSeries);
  let profitChart = null;
  let last = null;
  function scissors() {
    const s = svg("svg", { viewBox: "0 0 24 24", class: "scissors", "aria-hidden": "true", fill: "none", stroke: "currentColor", "stroke-width": "1.8", "stroke-linecap": "round", "stroke-linejoin": "round" });
    svg("circle", { cx: 6, cy: 6, r: 3 }, s);
    svg("circle", { cx: 6, cy: 18, r: 3 }, s);
    svg("path", { d: "M20 4 8.12 15.88M14.47 14.48 20 20M8.12 8.12 12 12" }, s);
    return s;
  }
  function renderSim() {
    for (const k in outputs) outputs[k][0].textContent = outputs[k][1](+inputs[k].value);
    last = simulate();
    const { p, value, res, everyone } = last;
    const best = res.model;
    const head = document.getElementById("stub-headline");
    const subl = document.getElementById("stub-sub");
    if (best.best > 0.5 && best.bi > 0) {
      head.textContent = best.bi >= M.depths.length - 1
        ? "Mail every household"
        : `Mail the model's top ${pct0(best.depth)} of households`;
      subl.textContent = `Expected profit ${money(best.best)} from ${int(p.N * best.depth)} mailings and about ${int(best.redeemers)} redeeming households.`;
    } else {
      head.textContent = "Hold this campaign";
      subl.textContent = value <= 0
        ? `Each redemption is worth ${money(value, 2)} after the discount, so every mailing depth loses money.`
        : "The postage costs more than the redemptions bring in at every depth. Lower the cost to send or raise the value of a sale.";
    }
    const side = document.getElementById("stub-side");
    side.replaceChildren(scissors());
    const row = (k, v) => { const d = el("div", "stub-row", null, side); el("dt", "", k, d); el("dd", "", v, d); };
    const depthLabel = (x) => (x.bi === 0 ? "mail no one" : `top ${pct0(x.depth)}`);
    row("Model, best depth", `${depthLabel(res.model)} · ${money(res.model.best)}`);
    row("Simple rule, best depth", `${depthLabel(res.rule)} · ${money(res.rule.best)}`);
    row("Mail everyone", money(everyone));
    row("Value of one redemption", money(value, 2));

    const all = [...res.model.prof, ...res.rule.prof, ...res.random.prof];
    const lo = Math.min(0, ...all);
    const hi = Math.max(0, ...all);
    const ticks = niceTicks(lo, hi === lo ? lo + 1 : hi, 5);
    const series = profitSeries.map((s) => ({ ...s, values: res[s.key].prof }));
    const markers = [];
    if (res.model.bi > 0) markers.push({ x: res.model.depth, y: res.model.best, cls: "s1", label: `${pct0(res.model.depth)} · ${moneyCompact(res.model.best)}`, position: "above" });
    if (res.rule.bi > 0) markers.push({ x: res.rule.depth, y: res.rule.best, cls: "s2", label: `${pct0(res.rule.depth)} · ${moneyCompact(res.rule.best)}`, position: "below" });
    const host = document.getElementById("chart-profit");
    const opts = {
      x: M.depths, xMin: 0, xMax: 1, yMin: ticks[0], yMax: ticks[ticks.length - 1],
      xTicks: [0, 0.2, 0.4, 0.6, 0.8, 1], yTicks: ticks, xFmt: pct0, yFmt: moneyCompact,
      valueFmt: (v) => money(v), xTitle: "Share of households mailed, best-ranked first", yTitle: "Expected profit",
      series, markers, height: 320, left: 56, focusIndex: res.model.bi,
      tooltipTitle: (x) => `Mail the top ${pct0(x)} (${int(p.N * x)} households)`,
      ariaLabel: `Best plan: ${document.getElementById("stub-headline").textContent}. Mailing everyone gives ${money(everyone)}.`,
      overlayLabel: "Profit chart. Use the left and right arrow keys to move along the curves.",
    };
    if (!profitChart) {
      profitChart = { opts };
      profitChart.handle = lineChart(host, new Proxy({}, { get: (_, k) => profitChart.opts[k] }));
    } else {
      profitChart.opts = opts;
      profitChart.handle.refresh();
    }
  }
  Object.values(inputs).forEach((i) => i.addEventListener("input", renderSim));
  document.getElementById("sim-reset").addEventListener("click", () => { setDefaults(); renderSim(); });
  setDefaults();
  renderSim();

  /* ------------------------------------------------------------------ incrementality */
  const segDefs = [
    { key: "recent", label: "Bought in the 8 weeks before", cls: "recent" },
    { key: "earlier", label: "Bought earlier", cls: "earlier" },
    { key: "new", label: "Not bought before", cls: "new" },
  ];
  legend(document.getElementById("stack-legend"), segDefs.map((s) => ({ ...s, shape: "rect" })));
  const stacksHost = document.getElementById("subsidy-stacks");
  mount(stacksHost, (W) => {
    stacksHost.replaceChildren(...sub.groups.map((g) => {
      const wrap = el("div", "stack-row");
      const head = el("div", "stack-head", null, wrap);
      el("span", "", g.label, head);
      el("span", "stack-n", `${int(g.n)} redemptions`, head);
      const bar = el("div", "stack", null, wrap);
      bar.setAttribute("role", "img");
      bar.setAttribute("aria-label", `${g.label}: ${segDefs.map((s) => `${pct0(g[s.key])} ${s.label.toLowerCase()}`).join(", ")}`);
      segDefs.forEach((s) => {
        const seg = el("div", `seg seg-${s.cls}`, null, bar);
        seg.style.flex = `${g[s.key]} 1 0`;
        seg.title = `${s.label}: ${pct(g[s.key])}`;
        if (g[s.key] * W >= 46) seg.textContent = pct0(g[s.key]);
      });
      return wrap;
    }));
  });
  simpleTable(document.getElementById("subsidy-table"), ["Campaigns", "Redemptions", "Bought in last 8 weeks", "Bought earlier", "Not bought before"],
    sub.groups.map((g) => [g.label, int(g.n), pct(g.recent), pct(g.earlier), pct(g.new)]));

  /* ------------------------------------------------------------------ section index highlight */
  if ("IntersectionObserver" in window) {
    const links = new Map([...document.querySelectorAll(".sections a")].map((a) => [a.getAttribute("href").slice(1), a]));
    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => {
        if (en.isIntersecting && links.has(en.target.id)) {
          links.forEach((a) => a.removeAttribute("aria-current"));
          links.get(en.target.id).setAttribute("aria-current", "true");
        }
      });
    }, { rootMargin: "-45% 0px -50% 0px" });
    links.forEach((_, id) => { const s = document.getElementById(id); if (s) io.observe(s); });
  }
})();
