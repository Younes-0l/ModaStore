(function () {
    'use strict';

    const root = document.querySelector('[data-price-range]');
    if (!root) return;

    const form = root.closest('form');
    const MIN = parseInt(root.dataset.min, 10);
    const MAX = parseInt(root.dataset.max, 10);
    const span = Math.max(MAX - MIN, 1);

    const txtMin = root.querySelector('[data-price-input="min"]');
    const txtMax = root.querySelector('[data-price-input="max"]');
    const rngMin = root.querySelector('[data-range="min"]');
    const rngMax = root.querySelector('[data-range="max"]');

    const DIGIT = /[0-9\u06F0-\u06F9\u0660-\u0669]/;

    // Accepts Persian/Arabic/English digits and any separator
    function parse(s) {
        const ascii = String(s || '')
            .replace(/[\u06F0-\u06F9]/g, function (d) { return d.charCodeAt(0) - 0x06F0; })
            .replace(/[\u0660-\u0669]/g, function (d) { return d.charCodeAt(0) - 0x0660; });
        const digits = ascii.replace(/\D/g, '');
        return digits ? parseInt(digits, 10) : null;
    }

    // Same style as the product page. For English digits use 'en-US' instead.
    function fmt(n) { return Number(n).toLocaleString('fa-IR'); }

    function clamp(n) { return Math.min(Math.max(n, MIN), MAX); }

    // Paint the filled part of the track and decide which thumb is on top
    function paint() {
        const a = (parseInt(rngMin.value, 10) - MIN) / span * 100;
        const b = (parseInt(rngMax.value, 10) - MIN) / span * 100;
        root.style.setProperty('--a', a + '%');
        root.style.setProperty('--b', b + '%');
        // When both thumbs overlap, the one with more room to move must be on top
        const minOnTop = parseInt(rngMin.value, 10) - MIN > span / 2;
        rngMin.style.zIndex = minOnTop ? 2 : 1;
        rngMax.style.zIndex = minOnTop ? 1 : 2;
    }

    // Re-format a text input while typing and keep the caret next to the same digit
    function formatLive(el) {
        const pos = el.selectionStart;
        const digitsBefore = el.value.slice(0, pos).split('').filter(function (c) { return DIGIT.test(c); }).length;
        const n = parse(el.value);
        el.value = n === null ? '' : fmt(n);
        let seen = 0, i = 0;
        while (i < el.value.length && seen < digitsBefore) {
            if (DIGIT.test(el.value[i])) seen++;
            i++;
        }
        try { el.setSelectionRange(i, i); } catch (e) { /* some inputs cannot set a caret */ }
    }

    // ----- slider -> text -----
    function onRange(e) {
        let a = parseInt(rngMin.value, 10);
        let b = parseInt(rngMax.value, 10);
        if (a > b) {
            // The thumb being dragged stops at the other one
            if (e.target === rngMin) { a = b; rngMin.value = a; }
            else { b = a; rngMax.value = b; }
        }
        txtMin.value = fmt(a);
        txtMax.value = fmt(b);
        paint();
    }
    rngMin.addEventListener('input', onRange);
    rngMax.addEventListener('input', onRange);

    // ----- text -> slider -----
    function onText(el, rng) {
        formatLive(el);
        const n = parse(el.value);
        if (n !== null) { rng.value = clamp(n); paint(); }
    }
    txtMin.addEventListener('input', function () { onText(txtMin, rngMin); });
    txtMax.addEventListener('input', function () { onText(txtMax, rngMax); });

    // Finalize on blur: clamp, fill empty fields, keep min <= max
    function settle() {
        let a = parse(txtMin.value);
        let b = parse(txtMax.value);
        a = clamp(a === null ? MIN : a);
        b = clamp(b === null ? MAX : b);
        if (a > b) { const t = a; a = b; b = t; }
        txtMin.value = fmt(a);
        txtMax.value = fmt(b);
        rngMin.value = a;
        rngMax.value = b;
        paint();
    }
    txtMin.addEventListener('change', settle);
    txtMax.addEventListener('change', settle);

    // Send clean numbers only, and skip a value that equals the full range
    form.addEventListener('submit', function () {
        settle();
        const a = parse(txtMin.value);
        const b = parse(txtMax.value);
        txtMin.value = String(a);
        txtMax.value = String(b);
        if (a <= MIN) txtMin.disabled = true;
        if (b >= MAX) txtMax.disabled = true;
    });

    function init() {
        txtMin.disabled = false;
        txtMax.disabled = false;
        settle();
    }
    init();
    // Back button (bfcache) must not leave disabled fields behind
    window.addEventListener('pageshow', function (e) { if (e.persisted) init(); });
})();