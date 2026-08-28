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

        // Build the trading calendar from every stock's retained history.
        for (const stock of (data.stocks || [])) {
          for (const item of (stock.history || [])) {
            if (item && isDate(item.date)) set.add(item.date);
          }
        }

        // Fallback to the dataset's current date if history is unavailable.
        if (!set.size && isDate(data.updated_at?.slice(0, 10))) {
          set.add(data.updated_at.slice(0, 10));
        }

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

      // For a weekend/holiday, use the nearest trading day not later than it.
      let i = tradingDates.length - 1;
      while (i > 0 && tradingDates[i] > value) i--;
      return i;
    }

    function goTo(index) {
      if (index < 0 || index >= tradingDates.length) return;
      const target = tradingDates[index];
      picker.value = target;

      // The main application listens to the date input/change events.
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
    loadDates();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
