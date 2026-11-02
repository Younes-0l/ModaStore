(function () {
    'use strict';

    const url = document.body.dataset.wishlistUrl;
    if (!url) return;

    const csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || '';
    const fa = function (n) { return Number(n).toLocaleString('fa-IR'); };
    const toast = function (msg, type) { if (window.modaToast && msg) window.modaToast(msg, type); };
    const pending = new Set(); // product ids with a request in flight

    function setBadge(count) {
        document.querySelectorAll('[data-wishlist-count]').forEach(function (el) {
            el.dataset.wishlistCount = count;
            el.textContent = fa(count);
            el.hidden = count <= 0;
            el.classList.remove('bump');
            void el.offsetWidth; // restart the animation
            el.classList.add('bump');
        });
    }

    // Update every heart of this product on the page (cards, product page, related items)
    function sync(id, active) {
        document.querySelectorAll('[data-wishlist][data-product-id="' + id + '"]').forEach(function (btn) {
            btn.classList.toggle('is-active', active);
            btn.setAttribute('aria-pressed', active ? 'true' : 'false');
            const label = active ? 'حذف از علاقه‌مندی‌ها' : 'افزودن به علاقه‌مندی‌ها';
            const text = btn.querySelector('[data-wish-label]');
            if (text) text.textContent = label; else btn.setAttribute('aria-label', label);
            // Keep the no-JS form pointing at the opposite state
            const form = btn.closest('form');
            if (form && form.elements.active) form.elements.active.value = active ? '0' : '1';
            if (active) {
                btn.classList.add('pop');
                setTimeout(function () { btn.classList.remove('pop'); }, 450);
            }
        });
    }

    // On the wishlist page a removed product leaves the grid
    function onRemoved(id) {
        const page = document.querySelector('[data-wishlist-page]');
        if (!page) return;
        const btn = page.querySelector('[data-wishlist][data-product-id="' + id + '"]');
        const card = btn && btn.closest('.product-card');
        if (!card) return;
        card.classList.add('is-leaving');

        const counter = page.querySelector('[data-wl-count]');
        if (counter) {
            const left = Math.max((parseInt(counter.dataset.wlCount, 10) || 1) - 1, 0);
            counter.dataset.wlCount = left;
            counter.textContent = '(' + fa(left) + ' کالا)';
        }
        setTimeout(function () {
            card.remove();
            // Empty page: reload to show the empty state or the previous page
            if (!page.querySelector('.product-card')) location.reload();
        }, 260);
    }

    document.addEventListener('click', async function (e) {
        const btn = e.target.closest('[data-wishlist]');
        if (!btn) return;
        e.preventDefault();

        const id = btn.dataset.productId;
        if (pending.has(id)) return;
        pending.add(id);

        const want = !btn.classList.contains('is-active');
        sync(id, want); // optimistic: the heart reacts instantly

        try {
            const res = await fetch(url, {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' },
                body: new URLSearchParams({
                    product_id: id,
                    active: want ? '1' : '0',
                    next: location.pathname + location.search,
                }),
            });
            let data = {};
            try { data = await res.json(); } catch (err) { /* non-JSON error page */ }

            if (res.status === 401 && data.login_url) {
                sync(id, !want);
                toast(data.message, 'error');
                setTimeout(function () { location.href = data.login_url; }, 900);
                return;
            }
            if (!res.ok || !data.ok) {
                sync(id, !want);
                toast(data.message || 'خطایی رخ داد. دوباره تلاش کنید.', 'error');
                return;
            }
            sync(id, data.active);
            setBadge(data.count);
            if (!data.active) onRemoved(id);
        } catch (err) {
            sync(id, !want);
            toast('خطا در ارتباط با سرور. دوباره تلاش کنید.', 'error');
        } finally {
            pending.delete(id);
        }
    });

    // Back button (bfcache) can show stale hearts, so reload to resync with the server
    window.addEventListener('pageshow', function (e) { if (e.persisted) location.reload(); });
})();