(function () {
    'use strict';

    function bindFileName(input, nameEl) {
        if (!input || !nameEl) return;
        input.addEventListener('change', function () {
            var name = input.files && input.files[0] ? input.files[0].name : '';
            nameEl.textContent = name;
            nameEl.classList.toggle('is-visible', !!name);
        });
    }

    var createForm = document.getElementById('supCreateModalForm');
    if (createForm) {
        bindFileName(
            createForm.querySelector('input[type="file"]'),
            document.getElementById('supCreateFileName')
        );
        createForm.addEventListener('submit', function () {
            var btn = document.getElementById('supCreateSubmitBtn');
            if (btn) {
                btn.disabled = true;
                btn.classList.add('is-loading');
            }
        });
    }

    var pageForm = document.getElementById('supCreatePageForm');
    if (pageForm) {
        bindFileName(
            pageForm.querySelector('input[type="file"]'),
            document.getElementById('supPageFileName')
        );
    }

    var modalBody = document.querySelector('#modal-ticket-create textarea');
    if (modalBody && window.matchMedia('(max-width: 768px)').matches) {
        modalBody.setAttribute('rows', '4');
    }

    var mobSearch = document.querySelector('.sup-mob-search');
    if (mobSearch) {
        var searchInput = mobSearch.querySelector('.sup-mob-search-input');
        var debounceTimer;
        if (searchInput) {
            searchInput.addEventListener('input', function () {
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(function () {
                    var len = searchInput.value.trim().length;
                    if (len === 0 || len >= 2) {
                        mobSearch.submit();
                    }
                }, 450);
            });
        }
    }
})();
