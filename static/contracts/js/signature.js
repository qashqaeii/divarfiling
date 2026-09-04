(function () {
  'use strict';
  var canvas = document.getElementById('ct-signature');
  var hidden = document.getElementById('ct-signature-data');
  var clearBtn = document.getElementById('ct-signature-clear');
  var form = document.getElementById('ct-accept-form');
  if (!canvas || !hidden) return;
  var ctx = canvas.getContext('2d');
  var drawing = false;
  function pos(e) {
    var r = canvas.getBoundingClientRect();
    var t = e.touches ? e.touches[0] : e;
    return { x: t.clientX - r.left, y: t.clientY - r.top };
  }
  function start(e) { drawing = true; var p = pos(e); ctx.beginPath(); ctx.moveTo(p.x, p.y); e.preventDefault(); }
  function move(e) {
    if (!drawing) return;
    var p = pos(e);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
    e.preventDefault();
  }
  function end() { drawing = false; }
  canvas.addEventListener('mousedown', start);
  canvas.addEventListener('mousemove', move);
  canvas.addEventListener('mouseup', end);
  canvas.addEventListener('touchstart', start, { passive: false });
  canvas.addEventListener('touchmove', move, { passive: false });
  canvas.addEventListener('touchend', end);
  if (clearBtn) clearBtn.addEventListener('click', function () { ctx.clearRect(0, 0, canvas.width, canvas.height); hidden.value = ''; });
  if (form) form.addEventListener('submit', function () {
    if (!hidden.value) hidden.value = canvas.toDataURL('image/png');
  });
})();
