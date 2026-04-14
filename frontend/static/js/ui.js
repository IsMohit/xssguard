/**
 * frontend/static/js/ui.js
 * UI utilities and animations
 */

let matrixAnimationId = null;

/**
 * Initialize the Matrix background animation
 */
export function initMatrix() {
  const canvas = document.getElementById("matrix-canvas");
  if (!canvas) return;

  const ctx = canvas.getContext("2d");
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;

  // Simple Matrix effect—random falling characters
  const chars = "01アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン";
  const charSize = 16;
  const columns = Math.floor(canvas.width / charSize);
  const drops = Array(columns).fill(0);

  function draw() {
    ctx.fillStyle = "rgba(0, 0, 0, 0.05)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.fillStyle = "#00ff00";
    ctx.font = `${charSize}px monospace`;

    for (let i = 0; i < drops.length; i++) {
      const char = chars[Math.floor(Math.random() * chars.length)];
      ctx.fillText(char, i * charSize, drops[i] * charSize);

      if (drops[i] * charSize > canvas.height && Math.random() > 0.95) {
        drops[i] = 0;
      }
      drops[i]++;
    }

    matrixAnimationId = requestAnimationFrame(draw);
  }

  draw();

  // Responsive canvas resize
  window.addEventListener("resize", () => {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  });
}

/**
 * Hide the matrix canvas with fade-out animation
 */
export function hideMatrix() {
  const canvas = document.getElementById("matrix-canvas");
  if (!canvas) return;

  // Cancel animation loop
  if (matrixAnimationId) {
    cancelAnimationFrame(matrixAnimationId);
  }

  // Fade out the canvas
  canvas.style.transition = "opacity 0.8s ease";
  canvas.style.opacity = "0";

  // Remove it after fade completes
  setTimeout(() => {
    canvas.style.display = "none";
  }, 800);
}

/**
 * Hide the loading screen
 */
export function hideLoadingScreen() {
  const loadingScreen = document.getElementById("loading-screen");
  if (loadingScreen) {
    loadingScreen.style.display = "none";
  }
  // Hide matrix after loading screen is done
  hideMatrix();
}

/**
 * Show the loading screen
 */
export function showLoadingScreen() {
  const loadingScreen = document.getElementById("loading-screen");
  if (loadingScreen) {
    loadingScreen.style.display = "flex";
  }
}

/**
 * Toast notifications
 */
export function toast(type, label, message) {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const t = document.createElement("div");
  t.className = `toast ${type}`;
  t.innerHTML = `<div class="toast-label">// ${label}</div>${escHtml(message)}`;
  container.appendChild(t);
  setTimeout(() => t.remove(), 3600);
}

/**
 * HTML escaping
 */
export function escHtml(s) {
  return String(s).replace(/[&<>"']/g, m =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m])
  );
}

/**
 * Copy to clipboard
 */
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

/**
 * Loading button state utility
 */
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
