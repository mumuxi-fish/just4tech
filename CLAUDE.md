# CLAUDE.md — Just4Tech Development & Deployment Guide

## Project

**just4.tech** — full-stack indie dev blog & AI tool directory.
- Repo: `https://github.com/mumuxi-fish/just4tech`
- Live: `https://just4.tech`
- CI: GitHub Actions → push `main` → auto-deploy

## Architecture

```
just4tech/
├── frontend/              Vue 3 SPA (Vite 8, Tailwind CSS 4, Vue Router)
│   ├── src/views/          Page components + admin/
│   ├── src/components/     Navbar, Footer, IconDisplay, BackToTop
│   ├── src/api/            API client helpers
│   ├── src/utils/          sound.js, meta.js
│   └── vite.config.js
├── backend/               Python FastAPI (port 8083, SQLite) — MODULAR
│   ├── main.py             App creation + startup (~90 lines, was ~1157)
│   ├── config.py           All settings, no hardcoded paths
│   ├── auth.py             API key, sessions, password hashing, rate limiting
│   ├── cache.py            In-memory TTL cache
│   ├── database.py         SQLite connection + schema
│   ├── middleware.py        Page view tracking middleware
│   ├── dependencies.py     FastAPI dependency injection
│   ├── routes/             Route modules (10 files)
│   │   ├── posts.py         Posts CRUD (8 routes)
│   │   ├── admin.py         Login, dashboard, analytics (9 routes)
│   │   ├── pages.py         Static pages (6 routes)
│   │   ├── media.py         Upload/list/delete (3 routes)
│   │   ├── contact.py       Contact form (3 routes)
│   │   ├── software.py      AI tools (3 routes)
│   │   ├── projects.py      Projects (2 routes)
│   │   ├── content.py       Content blocks (5 routes)
│   │   ├── icon_proxy.py    Icon proxy + prewarm (1 route)
│   │   └── sitemap.py       RSS + Sitemap (2 routes)
│   ├── tests/              pytest test suite (40+ tests)
│   │   ├── conftest.py      Fixtures (in-memory DB, TestClient)
│   │   ├── test_auth.py     Auth: passwords, sessions, rate limits, endpoints
│   │   ├── test_posts.py    Posts CRUD, pagination, permissions
│   │   └── test_routes.py   Icon proxy, RSS, sitemap, contact, projects
│   └── requirements.txt
├── Dockerfile             Multi-stage: Node build + Python runtime
├── docker-compose.yml     Local dev with persistent volumes
└── .github/workflows/
    └── deploy.yml         CI/CD pipeline
```

## Local Development

```bash
# Frontend (dev server with HMR, proxies /api to production)
cd frontend
npm ci
npm run dev              # → http://localhost:5173

# Backend
cd backend
pip install -r requirements.txt
API_KEY=*** DEV_MODE=1 python3 main.py   # DEV_MODE=1 disables secure cookies

# Docker
docker compose up --build

# Run tests
cd backend
python3 -m pytest tests/ -v
```

## Build

```bash
cd frontend
npm run build            # → frontend/dist/
```

## Server Layout

| Path | Purpose |
|------|---------|
| `/var/www/aitoolhub/spa/` | SPA static files (Nginx root) |
| `/home/ubuntu/aitoolhub-admin/` | Backend Python files |
| `/home/ubuntu/aitoolhub-admin/data/` | SQLite database (excluded from rsync) |
| `/home/ubuntu/aitoolhub-admin/static/uploads/` | User-uploaded media (excluded from rsync) |
| `/etc/aitoolhub/api_key` | API secret key (auto-generated on first deploy) |
| `/etc/aitoolhub/api_key_env` | systemd EnvironmentFile (API_KEY=...) |
| `/etc/systemd/system/aitoolhub-admin.service.d/override.conf` | systemd drop-in |

## Deployment Pipeline

Push to `main` triggers `.github/workflows/deploy.yml`:

1. **Build frontend** — `npm ci && npm run build`
2. **Deploy frontend** — `rsync dist/ → /var/www/aitoolhub/spa/` (excludes `/uploads/`, `/sitemap.xml`)
3. **Deploy backend** — `rsync backend/ → /home/ubuntu/aitoolhub-admin/` (excludes `__pycache__/`, `data/`, `static/uploads/`)
4. **Install deps** — `sudo pip install -r requirements.txt` (system-wide for systemd)
5. **Ensure API_KEY** — first deploy generates random key at `/etc/aitoolhub/api_key`, creates systemd EnvironmentFile, runs `daemon-reload`
6. **Restart** — `systemctl restart aitoolhub-admin` → health-check `curl http://127.0.0.1:8083/api/posts`

### Required GitHub Secrets

| Secret | Description |
|--------|-------------|
| `SSH_PRIVATE_KEY` | SSH key for deploy user |
| `DEPLOY_HOST` | Server IP/hostname |
| `DEPLOY_USER` | Server user (`ubuntu`) |

## API Reference

Base: `https://just4.tech`

### Public Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/posts` | Blog posts (paginated: `?page=N&limit=M`, filter: `?status=active`) |
| GET | `/api/posts/{id}` | Post by ID |
| GET | `/api/posts/slug/{slug}` | Post by slug |
| GET | `/api/software` | AI Tools (posts with `category='AI Tool'`) |
| GET | `/api/software/slug/{slug}` | Tool by slug |
| GET | `/api/projects` | Projects (posts with `category='Project'`) |
| GET | `/api/projects/{id}` | Project by ID |
| GET | `/api/page/{slug}` | Public page content |
| GET | `/rss.xml` | RSS feed (cached 10 min) |
| GET | `/sitemap.xml` | Sitemap (cached 15 min) |
| POST | `/api/contact` | Submit contact form |

### Admin Endpoints (Session Cookie)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/admin/login` | Login (rate-limited: 5 req/60s/IP) |
| POST | `/api/admin/logout` | Logout |
| GET | `/api/admin/session-status` | Check session validity |
| POST | `/api/posts` | Create post |
| PUT | `/api/posts/{id}` | Update post |
| DELETE | `/api/posts/{id}` | Delete post |
| PUT | `/api/posts/slug/{slug}` | Update post by slug |
| DELETE | `/api/posts/slug/{slug}` | Delete post by slug |
| POST | `/api/admin/upload` | Upload media (max 5MB, png/jpg/webp/gif/svg) |
| GET | `/api/admin/media` | List uploaded files |
| DELETE | `/api/admin/media/{filename}` | Delete media |
| GET | `/api/admin/analytics` | Dashboard stats |
| GET | `/api/admin/contact-messages` | Contact form submissions |
| PUT | `/api/pages/{page_id}` | Update static page |

### Authentication
- **Admin**: session cookie (`httponly`, `secure` in prod, `samesite=lax`, 7-day TTL)
- **API**: `X-API-Key` header with the value stored in `/etc/aitoolhub/api_key`
- **Rate limiting**: login endpoint limited to 5 requests per 60 seconds per IP

## Verification Checklist

After deployment, verify:

```bash
# 1. Service is running
ssh ubuntu@<host> "systemctl status aitoolhub-admin"

# 2. API health check
curl -s -o /dev/null -w '%{http_code}' https://just4.tech/api/posts
# Expected: 200

# 3. Check API key is set
ssh ubuntu@<host> "sudo cat /etc/aitoolhub/api_key"

# 4. Frontend is live
curl -s -o /dev/null -w '%{http_code}' https://just4.tech/
# Expected: 200

# 5. RSS feed
curl -s -o /dev/null -w '%{http_code}' https://just4.tech/rss.xml
# Expected: 200

# 6. Sitemap
curl -s -o /dev/null -w '%{http_code}' https://just4.tech/sitemap.xml
# Expected: 200

# 7. View recent logs
ssh ubuntu@<host> "sudo journalctl -u aitoolhub-admin --no-pager -n 30"

# 8. Admin login works
curl -s -X POST https://just4.tech/api/admin/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"<user>","password":"<pass>"}'
# Expected: {"ok":true}
```

## Troubleshooting

### Service fails to start
```bash
ssh ubuntu@<host> "sudo journalctl -u aitoolhub-admin --no-pager -n 50"
```
Common causes:
- `NameError` / `ImportError` → syntax error in `main.py` → fix and re-deploy
- `RuntimeError: API_KEY environment variable is required` → API key not set → re-run "Ensure API_KEY" step
- `ModuleNotFoundError: bcrypt` → pip install not run as root → `sudo pip install bcrypt`

### Frontend blank page
- Check `frontend/dist/index.html` exists on server
- Check Nginx config points to `/var/www/aitoolhub/spa/`
- Browser console for JS errors

### API returns 401
- Session expired → re-login at `/admin/login`
- API key mismatch → check `/etc/aitoolhub/api_key`

### Cache issues after deploy
- RSS/Sitemap caches auto-invalidate when posts are created/updated/deleted
- To force refresh: restart the backend service

## Database

SQLite at `backend/data/aitoolhub.db` (WAL mode enabled).

Tables:
- `posts` — all content (blog, AI tools, projects, indie devs, sites) differentiated by `category`
- `users` — admin accounts (bcrypt password hashing)
- `site_pages` — static page content
- `content_blocks` — editable page sections
- `page_views` — view counter (path + date)
- `contact_messages` — contact form submissions
- `ai_config` — AI-related settings (key-value)
- `tools` / `software` — **deprecated**, content now in `posts` table

## Security Notes

- API key is **auto-generated** on first deploy (stored at `/etc/aitoolhub/api_key`, chmod 600)
- Passwords hashed with **bcrypt** (backward-compatible with legacy SHA256+salt and unsalted SHA256)
- Session cookies: `httponly`, `secure` (prod only), `samesite=lax`, 7-day TTL with **automatic cleanup**
- CORS restricted to `just4.tech`, `www.just4.tech`, and `localhost`
- Login rate-limited: **5 attempts per 60 seconds** per IP
- Admin username is **NOT stored in localStorage** (fetched from session API)
- Uploads validated: max 5MB, whitelisted extensions only
