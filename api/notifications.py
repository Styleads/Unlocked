"""
api/notifications.py — Resend Email Delivery, Content Rendering, and Notification Scheduler.

Enforces:
- Consent check: Emails are dispatched ONLY if explicit user opt-in is active.
- Sensitive data minimization: No Aadhaar numbers, OTPs, full income numbers, caste details,
  or document scans in email bodies.
- Demo mode protection: Simulated time emails route to DEMO_EMAIL_TO and carry [DEMO] labeling.
- Idempotency: Unique idempotency keys to avoid duplicate sends across retries/scheduler ticks.
- State integrity: Provider API acceptance is recorded as 'accepted', never falsely marked 'delivered'.
"""
from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Protocol

import resend

from api.clock import is_demo_mode, now_utc
from api.database import (
    claim_due_notifications,
    get_notification_preferences,
    update_notification_status,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Email Provider Interface & Resend Implementation
# ---------------------------------------------------------------------------

class EmailProvider(Protocol):
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: str,
        idempotency_key: Optional[str] = None,
        is_demo: bool = False,
    ) -> dict[str, Any]:
        """Send an email and return provider metadata including message ID."""
        ...


class ResendEmailProvider:
    """Official Resend SDK provider with demo recipient override and idempotency."""

    def __init__(self, api_key: Optional[str] = None, from_email: Optional[str] = None):
        self.api_key = api_key if api_key is not None else os.getenv("RESEND_API_KEY", "")
        self.from_email = from_email or os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: str,
        idempotency_key: Optional[str] = None,
        is_demo: bool = False,
    ) -> dict[str, Any]:
        recipient = to_email.strip()

        # If in demo mode or demo notification, override to DEMO_EMAIL_TO if set
        demo_active = is_demo or is_demo_mode()
        if demo_active:
            demo_to = os.getenv("DEMO_EMAIL_TO", "").strip()
            if demo_to:
                recipient = demo_to
            if not subject.startswith("[DEMO]"):
                subject = f"[DEMO] {subject}"
            body_text = f"[DEMO SIMULATION]\nThis email was triggered in demo mode with simulated time.\n\n" + body_text
            body_html = f"<div style='background:#fef3c7;border:1px solid #f59e0b;padding:8px;margin-bottom:12px;font-family:sans-serif;color:#92400e;border-radius:4px;'><strong>[DEMO SIMULATION]</strong> This notification was triggered in demo mode using simulated time.</div>" + body_html

        if not self.api_key:
            raise ValueError("RESEND_API_KEY is not configured in environment.")

        resend.api_key = self.api_key

        params: dict[str, Any] = {
            "from": self.from_email,
            "to": [recipient],
            "subject": subject,
            "html": body_html,
            "text": body_text,
        }
        if idempotency_key:
            params["headers"] = {"Idempotency-Key": idempotency_key}

        # Dispatch using resend SDK async method
        if hasattr(resend.Emails, "send_async"):
            result = await resend.Emails.send_async(params)
        else:
            result = resend.Emails.send(params)

        message_id = ""
        if isinstance(result, dict):
            message_id = result.get("id") or ""
        elif hasattr(result, "id"):
            message_id = getattr(result, "id", "") or ""

        return {
            "id": message_id,
            "recipient": recipient,
            "subject": subject,
            "status": "accepted",
        }


# Global/injectable provider reference for testing
_active_email_provider: Optional[EmailProvider] = None


def get_email_provider() -> EmailProvider:
    global _active_email_provider
    if _active_email_provider is None:
        _active_email_provider = ResendEmailProvider()
    return _active_email_provider


def set_email_provider(provider: Optional[EmailProvider]) -> None:
    """Override email provider, primarily for unit testing without live network calls."""
    global _active_email_provider
    _active_email_provider = provider


def sanitize_error(error_msg: str) -> str:
    """Sanitize error messages to avoid leaking API keys or tokens in logs/database."""
    # Mask any potential API key patterns (re_..., Bearer ..., 30+ char hex/base64)
    sanitized = re.sub(r"(re_[a-zA-Z0-9_-]{20,})", "[REDACTED_API_KEY]", error_msg)
    sanitized = re.sub(r"(Bearer\s+)[a-zA-Z0-9_\-\.]{15,}", r"\1[REDACTED]", sanitized)
    return sanitized[:500]


# ---------------------------------------------------------------------------
# Notification Content Builders
# ---------------------------------------------------------------------------

def render_simulated_appointment_email(
    scheme_name: str,
    scheduled_at_str: str,
    location: Optional[str] = None,
    office_name: Optional[str] = None,
    documents: Optional[list[str]] = None,
) -> tuple[str, str, str]:
    """Render simulated appointment confirmation email watermarked as simulation. `documents` comes from the scheme's own
    checklist; with none, the email lists none rather than a fixed set that may not apply."""
    subject = f"[SIMULATED DEMO] Appointment Confirmed for {scheme_name}"
    loc_str = f"Location: {location}\n" if location else ""
    office_str = f"Office: {office_name}\n" if office_name else ""
    docs = [d for d in (documents or []) if d]
    checklist_text = ("Preparation Checklist:\n" + "\n".join(f"- {d}" for d in docs) + "\n") if docs else ""
    checklist_html = ("<h3 style=\"color: #1f2937; margin-top: 20px;\">Preparation Checklist:</h3><ul>" + "".join(f"<li>{d}</li>" for d in docs) + "</ul>") if docs else ""

    text_body = f"""Hello,

[SIMULATION DEMO NOTICE]
This notification confirms an appointment simulated through Project Unlocked's in-website demonstration.
No real government office was contacted and no actual booking was made.

Simulated Appointment Details:
Scheme: {scheme_name}
{office_str}Scheduled Date & Time: {scheduled_at_str}
{loc_str}
{checklist_text}
Thank you for exploring Project Unlocked.
"""

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: sans-serif; line-height: 1.5; color: #1f2937; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background-color: #fef3c7; border: 1px solid #f59e0b; padding: 12px; border-radius: 6px; margin-bottom: 20px;">
            <strong style="color: #92400e;">[SIMULATION DEMO ONLY]</strong>
            <p style="margin: 4px 0 0 0; color: #92400e; font-size: 13px;">This notification was generated from an in-website appointment enquiry simulation. No actual government office was contacted.</p>
        </div>
        <h2 style="color: #059669;">Simulated Appointment Confirmed</h2>
        <p>Your simulated appointment for <strong>{scheme_name}</strong> has been confirmed in the demonstration environment.</p>
        <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
            <tr><td style="padding: 8px 0; color: #6b7280;">Office:</td><td><strong>{office_name or 'the (simulated) office desk'}</strong></td></tr>
            <tr><td style="padding: 8px 0; color: #6b7280;">Scheduled Slot:</td><td><strong>{scheduled_at_str}</strong></td></tr>
            <tr><td style="padding: 8px 0; color: #6b7280;">Location:</td><td>{location or 'Designated office verification counter'}</td></tr>
        </table>
        {checklist_html}
        <p style="font-size: 12px; color: #6b7280; margin-top: 24px;">Project Unlocked — Transparent Citizen Follow-Through</p>
    </body>
    </html>
    """
    return subject, text_body, html_body


def render_action_plan_email(
    schemes: list[dict[str, Any]],
    checklist_items: list[dict[str, Any]],
    follow_up_url: Optional[str] = None,
) -> tuple[str, str, str]:
    """
    Render Action Plan Summary email.
    Subject: Your Unlocked Action Plan & Recommended Benefits
    Excludes sensitive profile info (income, caste, Aadhaar).
    """
    subject = "Your Unlocked Action Plan & Recommended Welfare Schemes"

    scheme_names = [s.get("name", "Welfare Scheme") for s in schemes[:5]]
    schemes_text = "\n".join([f"  • {name}" for name in scheme_names]) or "  • Relevant government schemes identified for you."

    tasks_text = ""
    if checklist_items:
        tasks_text = "\nImmediate Next Document Tasks:\n" + "\n".join(
            [f"  [{i+1}] {item.get('name', 'Required Document')}" for i, item in enumerate(checklist_items[:5])]
        )

    link_text = f"\nAccess your secure session and tracker:\n{follow_up_url}\n" if follow_up_url else ""

    text_body = f"""Hello,

Thank you for exploring government benefit schemes on Unlocked.
Here is your personalized summary and action plan:

Potential Schemes Matched:
{schemes_text}
{tasks_text}
{link_text}
Reminder: Unlocked will never ask for your passwords, OTPs, or bank details.
You can disable email updates anytime from your session dashboard.

Warm regards,
Project Unlocked — Karnataka Benefits Discovery
"""

    schemes_html = "".join([f"<li><strong>{name}</strong></li>" for name in scheme_names])
    tasks_html = ""
    if checklist_items:
        tasks_items = "".join([f"<li>{item.get('name', 'Required Document')}</li>" for item in checklist_items[:5]])
        tasks_html = f"<h3 style='color:#1e3a8a;margin-top:16px;'>Immediate Document Tasks</h3><ol>{tasks_items}</ol>"

    link_html = ""
    if follow_up_url:
        link_html = f"""
        <div style="margin:24px 0;">
            <a href="{follow_up_url}" style="background-color:#2563eb;color:#ffffff;padding:12px 20px;text-decoration:none;border-radius:6px;font-weight:bold;display:inline-block;">View Your Action Plan Dashboard</a>
        </div>
        <p style="font-size:12px;color:#6b7280;">If the button does not work, copy and paste this link: <br><a href="{follow_up_url}">{follow_up_url}</a></p>
        """

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.5; color: #1f2937; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="border-bottom: 2px solid #e5e7eb; padding-bottom: 12px; margin-bottom: 20px;">
            <h2 style="color: #111827; margin: 0;">Unlocked Action Plan Summary</h2>
            <p style="color: #4b5563; font-size: 14px; margin: 4px 0 0 0;">Government Welfare Benefits Discovery</p>
        </div>
        <p>Hello,</p>
        <p>Thank you for using Unlocked. Here is the summary of potentially relevant schemes and initial document procurement steps identified for your profile.</p>
        <h3 style="color:#1e3a8a;margin-top:16px;">Matched Schemes</h3>
        <ul>{schemes_html}</ul>
        {tasks_html}
        {link_html}
        <hr style="border:0; border-top:1px solid #e5e7eb; margin:24px 0;" />
        <p style="font-size:12px; color:#9ca3af;">Privacy notice: Unlocked does not share your contact details. You can disable notifications at any time.</p>
    </body>
    </html>
    """
    return subject, html_body, text_body


def render_appointment_reminder_email(
    purpose: str,
    scheduled_at_str: str,
    location: Optional[str] = None,
    scheme_name: Optional[str] = None,
    follow_up_url: Optional[str] = None,
) -> tuple[str, str, str]:
    """Render Pre-Appointment Reminder email."""
    subject = f"Reminder: Upcoming Appointment for {scheme_name or purpose}"

    loc_str = f"Location: {location}\n" if location else ""
    link_str = f"\nView appointment details and preparation checklist:\n{follow_up_url}\n" if follow_up_url else ""

    text_body = f"""Hello,

This is a reminder regarding your upcoming appointment:

Purpose: {purpose}
Scheduled Date & Time: {scheduled_at_str}
{loc_str}
Preparation Tips:
- Carry original identity documents and required certificates.
- Keep application reference numbers (RD number, acknowledgment) handy.
{link_str}
Safe travels,
Project Unlocked
"""

    loc_html = f"<p><strong>Location:</strong> {location}</p>" if location else ""
    link_html = f"""<p style="margin-top:20px;"><a href="{follow_up_url}" style="background-color:#2563eb;color:#ffffff;padding:10px 16px;text-decoration:none;border-radius:4px;font-weight:bold;display:inline-block;">View Appointment & Document Checklist</a></p>""" if follow_up_url else ""

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: sans-serif; line-height: 1.5; color: #1f2937; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #1e3a8a;">Appointment Reminder</h2>
        <p>Hello, this is a reminder for your scheduled in-person visit.</p>
        <div style="background:#f3f4f6; padding:16px; border-radius:6px; margin:16px 0;">
            <p style="margin:0 0 8px 0;"><strong>Purpose:</strong> {purpose}</p>
            <p style="margin:0 0 8px 0;"><strong>Scheduled Time:</strong> {scheduled_at_str}</p>
            {loc_html}
        </div>
        <p><strong>Checklist:</strong> Please ensure you carry all original copies of required documents.</p>
        {link_html}
    </body>
    </html>
    """
    return subject, html_body, text_body


def render_appointment_follow_up_email(
    purpose: str,
    follow_up_url: str,
    scheme_name: Optional[str] = None,
) -> tuple[str, str, str]:
    """Render Post-Appointment Follow-up email."""
    subject = f"How did your appointment go? — {scheme_name or purpose}"

    text_body = f"""Hello,

You had an appointment scheduled for: {purpose}.

Did you attend the appointment?
What did the office say?

Please update what happened so Unlocked can update your action plan and next steps:
{follow_up_url}

Thank you,
Project Unlocked
"""

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: sans-serif; line-height: 1.5; color: #1f2937; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #1e3a8a;">Post-Appointment Follow-Up</h2>
        <p>Hello, you had an appointment scheduled for: <strong>{purpose}</strong>.</p>
        <p>Did you attend? Were all documents accepted, or was additional verification requested?</p>
        <div style="margin:24px 0;">
            <a href="{follow_up_url}" style="background-color:#059669;color:#ffffff;padding:12px 20px;text-decoration:none;border-radius:6px;font-weight:bold;display:inline-block;">Report Appointment Outcome</a>
        </div>
        <p style="font-size:12px; color:#6b7280;">Your response helps Unlocked dynamically adjust your document prerequisites and deadline schedule.</p>
    </body>
    </html>
    """
    return subject, html_body, text_body


def render_deadline_reminder_email(
    scheme_name: str,
    deadline_str: str,
    application_url: Optional[str] = None,
    source_url: Optional[str] = None,
    follow_up_url: Optional[str] = None,
) -> tuple[str, str, str]:
    """Render Deadline Reminder email."""
    subject = f"Deadline Approaching: {scheme_name}"
    app_str = f"Official Portal: {application_url}\n" if application_url else ""
    src_str = f"Deadline Source: {source_url}\n" if source_url else ""
    link_str = f"\nTrack your application progress:\n{follow_up_url}\n" if follow_up_url else ""

    text_body = f"""Hello,

The published application deadline for {scheme_name} is approaching:
Deadline: {deadline_str}
{src_str}{app_str}
Please ensure all documents and prerequisites are ready before submitting.
{link_str}
Regards,
Project Unlocked
"""

    app_html = f"<p><strong>Official Portal:</strong> <a href='{application_url}'>{application_url}</a></p>" if application_url else ""
    link_html = f"<p><a href='{follow_up_url}' style='background-color:#2563eb;color:#ffffff;padding:10px 16px;text-decoration:none;border-radius:4px;font-weight:bold;display:inline-block;'>Check Status & Action Plan</a></p>" if follow_up_url else ""

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: sans-serif; line-height: 1.5; color: #1f2937; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #b91c1c;">Application Deadline Approaching</h2>
        <p>The deadline for <strong>{scheme_name}</strong> is nearing:</p>
        <div style="background:#fee2e2; border:1px solid #f87171; padding:12px; border-radius:6px; margin:16px 0; color:#991b1b;">
            <strong>Deadline Date:</strong> {deadline_str}
        </div>
        {app_html}
        {link_html}
    </body>
    </html>
    """
    return subject, html_body, text_body


def render_application_status_update_email(
    scheme_name: str,
    old_status: str,
    new_status: str,
    next_action: Optional[str] = None,
    follow_up_url: Optional[str] = None,
) -> tuple[str, str, str]:
    """Render Application Status Update email."""
    subject = f"Status Update for {scheme_name}: {new_status.replace('_', ' ').title()}"

    next_str = f"\nRecommended Next Action:\n{next_action}\n" if next_action else ""
    link_str = f"\nView your application progress:\n{follow_up_url}\n" if follow_up_url else ""

    text_body = f"""Hello,

Your tracked application status for {scheme_name} has been updated:
Previous Status: {old_status.replace('_', ' ').title()}
New Status: {new_status.replace('_', ' ').title()}
{next_str}{link_str}
Regards,
Project Unlocked
"""

    next_html = f"<p><strong>Next Recommended Action:</strong> {next_action}</p>" if next_action else ""
    link_html = f"<p style='margin-top:20px;'><a href='{follow_up_url}' style='background-color:#2563eb;color:#ffffff;padding:10px 16px;text-decoration:none;border-radius:4px;font-weight:bold;display:inline-block;'>View Applications Dashboard</a></p>" if follow_up_url else ""

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: sans-serif; line-height: 1.5; color: #1f2937; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #1e3a8a;">Application Status Updated</h2>
        <p>Your application status for <strong>{scheme_name}</strong> has changed:</p>
        <div style="background:#f3f4f6; padding:14px; border-radius:6px; margin:16px 0;">
            <p style="margin:0 0 6px 0;"><strong>Previous:</strong> {old_status.replace('_', ' ').title()}</p>
            <p style="margin:0; font-size:16px; color:#1e3a8a;"><strong>Current:</strong> {new_status.replace('_', ' ').title()}</p>
        </div>
        {next_html}
        {link_html}
    </body>
    </html>
    """
    return subject, html_body, text_body


# ---------------------------------------------------------------------------
# Due Notification Poller & Scheduler
# ---------------------------------------------------------------------------

async def process_due_notifications(
    limit: int = 50,
    db_path: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Process due notifications scheduled on or before the current clock time.
    Atomically claims due notifications, verifies consent, dispatches via provider,
    and records results in SQLite.
    """
    now_dt = now_utc()
    now_iso = now_dt.isoformat()

    claimed = await claim_due_notifications(now_iso=now_iso, limit=limit, db_path=db_path)
    if not claimed:
        return []

    provider = get_email_provider()
    results: list[dict[str, Any]] = []

    for notif in claimed:
        notif_id = notif["notification_id"]
        session_id = notif["session_id"]
        notif_type = notif["notification_type"]
        recipient = notif["recipient"]
        subject = notif["subject"]
        body_html = notif.get("body_html") or ""
        body_text = notif.get("body_text") or ""
        idempotency_key = notif.get("idempotency_key")
        is_demo = bool(notif.get("is_demo", 0))

        # Check consent preferences for this session
        prefs = await get_notification_preferences(session_id, db_path=db_path)
        if not prefs or not prefs.get("email_enabled"):
            logger.info("Notification %s skipped: no consent for session %s", notif_id, session_id)
            updated = await update_notification_status(
                notif_id,
                status="skipped_no_consent",
                last_error="User notification preferences are disabled or consent missing.",
                db_path=db_path,
            )
            if updated:
                results.append(updated)
            continue

        # Check category preference if configured
        categories = prefs.get("categories") or {}
        if categories and not categories.get(notif_type, True):
            logger.info("Notification %s skipped: category %s disabled in preferences", notif_id, notif_type)
            updated = await update_notification_status(
                notif_id,
                status="skipped_no_consent",
                last_error=f"Notification category '{notif_type}' disabled by user preferences.",
                db_path=db_path,
            )
            if updated:
                results.append(updated)
            continue

        # Dispatch email
        try:
            target_recipient = recipient
            if is_demo or is_demo_mode():
                demo_to = os.getenv("DEMO_EMAIL_TO", "").strip()
                if demo_to:
                    target_recipient = demo_to
                if not subject.startswith("[DEMO]"):
                    subject = f"[DEMO] {subject}"
                if "[DEMO SIMULATION]" not in body_text:
                    body_text = f"[DEMO SIMULATION]\nThis email was triggered in demo mode with simulated time.\n\n" + body_text

            send_res = await provider.send_email(
                to_email=target_recipient,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
                idempotency_key=idempotency_key,
                is_demo=is_demo,
            )
            msg_id = send_res.get("id") or f"msg_{uuid.uuid4().hex[:12]}"
            updated = await update_notification_status(
                notif_id,
                status="accepted",
                provider_message_id=msg_id,
                sent_at_utc=now_iso,
                db_path=db_path,
            )
            if updated:
                results.append(updated)
            logger.info("Notification %s accepted by provider (message_id: %s)", notif_id, msg_id)
        except Exception as exc:
            err_msg = sanitize_error(str(exc))
            logger.error("Failed to send notification %s: %s", notif_id, err_msg)
            updated = await update_notification_status(
                notif_id,
                status="failed",
                last_error=err_msg,
                db_path=db_path,
            )
            if updated:
                results.append(updated)

    return results
