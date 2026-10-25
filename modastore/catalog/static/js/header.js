(function () {
    'use strict';

    const toggleBtn = document.querySelector('.menu-toggle');
    const closeBtn = document.querySelector('.menu-close');
    const menu = document.getElementById('mobile-menu');
    const overlay = document.querySelector('.menu-overlay');

    if (!toggleBtn || !menu || !overlay) return;

    function openMenu() {
        menu.classList.add('is-open');
        menu.setAttribute('aria-hidden', 'false');
        toggleBtn.setAttribute('aria-expanded', 'true');
        overlay.hidden = false;
        document.body.classList.add('menu-open');
        closeBtn.focus();
    }

    function closeMenu() {
        menu.classList.remove('is-open');
        menu.setAttribute('aria-hidden', 'true');
        toggleBtn.setAttribute('aria-expanded', 'false');
        overlay.hidden = true;
        document.body.classList.remove('menu-open');
        toggleBtn.focus();
    }

    toggleBtn.addEventListener('click', openMenu);
    closeBtn.addEventListener('click', closeMenu);
    overlay.addEventListener('click', closeMenu);

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && menu.classList.contains('is-open')) closeMenu();
    });

    // Close the drawer automatically when the viewport grows to desktop size
    window.matchMedia('(min-width: 1024px)').addEventListener('change', function (e) {
        if (e.matches && menu.classList.contains('is-open')) closeMenu();
    });
})();