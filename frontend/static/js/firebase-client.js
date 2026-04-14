/**
 * frontend/static/js/firebase-client.js
 * ──────────────────────────────────────
 * Firebase Client SDK wrapper.
 * firebaseConfig is injected by Flask via the template (window.FIREBASE_CONFIG).
 * This file is loaded in every template that needs auth.
 */

import { initializeApp } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js";
import {
  getAuth,
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signOut,
  onAuthStateChanged as firebaseOnAuthStateChanged,
  updateProfile,
} from "https://www.gstatic.com/firebasejs/10.7.1/firebase-auth.js";

const requiredKeys = ["apiKey", "authDomain", "projectId", "appId"];
const firebaseConfig = window.FIREBASE_CONFIG || {};
const hasValidFirebaseConfig = requiredKeys.every((key) => {
  const value = firebaseConfig[key];
  return typeof value === "string" && value.trim();
});

let app = null;
let auth = null;

if (hasValidFirebaseConfig) {
  app = initializeApp(firebaseConfig);
  auth = getAuth(app);
} else {
  console.error("Firebase config missing or incomplete.", firebaseConfig);
}

function ensureAuthConfigured() {
  if (auth) return;
  throw new Error("Firebase is not configured. Set FIREBASE_API_KEY and related client env vars.");
}

function onAuthStateChanged(callback) {
  if (!auth) {
    callback(null);
    return () => {};
  }
  return firebaseOnAuthStateChanged(auth, callback);
}

export { auth, onAuthStateChanged, hasValidFirebaseConfig };

// ── Auth helpers ─────────────────────────────────────────────

/**
 * Register a new user, update their display name,
 * then sync the user doc to Firestore via our Flask backend.
 */
export async function registerUser(displayName, email, password) {
  try {
    ensureAuthConfigured();
    console.log("[SIGNUP] Step 1: Creating user with Firebase Auth...");
    const cred = await createUserWithEmailAndPassword(auth, email, password);
    console.log("[SIGNUP] Step 2: Firebase account created, user ID:", cred.user.uid);
    
    console.log("[SIGNUP] Step 3: Updating user profile with display name...");
    await updateProfile(cred.user, { displayName });
    console.log("[SIGNUP] Step 4: Display name updated");
    
    console.log("[SIGNUP] Step 5: Getting ID token...");
    const idToken = await cred.user.getIdToken();
    console.log("[SIGNUP] Step 6: ID token obtained (length:", idToken.substring(0,20) + "...)");
    
    // Tell our Flask backend to create the Firestore user document
    console.log("[SIGNUP] Step 7: Calling /api/auth/sync-user to create Firestore user...");
    const syncRes = await fetch("/api/auth/sync-user", {
      method: "POST",
      headers: { 
        "Content-Type": "application/json", 
        "Authorization": `Bearer ${idToken}` 
      },
      body: JSON.stringify({ displayName, email }),
    });

    console.log("[SIGNUP] Step 8: sync-user response status:", syncRes.status);
    
    if (!syncRes.ok) {
      const errData = await syncRes.json().catch(() => ({}));
      console.error("[SIGNUP] ERROR: Sync-user failed!", {
        status: syncRes.status,
        statusText: syncRes.statusText,
        errorData: errData,
      });
      throw new Error(errData.error || `Backend sync failed with status ${syncRes.status}: ${errData.message || syncRes.statusText}`);
    }

    console.log("[SIGNUP] Step 9: Success! User synced to backend.");
    return cred.user;
  } catch (err) {
    console.error("[SIGNUP] EXCEPTION CAUGHT:", {
      name: err.name,
      code: err.code,
      message: err.message,
      stack: err.stack,
    });
    throw err;
  }
}

/**
 * Sign in, return the Firebase User object.
 */
export async function loginUser(email, password) {
  ensureAuthConfigured();
  const cred = await signInWithEmailAndPassword(auth, email, password);
  return cred.user;
}

/**
 * Sign out the current user.
 */
export async function logoutUser() {
  ensureAuthConfigured();
  await signOut(auth);
}

/**
 * Get a fresh ID token for the currently signed-in user.
 * Pass forceRefresh=true if the token may be near expiry.
 */
export async function getIdToken(forceRefresh = false) {
  ensureAuthConfigured();
  const user = auth.currentUser;
  if (!user) throw new Error("No user signed in");
  return user.getIdToken(forceRefresh);
}

/**
 * Convenience: returns the current user or null.
 */
export function currentUser() {
  return auth?.currentUser || null;
}

// Shared global bridge used by legacy page helpers in utils.js and templates.
window.XSSGuardFirebase = {
  onAuthChange(callback) {
    return onAuthStateChanged(callback);
  },
  async getToken(forceRefresh = false) {
    return getIdToken(forceRefresh);
  },
  async signOut() {
    return logoutUser();
  },
  currentUser,
};
