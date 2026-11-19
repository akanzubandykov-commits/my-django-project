(function () {
  var data = document.getElementById('lessonData'), btn = document.getElementById('playBtn'), box = document.getElementById('present');
  if (!data || !btn || !box) return;
  var L = JSON.parse(data.textContent), S = L.stages || [], Q = L.quiz || [];
  var slides = S.map(function (s) { return { t: 's', d: s }; }).concat(Q.map(function (q) { return { t: 'q', d: q }; }));
  var i = 0, left = 0, tm = null, score = 0, answered = {};
  var $ = function (id) { return document.getElementById(id); };
  function fmt(s) { s = Math.max(0, s); var m = Math.floor(s / 60), r = s % 60; return (m < 10 ? '0' : '') + m + ':' + (r < 10 ? '0' : '') + r; }
  function stop() { if (tm) { clearInterval(tm); tm = null; } $('pStart').textContent = 'Таймер'; }
  function para(b, text) {
    String(text || '').split(/\n+/).forEach(function (line) {
      if (line.trim()) { var p = document.createElement('p'); p.textContent = line; b.appendChild(p); }
    });
  }
  function quizStatus(qi) { $('pStage').textContent = 'Сынақ ' + (qi + 1) + ' / ' + Q.length + ' | дұрыс: ' + score; }
  function showQuiz(qi) {
    var q = Q[qi], b = $('pBody');
    quizStatus(qi); $('pName').textContent = q.q; $('pTimer').textContent = ''; $('pStart').hidden = true;
    b.textContent = '';
    q.options.forEach(function (o, k) {
      var x = document.createElement('button'); x.type = 'button'; x.className = 'qopt'; x.textContent = o;
      if (answered[qi] !== undefined) { x.disabled = true; if (k === q.answer) x.classList.add('ok'); }
      x.addEventListener('click', function () { pick(qi, k); });
      b.appendChild(x);
    });
    if (answered[qi] !== undefined && q.explanation) { var e = document.createElement('p'); e.className = 'qexp'; e.textContent = q.explanation; b.appendChild(e); }
  }
  function pick(qi, k) {
    if (answered[qi] !== undefined) return;
    var q = Q[qi], ok = k === q.answer; answered[qi] = ok; if (ok) score++;
    var btns = $('pBody').querySelectorAll('.qopt');
    btns.forEach(function (x, idx) { x.disabled = true; if (idx === q.answer) x.classList.add('ok'); else if (idx === k) x.classList.add('no'); });
    if (q.explanation) { var e = document.createElement('p'); e.className = 'qexp'; e.textContent = q.explanation; $('pBody').appendChild(e); }
    quizStatus(qi);
  }
  function show(n) {
    if (!slides.length) return;
    i = Math.max(0, Math.min(slides.length - 1, n)); stop();
    var sl = slides[i];
    if (sl.t === 'q') { showQuiz(i - S.length); return; }
    var s = sl.d;
    $('pStart').hidden = false;
    $('pStage').textContent = (i + 1) + ' / ' + S.length;
    $('pName').textContent = s.name;
    left = (s.minutes || 0) * 60;
    $('pTimer').textContent = fmt(left); $('pTimer').classList.remove('over');
    var b = $('pBody'); b.textContent = ''; para(b, s.body);
  }
  function tick() {
    left--; $('pTimer').textContent = fmt(left);
    if (left <= 0) { stop(); $('pTimer').classList.add('over'); }
  }
  function open() { score = 0; answered = {}; box.hidden = false; document.body.style.overflow = 'hidden'; show(0); }
  function close() { stop(); box.hidden = true; document.body.style.overflow = ''; }
  btn.addEventListener('click', open);
  $('pClose').addEventListener('click', close);
  $('pPrev').addEventListener('click', function () { show(i - 1); });
  $('pNext').addEventListener('click', function () { show(i + 1); });
  $('pStart').addEventListener('click', function () {
    if (tm) { stop(); return; }
    $('pTimer').classList.remove('over');
    var cur = slides[i] && slides[i].d;
    if (left <= 0) left = ((cur && cur.minutes) || 1) * 60;
    tm = setInterval(tick, 1000); this.textContent = 'Тоқтату';
  });
  document.addEventListener('keydown', function (e) {
    if (box.hidden) return;
    if (e.key === 'ArrowRight') show(i + 1);
    else if (e.key === 'ArrowLeft') show(i - 1);
    else if (e.key === 'Escape') close();
  });
})();
