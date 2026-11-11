/* Shared, buildless browser utilities. No external runtime dependencies. */
window.CV = (() => {
  const $ = (selector, parent = document) => parent.querySelector(selector);
  const escape = value => String(value).replace(/[&<>"']/g, character => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[character]));
  const number = value => new Intl.NumberFormat('id-ID').format(value);
  const percent = value => `${new Intl.NumberFormat('id-ID', { maximumFractionDigits: 1 }).format(value)}%`;
  const time = (value, options = {}) => new Intl.DateTimeFormat('id-ID', { timeZone: 'Asia/Jakarta', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', ...options }).format(new Date(value));
  async function api(url, options = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch(url, { ...options, cache: 'no-store', headers: { 'Content-Type': 'application/json', ...options.headers }, signal: controller.signal });
      const body = await response.json();
      if (!response.ok) {
        const error = new Error(body.error || `Permintaan gagal (${response.status}).`);
        error.status = response.status;
        error.details = body;
        throw error;
      }
      return body;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('Server belum merespons. Periksa koneksi lalu coba kembali.');
      if (error instanceof TypeError) throw new Error('Tidak dapat terhubung ke server. Periksa koneksi aplikasi.');
      throw error;
    } finally { clearTimeout(timeout); }
  }
  function options(select, values, placeholder) {
    select.replaceChildren(new Option(placeholder, ''), ...values.map(value => new Option(String(value), String(value))));
    select.disabled = false;
  }
  function notice(element, message) { element.textContent = message; element.hidden = !message; }
  function installPosters(config) {
    // One shared dialog, outside the voting form. Opening it never selects a radio.
    if ($('#poster-dialog')) return;
    const dialog = document.createElement('dialog');
    dialog.id = 'poster-dialog';
    dialog.className = 'poster-dialog';
    dialog.setAttribute('aria-labelledby', 'poster-title');
    dialog.setAttribute('aria-describedby', 'poster-description');
    dialog.innerHTML = '<div class="poster-heading"><div><span class="eyebrow">MATERI SIMULASI AKADEMIK</span><h2 id="poster-title"></h2></div><button type="button" class="button secondary compact" id="close-poster" autofocus>Tutup <span aria-hidden="true">×</span></button></div><p id="poster-description">Visual untuk simulasi akademik, bukan bukti pencalonan resmi.</p><img id="poster-image" width="1122" height="1402" decoding="async">';
    document.body.append(dialog);
    let opener;
    document.addEventListener('click', event => {
      const button = event.target.closest('[data-poster]');
      if (!button || button.disabled) return;
      const candidate = config.candidates.find(item => item.option === button.dataset.poster);
      if (!candidate) return;
      opener = button;
      $('#poster-title').textContent = `Paslon ${candidate.number} · ${candidate.names}`;
      const image = $('#poster-image');
      image.src = candidate.assets.poster;
      image.alt = `Poster paslon ${candidate.number}: ${candidate.people.map(person => `${person.name}, ${person.role}`).join('; ')}. Simulasi akademik.`;
      dialog.showModal();
    });
    $('#close-poster').addEventListener('click', () => dialog.close());
    // Native Escape handling closes the modal and the close event restores focus.
    dialog.addEventListener('close', () => { if (opener?.isConnected) opener.focus({preventScroll:true}); });
  }
  return { $, escape, number, percent, time, api, options, notice, installPosters };
})();
