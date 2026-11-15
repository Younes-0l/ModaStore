/* Profile page: styled delete confirmation. Without JS the forms simply submit. */
(function () {
    'use strict';
    var dialog = document.getElementById('pf-confirm');
    if (!dialog || typeof dialog.showModal !== 'function') { return; }
    var text = document.getElementById('pf-confirm-text');
    var pending = null;

    document.addEventListener('submit', function (e) {
        var form = e.target.closest ? e.target.closest('form[data-confirm]') : null;
        if (!form || form.dataset.confirmed) { return; }
        e.preventDefault();
        pending = form;
        text.textContent = form.dataset.confirm;
        dialog.showModal();
    });

    dialog.addEventListener('close', function () {
        if (dialog.returnValue === 'ok' && pending) {
            pending.dataset.confirmed = '1';
            pending.submit();
        }
        pending = null;
        dialog.returnValue = '';
    });

    // Click on the dark backdrop closes the dialog
    dialog.addEventListener('click', function (e) { if (e.target === dialog) { dialog.close('cancel'); } });
})();
