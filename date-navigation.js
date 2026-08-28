(() => {
  const picker = document.getElementById('datePicker');
  const datebox = document.querySelector('.datebox');
  if (!picker || !datebox || document.getElementById('prevTradingDay')) return;

  const wrap = document.createElement('div');
  wrap.id = 'tradingDayNav';
  wrap.style.cssText = 'display:flex;align-items:center;gap:6px;margin-left:2px;';
  wrap.innerHTML = '<button id="prevTradingDay" type="button" title="前一個有交易資料的日期">← 前一交易日</button>' +
                   '<button id="nextTradingDay" type="button" title="下一個有交易資料的日期">下一交易日 →</button>';
  datebox.insertAdjacentElement('afterend', wrap);

  const prev = document.getElementById('prevTradingDay');
  const next = document.getElementById('nextTradingDay');
  let tradingDates = [];

  const parseDate = s => /^\\d{4}-\\d{2}-\\d{2}$/.test(s) ? new Date(s + 'T00:00:00Z') : null;
  const iso = d => d.toISOString().slice(0, 10);

  async function loadDates() {
    try {
      const res = await fetch('data/latest.json?' + Date.now(), { cache: 'no-store' });
      if (!res.ok) throw new Error('data unavailable');
      const data = await res.json();
      const set = new Set();
      (data.stocks || []).forEach(stock => {
        (stock.history || []).forEach(item => {
          if (item && /^\\d{4}-\\d{2}-\\d{2}$/.test(item.date)) set.add(item.date);
        });
      });
      tradingDates = Array.from(set).sort();
      updateState();
    } catch (e) {
      prev.disabled = true;
      next.disabled = true;
    }
  }

  function currentIndex() {
    if (!tradingDates.length) return -1;
    const value = picker.value;
    if (!value) return tradingDates.length - 1;
    let exact = tradingDates.indexOf(value);
    if (exact >= 0) return exact;
    let i = tradingDates.findIndex(d => d > value);
    return i < 0 ? tradingDates.length - 1 : Math.max(0, i - 1);
  }

  function setDate(index) {
    if (index < 0 || index >= tradingDates.length) return;
    picker.value = tradingDates[index];
    picker.dispatchEvent(new Event('change', { bubbles: true }));
    picker.dispatchEvent(new Event('input', { bubbles: true }));
    updateState();
  }

  function updateState() {
    const i = currentIndex();
    prev.disabled = i <= 0;
    next.disabled = i < 0 || i >= tradingDates.length - 1;
    const selected = picker.value;
    if (selected && tradingDates.length && !tradingDates.includes(selected)) {
      const label = selected > tradingDates[tradingDates.length - 1] ? '已超過最新資料' : '休市日：按鈕會跳至最近交易日';
      picker.title = label;
    } else {
      picker.title = '選擇日期';
    }
  }

  prev.addEventListener('click', () => setDate(currentIndex() - 1));
  next.addEventListener('click', () => setDate(currentIndex() + 1));
  picker.addEventListener('change', updateState);
  picker.addEventListener('input', updateState);
  loadDates();
})();
