(function () {
    'use strict';

    /* Toast auto-dismiss */
    document.querySelectorAll('.ff-toast').forEach(function (toast) {
        var delay = parseInt(toast.dataset.dismiss || '5000', 10);
        setTimeout(function () {
            toast.classList.add('hiding');
            setTimeout(function () { toast.remove(); }, 300);
        }, delay);
    });

    document.querySelectorAll('.ff-toast-close').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var toast = btn.closest('.ff-toast');
            if (toast) {
                toast.classList.add('hiding');
                setTimeout(function () { toast.remove(); }, 300);
            }
        });
    });

    /* Bottom drawer (Historique / Compte) */
    var drawerBtn = document.getElementById('ffDrawerBtn');
    var drawer = document.getElementById('ffDrawer');
    var drawerOverlay = document.getElementById('ffDrawerOverlay');
    var drawerClose = document.getElementById('ffDrawerClose');

    function openDrawer() {
        if (drawer) drawer.classList.add('active');
        if (drawerOverlay) drawerOverlay.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    function closeDrawer() {
        if (drawer) drawer.classList.remove('active');
        if (drawerOverlay) drawerOverlay.classList.remove('active');
        document.body.style.overflow = '';
    }

    if (drawerBtn) drawerBtn.addEventListener('click', openDrawer);
    if (drawerClose) drawerClose.addEventListener('click', closeDrawer);
    if (drawerOverlay) drawerOverlay.addEventListener('click', closeDrawer);

    /* Generic modal helpers */
    window.ffOpenModal = function (id) {
        var el = document.getElementById(id);
        if (el) {
            el.classList.add('active');
            document.body.style.overflow = 'hidden';
        }
    };

    window.ffCloseModal = function (id) {
        var el = document.getElementById(id);
        if (el) {
            el.classList.remove('active');
            document.body.style.overflow = '';
        }
    };

    document.querySelectorAll('[data-ff-close]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var target = btn.getAttribute('data-ff-close');
            if (target) ffCloseModal(target);
        });
    });

    document.querySelectorAll('.ff-overlay').forEach(function (overlay) {
        overlay.addEventListener('click', function (e) {
            if (e.target === overlay) {
                overlay.classList.remove('active');
                document.body.style.overflow = '';
            }
        });
    });

    /* Copy referral link */
    window.ffCopyText = function (elementId) {
        var el = document.getElementById(elementId);
        if (!el) return;
        var text = el.innerText || el.textContent;
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(function () {
                ffShowCopyFeedback();
            });
        } else {
            var tmp = document.createElement('textarea');
            tmp.value = text;
            document.body.appendChild(tmp);
            tmp.select();
            document.execCommand('copy');
            document.body.removeChild(tmp);
            ffShowCopyFeedback();
        }
    };

    function ffShowCopyFeedback() {
        var existing = document.getElementById('ff-copy-toast');
        if (existing) existing.remove();
        var container = document.querySelector('.ff-toast-container');
        if (!container) return;
        var toast = document.createElement('div');
        toast.id = 'ff-copy-toast';
        toast.className = 'ff-toast ff-toast--success';
        toast.innerHTML = '<i class="fas fa-check-circle"></i><span>Lien copié dans le presse-papiers !</span>';
        container.appendChild(toast);
        setTimeout(function () {
            toast.classList.add('hiding');
            setTimeout(function () { toast.remove(); }, 300);
        }, 3000);
    }

    /* Password toggle */
    document.querySelectorAll('[data-toggle-pwd]').forEach(function (btn) {
        var inputId = btn.getAttribute('data-toggle-pwd');
        var input = document.getElementById(inputId);
        if (!input) return;
        btn.addEventListener('click', function () {
            var isHidden = input.type === 'password';
            input.type = isHidden ? 'text' : 'password';
            var icon = btn.querySelector('i');
            if (icon) {
                icon.classList.toggle('fa-eye', !isHidden);
                icon.classList.toggle('fa-eye-slash', isHidden);
            }
        });
    });

    /* Signup policy checkbox */
    var policyCheck = document.getElementById('ffPolicyCheck');
    var signBtn = document.getElementById('ffSignBtn');
    if (policyCheck && signBtn) {
        function toggleSignBtn() {
            signBtn.disabled = !policyCheck.checked;
        }
        policyCheck.addEventListener('change', toggleSignBtn);
        toggleSignBtn();
    }
})();
