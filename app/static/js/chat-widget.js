/* Khung chat Trợ lý AI nổi: mở/đóng, tải lịch sử trong phiên, gửi câu hỏi tới /ai/ask (JSON + CSRF). */
(function () {
  var root = document.getElementById('cw');
  if (!root) return;
  var panel = document.getElementById('cw-panel'), fab = document.getElementById('cw-fab'),
      body = document.getElementById('cw-body'), form = document.getElementById('cw-form'),
      q = document.getElementById('cw-q'), mode = document.getElementById('cw-mode'), loaded = false;
  var csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || '';

  function esc(s) { var d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
  function scroll() { body.scrollTop = body.scrollHeight; }
  function addMe(text) {
    body.insertAdjacentHTML('beforeend', '<div class="chat-row me"><div class="bubble me">' + esc(text) + '</div></div>');
  }
  function addBot(html, extra) {
    body.insertAdjacentHTML('beforeend', '<div class="chat-row bot"><span class="chat-avatar bot sm"><i class="bi bi-stars"></i></span>' +
      '<div class="bubble bot">' + html + (extra || '') + '</div></div>');
  }
  function sources(cits) {
    if (!cits || !cits.length) return '';
    return '<div class="chat-sources"><div class="label">Nguồn tham khảo</div>' + cits.map(function (c) {
      return '<a class="source" href="' + esc(c.url) + '"><i class="bi ' +
        (c.source === 'job' ? 'bi-briefcase' : 'bi-book') + '"></i><span class="t">' + esc(c.title) + '</span></a>';
    }).join('') + '</div>';
  }
  function setMode(p) {
    mode.textContent = p === 'demo' ? 'Chế độ demo' : 'Trả lời bằng AI · bấm vào tin để xem';
  }
  function open(state) {
    panel.hidden = !state; root.classList.toggle('is-open', state); fab.setAttribute('aria-expanded', state);
    try { sessionStorage.setItem('cw-open', state ? '1' : ''); } catch (e) {}
    if (state && !loaded) {
      loaded = true;
      fetch(root.dataset.history, { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (d) {
        setMode(d.provider);
        d.history.forEach(function (t) { addMe(t.q); addBot(t.html); });
        scroll();
      }).catch(function () {});
    }
    if (state) { setTimeout(function () { q.focus(); scroll(); }, 50); }
  }
  function send(text) {
    text = text.trim();
    if (!text) return;
    addMe(text); q.value = ''; q.style.height = '';
    var mine = body.lastElementChild;
    body.insertAdjacentHTML('beforeend', '<div class="chat-row bot" id="cw-typing"><span class="chat-avatar bot sm"><i class="bi bi-stars"></i></span>' +
      '<div class="bubble bot cw-typing"><span></span><span></span><span></span></div></div>');
    scroll();
    fetch(root.dataset.ask, { method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf }, body: JSON.stringify({ question: text }) })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var warn = d.provider === 'demo (LLM lỗi)' ? '<div class="chat-note warn"><i class="bi bi-exclamation-triangle"></i> Mô hình AI đang bận nên tạm trả lời ở chế độ demo.</div>' : '';
        var html = d.html || esc(d.answer || d.error || 'Có lỗi xảy ra.');
        addBot(html, warn + (html.indexOf('job-item') < 0 ? sources(d.citations) : ''));
      })
      .catch(function () { addBot('<p>Không kết nối được máy chủ, bạn thử lại nhé.</p>'); })
      .finally(function () {
        var t = document.getElementById('cw-typing'); if (t) t.remove();
        body.scrollTop = mine.offsetTop - body.offsetTop - 8;      // đầu câu hỏi vừa gửi nằm ở trên cùng
      });
  }
  fab.addEventListener('click', function () { open(panel.hidden); });
  document.getElementById('cw-close').addEventListener('click', function () { open(false); });
  document.getElementById('cw-reset').addEventListener('click', function () {
    fetch(root.dataset.reset, { method: 'POST', credentials: 'same-origin', headers: { 'X-CSRFToken': csrf } });
    body.querySelectorAll('.chat-row').forEach(function (r, i) { if (i > 0) r.remove(); });
  });
  form.addEventListener('submit', function (e) { e.preventDefault(); send(q.value); });
  q.addEventListener('keydown', function (e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(q.value); } });
  q.addEventListener('input', function () { q.style.height = ''; q.style.height = Math.min(q.scrollHeight, 120) + 'px'; });
  document.querySelectorAll('#cw-suggest .chip').forEach(function (b) { b.addEventListener('click', function () { send(b.dataset.q); }); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !panel.hidden) open(false); });
  try { if (sessionStorage.getItem('cw-open')) open(true); } catch (e) {}
})();
