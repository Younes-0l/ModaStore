(function () {
    'use strict';

    const csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || '';
    const addUrl = document.body.dataset.cartAddUrl;
    const fa = function (n) { return Number(n).toLocaleString('fa-IR'); };

    // ---- Header badge ----
    function setBadge(count) {
        document.querySelectorAll('[data-cart-count]').forEach(function (el) {
            el.dataset.cartCount = count;
            el.textContent = fa(count);
            el.hidden = count <= 0;
        });
    }
    const first = document.querySelector('[data-cart-count]');
    if (first) setBadge(parseInt(first.dataset.cartCount, 10) || 0);

    // ---- Toast ----
    let toastTimer;
    function toast(message, type) {
        let el = document.getElementById('toast');
        if (!el) {
            el = document.createElement('div');
            el.id = 'toast';
            el.setAttribute('role', 'status');
            el.setAttribute('aria-live', 'polite');
            document.body.appendChild(el);
        }
        el.className = 'toast toast--' + (type || 'success');
        el.textContent = message;
        void el.offsetWidth; // restart the transition when messages come quickly
        el.classList.add('is-visible');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(function () { el.classList.remove('is-visible'); }, 3000);
    }

    // ---- Add to cart ----
    async function addToCart(variantId, btn) {
        if (!addUrl) return;
        if (btn) btn.disabled = true;
        try {
            const res = await fetch(addUrl, {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' },
                body: new URLSearchParams({ variant_id: variantId, quantity: 1 }),
            });
            const data = await res.json();
            if (typeof data.count === 'number') setBadge(data.count);
            toast(data.message, data.ok ? 'success' : 'error');
        } catch (err) {
            toast('خطا در ارتباط با سرور. دوباره تلاش کنید.', 'error');
        } finally {
            if (btn) btn.disabled = false;
        }
    }

    // Quick-add buttons on product cards
    document.addEventListener('click', function (e) {
        const btn = e.target.closest('[data-add-variant]');
        if (!btn) return;
        e.preventDefault();
        addToCart(btn.dataset.addVariant, btn);
    });

    // Product page form: enhanced with fetch, still works as a normal POST without JS
    const form = document.getElementById('add-form');
    if (form) {
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            addToCart(form.elements.variant_id.value, form.querySelector('button[type="submit"]'));
        });
    }
})();