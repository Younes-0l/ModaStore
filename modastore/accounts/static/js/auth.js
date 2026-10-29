(function () {
    'use strict';

    const btn = document.getElementById('resend-btn');
    if (!btn) return;

    let left = parseInt(btn.dataset.wait, 10) || 0;
    const label = 'ارسال مجدد کد';

    function tick() {
        if (left > 0) {
            btn.disabled = true;
            btn.textContent = label + ' (' + left.toLocaleString('fa-IR') + ')';
            left -= 1;
            setTimeout(tick, 1000);
        } else {
            btn.disabled = false;
            btn.textContent = label;
        }
    }
    tick();
})();