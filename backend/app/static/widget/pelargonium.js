/*
 * Pelargonium Shop — catalog + cart + order widget for Tilda (block T123 "HTML code").
 *
 *   <div id="pelargonium-catalog"></div>
 *   <script src="https://API_HOST/static/widget/pelargonium.js" data-lang="ru"></script>
 *
 * data-api          API origin (default: where this script is loaded from)
 * data-lang         ru | kk | en (default: last choice of the visitor, then ru)
 * data-lang-switch  "false" hides the RU/KZ/EN switch (e.g. separate Tilda pages per language)
 * data-target       id of the container (default: pelargonium-catalog)
 */
(function () {
  'use strict';
  var script = document.currentScript;
  var API = (script.dataset.api || new URL(script.src).origin).replace(/\/$/, '');
  var LANGS = ['ru', 'kk', 'en'];
  var TYPES = ['zonal', 'rosebud', 'ivy', 'star', 'regal', 'angel'];
  var COLORS = { pink: '#ec8fb0', red: '#d9192c', white: '#ffffff', purple: '#9b59b6', salmon: '#f4876a' };
  var EXTRA = {
    ru: { loading: 'Загружаем каталог…', errLoad: 'Не удалось загрузить каталог.', retry: 'Повторить', errServer: 'Не получилось отправить заявку. Попробуйте ещё раз или позвоните нам.', careLink: 'Памятка по уходу',
      searchAi: 'Название или описание: «белые розочки до 4000»…', aiBtn: '✨ Подобрать с ИИ', aiThinking: 'Подбираем сорта…',
      aiFound: 'Подбор ИИ по запросу', aiNote: 'ИИ может ошибаться — проверьте описание сорта. Цена и наличие — из каталога.',
      aiClarify: 'Уточните, пожалуйста: какой цвет, бюджет или место (подоконник, балкон, кашпо)? С вопросами о здоровье лучше обратиться к специалисту.',
      aiNone: 'Подходящих сортов в каталоге нет. Попробуйте смягчить условия.', aiFallback: 'Умный подбор сейчас недоступен — показан поиск по названию.',
      aiShowAll: 'Показать весь каталог', aiHint: 'Не нашли по названию? Опишите словами, что хотите, и нажмите' },
    kk: { loading: 'Каталог жүктелуде…', errLoad: 'Каталогты жүктеу мүмкін болмады.', retry: 'Қайталау', errServer: 'Өтінімді жіберу мүмкін болмады. Қайталап көріңіз немесе бізге қоңырау шалыңыз.', careLink: 'Күтім жадынамасы',
      searchAi: 'Атауы немесе сипаттамасы: «4000-ға дейін ақ раушандар»…', aiBtn: '✨ ЖИ-мен таңдау', aiThinking: 'Сорттарды таңдап жатырмыз…',
      aiFound: 'ЖИ таңдауы, сұрау', aiNote: 'ЖИ қателесуі мүмкін — сорт сипаттамасын тексеріңіз. Баға мен қолжетімділік — каталогтан.',
      aiClarify: 'Нақтылаңызшы: қандай түс, бюджет немесе орын (терезе алды, балкон, кашпо)? Денсаулық сұрақтары бойынша маманға жүгініңіз.',
      aiNone: 'Каталогта сәйкес сорт жоқ. Шарттарды жұмсартып көріңіз.', aiFallback: 'Ақылды таңдау қазір қолжетімсіз — атауы бойынша іздеу көрсетілді.',
      aiShowAll: 'Бүкіл каталогты көрсету', aiHint: 'Атауы бойынша таппадыңыз ба? Не қалайтыныңызды сөзбен жазып, басыңыз' },
    en: { loading: 'Loading the catalog…', errLoad: 'Could not load the catalog.', retry: 'Retry', errServer: 'Could not send your request. Please try again or call us.', careLink: 'Care guide',
      searchAi: 'Name or description: "white mini roses under 4000"…', aiBtn: '✨ Pick with AI', aiThinking: 'Picking varieties…',
      aiFound: 'AI picks for', aiNote: 'AI can make mistakes — check the variety description. Price and stock come from the catalog.',
      aiClarify: 'Could you be more specific: colour, budget or place (windowsill, balcony, hanging basket)? For health questions, please ask a specialist.',
      aiNone: 'No variety in the catalog matches. Try relaxing the conditions.', aiFallback: 'Smart search is unavailable right now — showing search by name.',
      aiShowAll: 'Show the whole catalog', aiHint: 'Nothing by name? Describe what you want in your own words and press' }
  };

  var store = {
    get: function (k, d) { try { var v = localStorage.getItem('psw_' + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
    set: function (k, v) { try { localStorage.setItem('psw_' + k, JSON.stringify(v)); } catch (e) {} }
  };

  var T = null;
  var lang = LANGS.indexOf(script.dataset.lang) >= 0 ? script.dataset.lang : store.get('lang', 'ru');
  var showSwitch = script.dataset.langSwitch !== 'false';
  var state = { q: '', type: '', colors: [], stock: false, sort: 'default' };
  var list = [], known = {}, cart = store.get('cart', {}), view = 'cart', draft = null, lastOrder = null, modalId = null, modalQty = 1;
  var root, el = {};
  var aiReady = false, ai = null, aiSeq = 0;  // ai = {q, status, fallback} while showing smart-search results

  function t(k) { return (EXTRA[lang] && EXTRA[lang][k]) || (T[lang] && T[lang][k] != null ? T[lang][k] : T.ru[k]); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function money(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ' ') + ' ₸'; }
  function photo(v, small) {
    if (!v.photo_url) return '';
    var url = v.photo_url.charAt(0) === '/' ? API + v.photo_url : v.photo_url;
    // Wikimedia serves fixed thumbnail widths; cards don't need the 960px one
    return small ? url.replace(/\/960px-/, '/500px-') : url;
  }
  function imgHtml(v, big) {
    return photo(v) ? '<img src="' + esc(photo(v, !big)) + '" alt="' + esc(v.name) + '" loading="lazy" onerror="this.parentNode.classList.add(\'psw-noimg\');this.remove()">'
                    : '';
  }
  function api(path, opts) {
    return fetch(API + path, opts).then(function (r) {
      return r.text().then(function (txt) { var body = null; try { body = txt ? JSON.parse(txt) : null; } catch (e) {} return { status: r.status, body: body }; });
    });
  }
  function toast(msg) { el.toast.textContent = msg; el.toast.classList.add('psw-show'); clearTimeout(toast.t); toast.t = setTimeout(function () { el.toast.classList.remove('psw-show'); }, 1800); }

  /* ---------------- styles ---------------- */
  var CSS = '\
.psw{--g:#345e4a;--gs:#e6efe9;--p:#c4517a;--ps:#fbe9ef;--ink:#2b2a28;--mut:#77736c;--line:#ebe5dc;--bad:#b3261e;--warn:#a86b00;color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;box-sizing:border-box}\n.psw-root{max-width:1180px;margin:0 auto;padding:0 16px}\
.psw *{box-sizing:border-box}.psw button,.psw input,.psw select,.psw textarea{font:inherit;color:inherit}\
.psw-top{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:14px;flex-wrap:wrap}\
.psw-langs{display:flex;border:1px solid var(--line);border-radius:999px;overflow:hidden;background:#fff}\
.psw-langs button{border:0;background:none;padding:6px 12px;cursor:pointer;font-size:13px;font-weight:600;color:var(--mut)}.psw-langs button.on{background:var(--g);color:#fff}\
.psw-btn{border:0;border-radius:10px;padding:10px 16px;cursor:pointer;font-weight:600;background:var(--g);color:#fff}.psw-btn:hover{filter:brightness(1.08)}.psw-btn:disabled{background:#c9c4bc;cursor:not-allowed}\
.psw-btn.ghost{background:transparent;color:var(--g);border:1px solid var(--g)}.psw-btn.sm{padding:6px 10px;font-size:13px}\
.psw-cartbtn{position:fixed;right:20px;bottom:20px;z-index:9990;box-shadow:0 6px 20px rgba(0,0,0,.18);border-radius:999px;padding:12px 18px}\
.psw-badge{display:inline-grid;place-items:center;min-width:22px;height:22px;margin-left:8px;border-radius:999px;background:var(--p);font-size:12px;padding:0 6px}\
.psw-filters{display:flex;flex-wrap:wrap;gap:10px;align-items:center;background:#fff;border:1px solid var(--line);border-radius:14px;padding:12px;margin-bottom:20px}\
.psw-filters input[type=search],.psw-filters select{border:1px solid var(--line);border-radius:10px;padding:8px 12px;background:#fff;min-width:0}.psw-filters input[type=search]{flex:1 1 200px}\
.psw-chips{display:flex;gap:6px;flex-wrap:wrap}.psw-chip{border:1px solid var(--line);background:#fff;border-radius:999px;padding:5px 12px;cursor:pointer;font-size:13px;display:flex;align-items:center;gap:6px}\
.psw-chip.on{border-color:var(--g);background:var(--gs);color:var(--g);font-weight:600}.psw-dot{width:10px;height:10px;border-radius:50%;border:1px solid rgba(0,0,0,.15)}\
.psw-check{display:flex;align-items:center;gap:6px;font-size:14px;cursor:pointer}\
.psw-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:18px}\
.psw-card{background:#fff;border:1px solid var(--line);border-radius:14px;overflow:hidden;box-shadow:0 2px 10px rgba(40,30,20,.06);display:flex;flex-direction:column;cursor:pointer;transition:transform .15s}.psw-card:hover{transform:translateY(-2px)}\
.psw-img{aspect-ratio:1/1;background:linear-gradient(135deg,#fbe9ef,#e6efe9);position:relative;overflow:hidden}.psw-img img{width:100%;height:100%;object-fit:cover;display:block}\
.psw-noimg:after{content:"🌸";position:absolute;inset:0;display:grid;place-items:center;font-size:64px}\
.psw-out .psw-img{filter:grayscale(.7);opacity:.75}\
.psw-tag{position:absolute;top:10px;left:10px;font-size:12px;font-weight:600;padding:3px 9px;border-radius:999px;background:#fff;color:var(--g);z-index:1}.psw-tag.no{background:var(--bad);color:#fff}.psw-tag.few{background:#fff4dc;color:var(--warn)}\
.psw-body{padding:12px 14px 14px;display:flex;flex-direction:column;gap:4px;flex:1}.psw-body h3{margin:0;font-size:16px}.psw-meta{font-size:13px;color:var(--mut)}\
.psw-price{font-weight:700;font-size:18px;margin-top:auto;display:flex;justify-content:space-between;align-items:center}\
.psw-empty{padding:40px;text-align:center;color:var(--mut);background:#fff;border-radius:14px;border:1px dashed var(--line);grid-column:1/-1}\
.psw-ov{position:fixed;inset:0;background:rgba(30,25,20,.45);z-index:9995;display:none;align-items:center;justify-content:center;padding:16px}.psw-ov.open{display:flex}\
.psw-modal{background:#fff;border-radius:18px;max-width:880px;width:100%;max-height:92vh;overflow:auto;display:grid;grid-template-columns:1fr 1fr;position:relative}\
.psw-modal .psw-img{aspect-ratio:auto;min-height:420px}.psw-info{padding:24px;display:flex;flex-direction:column;gap:10px}.psw-info h2{margin:0;font-size:24px;color:var(--g)}\
.psw-x{position:absolute;top:10px;right:10px;border:0;background:#fff;border-radius:50%;width:34px;height:34px;cursor:pointer;font-size:20px;box-shadow:0 2px 10px rgba(0,0,0,.1);z-index:2}\
.psw-qty{display:flex;align-items:center;border:1px solid var(--line);border-radius:10px;width:max-content}.psw-qty button{border:0;background:none;width:34px;height:34px;cursor:pointer;font-size:18px}.psw-qty span{min-width:28px;text-align:center;font-weight:600}\
.psw-care{background:var(--gs);border-radius:12px;padding:12px 14px;font-size:14px}.psw-care b{color:var(--g)}.psw-credit{font-size:11px;color:var(--mut)}.psw-credit a{color:var(--mut)}\
.psw-drawer{position:fixed;top:0;right:0;bottom:0;width:min(440px,100%);background:#fff;z-index:9999;transform:translateX(100%);transition:transform .25s;display:flex;flex-direction:column;box-shadow:-4px 0 24px rgba(0,0,0,.12)}.psw-drawer.open{transform:none}\
.psw-dh{display:flex;justify-content:space-between;align-items:center;padding:16px}.psw-dh h2{font-size:20px;margin:0;color:var(--g)}.psw-dc{padding:0 16px 16px;overflow:auto;flex:1}\
.psw-line{display:grid;grid-template-columns:56px 1fr auto;gap:10px;align-items:center;padding:10px 0;border-bottom:1px solid var(--line)}.psw-line .psw-img{width:56px;height:56px;border-radius:10px}\
.psw-rm{border:0;background:none;color:var(--bad);cursor:pointer;font-size:13px;padding:0}.psw-total{display:flex;justify-content:space-between;font-weight:700;font-size:18px;padding:14px 0}\
.psw-f{display:flex;flex-direction:column;gap:4px;margin-bottom:12px}.psw-f label{font-size:13px;font-weight:600}.psw-f input,.psw-f textarea{border:1px solid var(--line);border-radius:10px;padding:9px 12px;background:#fff}\
.psw-bad input,.psw-bad textarea{border-color:var(--bad)}.psw-err{color:var(--bad);font-size:12px}\
.psw-radio{display:flex;gap:8px}.psw-radio label{flex:1;border:1px solid var(--line);border-radius:10px;padding:10px;cursor:pointer;font-weight:500;display:flex;gap:8px;align-items:flex-start}.psw-radio label.on{border-color:var(--g);background:var(--gs)}\
.psw-hint{font-size:12px;color:var(--mut)}.psw-ok{text-align:center;padding:30px 10px}.psw-num{font-size:28px;font-weight:800;color:var(--g);margin:8px 0}\
.psw-toast{position:fixed;bottom:84px;left:50%;transform:translateX(-50%);background:var(--ink);color:#fff;padding:10px 18px;border-radius:999px;z-index:10000;font-size:14px;opacity:0;transition:opacity .2s;pointer-events:none}.psw-toast.psw-show{opacity:1}\
.psw-ai{background:var(--p)}.psw-ai[hidden]{display:none}\
.psw-aibar{background:var(--ps);border-radius:14px;padding:12px 14px;margin-bottom:16px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}.psw-aibar[hidden]{display:none}\
.psw-aibar b{color:var(--p)}.psw-aibar .psw-hint{margin-top:2px}\
@media (max-width:820px){.psw-modal{display:block}.psw-modal .psw-img{min-height:0;height:300px}}';

  /* ---------------- skeleton ---------------- */
  function mount() {
    root = document.getElementById(script.dataset.target || 'pelargonium-catalog');
    if (!root) { root = document.createElement('div'); script.parentNode.insertBefore(root, script); }
    var style = document.createElement('style'); style.textContent = CSS; document.head.appendChild(style);
    root.className = 'psw psw-root';
    root.innerHTML =
      '<div class="psw-top"><div class="psw-langs" ' + (showSwitch ? '' : 'hidden') + '>' +
      LANGS.map(function (l) { return '<button data-l="' + l + '">' + (l === 'kk' ? 'KZ' : l.toUpperCase()) + '</button>'; }).join('') + '</div></div>' +
      '<div class="psw-filters"><input type="search" data-r="q" maxlength="400"><button class="psw-btn psw-ai" data-r="aiBtn" data-act="ai" hidden></button><select data-r="type"></select><div class="psw-chips" data-r="colors"></div>' +
      '<label class="psw-check"><input type="checkbox" data-r="stock"> <span data-r="stockLbl"></span></label><select data-r="sort"></select></div>' +
      '<div class="psw-aibar" data-r="aiBar" hidden></div><div class="psw-grid" data-r="grid"></div>' +
      '<button class="psw-btn psw-cartbtn" data-r="cartBtn"><span data-r="cartLbl"></span><span class="psw-badge" data-r="count">0</span></button>' +
      '<div class="psw-ov" data-r="modalOv"><div class="psw-modal"><button class="psw-x" data-act="closeModal">×</button><div class="psw-img" data-r="mImg"></div><div class="psw-info" data-r="mInfo"></div></div></div>' +
      '<div class="psw-ov" data-r="cartOv"></div>' +
      '<aside class="psw-drawer" data-r="drawer"><div class="psw-dh"><h2 data-r="dTitle"></h2><button class="psw-x" style="position:static" data-act="closeCart">×</button></div><div class="psw-dc" data-r="dContent"></div></aside>' +
      '<div class="psw-toast" data-r="toast"></div>';
    root.querySelectorAll('[data-r]').forEach(function (n) { el[n.dataset.r] = n; });
    // the floating cart and overlays must escape Tilda's block containers
    [el.cartBtn, el.modalOv, el.cartOv, el.drawer, el.toast].forEach(function (n) { n.classList.add('psw'); document.body.appendChild(n); });
    bind();
  }

  function bind() {
    root.querySelector('.psw-langs').addEventListener('click', function (e) {
      var l = e.target.dataset.l; if (!l) return;
      if (view === 'form') saveDraft();
      lang = l; store.set('lang', l); renderStatic(); renderAiBar(); renderGrid(); renderCount();
      if (el.drawer.classList.contains('open')) renderCart();
      if (modalId) renderModal();
    });
    var timer;
    el.q.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(function () { state.q = el.q.value; load(); }, 250); });
    // Enter runs the smart search when the model is ready; typing goes back to the regular search by name
    el.q.addEventListener('keydown', function (e) { if (e.key === 'Enter' && aiReady && el.q.value.trim()) { e.preventDefault(); clearTimeout(timer); runAI(); } });
    el.type.addEventListener('change', function () { state.type = el.type.value; load(); });
    el.sort.addEventListener('change', function () { state.sort = el.sort.value; load(); });
    el.stock.addEventListener('change', function () { state.stock = el.stock.checked; load(); });
    el.cartBtn.addEventListener('click', openCart);
    el.cartOv.addEventListener('click', closeCart);
    el.modalOv.addEventListener('click', function (e) { if (e.target === el.modalOv) closeModal(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') { closeModal(); closeCart(); } });
    // one delegated handler for all buttons with data-act
    document.addEventListener('click', function (e) {
      var b = e.target.closest('[data-act]'); if (!b || !b.closest('.psw')) return;
      var a = b.dataset.act, id = +b.dataset.id;
      if (a === 'open') openModal(id);
      else if (a === 'add') { e.stopPropagation(); addToCart(id, 1); }
      else if (a === 'color') { var i = state.colors.indexOf(b.dataset.c); i >= 0 ? state.colors.splice(i, 1) : state.colors.push(b.dataset.c); renderColors(); load(); }
      else if (a === 'reset') { state = { q: '', type: '', colors: [], stock: false, sort: 'default' }; el.q.value = ''; el.stock.checked = false; renderStatic(); load(); }
      else if (a === 'retry') load();
      else if (a === 'ai') runAI();
      else if (a === 'aiOff') { el.q.value = ''; state.q = ''; load(); }
      else if (a === 'closeModal') closeModal();
      else if (a === 'closeCart') closeCart();
      else if (a === 'mMinus') { modalQty = Math.max(1, modalQty - 1); renderModal(); }
      else if (a === 'mPlus') { modalQty = Math.min(known[modalId].stock, modalQty + 1); renderModal(); }
      else if (a === 'mAdd') { addToCart(modalId, modalQty); closeModal(); }
      else if (a === 'qty') setQty(id, +b.dataset.q);
      else if (a === 'checkout') { view = 'form'; renderCart(); }
      else if (a === 'back') { saveDraft(); view = 'cart'; renderCart(); }
      else if (a === 'done') closeCart();
    });
  }

  /* ---------------- catalog ---------------- */
  function renderStatic() {
    root.querySelectorAll('.psw-langs button').forEach(function (b) { b.classList.toggle('on', b.dataset.l === lang); });
    el.q.placeholder = aiReady ? t('searchAi') : t('search');
    el.aiBtn.textContent = t('aiBtn'); el.aiBtn.hidden = !aiReady;
    el.type.innerHTML = '<option value="">' + esc(t('allTypes')) + '</option>' + TYPES.map(function (k) { return '<option value="' + k + '">' + esc(t('types')[k]) + '</option>'; }).join('');
    el.type.value = state.type;
    el.sort.innerHTML = [['default', 'sortDefault'], ['price_asc', 'sortPriceAsc'], ['price_desc', 'sortPriceDesc'], ['name', 'sortName']]
      .map(function (o) { return '<option value="' + o[0] + '">' + esc(t(o[1])) + '</option>'; }).join('');
    el.sort.value = state.sort;
    el.stockLbl.textContent = t('onlyInStock');
    el.cartLbl.textContent = t('cart');
    renderColors();
  }
  function renderColors() {
    el.colors.innerHTML = Object.keys(COLORS).map(function (k) {
      return '<button class="psw-chip ' + (state.colors.indexOf(k) >= 0 ? 'on' : '') + '" data-act="color" data-c="' + k + '"><span class="psw-dot" style="background:' + COLORS[k] + '"></span>' + esc(t('colors')[k]) + '</button>';
    }).join('');
  }
  function query() {
    var p = new URLSearchParams();
    if (state.q.trim()) p.set('q', state.q.trim());
    if (state.type) p.set('type', state.type);
    state.colors.forEach(function (c) { p.append('color', c); });
    if (state.stock) p.set('in_stock', 'true');
    if (state.sort !== 'default') p.set('sort', state.sort);
    return p.toString();
  }
  var loadSeq = 0;
  function load() {
    var seq = ++loadSeq;
    ai = null; aiSeq++; renderAiBar();
    if (!list.length) el.grid.innerHTML = '<div class="psw-empty">' + esc(t('loading')) + '</div>';
    return api('/api/varieties?' + query()).then(function (r) {
      if (seq !== loadSeq) return;  // a newer request already answered
      if (r.status !== 200) throw new Error();
      list = r.body; list.forEach(function (v) { known[v.id] = v; });
      renderGrid(); renderCount();
    }).catch(function () {
      if (seq !== loadSeq) return;
      el.grid.innerHTML = '<div class="psw-empty">' + esc(t('errLoad')) + '<br><br><button class="psw-btn ghost sm" data-act="retry">' + esc(t('retry')) + '</button></div>';
    });
  }
  function stockTag(v) {
    if (v.stock <= 0) return '<span class="psw-tag no">' + esc(t('outStock')) + '</span>';
    if (v.stock <= 2) return '<span class="psw-tag few">' + esc(t('few')) + ' ' + v.stock + ' ' + esc(t('pcs')) + '</span>';
    return '<span class="psw-tag">' + esc(t('inStock')) + '</span>';
  }
  function renderGrid() {
    if (ai && !list.length) {
      var msg = ai.status === 'clarify' ? t('aiClarify') : t('aiNone');
      el.grid.innerHTML = '<div class="psw-empty">' + esc(msg) + '<br><br><button class="psw-btn ghost sm" data-act="aiOff">' + esc(t('aiShowAll')) + '</button></div>'; return;
    }
    if (!list.length) {
      var hint = aiReady && state.q.trim() ? '<br><br>' + esc(t('aiHint')) + ' <button class="psw-btn psw-ai sm" data-act="ai">' + esc(t('aiBtn')) + '</button>' : '';
      el.grid.innerHTML = '<div class="psw-empty">' + esc(t('nothing')) + hint + '<br><br><button class="psw-btn ghost sm" data-act="reset">' + esc(t('resetFilters')) + '</button></div>'; return;
    }
    el.grid.innerHTML = list.map(function (v) {
      return '<article class="psw-card ' + (v.stock <= 0 ? 'psw-out' : '') + '" data-act="open" data-id="' + v.id + '">' +
        '<div class="psw-img' + (photo(v) ? '' : ' psw-noimg') + '">' + imgHtml(v) + stockTag(v) + '</div>' +
        '<div class="psw-body"><h3>' + esc(v.name) + '</h3><div class="psw-meta">' + esc(t('types')[v.type]) + ' · ' + esc(t('colors')[v.color]) + '</div>' +
        '<div class="psw-price">' + money(v.price) + '<button class="psw-btn sm" data-act="add" data-id="' + v.id + '"' + (v.stock <= 0 ? ' disabled' : '') + '>' + esc(t('addToCart')) + '</button></div></div></article>';
    }).join('');
  }

  /* ---------------- smart search (AI) ---------------- */
  function renderAiBar() {
    if (!ai) { el.aiBar.hidden = true; return; }
    el.aiBar.hidden = false;
    el.aiBar.innerHTML = ai.loading
      ? '<div>' + esc(t('aiThinking')) + '</div>'
      : '<div><div>' + (ai.fallback ? esc(t('aiFallback')) : esc(t('aiFound')) + ' <b>«' + esc(ai.q) + '»</b>') + '</div>' +
        (ai.fallback ? '' : '<div class="psw-hint">' + esc(t('aiNote')) + '</div>') + '</div>' +
        '<button class="psw-btn ghost sm" data-act="aiOff">' + esc(t('aiShowAll')) + '</button>';
  }
  function runAI() {
    var q = el.q.value.trim(); if (!q) { el.q.focus(); return; }
    var seq = ++aiSeq; loadSeq++;  // drop any regular search still in flight
    ai = { q: q, loading: true }; renderAiBar(); el.aiBtn.disabled = true;
    api('/api/search?q=' + encodeURIComponent(q)).then(function (r) {
      if (seq !== aiSeq) return;
      if (r.status !== 200) throw new Error();
      ai = { q: q, status: r.body.status, fallback: r.body.fallback };
      list = r.body.items; list.forEach(function (v) { known[v.id] = v; });
      renderAiBar(); renderGrid();
    }).catch(function () {
      if (seq !== aiSeq) return;
      ai = null; renderAiBar(); state.q = q; load();
    }).then(function () { el.aiBtn.disabled = false; });
  }

  /* ---------------- product modal ---------------- */
  function openModal(id) { modalId = id; modalQty = 1; renderModal(); el.modalOv.classList.add('open'); }
  function closeModal() { el.modalOv.classList.remove('open'); modalId = null; }
  function renderModal() {
    var v = known[modalId]; if (!v) return;
    el.mImg.className = 'psw-img' + (photo(v) ? '' : ' psw-noimg');
    el.mImg.innerHTML = imgHtml(v, true);
    var c = v.photo_credit;
    el.mInfo.innerHTML =
      '<div class="psw-meta">' + esc(t('types')[v.type]) + ' · ' + esc(t('colors')[v.color]) + '</div><h2>' + esc(v.name) + '</h2>' +
      '<div style="font-size:24px;font-weight:800">' + money(v.price) + '</div>' +
      (v.stock > 0 ? '<div style="color:var(--g);font-weight:600">' + esc(t('inStock')) + ': ' + v.stock + ' ' + esc(t('pcs')) + '</div>'
                   : '<div style="color:var(--bad);font-weight:600">' + esc(t('outStock')) + '</div>') +
      '<p style="margin:0">' + esc(v.description[lang] || v.description.ru) + '</p>' +
      (c ? '<div class="psw-credit">' + esc(t('photoBy')) + ': ' + (c.source_url ? '<a href="' + esc(c.source_url) + '" target="_blank" rel="noopener">' + esc(c.author) + '</a>' : esc(c.author)) + ', ' + esc(c.license) + ', Wikimedia Commons</div>' : '') +
      '<div class="psw-care"><b>' + esc(t('types')[v.type]) + '.</b> ' + esc(t('typeDesc')[v.type]) + '<br><br><b>' + esc(t('careFor')) + ':</b> ' + esc(t('typeCare')[v.type]) + '</div>' +
      (v.stock > 0 ? '<div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-top:6px"><div class="psw-qty"><button data-act="mMinus">−</button><span>' + modalQty + '</span><button data-act="mPlus">+</button></div>' +
        '<button class="psw-btn" data-act="mAdd">' + esc(t('addToCart')) + ' · ' + money(v.price * modalQty) + '</button></div>' : '');
  }

  /* ---------------- cart ---------------- */
  function lines() { return Object.keys(cart).map(function (id) { return { v: known[id], q: cart[id] }; }).filter(function (l) { return l.v; }); }
  function total() { return lines().reduce(function (s, l) { return s + l.v.price * l.q; }, 0); }
  function renderCount() { el.count.textContent = lines().reduce(function (s, l) { return s + l.q; }, 0); }
  function saveCart() { store.set('cart', cart); renderCount(); }
  function addToCart(id, n) {
    var v = known[id], have = cart[id] || 0;
    if (!v || have + n > v.stock) { toast(t('maxStock')); return; }
    cart[id] = have + n; saveCart(); toast(t('added'));
  }
  function setQty(id, n) {
    var v = known[id];
    if (n <= 0 || !v) delete cart[id]; else cart[id] = Math.min(n, v.stock);
    saveCart(); renderCart();
  }
  function openCart() { view = 'cart'; renderCart(); el.drawer.classList.add('open'); el.cartOv.classList.add('open'); }
  function closeCart() { el.drawer.classList.remove('open'); el.cartOv.classList.remove('open'); }

  function renderCart() {
    var c = el.dContent;
    if (view === 'success') {
      el.dTitle.textContent = t('successTitle');
      c.innerHTML = '<div class="psw-ok"><div style="font-size:48px">🌸</div><p>' + esc(t('successText')) + '</p><div class="psw-num">' + esc(lastOrder.number) + '</div><p class="psw-hint">' + esc(t('successNext')) + '</p><br><button class="psw-btn" data-act="done">' + esc(t('continueShop')) + '</button></div>';
      return;
    }
    var ls = lines();
    if (view === 'cart') {
      el.dTitle.textContent = t('cartTitle');
      if (!ls.length) { c.innerHTML = '<div class="psw-empty">' + esc(t('cartEmpty')) + '</div>'; return; }
      c.innerHTML = ls.map(function (l) {
        return '<div class="psw-line"><div class="psw-img' + (photo(l.v) ? '' : ' psw-noimg') + '">' + imgHtml(l.v) + '</div><div><b>' + esc(l.v.name) + '</b><div class="psw-meta">' + money(l.v.price) + '</div>' +
          '<div style="display:flex;gap:10px;align-items:center;margin-top:4px"><div class="psw-qty"><button data-act="qty" data-id="' + l.v.id + '" data-q="' + (l.q - 1) + '">−</button><span>' + l.q + '</span><button data-act="qty" data-id="' + l.v.id + '" data-q="' + (l.q + 1) + '">+</button></div>' +
          '<button class="psw-rm" data-act="qty" data-id="' + l.v.id + '" data-q="0">✕</button></div></div><b>' + money(l.v.price * l.q) + '</b></div>';
      }).join('') +
        '<div class="psw-total"><span>' + esc(t('total')) + '</span><span>' + money(total()) + '</span></div><button class="psw-btn" style="width:100%" data-act="checkout">' + esc(t('checkout')) + '</button>';
      return;
    }
    el.dTitle.textContent = t('orderTitle');
    var d = draft || { name: '', phone: '', delivery: 'pickup', address: '', comment: '' };
    var radio = function (val, title, text) {
      return '<label class="' + (d.delivery === val ? 'on' : '') + '"><input type="radio" name="psw-del" value="' + val + '"' + (d.delivery === val ? ' checked' : '') + '><span><b>' + esc(t(title)) + '</b><br><span class="psw-hint">' + esc(t(text)) + '</span></span></label>';
    };
    c.innerHTML =
      '<button class="psw-rm" style="color:var(--g);margin-bottom:12px" data-act="back">' + esc(t('back')) + '</button>' +
      '<div style="border:1px solid var(--line);border-radius:12px;padding:12px;margin-bottom:14px">' + ls.map(function (l) {
        return '<div style="display:flex;justify-content:space-between;font-size:14px"><span>' + esc(l.v.name) + ' × ' + l.q + '</span><span>' + money(l.v.price * l.q) + '</span></div>';
      }).join('') + '<div style="display:flex;justify-content:space-between;font-weight:700;margin-top:6px"><span>' + esc(t('total')) + '</span><span>' + money(total()) + '</span></div></div>' +
      '<form novalidate>' +
      '<div class="psw-f" data-f="name"><label>' + esc(t('name')) + ' *</label><input name="name" value="' + esc(d.name) + '" autocomplete="name"><span class="psw-err"></span></div>' +
      '<div class="psw-f" data-f="phone"><label>' + esc(t('phone')) + ' *</label><input name="phone" type="tel" value="' + esc(d.phone) + '" placeholder="+7 7__ ___ __ __" autocomplete="tel"><span class="psw-err"></span></div>' +
      '<div class="psw-f"><label>' + esc(t('delivery')) + ' *</label><div class="psw-radio">' + radio('pickup', 'pickup', 'pickupText') + radio('courier', 'courier', 'courierText') + '</div></div>' +
      (d.delivery === 'courier' ? '<div class="psw-f" data-f="address"><label>' + esc(t('address')) + ' *</label><input name="address" value="' + esc(d.address) + '" autocomplete="street-address"><span class="psw-err"></span></div>' : '') +
      '<div class="psw-f"><label>' + esc(t('comment')) + '</label><textarea name="comment" rows="2" placeholder="' + esc(t('commentPh')) + '">' + esc(d.comment) + '</textarea></div>' +
      '<div class="psw-err" data-f="general" style="margin-bottom:8px"></div><button class="psw-btn" style="width:100%">' + esc(t('send')) + '</button></form>';
    var form = c.querySelector('form');
    form.addEventListener('change', function (e) { if (e.target.name === 'psw-del') { saveDraft(); renderCart(); } });
    form.addEventListener('submit', submit);
    phoneMask(form.elements.phone);
  }
  function saveDraft() {
    var f = el.dContent.querySelector('form'); if (!f) return;
    var val = function (n) { return f.elements[n] ? f.elements[n].value : ''; };
    var del = f.querySelector('input[name=psw-del]:checked');
    draft = { name: val('name'), phone: val('phone'), delivery: del ? del.value : 'pickup', address: val('address'), comment: val('comment') };
  }
  /* ---------------- phone mask: "87011234567" → "+7 701 123 45 67" while typing ---------------- */
  // national part = the 10 digits after +7; all Kazakh mobile numbers start with 7 (70x, 74x, 77x)
  function nationalDigits(value) {
    var d = value.replace(/\D/g, '');
    if (/^\s*\+7/.test(value)) d = d.slice(1);            // "+7 ..." — the 7 is the country code
    else if (d.length === 11 || d.charAt(0) === '8') d = d.slice(1); // "8 701 ...", "7 701 ..."
    if (d.charAt(0) === '8') d = d.slice(1);               // "+7 8 701..." — habit of typing 8
    return d.slice(0, 10);                                  // extra digits are ignored
  }
  function formatPhone(nat) {
    var parts = [nat.slice(0, 3), nat.slice(3, 6), nat.slice(6, 8), nat.slice(8, 10)].filter(Boolean);
    return '+7 ' + parts.join(' ');
  }
  function phoneMask(input) {
    if (!input) return;
    var apply = function () {
      var caret = input.selectionStart, before = input.value.slice(0, caret);
      var digitsBefore = nationalDigits(before).length;   // where the caret is, counted in national digits
      var nat = nationalDigits(input.value);
      input.value = formatPhone(nat);
      // put the caret back after the same number of digits
      var pos = 3, seen = 0;
      while (pos < input.value.length && seen < digitsBefore) { if (/\d/.test(input.value[pos])) seen++; pos++; }
      if (document.activeElement === input) input.setSelectionRange(pos, pos);
      if (nat.length === 10) setErr('phone', '');           // fixed the number — drop the old error
    };
    input.addEventListener('focus', function () { if (!input.value) { input.value = '+7 '; } });
    input.addEventListener('blur', function () { if (input.value.trim() === '+7') input.value = ''; });
    input.addEventListener('input', apply);
    input.addEventListener('keydown', function (e) {
      var p = input.selectionStart;
      if (input.selectionStart !== input.selectionEnd) return;
      // don't let Backspace eat "+7 " or get stuck on a space
      if (e.key === 'Backspace' && p <= 3) { e.preventDefault(); return; }
      if (e.key === 'Backspace' && input.value[p - 1] === ' ') input.setSelectionRange(p - 1, p - 1);
    });
    if (input.value) input.value = formatPhone(nationalDigits(input.value));
  }

  function normPhone(p) {
    var d = p.replace(/\D/g, '');
    if (d.length === 11 && (d[0] === '8' || d[0] === '7')) d = d.slice(1);
    return d.length === 10 ? '+7' + d : null;
  }
  function setErr(field, msg) {
    var f = el.dContent.querySelector('[data-f="' + field + '"]'); if (!f) return;
    if (field === 'general') { f.textContent = msg || ''; return; }
    f.classList.toggle('psw-bad', !!msg); f.querySelector('.psw-err').textContent = msg || '';
  }
  function submit(e) {
    e.preventDefault(); saveDraft();
    var d = draft, ok = true;
    var check = function (field, bad, msg) { setErr(field, bad ? msg : ''); if (bad) ok = false; };
    check('name', d.name.trim().length < 2, t('errName'));
    check('phone', !normPhone(d.phone), t('errPhone'));
    if (d.delivery === 'courier') check('address', d.address.trim().length < 5, t('errAddress'));
    setErr('general', '');
    if (!ok || !lines().length) return;

    var btn = el.dContent.querySelector('form .psw-btn'); btn.disabled = true;
    api('/api/orders', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: d.name.trim(), phone: d.phone, delivery: d.delivery, address: d.address, comment: d.comment, lang: lang,
        items: lines().map(function (l) { return { variety_id: l.v.id, qty: l.q }; }) })
    }).then(function (r) {
      if (r.status === 201) {
        lastOrder = r.body; cart = {}; saveCart(); draft = null; view = 'success'; renderCart(); load();
        return;
      }
      btn.disabled = false;
      var code = r.body && r.body.detail && r.body.detail.code;
      if (r.status === 409 && code === 'out_of_stock') {
        setErr('general', t('errStock') + ': ' + r.body.detail.items.map(function (i) { return i.name; }).join(', '));
        load();
      } else if (r.status === 422 && Array.isArray(r.body && r.body.detail)) {
        r.body.detail.forEach(function (err) {
          var f = err.loc[err.loc.length - 1];
          if (f === 'name') setErr('name', t('errName'));
          else if (f === 'phone') setErr('phone', t('errPhone'));
          else if (/address/.test(err.msg)) setErr('address', t('errAddress'));
          else setErr('general', t('errServer'));
        });
      } else setErr('general', t('errServer'));
    }).catch(function () { btn.disabled = false; setErr('general', t('errServer')); });
  }

  /* ---------------- start ---------------- */
  function start() {
    mount();
    fetch(API + '/static/i18n.json').then(function (r) { return r.json(); }).then(function (dict) {
      T = dict; renderStatic();
      // the smart-search button appears only when the server says the model is ready
      api('/api/search/status').then(function (r) { aiReady = !!(r.status === 200 && r.body.ready); renderStatic(); }).catch(function () {});
      // the cart may hold varieties hidden by current filters: load the full list once
      return api('/api/varieties').then(function (r) { if (r.status === 200) r.body.forEach(function (v) { known[v.id] = v; }); renderCount(); });
    }).then(load).catch(function () {
      el.grid.innerHTML = '<div class="psw-empty">Pelargonium Shop: API ' + esc(API) + ' недоступен / unavailable</div>';
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
