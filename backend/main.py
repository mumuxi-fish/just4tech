import uuid
import json
import os as _os
import hashlib
import asyncio
from urllib.parse import unquote
from datetime import datetime, date, timedelta
from functools import wraps

from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
import httpx

from database import get_db, init_db

# ===== API Key Auth for machine-to-machine calls =====
API_KEY = _os.environ.get("API_KEY", _os.environ.get("MCP_API_KEY"))
if not API_KEY:
    raise RuntimeError(
        "API_KEY environment variable is required. "
        "Generate one with: python3 -c 'import secrets; print(secrets.token_hex(24))'"
    )

def require_api_key(request: Request):
    """Check X-API-Key header for machine-to-machine access."""
    api_key = request.headers.get("X-API-Key", "")
    if api_key == API_KEY:
        return True
    return False

def api_key_required(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        request = kwargs.get("request")
        if request and require_api_key(request):
            return await func(*args, **kwargs)
        # Also allow session-based auth (admin users)
        user = None
        if request:
            user = check_session(request) if hasattr(request, "cookies") else None
        if user:
            return await func(*args, **kwargs)
        raise HTTPException(status_code=401, detail="API key required. Set X-API-Key header or log in as admin.")
    return wrapper

app = FastAPI(title="AI Tool Hub Admin")

# ── Simple response cache (module-level, TTL-based) ──
_cache = {}
def cached(key: str, ttl_seconds: int = 300):
    """Decorator: cache response for `ttl_seconds`. Keyed by `key`."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            entry = _cache.get(key)
            if entry and (datetime.now() - entry["ts"]).total_seconds() < ttl_seconds:
                return entry["data"]
            result = await func(*args, **kwargs)
            _cache[key] = {"ts": datetime.now(), "data": result}
            return result
        return wrapper
    return decorator

def invalidate_cache(*keys: str):
    """Invalidate cache entries by key (e.g., on content change)."""
    for k in keys:
        _cache.pop(k, None)

# ── Simple in-memory rate limiter ──
_rate_limits = {}
def check_rate_limit(key: str, max_requests: int = 10, window_seconds: int = 60) -> bool:
    """Return True if request is allowed, False if rate-limited."""
    now = datetime.now()
    entry = _rate_limits.get(key)
    if entry:
        count, start = entry
        if (now - start).total_seconds() < window_seconds:
            if count >= max_requests:
                return False
            _rate_limits[key] = (count + 1, start)
        else:
            _rate_limits[key] = (1, now)
    else:
        _rate_limits[key] = (1, now)
    return True

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://just4.tech",
        "https://www.just4.tech",
    ],
    allow_origin_regex=r"^https?://localhost(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount /static/ for direct file serving (icon cache, uploads, etc.)
# Cached icons are served at filesystem speed, bypassing Python route handlers
_static_dir = _os.path.join(_os.path.dirname(__file__), "static")
_os.makedirs(_static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=_static_dir), name="static")

# Manual Jinja2 setup
_tpl_dir = _os.path.join(_os.path.dirname(__file__), "templates")
_jinja_env = Environment(loader=FileSystemLoader(_tpl_dir), autoescape=True)

def render(template_name, **context):
    template = _jinja_env.get_template(template_name)
    return HTMLResponse(template.render(**context))

SESSIONS = {}       # token -> {username, expires_at}

SESSION_TTL = 86400 * 7  # 7 days

def check_session(request):
    token = request.cookies.get("session")
    if not token:
        return None
    entry = SESSIONS.get(token)
    if not entry:
        return None
    if datetime.now() > entry["expires_at"]:
        del SESSIONS[token]
        return None
    return entry["username"]

def _cleanup_expired_sessions():
    """Remove expired sessions. Called on login to avoid a background task."""
    now = datetime.now()
    expired = [t for t, e in SESSIONS.items() if now > e["expires_at"]]
    for t in expired:
        del SESSIONS[t]

_bcrypt_module = None
_bcrypt_available = None

def hash_password(password):
    """Hash password with bcrypt. Falls back to salted SHA-256 only if bcrypt is unavailable."""
    global _bcrypt_module, _bcrypt_available
    if _bcrypt_available is None:
        try:
            import bcrypt
            _bcrypt_module = bcrypt
            _bcrypt_available = True
        except ImportError:
            _bcrypt_available = False

    if _bcrypt_available:
        return _bcrypt_module.hashpw(password.encode(), _bcrypt_module.gensalt()).decode()
    else:
        import hashlib
        import os as _os
        salt = _os.urandom(32).hex()
        return "sha256$" + salt + "$" + hashlib.sha256((salt + password).encode()).hexdigest()

def verify_password(password, stored_hash):
    """Verify a password against a stored hash. Supports bcrypt and salted SHA-256 (legacy)."""
    if stored_hash.startswith("$2b$") or stored_hash.startswith("$2a$"):
        import bcrypt
        return bcrypt.checkpw(password.encode(), stored_hash.encode())
    elif stored_hash.startswith("sha256$"):
        import hashlib
        _, salt, h = stored_hash.split("$")
        return hashlib.sha256((salt + password).encode()).hexdigest() == h
    else:
        # Legacy: unsalted SHA-256
        import hashlib
        return hashlib.sha256(password.encode()).hexdigest() == stored_hash

@app.middleware("http")
async def track_views(request: Request, call_next):
    response = await call_next(request)
    if request.method == "GET" and not request.url.path.startswith(("/admin", "/api", "/static")):
        today = date.today().isoformat()
        path = request.url.path
        conn = get_db()
        try:
            conn.execute("""
                INSERT INTO page_views (path, date, count) VALUES (?, ?, 1)
                ON CONFLICT(path, date) DO UPDATE SET count = count + 1
            """, (path, today))
            conn.commit()
        except:
            pass
        finally:
            conn.close()
    return response

# ===================== ADMIN ROUTES =====================

@app.post("/api/admin/change-username")
async def api_change_username(request: Request):
    user = check_session(request)
    if not user:
        raise HTTPException(401)
    data = await request.json()
    new_username = data.get("new_username", "").strip()
    password = data.get("password", "")
    if len(new_username) < 3:
        return JSONResponse({"ok": False, "error": "Username must be at least 3 characters"})
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (user,)).fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        conn.close()
        return JSONResponse({"ok": False, "error": "Password is incorrect"})
    # Check if new username exists
    existing = conn.execute("SELECT id FROM users WHERE username = ?", (new_username,)).fetchone()
    if existing:
        conn.close()
        return JSONResponse({"ok": False, "error": "Username already taken"})
    conn.execute("UPDATE users SET username = ? WHERE username = ?", (new_username, user))
    conn.commit()
    conn.close()
    # Update session
    token = request.cookies.get("session", "")
    if token in SESSIONS:
        SESSIONS[token]["username"] = new_username
    return JSONResponse({"ok": True, "username": new_username})

@app.post("/api/admin/change-password")
async def api_change_password(request: Request):
    user = check_session(request)
    if not user:
        raise HTTPException(401)
    data = await request.json()
    old_pw = data.get("old_password", "")
    new_pw = data.get("new_password", "")
    if len(new_pw) < 6:
        return JSONResponse({"ok": False, "error": "New password must be at least 6 characters"})
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (user,)).fetchone()
    if not row or not verify_password(old_pw, row["password_hash"]):
        conn.close()
        return JSONResponse({"ok": False, "error": "Current password is incorrect"})
    conn.execute("UPDATE users SET password_hash = ? WHERE username = ?", (hash_password(new_pw), user))
    conn.commit()
    conn.close()
    return JSONResponse({"ok": True})

@app.post("/api/admin/login")
async def api_admin_login(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(f"login:{client_ip}", max_requests=5, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")
    data = await request.json()
    username = data.get("username")
    password = data.get("password")
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    if user and verify_password(password, user["password_hash"]):
        _cleanup_expired_sessions()
        token = uuid.uuid4().hex
        SESSIONS[token] = {"username": username, "expires_at": datetime.now() + timedelta(seconds=SESSION_TTL)}
        resp = JSONResponse({"ok": True})
        secure = not _os.environ.get("DEV_MODE", "").lower() in ("1", "true", "yes")
        resp.set_cookie(key="session", value=token, httponly=True, secure=secure, samesite='lax', max_age=86400*7, path="/")
        return resp
    return JSONResponse({"ok": False, "error": "Invalid username or password"}, status_code=401)

@app.post("/api/admin/logout")
async def api_admin_logout():
    return JSONResponse({"ok": True})

@app.get("/api/posts")
async def api_posts(request: Request, status: str = "", page: int = 0, limit: int = 20):
    conn = get_db()
    user = check_session(request)

    base_query = "FROM posts"
    params = []
    if status:
        if status == "all":
            base_query += " ORDER BY created_at DESC"
        else:
            base_query += " WHERE status = ? ORDER BY created_at DESC"
            params.append(status)
    elif user or require_api_key(request):
        base_query += " ORDER BY created_at DESC"
    else:
        base_query += " WHERE status = 'active' ORDER BY created_at DESC"

    # Pagination: page=0 means all (backward compatible)
    if page > 0:
        offset = (page - 1) * limit
        count_row = conn.execute(f"SELECT COUNT(*) as cnt {base_query}", params).fetchone()
        total = count_row["cnt"]
        rows = conn.execute(f"SELECT * {base_query} LIMIT ? OFFSET ?", params + [limit, offset]).fetchall()
        conn.close()
        return {"posts": [dict(r) for r in rows], "total": total, "page": page, "limit": limit}
    else:
        rows = conn.execute(f"SELECT * {base_query}", params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

@app.get("/api/posts/{post_id}")
async def api_post(post_id: int, request: Request):
    conn = get_db()
    user = check_session(request)
    if user or require_api_key(request):
        post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    else:
        post = conn.execute("SELECT * FROM posts WHERE id = ? AND status = 'active'", (post_id,)).fetchone()
    conn.close()
    if not post:
        raise HTTPException(404)
    return dict(post)

@app.get("/api/posts/slug/{slug}")
async def api_post_by_slug(slug: str, request: Request):
    conn = get_db()
    user = check_session(request)
    if user or require_api_key(request):
        post = conn.execute("SELECT * FROM posts WHERE slug = ?", (slug,)).fetchone()
    else:
        post = conn.execute("SELECT * FROM posts WHERE slug = ? AND status = 'active'", (slug,)).fetchone()
    conn.close()
    if not post:
        raise HTTPException(status_code=404, detail="Not Found")
    return dict(post)

@app.post("/api/posts")
async def api_create_post(request: Request):
    user = check_session(request)
    if not (user or require_api_key(request)):
        raise HTTPException(401)
    data = await request.json()
    conn = get_db()
    conn.execute("""
        INSERT INTO posts (slug, title, content, category, excerpt, tags, author, status, cover_image, icon, subtitle, external_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (data["slug"], data["title"], data["content"], data.get("category", "review"),
          data.get("excerpt", ""), data.get("tags", ""), data.get("author", "AI Tool Hub Team"),
          data.get("status", "draft"), data.get("cover_image", ""),
          data.get("icon", ""), data.get("subtitle", ""), data.get("external_url", "")))
    conn.commit()
    post_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    invalidate_cache("rss_feed", "sitemap")
    return {"ok": True, "id": post_id}

@app.put("/api/posts/{post_id}")
async def api_update_post(post_id: int, request: Request):
    user = check_session(request)
    if not (user or require_api_key(request)):
        raise HTTPException(401)
    data = await request.json()
    conn = get_db()
    existing = conn.execute("SELECT slug, title, content, category, excerpt, tags, author, status, cover_image, icon, subtitle, external_url FROM posts WHERE id=?", (post_id,)).fetchone()
    if not existing:
        conn.close()
        raise HTTPException(404)
    conn.execute("""
        UPDATE posts SET slug=?, title=?, content=?, category=?, excerpt=?, tags=?, author=?, status=?, cover_image=?, icon=?, subtitle=?, external_url=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (
        data.get("slug", existing["slug"]),
        data.get("title", existing["title"]),
        data.get("content", existing["content"]),
        data.get("category", existing["category"]),
        data.get("excerpt", existing["excerpt"] or ""),
        data.get("tags", existing["tags"] or ""),
        data.get("author", existing["author"] or "AI Tool Hub Team"),
        data.get("status", existing["status"] or "draft"),
        data.get("cover_image", existing["cover_image"] or ""),
        data.get("icon", existing["icon"] or ""),
        data.get("subtitle", existing["subtitle"] or ""),
        data.get("external_url", existing["external_url"] or ""),
        post_id
    ))
    conn.commit()
    conn.close()
    invalidate_cache("rss_feed", "sitemap")
    return {"ok": True}

@app.delete("/api/posts/{post_id}")
async def api_delete_post(post_id: int, request: Request):
    user = check_session(request)
    if not user:
        raise HTTPException(401)
    conn = get_db()
    conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()
    invalidate_cache("rss_feed", "sitemap")
    return {"ok": True}

@app.get("/api/stats/overview")
async def api_stats_overview(request: Request):
    user = check_session(request)
    if not user:
        raise HTTPException(401)
    conn = get_db()
    total_views = conn.execute("SELECT SUM(count) as c FROM page_views").fetchone()["c"] or 0
    today_views = conn.execute("SELECT SUM(count) as c FROM page_views WHERE date = ?",
                               (date.today().isoformat(),)).fetchone()["c"] or 0
    top_pages = conn.execute(
        "SELECT path, SUM(count) as cnt FROM page_views GROUP BY path ORDER BY cnt DESC LIMIT 10"
    ).fetchall()
    daily_views = conn.execute(
        "SELECT date, SUM(count) as cnt FROM page_views GROUP BY date ORDER BY date LIMIT 30"
    ).fetchall()
    conn.close()
    return {
        "total_views": total_views,
        "today_views": today_views,
        "top_pages": [dict(p) for p in top_pages],
        "daily_views": [dict(d) for d in daily_views],
    }

@app.on_event("startup")
async def startup():
    init_db()
    # Pre-warm icon cache in background (don't block startup)
    asyncio.create_task(_prewarm_icon_cache())


async def _prewarm_icon_cache():
    """Fetch all AI tool icons in the background and populate disk cache.
    This ensures icons are served from local disk on first user request."""
    conn = get_db()
    tools = conn.execute(
        "SELECT icon FROM posts WHERE category='AI Tool' AND status='active' AND icon LIKE 'http%'"
    ).fetchall()
    conn.close()

    icons = [t["icon"].strip() for t in tools if t["icon"] and t["icon"].strip().startswith(("http://", "https://"))]
    if not icons:
        return

    print(f"[icon-cache] Pre-warming {len(icons)} tool icons...")
    cached = 0
    for remote_url in icons:
        cache_key = hashlib.sha256(remote_url.encode()).hexdigest()
        cache_path = _os.path.join(ICON_CACHE_DIR, cache_key)
        if _os.path.exists(cache_path):
            cached += 1
            continue
        try:
            fetch_url = _rewrite_icon_url(remote_url)
            async with httpx.AsyncClient(timeout=ICON_FETCH_TIMEOUT, headers=ICON_FETCH_HEADERS) as client:
                resp = await client.get(fetch_url, follow_redirects=True)
                if resp.status_code == 200:
                    body = resp.read()
                    if len(body) <= ICON_MAX_SIZE:
                        _os.makedirs(ICON_CACHE_DIR, exist_ok=True)
                        with open(cache_path, "wb") as f:
                            f.write(body)
                        cached += 1
        except Exception:
            pass  # Individual failures are non-fatal; will retry on first user request
    print(f"[icon-cache] Pre-warmed {cached}/{len(icons)} icons")

# ===================== SOFTWARE (Admin) =====================

@app.get("/api/software")
async def api_software():
    conn = get_db()
    items = conn.execute("SELECT * FROM posts WHERE category='AI Tool' AND status='active' ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(s) for s in items]

@app.get("/api/software/{sw_id}")
async def api_software_one(sw_id: int):
    conn = get_db()
    sw = conn.execute("SELECT * FROM posts WHERE id = ? AND category='AI Tool'", (sw_id,)).fetchone()
    conn.close()
    if not sw:
        raise HTTPException(404)
    return dict(sw)

@app.get("/api/software/slug/{slug}")
async def api_software_by_slug(slug: str):
    conn = get_db()
    sw = conn.execute("SELECT * FROM posts WHERE slug = ? AND category='AI Tool'", (slug,)).fetchone()
    conn.close()
    if not sw:
        raise HTTPException(status_code=404, detail="Not Found")
    return dict(sw)


# ── Icon proxy: fetch + cache external tool icons ──
ICON_CACHE_DIR = _os.path.join(_os.path.dirname(__file__), "static", "icon-cache")
ICON_MAX_SIZE = 512 * 1024  # 512 KiB max per icon
ICON_FETCH_TIMEOUT = 5.0    # seconds
ICON_FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Just4Tech/1.0; +https://just4.tech)",
    "Accept": "image/avif,image/webp,image/png,image/svg+xml,image/*;q=0.8,*/*;q=0.5",
}

# URL rewriters for icon sources that block datacenter IPs.
# Each returns a replacement fetch URL (or None to keep original).
import re
def _rewrite_icon_url(url: str) -> str:
    """Rewrite known icon-service URLs to alternatives that don't block servers."""
    # favicon.im → Google favicon service (server-friendly)
    m = re.match(r'https?://favicon\.im/(.+)$', url)
    if m:
        domain = m.group(1).rstrip('/')
        return f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
    return url  # keep original

@app.get("/api/icon-proxy")
async def api_icon_proxy(url: str = ""):
    """Proxy external icon URLs through our domain with disk caching.
    Pass the remote URL as a URL-encoded `url` query parameter.
    """
    if not url:
        raise HTTPException(status_code=400, detail="Missing `url` query parameter")

    # Decode the remote URL
    remote_url = unquote(url)

    # Only allow http/https
    if not remote_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Only http/https URLs are allowed")

    # Hash the original URL → cache key (consistent with frontend)
    cache_key = hashlib.sha256(remote_url.encode()).hexdigest()
    cache_path = _os.path.join(ICON_CACHE_DIR, cache_key)

    # Serve from disk cache if available (FileResponse = zero-copy, supports Range)
    if _os.path.exists(cache_path):
        return FileResponse(
            cache_path,
            media_type=_guess_mime_from_path(cache_path),
            headers={"Cache-Control": "public, max-age=604800"},
        )

    # Rewrite URL for sources that block datacenter IPs (e.g. favicon.im → Google)
    fetch_url = _rewrite_icon_url(remote_url)

    # Fetch from remote
    try:
        async with httpx.AsyncClient(timeout=ICON_FETCH_TIMEOUT, headers=ICON_FETCH_HEADERS) as client:
            resp = await client.get(fetch_url, follow_redirects=True)
            if resp.status_code != 200:
                raise HTTPException(status_code=404, detail=f"Remote icon returned {resp.status_code}")
            body = resp.read()
            if len(body) > ICON_MAX_SIZE:
                raise HTTPException(status_code=400, detail="Remote icon exceeds size limit")
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Failed to fetch remote icon")

    content_type = resp.headers.get("content-type", "image/png")

    # Write to disk cache
    _os.makedirs(ICON_CACHE_DIR, exist_ok=True)
    with open(cache_path, "wb") as f:
        f.write(body)

    return Response(
        content=body,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=604800"},
    )


def _guess_mime_from_path(path: str) -> str:
    """Guess MIME type from file extension."""
    ext = _os.path.splitext(path)[1].lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
        ".ico": "image/x-icon",
    }.get(ext, "image/png")


@app.get("/api/projects")
async def api_get_projects(request: Request):
    conn = get_db()
    rows = conn.execute("SELECT * FROM posts WHERE category='Project' AND status='active' ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/projects/{project_id}")
async def api_get_project(project_id: int):
    conn = get_db()
    project = conn.execute("SELECT * FROM posts WHERE id = ? AND category='Project'", (project_id,)).fetchone()
    conn.close()
    if not project:
        raise HTTPException(404)
    return dict(project)




# ===================== PAGES API =====================

@app.get("/api/pages")
async def api_get_pages(request: Request):
    user = check_session(request)
    if not user:
        raise HTTPException(401)
    conn = get_db()
    pages = conn.execute("SELECT id, slug, title, meta_title, meta_description FROM site_pages ORDER BY slug").fetchall()
    conn.close()
    return [dict(p) for p in pages]

@app.get("/api/page/{slug}")
async def api_get_public_page(slug: str):
    conn = get_db()
    page = conn.execute("SELECT * FROM site_pages WHERE slug = ?", (slug,)).fetchone()
    conn.close()
    if not page:
        raise HTTPException(404)
    return dict(page)

@app.get("/api/pages/{page_id}")
async def api_get_page(page_id: int, request: Request):
    user = check_session(request)
    if not user:
        raise HTTPException(401)
    conn = get_db()
    page = conn.execute("SELECT * FROM site_pages WHERE id = ?", (page_id,)).fetchone()
    conn.close()
    if not page:
        raise HTTPException(404)
    return dict(page)

@app.put("/api/pages/{page_id}")
async def api_update_page(page_id: int, request: Request):
    user = check_session(request)
    if not user:
        raise HTTPException(401)
    data = await request.json()
    conn = get_db()
    conn.execute("""UPDATE site_pages SET title=?, meta_title=?, meta_description=?, content=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
        (data.get("title",""), data.get("meta_title",""), data.get("meta_description",""),
         data.get("content",""), page_id))
    conn.commit()
    conn.close()
    return {"ok": True}

# ===================== CONTACT MESSAGES API =====================

@app.get("/api/admin/contact-messages")
async def api_get_contact_messages(request: Request):
    user = check_session(request)
    if not user:
        raise HTTPException(401)
    conn = get_db()
    msgs = conn.execute("SELECT * FROM contact_messages ORDER BY created_at DESC LIMIT 100").fetchall()
    conn.close()
    return [dict(m) for m in msgs]

@app.delete("/api/admin/contact-messages/{msg_id}")
async def api_delete_contact_message(msg_id: int, request: Request):
    user = check_session(request)
    if not user:
        raise HTTPException(401)
    conn = get_db()
    conn.execute("DELETE FROM contact_messages WHERE id = ?", (msg_id,))
    conn.commit()
    conn.close()
    return {"ok": True}

# ===================== AI SETTINGS API =====================

@app.get("/api/admin/ai-settings")
async def api_get_ai_settings(request: Request):
    user = check_session(request)
    if not user:
        raise HTTPException(401)
    conn = get_db()
    settings = conn.execute("SELECT * FROM ai_config").fetchall()
    conn.close()
    result = {}
    for s in settings:
        result[s["key"]] = s["value"]
    return result

@app.post("/api/admin/ai-settings")
async def api_save_ai_settings(request: Request):
    user = check_session(request)
    if not user:
        raise HTTPException(401)
    data = await request.json()
    conn = get_db()
    for key, value in data.items():
        conn.execute("INSERT OR REPLACE INTO ai_config (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (key, str(value)))
    conn.commit()
    conn.close()
    return {"ok": True}

# ===================== ANALYTICS API =====================

@app.get("/api/admin/analytics")
async def api_get_analytics(request: Request):
    user = check_session(request)
    if not user:
        raise HTTPException(401)
    conn = get_db()
    total_views = conn.execute("SELECT COALESCE(SUM(count), 0) as c FROM page_views").fetchone()["c"]
    today_views = conn.execute("SELECT COALESCE(SUM(count), 0) as c FROM page_views WHERE date = date('now')").fetchone()["c"]
    total_posts = conn.execute("SELECT COUNT(*) as c FROM posts").fetchone()["c"]
    total_software = conn.execute("SELECT COUNT(*) as c FROM posts WHERE category='AI Tool'").fetchone()["c"]
    total_projects = conn.execute("SELECT COUNT(*) as c FROM posts WHERE category='Project'").fetchone()["c"]
    contact_count = conn.execute("SELECT COUNT(*) as c FROM contact_messages").fetchone()["c"]
    
    # Daily views for chart (last 30 days)
    daily_views = conn.execute(
        "SELECT date, SUM(count) as cnt FROM page_views GROUP BY date ORDER BY date DESC LIMIT 30"
    ).fetchall()
    
    # Top pages
    top_pages = conn.execute(
        "SELECT path, SUM(count) as cnt FROM page_views GROUP BY path ORDER BY cnt DESC LIMIT 10"
    ).fetchall()
    
    conn.close()
    return {
        "total_views": total_views,
        "today_views": today_views,
        "total_posts": total_posts,
        "total_software": total_software,
        "total_projects": total_projects,
        "contact_count": contact_count,
        "daily_views": [{"date": r["date"], "count": r["cnt"]} for r in daily_views],
        "top_pages": [{"path": r["path"], "count": r["cnt"]} for r in top_pages]
    }

# ===================== PUBLIC SOFTWARE ROUTES =====================

@app.get("/software/", response_class=HTMLResponse)
async def public_software_list(request: Request):
    conn = get_db()
    all_sw = conn.execute("SELECT * FROM software WHERE status='active' ORDER BY featured DESC, created_at DESC").fetchall()
    conn.close()
    categories = set()
    for s in all_sw:
        if s["category"]:
            categories.add(s["category"])
    return render("public/software_list.html", request=request, software=all_sw, categories=sorted(categories))

@app.get("/software/{slug}", response_class=HTMLResponse)
async def public_software_detail(request: Request, slug: str):
    conn = get_db()
    sw = conn.execute("SELECT * FROM software WHERE slug=? AND status='active'", (slug,)).fetchone()
    if not sw:
        raise HTTPException(404)
    related = conn.execute("SELECT * FROM software WHERE category=? AND id!=? AND status='active' LIMIT 4", (sw["category"], sw["id"])).fetchall()
    conn.close()
    return render("public/software_detail.html", request=request, sw=sw, related=related)

# ===================== PAGES (Site Content Editor) =====================

@app.get("/api/pages/list")
async def api_list_pages():
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT page_path FROM content_blocks ORDER BY page_path").fetchall()
    conn.close()
    return {"pages": [r["page_path"] for r in rows]}

@app.get("/api/stats")
async def api_get_stats():
    conn = get_db()
    stats = {}
    for table in ["posts", "content_blocks", "site_pages"]:
        try:
            c = conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()
            stats[table] = c["cnt"]
        except Exception:
            stats[table] = 0
    conn.close()
    return stats

# Public page rendering
@app.get("/page/{slug}", response_class=HTMLResponse)
async def public_page(request: Request, slug: str):
    conn = get_db()
    page = conn.execute("SELECT * FROM site_pages WHERE slug = ?", (slug,)).fetchone()
    conn.close()
    if not page:
        raise HTTPException(404)
    meta_title = page["meta_title"] or page["title"]
    meta_desc = page["meta_description"] or ""
    return render("public/page.html", request=request, page=page, meta_title=meta_title, meta_desc=meta_desc)

# ===================== CONTENT BLOCKS (Page Content Editor) =====================

@app.get("/api/admin/session-status")
async def admin_session_status(request: Request):
    user = check_session(request)
    return {"authenticated": user is not None, "user": user}

@app.get("/api/content/pages/list")
async def api_content_pages_list():
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT page_path FROM content_blocks ORDER BY page_path").fetchall()
    conn.close()
    return {"pages": [r["page_path"] for r in rows]}

@app.get("/api/content/{page_path:path}")
async def api_content_get(page_path: str):
    if not page_path:
        page_path = "/"
    conn = get_db()
    blocks = conn.execute("SELECT block_key, content, content_type FROM content_blocks WHERE page_path = ?", (page_path,)).fetchall()
    conn.close()
    return {"blocks": [{"block_key": b["block_key"], "content": b["content"], "content_type": b["content_type"]} for b in blocks]}

@app.put("/api/content/{page_path:path}/{block_key}")
async def api_content_update(page_path: str, block_key: str, request: Request):
    if not page_path:
        page_path = "/"
    user = check_session(request)
    if not user:
        raise HTTPException(401)
    data = await request.json()
    content = data.get("content", "")
    content_type = data.get("content_type", "text")
    conn = get_db()
    conn.execute("""
        INSERT INTO content_blocks (page_path, block_key, content, content_type, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(page_path, block_key) DO UPDATE SET
            content = excluded.content,
            content_type = excluded.content_type,
            updated_at = CURRENT_TIMESTAMP
    """, (page_path, block_key, content, content_type))
    conn.commit()
    conn.close()
    return {"ok": True}

@app.post("/api/content/{page_path:path}/bulk")
async def api_content_bulk(page_path: str, request: Request):
    if not page_path:
        page_path = "/"
    user = check_session(request)
    if not user:
        raise HTTPException(401)
    data = await request.json()
    blocks = data.get("blocks", [])
    conn = get_db()
    for block in blocks:
        conn.execute("""
            INSERT INTO content_blocks (page_path, block_key, content, content_type, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(page_path, block_key) DO UPDATE SET
                content = excluded.content,
                content_type = excluded.content_type,
                updated_at = CURRENT_TIMESTAMP
        """, (page_path, block["block_key"], block.get("content", ""), block.get("content_type", "text")))
    conn.commit()
    conn.close()
    return {"ok": True}

@app.delete("/api/content/{page_path:path}/{block_key}")
async def api_content_delete(page_path: str, block_key: str, request: Request):
    if not page_path:
        page_path = "/"
    user = check_session(request)
    if not user:
        raise HTTPException(401)
    conn = get_db()
    conn.execute("DELETE FROM content_blocks WHERE page_path = ? AND block_key = ?", (page_path, block_key))
    conn.commit()
    conn.close()
    return {"ok": True}

@app.post("/api/contact")
async def api_contact(request: Request):
    data = await request.json()
    name = data.get("name", "")
    email = data.get("email", "")
    subject_key = data.get("subject", "general")
    msg_body = data.get("message", "")
    subject_labels = {
        "general": "General Inquiry", "tool-suggestion": "Tool Suggestion",
        "blog-topic": "Blog Topic Request", "bug": "Bug Report",
        "feedback": "Feedback", "other": "Other",
    }
    subject_label = subject_labels.get(subject_key, "General Inquiry")
    conn = get_db()
    conn.execute("INSERT INTO contact_messages (name, email, subject, message) VALUES (?,?,?,?)", (name, email, subject_label, msg_body))
    conn.commit()
    conn.close()
    try:
        import httpx
        httpx.post("http://localhost:18085/send-email", json={
            "name": name, "email": email, "subject": subject_key, "message": msg_body
        }, timeout=5)
    except:
        pass
    return {"ok": True, "message": "Message received. Thanks!"}

# ======== Slug-Based Post Operations ========
@app.put("/api/posts/slug/{slug}")
async def api_update_post_by_slug(slug: str, request: Request):
    user = check_session(request)
    if not (user or require_api_key(request)):
        raise HTTPException(401)
    data = await request.json()
    conn = get_db()
    existing = conn.execute("SELECT id FROM posts WHERE slug=?", (slug,)).fetchone()
    if not existing:
        conn.close()
        raise HTTPException(404)
    
    fields = []
    values = []
    for f in ["title","content","category","excerpt","tags","author","status","cover_image","slug","icon","subtitle","external_url"]:
        if f in data:
            fields.append(f"{f}=?")
            values.append(data[f])
    if not fields:
        conn.close()
        return {"ok": False, "error": "No fields to update"}
    values.append(slug)
    conn.execute(f"UPDATE posts SET {', '.join(fields)}, updated_at=CURRENT_TIMESTAMP WHERE slug=?", values)
    conn.commit()
    conn.close()
    invalidate_cache("rss_feed", "sitemap")
    return {"ok": True}

@app.delete("/api/posts/slug/{slug}")
async def api_delete_post_by_slug(slug: str, request: Request):
    user = check_session(request)
    if not (user or require_api_key(request)):
        raise HTTPException(401)
    conn = get_db()
    conn.execute("DELETE FROM posts WHERE slug=?", (slug,))
    conn.commit()
    conn.close()
    invalidate_cache("rss_feed", "sitemap")
    return {"ok": True, "slug": slug}

# ===================== IMAGE UPLOAD =====================

@app.post("/api/admin/upload")
async def api_upload_image(request: Request):
    user = check_session(request)
    if not user:
        raise HTTPException(401)
    import uuid as _uuid, os as _os
    try:
        form = await request.form()
        file = form.get("file")
        if not file:
            return JSONResponse({"ok": False, "error": "No file provided"})
        # Validate file type
        filename = file.filename or "image.png"
        ext = _os.path.splitext(filename)[1].lower()
        if ext not in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"):
            return JSONResponse({"ok": False, "error": "Invalid file type: " + ext})
        # Save to static dir
        safe_name = _uuid.uuid4().hex[:12] + ext
        upload_dir = _os.path.join(_os.path.dirname(__file__), "static", "uploads")
        upload_dir2 = "/var/www/aitoolhub/spa/uploads"
        _os.makedirs(upload_dir, exist_ok=True)
        _os.makedirs(upload_dir2, exist_ok=True)
        contents = await file.read()
        # Check file size (max 5MB)
        if len(contents) > 5 * 1024 * 1024:
            return JSONResponse({"ok": False, "error": "File too large (max 5MB)"})
        with open(_os.path.join(upload_dir, safe_name), "wb") as f:
            f.write(contents)
        with open(_os.path.join(upload_dir2, safe_name), "wb") as f:
            f.write(contents)
        url = "/uploads/" + safe_name
        return JSONResponse({"ok": True, "url": url})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)})

@app.get("/rss.xml", response_class=Response)
@cached("rss_feed", ttl_seconds=600)
async def rss_feed():
    conn = get_db()
    posts = conn.execute("SELECT * FROM posts WHERE status='active' ORDER BY created_at DESC LIMIT 20").fetchall()
    conn.close()
    from datetime import date, timezone
    from email.utils import format_datetime
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>')
    lines.append('<title>Just4Tech Blog</title><link>https://just4.tech/blog</link>')
    lines.append('<description>Indie dev stories, tutorials, and tool reviews</description>')
    lines.append('<language>en</language>')
    lines.append('<atom:link href="https://just4.tech/rss.xml" rel="self" type="application/rss+xml"/>')
    for p in posts:
        raw = p["created_at"] or ""
        if raw:
            try:
                from datetime import datetime
                dt = datetime.strptime(raw[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                pd = format_datetime(dt, usegmt=True)
            except:
                pd = raw[:19]
        else:
            pd = str(date.today())
        lines.append(f"<item><title>{p['title']}</title>")
        lines.append(f"<link>https://just4.tech/blog/{p['slug']}</link>")
        lines.append(f"<guid>https://just4.tech/blog/{p['slug']}</guid>")
        lines.append(f"<description>{(p['excerpt'] or '')[:500]}</description>")
        lines.append(f"<pubDate>{pd}</pubDate>")
        lines.append(f"<category>{p['category'] or ''}</category></item>")
    lines.append('</channel></rss>')
    return Response(content="\n".join(lines), media_type="application/rss+xml")

# ===================== MEDIA LIBRARY =====================

@app.get("/api/admin/media")
async def api_list_media(request: Request):
    user = check_session(request)
    if not user:
        raise HTTPException(401)
    import os as _os, glob as _glob
    upload_dir = _os.path.join(_os.path.dirname(__file__), "static", "uploads")
    _os.makedirs(upload_dir, exist_ok=True)
    files = []
    for fpath in sorted(_glob.glob(_os.path.join(upload_dir, "*")), key=lambda x: _os.path.getmtime(x), reverse=True):
        fname = _os.path.basename(fpath)
        if fname == ".gitkeep":
            continue
        size = _os.path.getsize(fpath)
        mtime = _os.path.getmtime(fpath)
        from datetime import datetime
        files.append({
            "filename": fname,
            "url": "/uploads/" + fname,
            "size": size,
            "size_display": f"{size/1024:.1f} KB" if size < 1024*1024 else f"{size/1024/1024:.1f} MB",
            "updated_at": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"),
        })
    return {"files": files}

@app.delete("/api/admin/media/{filename:path}")
async def api_delete_media(filename: str, request: Request):
    user = check_session(request)
    if not user:
        raise HTTPException(401)
    import os as _os
    upload_dir = _os.path.join(_os.path.dirname(__file__), "static", "uploads")
    upload_dir2 = "/var/www/aitoolhub/spa/uploads"
    for d in [upload_dir, upload_dir2]:
        fpath = _os.path.join(d, filename)
        if _os.path.exists(fpath):
            _os.remove(fpath)
    return {"ok": True}

@app.get("/sitemap.xml", response_class=Response)
@cached("sitemap", ttl_seconds=900)
async def sitemap():
    conn = get_db()
    posts = conn.execute("SELECT slug, updated_at FROM posts WHERE status='active' AND category NOT IN ('AI Tool','Project','Indie Dev') ORDER BY updated_at DESC").fetchall()
    software = conn.execute("SELECT slug, updated_at FROM posts WHERE status='active' AND category='AI Tool' ORDER BY updated_at DESC").fetchall()
    projects = conn.execute("SELECT slug, updated_at FROM posts WHERE status='active' AND category='Project' ORDER BY updated_at DESC").fetchall()
    indie_devs = conn.execute("SELECT slug, updated_at FROM posts WHERE status='active' AND category='Indie Dev' ORDER BY updated_at DESC").fetchall()
    sites_posts = conn.execute("SELECT slug, updated_at FROM posts WHERE status='active' AND category='Site' ORDER BY updated_at DESC").fetchall()
    conn.close()

    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']

    static_pages = [
        ("/", "1.0"), ("/blog", "0.8"), ("/aitools", "0.7"),
        ("/about", "0.6"), ("/contact", "0.5"),
        ("/privacy", "0.3"), ("/terms", "0.3"), ("/projects", "0.7"), ("/indie-devs", "0.6"), ("/tutorials", "0.7"), ("/sites", "0.6"),
    ]
    for page, priority in static_pages:
        lines.append(f"  <url><loc>https://just4.tech{page}</loc><priority>{priority}</priority></url>")

    for p in posts:
        updated = (p["updated_at"] or "")[:10] or date.today().isoformat()
        lines.append(f"  <url><loc>https://just4.tech/blog/{p['slug']}</loc><lastmod>{updated}</lastmod><priority>0.7</priority></url>")

    for s in software:
        updated = (s["updated_at"] or "")[:10] or date.today().isoformat()
        lines.append(f"  <url><loc>https://just4.tech/aitools/{s['slug']}</loc><lastmod>{updated}</lastmod><priority>0.6</priority></url>")

    for p in projects:
        updated = (p["updated_at"] or "")[:10] or date.today().isoformat()
        lines.append(f"  <url><loc>https://just4.tech/projects/{p['slug']}</loc><lastmod>{updated}</lastmod><priority>0.6</priority></url>")

    for d in indie_devs:
        updated = (d["updated_at"] or "")[:10] or date.today().isoformat()
        lines.append(f"  <url><loc>https://just4.tech/blog/{d['slug']}</loc><lastmod>{updated}</lastmod><priority>0.5</priority></url>")

    for s in sites_posts:
        updated = (s["updated_at"] or "")[:10] or date.today().isoformat()
        lines.append(f"  <url><loc>https://just4.tech/sites/{s['slug']}</loc><lastmod>{updated}</lastmod><priority>0.6</priority></url>")

    lines.append("</urlset>")
    return "\n".join(lines)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8083)
