# Quick Start Guide: Testing the Authentication Fix

## Overview
This health app now requires proper authentication to prevent unauthorized patient data access. The fix implements a secure, HIPAA-compliant auth flow.

## What Changed

### ✅ Frontend (`web/src/app/page.tsx`)
- Added authentication check on page load
- Unauthenticated users redirected to `/login`
- Loading screen shows "Verifying credentials..." during auth check
- Data only fetches after auth verification completes

### ✅ Backend (`agent-server/auth.py`)
- Improved error messages (user-friendly, security-conscious)
- Better token validation with comprehensive logging
- Proper error handling for expired/invalid sessions

### ✅ Fixed TypeScript Errors
- `AdherencePanel.tsx`: Added null safety for plan_id
- `MetabolicCanvas.tsx`: Added label property to state

---

## Local Testing Setup

### Prerequisites
```bash
# 1. Backend should be running
cd D:\pharmacogenomic-harness\agent-server
uv run uvicorn main:app --reload

# 2. Frontend should be running  
cd D:\pharmacogenomic-harness\web
npm run dev
```

### Step 1: Test Unauthenticated Access (Should Redirect to Login)

1. **Start fresh** (clear cookies if needed):
   ```bash
   # Open browser DevTools → Application → Cookies
   # Delete 'better-auth.session_token' if it exists
   ```

2. **Navigate** to `http://localhost:3000`
   
3. **Observe**:
   - ✅ Loading screen: "Verifying credentials..."
   - ✅ After ~1 second: Redirects to `http://localhost:3000/login`
   - ❌ App page should NOT render (if it does, auth check failed)

### Step 2: Test Login Flow (Should Authenticate)

1. **On login page**, enter test credentials:
   ```
   Email: doctor@clinic.com
   Password: testpass
   ```
   Or create new account:
   ```
   Email: test@example.com  
   Password: secure_password_123
   Name: Test Doctor
   ```

2. **Observe** login process:
   - ✅ "Authenticating..." spinner shows
   - ✅ After 1-2 seconds: Redirects to home page
   - ✅ App loads successfully
   - ✅ Patient list visible
   - ✅ Medication dropdown populated

3. **Verify session token**:
   ```javascript
   // In browser console (F12)
   document.cookie
   // Should include: 'better-auth.session_token=...'
   ```

### Step 3: Test API Requests (Should Include Auth Header)

1. **In browser DevTools**, go to **Network** tab

2. **Trigger an API call** (e.g., click on different patient or evaluation)

3. **Examine request**:
   ```
   GET /api/patients
   Request Headers:
   ✅ Authorization: Bearer 7aNIv3kI...
   ✅ Content-Type: application/json
   ```

4. **Verify response**:
   ```
   Status: 200 OK (not 401)
   Response: { "patients": [...] }
   ```

### Step 4: Test Expired Session (Should Redirect to Login)

1. **Clear the session token**:
   ```javascript
   // In browser console
   document.cookie = 'better-auth.session_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC;'
   ```

2. **Reload page** (`F5`)

3. **Observe**:
   - ✅ Loading screen: "Verifying credentials..."
   - ✅ Redirects to login page
   - ❌ App page should NOT load

### Step 5: Test Logout (Should Clear Session)

1. **From app**, click **profile icon** (top right)

2. **Select** "End Session"

3. **Observe**:
   - ✅ "Authenticating..." spinner briefly shows
   - ✅ Redirects to login page
   - ✅ Cookie is cleared

4. **Verify**:
   ```javascript
   // In console
   document.cookie
   // Should NOT include 'better-auth.session_token'
   ```

5. **Try navigating** to `http://localhost:3000`
   - ✅ Should redirect to login

---

## Backend Verification

### Check Server Logs

**Terminal running backend** should show:
```
INFO: Incoming API request
  method: GET
  path: /api/patients
  client_ip: 127.0.0.1
```

For authenticated requests:
```
Session found for userId: user_123
```

For unauthenticated requests:
```
Session not found in DB for token starting with 7aNIv3kI...
```

### Test Backend Directly (Optional)

```bash
# Without token (should fail with 401)
curl http://127.0.0.1:8000/api/patients

# Expected: 401 Unauthorized
# {
#   "error": {
#     "code": "AUTH_FAILED",
#     "message": "Authorization header missing or malformed"
#   }
# }

# With invalid token (should fail with 401)
curl -H "Authorization: Bearer invalid_token" \
  http://127.0.0.1:8000/api/patients

# Expected: 401 Unauthorized  
# {
#   "error": {
#     "code": "AUTH_FAILED", 
#     "message": "Invalid or expired session. Please log in again."
#   }
# }
```

---

## Troubleshooting

### Problem: Loading forever on home page

**Cause**: Auth check stuck or backend unreachable

**Solution**:
1. Check browser console (`F12`) for errors
2. Verify backend is running: `curl http://127.0.0.1:8000/`
3. Check Supabase connection in `.env`
4. Check logs in both terminals

### Problem: Login doesn't work

**Cause**: BetterAuth misconfigured or database issue

**Solution**:
1. Verify `DATABASE_URL` is correct in `web/.env.local`
2. Verify Supabase is reachable
3. Check browser console for BetterAuth errors
4. Try signup instead (creates new user)

### Problem: Still seeing 401 after login

**Cause**: Token not being sent or backend not recognizing it

**Solution**:
1. Check **Network** tab - Authorization header present?
2. Verify token in cookie: `document.cookie`
3. Check backend logs for session lookup error
4. Try logging out and back in

### Problem: Can access API without login

**Cause**: Auth check not working on frontend

**Solution**:
1. Hard refresh: `Ctrl+Shift+R` (clear cache)
2. Check browser console for errors in page.tsx
3. Verify `authClient.getSession()` is being called
4. Check network tab for auth check request

---

## Security Checklist

Before deployment to production:

- [ ] HTTPS enabled (Bearer tokens only transmitted over HTTPS)
- [ ] HttpOnly cookies enabled (BetterAuth default, verify in Supabase)
- [ ] CORS properly configured (only allow trusted origins)
- [ ] Rate limiting enabled on login endpoint
- [ ] Session timeout configured (7 days by default)
- [ ] Audit logs enabled for all API requests
- [ ] HIPAA compliance audit completed
- [ ] Penetration testing performed

---

## Next Steps

1. **Development**: Run tests locally ✅
2. **Staging**: Deploy to staging environment with real Supabase
3. **Production**: Enable HTTPS, configure firewall, enable HIPAA logging
4. **Monitoring**: Set up alerts for auth failures and suspicious activity

---

## Support

For issues or questions:
1. Check logs in both backend and frontend terminals
2. Review `AUTH_FIX_SUMMARY.md` for detailed documentation
3. Check browser DevTools (F12) for client-side errors
4. Verify Supabase connection and session table

---

**Status**: ✅ Ready for Testing  
**Last Updated**: May 31, 2026
