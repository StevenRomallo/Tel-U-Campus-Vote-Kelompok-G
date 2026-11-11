(() => {
  const { $, api, notice } = CV;
  let busy = false;
  $('#toggle-password').addEventListener('click', () => {
    const show = $('#password').type === 'password';
    $('#password').type = show ? 'text' : 'password';
    $('#toggle-password').textContent = show ? 'Sembunyikan' : 'Tampilkan';
    $('#toggle-password').setAttribute('aria-pressed', String(show));
  });
  $('#nim').addEventListener('change', () => { $('#nim').value = $('#nim').value.trim(); });
  $('#nim').addEventListener('paste', event => {
    const value = event.clipboardData.getData('text').trim();
    if (/^1010[0-9]{8}$/.test(value)) { event.preventDefault(); $('#nim').value = value; }
  });
  $('#login-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (busy) return;
    const nim = $('#nim').value.trim();
    if (!/^1010[0-9]{8}$/.test(nim)) {
      notice($('#login-error'), 'NIM harus 12 digit: 1010 diikuti delapan angka.'); return;
    }
    busy = true; $('#login-button').disabled = true;
    $('#login-button').textContent = 'Memeriksa sesi…';
    notice($('#login-error'), '');
    try {
      await api('/auth/login', { method:'POST', body:JSON.stringify({nim, password:$('#password').value}) });
      $('#password').value = '';
      location.replace('index.html');
    } catch (error) {
      notice($('#login-error'), error.message);
      busy = false; $('#login-button').disabled = false;
      $('#login-button').textContent = 'Masuk ke bilik suara →';
    }
  });
  api('/auth/me').then(() => location.replace('index.html')).catch(error => {
    if (error.status !== 401) notice($('#login-error'), error.message);
  });
})();
