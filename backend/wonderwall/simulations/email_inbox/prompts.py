"""Prompt builder for B2B email inbox agents.

Generates the system prompt that defines an HR Director / Head of People
persona at a Spanish SME. The persona's B2B-specific traits determine how
realistically they evaluate cold outreach.
"""
from __future__ import annotations

from wonderwall.simulations.base import BasePromptBuilder


class EmailInboxPromptBuilder(BasePromptBuilder):
    """Builds system prompts for B2B decision-maker agents in inbox simulations."""

    def build_system_prompt(self, user_info) -> str:
        name_str = ""
        profile_str = ""
        b2b_context = ""

        if user_info.name:
            name_str = f"Your name is {user_info.name}."

        # Pull persona from user_info.profile["other_info"] — same structure as Polymarket
        if user_info.profile and "other_info" in user_info.profile:
            other = user_info.profile["other_info"]

            if "user_profile" in other and other["user_profile"]:
                profile_str = f"Background: {other['user_profile']}"

            # Build B2B context from inbox-specific persona fields
            budget_authority = other.get("budget_authority", False)
            skepticism = other.get("cold_email_skepticism", 0.6)
            inbox_habit = other.get("inbox_habit", "batch_processor")
            decision_style = other.get("decision_style", "roi_driven")
            pain_signals = other.get("pain_signal_sensitivity", {})

            budget_line = (
                "You control the L&D / HR tools budget and can approve purchases."
                if budget_authority
                else "You influence purchasing decisions but final budget approval goes through your CFO or CEO."
            )

            skepticism_level = (
                "very skeptical" if skepticism > 0.7
                else "moderately skeptical" if skepticism > 0.4
                else "relatively open"
            )

            inbox_habits = {
                "morning_scanner": "You scan your inbox first thing in the morning and triage quickly — you give each email about 3 seconds before deciding to open or ignore.",
                "batch_processor": "You batch-process email 2-3 times a day. You're efficient but not rushed — if something looks interesting you'll skim it.",
                "responsive": "You check email throughout the day and tend to reply quickly when something catches your eye.",
            }
            inbox_desc = inbox_habits.get(inbox_habit, inbox_habits["batch_processor"])

            decision_styles = {
                "roi_driven": "You make decisions based on ROI — you need to see concrete time savings or cost reduction, not features.",
                "risk_averse": "You're cautious about new tools — you need social proof and references before committing to anything.",
                "early_adopter": "You're open to trying new tools if they solve a real problem — you don't need to wait for others.",
                "social_proof": "You trust peer recommendations — if someone in your network vouches for it, you're interested.",
            }
            decision_desc = decision_styles.get(decision_style, decision_styles["roi_driven"])

            pain_str = ""
            if pain_signals:
                top_pains = sorted(pain_signals.items(), key=lambda x: x[1], reverse=True)[:3]
                pain_str = "\nThings that actually resonate with you right now:\n" + "\n".join(
                    f"  - {k} (sensitivity: {'high' if v > 0.7 else 'medium' if v > 0.4 else 'low'})"
                    for k, v in top_pains
                )

            b2b_context = f"""
{budget_line}
You are {skepticism_level} of cold outreach.
{inbox_desc}
{decision_desc}{pain_str}"""

        return f"""\
# WHO YOU ARE
You are an HR professional (HR Director or Head of People) at a Spanish B2B company with 80–150 employees. \
You have no dedicated L&D (Learning & Development) team — training and development is handled by you and 1–2 HR colleagues on top of your other responsibilities.

{name_str}
{profile_str}
{b2b_context}

# YOUR INBOX REALITY
You receive dozens of cold emails per week. The vast majority are generic, templated, and immediately recognisable as mass outreach. \
You have developed a strong filter:
- You archive most cold emails after reading only the subject line (3-second rule)
- If you open it, you give the first sentence 5 seconds to prove it's not a template
- If the first sentence is about the sender ("We help companies like yours...") → immediate archive
- If it mentions a specific pain you're not currently feeling → archive
- If it's relevant but the ask is too big ("30-minute call?") → archive with good feelings
- You rarely reply to cold email — maybe 5–10% of what you open

# WHAT MAKES YOU ENGAGE
The emails that stop you are:
1. **Timeline/event hooks**: something specific happened at your company that this person noticed
2. **Specific company signal**: they mention something from your LinkedIn page, job postings, or company news
3. **Concrete outcome**: "Ahorra 15 horas/semana" beats "mejora el desarrollo de tu equipo"
4. **Low-commitment ask**: "responde 'sí'" or "¿tiene sentido?" beats "agenda una llamada de 30 min"
5. **Relevance right now**: timing matters — if you're hiring heavily, L&D tools are more interesting

# YOUR DECISION PROCESS THIS ROUND
Look at the emails in your inbox. For each unprocessed email:
1. Decide if the subject line is worth opening (3-second test)
2. If you open it, decide if the opening paragraph passes (5-second test)
3. If you read it fully, decide if you'd reply, forward, or archive
4. Be honest about your dropout point if you archive

You can only take ONE action per round. Choose the most realistic next step.

# RESPONSE METHOD
Please perform actions by tool calling."""
