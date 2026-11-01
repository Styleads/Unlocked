#!/usr/bin/env python3
"""
interactive_cli.py — Interactive Test Interface for Project Unlocked.

Provides a comprehensive, step-by-step interactive CLI to test all four agents
and the central orchestrator:
1. Citizen Profile Setup (Presets or Custom)
2. Scheme Discovery (Live Official Search or Offline Fallback Collection)
3. Dynamic Question Answering & Non-Destructive Skip Reassessment (Agent 2)
4. Topological Document Action Plan DAG with Live Status Updates (Agent 3)
5. Action & Follow-Through Studio: Grounded Emails, .ics Calendars, Progress Tracking (Agent 4)
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table
from rich.text import Text

# Ensure current directory is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env", override=False)

from api.database import (
    create_session,
    get_session,
    init_db,
    add_office_chat_message,
    create_office_chat_session,
    create_unresolved_question,
    get_appointment_preferences,
    get_office_chat_session,
    get_office_contact_by_scheme,
    get_unresolved_question,
    list_office_chat_messages,
    list_unresolved_questions,
    save_appointment_preferences,
    update_office_chat_session,
    update_unresolved_question,
)
from api.orchestrator import (
    analyze_scheme_rejection,
    generate_action_plan,
    generate_calendar_action,
    generate_email_action,
    get_session_questions,
    get_session_schemes,
    process_answers,
    record_application_progress,
    run_discovery,
    update_checklist_status,
)
from api.schemas import (
    AnswerInput,
    EventKind,
    SessionCalendarActionRequest,
    SessionEmailActionRequest,
    SessionRejectionActionRequest,
)
from api.office_simulator import OfficeSimulatorService
from agent4.office_chat_models import (
    AppointmentOffer,
    AppointmentStatus,
    ChatStatus,
    ContactSource,
    OfficeChatMessage,
    OfficeChatSession,
    OfficeContact,
    TimeWindow,
    UnresolvedQuestion,
    UnresolvedQuestionStatus,
    UserAppointmentPreferences,
    VerificationStatus,
)
from agent4.office_chat_agent import (
    build_initial_office_enquiry,
    decide_chat_turn,
    format_whatsapp_click_url,
)
from api.main import _generate_simulated_ics

console = Console()

# ---------------------------------------------------------------------------
# Citizen Demographic Presets
# ---------------------------------------------------------------------------

PRESETS = [
    {
        "name": "Basavaraj Gowda (Farmer, Mandya)",
        "context": {
            "name": "Basavaraj Gowda",
            "occupation": "farmer",
            "state": "Karnataka",
            "district": "Mandya",
            "annual_income": 120000,
            "interests": ["crop insurance", "drip irrigation", "income support"],
            "domicile_karnataka": True,
            "social_category": "OBC",
        },
    },
    {
        "name": "Priyanka Naik (SC Engineering Student, Dharwad)",
        "context": {
            "name": "Priyanka Naik",
            "occupation": "student",
            "state": "Karnataka",
            "district": "Dharwad",
            "annual_income": 180000,
            "education_level": "Undergraduate",
            "course_type": "Engineering",
            "social_category": "SC",
            "interests": ["post-matric scholarship", "fee reimbursement", "hostel subsidy"],
            "domicile_karnataka": True,
        },
    },
    {
        "name": "Syed Farooq (Rural Artisan / Weaver, Ramanagara)",
        "context": {
            "name": "Syed Farooq",
            "occupation": "self-employed",
            "state": "Karnataka",
            "district": "Ramanagara",
            "annual_income": 95000,
            "is_minority": True,
            "interests": ["weaver loan subsidy", "tool kit assistance"],
            "domicile_karnataka": True,
        },
    },
]


def print_banner():
    banner = r"""
[bold cyan]  _   _ _   _ _     ___   ____ _  _______ ____  [/bold cyan]
[bold cyan] | | | | \ | | |   / _ \ / ___| |/ / ____|  _ \ [/bold cyan]
[bold cyan] | | | |  \| | |  | | | | |   | ' /|  _| | | | |[/bold cyan]
[bold cyan] | |_| | |\  | |__| |_| | |___| . \| |___| |_| |[/bold cyan]
[bold cyan]  \___/|_| \_|_____\___/ \____|_|\_\_____|____/ [/bold cyan]
[white]   Karnataka Citizen Benefits & Follow-Through Assistant[/white]
[dim]   Interactive Multi-Agent Testing & Simulation Console[/dim]
"""
    console.print(Panel(banner, border_style="cyan", box=box.ROUNDED))


def format_status(status_str: Optional[str]) -> str:
    if not status_str:
        return "[dim]unknown[/dim]"
    colors = {
        "potential_match": "bold green",
        "more_information_needed": "bold yellow",
        "unlikely_to_match": "bold red",
        "not_yet_verified": "bold blue",
        "uncertain": "bold magenta",
        "verified": "bold green",
        "unverified": "bold red",
        "partially_verified": "bold yellow",
    }
    color = colors.get(status_str.lower(), "white")
    return f"[{color}]{status_str.replace('_', ' ').upper()}[/{color}]"


# ---------------------------------------------------------------------------
# Step 1: Profile Initialization
# ---------------------------------------------------------------------------

async def setup_citizen_profile() -> tuple[str, dict[str, Any]]:
    console.print("\n[bold cyan]══ STEP 1: Citizen Profile Setup ══[/bold cyan]")
    console.print("Choose how to configure the citizen demographic context:\n")

    for idx, preset in enumerate(PRESETS, start=1):
        ctx = preset["context"]
        console.print(f"  [bold cyan]{idx}[/bold cyan]. [white]{preset['name']}[/white]")
        console.print(f"     [dim]Occupation: {ctx.get('occupation')}, District: {ctx.get('district')}, Income: ₹{ctx.get('annual_income'):,}[/dim]")

    console.print(f"  [bold cyan]{len(PRESETS) + 1}[/bold cyan]. [white]Create Custom Citizen Profile[/white]\n")

    choice = IntPrompt.ask(
        "Select citizen profile option",
        default=1,
        choices=[str(i) for i in range(1, len(PRESETS) + 2)],
    )

    if choice <= len(PRESETS):
        selected = PRESETS[choice - 1]
        context = selected["context"]
        console.print(f"\n[green]✓ Selected preset:[/green] {selected['name']}")
    else:
        console.print("\n[bold]Enter Custom Citizen Details:[/bold]")
        name = Prompt.ask("Citizen Full Name", default="Ramesh Kumar")
        occupation = Prompt.ask("Occupation (farmer, student, self-employed, unemployed, artisan)", default="farmer")
        state = Prompt.ask("State", default="Karnataka")
        district = Prompt.ask("District (e.g., Mandya, Dharwad, Mysuru, Bengaluru)", default="Mandya")
        income = IntPrompt.ask("Approximate Annual Family Income (INR)", default=150000)
        social_cat = Prompt.ask("Social Category (General, OBC, SC, ST)", default="OBC")
        interests_str = Prompt.ask("Interests (comma-separated)", default="crop insurance, financial assistance")
        interests = [s.strip() for s in interests_str.split(",") if s.strip()]

        context = {
            "name": name,
            "occupation": occupation,
            "state": state,
            "district": district,
            "annual_income": income,
            "social_category": social_cat,
            "interests": interests,
            "domicile_karnataka": (state.lower() == "karnataka"),
        }

    # Summary table
    table = Table(title="Citizen Profile Initialized", box=box.ROUNDED)
    table.add_column("Attribute", style="cyan")
    table.add_column("Value", style="white")
    for k, v in context.items():
        table.add_row(k, str(v))
    console.print(table)

    session_id = str(uuid.uuid4())
    session = await create_session(session_id=session_id, context=context, scope="guided", preferred_language="en")
    console.print(f"[dim]Persisted session to SQLite: {session.session_id}[/dim]")
    return session.session_id, context


# ---------------------------------------------------------------------------
# Step 2: Discovery Execution
# ---------------------------------------------------------------------------

async def execute_discovery(session_id: str) -> list[Any]:
    console.print("\n[bold cyan]══ STEP 2: Scheme Discovery Pipeline (Agent 1) ══[/bold cyan]")
    
    has_gemini = bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
    has_tavily = bool(os.getenv("TAVILY_API_KEY"))

    console.print(f"API Key Status:")
    console.print(f"  • Google Gemini: {'[green]Configured[/green]' if has_gemini else '[yellow]Not configured (offline fallback available)[/yellow]'}")
    console.print(f"  • Tavily Search: {'[green]Configured[/green]' if has_tavily else '[yellow]Not configured (offline fallback available)[/yellow]'}")

    console.print("\nDiscovery Mode Options:")
    console.print("  [bold cyan]1[/bold cyan]. Offline Fallback Collection (Fast, 0 API quota, 5 verified Karnataka schemes)")
    console.print("  [bold cyan]2[/bold cyan]. Live Official Web Search (Tavily restricted to .gov.in + Gemini Flash extraction)")

    default_mode = "2" if (has_gemini and has_tavily) else "1"
    mode_choice = Prompt.ask("Choose discovery mode", choices=["1", "2"], default=default_mode)

    search_scope = "fallback" if mode_choice == "1" else "guided"

    with console.status("[bold cyan]Executing Discovery Agent & Compliance Adapter...[/bold cyan]", spinner="dots"):
        result = await run_discovery(
            session_id=session_id,
            search_scope=search_scope,
            preferred_language="en",
            enable_fallback=True,
        )

    schemes = await get_session_schemes(session_id)
    console.print(f"\n[green]✓ Discovery complete![/green] Found [bold]{len(schemes)}[/bold] schemes (Source Mode: [bold cyan]{result.source_mode}[/bold cyan]):\n")

    if result.diagnostics:
        diag = result.diagnostics
        diag_lines = [
            f"• Search Queries Generated: [bold]{diag.get('search_queries_count', 0)}[/bold]",
            f"• Search Results Retrieved: [bold]{diag.get('search_results_retrieved', 0)}[/bold] (Unique: [bold]{diag.get('unique_results_count', 0)}[/bold])",
            f"• Schemes Extracted: [bold]{diag.get('schemes_extracted_count', 0)}[/bold]",
            f"• Validation Failures: [bold]{diag.get('schemes_validation_failed_count', 0)}[/bold]",
            f"• Duplicates Removed: [bold]{diag.get('schemes_duplicates_removed_count', 0)}[/bold]",
            f"• Claims Verified: [bold green]{diag.get('claims_verified_count', 0)}[/bold green]",
            f"• Final Schemes Available: [bold cyan]{diag.get('final_schemes_count', len(schemes))}[/bold cyan]",
        ]
        console.print(Panel(
            "\n".join(diag_lines),
            title="[bold cyan]Discovery Pipeline Diagnostics[/bold cyan]",
            box=box.ROUNDED,
            border_style="cyan"
        ))
        console.print()

    table = Table(box=box.ROUNDED, expand=True)
    table.add_column("#", justify="center", width=4)
    table.add_column("Scheme Title", style="bold white", width=34)
    table.add_column("Department / Level", style="dim", width=22)
    table.add_column("Initial Status", width=20)
    table.add_column("Deadline", width=18)
    table.add_column("Benefit", width=30)

    for idx, s in enumerate(schemes, start=1):
        status_disp = format_status(s.assessment_status)
        dept = s.department or s.government_level or "Karnataka"
        benefit = str(s.benefit or "Official welfare benefit")
        if getattr(s, "deadline_status", "") == "expired":
            deadline_disp = f"[bold red]EXPIRED ({s.deadline})[/bold red]"
        elif s.deadline:
            deadline_disp = f"[bold yellow]{s.deadline}[/bold yellow]"
        else:
            deadline_disp = "[dim]Not published[/dim]"
        table.add_row(str(idx), s.name, dept, status_disp, deadline_disp, benefit)

    console.print(table)
    return schemes


# ---------------------------------------------------------------------------
# Step 3: Question Answering & Reassessment
# ---------------------------------------------------------------------------

async def interactive_questionnaire(session_id: str):
    console.print("\n[bold cyan]══ STEP 3: Consolidated Questionnaire & Reassessment (Agent 2) ══[/bold cyan]")
    console.print("[dim]Agent 2 analyzes all candidate schemes, excludes known context answers, and ranks questions by information gain.[/dim]\n")

    question_counter = 1
    batch_idx = 1
    while True:
        questions = await get_session_questions(session_id)
        if not questions:
            console.print("[green]✓ No further questions needed for the current candidate schemes![/green]")
            break

        console.print(f"\n[bold cyan]══ QUESTION BATCH {batch_idx} ══[/bold cyan]")
        console.print(f"[bold yellow]Questions in this batch: {len(questions)}[/bold yellow]\n")

        for q_pos, q in enumerate(questions, start=1):
            console.print(Panel(
                f"[bold white]{question_counter}. {q.question}[/bold white]\n\n"
                f"[dim cyan]Attribute ID:[/dim cyan] {q.attribute}\n"
                f"[dim cyan]Why Asked:[/dim cyan] {q.why_asked}\n"
                f"[dim cyan]Candidate Schemes Impacted:[/dim cyan] {', '.join(q.related_scheme_ids) or 'Multiple'}\n"
                f"[dim cyan]Can Skip:[/dim cyan] Yes (type 's' to skip or 'u' for not sure)\n"
                f"[dim cyan]Batch Progress:[/dim cyan] Question {q_pos} of {len(questions)}",
                border_style="yellow",
                box=box.ROUNDED,
            ))
            question_counter += 1

            console.print("[bold]How would you like to answer?[/bold]")
            answer_val = None
            answer_state = "answered"

            if q.input_type.value == "boolean":
                console.print("  [1] Yes (True)")
                console.print("  [2] No (False)")
                console.print("  [s] Skip this question")
                console.print("  [u] Not sure / Unknown")
                console.print("  [p] Prefer not to answer")
                ans_choice = Prompt.ask("Your answer", choices=["1", "2", "s", "u", "p"], default="1")
                if ans_choice == "1":
                    answer_val = True
                elif ans_choice == "2":
                    answer_val = False
                elif ans_choice == "s":
                    answer_state = "skipped"
                elif ans_choice == "u":
                    answer_state = "unknown"
                elif ans_choice == "p":
                    answer_state = "prefer_not_to_answer"

            elif q.input_type.value == "select" and q.options:
                for opt_idx, opt in enumerate(q.options, start=1):
                    console.print(f"  [{opt_idx}] {opt}")
                console.print("  [s] Skip")
                console.print("  [u] Not sure / Unknown")
                console.print("  [p] Prefer not to answer")
                choices = [str(i) for i in range(1, len(q.options) + 1)] + ["s", "u", "p"]
                ans_choice = Prompt.ask("Your choice", choices=choices, default="1")
                if ans_choice in ["s", "u", "p"]:
                    answer_state = {"s": "skipped", "u": "unknown", "p": "prefer_not_to_answer"}[ans_choice]
                else:
                    answer_val = q.options[int(ans_choice) - 1]

            elif q.input_type.value in ("number", "range"):
                if q.ranges:
                    console.print("Select income range band:")
                    for r_idx, r in enumerate(q.ranges, start=1):
                        console.print(f"  [{r_idx}] {r.label}")
                    console.print("  [c] Enter custom numeric amount")
                    console.print("  [s] Skip")
                    console.print("  [u] Not sure")
                    r_choices = [str(i) for i in range(1, len(q.ranges) + 1)] + ["c", "s", "u"]
                    ans_choice = Prompt.ask("Choice", choices=r_choices, default="1")
                    if ans_choice in ["s", "u"]:
                        answer_state = "skipped" if ans_choice == "s" else "unknown"
                    elif ans_choice == "c":
                        num = IntPrompt.ask("Enter amount in INR")
                        answer_val = num
                    else:
                        selected_range = q.ranges[int(ans_choice) - 1]
                        answer_val = {"min": selected_range.min, "max": selected_range.max}
                else:
                    raw_val = Prompt.ask("Enter numeric value (or 's' to skip, 'u' for unknown)", default="s")
                    if raw_val.lower() in ("s", "skip"):
                        answer_state = "skipped"
                    elif raw_val.lower() in ("u", "unknown", "not sure"):
                        answer_state = "unknown"
                    else:
                        try:
                            answer_val = float(raw_val)
                        except ValueError:
                            answer_val = raw_val
            else:
                raw_val = Prompt.ask("Enter value (or 's' to skip, 'u' for unknown)", default="s")
                if raw_val.lower() in ("s", "skip"):
                    answer_state = "skipped"
                elif raw_val.lower() in ("u", "unknown"):
                    answer_state = "unknown"
                else:
                    answer_val = raw_val

            # Submit answer immediately to trigger live dynamic reassessment
            with console.status(f"[bold cyan]Submitting answer for {q.attribute} and re-evaluating schemes...[/bold cyan]", spinner="dots"):
                reassessment = await process_answers(
                    session_id=session_id,
                    submitted_answers=[
                        AnswerInput(attribute=q.attribute, value=answer_val, state=answer_state)
                    ],
                )

            console.print(f"[green]✓ Answer recorded:[/green] state={answer_state}, stored_value={answer_val}\n")

            # Show reassessment overview table
            schemes = await get_session_schemes(session_id)
            re_table = Table(title=f"Reassessment Status After Answering '{q.attribute}'", box=box.SIMPLE_HEAD)
            re_table.add_column("Scheme", style="white")
            re_table.add_column("Updated Status", justify="center")
            re_table.add_column("Reason / Explanation", style="dim")

            for s in schemes:
                re_table.add_row(s.name, format_status(s.assessment_status), (s.assessment_explanation or "")[:70] + "...")
            console.print(re_table)

            if q_pos < len(questions):
                if not Confirm.ask("\nProceed to the next question?", default=True):
                    break

        batch_idx += 1
        # Check if user wants another batch
        remaining = await get_session_questions(session_id)
        if remaining:
            if not Confirm.ask(f"\nThere are {len(remaining)} more questions. Would you like to continue answering?", default=True):
                break
        else:
            break


# ---------------------------------------------------------------------------
# Step 4: Document Action Plan DAG (Agent 3)
# ---------------------------------------------------------------------------

async def interactive_action_plan(session_id: str):
    console.print("\n[bold cyan]══ STEP 4: Topological Document Action Plan DAG (Agent 3) ══[/bold cyan]")
    console.print("[dim]Agent 3 constructs a dependency graph of all required certificates and uses Kahn's topological sort.[/dim]\n")

    while True:
        with console.status("[bold cyan]Computing Action Plan DAG...[/bold cyan]", spinner="dots"):
            plan = await generate_action_plan(session_id)

        console.print(f"[bold green]Topological Action Plan Summary:[/bold green]")
        console.print(f"[white]{plan.explanation}[/white]\n")

        if plan.shared_prerequisites:
            console.print(Panel(
                f"[bold yellow]★ High-Leverage Shared Prerequisites:[/bold yellow]\n"
                f"These documents unlock 2 or more schemes simultaneously: [bold cyan]{', '.join(plan.shared_prerequisites)}[/bold cyan]\n"
                f"[dim]Obtaining these first gives the highest civic return on effort.[/dim]",
                border_style="yellow",
            ))

        # Checklist table
        table = Table(title="Prioritized Procurement Checklist", box=box.ROUNDED)
        table.add_column("Seq #", justify="center", width=6)
        table.add_column("Document Name", style="bold white", width=30)
        table.add_column("Current Status", width=14)
        table.add_column("Prerequisites", style="dim", width=22)
        table.add_column("Required By Schemes", style="dim")

        for item in plan.checklist:
            status_style = {
                "have": "[green]HAVE[/green]",
                "obtained": "[cyan]OBTAINED[/cyan]",
                "needed": "[bold yellow]NEEDED[/bold yellow]",
                "unknown": "[dim]UNKNOWN[/dim]",
            }.get(item.status.value, item.status.value)

            table.add_row(
                str(item.order),
                item.name,
                status_style,
                ", ".join(item.dependencies) or "None",
                ", ".join(item.required_by_scheme_ids),
            )

        console.print(table)

        console.print("\n[bold]Document Management Options:[/bold]")
        console.print("  [bold cyan]1[/bold cyan]. Toggle a document status (Mark as 'have' or 'obtained' to recompute DAG)")
        console.print("  [bold cyan]2[/bold cyan]. View DAG Graph Nodes & Sourced Edges")
        console.print("  [bold cyan]3[/bold cyan]. Proceed to Action & Follow-Through (Agent 4)")

        doc_choice = Prompt.ask("Choose option", choices=["1", "2", "3"], default="3")

        if doc_choice == "1":
            doc_options = {str(i): item for i, item in enumerate(plan.checklist, start=1)}
            for k, it in doc_options.items():
                console.print(f"  [{k}] {it.name} (Current: {it.status.value})")
            picked = Prompt.ask("Select document number to update", choices=list(doc_options.keys()))
            target_doc = doc_options[picked]

            new_status = Prompt.ask(
                f"Set status for '{target_doc.name}'",
                choices=["have", "obtained", "needed", "unknown"],
                default="have",
            )

            await update_checklist_status(session_id=session_id, doc_id=target_doc.id, status=new_status)
            console.print(f"[green]✓ Updated '{target_doc.name}' to '{new_status}'! Recomputing DAG...[/green]\n")
        elif doc_choice == "2":
            edge_table = Table(title="Sourced Dependency Graph Edges", box=box.SIMPLE)
            edge_table.add_column("Source", style="cyan")
            edge_table.add_column("Relation", style="dim")
            edge_table.add_column("Target", style="white")
            edge_table.add_column("Official Source Evidence URL", style="blue")
            for e in plan.edges:
                edge_table.add_row(e.source, e.relation, e.target, e.source_url)
            console.print(edge_table)
            Prompt.ask("\nPress Enter to return to Document Plan menu")
        else:
            break


# ---------------------------------------------------------------------------
# Office Chat Simulator (WhatsApp-Style Demo)
# ---------------------------------------------------------------------------

async def interactive_office_chat_simulation(session_id: str) -> None:
    console.print("\n[bold green]══ IN-WEBSITE OFFICE CHAT SIMULATOR (WhatsApp-Style Demo) ══[/bold green]")
    console.print("[yellow bold]⚠️  [SIMULATION DEMO ONLY] In-website simulation. Zero PII shared. No actual office contacted.[/yellow bold]\n")

    schemes = await get_session_schemes(session_id)
    if not schemes:
        console.print("[yellow]No schemes available in session. Please run discovery first.[/yellow]")
        return

    console.print("Select target scheme to enquire about:")
    for idx, s in enumerate(schemes, start=1):
        dept = getattr(s, "department", "Welfare Department") or "Welfare Department"
        console.print(f"  [{idx}] [bold]{s.name}[/bold] ({dept})")
    s_idx = IntPrompt.ask("Scheme", default=1, choices=[str(i) for i in range(1, len(schemes) + 1)])
    target_scheme = schemes[s_idx - 1]

    # Office details from scheme or database or fallback
    office = getattr(target_scheme, "office_contact", None)
    if not office:
        office = await get_office_contact_by_scheme(target_scheme.id)
    if not office:
        office = OfficeContact(
            office_name=f"{target_scheme.name} Helpdesk & Taluk Office",
            physical_address="Taluk Office Complex, Mini Vidhana Soudha, Bengaluru, Karnataka 560001",
            phone="+91-80-22221111",
            whatsapp_number="+918022221111",
            email="helpdesk.schemes@karnataka.gov.in",
            office_hours={"monday": {"open": "10:00", "close": "17:30"}, "friday": {"open": "10:00", "close": "17:30"}},
            contact_source=ContactSource.curated_directory,
            verification_status=VerificationStatus.verified,
        )

    # Display Office Card
    console.print(Panel(
        f"[bold cyan]Office:[/bold cyan] {office.office_name}\n"
        f"[bold cyan]Address:[/bold cyan] {office.physical_address or 'Taluk Administrative Office'}\n"
        f"[bold cyan]Phone:[/bold cyan] {office.phone or 'Not listed'}\n"
        f"[bold cyan]WhatsApp Desk:[/bold cyan] {office.whatsapp_number or 'Not listed'}\n"
        f"[bold cyan]Working Hours:[/bold cyan] Mon-Fri 10:00 - 17:30 IST",
        title=f"🏛️ {target_scheme.name} — Official Office Contact",
        border_style="cyan",
        box=box.ROUNDED,
    ))

    # Scenario Selection
    console.print("\n[bold]Select Simulation Scenario:[/bold]")
    console.print("  [bold cyan]1[/bold cyan]. Scenario A: Standard Slot Booking (Representative offers in-range slot ➔ Confirmed)")
    console.print("  [bold cyan]2[/bold cyan]. Scenario B: No Availability in Requested Window (Representative offers alternate slot)")
    console.print("  [bold cyan]3[/bold cyan]. Scenario C: Missing Info / Clarification (Representative asks info ➔ WhatsApp handoff)")
    console.print("  [bold cyan]4[/bold cyan]. Scenario D: Unsupported Channel (Office does not process chat appointments)")

    sc_choice = Prompt.ask("Scenario", choices=["1", "2", "3", "4"], default="1")
    sc_map = {
        "1": "scenario_a_success",
        "2": "scenario_b_no_slots",
        "3": "scenario_c_clarification",
        "4": "scenario_d_unclear_unsupported",
    }
    scenario_id = sc_map[sc_choice]

    pre_auth = Confirm.ask("Enable pre-authorized auto-confirmation (instantly accept slots matching preferences)?", default=True)

    prefs = UserAppointmentPreferences(
        preferred_days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
        preferred_windows=[TimeWindow(start="10:00", end="13:00"), TimeWindow(start="14:00", end="17:00")],
        notes="Citizen prefers morning appointment for document verification",
        pre_authorized_confirmation=pre_auth,
    )
    await save_appointment_preferences(session_id, prefs)

    chat_id = f"sim_{uuid.uuid4().hex[:8]}"
    chat_session = OfficeChatSession(
        chat_id=chat_id,
        session_id=session_id,
        scheme_id=target_scheme.id,
        office_id=office.office_id if office else None,
        scenario_id=scenario_id,
        chat_status=ChatStatus.active,
        appointment_status=AppointmentStatus.requested,
        preferences=prefs,
    )
    await create_office_chat_session(chat_session)

    # Turn 1: Initial Advocate Message
    initial_text = build_initial_office_enquiry(
        scheme_name=target_scheme.name,
        office_name=office.office_name,
        user_preferences=prefs,
    )
    m1 = OfficeChatMessage(
        chat_id=chat_id,
        sender="unlocked",
        message_text=initial_text,
        turn_index=1,
    )
    await add_office_chat_message(m1)

    console.print("\n" + "─"*65)
    console.print(f"[bold green]💬 WhatsApp Simulator Active • Scheme: {target_scheme.name}[/bold green]")
    console.print("[dim]Simulation Demo Only • Zero-PII Boundary • No Actual Office Contacted[/dim]")
    console.print("─"*65 + "\n")

    console.print(Panel(
        f"{m1.message_text}\n\n[dim]10:00 AM • Sent by Unlocked Citizen Advocate • Zero-PII Enforced[/dim]",
        title="[bold green]📱 Unlocked Citizen Advocate[/bold green]",
        border_style="green",
        box=box.ROUNDED,
    ))

    # Turn 2: Representative reply
    sim_service = OfficeSimulatorService()
    turn_2_res = sim_service.process_turn(
        scenario_id=scenario_id,
        turn_index=2,
        assistant_message=m1.message_text,
        preferences=prefs,
        office=office,
    )
    m2 = OfficeChatMessage(
        chat_id=chat_id,
        sender="representative",
        message_text=turn_2_res.message,
        turn_index=2,
    )
    await add_office_chat_message(m2)

    console.print(Panel(
        f"{m2.message_text}\n\n[dim]10:01 AM • Received from {office.office_name}[/dim]",
        title=f"[bold blue]🏛️ {office.office_name}[/bold blue]",
        border_style="blue",
        box=box.ROUNDED,
    ))

    # Turn 3: Assistant / Citizen Advocate decision
    history = [m1, m2]
    asst_turn_3 = await decide_chat_turn(
        chat_history=history,
        preferences=prefs,
        scheme=target_scheme,
        office=office,
        representative_slot=turn_2_res.offered_slot,
        scenario_id=scenario_id,
    )

    user_approved_slot = None
    if asst_turn_3.appointment_offer:
        offered = asst_turn_3.appointment_offer
        if not prefs.pre_authorized_confirmation:
            console.print(Panel(
                f"[bold yellow]Proposed Appointment Slot:[/bold yellow]\n"
                f"  📅 Date: {offered.date}\n"
                f"  ⏰ Time: {offered.time}\n"
                f"  📍 Location: {offered.location or office.physical_address}\n\n"
                f"[italic]Pre-authorization is OFF. Review and confirm before scheduling.[/italic]",
                title="⚠️ Citizen Approval Required",
                border_style="yellow",
                box=box.ROUNDED,
            ))
            approved = Confirm.ask("Do you want to accept and confirm this simulated slot?", default=True)
            if approved:
                user_approved_slot = offered
                asst_turn_3.appointment_status = AppointmentStatus.simulated_confirmed
                asst_turn_3.reply_message = (
                    f"Thank you. The citizen confirms the appointment on {offered.date} at {offered.time}. "
                    "We will arrive with all required documents."
                )
            else:
                asst_turn_3.appointment_status = AppointmentStatus.offered
                asst_turn_3.reply_message = (
                    "Thank you. The citizen cannot make that timing. Could you please propose another date next week?"
                )

    m3 = OfficeChatMessage(
        chat_id=chat_id,
        sender="unlocked",
        message_text=asst_turn_3.reply_message,
        turn_index=3,
    )
    await add_office_chat_message(m3)

    console.print(Panel(
        f"{m3.message_text}\n\n[dim]10:02 AM • Sent by Unlocked Citizen Advocate[/dim]",
        title="[bold green]📱 Unlocked Citizen Advocate[/bold green]",
        border_style="green",
        box=box.ROUNDED,
    ))

    # Turn 4: Representative concluding reply
    turn_4_res = sim_service.process_turn(
        scenario_id=scenario_id,
        turn_index=4,
        assistant_message=m3.message_text,
        preferences=prefs,
        office=office,
    )
    m4 = OfficeChatMessage(
        chat_id=chat_id,
        sender="representative",
        message_text=turn_4_res.message,
        turn_index=4,
    )
    await add_office_chat_message(m4)

    console.print(Panel(
        f"{m4.message_text}\n\n[dim]10:03 AM • Received from {office.office_name}[/dim]",
        title=f"[bold blue]🏛️ {office.office_name}[/bold blue]",
        border_style="blue",
        box=box.ROUNDED,
    ))

    # Conclude session and update records
    chat_session.chat_status = ChatStatus.completed
    if asst_turn_3.appointment_offer and (prefs.pre_authorized_confirmation or user_approved_slot):
        chat_session.appointment_status = AppointmentStatus.simulated_confirmed
        chat_session.appointment = asst_turn_3.appointment_offer
    elif scenario_id == "scenario_b_no_slots":
        chat_session.appointment_status = AppointmentStatus.no_availability
    elif scenario_id == "scenario_d_unclear_unsupported":
        chat_session.chat_status = ChatStatus.unable_to_resolve
        chat_session.appointment_status = AppointmentStatus.not_requested
    await update_office_chat_session(chat_session)

    # Unresolved question handling (Scenario C)
    if asst_turn_3.unresolved_question or turn_2_res.receiver_whatsapp_number or turn_2_res.requested_info:
        q_text = asst_turn_3.unresolved_question or turn_2_res.requested_info or "Clarification required on supporting documents"
        wa_target = turn_2_res.receiver_whatsapp_number or office.whatsapp_number or "+918022221111"
        draft = f"Namaskara, regarding {target_scheme.name}: I need clarification on {q_text}."
        click_url = format_whatsapp_click_url(wa_target, draft)

        uq = UnresolvedQuestion(
            session_id=session_id,
            chat_id=chat_id,
            scheme_id=target_scheme.id,
            question_text=q_text,
            status=UnresolvedQuestionStatus.draft_prepared,
            receiver_whatsapp_number=wa_target,
            draft_message=draft,
            click_to_chat_url=click_url,
        )
        await create_unresolved_question(uq)

        console.print(Panel(
            f"[bold yellow]Unresolved Question Logged for Citizen Follow-up:[/bold yellow]\n\n"
            f"[bold cyan]Missing Information:[/bold cyan] {q_text}\n"
            f"[bold cyan]Representative WhatsApp Desk:[/bold cyan] {wa_target}\n"
            f"[bold cyan]Prepared Follow-Up Draft Message:[/bold cyan]\n  \"{draft}\"\n\n"
            f"[bold green]Click-to-Chat Direct URL:[/bold green]\n  {click_url}\n\n"
            f"[dim]The citizen can review and tap this URL to launch WhatsApp with the pre-filled message.[/dim]",
            title="📋 WhatsApp Direct Follow-Up Handoff Prepared",
            border_style="yellow",
            box=box.ROUNDED,
        ))

    # Confirmed Appointment -> ICS calendar download
    if chat_session.appointment_status == AppointmentStatus.simulated_confirmed and chat_session.appointment:
        ics_text = _generate_simulated_ics(target_scheme, chat_session.appointment)
        if ics_text:
            chat_session.appointment.calendar_ics = ics_text
            await update_office_chat_session(chat_session)

            console.print(Panel(
                f"[bold green]✓ Simulated In-Person Appointment Confirmed![/bold green]\n\n"
                f"  📅 Date: {chat_session.appointment.date}\n"
                f"  ⏰ Time: {chat_session.appointment.time}\n"
                f"  📍 Location: {chat_session.appointment.location or office.physical_address}\n"
                f"  🏷️ Watermark: [SIMULATION DEMO ONLY]\n\n"
                f"[dim]RFC 5545 .ics Calendar File Ready for Download.[/dim]",
                title="🗓️ Calendar Event Generated",
                border_style="green",
                box=box.ROUNDED,
            ))

            if Confirm.ask("Save simulated calendar invite (.ics) to disk?", default=True):
                ics_path = PROJECT_ROOT / f"simulated_appointment_{chat_id}.ics"
                ics_path.write_text(ics_text, encoding="utf-8")
                console.print(f"[green]✓ Saved invite to {ics_path}![/green]")

    console.print(f"\n[bold green]✓ Simulation completed (Session: {session_id}, Chat: {chat_id})[/bold green]\n")


# ---------------------------------------------------------------------------
# Step 5: Action & Follow-Through Studio (Agent 4)
# ---------------------------------------------------------------------------

async def interactive_action_studio(session_id: str):
    console.print("\n[bold cyan]══ STEP 5: Action & Follow-Through Studio (Agent 4) ══[/bold cyan]")
    console.print("[dim]Guardrail: Unlocked generates user-reviewed artifacts only (never autonomously submits or sends).[/dim]\n")

    schemes = await get_session_schemes(session_id)
    if not schemes:
        console.print("[yellow]No schemes available in session.[/yellow]")
        return

    while True:
        console.print("\n[bold]Select an Action to Test:[/bold]")
        console.print("  [bold cyan]1[/bold cyan]. Draft Official Inquiry / Clarification Email (Tokenized PII + Sourced Facts)")
        console.print("  [bold cyan]2[/bold cyan]. Generate RFC 5545 Calendar .ics File (Application Deadline or In-Person Appointment)")
        console.print("  [bold cyan]3[/bold cyan]. Record Application Progress & Contradiction Detection")
        console.print("  [bold cyan]4[/bold cyan]. Analyze Scheme Rejection Notice (Redaction + Official Guidance Next Steps)")
        console.print("  [bold cyan]5[/bold cyan]. Office Chat Simulator (WhatsApp-Style Demo, Scenarios A-D, Zero-PII, Slot Booking)")
        console.print("  [bold cyan]6[/bold cyan]. Exit Interactive Test Interface")

        choice = Prompt.ask("Select action", choices=["1", "2", "3", "4", "5", "6"], default="1")

        if choice == "1":
            # Email draft
            console.print("\nSelect target scheme:")
            for idx, s in enumerate(schemes, start=1):
                console.print(f"  [{idx}] {s.name}")
            s_idx = IntPrompt.ask("Scheme", default=1, choices=[str(i) for i in range(1, len(schemes) + 1)])
            target_scheme = schemes[s_idx - 1]

            purpose = Prompt.ask("Email Purpose", choices=["clarification", "document_query", "deadline_inquiry"], default="clarification")
            question = Prompt.ask("Citizen Question", default="Does my family income certificate from Nadakacheri count for this scheme?")

            with console.status("[bold cyan]Generating grounded email draft...[/bold cyan]", spinner="dots"):
                req = SessionEmailActionRequest(
                    scheme_id=target_scheme.id,
                    purpose=purpose,
                    question=question,
                    attributes=["annual_family_income", "domicile_karnataka"],
                )
                artifact = await generate_email_action(session_id=session_id, request=req)

            console.print(Panel(
                f"[bold green]Artifact Generated: {artifact.title}[/bold green] (by {artifact.generated_by})\n\n"
                f"[bold cyan]Subject:[/bold cyan] {artifact.subject}\n"
                f"[bold cyan]Recipient:[/bold cyan] {artifact.target_destination or '[placeholder — verify on official site]'}\n\n"
                f"{artifact.body_content}\n\n"
                f"[dim]Instructions: {artifact.instructions}[/dim]",
                border_style="green",
                box=box.ROUNDED,
            ))
            if artifact.warnings:
                for w in artifact.warnings:
                    console.print(f"[yellow]⚠️ Warning: {w}[/yellow]")

        elif choice == "2":
            # Calendar
            console.print("\nSelect target scheme:")
            for idx, s in enumerate(schemes, start=1):
                console.print(f"  [{idx}] {s.name}")
            s_idx = IntPrompt.ask("Scheme", default=1, choices=[str(i) for i in range(1, len(schemes) + 1)])
            target_scheme = schemes[s_idx - 1]

            default_kind = "deadline" if target_scheme.deadline else "appointment"
            kind_str = Prompt.ask("Event Kind", choices=["appointment", "deadline"], default=default_kind)
            kind = EventKind.appointment if kind_str == "appointment" else EventKind.deadline
            default_date = target_scheme.deadline or "2026-11-20"
            event_date = Prompt.ask("Event Date (YYYY-MM-DD)", default=default_date)

            start_time = None
            location = None
            if kind == EventKind.appointment:
                start_time = Prompt.ask("Start Time (HH:MM:SS)", default="10:30:00")
                location = Prompt.ask("Appointment Location", default="Taluk Office / Raitha Samparka Kendra")

            with console.status("[bold cyan]Generating RFC 5545 calendar event in Asia/Kolkata...[/bold cyan]", spinner="dots"):
                cal_req = SessionCalendarActionRequest(
                    scheme_id=target_scheme.id,
                    kind=kind,
                    event_date=event_date,
                    date_confirmed_by_user=True,
                    start_time=start_time,
                    location=location,
                )
                cal_artifact = await generate_calendar_action(session_id=session_id, request=cal_req)

            console.print(Panel(
                f"[bold green]{cal_artifact.title}[/bold green]\n"
                f"[dim]Status: {cal_artifact.status.value} | Filename: {cal_artifact.filename}[/dim]\n\n"
                f"{cal_artifact.body_content}",
                border_style="cyan",
                box=box.ROUNDED,
            ))

            save_file = Confirm.ask(f"Save '{cal_artifact.filename}' to disk?", default=True)
            if save_file:
                out_path = PROJECT_ROOT / (cal_artifact.filename or "event.ics")
                out_path.write_text(cal_artifact.body_content, encoding="utf-8")
                console.print(f"[green]✓ Saved to {out_path}![/green]")

        elif choice == "3":
            # Progress Tracking
            console.print("\nSelect target scheme:")
            for idx, s in enumerate(schemes, start=1):
                console.print(f"  [{idx}] {s.name}")
            s_idx = IntPrompt.ask("Scheme", default=1, choices=[str(i) for i in range(1, len(schemes) + 1)])
            target_scheme = schemes[s_idx - 1]

            console.print("Report lifecycle updates for this scheme:")
            submitted = Prompt.ask("Application submitted?", choices=["yes", "no", "unknown"], default="yes")
            decision = Prompt.ask("Decision received?", choices=["approved", "rejected", "pending", "unknown"], default="approved")
            benefit = Prompt.ask("Benefit actually received (money/kit)?", choices=["yes", "no", "unknown"], default="unknown")

            updates = [
                {"field": "submitted", "state": submitted},
                {"field": "decision", "state": decision},
                {"field": "benefit_received", "state": benefit},
            ]

            prog_res = await record_application_progress(
                session_id=session_id,
                scheme_id=target_scheme.id,
                updates=updates,
            )

            console.print(Panel(
                f"[bold white]Progress Summary: {prog_res.summary}[/bold white]\n\n"
                f"[bold cyan]Lifecycle Facts Recorded:[/bold cyan]\n"
                + "\n".join(f"  • {k}: {v.state} (reported: {v.recorded_at})" for k, v in prog_res.progress.items()),
                border_style="green",
            ))

            if prog_res.warnings:
                for w in prog_res.warnings:
                    console.print(f"[bold red]⚠️ Contradiction Warning: {w}[/bold red]")

            if prog_res.follow_ups:
                console.print("\n[bold yellow]Automated Follow-up Questions Triggered:[/bold yellow]")
                for fu in prog_res.follow_ups:
                    console.print(f"  ? {fu.question} (Options: {fu.options})")

        elif choice == "4":
            # Rejection Analysis
            console.print("\nSelect target scheme:")
            for idx, s in enumerate(schemes, start=1):
                console.print(f"  [{idx}] {s.name}")
            s_idx = IntPrompt.ask("Scheme", default=1, choices=[str(i) for i in range(1, len(schemes) + 1)])
            target_scheme = schemes[s_idx - 1]

            notice_sample = (
                "Your application for SSP Scholarship has been rejected. "
                "Applicant Aadhaar: 1234-5678-9012. Phone: +91 9876543210. "
                "Reason: Income certificate RD00392819 expired before verification cut-off."
            )
            console.print(f"\nDefault sample rejection notice:\n[dim]\"{notice_sample}\"[/dim]")
            use_sample = Confirm.ask("Use sample rejection notice?", default=True)

            if use_sample:
                notice_text = notice_sample
            else:
                notice_text = Prompt.ask("Paste official rejection notice text")

            guidance_passages = [
                {
                    "text": "Applicants whose application is rejected due to expired certificates may upload a renewed certificate within 15 days of notice on the Nadakacheri/SSP portal.",
                    "source_url": "https://ssp.postmatric.karnataka.gov.in/guidelines#appeals",
                }
            ]

            with console.status("[bold cyan]Analyzing rejection notice with PII redaction...[/bold cyan]", spinner="dots"):
                rej_req = SessionRejectionActionRequest(
                    scheme_id=target_scheme.id,
                    notice_text=notice_text,
                    guidance_passages=guidance_passages,
                    simulated=False,
                )
                rej_analysis = await analyze_scheme_rejection(session_id=session_id, request=rej_req)

            console.print(Panel(
                f"[bold red]Rejection Analysis Result[/bold red]\n\n"
                f"[bold cyan]Officially Supported Next Step Found:[/bold cyan] {rej_analysis.supported}\n"
                f"[bold cyan]Verbatim Stated Reason:[/bold cyan] \"{rej_analysis.reason_quote}\"\n"
                f"[bold cyan]Recommended Next Action:[/bold cyan]\n"
                + "\n".join(f"  • {step.action} (Source: {step.source_url})" for step in rej_analysis.next_steps)
                + f"\n\n[dim]Redacted Notice Sent to Processor:\n{rej_analysis.redacted_notice}[/dim]",
                border_style="red",
                box=box.ROUNDED,
            ))

        elif choice == "5":
            await interactive_office_chat_simulation(session_id)

        elif choice == "6":
            console.print("\n[bold cyan]Thank you for testing Project Unlocked! Exiting interface.[/bold cyan]")
            break


# ---------------------------------------------------------------------------
# Main Entry Point & Mode Selector
# ---------------------------------------------------------------------------

async def main():
    print_banner()
    await init_db()

    console.print("[bold]Select Testing Mode:[/bold]\n")
    console.print("  [bold cyan]1[/bold cyan]. Full End-to-End Citizen Journey (Profile ➔ Discovery ➔ Questions ➔ DAG ➔ Actions)")
    console.print("  [bold cyan]2[/bold cyan]. Test Agent 1: Scheme Discovery & Source Evidence")
    console.print("  [bold cyan]3[/bold cyan]. Test Agent 2: Consolidated Questionnaire & Dynamic Reassessment")
    console.print("  [bold cyan]4[/bold cyan]. Test Agent 3: Document Planning DAG & Topological Sorting")
    console.print("  [bold cyan]5[/bold cyan]. Test Agent 4: Action Studio (Emails, Calendars, Progress, Rejection)")
    console.print("  [bold cyan]6[/bold cyan]. Test Agent 4 Feature: Office Chat Simulator (WhatsApp-Style Demo)")
    console.print("  [bold cyan]7[/bold cyan]. Exit")

    mode = Prompt.ask("\nEnter choice", choices=["1", "2", "3", "4", "5", "6", "7"], default="1")
    if mode == "7":
        console.print("[cyan]Exiting interface.[/cyan]")
        return

    # Always ensure a valid active session
    session_id, context = await setup_citizen_profile()

    if mode == "1":
        # Full Journey
        schemes = await execute_discovery(session_id)
        if schemes:
            await interactive_questionnaire(session_id)
            await interactive_action_plan(session_id)
            await interactive_action_studio(session_id)

    elif mode == "2":
        # Agent 1
        schemes = await execute_discovery(session_id)
        if schemes and Confirm.ask("\nWould you like to inspect deep source evidence for a scheme?", default=True):
            for i, s in enumerate(schemes, start=1):
                console.print(f"  [{i}] {s.name}")
            pick = IntPrompt.ask("Select scheme", default=1, choices=[str(i) for i in range(1, len(schemes) + 1)])
            chosen = schemes[pick - 1]
            req_table = Table(title=f"Sourced Criteria for {chosen.name}", box=box.ROUNDED)
            req_table.add_column("Criterion Text", style="white")
            req_table.add_column("Operator / Value", style="cyan")
            req_table.add_column("Status", style="yellow")
            req_table.add_column("Official Source Evidence URL", style="blue")
            for r in chosen.requirements:
                r_dict = r if isinstance(r, dict) else r.model_dump()
                crit = r_dict.get("criterion", "")
                op_val = f"{r_dict.get('operator')}: {r_dict.get('value')}"
                st = r_dict.get("status", "")
                url = r_dict.get("source_url") or "None"
                req_table.add_row(crit, op_val, st, url)
            console.print(req_table)

    elif mode == "3":
        # Agent 2
        schemes = await execute_discovery(session_id)
        if schemes:
            await interactive_questionnaire(session_id)

    elif mode == "4":
        # Agent 3
        schemes = await execute_discovery(session_id)
        if schemes:
            await interactive_action_plan(session_id)

    elif mode == "5":
        # Agent 4
        schemes = await execute_discovery(session_id)
        if schemes:
            await interactive_action_studio(session_id)

    elif mode == "6":
        # Office Chat Simulation
        schemes = await execute_discovery(session_id)
        if schemes:
            await interactive_office_chat_simulation(session_id)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Session interrupted by user. Goodbye![/yellow]")
