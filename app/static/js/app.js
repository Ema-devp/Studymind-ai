/**
 * Core app behaviors shared across every page: theme toggling, sidebar
 * collapse/mobile-open, toast notifications, and small UI helpers.
 */

const StudyMind = (() => {
  const CSRF_TOKEN = document.querySelector('meta[name="csrf-token"]')?.content;

  function getCsrfHeaders(extra = {}) {
    return { "X-CSRFToken": CSRF_TOKEN, "Content-Type": "application/json", ...extra };
  }

  // ---------------- Theme ----------------
  // The server renders the correct data-theme attribute on every page load
  // (from the user's saved setting), so there's nothing to reconcile here -
  // this only handles the explicit toggle click, applying it instantly to
  // the DOM and persisting it in the background. No localStorage involved:
  // a second client-side copy of the theme was previously fighting with the
  // server-rendered value on every navigation, causing a visible flicker.
  function initTheme() {
    const root = document.documentElement;

    document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const current = root.getAttribute("data-theme") || "dark";
        const next = current === "dark" ? "light" : "dark";
        root.setAttribute("data-theme", next);
        fetch("/settings/theme", {
          method: "POST",
          headers: getCsrfHeaders(),
          body: JSON.stringify({ theme: next }),
        }).catch(() => {});
      });
    });
  }

  // ---------------- Sidebar ----------------
  function initSidebar() {
    const sidebar = document.querySelector(".sidebar");
    if (!sidebar) return;

    document.querySelectorAll("[data-sidebar-collapse]").forEach((btn) => {
      btn.addEventListener("click", () => sidebar.classList.toggle("collapsed"));
    });
    document.querySelectorAll("[data-sidebar-mobile-toggle]").forEach((btn) => {
      btn.addEventListener("click", () => sidebar.classList.toggle("mobile-open"));
    });
  }

  // ---------------- Toasts ----------------
  function ensureToastContainer() {
    let el = document.querySelector(".toast-container");
    if (!el) {
      el = document.createElement("div");
      el.className = "toast-container";
      document.body.appendChild(el);
    }
    return el;
  }

  function toast(message, type = "info", timeout = null) {
    const container = ensureToastContainer();
    const el = document.createElement("div");
    el.className = `toast ${type}`;
    el.innerHTML = `<span>${message}</span>`;
    container.appendChild(el);
    const effectiveTimeout = timeout ?? (type === "error" ? 9000 : 4200);
    setTimeout(() => {
      el.style.opacity = "0";
      el.style.transition = "opacity 200ms ease";
      setTimeout(() => el.remove(), 200);
    }, effectiveTimeout);
  }

  function initFlashMessages() {
    document.querySelectorAll("[data-flash]").forEach((el) => {
      toast(el.dataset.flash, el.dataset.flashType || "info");
    });
  }

  // ---------------- Dropdowns ----------------
  function initDropdowns() {
    document.addEventListener("click", (e) => {
      const trigger = e.target.closest("[data-dropdown-trigger]");
      document.querySelectorAll(".dropdown-menu.open").forEach((menu) => {
        if (!trigger || menu !== trigger.nextElementSibling) menu.classList.remove("open");
      });
      if (trigger) {
        trigger.nextElementSibling?.classList.toggle("open");
      }
    });
  }

  // ---------------- Confirm dialogs (native, kept simple) ----------------
  function initConfirms() {
    document.querySelectorAll("[data-confirm]").forEach((el) => {
      el.addEventListener("submit", (e) => {
        if (!confirm(el.dataset.confirm)) e.preventDefault();
      });
      el.addEventListener("click", (e) => {
        if (el.tagName === "BUTTON" && !confirm(el.dataset.confirm)) e.preventDefault();
      });
    });
  }

  function init() {
    initTheme();
    initSidebar();
    initFlashMessages();
    initDropdowns();
    initConfirms();
  }

  document.addEventListener("DOMContentLoaded", init);

  return { toast, getCsrfHeaders };
})();
