(function () {
    'use strict';

    var chat = document.getElementById('supChatMessages');
    if (chat) {
        chat.scrollTop = chat.scrollHeight;
    }

    var textarea = document.querySelector('.sup-compose-form textarea');
    if (textarea) {
        function autoGrow() {
            textarea.style.height = 'auto';
            textarea.style.height = Math.min(textarea.scrollHeight, 160) + 'px';
        }
        textarea.addEventListener('input', autoGrow);
        autoGrow();
        if (window.matchMedia('(min-width: 769px)').matches) {
            textarea.focus({ preventScroll: true });
        }
    }

    var fileInput = document.querySelector('.sup-compose-attach input[type="file"]');
    var fileNameEl = document.getElementById('supFileName');
    if (fileInput && fileNameEl) {
        fileInput.addEventListener('change', function () {
            var name = fileInput.files && fileInput.files[0] ? fileInput.files[0].name : '';
            fileNameEl.textContent = name;
            fileNameEl.classList.toggle('is-visible', !!name);
        });
    }

    var form = document.getElementById('supComposeForm');
    if (form) {
        form.addEventListener('submit', function () {
            var btn = form.querySelector('.sup-compose-send');
            if (btn) {
                btn.disabled = true;
                btn.classList.add('is-loading');
            }
        });
    }

    document.querySelectorAll('[data-sup-scroll-compose]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var compose = document.querySelector('.sup-detail-compose');
            if (!compose) return;
            compose.scrollIntoView({ behavior: 'smooth', block: 'end' });
            if (textarea) {
                setTimeout(function () {
                    textarea.focus({ preventScroll: true });
                }, 280);
            }
        });
    });
})();
