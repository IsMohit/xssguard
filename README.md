# 🛡️ XSSGuard — Full-Stack XSS Detection Platform

ML-powered XSS detection API · Flask backend · Firebase auth/DB · Dark cyberpunk UI

---

## Project Structure

```
xssguard/
├── run.py                              ← Entry point
├── requirements.txt
├── .env.example                        ← Copy to .env, fill in keys
├── .gitignore
├── README.md
│
├── config/
│   ├── settings.py                     ← All config from .env
│   └── firebase_service_account.json.example
│
├── backend/
│   ├── app.py                          ← Flask app factory
│   ├── firebase_init.py                ← Admin SDK init
│   ├── ml_loader.py                    ← Model + tokenizer loader
│   ├── routes/
│   │   ├── pages.py                    ← HTML page serving
│   │   ├── auth.py                     ← /api/auth/*
│   │   ├── xss.py                      ← /api/xss/*  (detection)
│   │   └── projects.py                 ← /api/projects/* (CRUD)
│   ├── middleware/
│   │   └── auth_middleware.py          ← @require_auth / @require_api_key
│   └── utils/
│       ├── xss_detector.py             ← CNN-LSTM + Bleach logic
│       └── logger.py                   ← JSONL attack logger
│
├── frontend/
│   ├── templates/
│   │   ├── base.html                   ← Injects Firebase config
│   │   ├── landing.html
│   │   ├── signin.html
│   │   ├── signup.html
│   │   ├── dashboard.html
│   │   └── project.html
│   └── static/
│       ├── css/theme.css               ← Full design system
│       └── js/
│           ├── firebase-client.js      ← Firebase SDK wrapper
│           └── utils.js                ← Shared helpers
│
├── ml_model/                           ← PUT YOUR .h5 AND .pkl HERE
│   └── (xss_cnn_lstm_model.h5)
│   └── (tokenizer.pkl)
│
└── logs/
    ├── app.log
    └── malicious_attempts.jsonl
```

---

## Quick Start

```bash
# 1. Install deps
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Copy ML model files
cp /path/to/xss_cnn_lstm_model.h5  ml_model/
cp /path/to/tokenizer.pkl           ml_model/

# 3. Set up .env
cp .env.example .env
# → Fill in Firebase keys (see Firebase Setup below)

# 4. Run
python run.py
# Open http://localhost:5000
```

---

## Firebase Setup

### A — Create project
1. https://console.firebase.google.com → Add project → name it → Create

### B — Enable Auth
Authentication → Sign-in method → Email/Password → Enable → Save

### C — Create Firestore
Firestore Database → Create database → Production mode → pick region → Enable

Paste these Firestore Security Rules:
```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /users/{uid} {
      allow read, write: if request.auth.uid == uid;
    }
    match /projects/{id} {
      allow read, write: if request.auth.uid == resource.data.uid;
      allow create: if request.auth != null;
    }
    match /api_keys/{id} { allow read: if false; }
    match /scan_logs/{id} {
      allow read: if request.auth.uid == resource.data.uid;
      allow create: if true;
    }
  }
}
```

### D — Service Account (Flask backend)
Project Settings → Service accounts → Generate new private key
→ Save as `config/firebase_service_account.json`  ⚠️ Never commit this file!

### E — Web App Config (frontend JS)
Project Settings → Your apps → </> → Register app
Copy the config values into your `.env`:
```env
FIREBASE_API_KEY=AIzaSy...
FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_STORAGE_BUCKET=your-project.appspot.com
FIREBASE_MESSAGING_SENDER_ID=123456789
FIREBASE_APP_ID=1:123456789:web:abcdef
```

---

## API Reference

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | /api/xss/check | X-API-Key | Single input scan |
| POST | /api/xss/batch-check | X-API-Key | Up to 100 inputs |
| GET  | /api/xss/health | — | Model health status |
| GET  | /api/xss/model-info | — | Architecture info |
| POST | /api/auth/sync-user | Bearer token | Sync user to Firestore |
| GET  | /api/auth/me | Bearer token | Get user profile |
| GET  | /api/projects/ | Bearer token | List projects |
| POST | /api/projects/ | Bearer token | Create project + key |
| GET  | /api/projects/<id> | Bearer token | Get project |
| DELETE | /api/projects/<id> | Bearer token | Delete project |
| POST | /api/projects/<id>/rotate-key | Bearer token | Rotate API key |
| GET  | /api/projects/<id>/logs | Bearer token | Project scan logs |
