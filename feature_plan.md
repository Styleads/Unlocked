# Unlocked — Email, Follow-through & Recovery Feature Plan

> **Purpose:** This document defines the P0 follow-through features agreed for Unlocked: Resend-powered email notifications, appointment reminders and post-appointment updates, application progress tracking, and source-grounded rejection recovery. It is intended to be handed directly to the four implementation agents.
>
> **Product principle:** Unlocked helps a person take the next appropriate step. It must not imply that an application is approved, that a reminder was delivered, or that a rejection can be appealed unless the relevant status or procedure is actually supported.

---

## 1. Scope and decisions

### 1.1 Confirmed product decisions

| Decision | Agreed behaviour |
|---|---|
| Primary notification channel | **Email through Resend** |
| WhatsApp | Keep the design extensible, but defer implementation. It is not required for the P0 demo. |
| Contact collection | Do **not** ask for email or phone number during initial onboarding. Ask after the user receives their action plan and chooses to enable follow-through. |
| Contact details | Email is sufficient for P0. Do not require a phone number. |
| Consent | Explicit opt-in for follow-through notifications. Explain what will be sent and allow the user to disable them. |
| Action-plan email | Show a preview and ask the user to confirm before sending the initial summary. |
| Scheduled reminders | Once the user has opted in, send the reminder types they selected without asking for approval on every routine reminder. |
| Government-office emails | P0 may generate drafts for the user to review and send. Do not automatically send emails to government offices. |
| Application updates | Provide a secure link back to the relevant Unlocked session/application follow-up screen. |
| Appointment follow-up | Ask what happened after an appointment; use the response to update application/document state and invoke the appropriate workflow stages. |
| Rejection handling | A rejection triggers investigation, not an automatic appeal. Verify whether a correction, clarification, grievance, appeal, reapplication, alternative scheme, or no further action is supported. |
| Demo time | Simulate time through an application-level clock. Never change the operating-system clock. |
| Demo email | Send a real Resend email to a configured test inbox, not to an evaluator or real user unless they explicitly opt in. Clearly label the event as a demo. |
| Data and state | Persist notification preferences, consent, appointment/application history, reminders, and notification outcomes in SQLite. |

### 1.2 P0 objectives

A user must be able to:

1. Complete discovery and receive a personalized document/action plan without providing contact details.
2. Opt into email follow-through after seeing the action plan.
3. Preview and confirm an initial action-plan email.
4. Schedule an appointment or record a relevant deadline.
5. Receive an email reminder before an appointment/deadline, where the date/time is known and the user has opted in.
6. Open a secure follow-up link from an email or calendar event.
7. Report whether an appointment happened and what the office said.
8. Update an application status (submitted, under review, approved, rejected, etc.).
9. Trigger a reassessment and updated next-step plan when new information arrives.
10. Report a rejection and receive a source-grounded recovery investigation and, where supported, a concrete next action.
11. Receive a follow-up reminder for an outstanding action, if opted in.
12. Demonstrate accelerated reminder delivery using demo mode and a real email to the configured test inbox.

### 1.3 Explicitly out of scope for P0

- WhatsApp Business / Cloud API integration.
- SMS, automated phone calls, or push notifications.
- Mandatory user accounts, passwords, or OTP login.
- Automatic government-portal submission or status scraping.
- Automatically sending emails to government offices.
- Automatically filing appeals, grievances, or reapplications.
- Claiming eligibility, approval, payment, or delivery without evidence.
- Uploading or storing identity-document scans as a requirement for follow-through.
- Full OCR/document extraction from rejection notices as a core dependency. The user may paste the rejection reason; file upload can be a stretch feature.
- A complex queue infrastructure or multi-worker scheduler. P0 may use a single-process DB-backed scheduler.

---

## 2. User journey changes

### 2.1 Initial onboarding — no contact details

The existing initial context form remains focused on information used for discovery and assessment, such as:

- State and district.
- Age or age range, where relevant.
- Education/employment status or life situation.
- Goal or benefit categories.
- Other relevant attributes supported by the selected discovery flow.

Do not request an email address or phone number at this stage. Do not make contact information a condition for discovering schemes or viewing results.

### 2.2 Follow-through opt-in after the action plan

After the user receives their action plan, show an optional prompt such as:

> **Stay on track with Unlocked**  
> Receive your action-plan summary, appointment reminders, deadline reminders, and follow-up prompts by email. You can disable these at any time.

The user chooses:

- Enable email reminders.
- Not now / continue without notifications.

If they enable email, ask for an email address and explicit consent. Do not ask for a phone number for the P0 email implementation.

Recommended consent copy:

> I agree to receive the Unlocked emails I selected, including action-plan updates, appointment reminders, deadline reminders, and follow-up prompts. I understand that Unlocked stores my email address and notification preferences for this session, and I can disable notifications or delete my session at any time.

The UI must make clear which notification categories are enabled. Consent should not be bundled with unrelated terms or inferred from entering an email address.

### 2.3 Email categories / preferences

For P0, support a simple preference model:

- `action_plan_summary` — initial summary after preview and confirmation.
- `appointment_reminders` — upcoming appointment reminder.
- `appointment_follow_up` — prompt after the appointment to report what happened.
- `deadline_reminders` — reminders for source-verified or user-entered deadlines.
- `pending_action_reminders` — reminders for user-visible outstanding tasks.
- `application_status_updates` — email after the user records a meaningful application status update and the plan changes.

A user may disable all notifications. At minimum, provide one obvious **Disable email reminders** action. If time permits, make category preferences individually configurable.

### 2.4 Post-action plan dashboard

Add a dashboard section named **My Applications & Progress** (or equivalent) that displays separate records for each scheme/application. It should show:

- Scheme name.
- Current application state.
- Whether the state is user-reported or independently verified.
- Completed and outstanding document/action tasks.
- Upcoming appointment/deadline, if any.
- Most recent update and next recommended action.
- A clear action to update progress.

Do not combine different schemes into one application record. A user may have one application approved and another rejected at the same time.

---

## 3. Application and appointment lifecycle

Appointments and applications are related but distinct entities. An appointment being attended does not imply that an application was submitted or approved.

### 3.1 Application states

Use a controlled lifecycle for each tracked scheme application. Suggested states:

| State | Meaning |
|---|---|
| `not_started` | User has not started preparing an application. |
| `preparing` | User is collecting documents or completing prerequisites. |
| `submitted` | User reports that the application was submitted, or a trusted integration confirms it. |
| `under_review` | User reports that the application is being processed, or a trusted source confirms it. |
| `approved` | Approval is reported by the user or confirmed by a trusted source. |
| `rejected` | Rejection is reported by the user or confirmed by a trusted source. |
| `benefit_received` | User reports or a trusted source confirms actual receipt of the benefit. |
| `closed` | User has ended tracking or the journey has reached a terminal outcome. |

Store the **status source** separately:

- `user_reported`
- `official_verified`
- `demo_simulated`

The UI must distinguish user-reported status from independently verified status. Do not silently upgrade a user report to verified.

### 3.2 Appointment states

Suggested appointment states:

- `scheduled`
- `rescheduled`
- `attended`
- `missed`
- `cancelled`
- `outcome_unknown`

An appointment can concern a document prerequisite (for example, obtaining a certificate) or an application process. Link it to the relevant session and, where applicable, application/document task.

### 3.3 Appointment scheduling

When a user schedules an appointment, capture:

- Appointment purpose.
- Date and time, if known.
- Time zone (use `Asia/Kolkata` as the default for the Karnataka-focused MVP, but store an IANA time zone rather than assuming it forever).
- Location or official office name, if supplied/verified.
- Related document/application task.
- Whether the user wants an email reminder.

Do not invent appointment times or locations. If the user provides only a date, do not fabricate a time.

### 3.4 Reminder timing

Recommended configurable defaults:

- Pre-appointment email: 24 hours before the appointment, when a precise time is available.
- Post-appointment follow-up email: approximately 2 hours after the scheduled appointment end/time.
- Deadline reminder: configurable lead time; use a sensible default such as 2 days before, but only for a real verified or user-entered deadline.
- Pending-action reminder: only when the task has a user-confirmed due date or the user explicitly asks for a reminder.

These defaults must be configurable. If the date/time is missing or uncertain, do not schedule a time-specific notification. Instead, show a manual follow-up action in the dashboard.

### 3.5 Post-appointment update screen

Email and calendar-event links should take the user directly to the relevant Unlocked follow-up page, not to an unrelated government website.

The page should ask:

**1. Did you attend?**
- Yes, I attended.
- It was rescheduled.
- I could not attend.
- The appointment was cancelled.
- I am not sure / something else.

**2. If attended, what happened?**
- Documents were accepted.
- Additional documents were requested.
- Application was submitted.
- Application is pending verification/review.
- Application was approved.
- Application was rejected.
- I was asked to return / another appointment was scheduled.
- Something else / I am not sure.

The exact outcome choices may be shown conditionally. Do not force the user to answer every question. Provide an optional free-text field:

> What did the office tell you? Were any documents missing? Were you given another date?

Allow the user to skip details. Unknown information remains unknown.

### 3.6 How each appointment outcome changes the workflow

| User update | System response |
|---|---|
| Documents accepted | Update the relevant user-reported document task; ask whether the application was also submitted if unclear. |
| Additional documents requested | Add/update the missing document task; verify whether it is required; invoke planning to update dependencies and next actions. |
| Application submitted | Set application to `submitted` with source `user_reported`; record the reported submission date; retain approval as pending. |
| Pending verification/review | Set application to `under_review` with source `user_reported`; schedule a follow-up only when a date is known or requested. |
| Approved | Record `approved` as user-reported; ask whether the benefit was actually received. Do not mark `benefit_received` automatically. |
| Rejected | Start the rejection-recovery workflow in Section 6. |
| Rescheduled | Update the appointment date/time and replace/cancel old reminders so the user does not receive stale notifications. |
| Missed/cancelled | Ask whether the user wants to reschedule; preserve unfinished document tasks. Do not assume the application has failed. |
| Unclear / other | Save the user's note and ask only the most useful follow-up question, if needed. Keep unsupported state unknown. |

---

## 4. Resend email implementation

### 4.1 Architecture

The LLM/agent generates or selects the content; the backend notification service enforces consent, validates the recipient, schedules the send, calls Resend, and records the result.

```text
Agent / workflow event
        |
        v
Notification content builder
        |
        v
Consent + preference + due-time checks
        |
        v
Notification record in SQLite
        |
        v
DB-backed scheduler / due-job poller
        |
        v
Resend email service
        |
        v
Resend API response + message ID
        |
        v
Notification status stored in SQLite
        |
        +--> Optional Resend webhook updates delivery/bounce status
```

The LLM must not receive the Resend API key or have unrestricted ability to send arbitrary email. It should request a typed notification action; the backend validates it.

### 4.2 Provider setup

Use the official Resend Python SDK. For the asynchronous FastAPI backend, the current SDK supports async methods through the async extra:

```bash
pip install "resend[async]"
```

The current async SDK pattern is `await resend.Emails.send_async(params)`. Confirm the exact API against Resend's current documentation during implementation.

Required environment variables:

```env
RESEND_API_KEY=
RESEND_FROM_EMAIL=
APP_BASE_URL=http://localhost:8000
APP_TIMEZONE=Asia/Kolkata
DEMO_MODE=false
DEMO_EMAIL_TO=
```

Never commit `.env` or a real API key. Add only variable names and safe placeholders to `.env.example`.

Before sending from a project-owned address, configure and verify a sending domain in Resend. For initial development, use the sender/test setup permitted by the Resend account. Do not assume a production sender domain is already available.

### 4.3 Email send behaviour

For every send:

1. Load notification and session preferences.
2. Confirm the user has opted into the relevant notification category.
3. Confirm the recipient email exists and is valid enough to send.
4. Ensure the notification has not already been sent/cancelled.
5. Render both HTML and plain-text content.
6. Add the secure Unlocked follow-up URL when relevant.
7. Call Resend from the backend only.
8. Persist the provider response/message ID and current status.
9. Handle failure without falsely displaying success.

Use a unique idempotency key per notification so retries or repeated scheduler ticks do not send duplicate messages. Resend documents idempotency support and currently retains idempotency keys for 24 hours; the application's own database status/deduplication must remain the longer-lived source of truth.

### 4.4 Notification states

Suggested values:

- `scheduled`
- `processing`
- `accepted` (Resend accepted the API request and returned a message ID)
- `delivered` (only after a delivery event/webhook confirms it)
- `failed`
- `cancelled`
- `skipped_no_consent`

Do not label an API-accepted message as `delivered`. If webhook delivery tracking is not implemented in P0, show `sent` or `accepted` and explain that delivery confirmation is unavailable.

### 4.5 Email types and contents

#### A. Action-plan summary

- Trigger: user has received the plan, opted into email, previewed it, and pressed **Send to my email**.
- Include: short summary, scheme names/statuses, immediate next steps, selected document tasks, verified official links, and a link back to Unlocked.
- Exclude: unnecessary sensitive profile details, identity numbers, full income values, caste details, or document images.

#### B. Pre-appointment reminder

- Trigger: scheduled reminder time reached and `appointment_reminders` is enabled.
- Include: appointment purpose, user-supplied/verified date and time, preparation checklist, location if known, and follow-up link.
- Never invent appointment details.

#### C. Post-appointment follow-up

- Trigger: configured follow-up time after the appointment, if the user has not already submitted an outcome.
- Include: brief prompt to update what happened and a secure link directly to the relevant appointment update page.
- Do not send again if the appointment outcome has already been recorded.

#### D. Deadline reminder

- Trigger: scheduled lead time before a verified or user-entered deadline.
- Include: scheme name, deadline, pending tasks, official application link, and follow-up dashboard link.
- Keep the deadline provenance visible in the application. If the source is uncertain, do not word it as a confirmed deadline.

#### E. Pending-action reminder

- Trigger: an outstanding action reaches a user-selected reminder date/time.
- Include: the action, why it matters, and the next available step.
- Do not nag repeatedly. Add a frequency cap and suppress reminders after task completion or opt-out.

#### F. Application status/action-plan update

- Trigger: a user update causes a material change in the action plan.
- Include: what changed and the next action. Do not disclose sensitive details unnecessarily.

### 4.6 Government-office email drafts are different

Use Resend to send notifications **to the Unlocked user**.

For P0, messages addressed to government offices should be generated as drafts for the user to review, copy, and send themselves. Do not send government-office emails automatically. This preserves user control and avoids sending unapproved or incorrect claims.

### 4.7 Resend webhooks (stretch / P1)

If time allows, add a Resend webhook endpoint for events such as `email.delivered`, `email.bounced`, and `email.complained`.

- Verify webhook signatures using the raw request body and Resend's documented verification method.
- Store the event against the Resend message ID.
- Never trust an unsigned webhook payload.
- Use delivery events to update `notification_status` from `accepted` to `delivered` or `failed` where appropriate.

Webhook delivery tracking is not a blocker for the P0 demo. A Resend API success response is sufficient to demonstrate an accepted send, but the UI must not call it delivered without confirmation.

---

## 5. Scheduler and accelerated demo mode

### 5.1 Why reminders must be database-backed

Do not rely only on an in-memory `asyncio.sleep()` or FastAPI `BackgroundTasks` for reminders that may be hours or days in the future. Those approaches do not provide durable scheduling across application restarts.

For P0, implement a simple DB-backed due-notification poller:

- Store each reminder with `scheduled_at` in UTC.
- A single-process scheduler/poller checks due rows periodically (for example every 30–60 seconds).
- Claim a due notification in a short SQLite transaction before attempting to send it.
- Send through Resend.
- Persist the result and provider message ID.
- Use application-level idempotency so repeated polls cannot create duplicate sends.
- Cancel or reschedule obsolete reminders when appointments/dates/tasks change.

The P0 implementation may assume one backend worker/process. Document that multiple workers would require stronger job claiming/locking or a dedicated queue before production deployment.

### 5.2 Clock abstraction

Create one clock abstraction used by reminder scheduling and due-job evaluation:

- Production clock: real UTC time.
- Demo clock: real time plus a configurable demo offset, or an explicitly controlled simulated timestamp.

Never change the machine/OS clock. Demo mode must be disabled by default and impossible to activate in a production deployment.

### 5.3 Fast-forward demo flow

The demo should prove that Unlocked can schedule a reminder and cause a real email to be sent when that reminder becomes due, without waiting multiple days.

Example:

1. Create a demo appointment or deadline with a future reminder.
2. Show the scheduled date/time in the dashboard.
3. Advance the simulated clock to the reminder time using a demo-only backend action.
4. Run the normal due-reminder processor.
5. Send a real Resend email to `DEMO_EMAIL_TO` (a team-controlled test inbox).
6. Display the notification record and Resend message ID/status.
7. Show the received email in the test inbox.

The UI and email subject should clearly indicate `[DEMO]` or otherwise state that time was simulated. Do not claim that real time passed.

### 5.4 Demo safety rules

- `DEMO_MODE=false` by default.
- Demo clock endpoints must return an error when demo mode is disabled.
- In demo mode, route outgoing email to `DEMO_EMAIL_TO` by default, rather than an evaluator's or real user's address.
- Prefix the subject/body with a clear demo label.
- Do not send demo-triggered emails to real users.
- Demo simulation must not mutate actual appointment dates, official deadlines, or the system clock.
- Keep simulated events marked `demo_simulated` in the database/UI.

---

## 6. Secure follow-up links

### 6.1 Desired user experience

An appointment reminder, post-appointment email, or calendar event should include a link that opens the exact relevant Unlocked update page.

The user should not have to repeat the discovery interview or search for the application again.

### 6.2 Token design

The project does not require full accounts for the hackathon, so use a secure, unguessable follow-up token rather than exposing a raw sequential ID.

Recommended approach:

- Generate a cryptographically random token with at least 256 bits of entropy.
- Store only a hash of the token in SQLite.
- Associate it with the session and the specific appointment/application scope it may update.
- Give it a configurable expiry.
- Allow token revocation when the session is deleted or the user disables/revokes the link.
- Provide a way to regenerate a link from the active session if needed.
- Rate-limit invalid-token attempts.
- Avoid logging the raw token.
- Do not put unnecessary personal information in the URL.

For P0, a scoped bearer link is acceptable as a lightweight session access mechanism, but clearly treat possession of the link as access. Do not expose the entire session if the link only needs to update one appointment.

### 6.3 Link handling and privacy

- Use HTTPS for any public deployment.
- Do not load third-party trackers/assets on the token-bearing follow-up page.
- Set a restrictive referrer policy (for example, `no-referrer`).
- Keep the token out of application logs and analytics.
- On session reset/deletion, revoke outstanding follow-up tokens and cancel pending notifications.
- A notification opt-out must stop future scheduled messages; it does not necessarily need to invalidate the follow-up page itself unless the user also revokes the link/session.

### 6.4 Calendar integration

If the existing `.ics` export is implemented, add the follow-up URL to the event description. The calendar event should include only the minimum appointment information and must not expose sensitive profile data.

---

## 7. Rejection recovery workflow

### 7.1 Product rule

**A rejection is a trigger for investigation, not an automatic terminal state and not an automatic appeal.**

Some rejections are recoverable; some are not. The system must verify whether an official remedy exists before recommending it. If no remedy is supported by available official information, say so and consider alternative schemes.

### 7.2 User input

When a user reports a rejection, collect:

- Which scheme/application was rejected.
- Whether the status is user-reported or supported by an official notice.
- Rejection reason (structured choice if known, plus optional free text).
- Rejection date, if known.
- Any deadline or instruction shown in the notice, if known.
- Optional rejection notice upload as a stretch capability; do not require a scan or identity document.

Suggested initial reasons:

- Missing document.
- Invalid/expired document.
- Incorrect information.
- An eligibility criterion was not met.
- Application submitted late / deadline missed.
- Duplicate or incomplete application.
- Administrative/technical issue.
- Other / reason not clear.

Do not force a user to choose a reason if they do not know it.

### 7.3 Recovery workflow stages

1. **Record the rejection report.** Save the reported reason and mark the status source as `user_reported` unless official evidence is available.
2. **Interpret the reason.** Action & Follow-through Agent extracts the relevant issue and any stated instruction/deadline. Preserve the user's original wording.
3. **Verify the underlying rule.** Eligibility & Verification Agent checks the exact scheme criterion, document requirement, deadline, and relevant official guidance.
4. **Find permitted recovery routes.** Search official sources for correction, supplementary document submission, clarification, grievance, appeal, or reapplication procedures where applicable.
5. **Reassess if new facts matter.** If the rejection reveals a new or corrected user attribute, rerun eligibility assessment. Missing information remains unknown.
6. **Update the plan.** Document & Planning Agent updates relevant document tasks, dependencies, and next actions using only verified requirements.
7. **Prepare a user-controlled action.** Action & Follow-through Agent may prepare a clarification/correction email draft or a source-grounded appeal draft if official rules permit it.
8. **Ask the user to review and decide.** The user carries out consequential submissions. Do not automatically submit an appeal or application.
9. **Schedule follow-up.** If the user chooses a next step and provides/accepts a date, schedule a reminder.
10. **Close or continue.** If no supported remedy is found, explain that clearly, close that application path if the user agrees, and discover alternative schemes where useful.

### 7.4 Recovery action classifications

Use a controlled classification. It is an assessment output, not a promise that the action is allowed:

- `correct_document`
- `submit_supplementary_documents`
- `request_clarification`
- `file_grievance`
- `appeal_or_reconsideration`
- `reapply`
- `alternative_scheme`
- `no_supported_remedy_found`
- `needs_more_information`
- `unknown`

Store evidence for each proposed recovery path:

- Official source URL.
- Exact requirement/procedure or a concise source-grounded extract.
- Verification status.
- Date checked.
- Any stated time limit.
- Uncertainty/conflict notes.

Never infer that a scheme permits an appeal merely because another government scheme does. Never invent a deadline, grievance portal, officer contact, or correction route.

### 7.5 Recovery status

Suggested recovery state values:

- `not_started`
- `investigating`
- `needs_more_information`
- `action_available`
- `no_supported_remedy_found`
- `user_action_pending`
- `resolved`
- `closed`

### 7.6 Examples

**Example A — Missing document**

User says: "My application was rejected because my income certificate was not accepted."

Unlocked should:

- Ask or extract whether the notice gives a specific reason (expired certificate, wrong authority, format, etc.).
- Verify the exact accepted certificate requirement from official guidance.
- Check whether the portal/authority permits correction or supplementary documents.
- If supported, add the correct document task and prepare a clarification/correction draft.
- If the process is unclear, draft a question to the relevant office rather than promising resubmission.

**Example B — Eligibility criterion not met**

User says: "My application was rejected because my income is above the scheme limit."

Unlocked should:

- Verify the threshold and its applicability to the scheme/year/category.
- Ask for clarification if the relevant income measure is unclear.
- Reassess using the corrected/confirmed information.
- If the user genuinely does not meet the criterion and no permitted remedy exists, do not recommend an appeal without evidence.
- Search for alternative schemes the user may potentially match.

**Example C — Administrative error/disputed decision**

User says: "The portal rejected my application even though I uploaded the requested document."

Unlocked should:

- Preserve the user's account as a user report.
- Check official help/grievance/clarification routes.
- Prepare a factual clarification draft and list the evidence the user may need to reference.
- Avoid accusing the authority or claiming that the rejection is invalid.

**Example D — No available remedy**

If official guidance confirms there is no correction/reapplication/appeal route, explain that no supported remedy was found. Ask whether the user wants to explore alternative schemes. A terminal application state should not terminate the user's broader Unlocked journey.

---

## 8. How the four existing agents participate

Do not add a fifth agent. Reuse the existing four logical workflow stages.

| Existing agent / owner | Follow-through responsibilities |
|---|---|
| **Agent 1 — Discovery** (Member 1) | Find alternative schemes after a terminal rejection; retrieve official scheme/application information when the recovery workflow needs it; preserve evidence and source URLs. |
| **Agent 2 — Eligibility & Verification** (Member 2) | Verify rejection reasons against official criteria; verify document rules and permitted recovery procedures; reassess when new information changes eligibility; distinguish unknown from not satisfied. |
| **Agent 3 — Document & Planning** (Member 2) | Update document checklist and dependency graph; mark user-reported completed tasks appropriately; recompute the ordered plan after new requirements or outcomes. |
| **Agent 4 — Action & Follow-through** (Member 1) | Interpret appointment/application updates; coordinate rejection recovery; generate reminder content and government-office email drafts; prepare the next action and follow-up timeline. |
| **Backend/orchestration** (Member 3) | Persist application/appointment state; enforce state transitions and consent; schedule notifications; create/revoke secure follow-up links; call Resend; expose APIs; maintain idempotency and demo mode. |
| **Frontend/UX** (Member 4) | Collect notification opt-in after the plan; show email preview; build My Applications & Progress; build appointment/outcome/rejection forms; display source evidence and recovery actions; show demo mode clearly. |

### 8.1 Handoff sequence after a progress update

```text
User submits appointment/application update
                  |
                  v
Backend validates session/token and stores report
                  |
                  v
Action & Follow-through interprets the update
                  |
        +---------+----------+
        |                    |
        v                    v
New eligibility fact?   Document/task change?
        |                    |
        v                    v
Eligibility &            Document &
Verification             Planning
        |                    |
        +---------+----------+
                  |
                  v
Backend persists revised assessment/plan
                  |
                  v
Action Agent prepares next-step explanation
                  |
                  v
User reviews plan / chooses next action
                  |
                  v
Schedule relevant email reminder (if opted in)
```

Only invoke the stages required by the new information. Do not call all agents for every trivial status update if no reassessment is needed.

---

## 9. Suggested backend data model

Adapt these to the existing SQLite/session JSON design rather than creating unnecessary complexity. The key requirement is durable state and an event history.

### 9.1 `notification_preferences`

Suggested fields:

- `session_id` (FK)
- `email` (nullable)
- `email_enabled` (boolean)
- `consent_version` (text)
- `consent_at` (timestamp)
- `disabled_at` (nullable timestamp)
- `timezone` (IANA time-zone string)
- `created_at`, `updated_at`

If category-level preferences are implemented, store them as explicit columns or a validated JSON object.

### 9.2 `tracked_applications`

Suggested fields:

- `application_id` (primary key)
- `session_id` (FK)
- `scheme_id`
- `status`
- `status_source` (`user_reported`, `official_verified`, `demo_simulated`)
- `reported_submission_at` (nullable)
- `last_updated_at`
- `recovery_status` (nullable)
- `created_at`

A scheme result is not automatically a tracked application. Create/activate the tracked application when the user chooses to pursue it or schedules a related task.

### 9.3 `appointments`

Suggested fields:

- `appointment_id` (primary key)
- `session_id` (FK)
- `application_id` (nullable FK)
- `related_task_id` (nullable)
- `purpose`
- `scheduled_at_utc` (nullable)
- `timezone`
- `location` (nullable)
- `status`
- `outcome_summary` (nullable)
- `status_source`
- `follow_up_at_utc` (nullable)
- `created_at`, `updated_at`

### 9.4 `application_events`

Append-only history of meaningful updates:

- `event_id`
- `session_id`
- `application_id`
- `appointment_id` (nullable)
- `event_type`
- `old_status` (nullable)
- `new_status` (nullable)
- `source` (`user_reported`, `official_verified`, `demo_simulated`, `system`)
- `details_json` (validated/minimized)
- `created_at`

This allows the dashboard to show a timeline and avoids losing prior status information when an application is updated.

### 9.5 `notifications`

Suggested fields:

- `notification_id` (primary key)
- `session_id` (FK)
- `application_id` (nullable FK)
- `appointment_id` (nullable FK)
- `notification_type`
- `channel` (P0: `email`)
- `recipient` (email; protect as personal data)
- `subject`
- `scheduled_at_utc` (nullable for immediate sends)
- `status`
- `provider` (`resend`)
- `provider_message_id` (nullable)
- `idempotency_key` (unique)
- `sent_at_utc` (nullable)
- `delivered_at_utc` (nullable)
- `last_error` (sanitized; never include API keys)
- `is_demo` (boolean)
- `created_at`, `updated_at`

Avoid storing rendered email bodies indefinitely unless needed for debugging; if stored, minimize personal data and apply the session retention policy.

### 9.6 `follow_up_tokens`

Suggested fields:

- `token_id`
- `session_id` (FK)
- `appointment_id` (nullable FK)
- `application_id` (nullable FK)
- `token_hash` (unique)
- `expires_at_utc`
- `revoked_at_utc` (nullable)
- `created_at`

Store only the token hash, not the raw bearer token.

### 9.7 Existing session deletion/reset behaviour

When a user deletes/resets a session:

- Delete or anonymize session-linked contact preferences according to the agreed retention policy.
- Revoke all follow-up tokens.
- Cancel pending notifications.
- Remove or cascade-delete appointment/application events and tracked state.
- Do not leave a pending reminder that can still send to the old email address.

---

## 10. Suggested API contract

Use the existing API style and ensure every data operation is scoped to a `session_id`, except secure token-based follow-up routes and provider webhooks.

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/sessions/{session_id}/notifications/preferences` | Save email address, opt-in, time zone and selected notification categories. |
| `GET` | `/api/sessions/{session_id}/notifications/preferences` | Retrieve notification preferences. |
| `POST` | `/api/sessions/{session_id}/notifications/action-plan/preview` | Generate a preview of the action-plan email without sending. |
| `POST` | `/api/sessions/{session_id}/notifications/action-plan/send` | Confirm and send the action-plan summary through Resend. |
| `GET` | `/api/sessions/{session_id}/notifications` | List recent/scheduled notifications. |
| `POST` | `/api/sessions/{session_id}/appointments` | Create an appointment and optional reminder jobs. |
| `PATCH` | `/api/sessions/{session_id}/appointments/{appointment_id}` | Reschedule/cancel/update appointment details and replace stale reminders. |
| `POST` | `/api/sessions/{session_id}/appointments/{appointment_id}/outcome` | Submit the post-appointment outcome. |
| `GET` | `/api/sessions/{session_id}/applications` | List tracked applications and their progress. |
| `POST` | `/api/sessions/{session_id}/applications` | Start tracking a scheme application. |
| `POST` | `/api/sessions/{session_id}/applications/{application_id}/outcome` | Submit an application status update. |
| `POST` | `/api/sessions/{session_id}/applications/{application_id}/rejection-analysis` | Start source-grounded rejection investigation. |
| `GET` | `/api/sessions/{session_id}/applications/{application_id}/recovery` | Retrieve current recovery status, evidence and next actions. |
| `POST` | `/api/sessions/{session_id}/notifications/{notification_id}/cancel` | Cancel a pending notification. |
| `POST` | `/api/sessions/{session_id}/notifications/disable` | Disable future email notifications and cancel pending jobs. |
| `GET` | `/api/follow-up/{token}` | Load the scoped appointment/application update page. |
| `POST` | `/api/follow-up/{token}/outcome` | Submit an update through the secure link. |
| `POST` | `/api/webhooks/resend` | Optional P1: receive verified Resend delivery/bounce events. |
| `POST` | `/api/demo/advance-time` | Demo-only: advance simulated time and process newly due notifications. Must be disabled outside demo mode. |

The precise route names may be adjusted to match the existing backend. The session scoping, consent checks, and token restrictions must not be dropped.

---

## 11. Frontend requirements

### 11.1 Follow-through opt-in component

Place after the initial action plan, not on the first onboarding form.

Required UI:

- Email address input.
- Clear description of email categories.
- Explicit consent checkbox/toggle.
- `Enable email reminders` and `Not now` actions.
- Confirmation that preferences were saved.
- A way to disable notifications later.

Do not imply that notifications are enabled until the backend confirms consent/preferences were saved.

### 11.2 Action-plan email preview

Show:

- To address.
- Subject.
- Rendered preview.
- Included scheme/action summary.
- Official source links.
- A clear `Send to my email` button.

Do not send the first action-plan email automatically merely because the user typed an address.

### 11.3 My Applications & Progress

For each tracked application show:

- Scheme name.
- Current application status and status source.
- Timeline of updates.
- Completed/pending document tasks.
- Appointment and deadline cards.
- Next action.
- `Update progress` action.
- `Analyze rejection` action when status is rejected.

### 11.4 Post-appointment form

Implement the structured questions in Section 3.5. Use conditional fields and allow optional free text. Do not require a file upload.

### 11.5 Rejection recovery screen

Show:

- Reported rejection reason.
- What Unlocked could verify.
- Official source links for the relevant rule/procedure.
- Recovery status.
- Suggested next actions with their evidence/uncertainty.
- Draft communication, if generated.
- `Mark action as completed` / `Update outcome` controls.

Do not show an `Appeal now` call to action unless the system has verified that the relevant scheme permits it and the user has reviewed the proposed action.

### 11.6 Notification history

At minimum show a simple list:

- Scheduled.
- Accepted/sent by provider.
- Delivered, only if confirmed by webhook.
- Failed.
- Cancelled.

Include the notification type and schedule time. Do not expose provider credentials or internal error traces.

---

## 12. Privacy, consent, and reliability requirements

1. No contact details during initial onboarding.
2. Email address is optional and collected only after the user chooses email follow-through.
3. Explicit opt-in is required before action-plan or reminder emails are sent.
4. Provide an easy way to disable notifications.
5. Session deletion/reset revokes follow-up links and cancels pending notifications.
6. Do not place Aadhaar numbers, OTPs, passwords, full income details, caste details, or document scans in email content unless absolutely necessary; for this feature, they should not be included.
7. Do not log raw follow-up tokens, API keys, or full sensitive request payloads.
8. Store timestamps in UTC and retain the user's IANA time zone for display/scheduling.
9. Recalculate reminders when the relevant appointment/deadline changes.
10. Cancel reminders after the corresponding task/outcome is complete.
11. Prevent duplicate sends using database state and Resend idempotency keys.
12. Distinguish provider acceptance from confirmed delivery.
13. Treat user reports and demo-simulated events differently from official verification.
14. Never make a consequential application, appeal, or grievance submission automatically.
15. Never invent a government recovery procedure or deadline.
16. Keep a documented session retention/deletion policy. Do not claim contact data is temporary if it remains in SQLite or provider logs.

---

## 13. Testing and acceptance criteria

### 13.1 Consent and contact collection

- [ ] A new user can complete discovery without an email or phone number.
- [ ] The follow-through opt-in appears after the action plan.
- [ ] The user can skip the opt-in.
- [ ] The user can enable email and save an address.
- [ ] The backend refuses to send when consent is absent or disabled.
- [ ] Disabling email cancels future pending notifications.

### 13.2 Resend integration

- [ ] API key is loaded from environment variables only.
- [ ] The app can send a test email through Resend.
- [ ] The initial action-plan email is previewed and confirmed by the user.
- [ ] Provider message ID is persisted.
- [ ] API failure is recorded and shown without falsely claiming delivery.
- [ ] Repeated scheduler ticks/retries do not send duplicate messages.
- [ ] HTML and plain-text email bodies are generated.
- [ ] Email content excludes unnecessary sensitive profile data.

### 13.3 Scheduling

- [ ] A scheduled notification survives a backend restart because its job is in SQLite.
- [ ] A due notification is processed by the scheduler.
- [ ] A future notification is not sent early.
- [ ] Rescheduling an appointment cancels/replaces the previous reminder.
- [ ] Completing an appointment/task suppresses its obsolete reminder.
- [ ] Missing/uncertain dates do not result in invented scheduled notifications.

### 13.4 Secure follow-up links

- [ ] A valid token opens only the intended scoped follow-up page.
- [ ] An invalid, expired, or revoked token is rejected.
- [ ] Raw tokens are not stored in the database or logs.
- [ ] Session deletion revokes the token.
- [ ] Updating progress through the link persists the same state as updating through the dashboard.

### 13.5 Appointment outcomes

- [ ] User can report attended, rescheduled, missed, or cancelled.
- [ ] Attended appointment can record accepted documents, extra documents, submission, pending review, approval, rejection, or other.
- [ ] Additional document request updates the relevant checklist/planning flow.
- [ ] Submitted does not become approved.
- [ ] Approved does not become benefit received automatically.
- [ ] Rescheduled appointment updates notification times and calendar details.
- [ ] User-reported status remains labelled as user-reported.

### 13.6 Rejection recovery

- [ ] Rejection report can be submitted without a file upload.
- [ ] Original user wording is retained in the event history.
- [ ] Agent identifies the stated reason or marks it unclear.
- [ ] Relevant eligibility/document/procedure claims include official evidence or are explicitly marked uncertain.
- [ ] Unknown recovery procedure does not become an invented appeal recommendation.
- [ ] Correction, clarification, grievance, appeal, or reapplication is proposed only when supported by official guidance.
- [ ] If no remedy is found, the system explains this and can offer alternative scheme discovery.
- [ ] New information triggers the relevant eligibility/planning reassessment.

### 13.7 Demo mode

- [ ] Demo mode is disabled by default.
- [ ] Demo clock cannot be advanced when demo mode is off.
- [ ] Advancing simulated time causes the ordinary due-notification processor to run.
- [ ] A real Resend email is sent to `DEMO_EMAIL_TO`.
- [ ] Email subject/UI clearly labels the event as simulated demo activity.
- [ ] No real user's email receives demo messages.
- [ ] System/OS clock remains unchanged.
- [ ] Demo state is labelled `demo_simulated` and is not presented as a real user outcome.

---

## 14. Implementation order

Build in dependency order. Do not start with WhatsApp or advanced rejection-document parsing.

### Phase 1 — State model and API contract

- Agree on application and appointment state values.
- Add notification preference/consent models.
- Add tracked application, appointment, event, notification, and follow-up-token models.
- Confirm session scoping on every new endpoint.
- Add Pydantic validation and migrations/schema creation.

**Exit condition:** The backend can persist a user opt-in, one tracked application, one appointment, and a notification row.

### Phase 2 — Resend test send

- Set up Resend account/API key.
- Verify/configure sender domain or use the permitted development sender for testing.
- Add `resend[async]` to dependencies.
- Implement a small `EmailProvider`/`ResendEmailProvider` adapter.
- Add a test endpoint or controlled development command.
- Send a test message to the team's test inbox.

**Exit condition:** A real test email is received and its Resend message ID is stored.

### Phase 3 — Consent and action-plan email

- Add post-plan email opt-in UI.
- Save email and preferences.
- Implement email preview.
- Require explicit confirmation before initial action-plan send.
- Add disable/opt-out control.

**Exit condition:** User can opt in, preview, send, and disable notifications.

### Phase 4 — Appointment and progress follow-through

- Add appointment creation/update APIs and UI.
- Add pre-appointment reminder scheduling.
- Add secure follow-up token links.
- Add post-appointment follow-up reminder.
- Add structured outcome form.
- Persist event history and update checklist/application state.

**Exit condition:** Appointment can be scheduled, reminder email can be sent, and the user can update the outcome from the email link.

### Phase 5 — Application progress and rejection recovery

- Add tracked application records/status timeline.
- Add status update UI.
- Implement rejection report input and classification.
- Invoke official-source verification and eligibility/planning reassessment as applicable.
- Generate evidence-backed next action or clearly state that no supported remedy was found.
- Generate a government-office email draft when useful; user reviews and sends it.

**Exit condition:** A rejected application causes a grounded investigation and updated plan, not an automatic appeal.

### Phase 6 — Scheduler, demo fast-forward, reliability

- Complete DB-backed due-notification polling.
- Add deduplication/idempotency.
- Add safe demo clock and test recipient override.
- Run the full demo scenario.
- Test failure, restart, cancellation, and opt-out cases.

**Exit condition:** The demo fast-forwards a reminder and delivers a real, clearly labelled email to the test inbox.

### Phase 7 — Optional polish

Only after P0 acceptance criteria pass:

- Resend webhooks for delivery/bounce tracking.
- `.ics` event includes secure follow-up URL.
- Rejection notice upload and parsing.
- More granular reminder preferences and frequency controls.
- WhatsApp Cloud API as a separate future channel.

---

## 15. Suggested team ownership

Keep the existing team split; do not create a separate fifth agent.

| Member | Ownership for these features |
|---|---|
| **Member 1 — Discovery + Action & Follow-through** | Outcome interpretation, rejection analysis orchestration, official recovery-route discovery, alternative scheme discovery, email content generation, government-office email drafts. |
| **Member 2 — Eligibility + Planning** | Verify rejection reason/requirements, reassess eligibility after new information, update document tasks and dependency plan. |
| **Member 3 — Backend / Technical Lead** | SQLite schema, consent enforcement, Resend service adapter, notification scheduler, secure follow-up tokens, APIs, idempotency, demo clock, integration tests. |
| **Member 4 — Frontend** | Follow-through opt-in, email preview/confirmation, My Applications & Progress, appointment update form, rejection recovery display, notification history, demo controls. |

### Parallel implementation contracts

- Member 1 returns structured outcome interpretation and recovery findings with source evidence; it does not call Resend directly.
- Member 2 returns updated assessments/plans with explicit uncertainty and evidence; it does not send notifications.
- Member 3 exposes notification and progress APIs; it does not implement agent reasoning inside route handlers.
- Member 4 consumes the APIs and shows source/status provenance; it does not simulate a successful backend send locally.

---

## 16. Core demo script

Use one coherent student scenario. Avoid trying to demonstrate every possible branch in one uninterrupted presentation.

1. User discovers several potentially relevant schemes.
2. User answers/skips consolidated questions.
3. Unlocked produces an eligibility explanation and document/action plan.
4. User opts into email follow-through after viewing the plan.
5. User previews and confirms the action-plan email.
6. User schedules an appointment related to a required document.
7. Dashboard displays the appointment and scheduled reminder.
8. Demo clock advances to the reminder time.
9. Resend sends a real `[DEMO]` reminder to the team's test inbox.
10. User opens the secure follow-up link and reports that an additional document was requested.
11. Unlocked updates the document checklist and action plan.
12. For the rejection branch, use a separate clearly labelled scenario or a reset state: user reports rejection, Unlocked checks official recovery guidance, and the system either produces a supported correction/clarification path or explains that no remedy is confirmed and offers alternatives.

For the live presentation, show actual email receipt and the updated application/action-plan timeline. Any simulated clock or simulated outcome must be explicitly labelled.

---

## 17. Definition of done for P0

The feature set is P0-complete when all of the following are true:

- [ ] Contact details are not required during onboarding.
- [ ] User can opt into email follow-through after receiving the action plan.
- [ ] Consent and notification preferences are persisted.
- [ ] Resend sends a real action-plan email after preview and confirmation.
- [ ] Appointment and deadline notifications can be scheduled in SQLite.
- [ ] A pre-appointment or deadline reminder can be delivered through Resend.
- [ ] Follow-up email contains a secure link to the relevant update page.
- [ ] User can report appointment outcome from that link.
- [ ] Application/document state and event history update correctly.
- [ ] The next plan is reassessed when new facts or document requirements arrive.
- [ ] Rejection triggers source-grounded investigation.
- [ ] The system does not assume every rejection is appealable.
- [ ] A supported remedy can be turned into a user-reviewed next action/draft.
- [ ] If no remedy is supported, the system communicates uncertainty and can find alternatives.
- [ ] User can disable future email notifications.
- [ ] Demo mode fast-forwards a reminder and sends a real email to the test inbox.
- [ ] No demo email is accidentally sent to a real user's address.
- [ ] No application, appeal, or government-office email is submitted automatically.

---

## 18. Implementation notes and official Resend references

Use the official documentation as the source of truth for SDK/API details because provider interfaces can change.

- Resend Python integration: https://resend.com/python
- Resend Python SDK async support: https://resend.com/changelog/python-sdk-async-support
- Resend email API: https://resend.com/features/email-api
- Resend idempotency keys: https://resend.com/changelog/idempotency-keys
- Resend webhooks: https://resend.com/features/webhooks
- Resend webhook management and verification notes: https://resend.com/changelog/managing-webhooks-via-api

Implementation reminders based on the current Resend documentation:

- The Python SDK supports async methods through `resend[async]`; use the async method in FastAPI handlers/scheduler code.
- Resend supports idempotency keys for email requests. Its documented idempotency window is 24 hours, so also maintain application-level notification deduplication in SQLite.
- Resend webhooks can report email lifecycle events. Verify webhook signatures before trusting them; webhook integration may remain P1 if the P0 schedule is tight.
- A provider API acceptance response is not proof that the email reached the recipient's inbox.

---

## 19. Final product rule

Unlocked's follow-through lifecycle is:

**Discover → Assess → Prepare → Apply → Track → Recover → Resolve.**

The system should not measure success only by how many schemes it discovers. It should help the user identify and complete the next appropriate step, update the plan when circumstances change, and respond responsibly when an application is delayed or rejected.

**A rejection is an investigation trigger, not an automatic terminal state and not an automatic appeal.** Sometimes correction, clarification, grievance, appeal, or reapplication is supported. Sometimes it is not. Unlocked must explain the evidence and uncertainty, let the user decide, and never invent a remedy.
