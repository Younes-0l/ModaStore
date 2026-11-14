/* Static pages: reveal-on-scroll (desktop only), animated counters, contact form counter,
   FAQ search/filter and the table of contents of long documents. All of it is progressive
   enhancement: every page is fully usable without this script. */
(function () {
    'use strict';

    var root = document.documentElement;
    var desktopMotion = window.matchMedia('(min-width: 1024px)').matches &&
        !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var faDigits = function (n) {
        return String(n).replace(/\d/g, function (d) { return '۰۱۲۳۴۵۶۷۸۹'[d]; });
    };
    var group = function (n) { return faDigits(n).replace(/\B(?=(\d{3})+(?!\d))/g, '٬'); };

    /* ----- Reveal + counters (desktop only) ----- */
    var reveals = document.querySelectorAll('.pg-reveal');
    var counters = document.querySelectorAll('[data-count]');
    if (desktopMotion && 'IntersectionObserver' in window) {
        if (reveals.length) {
            root.classList.add('pg-anim');
            var io = new IntersectionObserver(function (entries) {
                entries.forEach(function (e) {
                    if (e.isIntersecting) { e.target.classList.add('is-visible'); io.unobserve(e.target); }
                });
            }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
            reveals.forEach(function (el) { io.observe(el); });
        }
        var cio = new IntersectionObserver(function (entries) {
            entries.forEach(function (e) {
                if (!e.isIntersecting) { return; }
                cio.unobserve(e.target);
                var el = e.target, end = +el.dataset.count;
                var plus = el.dataset.suffix ? el.dataset.suffix : '+';
                var start = performance.now(), dur = 1200;
                (function tick(now) {
                    var t = Math.min(1, (now - start) / dur), eased = 1 - Math.pow(1 - t, 3);
                    el.textContent = group(Math.round(end * eased)) + plus;
                    if (t < 1) { requestAnimationFrame(tick); }
                })(start);
            });
        }, { threshold: 0.6 });
        counters.forEach(function (el) { cio.observe(el); });
    }

    /* ----- Contact form: live character counter ----- */
    var form = document.querySelector('[data-contact-form]');
    if (form) {
        var area = form.querySelector('textarea');
        var counter = form.querySelector('[data-counter]');
        var max = area ? +area.getAttribute('maxlength') || 2000 : 2000;
        var update = function () {
            counter.textContent = area.value.length + ' / ' + max;
            counter.classList.toggle('is-near', area.value.length > max * 0.9);
        };
        if (area && counter) { area.addEventListener('input', update); update(); }
        form.addEventListener('submit', function () {
            var btn = form.querySelector('button[type=submit]');
            if (btn) { btn.disabled = true; btn.style.opacity = '.7'; }   // prevent double submit
        });
    }

    /* ----- FAQ: search + category tabs ----- */
    var list = document.querySelector('[data-faq-list]');
    if (list) {
        var items = [].slice.call(list.querySelectorAll('.pg-faq'));
        var input = document.querySelector('[data-faq-search]');
        var tabs = document.querySelector('[data-faq-tabs]');
        var empty = list.querySelector('[data-faq-empty]');
        var cat = 'all';
        var norm = function (s) {
            return s.replace(/[۰-۹]/g, function (d) { return '۰۱۲۳۴۵۶۷۸۹'.indexOf(d); })
                .replace(/ي/g, 'ی').replace(/ك/g, 'ک').toLowerCase().trim();
        };
        var apply = function () {
            var q = norm(input.value), shown = 0;
            items.forEach(function (it) {
                var ok = (cat === 'all' || it.dataset.cat === cat) && (!q || norm(it.textContent).indexOf(q) !== -1);
                it.hidden = !ok;
                if (ok) { shown++; }
                if (q && ok) { it.open = shown === 1; }   // open the best (first) match
            });
            empty.hidden = shown !== 0;
        };
        input.addEventListener('input', apply);
        tabs.addEventListener('click', function (e) {
            var b = e.target.closest('button[data-filter]');
            if (!b) { return; }
            cat = b.dataset.filter;
            tabs.querySelectorAll('button').forEach(function (x) { x.classList.toggle('is-active', x === b); });
            apply();
        });
    }

    /* ----- Documents: build the table of contents + scroll spy ----- */
    var prose = document.querySelector('[data-prose]');
    var tocList = document.querySelector('[data-toc-list]');
    if (prose && tocList) {
        var heads = [].slice.call(prose.querySelectorAll('h2[id]'));
        var links = {};
        heads.forEach(function (h) {
            var li = document.createElement('li'), a = document.createElement('a');
            a.href = '#' + h.id; a.textContent = h.textContent;
            li.appendChild(a); tocList.appendChild(li); links[h.id] = a;
        });
        if ('IntersectionObserver' in window && heads.length) {
            var current = null;
            var spy = new IntersectionObserver(function (entries) {
                entries.forEach(function (e) { if (e.isIntersecting) { current = e.target.id; } });
                if (!current) { return; }
                Object.keys(links).forEach(function (id) { links[id].classList.toggle('is-active', id === current); });
                var active = links[current];
                if (active && window.innerWidth < 960) {
                    // keep the active chip visible in the horizontal strip without moving the page
                    active.scrollIntoView({ inline: 'center', block: 'nearest', behavior: 'smooth' });
                }
            }, { rootMargin: '-20% 0px -70% 0px' });
            heads.forEach(function (h) { spy.observe(h); });
        }
    }
})();
