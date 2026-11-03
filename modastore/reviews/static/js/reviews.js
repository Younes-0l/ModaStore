(function () {
    'use strict';

    const csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || '';
    const fa = function (n) { return Number(n).toLocaleString('fa-IR'); };
    const toast = function (msg, type) { if (window.modaToast && msg) window.modaToast(msg, type); };

    // ---- "Helpful" votes: optimistic, idempotent (sends the wanted state) ----
    const pending = new Set();
    document.addEventListener('click', async function (e) {
        const btn = e.target.closest('[data-helpful]');
        if (!btn || btn.disabled) return;
        const form = btn.closest('form');
        e.preventDefault();

        const key = form.action;
        if (pending.has(key)) return;
        pending.add(key);

        const want = !btn.classList.contains('is-active');
        const counter = btn.querySelector('[data-helpful-count]');
        const apply = function (active, count) {
            btn.classList.toggle('is-active', active);
            form.elements.active.value = active ? '0' : '1';
            if (counter && typeof count === 'number') {
                counter.textContent = '(' + fa(count) + ')';
                counter.hidden = count <= 0;
            }
        };
        const before = { active: !want, count: counter ? parseInt(counter.textContent.replace(/\D/g, ''), 10) || 0 : 0 };
        apply(want);

        try {
            const res = await fetch(form.action, {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' },
                body: new URLSearchParams({
                    active: want ? '1' : '0',
                    next: location.pathname + location.search + '#reviews',
                }),
            });
            let data = {};
            try { data = await res.json(); } catch (err) { /* non-JSON error page */ }

            if (res.status === 401 && data.login_url) {
                apply(before.active, before.count);
                toast(data.message, 'error');
                setTimeout(function () { location.href = data.login_url; }, 900);
                return;
            }
            if (!res.ok || !data.ok) {
                apply(before.active, before.count);
                toast(data.message || 'خطایی رخ داد. دوباره تلاش کنید.', 'error');
                return;
            }
            apply(data.active, data.count);
        } catch (err) {
            apply(before.active, before.count);
            toast('خطا در ارتباط با سرور. دوباره تلاش کنید.', 'error');
        } finally {
            pending.delete(key);
        }
    });

    // ---- Long reviews: "read more" (measured when the tab is actually visible) ----
    const bodies = document.querySelectorAll('[data-clamp]');
    if (bodies.length && 'IntersectionObserver' in window) {
        const io = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                const el = entry.target;
                io.unobserve(el);
                el.classList.add('is-clamped');
                if (el.scrollHeight <= el.clientHeight + 1) {
                    el.classList.remove('is-clamped');
                    return;
                }
                const more = document.createElement('button');
                more.type = 'button';
                more.className = 'rv-more';
                more.textContent = 'ادامه نظر';
                more.addEventListener('click', function () {
                    const open = el.classList.toggle('is-clamped');
                    more.textContent = open ? 'ادامه نظر' : 'بستن';
                });
                el.after(more);
            });
        });
        bodies.forEach(function (el) { io.observe(el); });
    }

    // ---- Star picker text ----
    const rateText = document.querySelector('[data-rate-text]');
    if (rateText) {
        const words = { 1: 'خیلی بد', 2: 'بد', 3: 'متوسط', 4: 'خوب', 5: 'عالی' };
        const show = function () {
            const on = document.querySelector('.rate-stars input:checked');
            rateText.textContent = on ? words[on.value] : '';
        };
        document.querySelectorAll('.rate-stars input').forEach(function (i) { i.addEventListener('change', show); });
        show();
    }
})();