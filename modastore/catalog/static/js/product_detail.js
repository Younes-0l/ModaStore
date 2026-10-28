(function () {
    'use strict';

    const dataEl = document.getElementById('variants-data');
    if (!dataEl) return;
    const variants = JSON.parse(dataEl.textContent);

    // --- Gallery ---
    const mainImg = document.getElementById('gallery-main');
    document.querySelectorAll('.thumb').forEach(function (btn) {
        btn.addEventListener('click', function () {
            if (mainImg) mainImg.src = btn.dataset.src;
            document.querySelectorAll('.thumb').forEach(function (b) { b.classList.remove('is-active'); });
            btn.classList.add('is-active');
        });
    });

    // --- Tabs ---
    document.querySelectorAll('.tab').forEach(function (tab) {
        tab.addEventListener('click', function () {
            document.querySelectorAll('.tab').forEach(function (t) {
                t.classList.remove('is-active');
                t.setAttribute('aria-selected', 'false');
            });
            document.querySelectorAll('.tab-panel').forEach(function (p) { p.classList.remove('is-active'); });
            tab.classList.add('is-active');
            tab.setAttribute('aria-selected', 'true');
            document.getElementById('tab-' + tab.dataset.tab).classList.add('is-active');
        });
    });

    // --- Variant selection ---
    const colorBtns = Array.from(document.querySelectorAll('#color-options .swatch'));
    const storageBtns = Array.from(document.querySelectorAll('#storage-options .chip'));
    const colorLabel = document.getElementById('color-label');
    const priceEl = document.getElementById('price');
    const oldPriceEl = document.getElementById('old-price');
    const discountEl = document.getElementById('discount');
    const stockEl = document.getElementById('stock-msg');
    const cartBtn = document.getElementById('add-to-cart');
    if (!priceEl) return;

    const state = {
        color: (colorBtns.find(function (b) { return b.classList.contains('is-active'); }) || {dataset: {}}).dataset.color || '',
        storage: (storageBtns.find(function (b) { return b.classList.contains('is-active'); }) || {dataset: {}}).dataset.storage || '',
    };

    // Same grouping and separator style as the server-side price filter
    function formatPrice(n) {
        return Number(n).toLocaleString('fa-IR');
    }

    function findVariant() {
        return variants.find(function (v) {
            return v.color === state.color && v.storage === state.storage;
        });
    }

    function render() {
        // Disable options that do not exist together with the other selection
        colorBtns.forEach(function (b) {
            b.disabled = !variants.some(function (v) { return v.color === b.dataset.color && v.storage === state.storage; });
        });
        storageBtns.forEach(function (b) {
            b.disabled = !variants.some(function (v) { return v.storage === b.dataset.storage && v.color === state.color; });
        });
        colorBtns.forEach(function (b) { b.classList.toggle('is-active', b.dataset.color === state.color); });
        storageBtns.forEach(function (b) { b.classList.toggle('is-active', b.dataset.storage === state.storage); });
        if (colorLabel) colorLabel.textContent = state.color;

        const v = findVariant();
        if (!v) return;

        priceEl.textContent = formatPrice(v.price);
        oldPriceEl.hidden = !v.old_price;
        oldPriceEl.textContent = v.old_price ? formatPrice(v.old_price) : '';
        discountEl.hidden = !v.discount;
        discountEl.textContent = v.discount + '٪';

        const inStock = v.stock > 0;
        stockEl.textContent = !inStock ? 'ناموجود'
            : (v.stock <= 5 ? 'تنها ' + v.stock.toLocaleString('fa-IR') + ' عدد در انبار باقی مانده' : 'موجود در انبار');
        stockEl.classList.toggle('stock--out', !inStock);
        cartBtn.disabled = !inStock;
        cartBtn.dataset.variantId = v.id;
    }

    colorBtns.forEach(function (b) {
        b.addEventListener('click', function () {
            state.color = b.dataset.color;
            // If the current storage does not exist in this color, switch to the first one that does
            if (!findVariant()) {
                const alt = variants.find(function (v) { return v.color === state.color; });
                if (alt) state.storage = alt.storage;
            }
            render();
        });
    });

    storageBtns.forEach(function (b) {
        b.addEventListener('click', function () {
            state.storage = b.dataset.storage;
            if (!findVariant()) {
                const alt = variants.find(function (v) { return v.storage === state.storage; });
                if (alt) state.color = alt.color;
            }
            render();
        });
    });

    render();
})();