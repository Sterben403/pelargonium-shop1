/* Owner workspace: orders register + catalog management, talks to /api/admin/*. */
(function () {
  'use strict';
  var TYPES = ['zonal', 'rosebud', 'ivy', 'star', 'regal', 'angel'];
  var COLORS = ['pink', 'red', 'white', 'purple', 'salmon'];
  var STATUSES = ['new', 'confirmed', 'ready', 'done', 'cancelled'];
  var EXTRA = {
    ru: { errServer: 'Ошибка сервера, попробуйте ещё раз', fileTooLarge: 'Файл слишком большой (до 8 МБ)', sessionEnded: 'Сессия истекла — войдите снова' },
    kk: { errServer: 'Сервер қатесі, қайталап көріңіз', fileTooLarge: 'Файл тым үлкен (8 МБ дейін)', sessionEnded: 'Сессия аяқталды — қайта кіріңіз' },
    en: { errServer: 'Server error, please try again', fileTooLarge: 'File is too large (max 8 MB)', sessionEnded: 'Session expired — please sign in again' }
  };
  var $ = function (id) { return document.getElementById(id); };
  var store = {
    get: function (s, k, d) { try { var v = s.getItem('psa_' + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
    set: function (s, k, v) { try { v == null ? s.removeItem('psa_' + k) : s.setItem('psa_' + k, JSON.stringify(v)); } catch (e) {} }
  };
  var T, lang = store.get(localStorage, 'lang', 'ru'), token = store.get(sessionStorage, 'token', null);
  var orders = [], varieties = [], oStatus = '', newFile = null;

  function t(k) { return (EXTRA[lang] && EXTRA[lang][k]) || (T[lang][k] != null ? T[lang][k] : T.ru[k]); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function money(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ' ') + ' ₸'; }
  function fmtPhone(p) { return p.replace(/^\+7(\d{3})(\d{3})(\d{2})(\d{2})$/, '+7 $1 $2 $3 $4'); }
  function toast(m) { var el = $('toast'); el.textContent = m; el.classList.add('show'); clearTimeout(toast.t); toast.t = setTimeout(function () { el.classList.remove('show'); }, 2000); }

  function api(method, path, body, isForm) {
    var headers = {};
    if (token) headers.Authorization = 'Bearer ' + token;
    if (body && !isForm) headers['Content-Type'] = 'application/json';
    return fetch(path, { method: method, headers: headers, body: body ? (isForm ? body : JSON.stringify(body)) : undefined })
      .then(function (r) {
        if (r.status === 401 && path !== '/api/admin/login') { logout(); toast(t('sessionEnded')); throw new Error('401'); }
        return r.text().then(function (x) { var b = null; try { b = x ? JSON.parse(x) : null; } catch (e) {} return { status: r.status, body: b }; });
      });
  }

  /* ---------- i18n ---------- */
  function applyI18n() {
    document.documentElement.lang = lang;
    document.querySelectorAll('[data-i]').forEach(function (n) { n.textContent = t(n.dataset.i); });
    document.querySelectorAll('[data-ph]').forEach(function (n) { n.placeholder = t(n.dataset.ph); });
    document.querySelectorAll('#langs button').forEach(function (b) { b.classList.toggle('on', b.dataset.l === lang); });
    var f = $('addForm');
    f.elements.type.innerHTML = TYPES.map(function (k) { return '<option value="' + k + '">' + esc(t('types')[k]) + '</option>'; }).join('');
    f.elements.color.innerHTML = COLORS.map(function (k) { return '<option value="' + k + '">' + esc(t('colors')[k]) + '</option>'; }).join('');
    $('guideList').innerHTML = t('guide').map(function (g) { return '<li>' + esc(g) + '</li>'; }).join('');
    if (token) renderAll();
  }

  /* ---------- auth ---------- */
  function showPanel() {
    $('login').hidden = !!token; $('panel').hidden = !token; $('logoutBtn').hidden = !token;
    if (token) refresh(); else setTimeout(function () { $('pw').focus(); }, 30);
  }
  function logout() { token = null; store.set(sessionStorage, 'token', null); showPanel(); }
  $('logoutBtn').onclick = logout;
  $('login').onsubmit = function (e) {
    e.preventDefault();
    api('POST', '/api/admin/login', { password: $('pw').value }).then(function (r) {
      if (r.status === 200) { token = r.body.token; store.set(sessionStorage, 'token', token); $('pw').value = ''; $('pwErr').textContent = ''; $('pwF').classList.remove('bad'); showPanel(); }
      else { $('pwErr').textContent = t('errPw'); $('pwF').classList.add('bad'); }
    });
  };

  /* ---------- data ---------- */
  function refresh() {
    return Promise.all([
      api('GET', '/api/admin/orders' + (oStatus ? '?status=' + oStatus : '')),
      api('GET', '/api/admin/varieties'),
      api('GET', '/api/admin/stats'),
      api('GET', '/api/admin/orders')
    ]).then(function (res) {
      orders = res[0].body; varieties = res[1].body; refresh.stats = res[2].body; refresh.all = res[3].body;
      renderAll();
    }).catch(function () {});
  }
  function renderAll() { if (!refresh.stats) return; renderKpis(); renderOrders(); renderItems(); }

  function renderKpis() {
    var s = refresh.stats;
    $('kpis').innerHTML = [[t('kNew'), s.new_orders], [t('kActive'), s.in_progress], [t('kRevenue'), money(s.revenue_done)], [t('kOut'), s.out_of_stock]]
      .map(function (k) { return '<div class="box"><b>' + esc(k[1]) + '</b><span class="meta">' + esc(k[0]) + '</span></div>'; }).join('');
  }
  function renderOrders() {
    var all = refresh.all || [];
    $('oFilter').innerHTML = [''].concat(STATUSES).map(function (s) {
      var n = s ? all.filter(function (o) { return o.status === s; }).length : all.length;
      return '<button class="chip ' + (oStatus === s ? 'on' : '') + '" data-s="' + s + '">' + esc(s ? t('statuses')[s] : t('all')) + ' (' + n + ')</button>';
    }).join('');
    var locale = lang === 'en' ? 'en-GB' : 'ru-RU';
    $('ordersBody').innerHTML = orders.length ? orders.map(function (o) {
      return '<tr><td><b>' + esc(o.number) + '</b></td>' +
        '<td>' + new Date(o.created_at).toLocaleString(locale, { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) + '</td>' +
        '<td>' + esc(o.customer_name) + '<br><a href="tel:' + esc(o.phone) + '">' + esc(fmtPhone(o.phone)) + '</a>' + (o.comment ? '<div class="meta">💬 ' + esc(o.comment) + '</div>' : '') + '</td>' +
        '<td>' + o.items.map(function (i) { return esc(i.name) + ' × ' + i.qty; }).join('<br>') + '</td>' +
        '<td>' + (o.delivery === 'courier' ? esc(t('courier')) + '<div class="meta">' + esc(o.address) + '</div>' : esc(t('pickup'))) + '</td>' +
        '<td style="white-space:nowrap">' + money(o.total) + '</td>' +
        '<td><span class="st st-' + o.status + '">' + esc(t('statuses')[o.status]) + '</span><br><select style="margin-top:6px" data-order="' + o.id + '">' +
        STATUSES.map(function (s) { return '<option value="' + s + '"' + (s === o.status ? ' selected' : '') + '>' + esc(t('statuses')[s]) + '</option>'; }).join('') + '</select></td></tr>';
    }).join('') : '<tr><td colspan="7" class="meta" style="text-align:center;padding:30px">' + esc(t('noOrders')) + '</td></tr>';
  }
  function photoSrc(v) { return v.photo_url || ''; }
  function renderItems() {
    $('itemsBody').innerHTML = varieties.map(function (v) {
      return '<tr data-id="' + v.id + '"><td style="min-width:200px"><div style="display:flex;gap:10px;align-items:center"><div class="thumb">' +
        (photoSrc(v) ? '<img src="' + esc(photoSrc(v)) + '" alt="" loading="lazy">' : '🌸') + '</div><div><b>' + esc(v.name) + '</b><div class="meta">' + esc(t('types')[v.type]) + '</div>' +
        '<label class="photobtn">📷 ' + esc(t('changePhoto')) + '<input type="file" accept="image/*" hidden data-photo="' + v.id + '"></label></div></div></td>' +
        '<td style="width:110px"><input type="number" min="1" step="100" data-k="price" value="' + v.price + '"></td>' +
        '<td style="width:100px"><input type="number" min="0" data-k="stock" value="' + v.stock + '"></td>' +
        '<td style="min-width:260px"><textarea data-k="desc_ru">' + esc(v.description.ru) + '</textarea></td>' +
        '<td style="white-space:nowrap"><button class="btn sm" data-save="' + v.id + '">' + esc(t('save')) + '</button> <button class="btn sm danger" data-del="' + v.id + '" title="' + esc(t('delete')) + '">✕</button></td></tr>';
    }).join('');
  }

  /* ---------- actions ---------- */
  $('oFilter').onclick = function (e) { var b = e.target.closest('[data-s]'); if (!b) return; oStatus = b.dataset.s; refresh(); };
  $('ordersBody').onchange = function (e) {
    var id = e.target.dataset.order; if (!id) return;
    api('PATCH', '/api/admin/orders/' + id, { status: e.target.value }).then(function (r) {
      if (r.status === 200) { toast(t('saved')); refresh(); }
      else { toast(r.body && r.body.detail && r.body.detail.code === 'out_of_stock' ? t('errStock') : t('errServer')); refresh(); }
    });
  };
  $('itemsBody').onclick = function (e) {
    var save = e.target.dataset.save, del = e.target.dataset.del;
    if (save) {
      var row = e.target.closest('tr'), val = function (k) { return row.querySelector('[data-k="' + k + '"]').value; };
      var price = parseInt(val('price'), 10), stock = parseInt(val('stock'), 10);
      if (!(price > 0)) { toast(t('errPrice')); return; }
      api('PATCH', '/api/admin/varieties/' + save, { price: price, stock: Math.max(0, stock || 0), desc_ru: val('desc_ru') })
        .then(function (r) { toast(r.status === 200 ? t('saved') : t('errServer')); refresh(); });
    }
    if (del) {
      var v = varieties.find(function (x) { return x.id === +del; });
      if (!confirm(t('confirmDelete').replace('{name}', v.name))) return;
      api('DELETE', '/api/admin/varieties/' + del).then(function (r) { toast(r.status === 204 ? t('deleted') : t('errServer')); refresh(); });
    }
  };
  $('itemsBody').onchange = function (e) {
    var id = e.target.dataset.photo; if (!id || !e.target.files[0]) return;
    uploadPhoto(id, e.target.files[0]).then(function (ok) { if (ok) toast(t('saved')); refresh(); });
  };
  function uploadPhoto(id, file) {
    var fd = new FormData(); fd.append('file', file);
    return api('POST', '/api/admin/varieties/' + id + '/photo', fd, true).then(function (r) {
      if (r.status === 200) return true;
      toast(r.status === 413 ? t('fileTooLarge') : t('badPhoto')); return false;
    });
  }

  $('addBtn').onclick = function () { $('addForm').hidden = false; $('addForm').elements.name.focus(); };
  $('cancelAdd').onclick = resetAdd;
  function resetAdd() {
    var f = $('addForm'); f.reset(); f.hidden = true; newFile = null; $('preview').innerHTML = '📷'; $('addErr').textContent = '';
    f.querySelectorAll('.bad').forEach(function (n) { n.classList.remove('bad'); }); f.querySelectorAll('.err').forEach(function (n) { n.textContent = ''; });
  }
  $('newFile').onchange = function (e) {
    newFile = e.target.files[0] || null;
    $('preview').innerHTML = newFile ? '<img src="' + URL.createObjectURL(newFile) + '" alt="">' : '📷';
  };
  $('addForm').onsubmit = function (e) {
    e.preventDefault();
    var f = e.target, ok = true;
    var setErr = function (k, m) { var n = f.querySelector('[data-f="' + k + '"]'); n.classList.toggle('bad', !!m); n.querySelector('.err').textContent = m || ''; if (m) ok = false; };
    var name = f.elements.name.value.trim(), price = parseInt(f.elements.price.value, 10);
    setErr('name', name.length < 2 ? t('errVarName') : '');
    setErr('price', !(price > 0) ? t('errPrice') : '');
    if (!ok) return;
    api('POST', '/api/admin/varieties', {
      name: name, type: f.elements.type.value, color: f.elements.color.value, price: price,
      stock: Math.max(0, parseInt(f.elements.stock.value, 10) || 0),
      desc_ru: f.elements.desc_ru.value.trim(), desc_kk: f.elements.desc_kk.value.trim(), desc_en: f.elements.desc_en.value.trim()
    }).then(function (r) {
      if (r.status === 409) { setErr('name', t('errDup')); return; }
      if (r.status !== 201) { $('addErr').textContent = t('errServer'); return; }
      return (newFile ? uploadPhoto(r.body.id, newFile) : Promise.resolve()).then(function () {
        resetAdd(); toast(t('varietyAdded')); refresh();
      });
    });
  };

  $('tabs').onclick = function (e) {
    var b = e.target.closest('[data-tab]'); if (!b) return;
    document.querySelectorAll('#tabs button').forEach(function (x) { x.classList.toggle('on', x === b); });
    ['orders', 'items', 'guide'].forEach(function (k) { $('tab-' + k).hidden = k !== b.dataset.tab; });
  };
  $('langs').onclick = function (e) { var l = e.target.dataset.l; if (!l) return; lang = l; store.set(localStorage, 'lang', l); applyI18n(); };

  fetch('/static/i18n.json').then(function (r) { return r.json(); }).then(function (d) { T = d; applyI18n(); showPanel(); });
})();
