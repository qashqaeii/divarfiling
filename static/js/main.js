// JavaScript اصلی

function initPublicThemeToggle() {
    const html = document.documentElement;
    if (!html.classList.contains('mk-public')) return;

    const buttons = document.querySelectorAll('[data-theme-toggle]');
    const STORAGE_KEY = 'ws-theme';

    function applyTheme(theme) {
        html.dataset.theme = theme;
        const iconClass = theme === 'light' ? 'fas fa-sun' : 'fas fa-moon';
        const label = theme === 'light' ? 'فعال\u200cسازی تم تاریک' : 'فعال\u200cسازی تم روشن';
        const hint = theme === 'light' ? 'تم تاریک' : 'تم روشن';
        buttons.forEach(function (btn) {
            const icon = btn.querySelector('i');
            if (icon) icon.className = iconClass;
            btn.setAttribute('aria-label', label);
            btn.setAttribute('title', hint);
        });
    }

    const saved = localStorage.getItem('ws-theme');
    if (saved === 'light' || saved === 'dark') {
        applyTheme(saved);
    } else {
        applyTheme('light');
    }

    buttons.forEach(function (btn) {
        btn.addEventListener('click', function () {
            const next = html.dataset.theme === 'dark' ? 'light' : 'dark';
            localStorage.setItem(STORAGE_KEY, next);
            applyTheme(next);
        });
    });
}

document.addEventListener('DOMContentLoaded', function() {
    initPublicThemeToggle();

    function initPublicMobileMenu() {
        const mobileMenuToggle = document.getElementById('mobileMenuToggle');
        const mobilePanel = document.getElementById('mkMobilePanel');
        const mqMobile = window.matchMedia('(max-width: 960px)');

        if (!mobileMenuToggle || !mobilePanel) return;

        const toggleIcon = mobileMenuToggle.querySelector('i');
        const navMenu = mobilePanel.querySelector('#siteNavMenu');
        const navAccount = mobilePanel.querySelector('#siteNavAccount');
        const siteNav = document.querySelector('.mk-navbar') || document.querySelector('.navbar');

        let navBackdrop = document.getElementById('mkMobileNavBackdrop');
        let suppressOutsideClose = false;

        if (!navBackdrop) {
            navBackdrop = document.createElement('div');
            navBackdrop.id = 'mkMobileNavBackdrop';
            navBackdrop.className = 'mk-mobile-nav-backdrop';
            navBackdrop.setAttribute('aria-hidden', 'true');
            navBackdrop.tabIndex = -1;
            document.body.appendChild(navBackdrop);
        }

        function isMobileView() {
            return mqMobile.matches;
        }

        function isMenuOpen() {
            return mobilePanel.classList.contains('is-open');
        }

        function setMenuOpen(open) {
            if (!isMobileView()) {
                open = false;
            }

            mobilePanel.classList.toggle('is-open', open);
            mobilePanel.classList.toggle('active', open);
            navMenu?.classList.toggle('active', open);
            navAccount?.classList.toggle('active', open);
            siteNav?.classList.toggle('mk-nav-open', open);
            document.documentElement.classList.toggle('mk-nav-open', open);
            document.body.classList.toggle('mk-nav-open', open);
            navBackdrop.classList.toggle('is-visible', open);

            mobilePanel.setAttribute('aria-hidden', open ? 'false' : 'true');
            navBackdrop.setAttribute('aria-hidden', open ? 'false' : 'true');
            mobileMenuToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
            mobileMenuToggle.setAttribute('aria-label', open ? 'بستن منو' : 'باز کردن منو');

            if (toggleIcon) {
                toggleIcon.className = open ? 'fas fa-times' : 'fas fa-bars';
            }

            if (open) {
                suppressOutsideClose = true;
                window.setTimeout(function () {
                    suppressOutsideClose = false;
                }, 320);
            }
        }

        function closeMenu() {
            setMenuOpen(false);
        }

        function openMenu() {
            if (!isMobileView()) return;
            setMenuOpen(true);
        }

        if (mqMobile.addEventListener) {
            mqMobile.addEventListener('change', closeMenu);
        } else if (mqMobile.addListener) {
            mqMobile.addListener(closeMenu);
        }

        mobileMenuToggle.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            if (!isMobileView()) return;
            if (isMenuOpen()) closeMenu();
            else openMenu();
        });

        const mobilePanelClose = document.getElementById('mkMobilePanelClose');
        if (mobilePanelClose) {
            mobilePanelClose.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                closeMenu();
            });
        }

        navBackdrop.addEventListener('click', closeMenu);

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && isMenuOpen()) {
                closeMenu();
            }
        });

        document.addEventListener('click', function (e) {
            if (!isMenuOpen() || suppressOutsideClose) return;
            if (mobileMenuToggle.contains(e.target)) return;
            if (mobilePanel.contains(e.target)) return;
            closeMenu();
        });

        mobilePanel.querySelectorAll('a').forEach(function (link) {
            link.addEventListener('click', closeMenu);
        });
    }

    initPublicMobileMenu();

    // Alerts handled by mk-notices.js

    // Lazy Loading برای تصاویر
    const lazyImages = document.querySelectorAll('img.lazy-load[data-src]');

    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.classList.add('loaded');
                    img.classList.remove('lazy-load');
                    imageObserver.unobserve(img);
                }
            });
        }, {
            rootMargin: '50px'
        });

        lazyImages.forEach(img => {
            imageObserver.observe(img);
        });
    } else {
        lazyImages.forEach(img => {
            img.src = img.dataset.src;
            img.classList.add('loaded');
        });
    }

    const statNumbers = document.querySelectorAll('.stat-number, .hero-stat-number');
    const formatNumber = (num) => {
        return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '،');
    };

    statNumbers.forEach(stat => {
        const target = parseInt(stat.getAttribute('data-count')) || 0;
        if (target > 0) {
            stat.textContent = formatNumber(target);
        }
    });

    const enamadImg = document.querySelector('#enamad-link img[data-src]');
    if (enamadImg) {
        const loadEnamad = () => {
            if (enamadImg.dataset.src) {
                enamadImg.src = enamadImg.dataset.src;
                enamadImg.removeAttribute('data-src');
            }
        };

        if ('IntersectionObserver' in window) {
            const enamadObserver = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        loadEnamad();
                        enamadObserver.unobserve(entry.target);
                    }
                });
            }, {
                rootMargin: '200px'
            });

            enamadObserver.observe(enamadImg);
        } else {
            setTimeout(loadEnamad, 2000);
        }
    }
});
