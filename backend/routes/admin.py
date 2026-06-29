"""Admin routes: login, logout, dashboard, analytics, settings."""

import logging
from datetime import date

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from database import get_db
from auth import (
    check_session, create_session, destroy_session,
    update_session_username, verify_password, hash_password,
    check_rate_limit,
)
from config import DEV_MODE

logger = logging.getLogger("just4tech.routes.admin")
router = APIRouter(tags=["admin"])


# ── Login / Logout ─────────────────────────────────────────────

@router.post("/api/admin/login")
async def admin_login(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(f"login:{client_ip}"):
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")

    data = await request.json()
    username = data.get("username")
    password = data.get("password")

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()

    if user and verify_password(password, user["password_hash"]):
        token, _ = create_session(username)
        resp = JSONResponse({"ok": True})
        resp.set_cookie(
            key="session", value=token,
            httponly=True, secure=not DEV_MODE, samesite="lax",
            max_age=86400 * 7, path="/",
        )
        logger.info("Admin login: %s from %s", username, client_ip)
        return resp

    logger.warning("Failed login attempt for %s from %s", username, client_ip)
    return JSONResponse({"ok": False, "error": "Invalid username or password"}, status_code=401)


@router.post("/api/admin/logout")
async def admin_logout(request: Request):
    """Log out: destroy server-side session."""
    token = request.cookies.get("session", "")
    if token:
        destroy_session(token)
        logger.info("Admin logout: token=%s...", token[:8])
    return JSONResponse({"ok": True})


# ── Session status ─────────────────────────────────────────────

@router.get("/api/admin/session-status")
async def session_status(request: Request):
    user = check_session(request)
    return {"authenticated": user is not None, "user": user}


# ── Change username / password ────────────────────────────────

@router.post("/api/admin/change-username")
async def change_username(request: Request):
    user = check_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
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

    existing = conn.execute("SELECT id FROM users WHERE username = ?", (new_username,)).fetchone()
    if existing:
        conn.close()
        return JSONResponse({"ok": False, "error": "Username already taken"})

    conn.execute("UPDATE users SET username = ? WHERE username = ?", (new_username, user))
    conn.commit()
    conn.close()

    token = request.cookies.get("session", "")
    update_session_username(token, new_username)
    logger.info("Username changed: %s → %s", user, new_username)
    return JSONResponse({"ok": True, "username": new_username})


@router.post("/api/admin/change-password")
async def change_password(request: Request):
    user = check_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
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

    conn.execute("UPDATE users SET password_hash = ? WHERE username = ?",
                 (hash_password(new_pw), user))
    conn.commit()
    conn.close()
    logger.info("Password changed for user: %s", user)
    return JSONResponse({"ok": True})


# ── Dashboard / Analytics ──────────────────────────────────────

@router.get("/api/admin/analytics")
async def analytics(request: Request):
    user = check_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    conn = get_db()
    total_views = conn.execute(
        "SELECT COALESCE(SUM(count), 0) as c FROM page_views"
    ).fetchone()["c"]
    today_views = conn.execute(
        "SELECT COALESCE(SUM(count), 0) as c FROM page_views WHERE date = date('now')"
    ).fetchone()["c"]
    total_posts = conn.execute("SELECT COUNT(*) as c FROM posts").fetchone()["c"]
    total_software = conn.execute(
        "SELECT COUNT(*) as c FROM posts WHERE category='AI Tool'"
    ).fetchone()["c"]
    total_projects = conn.execute(
        "SELECT COUNT(*) as c FROM posts WHERE category='Project'"
    ).fetchone()["c"]
    contact_count = conn.execute("SELECT COUNT(*) as c FROM contact_messages").fetchone()["c"]

    daily_views = conn.execute(
        "SELECT date, SUM(count) as cnt FROM page_views "
        "GROUP BY date ORDER BY date DESC LIMIT 30"
    ).fetchall()

    top_pages = conn.execute(
        "SELECT path, SUM(count) as cnt FROM page_views "
        "GROUP BY path ORDER BY cnt DESC LIMIT 10"
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
        "top_pages": [{"path": r["path"], "count": r["cnt"]} for r in top_pages],
    }


@router.get("/api/stats/overview")
async def stats_overview(request: Request):
    user = check_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    conn = get_db()
    total_views = conn.execute("SELECT SUM(count) as c FROM page_views").fetchone()["c"] or 0
    today_views = conn.execute(
        "SELECT SUM(count) as c FROM page_views WHERE date = ?",
        (date.today().isoformat(),),
    ).fetchone()["c"] or 0
    top_pages = conn.execute(
        "SELECT path, SUM(count) as cnt FROM page_views "
        "GROUP BY path ORDER BY cnt DESC LIMIT 10"
    ).fetchall()
    daily_views = conn.execute(
        "SELECT date, SUM(count) as cnt FROM page_views "
        "GROUP BY date ORDER BY date LIMIT 30"
    ).fetchall()
    conn.close()
    return {
        "total_views": total_views,
        "today_views": today_views,
        "top_pages": [dict(p) for p in top_pages],
        "daily_views": [dict(d) for d in daily_views],
    }


# ── AI Settings ────────────────────────────────────────────────

@router.get("/api/admin/ai-settings")
async def get_ai_settings(request: Request):
    user = check_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    conn = get_db()
    settings = conn.execute("SELECT * FROM ai_config").fetchall()
    conn.close()
    return {s["key"]: s["value"] for s in settings}


@router.post("/api/admin/ai-settings")
async def save_ai_settings(request: Request):
    user = check_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    data = await request.json()
    conn = get_db()
    for key, value in data.items():
        conn.execute(
            "INSERT OR REPLACE INTO ai_config (key, value, updated_at) "
            "VALUES (?, ?, CURRENT_TIMESTAMP)",
            (key, str(value)),
        )
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Diagnostic: migration status (public, no auth) ────────────

@router.get("/api/admin/migration-status")
async def migration_status():
    """Public diagnostic endpoint — shows which migrations have run."""
    from migrations import get_migration_status
    return get_migration_status()


@router.post("/api/admin/migration-rerun")
async def migration_rerun(request: Request):
    """Force re-run a migration. Requires API key or admin session."""
    from auth import check_session, require_api_key
    if not check_session(request) and not require_api_key(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    data = await request.json()
    name = data.get("name", "")
    from migrations import run_migrations
    from database import get_db
    conn = get_db()
    # Reset the migration flag so it runs again
    conn.execute("DELETE FROM ai_config WHERE key = ?", (f"migration:{name}",))
    conn.commit()
    conn.close()
    run_migrations()
    from migrations import get_migration_status
    return get_migration_status()
