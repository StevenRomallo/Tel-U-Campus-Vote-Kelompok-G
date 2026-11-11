(() => {
  const { $, escape: e, number: n, percent: p, time, api, options, notice } = CV;
  const filterForm = $('#filters');
  const dialog = $('#action-dialog');
  const labels = { faculty: 'Fakultas', program: 'Program studi', cohort: 'Angkatan' };
  let config, data, stream, toastTimer, reconnectTimer, reconnectDelay = 1000, paused = false, busy = false, queued = false, page = 0, action, acting = false, connected = false;
  const pageSize = 10;
  const candidateLabel = option => { const c = config.candidates.find(item => item.option === option); return `Paslon ${c.number} · ${c.names}`; };
  function params() {
    const query = new URLSearchParams();
    for (const [key, value] of new FormData(filterForm)) {
      if (!value) continue;
      // Inputs explicitly represent WIB, independently of the browser's timezone.
      query.set(key, ['from', 'to'].includes(key) ? new Date(`${value}:00+07:00`).toISOString() : value);
    }
    return query;
  }
  function fillPrograms() {
    const selected = $('#filter-program').value;
    const faculty = config.faculties.find(item => item.name === $('#filter-faculty').value);
    const programs = faculty ? faculty.programs : config.faculties.flatMap(item => item.programs);
    options($('#filter-program'), programs, 'Semua program studi');
    if (programs.includes(selected)) $('#filter-program').value = selected;
  }
  async function initialize() {
    try {
      config = await api('/config');
      CV.installPosters(config);
      $('#candidate-legend').innerHTML = config.candidates.map(c => `<span><i class="legend-${c.option.toLowerCase()}"></i> ${e(candidateLabel(c.option))}</span>`).join('');
      for (const c of config.candidates) $(`#summary-heading-${c.option}`).textContent = candidateLabel(c.option);
      options($('#filter-faculty'), config.faculties.map(item => item.name), 'Semua fakultas');
      fillPrograms();
      options($('#filter-cohort'), [...config.cohorts].reverse(), 'Semua angkatan');
      $('#filter-from').disabled = $('#filter-to').disabled = false;
      $('#period-label').textContent = config.period;
      $('#demo-tools-note').textContent = config.demo_tools ? 'Tambahkan 120 catatan fiktif yang berlabel demo. Hanya tersedia ketika penyimpanan kosong.' : 'Alat data demo nonaktif. Jalankan dengan --demo-tools atau ENABLE_DEMO_TOOLS=true untuk mengaktifkan.';
      connectLive();
    } catch (error) {
      notice($('#dashboard-error'), `${error.message} Muat ulang setelah server tersedia.`);
      $('#connection-status').textContent = 'Koneksi belum tersedia';
      $('#connection-status').classList.add('offline');
    }
  }
  function connectionState(live) {
    connected = live;
    $('#connection-status').innerHTML = live ? '<span class="pulse-dot"></span> LIVE · tersambung langsung' : '<span class="pulse-dot"></span> Menyambungkan ulang…';
    $('#connection-status').classList.toggle('offline', !live);
  }
  function connectLive() {
    clearTimeout(reconnectTimer);
    if (paused) return;
    stream?.close();
    stream = new EventSource('/events');
    stream.onopen = () => { reconnectDelay = 1000; connectionState(true); };
    stream.addEventListener('votes-changed', () => refresh());
    stream.onerror = () => {
      connectionState(false);
      $('#export-csv').disabled = true;
      notice($('#dashboard-error'), 'Sambungan langsung terputus. Data terakhir dipertahankan; hasil akan diselaraskan saat koneksi pulih.');
      // A proxy HTTP 502 can close EventSource permanently. Recreate only the
      // transport when CLOSED; native CONNECTING retries remain browser-owned.
      if (!paused && stream.readyState === EventSource.CLOSED) {
        clearTimeout(reconnectTimer);
        reconnectTimer = setTimeout(connectLive, reconnectDelay);
        reconnectDelay = Math.min(reconnectDelay * 2, 15000);
      }
    };
  }
  async function refresh() {
    if (busy) { queued = true; return; }
    busy = true;
    const requested = params().toString();
    try {
      const next = await api(`/votes?${requested}`);
      if (requested !== params().toString()) { queued = true; return; }
      const changed = data && (data.storage_total !== next.storage_total || data.summary.total !== next.summary.total);
      data = next;
      render();
      if (changed) {
        clearTimeout(toastTimer);
        $('#live-toast').hidden = false;
        toastTimer = setTimeout(() => { $('#live-toast').hidden = true; }, 2600);
      }
      notice($('#dashboard-error'), '');
      connectionState(connected);
      $('#last-update').textContent = `Tersinkron ${time(data.generated_at, {second:'2-digit'})} WIB`;
      $('#export-csv').disabled = !connected;
    } catch (error) {
      notice($('#dashboard-error'), `${error.message} ${data ? 'Data terakhir tetap ditampilkan; filter yang terlihat mungkin belum diterapkan. Unduhan sementara dinonaktifkan.' : 'Belum ada hasil yang dapat ditampilkan.'}`);
      $('#export-csv').disabled = true;
      $('#connection-status').textContent = 'Koneksi terputus · mencoba kembali';
      $('#connection-status').classList.add('offline');
    } finally {
      busy = false;
      if (queued) { queued = false; queueMicrotask(refresh); }
    }
  }
  function render() {
    const s = data.summary;
    animateNumber($('#stat-total'), s.total);
    animateNumber($('#stat-margin'), s.margin);
    $('#stat-leader').textContent = !s.total ? 'Belum ada suara dalam filter' : s.leader ? `${config.candidates.find(c => c.option === s.leader).names} sedang unggul` : 'Perolehan kedua pasangan seri';
    animateNumber($('#stat-faculties'), s.faculties);
    $('#stat-programs').textContent = `${n(s.programs)} program studi terwakili`;
    animateNumber($('#stat-cohorts'), s.cohorts);
    const donut = $('#results-donut');
    const circumference = 2 * Math.PI * 68;
    const partA = s.total ? s.A / s.total * circumference : 0;
    const partB = s.total ? s.B / s.total * circumference : 0;
    donut.style.background = 'none';
    donut.innerHTML = `<svg viewBox="0 0 180 180" aria-hidden="true"><defs><linearGradient id="ring-a" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#ff748e"/><stop offset="1" stop-color="#c62159"/></linearGradient><linearGradient id="ring-b" x1="0" y1="1" x2="1" y2="0"><stop stop-color="#7c61ed"/><stop offset="1" stop-color="#36b5eb"/></linearGradient></defs><circle class="donut-orbit" cx="90" cy="90" r="86"/><g transform="rotate(-90 90 90)" fill="none" stroke-width="20"><circle cx="90" cy="90" r="68" stroke="#e8e4f1"/><circle class="ring-segment" cx="90" cy="90" r="68" stroke="url(#ring-a)" stroke-dasharray="${partA} ${circumference}"/><circle class="ring-segment" cx="90" cy="90" r="68" stroke="url(#ring-b)" stroke-dasharray="${partB} ${circumference}" stroke-dashoffset="${-partA}"/></g></svg><div><span id="donut-total">${n(s.total)}</span><small>SUARA MASUK</small></div>`;
    donut.setAttribute('aria-label', s.total ? `${candidateLabel("A")} ${n(s.A)} suara (${p(s.percent_A)}), ${candidateLabel("B")} ${n(s.B)} suara (${p(s.percent_B)}). Total ${n(s.total)} suara dalam filter.` : 'Belum ada suara dalam filter aktif');
    $('#candidate-results').innerHTML = config.candidates.map(c => `<div class="result-candidate ${c.option === 'B' ? 'candidate-b' : ''}"><div class="result-portrait"><img src="${e(c.assets.pair)}" alt="Foto pasangan ${e(c.names)}" width="1122" height="1402" decoding="async"><span class="result-number">${e(c.number)}</span></div><div class="result-candidate-info"><div><strong>${e(c.names)}</strong><span>${s.leader === c.option && s.total ? '<span class="leader-tag">Unggul sementara</span>' : '<small>Simulasi akademik</small>'}</span></div><div class="result-candidate-metrics"><strong>${p(s[`percent_${c.option}`])}</strong><span>${n(s[c.option])} suara</span></div><div class="result-track"><span style="width:${s[`percent_${c.option}`]}%"></span></div></div></div>`).join('') + (!s.total ? '<p class="empty-inline">Belum ada suara masuk dalam cakupan ini. <a href="index.html">Ke bilik suara ↗</a></p>' : '');
    const active = Object.entries(data.filters).map(([key, value]) => ['from','to'].includes(key) ? `${key === 'from' ? 'Dari' : 'Sampai'} ${time(value)} WIB` : `${labels[key]}: ${value}`);
    $('#filter-context').textContent = active.length ? `Filter aktif · ${active.join(' · ')} — ${n(s.total)} catatan` : `Seluruh data · ${n(s.total)} catatan suara · Tanpa filter`;
    notice($('#demo-banner'), s.demo_count ? `${n(s.demo_count)} dari ${n(s.total)} catatan dalam filter adalah data demonstrasi fiktif. Hasil ini untuk simulasi, bukan pemilihan resmi.` : '');
    notice($('#historical-notice'), data.historical_excluded ? `${n(data.historical_excluded)} catatan historis dari luar Bandung tetap disimpan, tetapi tidak termasuk hasil pemilihan Bandung.` : '');
    for (const field of Object.keys(labels)) renderBars(field);
    renderTrend(); renderSummary(); renderRecords();
    $('#seed-demo').disabled = !config.demo_tools || data.storage_total !== 0;
  }
  const animations = new WeakMap();
  function animateNumber(element, value) {
    const old = Number(element.dataset.value || 0);
    element.dataset.value = value;
    cancelAnimationFrame(animations.get(element));
    if (old === value || matchMedia('(prefers-reduced-motion: reduce)').matches) {
      element.textContent = n(value); return;
    }
    const start = performance.now();
    function frame(tick) {
      const progress = Math.min(1, (tick - start) / 450);
      element.textContent = n(Math.round(old + (value - old) * (1 - (1-progress)**3)));
      if (progress < 1) animations.set(element, requestAnimationFrame(frame));
    }
    animations.set(element, requestAnimationFrame(frame));
  }
  function renderBars(field) {
    const rows = data.groups[field];
    const max = Math.max(1, ...rows.map(row => row.total));
    $(`#chart-${field}`).innerHTML = rows.length ? rows.map(row => `<div class="bar-row"><div class="bar-label"><span>${e(row.label)}</span><strong>${n(row.total)} <small>suara</small></strong></div><div class="stacked-track" role="img" aria-label="${e(row.label)}: ${e(candidateLabel("A"))} ${n(row.A)} suara (${p(row.percent_A)}), ${e(candidateLabel("B"))} ${n(row.B)} suara (${p(row.percent_B)})."><span class="bar-a" style="width:${row.A / max * 100}%" title="${e(candidateLabel("A"))}: ${n(row.A)} suara · ${p(row.percent_A)} dari kelompok">${row.A / max > .15 ? n(row.A) : ''}</span><span class="bar-b" style="width:${row.B / max * 100}%" title="${e(candidateLabel("B"))}: ${n(row.B)} suara · ${p(row.percent_B)} dari kelompok">${row.B / max > .15 ? n(row.B) : ''}</span></div><div class="bar-percent"><span>01 ${p(row.percent_A)} · 02 ${p(row.percent_B)} dalam kelompok</span></div></div>`).join('') : '<div class="chart-empty"><span aria-hidden="true">▥</span><strong>Belum ada sebaran suara</strong><p>Grafik muncul saat ada catatan<br>yang sesuai filter.</p></div>';
  }
  function renderTrend() {
    const rows = data.trend;
    const daily = data.trend_interval === 'day';
    const detailsOpen = Boolean($('#trend-chart details')?.open);
    $('#trend-description').textContent = `Jumlah suara per ${daily ? 'hari' : 'jam'}, sesuai filter aktif.`;
    if (!rows.length) {
      $('#trend-chart').innerHTML = '<div class="chart-empty"><span aria-hidden="true">↗</span><strong>Jejaknya dimulai dari satu suara.</strong><p>Aktivitas akan terlihat setelah suara masuk.</p></div>';
      return;
    }
    const width = 520, height = 180, padX = 30, padY = 20;
    const max = Math.max(...rows.map(row => row.total), 1);
    const step = (width - padX * 2) / Math.max(1, rows.length - 1);
    const points = rows.map((row, i) => [rows.length === 1 ? width / 2 : padX + i * step, height - padY - row.total / max * (height - padY * 2)]);
    const line = points.map(([x, y]) => `${x},${y}`).join(' ');
    const label = row => daily ? time(row.time, { hour: undefined, minute: undefined }) : time(row.time, { day: undefined, month: undefined });
    $('#trend-chart').innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Tren jumlah suara per ${daily ? 'hari' : 'jam'} dalam filter. Tabel rincian tersedia di bawah grafik."><defs><linearGradient id="trend-fill" x1="0" x2="0" y1="0" y2="1"><stop stop-color="#b898fc" stop-opacity=".35"/><stop offset="1" stop-color="#9d8aff" stop-opacity="0"/></linearGradient><linearGradient id="trend-line" x1="0" y1="0" x2="1" y2="0"><stop stop-color="#ff91b1"/><stop offset=".5" stop-color="#b498f2"/><stop offset="1" stop-color="#5fd1ed"/></linearGradient></defs>${[0, .5, 1].map(v => `<path d="M${padX} ${height - padY - v * (height - padY * 2)}H${width - padX}" stroke="#ffffff18" stroke-dasharray="4 5"/><text x="0" y="${height - padY - v * (height - padY * 2) + 4}" fill="#a99dc0" font-size="11">${n(Math.round(max * v))}</text>`).join('')}<polygon points="${points[0][0]},${height-padY} ${line} ${points[points.length-1][0]},${height-padY}" fill="url(#trend-fill)"/><polyline points="${line}" fill="none" stroke="url(#trend-line)" stroke-width="3.5" stroke-linejoin="round"/>${points.map(([x,y],i) => `<circle cx="${x}" cy="${y}" r="4" fill="#e3cbff" stroke="#352c51" stroke-width="2" tabindex="0"><title>${e(time(rows[i].time))} WIB: ${n(rows[i].total)} suara</title></circle>`).join('')}</svg><div class="trend-axis"><span>${e(label(rows[0]))}</span><span>${e(label(rows[rows.length-1]))} WIB</span></div><details class="trend-data" ${detailsOpen ? 'open' : ''}><summary>Lihat angka per ${daily ? 'hari' : 'jam'}</summary><div class="trend-data-list">${rows.map(row => `<span>${e(time(row.time))} WIB <strong>${n(row.total)} suara</strong></span>`).join('')}</div></details>`;
  }
  function renderSummary() {
    if (!data) return;
    const rows = data.groups[$('#group-by').value];
    $('#summary-body').innerHTML = rows.length ? rows.map(row => `<tr><th scope="row">${e(row.label)}</th><td class="red-text">${n(row.A)}</td><td class="blue-text">${n(row.B)}</td><td><strong>${n(row.total)}</strong></td><td>${p(row.percent_A)} / ${p(row.percent_B)}</td><td>${p(row.contribution)}</td><td><span class="table-badge ${row.A === row.B ? 'neutral' : row.A > row.B ? 'a' : 'b'}">${row.A === row.B ? 'Seri' : e(candidateLabel(row.A > row.B ? 'A' : 'B'))}</span></td></tr>`).join('') : '<tr><td colspan="7" class="empty-table">Belum ada catatan yang sesuai filter.</td></tr>';
  }
  function renderRecords() {
    if (!data) return;
    const rows = [...data.votes].reverse();
    page = Math.min(page, Math.max(0, Math.ceil(rows.length / pageSize) - 1));
    if (!$('#records-body').contains(document.activeElement)) {
      $('#records-body').innerHTML = rows.slice(page * pageSize, (page + 1) * pageSize).map(row => `<tr><td><strong class="voter-alias"><span aria-hidden="true">◈</span> ${e(row.alias)}</strong></td><td>${e(time(row.created_at))}</td><td><span class="privacy-chip">Identitas disamarkan</span><small>Pilihan & profil individu tidak ditampilkan</small></td><td>${row.is_demo ? '<span class="demo-tag">Demo</span>' : 'Input pengguna'}</td><td><button class="delete-button" data-index="${row.index}" data-id="${e(row.id)}" aria-label="Hapus catatan ${e(row.alias)}">Hapus</button></td></tr>`).join('') || '<tr><td colspan="5" class="empty-table">Penyimpanan atau hasil filter masih kosong.</td></tr>';
    }
    $('#records-count').textContent = `${n(rows.length)} catatan · Halaman ${page+1} dari ${Math.max(1, Math.ceil(rows.length/pageSize))}`;
    $('#previous-page').disabled = page === 0;
    $('#next-page').disabled = (page+1)*pageSize >= rows.length;
  }
  function openAction(title, description, callback, confirmLabel) {
    action = callback;
    $('#action-title').textContent = title;
    $('#action-description').textContent = description;
    $('#confirm-action').textContent = confirmLabel;
    notice($('#action-error'), '');
    dialog.showModal();
  }
  $('#records-body').addEventListener('click', event => {
    const button = event.target.closest('[data-id]');
    if (!button) return;
    const query = new URLSearchParams({index: button.dataset.index, id: button.dataset.id});
    openAction('Hapus catatan suara ini?', 'Catatan akan dihapus dari penyimpanan dan hasil voting dihitung ulang. Tindakan ini tidak dapat dibatalkan dari aplikasi.', () => api(`/votes?${query}`, {method: 'DELETE', headers:{'X-Admin-Token':$('#admin-token').value}}), 'Ya, hapus catatan');
  });
  $('#seed-demo').addEventListener('click', () => openAction('Tambahkan data demonstrasi?', '120 catatan suara fiktif berlabel demo akan ditambahkan ke penyimpanan kosong. Data ini akan terlihat di seluruh grafik dan tabel.', () => api('/demo-votes', {method:'POST', body:'{}', headers:{'X-Admin-Token':$('#admin-token').value}}), 'Tambahkan 120 suara demo'));
  $('#cancel-action').addEventListener('click', () => { if (!acting) dialog.close(); });
  dialog.addEventListener('cancel', event => { if (acting) event.preventDefault(); });
  $('#confirm-action').addEventListener('click', async () => {
    if (acting || !action) return;
    acting = true;
    const label = $('#confirm-action').textContent;
    $('#confirm-action').disabled = $('#cancel-action').disabled = true;
    $('#confirm-action').textContent = 'Memproses…';
    try {
      const response = await action();
      $('#management-status').textContent = response.message;
      dialog.close();
      await refresh();
    } catch (error) { notice($('#action-error'), error.message); }
    finally { acting = false; $('#confirm-action').disabled = $('#cancel-action').disabled = false; $('#confirm-action').textContent = label; }
  });
  filterForm.addEventListener('submit', event => event.preventDefault());
  filterForm.addEventListener('change', event => { if (!config) return; if (event.target.name === 'faculty') fillPrograms(); page = 0; refresh(); });
  $('#reset-filters').addEventListener('click', () => { filterForm.reset(); if (config) { fillPrograms(); page = 0; refresh(); } });
  $('#group-by').addEventListener('change', renderSummary);
  $('#previous-page').addEventListener('click', () => { page--; renderRecords(); });
  $('#next-page').addEventListener('click', () => { page++; renderRecords(); });
  $('#export-csv').addEventListener('click', () => {
    if (!data) return;
    const key = $('#group-by').value;
    const quote = value => `"${String(value).replace(/^[=+@-]/, "'$&").replace(/"/g, '""')}"`;
    const rows = [['Rekap Tel-U Campus Vote — simulasi akademik'],['Filter', $('#filter-context').textContent],['Diperbarui (WIB)', time(data.generated_at)], ...config.candidates.map(c => ['Identitas kandidat', c.option, c.number, c.names, ...c.people.map(person => `${person.role}: ${person.name}`)]), [labels[key], `Suara ${candidateLabel('A')}`, `Suara ${candidateLabel('B')}`, 'Total', `Persen ${candidateLabel('A')} dalam kelompok`, `Persen ${candidateLabel('B')} dalam kelompok`, 'Kontribusi ke hasil filter (%)', 'Unggul'], ...data.groups[key].map(row => [row.label, row.A, row.B, row.total, row.percent_A, row.percent_B, row.contribution, row.A === row.B ? 'Seri' : candidateLabel(row.A > row.B ? 'A' : 'B')])];
    const blob = new Blob(['\uFEFF' + rows.map(row => row.map(quote).join(',')).join('\r\n')], {type:'text/csv;charset=utf-8'});
    const url = URL.createObjectURL(blob), anchor = document.createElement('a');
    anchor.href = url; anchor.download = `rekap-campus-vote-${key}.csv`; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  window.addEventListener('pagehide', () => { paused = true; stream?.close(); clearTimeout(toastTimer); clearTimeout(reconnectTimer); });
  window.addEventListener('pageshow', event => { if (event.persisted && config) { paused = false; connectLive(); } });
  initialize();
})();
