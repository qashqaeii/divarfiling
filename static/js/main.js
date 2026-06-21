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

    const saved = localStorage.getItem(STORAGE_KEY);
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
        const navMenu = document.getElementById('siteNavMenu') || document.querySelector('.nav-menu');
        const navAccount = document.getElementById('siteNavAccount') || document.querySelector('.nav-actions');
        const siteNav = document.querySelector('.mk-navbar') || document.querySelector('.navbar');

        if (!mobileMenuToggle || !navMenu) return;

        const toggleIcon = mobileMenuToggle.querySelector('i');

        function setMenuOpen(open) {
            navMenu.classList.toggle('active', open);
            navAccount?.classList.toggle('active', open);
            siteNav?.classList.toggle('mk-nav-open', open);
            document.body.classList.toggle('mk-nav-open', open);
            mobileMenuToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
            mobileMenuToggle.setAttribute('aria-label', open ? 'بستن منو' : 'باز کردن منو');
            if (toggleIcon) {
                toggleIcon.className = open ? 'fas fa-times' : 'fas fa-bars';
            }
        }

        function closeMenu() {
            setMenuOpen(false);
        }

        mobileMenuToggle.addEventListener('click', function () {
            setMenuOpen(!navMenu.classList.contains('active'));
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && navMenu.classList.contains('active')) {
                closeMenu();
            }
        });

        document.addEventListener('click', function (e) {
            if (!navMenu.classList.contains('active')) return;
            if (siteNav && siteNav.contains(e.target)) return;
            closeMenu();
        });

        navMenu.querySelectorAll('a').forEach(function (link) {
            link.addEventListener('click', closeMenu);
        });
        navAccount?.querySelectorAll('a').forEach(function (link) {
            link.addEventListener('click', closeMenu);
        });
    }

    initPublicMobileMenu();
    
    // Close alerts
    const alertCloses = document.querySelectorAll('.alert-close');
    alertCloses.forEach(btn => {
        btn.addEventListener('click', function() {
            this.parentElement.style.transition = 'opacity 0.3s';
            this.parentElement.style.opacity = '0';
            setTimeout(() => {
                this.parentElement.remove();
            }, 300);
        });
    });
    
    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.3s';
            alert.style.opacity = '0';
            setTimeout(() => {
                alert.remove();
            }, 300);
        }, 5000);
    });
    
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
            rootMargin: '50px' // شروع بارگذاری 50px قبل از رسیدن به viewport
        });
        
        lazyImages.forEach(img => {
            imageObserver.observe(img);
        });
    } else {
        // Fallback برای مرورگرهای قدیمی
        lazyImages.forEach(img => {
            img.src = img.dataset.src;
            img.classList.add('loaded');
        });
    }
    
    // Counter Animation حذف شده - نمایش مستقیم اعداد
    const statNumbers = document.querySelectorAll('.stat-number, .hero-stat-number');
    const formatNumber = (num) => {
        // فرمت اعداد با جداکننده هزارگان فارسی
        return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, "،");
    };
    
    // نمایش مستقیم اعداد بدون انیمیشن
    statNumbers.forEach(stat => {
        const target = parseInt(stat.getAttribute('data-count')) || 0;
        if (target > 0) {
            stat.textContent = formatNumber(target);
        }
    });
    
    // Lazy Loading برای نماد اعتماد الکترونیک (Enamad)
    const enamadImg = document.querySelector('#enamad-link img[data-src]');
    if (enamadImg) {
        // لود تصویر بعد از لود کامل صفحه و با تاخیر
        const loadEnamad = () => {
            if (enamadImg.dataset.src) {
                enamadImg.src = enamadImg.dataset.src;
                enamadImg.removeAttribute('data-src');
            }
        };
        
        // استفاده از IntersectionObserver برای لود وقتی به viewport نزدیک شد
        if ('IntersectionObserver' in window) {
            const enamadObserver = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        loadEnamad();
                        enamadObserver.unobserve(entry.target);
                    }
                });
            }, {
                rootMargin: '200px' // شروع بارگذاری 200px قبل از رسیدن به viewport
            });
            
            enamadObserver.observe(enamadImg);
        } else {
            // Fallback: لود بعد از 2 ثانیه
            setTimeout(loadEnamad, 2000);
        }
    }
    
});

