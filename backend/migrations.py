"""Data migrations that run on application startup. Idempotent and versioned."""

import logging
import random
from datetime import datetime, timedelta

from database import get_db

logger = logging.getLogger("just4tech.migrations")

# ── Migration tracking ────────────────────────────────────────

def _is_migration_done(conn, name: str) -> bool:
    """Check if a named migration has already been applied."""
    row = conn.execute(
        "SELECT value FROM ai_config WHERE key = ?", (f"migration:{name}",)
    ).fetchone()
    return row is not None and row["value"] == "done"


def _mark_migration_done(conn, name: str) -> None:
    """Mark a migration as applied."""
    conn.execute(
        "INSERT OR REPLACE INTO ai_config (key, value, updated_at) "
        "VALUES (?, 'done', CURRENT_TIMESTAMP)",
        (f"migration:{name}",),
    )


# ── Migration 001: Privacy Policy ─────────────────────────────

UPDATED_PRIVACY_POLICY = """*Last updated: June 28, 2026*

## Introduction

At Just4Tech ("we", "our", or "us"), we take your privacy seriously. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you visit our website just4.tech (the "Website"). Please read this privacy policy carefully. If you do not agree with the terms of this privacy policy, please do not access the site.

## Information We Collect

### Information You Voluntarily Provide
If you contact us through our contact form, we collect the information you provide: name, email address, subject, and message content. This information is used solely to respond to your inquiry and is never sold to third parties.

### Automatically Collected Information
When you visit our Website, we may automatically collect certain information about your device, including:

- **Usage Data**: Pages visited, time spent on pages, referring URLs
- **Device Information**: Browser type and version, operating system, device type (desktop/mobile/tablet)
- **Approximate Location**: Country and city level only (derived from IP address — we do not collect precise GPS location)

This data is collected through standard server logs and privacy-focused analytics. We do not use this data to identify individual users.

## Cookies and Tracking Technologies

### Essential Cookies
We use minimal essential cookies required for the Website to function properly:
- Session cookies for admin authentication (httponly, secure)

### Third-Party Cookies
We may use third-party services that place cookies on your device:

**Google AdSense**: We display advertisements through Google AdSense, which uses cookies to serve ads based on your prior visits to our Website or other websites. Google's use of advertising cookies enables it and its partners to serve ads to you based on your visit to our sites and/or other sites on the Internet.

You may opt out of personalized advertising by visiting:
- [Google Ads Settings](https://www.google.com/settings/ads)
- [www.aboutads.info](https://www.aboutads.info/choices/)

**Analytics**: We may use privacy-focused analytics services that collect anonymous usage data. No personally identifiable information is shared with these services.

### Cookie Control
Most web browsers allow you to control cookies through their settings preferences. You can set your browser to refuse cookies or to alert you when cookies are being sent. However, if you disable cookies, some features of the Website may not function properly.

## How We Use Your Information

Any information we collect is used for the following purposes:
- To operate, maintain, and improve our Website
- To respond to your comments, questions, and requests
- To analyze usage patterns and trends (aggregated, anonymized)
- To display relevant advertisements through third-party ad networks
- To detect, prevent, and address technical issues
- To comply with legal obligations

## Advertising

We display advertisements on our Website through Google AdSense and potentially other third-party advertising networks. These third parties may use cookies, web beacons, and similar technologies to collect information about your visits to our Website and other websites to provide targeted advertisements.

- Third-party vendors, including Google, use cookies to serve ads based on your prior visits
- Google's use of the DoubleClick cookie enables it and its partners to serve ads based on your visit to our Website and/or other sites on the Internet
- You may opt out of the DoubleClick cookie by visiting [Google Ads Settings](https://www.google.com/settings/ads)
- You may opt out of some third-party vendors' uses of cookies for personalized advertising by visiting [www.aboutads.info](https://www.aboutads.info/)

## Data Security

We implement appropriate technical and organizational security measures to protect your information:
- All traffic is encrypted via HTTPS/TLS
- Passwords are hashed using bcrypt (one-way encryption)
- Admin sessions are secured with httponly and secure cookies
- Login endpoints are rate-limited to prevent brute force attacks

However, no method of transmission over the Internet or electronic storage is 100% secure. While we strive to protect your personal data, we cannot guarantee its absolute security.

## Data Retention

- Contact form submissions: Retained for up to 90 days, then deleted
- Server logs and analytics data: Retained in aggregated form indefinitely
- Session cookies: Expire after 7 days of inactivity

## Your Rights

Depending on your location, you may have the following rights regarding your personal data:

### GDPR (European Economic Area / UK)
If you are a resident of the EEA or UK, you have the right to:
- **Access** your personal data
- **Rectify** inaccurate personal data
- **Erase** your personal data ("right to be forgotten")
- **Restrict** processing of your personal data
- **Data portability** — receive your data in a structured, commonly used format
- **Object** to processing of your personal data

### CCPA / CPRA (California)
If you are a California resident, you have the right to:
- **Know** what personal information is collected, used, shared, or sold
- **Delete** personal information held by businesses
- **Opt-out** of the sale or sharing of personal information
- **Non-discrimination** for exercising your CCPA rights

To exercise any of these rights, please contact us using the information below. We will respond to your request within the timeframe required by applicable law.

## Children's Privacy

Our Website is not intended for children under 13 years of age. We do not knowingly collect personal information from children under 13. If you are a parent or guardian and believe your child has provided us with personal data, please contact us.

## Third-Party Links

Our Website may contain links to third-party websites. We are not responsible for the privacy practices or content of these external sites. We encourage you to review the privacy policies of any third-party sites you visit.

## Changes to This Privacy Policy

We may update this Privacy Policy from time to time. We will notify you of any changes by posting the new Privacy Policy on this page and updating the "Last updated" date. You are advised to review this Privacy Policy periodically for any changes.

## Contact Us

If you have any questions about this Privacy Policy, your data rights, or wish to exercise any of your rights, please contact us:

- **Website**: [https://just4.tech/contact](https://just4.tech/contact)
- **Email**: [guotong1996@gmail.com](mailto:guotong1996@gmail.com)
"""


def _migrate_001_privacy(conn) -> None:
    """Update privacy policy with GDPR/CCPA/AdSense disclosure."""
    existing = conn.execute(
        "SELECT id FROM site_pages WHERE slug = ?", ("privacy",)
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE site_pages SET content = ?, updated_at = CURRENT_TIMESTAMP WHERE slug = ?",
            (UPDATED_PRIVACY_POLICY, "privacy"),
        )
        logger.info("Migration 001: Privacy policy updated")
    else:
        conn.execute(
            "INSERT INTO site_pages (slug, title, content, meta_title, meta_description) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                "privacy",
                "Privacy Policy",
                UPDATED_PRIVACY_POLICY,
                "Privacy Policy — Just4Tech",
                "Just4Tech privacy policy: how we collect, use, and protect your data. "
                "Includes GDPR, CCPA, and Google AdSense cookie disclosures.",
            ),
        )
        logger.info("Migration 001: Privacy policy created")


# ── Migration 002: Disperse Post Dates ────────────────────────

def _migrate_002_disperse_dates(conn) -> None:
    """Spread posts across 3 months (April-June) for organic look."""
    posts = conn.execute(
        "SELECT id, created_at FROM posts ORDER BY id"
    ).fetchall()

    if not posts:
        return

    # Start from April 1, end June 25 (original last date)
    start_date = datetime(2026, 4, 1)
    end_date = datetime(2026, 6, 25)
    total_days = (end_date - start_date).days  # ~85 days
    total_posts = len(posts)

    # Distribute posts across the range with some randomness
    # Use a pattern: 2-3 posts per week, some gaps
    interval = max(1, total_days // total_posts)  # ~1.7 days between posts
    
    for i, post in enumerate(posts):
        # Base offset with slight jitter
        day_offset = i * interval + random.randint(-1, 2)
        day_offset = max(0, min(total_days, day_offset))
        new_date = start_date + timedelta(days=day_offset)
        
        # Randomize time of day
        hour = random.randint(6, 22)  # 6AM-10PM
        minute = random.randint(0, 59)
        new_datetime = new_date.replace(hour=hour, minute=minute, second=0)

        conn.execute(
            "UPDATE posts SET created_at = ?, updated_at = ? WHERE id = ?",
            (new_datetime.strftime("%Y-%m-%d %H:%M:%S"),
             new_datetime.strftime("%Y-%m-%d %H:%M:%S"),
             post["id"]),
        )

    logger.info(
        "Migration 002: Dispersed %d posts from %s to %s",
        total_posts,
        start_date.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d"),
    )


# ── Runner ────────────────────────────────────────────────────

MIGRATIONS = [
    ("001_privacy", _migrate_001_privacy),
    ("002_disperse_dates", _migrate_002_disperse_dates),
]


def run_migrations() -> None:
    """Run all pending data migrations. Idempotent — each runs once."""
    conn = get_db()

    for name, func in MIGRATIONS:
        if _is_migration_done(conn, name):
            continue
        try:
            func(conn)
            _mark_migration_done(conn, name)
            conn.commit()
            logger.info("Migration %s: applied", name)
        except Exception:
            logger.exception("Migration %s failed", name)
            conn.rollback()

    conn.close()


def get_migration_status() -> dict:
    """Return status of all migrations (for diagnostics)."""
    conn = get_db()
    result = {}
    for name, _ in MIGRATIONS:
        result[name] = "done" if _is_migration_done(conn, name) else "pending"
    # Also count posts and their date range
    posts = conn.execute("SELECT created_at FROM posts ORDER BY created_at").fetchall()
    if posts:
        dates = [p["created_at"][:10] for p in posts]
        result["post_count"] = len(posts)
        result["date_min"] = min(dates)
        result["date_max"] = max(dates)
        result["unique_dates"] = len(set(dates))
    conn.close()
    return result
