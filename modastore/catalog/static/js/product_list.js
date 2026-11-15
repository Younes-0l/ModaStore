(function () {
    'use strict';

    var root = document.documentElement;
    var panel = document.getElementById('filters');
    var overlay = document.querySelector('.filter-overlay');
    var openBtn = document.querySelector('.filter-open');
    var closeBtn = document.querySelector('.filter-close');
    var form = document.querySelector('[data-filter-form]');
    var desktop = window.matchMedia('(min-width: 1024px)');

    /* ----- Filter bottom sheet (mobile) ----- */
    function open() {
        panel.classList.add('is-open');
        overlay.hidden = false;
        document.body.classList.add('menu-open');
        if (openBtn) { openBtn.setAttribute('aria-expanded', 'true'); }
    }
    function close() {
        panel.classList.remove('is-open');
        overlay.hidden = true;
        document.body.classList.remove('menu-open');
        if (openBtn) { openBtn.setAttribute('aria-expanded', 'false'); }
    }
    if (panel && overlay) {
        if (openBtn) { openBtn.addEventListener('click', open); }
        if (closeBtn) { closeBtn.addEventListener('click', close); }
        overlay.addEventListener('click', close);
        document.addEventListener('keydown', function (e) { if (e.key === 'Escape') { close(); } });
        desktop.addEventListener('change', function (e) { if (e.matches) { close(); } });
    }

    /* ----- Grid / list view (remembered) ----- */
    var viewBtns = [].slice.call(document.querySelectorAll('[data-view]'));
    function setView(v, save) {
        root.dataset.plView = v;
        viewBtns.forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.view === v ? 'true' : 'false'); });
        if (save) { try { localStorage.setItem('pl-view', v); } catch (e) { /* storage may be blocked */ } }
    }
    setView(root.dataset.plView === 'list' ? 'list' : 'grid', false);
    viewBtns.forEach(function (b) { b.addEventListener('click', function () { setView(b.dataset.view, true); }); });

    /* ----- Brand search inside the filter ----- */
    var brandSearch = document.querySelector('[data-brand-search]');
    if (brandSearch) {
        var items = [].slice.call(document.querySelectorAll('[data-brand-list] li'));
        brandSearch.addEventListener('input', function () {
            var q = brandSearch.value.trim().toLowerCase();
            items.forEach(function (li) { li.hidden = q && li.dataset.name.indexOf(q) === -1; });
        });
        // Enter must not submit the whole filter form while searching brands
        brandSearch.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); } });
    }

    /* ----- Form: clean URLs + apply instantly on desktop ----- */
    if (form) {
        form.addEventListener('submit', function () {
            // Empty values (e.g. "all ratings") would only pollute the URL
            [].forEach.call(form.elements, function (el) {
                if (el.name && el.type !== 'submit' && !el.disabled && el.value === '') { el.disabled = true; }
            });
        });
        var timer;
        form.addEventListener('change', function (e) {
            if (!desktop.matches || (e.target.matches && e.target.matches('[data-brand-search]'))) { return; }
            clearTimeout(timer);
            timer = setTimeout(function () {
                if (form.requestSubmit) { form.requestSubmit(); } else { form.submit(); }
            }, 350);
        });
    }

    /* ----- Navigation feedback: thin progress bar + dimmed grid ----- */
    function busy() { root.classList.add('is-navigating'); }
    document.addEventListener('click', function (e) {
        var a = e.target.closest && e.target.closest('.sort-links a, .pl-pager a, .filter-chip, .filter-links a, .pl-cats a, .empty-state a');
        if (a && !e.ctrlKey && !e.metaKey && !e.shiftKey && e.button === 0) { busy(); }
    });
    if (form) { form.addEventListener('submit', busy); }
    window.addEventListener('pageshow', function () { root.classList.remove('is-navigating'); });   // back button
})();