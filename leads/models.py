from django.conf import settings
from django.db import models
from django.db.models import UniqueConstraint
from django.utils import timezone


class LeadTag(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lead_tags")
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=20, default="slate")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            UniqueConstraint(fields=["owner", "name"], name="unique_tag_name_per_owner"),
        ]

    def __str__(self):
        return self.name


class Lead(models.Model):
    class Stage(models.TextChoices):
        NEW = "new", "New"
        ATTEMPTING = "attempting", "Attempting Contact"
        CONTACTED = "contacted", "Contacted"
        QUALIFIED = "qualified", "Qualified"
        PROPOSAL = "proposal", "Proposal Sent"
        NEGOTIATION = "negotiation", "Negotiation"
        WON = "won", "Won"
        LOST = "lost", "Lost"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="leads",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=100)
    email = models.EmailField()
    company = models.CharField(max_length=100)
    industry = models.CharField(max_length=100)
    phone = models.CharField(max_length=30, blank=True, default="")
    website = models.URLField(blank=True, default="")
    job_title = models.CharField(max_length=100, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    source = models.CharField(max_length=100, blank=True, default="")
    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.NEW)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    notes_summary = models.CharField(max_length=255, blank=True, default="")
    score = models.IntegerField(null=True, blank=True)
    reason = models.TextField(blank=True, default="")
    generated_email = models.TextField(blank=True, default="")
    last_scored_at = models.DateTimeField(null=True, blank=True)
    last_contacted_at = models.DateTimeField(null=True, blank=True)
    next_follow_up_at = models.DateTimeField(null=True, blank=True)
    tags = models.ManyToManyField(LeadTag, blank=True, related_name="leads")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at"]
        constraints = [
            UniqueConstraint(fields=["owner", "email"], name="unique_lead_email_per_owner"),
        ]

    def __str__(self):
        return f"{self.name} - {self.company}"

    @property
    def is_follow_up_overdue(self):
        return bool(self.next_follow_up_at and self.next_follow_up_at < timezone.now())


class LeadNote(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lead_notes")
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="notes")
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Note for {self.lead.name}"


class LeadTask(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lead_tasks")
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=140)
    due_date = models.DateField(null=True, blank=True)
    priority = models.CharField(max_length=20, choices=Lead.Priority.choices, default=Lead.Priority.MEDIUM)
    notes = models.TextField(blank=True, default="")
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["is_completed", "due_date", "-created_at"]

    def __str__(self):
        return self.title


class LeadActivity(models.Model):
    class ActivityType(models.TextChoices):
        LEAD_CREATED = "lead_created", "Lead Created"
        LEAD_UPDATED = "lead_updated", "Lead Updated"
        NOTE_ADDED = "note_added", "Note Added"
        TASK_ADDED = "task_added", "Task Added"
        TASK_COMPLETED = "task_completed", "Task Completed"
        STAGE_CHANGED = "stage_changed", "Stage Changed"
        SCORE_UPDATED = "score_updated", "Score Updated"
        EMAIL_GENERATED = "email_generated", "Email Generated"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lead_activities")
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="activities")
    activity_type = models.CharField(max_length=30, choices=ActivityType.choices)
    summary = models.CharField(max_length=255)
    details = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.summary


class GeneratedEmail(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="generated_emails")
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="email_history")
    subject = models.CharField(max_length=255, blank=True, default="")
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Email for {self.lead.name} at {self.created_at:%Y-%m-%d %H:%M}"
