import os
import sys
from datetime import timedelta
from pathlib import Path

import django

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ["GEMINI_API_KEY"] = ""
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "leadmanager.settings")
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone

from leads.ai_service import score_lead
from leads.models import Lead, LeadActivity, LeadTag


def main():
    user_model = get_user_model()
    now = timezone.now()
    lead_templates = [
        {
            "name": "Maya Chen",
            "email": "maya.chen@northpeaksoftware.com",
            "company": "NorthPeak Software",
            "industry": "SaaS",
            "phone": "+1-415-555-0142",
            "website": "https://northpeaksoftware.com",
            "job_title": "VP of Revenue Operations",
            "city": "San Francisco",
            "source": "LinkedIn outbound",
            "stage": Lead.Stage.QUALIFIED,
            "priority": Lead.Priority.HIGH,
            "notes_summary": "Scaling pipeline ops and evaluating workflow automation for inbound lead routing.",
            "tags": ["saas", "revops", "enterprise"],
            "last_contacted_at": now - timedelta(days=2),
            "next_follow_up_at": now + timedelta(days=2),
        },
        {
            "name": "Daniel Foster",
            "email": "daniel.foster@blueharborcapital.com",
            "company": "BlueHarbor Capital",
            "industry": "Finance",
            "phone": "+1-646-555-0198",
            "website": "https://blueharborcapital.com",
            "job_title": "Director of Growth",
            "city": "New York",
            "source": "Referral",
            "stage": Lead.Stage.CONTACTED,
            "priority": Lead.Priority.HIGH,
            "notes_summary": "Warm intro from advisor network; interested in cleaner lead qualification and response SLAs.",
            "tags": ["finance", "warm", "decision-maker"],
            "last_contacted_at": now - timedelta(days=5),
            "next_follow_up_at": now + timedelta(days=1),
        },
        {
            "name": "Priya Raman",
            "email": "priya.raman@atlasbiologics.com",
            "company": "Atlas Biologics",
            "industry": "Healthcare",
            "phone": "+1-617-555-0111",
            "website": "https://atlasbiologics.com",
            "job_title": "Commercial Strategy Lead",
            "city": "Boston",
            "source": "Website demo request",
            "stage": Lead.Stage.ATTEMPTING,
            "priority": Lead.Priority.MEDIUM,
            "notes_summary": "Requested a walkthrough focused on handoff between marketing and inside sales teams.",
            "tags": ["healthcare", "inbound", "demo-request"],
            "last_contacted_at": now - timedelta(days=1),
            "next_follow_up_at": now + timedelta(days=3),
        },
        {
            "name": "Jordan Alvarez",
            "email": "jordan.alvarez@forgeworksmanufacturing.com",
            "company": "ForgeWorks Manufacturing",
            "industry": "Manufacturing",
            "phone": "+1-312-555-0174",
            "website": "https://forgeworksmanufacturing.com",
            "job_title": "Head of Sales Enablement",
            "city": "Chicago",
            "source": "Trade show",
            "stage": Lead.Stage.NEW,
            "priority": Lead.Priority.MEDIUM,
            "notes_summary": "Met at Midwest Operations Summit; team wants faster prioritization for distributor and OEM leads.",
            "tags": ["manufacturing", "event", "mid-market"],
            "last_contacted_at": now - timedelta(days=7),
            "next_follow_up_at": now + timedelta(days=4),
        },
    ]

    created_total = 0
    updated_total = 0

    for user in user_model.objects.order_by("id"):
        for template in lead_templates:
            defaults = {key: value for key, value in template.items() if key != "tags"}
            lead, created = Lead.objects.update_or_create(
                owner=user,
                email=template["email"],
                defaults=defaults,
            )

            tags = []
            for tag_name in template["tags"]:
                tag, _ = LeadTag.objects.get_or_create(owner=user, name=tag_name)
                tags.append(tag)
            lead.tags.set(tags)

            score, reason = score_lead(lead)
            lead.score = score
            lead.reason = reason
            lead.last_scored_at = now
            lead.save(update_fields=["score", "reason", "last_scored_at", "updated_at"])

            if created:
                LeadActivity.objects.create(
                    owner=user,
                    lead=lead,
                    activity_type=LeadActivity.ActivityType.LEAD_CREATED,
                    summary=f"Seeded lead {lead.name} for {lead.company}.",
                    details=lead.notes_summary,
                )
                LeadActivity.objects.create(
                    owner=user,
                    lead=lead,
                    activity_type=LeadActivity.ActivityType.SCORE_UPDATED,
                    summary=f"Seeded AI score for {lead.name} to {score}.",
                    details=reason,
                )
                created_total += 1
            else:
                updated_total += 1

    for user in user_model.objects.order_by("id"):
        print(f"{user.username}: {Lead.objects.filter(owner=user).count()} leads")
    print(f"created={created_total} updated={updated_total}")


if __name__ == "__main__":
    main()
