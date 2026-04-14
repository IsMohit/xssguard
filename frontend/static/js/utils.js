/**
 * utils.js — Shared helpers used by all pages
 */

/* ── Toast notifications ──────────────────────────────────── */
export function showToast(type, label, message) {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const t = document.createElement("div");
  t.className = `toast ${type}`;
  t.innerHTML = `<div class="toast-label">// ${label}</div>${escHtml(message)}`;
  container.appendChild(t);
  setTimeout(() => t.remove(), 3600);
}

/* ── HTML escaping ────────────────────────────────────────── */
export function escHtml(s) {
  return String(s).replace(/[&<>"']/g, m =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m])
  );
}

/* ── Copy to clipboard ────────────────────────────────────── */
export async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    return true;
  }
}

/* ── Loading button state ─────────────────────────────────── */
export function setLoading(btn, loading, loadingText = "PROCESSING...") {
  if (loading) {
    btn._origText = btn.textContent;
    btn.textContent = loadingText;
    btn.disabled = true;
  } else {
    btn.textContent = btn._origText || "SUBMIT";
    btn.disabled = false;
  }
}

/* ── Auth guard: redirect to /signin if not logged in ─────── */
export function requireAuth(callback) {
  const fb = window.XSSGuardFirebase;
  if (!fb) {
    window.location.href = "/signin";
    return;
  }
  fb.onAuthChange((user) => {
    if (!user) {
      window.location.href = "/signin";
    } else {
      callback(user);
    }
  });
}

/* ── Redirect logged-in users away from auth pages ───────── */
export function redirectIfAuthed() {
  const fb = window.XSSGuardFirebase;
  if (!fb) return;
  fb.onAuthChange((user) => {
    if (user) window.location.href = "/dashboard";
  });
}

/* ── Format ISO date ──────────────────────────────────────── */
export function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso._seconds ? iso._seconds * 1000 : iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function formatDateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso._seconds ? iso._seconds * 1000 : iso);
  return d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

/* ── Authenticated fetch wrapper ──────────────────────────── */
export async function authFetch(url, options = {}) {
  const token = await window.XSSGuardFirebase.getToken();
  return fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(options.headers || {}),
    },
  });
}

/* ── Matrix background ────────────────────────────────────── */
export function initMatrix() {
  const canvas = document.getElementById("matrix-bg");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  function resize() { canvas.width = window.innerWidth; canvas.height = window.innerHeight; }
  resize();
  window.addEventListener("resize", resize);
  const chars = "01アイウエカキクサシスXSSINJECT<>alert()script/onerror=";
  const fs = 13;
  let cols = Math.floor(canvas.width / fs);
  let drops = Array(cols).fill(1);
  window.addEventListener("resize", () => {
    cols = Math.floor(canvas.width / fs);
    drops = Array(cols).fill(1);
  });
  function draw() {
    ctx.fillStyle = "rgba(10,10,8,0.04)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#F5C500";
    ctx.font = `${fs}px Share Tech Mono`;
    for (let i = 0; i < drops.length; i++) {
      ctx.fillText(chars[Math.floor(Math.random() * chars.length)], i * fs, drops[i] * fs);
      if (drops[i] * fs > canvas.height && Math.random() > 0.975) drops[i] = 0;
      drops[i]++;
    }
  }
  setInterval(draw, 55);
}

/* ── Loading screen dismissal ─────────────────────────────── */
export function dismissLoadingScreen(delay = 1800) {
  window.addEventListener("load", () => {
    setTimeout(() => {
      const ls = document.getElementById("loading-screen");
      if (!ls) return;
      ls.style.transition = "opacity .5s ease";
      ls.style.opacity = "0";
      setTimeout(() => ls.remove(), 520);
    }, delay);
  });
}
