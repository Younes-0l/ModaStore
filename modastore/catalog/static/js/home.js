(function () {
    'use strict';

    /* ---------- Scroll reveal ---------- */
    var targets = document.querySelectorAll('.reveal, .stagger');
    if (targets.length) {
        if (!('IntersectionObserver' in window)) {
            targets.forEach(function (el) { el.classList.add('is-visible'); });
        } else {
            var observer = new IntersectionObserver(function (entries) {
                entries.forEach(function (entry) {
                    if (!entry.isIntersecting) return;
                    entry.target.classList.add('is-visible');
                    observer.unobserve(entry.target); // animate once, then stop watching
                });
            }, { rootMargin: '0px 0px -8% 0px', threshold: 0.1 });
            targets.forEach(function (el) { observer.observe(el); });
        }
    }

    /* ---------- Product tabs (new / offers / top rated) ---------- */
    var box = document.querySelector('[data-tabs]');
    if (!box) return;
    var tabs = [].slice.call(box.querySelectorAll('[data-tab]'));
    var panels = [].slice.call(box.querySelectorAll('[data-panel]'));

    function show(name) {
        tabs.forEach(function (t) {
            var on = t.dataset.tab === name;
            t.classList.toggle('is-active', on);
            t.setAttribute('aria-selected', on ? 'true' : 'false');
            t.tabIndex = on ? 0 : -1;
        });
        panels.forEach(function (p) {
            var on = p.dataset.panel === name;
            p.hidden = !on;
            p.classList.remove('hx-in');
            if (on) { void p.offsetWidth; p.classList.add('hx-in'); }   // replay the entrance animation
        });
    }
    tabs.forEach(function (t, i) {
        t.addEventListener('click', function () { show(t.dataset.tab); });
        t.addEventListener('keydown', function (e) {   // arrow keys move between tabs (RTL: right = previous)
            var step = e.key === 'ArrowLeft' ? 1 : e.key === 'ArrowRight' ? -1 : 0;
            if (!step) return;
            var next = tabs[(i + step + tabs.length) % tabs.length];
            next.focus(); show(next.dataset.tab);
        });
    });
})();