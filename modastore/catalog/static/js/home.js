(function () {
    'use strict';

    const targets = document.querySelectorAll('.reveal, .stagger');
    if (!targets.length) return;

    // Old browsers: just show everything
    if (!('IntersectionObserver' in window)) {
        targets.forEach(function (el) { el.classList.add('is-visible'); });
        return;
    }

    const observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            if (!entry.isIntersecting) return;
            entry.target.classList.add('is-visible');
            observer.unobserve(entry.target); // animate once, then stop watching
        });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.1 });

    targets.forEach(function (el) { observer.observe(el); });
})();