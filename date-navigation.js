(() => {
  function init() {
    const picker = document.getElementById('datePicker');
    const datebox = document.querySelector('.datebox');
    if (!picker || !datebox) return;
    if (document.getElementById('tradingDayNav')) return;

    const nav = document.createElement('div');
    nav.id = 'tradingDayNav';
    nav.style.cssText = 'display:flex;align-items:center;gap:6px;margin-left:2px;';
    nav.innerHTML = `
      <button id="prevTradingDay" type="button" title="前一個有交易資料的日期">← 前一交易日</button>
      <button id="nextTradingDay" type="button" title="下一個有交易資料的日期">下一交易日 →</button>`;
    datebox.insertAdjacentElement('afterend', nav);

    const prev = document.getElementById('prevTradingDay');
    const next = document.getElementById('nextTradingDay');
    let tradingDates = [];

    const isDate = s => typeof s === 'string' && s.length === 10 &&
      s[4] === '-' && s[7] === '-' && !Number.isNaN(Date.parse(s + 'T00:00:00Z'));

    async function loadDates() {
      try {
        const res = await fetch('./data/latest.json?nav=' + Date.now(), { cache: 'no-store' });
        if (!res.ok) throw new Error('data unavailable');
        const data = await res.json();
        const set = new Set();
        for (const stock of (data.stocks || [])) {
          for (const item of (stock.history || [])) {
            if (item && isDate(item.date)) set.add(item.date);
          }
        }
        if (!set.size && isDate(data.updated_at?.slice(0, 10))) set.add(data.updated_at.slice(0, 10));
        tradingDates = [...set].sort();
        updateState();
      } catch (err) {
        console.error('Trading-day navigation failed:', err);
        prev.disabled = true;
        next.disabled = true;
      }
    }

    function currentIndex() {
      if (!tradingDates.length) return -1;
      const value = picker.value;
      if (!value) return tradingDates.length - 1;
      const exact = tradingDates.indexOf(value);
      if (exact >= 0) return exact;
      let i = tradingDates.length - 1;
      while (i > 0 && tradingDates[i] > value) i--;
      return i;
    }

    function goTo(index) {
      if (index < 0 || index >= tradingDates.length) return;
      picker.value = tradingDates[index];
      picker.dispatchEvent(new Event('input', { bubbles: true }));
      picker.dispatchEvent(new Event('change', { bubbles: true }));
      updateState();
    }

    function updateState() {
      const i = currentIndex();
      prev.disabled = i <= 0;
      next.disabled = i < 0 || i >= tradingDates.length - 1;
    }

    prev.addEventListener('click', e => {
      e.preventDefault();
      e.stopPropagation();
      goTo(currentIndex() - 1);
    });
    next.addEventListener('click', e => {
      e.preventDefault();
      e.stopPropagation();
      goTo(currentIndex() + 1);
    });
    picker.addEventListener('change', updateState);
    picker.addEventListener('input', updateState);

    // The data fetch is asynchronous. Wrap the main renderer before it receives
    // the response so a single malformed stock record cannot blank the whole UI.
    if (typeof window.render === 'function' && !window.__radarRenderWrapped) {
      const originalRender = window.render;
      const safe = v => {
        if (v == null) return '-';
        try { return String(v); } catch (_) { return '-'; }
      };
      window.render = function () {
        try {
          return originalRender();
        } catch (err) {
          console.error('Radar render failed; using safe renderer:', err);
          try {
            const tableBody = document.querySelector('#tbl tbody');
            const source = Array.isArray(rows) ? rows : [];
            if (tableBody) {
              tableBody.innerHTML = source.map(x => {
                const r = x || {};
                const conclusion = safe(r.technical_signal);
                const strategy = safe(r.strategy);
                return `<tr>
                  <td><div class="conclusion"><span class="badge">${conclusion}</span><span class="strategy">${strategy}</span></div></td>
                  <td><b>${safe(r.name)}</b></td><td>${safe(r.id)}</td><td>${safe(r.category)}</td>
                  <td>${safe(r.price)}</td><td>${safe(r.pct)}%</td><td><b>${safe(r.score)}</b></td>
                  <td>${safe(r.industry_score)}</td><td>${safe(r.fundamental_score)}</td><td>${safe(r.valuation_score)}</td>
                  <td>${safe(r.chips_score)}</td><td>${safe(r.technical_score)}</td><td>${safe(r.pe)}</td><td>${safe(r.eps_ttm)}</td>
                  <td>${safe(r.revenue)}</td><td>${safe(r.revenue_yoy)}</td><td>${safe(r.foreign_20d_net)}</td>
                  <td>${safe(r.trust_20d_net)}</td><td>${safe(r.institution_20d_net)}</td><td>${safe(r.ma5)}</td>
                  <td>${safe(r.ma20)}</td><td>${safe(r.ma60)}</td><td>${safe(r.ma20_gap_pct)}</td><td>${safe(r.rsi14)}</td>
                  <td>${safe(r.macd_hist)}</td><td>${safe(r.volume_ratio_5d_20d)}</td>
                </tr>`;
              }).join('');
            }
            const status = document.getElementById('status');
            if (status) status.textContent = `V3.3｜資料已載入｜${source.length} 檔（安全顯示模式）`;
          } catch (fallbackErr) {
            console.error('Safe renderer failed:', fallbackErr);
          }
        }
      };
      window.__radarRenderWrapped = true;
    }

    loadDates();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
