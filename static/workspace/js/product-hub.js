(function () {
  'use strict';

  function csrfToken() {
    var el = document.querySelector('[name=csrfmiddlewaretoken]');
    if (el) return el.value;
    var m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  function postJson(url) {
    return fetch(url, {
      method: 'POST',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'Accept': 'application/json',
        'X-CSRFToken': csrfToken(),
      },
      credentials: 'same-origin',
    }).then(function (r) {
      return r.json().then(function (data) {
        if (!r.ok) {
          var err = new Error((data && data.message) || 'error');
          err.data = data;
          err.status = r.status;
          throw err;
        }
        return data;
      });
    });
  }

  document.addEventListener('click', function (ev) {
    var voteBtn = ev.target.closest('[data-ph-vote]');
    if (voteBtn) {
      ev.preventDefault();
      if (voteBtn.disabled) return;
      var url = voteBtn.getAttribute('data-ph-vote');
      voteBtn.disabled = true;
      postJson(url).then(function (data) {
        voteBtn.classList.toggle('is-on', !!data.voted);
        var countEl = voteBtn.querySelector('[data-ph-count]');
        if (countEl) countEl.textContent = data.votes_count;
        if (typeof showToast === 'function') {
          showToast(data.voted ? 'رای شما ثبت شد' : 'رای برداشته شد', 'success');
        }
      }).catch(function (err) {
        if (err.data && err.data.upgrade_url) {
          window.location.href = err.data.upgrade_url;
          return;
        }
        if (typeof showToast === 'function') {
          showToast((err.data && err.data.message) || 'خطا در ثبت رای', 'error');
        }
      }).finally(function () {
        voteBtn.disabled = false;
      });
      return;
    }

    var followBtn = ev.target.closest('[data-ph-follow]');
    if (followBtn) {
      ev.preventDefault();
      if (followBtn.disabled) return;
      var furl = followBtn.getAttribute('data-ph-follow');
      followBtn.disabled = true;
      postJson(furl).then(function (data) {
        followBtn.classList.toggle('is-on', !!data.following);
        followBtn.textContent = data.following ? 'در حال دنبال' : 'دنبال کردن';
        var fc = followBtn.parentElement && followBtn.parentElement.querySelector('[data-ph-follows]');
        if (fc) fc.textContent = data.follows_count;
        if (typeof showToast === 'function') {
          showToast(data.following ? 'اکنون این پیشنهاد را دنبال می‌کنید' : 'دنبال کردن لغو شد', 'info');
        }
      }).catch(function (err) {
        if (err.data && err.data.upgrade_url) {
          window.location.href = err.data.upgrade_url;
          return;
        }
        if (typeof showToast === 'function') {
          showToast((err.data && err.data.message) || 'خطا', 'error');
        }
      }).finally(function () {
        followBtn.disabled = false;
      });
    }
  });
})();
