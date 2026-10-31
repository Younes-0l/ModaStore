(function () {
    'use strict';

    // ---- Address tabs: saved addresses / new address ----
    const modeInput = document.getElementById('mode');
    const tabs = document.querySelectorAll('[data-mode-tab]');
    const panels = document.querySelectorAll('[data-mode-panel]');
    if (modeInput && tabs.length) {
        const setMode = function (mode) {
            modeInput.value = mode;
            tabs.forEach(function (t) {
                const on = t.dataset.modeTab === mode;
                t.classList.toggle('is-active', on);
                t.setAttribute('aria-selected', on ? 'true' : 'false');
            });
            panels.forEach(function (p) { p.hidden = p.dataset.modePanel !== mode; });
        };
        tabs.forEach(function (t) {
            t.addEventListener('click', function () { setMode(t.dataset.modeTab); });
        });
    }

    // ---- Payment countdown ----
    const cd = document.querySelector('[data-countdown]');
    if (cd) {
        const out = cd.querySelector('[data-countdown-text]');
        const end = Date.now() + (parseInt(cd.dataset.countdown, 10) || 0) * 1000;
        const two = function (n) { return n.toLocaleString('fa-IR', { minimumIntegerDigits: 2 }); };
        const tick = function () {
            const left = Math.max(0, Math.round((end - Date.now()) / 1000));
            out.textContent = two(Math.floor(left / 60)) + ':' + two(left % 60);
            if (left <= 0) {
                clearInterval(timer);
                location.reload(); // the server cancels the order and shows the result page
            }
        };
        const timer = setInterval(tick, 1000);
        tick();
    }

    // ---- Prevent double submits (e.g. two orders from a double click) ----
    document.querySelectorAll('form[data-once]').forEach(function (form) {
        form.addEventListener('submit', function () {
            const btn = form.querySelector('button[type="submit"]');
            if (btn) setTimeout(function () { btn.disabled = true; }, 0);
        });
    });
    // Coming back with the browser's back button must not leave a dead button
    window.addEventListener('pageshow', function (e) { if (e.persisted) location.reload(); });
})();