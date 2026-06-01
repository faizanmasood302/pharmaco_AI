# 🧪 Postman API Testing Guide

## Overview
This guide shows how to test the protected APIs in Postman after the authentication fix.

---

## Step 1: Get a Valid Session Token

### Option A: Via Browser (Easiest)

**1. Login to the app:**
```
1. Go to http://localhost:3000/login
2. Enter credentials:
   - Email: doctor@clinic.com
   - Password: testpass
3. Click "Access Clinical Suite"
4. Wait for redirect to home page
```

**2. Copy the session token:**
```javascript
// Open Browser DevTools (F12)
// Go to Console tab
// Paste this and press Enter:

document.cookie
  .split(';')
  .find(c => c.includes('better-auth.session_token'))
  .split('=')[1]
```

**Example Output:**
```
"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyXzEyMyIsImlhdCI6MTY4Njc1ODAxMn0..."
```

**3. Copy the token value** (without quotes)

---

### Option B: Via curl (Advanced)

**1. First, get auth credentials from Supabase:**

```bash
# Set your credentials
EMAIL="doctor@clinic.com"
PASSWORD="testpass"
SUPABASE_URL="https://uunghmbfnhtaxbjdsted.supabase.co"
SUPABASE_ANON_KEY="sb_publishable_OAgcZZ7iTNLy7DxpfZ8rNw_OcgweVm4"

# Login and get session
curl -X POST "${SUPABASE_URL}/auth/v1/token?grant_type=password" \
  -H "apikey: ${SUPABASE_ANON_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\"}" | jq .
```

**Look for** `access_token` in the response - this is your session token.

---

## Step 2: Open Postman

### Create a New Request

1. **Open Postman** (download from postman.com if needed)
2. **Click** "+" to create new request
3. **Choose** GET method
4. **Enter URL**: `http://127.0.0.1:8000/api/patients`

---

## Step 3: Add Authorization Header

### Method 1: Manually Add Header (Recommended for Testing)

**1. Click "Headers" tab**
```
Headers
├─ Key: Authorization
├─ Value: Bearer {YOUR_TOKEN_HERE}
└─ (replace {YOUR_TOKEN_HERE} with actual token)
```

**2. Example:**
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**3. Click "Send"**

---

### Method 2: Use Postman Environment Variables

**Better for repeated testing:**

**1. Create Environment:**
```
Postman → Environments → Create New
Environment Name: PGX_Dev
Variable Name: sessionToken
Initial Value: {paste_your_token_here}
Current Value: {paste_your_token_here}
Save
```

**2. In request header:**
```
Authorization: Bearer {{sessionToken}}
```

**3. Select environment** from top-right dropdown before sending

---

## Step 4: Test Each Protected API

### ✅ Test 1: Get Patients

```
Method: GET
URL: http://127.0.0.1:8000/api/patients
Header: Authorization: Bearer {token}

Expected Response: 200 OK
{
  "patients": [
    {
      "id": "PGX-001",
      "display_name": "Maria Chen",
      "indication": "Chronic neuropathic pain",
      "phenotype": "Ultra-Rapid Metabolizer"
    },
    ...
  ]
}
```

---

### ✅ Test 2: Get Medications

```
Method: GET
URL: http://127.0.0.1:8000/api/medications
Header: Authorization: Bearer {token}

Expected Response: 200 OK
{
  "medications": [
    {
      "name": "Codeine",
      "enzyme": "CYP2D6",
      "is_prodrug": true
    },
    {
      "name": "Tramadol",
      "enzyme": "CYP2D6",
      "is_prodrug": true
    },
    ...
  ]
}
```

---

### ✅ Test 3: Get Evaluations

```
Method: GET
URL: http://127.0.0.1:8000/api/evaluations/PGX-001
Header: Authorization: Bearer {token}

Expected Response: 200 OK
{
  "evaluations": [
    {
      "id": "eval_123",
      "patient_id": "PGX-001",
      "medication": "Codeine",
      "flagged": false,
      "risk_level": "low",
      "created_at": "2026-05-31T...",
      "result_json": {...}
    }
  ]
}
```

---

### ✅ Test 4: Run Evaluation (POST Request)

```
Method: POST
URL: http://127.0.0.1:8000/api/evaluate
Header: Authorization: Bearer {token}
Header: Content-Type: application/json

Body (raw JSON):
{
  "patient_id": "PGX-001",
  "medication": "Codeine"
}

Expected Response: 200 OK
{
  "status": "success",
  "patient_id": "PGX-001",
  "medication": "Codeine",
  "flagged": true,
  "risk_level": "high",
  "reasoning": "Patient is Ultra-Rapid Metabolizer...",
  "recommendations": "Consider alternative medication...",
  ...
}
```

---

## Step 5: Verify All Responses

### ✅ Success Response (200 OK)
```
Status: 200 OK
Response has data
No error message
```

### ❌ Auth Failed Response (401 Unauthorized)
```
Status: 401 Unauthorized
Error: {
  "error": {
    "code": "AUTH_FAILED",
    "message": "Invalid or expired session. Please log in again.",
    "request_id": "..."
  }
}
```

**This means**: Your token is invalid or expired → Get a new token and retry

---

## Common Issues & Solutions

### Issue 1: "Authorization header missing or malformed"

**Cause**: Header not sent or wrong format

**Fix:**
```
❌ Wrong: Authorization: {token}
❌ Wrong: Authorization: Token {token}
✅ Correct: Authorization: Bearer {token}
```

---

### Issue 2: "Invalid or expired session. Please log in again."

**Cause**: Token expired or invalid

**Fix:**
1. Get new token (login again in browser)
2. Copy new token
3. Update Postman request

---

### Issue 3: "Cannot GET /api/patients"

**Cause**: Wrong URL or backend not running

**Fix:**
1. Verify backend is running: `uv run uvicorn main:app --reload`
2. Verify URL: `http://127.0.0.1:8000/api/patients` (port 8000, not 3000)

---

### Issue 4: Response shows "unauthorized"

**Cause**: Header not properly sent

**Fix:**
1. Check "Headers" tab in Postman
2. Verify Authorization header exists
3. Verify token is not expired
4. Try sending again

---

## Quick Copy-Paste Testing

### Full cURL Command (if you prefer CLI)

```bash
# 1. Get token (replace credentials)
curl -X POST "https://uunghmbfnhtaxbjdsted.supabase.co/auth/v1/token?grant_type=password" \
  -H "apikey: sb_publishable_OAgcZZ7iTNLy7DxpfZ8rNw_OcgweVm4" \
  -H "Content-Type: application/json" \
  -d '{"email":"doctor@clinic.com","password":"testpass"}' | jq '.access_token'

# 2. Copy the token output

# 3. Test /api/patients (replace TOKEN)
curl -H "Authorization: Bearer TOKEN" \
  http://127.0.0.1:8000/api/patients

# 4. Test /api/medications (replace TOKEN)
curl -H "Authorization: Bearer TOKEN" \
  http://127.0.0.1:8000/api/medications

# 5. Test /api/evaluations (replace TOKEN)
curl -H "Authorization: Bearer TOKEN" \
  http://127.0.0.1:8000/api/evaluations/PGX-001

# 6. Test POST /api/evaluate (replace TOKEN)
curl -X POST http://127.0.0.1:8000/api/evaluate \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"patient_id":"PGX-001","medication":"Codeine"}'
```

---

## Postman Collection (Ready to Import)

### Create manually or import this:

```json
{
  "info": {
    "name": "Pharmacogenomic Harness - PGX API",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Get Patients",
      "request": {
        "method": "GET",
        "header": [
          {
            "key": "Authorization",
            "value": "Bearer {{sessionToken}}",
            "type": "text"
          }
        ],
        "url": {
          "raw": "http://127.0.0.1:8000/api/patients",
          "protocol": "http",
          "host": ["127", "0", "0", "1"],
          "port": "8000",
          "path": ["api", "patients"]
        }
      }
    },
    {
      "name": "Get Medications",
      "request": {
        "method": "GET",
        "header": [
          {
            "key": "Authorization",
            "value": "Bearer {{sessionToken}}",
            "type": "text"
          }
        ],
        "url": {
          "raw": "http://127.0.0.1:8000/api/medications",
          "protocol": "http",
          "host": ["127", "0", "0", "1"],
          "port": "8000",
          "path": ["api", "medications"]
        }
      }
    },
    {
      "name": "Get Evaluations",
      "request": {
        "method": "GET",
        "header": [
          {
            "key": "Authorization",
            "value": "Bearer {{sessionToken}}",
            "type": "text"
          }
        ],
        "url": {
          "raw": "http://127.0.0.1:8000/api/evaluations/PGX-001",
          "protocol": "http",
          "host": ["127", "0", "0", "1"],
          "port": "8000",
          "path": ["api", "evaluations", "PGX-001"]
        }
      }
    },
    {
      "name": "Run Evaluation",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Authorization",
            "value": "Bearer {{sessionToken}}",
            "type": "text"
          },
          {
            "key": "Content-Type",
            "value": "application/json",
            "type": "text"
          }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\"patient_id\": \"PGX-001\", \"medication\": \"Codeine\"}"
        },
        "url": {
          "raw": "http://127.0.0.1:8000/api/evaluate",
          "protocol": "http",
          "host": ["127", "0", "0", "1"],
          "port": "8000",
          "path": ["api", "evaluate"]
        }
      }
    }
  ]
}
```

**To import:**
1. Postman → File → Import
2. Paste the JSON above
3. Click Import
4. Set `{{sessionToken}}` environment variable
5. Run requests

---

## Testing Workflow Summary

```
1️⃣ Login to app (http://localhost:3000/login)
   ↓
2️⃣ Copy session token (console: document.cookie)
   ↓
3️⃣ Create Postman request
   ↓
4️⃣ Add Authorization header: Bearer {token}
   ↓
5️⃣ Send request
   ↓
6️⃣ Verify 200 OK response with data
   ↓
✅ API works correctly!
```

---

## Advanced: Testing Without Browser Login

If you want to test without browser UI:

```bash
# 1. Create account via API
curl -X POST http://127.0.0.1:3000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123",
    "name": "Test User"
  }'

# 2. Login via API
curl -X POST http://127.0.0.1:3000/api/auth/signin/email \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123"
  }'

# 3. Extract token from response
# 4. Use in Postman as shown above
```

---

## Verification Checklist

- [ ] Backend running (`uv run uvicorn main:app --reload`)
- [ ] Frontend running (`npm run dev`)
- [ ] Got valid session token from browser
- [ ] Created Postman request to `/api/patients`
- [ ] Added `Authorization: Bearer {token}` header
- [ ] Sent request
- [ ] Received 200 OK with patient data
- [ ] Tested all 4 endpoints
- [ ] All returned data successfully

---

## Key Points

✅ **Always include** `Authorization: Bearer {token}` header  
✅ **Use correct URL** `http://127.0.0.1:8000` (not :3000)  
✅ **Token expires** after 7 days (get new one from browser login)  
✅ **Content-Type** required for POST requests: `application/json`  
✅ **Check backend logs** for errors if request fails  

---

**Status**: Ready to test ✅  
**Backend Port**: 8000  
**Frontend Port**: 3000  
**Auth Required**: YES (all endpoints protected)
