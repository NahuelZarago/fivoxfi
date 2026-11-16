/*
 * Formularios de acceso: errores en rojo DEBAJO de cada campo (sin globos del navegador)
 * y medidor de contraseña. Se activa con <form data-auth-form novalidate>.
 *
 * Atributos por campo (todos opcionales):
 *   required | minlength | type="email" | data-match="#otroCampo" | data-label="Nombre"
 * El medidor se activa con data-strength en el campo de contraseña.
 * Siempre se vuelve a validar en el servidor: esto es solo comodidad.
 */
(function () {
    'use strict';
    var EMAIL = /^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$/;
    var LEVELS = [
        { name: 'Muy débil', color: 'bg-red-500', text: 'text-red-600', segs: 1 },
        { name: 'Débil', color: 'bg-red-500', text: 'text-red-600', segs: 1 },
        { name: 'Aceptable', color: 'bg-amber-500', text: 'text-amber-600', segs: 2 },
        { name: 'Buena', color: 'bg-lime-500', text: 'text-lime-700', segs: 3 },
        { name: 'Fuerte', color: 'bg-green-600', text: 'text-green-700', segs: 4 }
    ];

    function checks(p) {
        return {
            length: p.length >= 8, long: p.length >= 12,
            lower: /[a-z]/.test(p), upper: /[A-Z]/.test(p),
            digit: /\d/.test(p), symbol: /[^A-Za-z0-9]/.test(p)
        };
    }
    function levelFor(p, c) {
        if (!p) return null;
        var score = Object.keys(c).filter(function (k) { return c[k]; }).length;
        if (!c.length) return LEVELS[0];                         // menos de 8: nunca pasa de "muy débil"
        if (score <= 3) return LEVELS[1];
        if (score === 4) return LEVELS[2];
        if (score === 5) return LEVELS[3];
        return LEVELS[4];
    }

    function errorBox(field) { return field.form.querySelector('[data-error-for="' + field.id + '"]'); }
    function setError(field, message) {
        var box = errorBox(field);
        if (box) { box.textContent = message || ''; box.classList.toggle('hidden', !message); }
        field.classList.toggle('border-red-400', !!message);
        field.classList.toggle('focus:ring-red-400', !!message);
        field.classList.toggle('border-gray-200', !message);
        field.setAttribute('aria-invalid', message ? 'true' : 'false');
    }

    function validateField(field) {
        var v = field.value, label = field.dataset.label || 'Este campo';
        if (field.required && !v.trim()) return label + ' es obligatorio.';
        if (!v) return '';
        if (field.type === 'email' && !EMAIL.test(v.trim())) return 'Ingresá un email válido, por ejemplo nombre@empresa.com.';
        var min = parseInt(field.getAttribute('minlength') || '0', 10);
        if (min && v.length < min) return label + ' debe tener al menos ' + min + ' caracteres.';
        if (field.hasAttribute('data-strength')) {
            var c = checks(v);
            if (!c.length) return 'La contraseña debe tener al menos 8 caracteres.';
            if (!c.lower && !c.upper) return 'La contraseña debe incluir al menos una letra.';
            if (!c.digit) return 'La contraseña debe incluir al menos un número.';
        }
        if (field.dataset.match) {
            var other = field.form.querySelector(field.dataset.match);
            if (other && other.value !== v) return 'Las contraseñas no coinciden.';
        }
        return '';
    }

    function updateMeter(field) {
        var meter = field.form.querySelector('[data-meter-for="' + field.id + '"]');
        if (!meter) return;
        var p = field.value, c = checks(p), level = levelFor(p, c);
        meter.classList.toggle('hidden', !p);
        var segs = meter.querySelectorAll('[data-seg]');
        segs.forEach(function (s, i) {
            s.className = 'h-1.5 flex-1 rounded-full transition-colors ' + (level && i < level.segs ? level.color : 'bg-gray-200');
        });
        var label = meter.querySelector('[data-meter-label]');
        label.textContent = level ? 'Seguridad: ' + level.name : '';
        label.className = 'text-xs font-semibold mt-1.5 ' + (level ? level.text : '');
        meter.querySelectorAll('[data-rule]').forEach(function (li) {
            var ok = c[li.dataset.rule];
            li.className = ok ? 'text-green-700' : 'text-gray-400';
            li.querySelector('[data-icon]').textContent = ok ? '✓' : '○';
        });
    }

    function addToggle(field) {
        var wrap = document.createElement('div');
        wrap.className = 'relative';
        field.parentNode.insertBefore(wrap, field);
        wrap.appendChild(field);
        field.classList.add('pr-16');
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.textContent = 'Ver';
        btn.className = 'absolute right-3 top-1/2 -translate-y-1/2 text-xs font-semibold text-gray-500 hover:text-gray-800';
        btn.setAttribute('aria-label', 'Mostrar u ocultar contraseña');
        btn.addEventListener('click', function () {
            var show = field.type === 'password';
            field.type = show ? 'text' : 'password';
            btn.textContent = show ? 'Ocultar' : 'Ver';
        });
        wrap.appendChild(btn);
    }

    document.querySelectorAll('form[data-auth-form]').forEach(function (form) {
        var fields = Array.prototype.slice.call(form.querySelectorAll('input[id]'));
        fields.forEach(function (f) {
            if (f.type === 'password' && f.hasAttribute('data-toggle')) addToggle(f);
            f.addEventListener('blur', function () { if (f.value || f.dataset.touched) setError(f, validateField(f)); f.dataset.touched = '1'; });
            f.addEventListener('input', function () {
                if (f.hasAttribute('data-strength')) updateMeter(f);
                if (f.dataset.touched || errorBox(f) && !errorBox(f).classList.contains('hidden')) setError(f, validateField(f));
                // si cambia la contraseña, revalidar la confirmación
                fields.forEach(function (o) { if (o.dataset.match === '#' + f.id && o.value) setError(o, validateField(o)); });
            });
            if (f.hasAttribute('data-strength')) updateMeter(f);
        });
        form.addEventListener('submit', function (e) {
            var first = null;
            fields.forEach(function (f) {
                var msg = validateField(f);
                setError(f, msg);
                if (msg && !first) first = f;
            });
            if (first) { e.preventDefault(); first.focus(); }
        });
    });
})();
