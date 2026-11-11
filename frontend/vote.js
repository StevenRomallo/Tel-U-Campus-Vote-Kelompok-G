(() => {
  const { $, escape: e, api, options, notice } = CV;
  const form = $('#vote-form');
  const dialog = $('#confirm-dialog');
  let config, pending, sending = false, locked = false, csrf = '', statusStream, statusReconnect;
  function showVoted(status) {
    locked = true;
    clearTimeout(statusReconnect);
    statusStream?.close();
    for (const control of form.querySelectorAll('input, select, button')) control.disabled = true;
    form.hidden = true;
    pending = null;
    $('#voter-name').value = '';
    $('#confirmation-summary').replaceChildren();
    if (dialog.open) dialog.close();
    const date = new Date(status.voted_at);
    const day = new Intl.DateTimeFormat('id-ID',{timeZone:'Asia/Jakarta',dateStyle:'long'}).format(date);
    const clock = new Intl.DateTimeFormat('id-ID',{timeZone:'Asia/Jakarta',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).format(date);
    $('#voted-timestamp').textContent = `Anda sudah menggunakan hak pilih pada ${day} pukul ${clock} WIB.`;
    $('#vote-success').hidden = false;
  }
  function watchStatus() {
    clearTimeout(statusReconnect);
    if (locked) return;
    statusStream?.close();
    statusStream = new EventSource('/events');
    statusStream.addEventListener('votes-changed', async () => {
      try { const status = await api('/auth/me'); if (status.has_voted) showVoted(status); }
      catch (error) { if (error.status === 401) location.replace('login.html'); }
    });
    statusStream.onerror = () => {
      if (!locked && statusStream.readyState === EventSource.CLOSED) statusReconnect = setTimeout(watchStatus, 2000);
    };
  }
  async function initialize() {
    try {
      const session = await api('/auth/me');
      csrf = session.csrf_token;
      config = await api('/config');
      $('#election-title').textContent = config.title;
      $('#election-period').textContent = config.period;
      options($('#faculty'), config.faculties.map(item => item.name), 'Pilih fakultas');
      options($('#cohort'), [...config.cohorts].reverse(), 'Pilih angkatan');
      $('#candidate-grid').innerHTML = `<legend class="sr-only">Pilih pasangan calon</legend>${config.candidates.map(candidate => `<div class="candidate-card"><label class="candidate-choice"><input type="radio" name="option" value="${e(candidate.option)}" required><span class="candidate-art"><span class="art-orbit" aria-hidden="true"></span><img src="${e(candidate.assets.pair)}" alt="Paslon ${e(candidate.number)}: ${e(candidate.people[0].name)} di kiri dan ${e(candidate.people[1].name)} di kanan" width="1122" height="1402" decoding="async"><span class="candidate-select-mark" aria-hidden="true">✓</span><span class="fiction-badge">VISUAL SIMULASI AKADEMIK</span></span><span class="candidate-info"><span class="candidate-number">PASLON ${e(candidate.number)}</span><strong class="candidate-name">${e(candidate.names)}</strong><span class="candidate-people">${candidate.people.map(person => `<span><small>${e(person.role)}</small><strong>${e(person.name)}</strong></span>`).join('')}</span><span class="candidate-tagline">“${e(candidate.tagline)}”</span><span class="candidate-vision">${e(candidate.vision)}</span><span class="mission-list">${candidate.missions.map(mission => `<span><span aria-hidden="true">↗</span> ${e(mission)}</span>`).join('')}</span><span class="choose-label"><span class="radio-circle" aria-hidden="true"></span><span class="choose-default">Pilih pasangan ini</span><span class="choose-selected">✓ Pasangan pilihanmu</span></span></span></label><div class="candidate-actions"><button type="button" class="poster-button" data-poster="${e(candidate.option)}" aria-label="Lihat poster paslon ${e(candidate.number)}: ${e(candidate.names)}">Lihat poster <span aria-hidden="true">↗</span></button></div></div>`).join('')}`;
      CV.installPosters(config);
      $('#review-button').disabled = false;
      if (session.has_voted) showVoted(session);
      else watchStatus();
      $('#main').hidden = false;
      $('#auth-loading').hidden = true;
    } catch (error) {
      if (error.status === 401) { location.replace('login.html'); return; }
      $('#main').hidden = false; $('#auth-loading').hidden = true;
      notice($('#boot-error'), `${error.message} Muat ulang halaman setelah server tersedia.`);
    }
  }
  $('#faculty').addEventListener('change', () => {
    const faculty = config.faculties.find(item => item.name === $('#faculty').value);
    options($('#program'), faculty ? faculty.programs : [], faculty ? 'Pilih program studi' : 'Pilih fakultas terlebih dahulu');
    $('#program').disabled = !faculty;
  });
  form.addEventListener('submit', event => {
    event.preventDefault();
    if (sending || locked || !form.reportValidity()) return;
    pending = Object.fromEntries(new FormData(form));
    pending.cohort = Number(pending.cohort);
    const candidate = config.candidates.find(item => item.option === pending.option);
    $('#confirmation-summary').innerHTML = `<div class="chosen-summary"><span>${e(candidate.number)}</span><div><small>PASANGAN PILIHANMU · DEMO</small><strong>${e(candidate.names)}</strong></div></div><dl>${pending.name?.trim() ? `<div><dt>Nama · hanya di perangkat ini</dt><dd>${e(pending.name.trim())}</dd></div>` : ''}<div><dt>Lokasi</dt><dd>Telkom University Bandung</dd></div><div><dt>Fakultas</dt><dd>${e(pending.faculty)}</dd></div><div><dt>Program studi</dt><dd>${e(pending.program)}</dd></div><div><dt>Angkatan</dt><dd>${e(pending.cohort)}</dd></div></dl><p class="receipt-privacy">◈ Satu NIM, satu suara. Pilihan tidak dapat dikirim ulang.</p>`;
    notice($('#dialog-error'), '');
    dialog.showModal();
  });
  $('#cancel-vote').addEventListener('click', () => { if (!sending) dialog.close(); });
  dialog.addEventListener('cancel', event => { if (sending) event.preventDefault(); });
  $('#confirm-vote').addEventListener('click', async () => {
    if (sending || locked || !pending) return;
    sending = true;
    $('#confirm-vote').disabled = $('#cancel-vote').disabled = $('#review-button').disabled = true;
    $('#confirm-vote').textContent = 'Mencatat suaramu…';
    notice($('#dialog-error'), '');
    try {
      // Explicit allowlist: the optional name remains on this device only.
      const payload = Object.fromEntries(['option','faculty','program','cohort'].map(key => [key, pending[key]]));
      const response = await api('/votes', { method: 'POST', body: JSON.stringify(payload), headers:{'X-CSRF-Token':csrf} });
      showVoted(response);
      $('#vote-success').scrollIntoView({ behavior: 'smooth', block: 'center' });
      $('#vote-success a').focus({ preventScroll: true });
      pending = null;
    } catch (error) {
      if (error.status === 409 && error.details?.has_voted) showVoted(error.details);
      else if (error.status === 401) location.replace('login.html');
      else notice($('#dialog-error'), `${error.message} Hak pilih akan diperiksa kembali oleh server saat mencoba lagi.`);
    }
    finally {
      sending = false;
      $('#confirm-vote').disabled = $('#cancel-vote').disabled = $('#review-button').disabled = locked;
      $('#confirm-vote').textContent = 'Ya, kirim suara →';
    }
  });
  $('#logout-button').addEventListener('click', async () => {
    $('#logout-button').disabled = true;
    try { await api('/auth/logout',{method:'POST',body:'{}',headers:{'X-CSRF-Token':csrf}}); location.replace('login.html'); }
    catch(error) { if(error.status === 401) location.replace('login.html'); else { notice($('#boot-error'),error.message); $('#logout-button').disabled=false; } }
  });
  window.addEventListener('pagehide',()=>{clearTimeout(statusReconnect);statusStream?.close();});
  window.addEventListener('pageshow',event=>{if(event.persisted) location.reload();});
  initialize();
})();
