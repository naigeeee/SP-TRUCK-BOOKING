# Knowing who the user is

The `dev` environment is always behind Ninja Van sign-in, so these headers are always present
there. In `production`, they are present only when Google SSO is on (the Access tab).

With sign-in on, the platform injects `X-Forwarded-Email` and `X-Forwarded-User` headers
into every backend request. **Never build a login page, OAuth flow or session handling** —
just read the header:

```python
email = request.headers.get("X-Forwarded-Email")
```

The browser never sees these headers, so a frontend must ask a backend endpoint such as
`/api/me`. Headers are stripped on `/health` and on any public paths, and are spoofable if
SSO is off — so don't trust them for anything sensitive when SSO isn't enabled.
