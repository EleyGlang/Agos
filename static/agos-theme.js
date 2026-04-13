/**
 * agos-theme.js
 * Agos EP-Bluelife Management System
 *
 * Provides:
 *  - Dark / Light mode toggle (persists via localStorage)
 *  - Unified sidebar toggle for mobile
 *  - Logout modal helpers  ← FIXED: uses .open class (matches agos-theme.css)
 *  - Topbar date rendering
 *
 * Include once at the BOTTOM of every page's <body>:
 *   <script src="{{ url_for('static', filename='agos-theme.js') }}"></script>
 *
 * CSS contract (agos-theme.css):
 *   .agos-modal-overlay        { display: none; }
 *   .agos-modal-overlay.open   { display: flex; }
 */

/* ─────────────────────────────────────────────
   THEME PERSISTENCE
───────────────────────────────────────────── */
(function initTheme() {
  const saved = localStorage.getItem('agos-theme') || 'light';
  document.documentElement.setAttribute('data-theme', saved);
  if (document.body) document.body.setAttribute('data-theme', saved);

  document.addEventListener('DOMContentLoaded', () => {
    syncThemeCheckboxes(saved);
    renderTopbarDate();
    initSidebar();
    bindModalBackdrops();
  });
})();

function setTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  document.body.setAttribute('data-theme', theme);
  localStorage.setItem('agos-theme', theme);
  syncThemeCheckboxes(theme);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  setTheme(current === 'dark' ? 'light' : 'dark');
}

function syncThemeCheckboxes(theme) {
  document.querySelectorAll('.agos-theme-checkbox').forEach(cb => {
    cb.checked = (theme === 'dark');
  });
}

/* ─────────────────────────────────────────────
   TOPBAR DATE
───────────────────────────────────────────── */
function renderTopbarDate() {
  const el = document.getElementById('topbar-date');
  if (el) {
    el.textContent = new Date().toLocaleDateString('en-PH', {
      weekday: 'short', year: 'numeric', month: 'short', day: 'numeric'
    });
  }
}

/* ─────────────────────────────────────────────
   SIDEBAR (mobile)
───────────────────────────────────────────── */
function initSidebar() {
  checkWidth();
  window.addEventListener('resize', checkWidth);
}

function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('overlay');
  if (!sidebar) return;
  const isHidden = sidebar.classList.contains('-translate-x-full');
  if (isHidden) {
    sidebar.classList.remove('-translate-x-full');
    if (overlay) overlay.style.display = 'block';
  } else {
    sidebar.classList.add('-translate-x-full');
    if (overlay) overlay.style.display = 'none';
  }
}

function closeSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('overlay');
  if (sidebar) sidebar.classList.add('-translate-x-full');
  if (overlay) overlay.style.display = 'none';
}

function checkWidth() {
  const isMobile = window.innerWidth < 768;
  const sidebar  = document.getElementById('sidebar');
  const menuBtn  = document.getElementById('menu-btn');
  const overlay  = document.getElementById('overlay');
  if (!sidebar) return;

  if (isMobile) {
    if (menuBtn) { menuBtn.style.display = 'flex'; }
    if (!sidebar.classList.contains('-translate-x-full')) {
      sidebar.classList.add('-translate-x-full');
    }
    if (overlay) overlay.style.display = 'none';
  } else {
    if (menuBtn) { menuBtn.style.display = 'none'; }
    sidebar.classList.remove('-translate-x-full');
    if (overlay) overlay.style.display = 'none';
  }
}

/* ─────────────────────────────────────────────
   GENERIC MODAL HELPERS
   All modals: .agos-modal-overlay  (display:none by default)
               .agos-modal-overlay.open  (display:flex — set by CSS)
───────────────────────────────────────────── */
function openModal(id) {
  const m = document.getElementById(id);
  if (m) m.classList.add('open');
}

function closeModal(id) {
  const m = document.getElementById(id);
  if (m) m.classList.remove('open');
}

/* ─────────────────────────────────────────────
   LOGOUT MODAL
───────────────────────────────────────────── */
function openLogoutModal()  { openModal('logout-modal');  }
function closeLogoutModal() { closeModal('logout-modal'); }

function confirmLogout() {
  // Every page has: <a data-logout-url="{{ url_for('logout') }}" style="display:none">
  const el = document.querySelector('[data-logout-url]');
  if (el) {
    window.location.href = el.getAttribute('data-logout-url');
    return;
  }
  // Hard fallback
  window.location.href = '/logout';
}

/* ─────────────────────────────────────────────
   GLOBAL DISMISS: ESC key + backdrop click
───────────────────────────────────────────── */
function bindModalBackdrops() {
  // ESC closes all open modals
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.agos-modal-overlay.open')
        .forEach(m => m.classList.remove('open'));
    }
  });

  // Clicking the dark backdrop closes that modal
  document.querySelectorAll('.agos-modal-overlay').forEach(modal => {
    modal.addEventListener('click', e => {
      if (e.target === modal) modal.classList.remove('open');
    });
  });
}
