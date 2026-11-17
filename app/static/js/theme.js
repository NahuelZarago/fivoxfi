/* Tema claro/oscuro. Se carga en el <head> (antes de pintar) para evitar el destello de color.
   Preferencia: la guardada por la persona; si no hay, la del sistema operativo. */
(function () {
    'use strict';
    var KEY = 'fivox-theme', root = document.documentElement;

    function stored() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
    function systemDark() { return !!(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches); }
    function isDark() { var s = stored(); return s === 'dark' || (s !== 'light' && systemDark()); }

    function apply() {
        var dark = isDark();
        root.classList.toggle('dark', dark);
        root.style.colorScheme = dark ? 'dark' : 'light';
        var buttons = document.querySelectorAll('[data-theme-toggle]');
        for (var i = 0; i < buttons.length; i++) buttons[i].setAttribute('aria-pressed', dark ? 'true' : 'false');
    }

    apply();
    document.addEventListener('DOMContentLoaded', apply);
    document.addEventListener('click', function (e) {
        var btn = e.target.closest ? e.target.closest('[data-theme-toggle]') : null;
        if (!btn) return;
        try { localStorage.setItem(KEY, isDark() ? 'light' : 'dark'); } catch (err) { /* sin almacenamiento: vale solo esta vista */ root.classList.toggle('dark'); }
        apply();
    });
    if (window.matchMedia) {
        var mq = window.matchMedia('(prefers-color-scheme: dark)');
        var onChange = function () { if (!stored()) apply(); };
        if (mq.addEventListener) mq.addEventListener('change', onChange); else if (mq.addListener) mq.addListener(onChange);
    }
})();
