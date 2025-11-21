const PROD_API_BASE = "https://chessica-1nh3.onrender.com";
const isLocal = ["localhost", "127.0.0.1"].includes(window.location.hostname);
const API_BASE = `${isLocal ? "http://localhost:8000" : PROD_API_BASE}/api/v1`;
const AUTH_FEATURE_ENABLED = true; // can be overridden by backend feature flag or ?auth=dev

const refs = {
  signInForm: document.getElementById("signInForm"),
  signUpForm: document.getElementById("signUpForm"),
  signInEmail: document.getElementById("signInEmail"),
  signInCode: document.getElementById("signInCode"),
  signUpEmail: document.getElementById("signUpEmail"),
  signUpPassword: document.getElementById("signUpPassword"),
  signUpRemember: document.getElementById("signUpRemember"),
  sendCodeBtn: document.getElementById("sendCodeBtn"),
  signInSubmit: document.getElementById("signInSubmit"),
  signUpSubmit: document.getElementById("signUpSubmit"),
  toastHost: document.getElementById("toastHost"),
};

let featureEnabled = AUTH_FEATURE_ENABLED || window.location.search.includes("auth=dev");

function toggleEnabled(enabled) {
  const controls = [
    refs.signInEmail,
    refs.signInCode,
    refs.sendCodeBtn,
    refs.signInSubmit,
    refs.signUpEmail,
    refs.signUpPassword,
    refs.signUpRemember,
    refs.signUpSubmit,
  ];
  controls.forEach((el) => {
    if (!el) return;
    el.disabled = !enabled;
  });
  [refs.signInForm, refs.signUpForm].forEach((form) => {
    if (form) {
      form.setAttribute("aria-disabled", enabled ? "false" : "true");
    }
  });
}

function toast(message, tone = "good") {
  if (!refs.toastHost) return;
  const el = document.createElement("div");
  el.className = `toast ${tone === "bad" ? "bad" : tone === "warn" ? "warn" : "good"}`;
  el.textContent = message;
  refs.toastHost.appendChild(el);
  setTimeout(() => {
    el.remove();
  }, 3200);
}

function setBannerMessages(enabled) {
  const banner = document.querySelector(".auth-banner p");
  const pill = document.querySelector(".auth-banner .pill");
  if (banner) {
    banner.textContent = enabled
      ? "Preview mode enabled via ?auth=dev. These actions are stubbed."
      : "Accounts are being built. Access is currently disabled.";
  }
  if (pill) {
    pill.textContent = enabled ? "Dev preview" : "Private";
  }
}

async function requestCode(event) {
  event.preventDefault();
  if (!featureEnabled) {
    toast("Auth not available yet.", "bad");
    return;
  }
  const email = refs.signInEmail?.value?.trim();
  if (!email) {
    toast("Enter an email first.", "bad");
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/auth/send-code`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    if (!res.ok) throw new Error(`Send failed (${res.status})`);
    toast("Code sent. Check your email.", "good");
  } catch (err) {
    toast(err.message || "Failed to send code.", "bad");
  }
}

async function submitSignIn(event) {
  event.preventDefault();
  if (!featureEnabled) {
    toast("Auth not available yet.", "bad");
    return;
  }
  const email = refs.signInEmail?.value?.trim();
  const code = refs.signInCode?.value?.trim();
  if (!email || !code) {
    toast("Email and code required.", "bad");
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/auth/sign-in`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, code }),
    });
    if (!res.ok) throw new Error(`Sign-in failed (${res.status})`);
    const data = await res.json();
    toast(`Signed in as ${data?.user?.username || email}`, "good");
  } catch (err) {
    toast(err.message || "Sign-in failed.", "bad");
  }
}

async function submitSignUp(event) {
  event.preventDefault();
  if (!featureEnabled) {
    toast("Auth not available yet.", "bad");
    return;
  }
  const email = refs.signUpEmail?.value?.trim();
  const password = refs.signUpPassword?.value || "";
  const remember = Boolean(refs.signUpRemember?.checked);
  if (!email || !password) {
    toast("Email and password required.", "bad");
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/auth/sign-up`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, remember }),
    });
    if (!res.ok) throw new Error(`Sign-up failed (${res.status})`);
    const data = await res.json();
    toast(`Welcome, ${data?.user?.username || email}!`, "good");
  } catch (err) {
    toast(err.message || "Sign-up failed.", "bad");
  }
}

async function fetchFeatureFlag() {
  try {
    const res = await fetch(`${API_BASE}/auth/feature`);
    if (!res.ok) return;
    const data = await res.json();
    if (typeof data?.enabled === "boolean") {
      featureEnabled = data.enabled || featureEnabled;
    }
  } catch {
    // ignore
  }
}

function init() {
  fetchFeatureFlag().finally(() => {
    setBannerMessages(featureEnabled);
    toggleEnabled(featureEnabled);
  });
  if (refs.sendCodeBtn) refs.sendCodeBtn.addEventListener("click", requestCode);
  if (refs.signInForm) refs.signInForm.addEventListener("submit", submitSignIn);
  if (refs.signUpForm) refs.signUpForm.addEventListener("submit", submitSignUp);
}

init();
