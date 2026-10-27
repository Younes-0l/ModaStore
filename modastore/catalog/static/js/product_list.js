(function () {
    'use strict';

    const openBtn = document.querySelector('.filter-open');
    const closeBtn = document.querySelector('.filter-close');
    const panel = document.getElementById('filters');
    const overlay = document.querySelector('.filter-overlay');
    if (!openBtn || !panel || !overlay) return;

    function open() {
        panel.classList.add('is-open');
        overlay.hidden = false;
        document.body.classList.add('menu-open');
    }
    function close() {
        panel.classList.remove('is-open');
        overlay.hidden = true;
        document.body.classList.remove('menu-open');
    }

    openBtn.addEventListener('click', open);
    closeBtn.addEventListener('click', close);
    overlay.addEventListener('click', close);
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') close();
    });
})();