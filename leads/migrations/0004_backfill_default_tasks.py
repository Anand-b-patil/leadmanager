from django.db import migrations
from django.utils import timezone


def create_default_tasks_for_existing_leads(apps, schema_editor):
    Lead = apps.get_model("leads", "Lead")
    LeadTask = apps.get_model("leads", "LeadTask")

    existing_task_lead_ids = set(LeadTask.objects.values_list("lead_id", flat=True))
    today = timezone.now().date()
    tasks_to_create = []

    for lead in Lead.objects.exclude(owner_id__isnull=True).iterator():
        if lead.id in existing_task_lead_ids:
            continue
        due_date = lead.next_follow_up_at.date() if lead.next_follow_up_at else today
        tasks_to_create.append(
            LeadTask(
                owner_id=lead.owner_id,
                lead_id=lead.id,
                title="Initial follow-up",
                due_date=due_date,
                priority=lead.priority,
                notes="Auto-created so every lead starts with a follow-up task.",
            )
        )

    if tasks_to_create:
        LeadTask.objects.bulk_create(tasks_to_create)


class Migration(migrations.Migration):
    dependencies = [
        ("leads", "0003_alter_lead_options_lead_city_lead_job_title_and_more"),
    ]

    operations = [
        migrations.RunPython(create_default_tasks_for_existing_leads, migrations.RunPython.noop),
    ]
