import csv

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.db.models import Avg, Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from .ai_service import generate_outreach_email, score_lead
from .forms import AccountForm, LeadForm, LeadNoteForm, LeadTaskForm, LoginForm, SignUpForm
from .models import GeneratedEmail, Lead, LeadActivity, LeadNote, LeadTag, LeadTask


def log_activity(owner, lead, activity_type, summary, details=""):
    LeadActivity.objects.create(
        owner=owner,
        lead=lead,
        activity_type=activity_type,
        summary=summary,
        details=details,
    )


def sync_tags(lead, tags_input):
    tags = []
    for raw_name in tags_input.split(","):
        name = raw_name.strip()
        if not name:
            continue
        tag, _ = LeadTag.objects.get_or_create(owner=lead.owner, name=name)
        tags.append(tag)
    lead.tags.set(tags)


def get_safe_next_url(request, default_url):
    next_url = request.POST.get("next") or request.GET.get("next") or request.META.get("HTTP_REFERER")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return next_url
    return default_url


def build_stage_rows(leads):
    total = leads.count() or 1
    aggregated = {row["stage"]: row["count"] for row in leads.values("stage").annotate(count=Count("id"))}
    return [
        {
            "value": value,
            "label": label,
            "count": aggregated.get(value, 0),
            "percent": int((aggregated.get(value, 0) / total) * 100),
        }
        for value, label in Lead.Stage.choices
    ]


class PublicLandingView(TemplateView):
    template_name = "landing.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("dashboard")
        return super().dispatch(request, *args, **kwargs)


class AppLoginView(LoginView):
    authentication_form = LoginForm
    template_name = "login.html"
    redirect_authenticated_user = True


class SignUpView(CreateView):
    form_class = SignUpForm
    template_name = "signup.html"
    success_url = reverse_lazy("dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        messages.success(self.request, "Your CRM workspace is ready.")
        return response


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        leads = Lead.objects.filter(owner=self.request.user).prefetch_related("tags")
        tasks = LeadTask.objects.filter(owner=self.request.user)
        activities = LeadActivity.objects.filter(owner=self.request.user).select_related("lead")
        avg_score = leads.exclude(score__isnull=True).aggregate(avg=Avg("score"))["avg"] or 0
        context.update(
            {
                "kpis": [
                    {"label": "Total Leads", "value": leads.count(), "tone": "primary"},
                    {
                        "label": "Qualified Pipeline",
                        "value": leads.filter(stage=Lead.Stage.QUALIFIED).count(),
                        "tone": "success",
                    },
                    {"label": "Won Accounts", "value": leads.filter(stage=Lead.Stage.WON).count(), "tone": "gold"},
                    {
                        "label": "Overdue Follow-ups",
                        "value": tasks.filter(is_completed=False, due_date__lt=timezone.localdate()).count(),
                        "tone": "danger",
                    },
                ],
                "average_score": round(avg_score, 1),
                "stage_rows": build_stage_rows(leads),
                "recent_leads": leads.order_by("-created_at")[:5],
                "upcoming_tasks": tasks.filter(is_completed=False).select_related("lead").order_by("due_date", "created_at")[:6],
                "recent_activities": activities[:8],
                "recent_emails": GeneratedEmail.objects.filter(owner=self.request.user).select_related("lead")[:4],
            }
        )
        return context


class LeadListView(LoginRequiredMixin, ListView):
    model = Lead
    template_name = "leads/lead_list.html"
    context_object_name = "leads"
    paginate_by = 10

    def get_queryset(self):
        queryset = (
            Lead.objects.filter(owner=self.request.user)
            .prefetch_related("tags")
            .order_by("-updated_at", "-created_at")
        )
        q = self.request.GET.get("q", "").strip()
        stage = self.request.GET.get("stage", "").strip()
        priority = self.request.GET.get("priority", "").strip()
        tag = self.request.GET.get("tag", "").strip()
        min_score = self.request.GET.get("min_score", "").strip()
        max_score = self.request.GET.get("max_score", "").strip()
        created_after = self.request.GET.get("created_after", "").strip()
        created_before = self.request.GET.get("created_before", "").strip()
        sort = self.request.GET.get("sort", "-updated_at").strip()

        if q:
            queryset = queryset.filter(
                Q(name__icontains=q)
                | Q(email__icontains=q)
                | Q(company__icontains=q)
                | Q(industry__icontains=q)
                | Q(notes__content__icontains=q)
            ).distinct()
        if stage:
            queryset = queryset.filter(stage=stage)
        if priority:
            queryset = queryset.filter(priority=priority)
        if tag:
            queryset = queryset.filter(tags__name__iexact=tag)
        if min_score:
            queryset = queryset.filter(score__gte=min_score)
        if max_score:
            queryset = queryset.filter(score__lte=max_score)
        if created_after:
            queryset = queryset.filter(created_at__date__gte=created_after)
        if created_before:
            queryset = queryset.filter(created_at__date__lte=created_before)

        allowed_sorts = {
            "name": "name",
            "-name": "-name",
            "score": "score",
            "-score": "-score",
            "created_at": "created_at",
            "-created_at": "-created_at",
            "next_follow_up_at": "next_follow_up_at",
            "-next_follow_up_at": "-next_follow_up_at",
            "-updated_at": "-updated_at",
        }
        return queryset.order_by(allowed_sorts.get(sort, "-updated_at"), "-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "stage_choices": Lead.Stage.choices,
                "priority_choices": Lead.Priority.choices,
                "tag_options": LeadTag.objects.filter(owner=self.request.user),
                "filters": {key: self.request.GET.get(key, "") for key in self.request.GET.keys()},
                "sort_options": [
                    ("-updated_at", "Recently updated"),
                    ("-created_at", "Newest"),
                    ("name", "Name A-Z"),
                    ("-score", "Highest score"),
                    ("next_follow_up_at", "Next follow-up"),
                ],
            }
        )
        return context


class PipelineView(LoginRequiredMixin, TemplateView):
    template_name = "leads/pipeline.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        leads = Lead.objects.filter(owner=self.request.user).prefetch_related("tags")
        columns = []
        for value, label in Lead.Stage.choices:
            stage_leads = leads.filter(stage=value).order_by("-score", "-updated_at")[:6]
            columns.append({"value": value, "label": label, "leads": stage_leads, "count": stage_leads.count()})
        context["pipeline_columns"] = columns
        context["stage_choices"] = Lead.Stage.choices
        return context


class LeadCreateView(LoginRequiredMixin, CreateView):
    model = Lead
    form_class = LeadForm
    template_name = "leads/lead_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Create Lead"
        context["submit_label"] = "Create Lead"
        return context

    def form_valid(self, form):
        form.instance.owner = self.request.user
        response = super().form_valid(form)
        sync_tags(self.object, form.cleaned_data.get("tags_input", ""))
        log_activity(
            self.request.user,
            self.object,
            LeadActivity.ActivityType.LEAD_CREATED,
            f"Added {self.object.name} to the CRM.",
        )
        messages.success(self.request, "Lead created successfully.")
        return response

    def get_success_url(self):
        return reverse("lead_detail", args=[self.object.pk])


class LeadUpdateView(LoginRequiredMixin, UpdateView):
    model = Lead
    form_class = LeadForm
    template_name = "leads/lead_form.html"

    def get_queryset(self):
        return Lead.objects.filter(owner=self.request.user).prefetch_related("tags")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Edit Lead"
        context["submit_label"] = "Save Changes"
        return context

    def form_valid(self, form):
        previous_stage = self.get_object().stage
        response = super().form_valid(form)
        sync_tags(self.object, form.cleaned_data.get("tags_input", ""))
        log_activity(
            self.request.user,
            self.object,
            LeadActivity.ActivityType.LEAD_UPDATED,
            f"Updated details for {self.object.name}.",
        )
        if previous_stage != self.object.stage:
            log_activity(
                self.request.user,
                self.object,
                LeadActivity.ActivityType.STAGE_CHANGED,
                f"Moved {self.object.name} to {self.object.get_stage_display()}.",
            )
        messages.success(self.request, "Lead updated successfully.")
        return response

    def get_success_url(self):
        return reverse("lead_detail", args=[self.object.pk])


class LeadDetailView(LoginRequiredMixin, DetailView):
    model = Lead
    template_name = "leads/lead_detail.html"
    context_object_name = "lead"

    def get_queryset(self):
        return (
            Lead.objects.filter(owner=self.request.user)
            .prefetch_related("tags", "notes", "tasks", "activities", "email_history")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lead = self.object
        context.update(
            {
                "note_form": LeadNoteForm(),
                "task_form": LeadTaskForm(),
                "open_tasks": lead.tasks.filter(is_completed=False),
                "completed_tasks": lead.tasks.filter(is_completed=True)[:5],
                "activities": lead.activities.all()[:12],
                "email_history": lead.email_history.all()[:8],
                "stage_choices": Lead.Stage.choices,
            }
        )
        return context


class TasksView(LoginRequiredMixin, ListView):
    model = LeadTask
    template_name = "tasks.html"
    context_object_name = "tasks"
    paginate_by = 12

    def get_queryset(self):
        queryset = LeadTask.objects.filter(owner=self.request.user).select_related("lead")
        status = self.request.GET.get("status", "open")
        priority = self.request.GET.get("priority", "")
        q = self.request.GET.get("q", "")

        if status == "open":
            queryset = queryset.filter(is_completed=False)
        elif status == "completed":
            queryset = queryset.filter(is_completed=True)
        elif status == "overdue":
            queryset = queryset.filter(is_completed=False, due_date__lt=timezone.localdate())

        if priority:
            queryset = queryset.filter(priority=priority)
        if q:
            queryset = queryset.filter(Q(title__icontains=q) | Q(notes__icontains=q) | Q(lead__name__icontains=q))

        return queryset.order_by("is_completed", "due_date", "-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "status": self.request.GET.get("status", "open"),
                "priority": self.request.GET.get("priority", ""),
                "q": self.request.GET.get("q", ""),
                "priority_choices": Lead.Priority.choices,
                "task_form": LeadTaskForm(),
                "lead_options": Lead.objects.filter(owner=self.request.user).order_by("name"),
            }
        )
        return context


class AnalyticsView(LoginRequiredMixin, TemplateView):
    template_name = "analytics.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        leads = Lead.objects.filter(owner=self.request.user)
        tasks = LeadTask.objects.filter(owner=self.request.user)
        scores = list(leads.exclude(score__isnull=True).values_list("score", flat=True))
        score_bands = {
            "0-39": len([score for score in scores if score < 40]),
            "40-69": len([score for score in scores if 40 <= score < 70]),
            "70-89": len([score for score in scores if 70 <= score < 90]),
            "90-100": len([score for score in scores if score >= 90]),
        }
        industry_rows = leads.values("industry").annotate(total=Count("id")).order_by("-total", "industry")[:6]
        activity_rows = (
            LeadActivity.objects.filter(owner=self.request.user)
            .values("activity_type")
            .annotate(total=Count("id"))
            .order_by("-total")
        )
        context.update(
            {
                "stage_rows": build_stage_rows(leads),
                "industry_rows": industry_rows,
                "score_bands": score_bands.items(),
                "activity_rows": activity_rows,
                "analytics_kpis": [
                    {"label": "Average Score", "value": round(leads.exclude(score__isnull=True).aggregate(avg=Avg("score"))["avg"] or 0, 1)},
                    {"label": "Open Tasks", "value": tasks.filter(is_completed=False).count()},
                    {"label": "Completed Tasks", "value": tasks.filter(is_completed=True).count()},
                    {"label": "Tagged Leads", "value": leads.filter(tags__isnull=False).distinct().count()},
                ],
            }
        )
        return context


class AIWorkspaceView(LoginRequiredMixin, TemplateView):
    template_name = "ai_workspace.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        leads = Lead.objects.filter(owner=self.request.user).order_by("-updated_at")
        context.update(
            {
                "ready_for_scoring": leads.filter(score__isnull=True)[:6],
                "recently_scored": leads.exclude(last_scored_at__isnull=True).order_by("-last_scored_at")[:6],
                "email_history": GeneratedEmail.objects.filter(owner=self.request.user).select_related("lead")[:12],
            }
        )
        return context


class AccountView(LoginRequiredMixin, UpdateView):
    form_class = AccountForm
    template_name = "account.html"
    success_url = reverse_lazy("account")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Account updated.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        leads = Lead.objects.filter(owner=self.request.user)
        context["account_stats"] = [
            {"label": "Owned Leads", "value": leads.count()},
            {"label": "Open Tasks", "value": LeadTask.objects.filter(owner=self.request.user, is_completed=False).count()},
            {"label": "Generated Emails", "value": GeneratedEmail.objects.filter(owner=self.request.user).count()},
        ]
        return context


class ExportLeadsView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="leads.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "Name",
                "Email",
                "Company",
                "Industry",
                "Stage",
                "Priority",
                "Score",
                "Next Follow Up",
                "Created At",
            ]
        )
        for lead in Lead.objects.filter(owner=request.user).prefetch_related("tags"):
            writer.writerow(
                [
                    lead.name,
                    lead.email,
                    lead.company,
                    lead.industry,
                    lead.get_stage_display(),
                    lead.get_priority_display(),
                    lead.score or "",
                    lead.next_follow_up_at.isoformat() if lead.next_follow_up_at else "",
                    lead.created_at.isoformat(),
                ]
            )
        return response


class AddLeadNoteView(LoginRequiredMixin, View):
    def post(self, request, lead_id):
        lead = get_object_or_404(Lead, pk=lead_id, owner=request.user)
        form = LeadNoteForm(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            note.owner = request.user
            note.lead = lead
            note.save()
            if not lead.notes_summary:
                lead.notes_summary = note.content[:255]
                lead.save(update_fields=["notes_summary", "updated_at"])
            log_activity(
                request.user,
                lead,
                LeadActivity.ActivityType.NOTE_ADDED,
                f"Added a note for {lead.name}.",
                note.content[:255],
            )
            messages.success(request, "Note saved.")
        else:
            messages.error(request, "Could not save the note.")
        return redirect("lead_detail", pk=lead.pk)


class AddLeadTaskView(LoginRequiredMixin, View):
    def post(self, request, lead_id=None):
        lead = None
        if lead_id:
            lead = get_object_or_404(Lead, pk=lead_id, owner=request.user)
        else:
            lead = get_object_or_404(Lead, pk=request.POST.get("lead_id"), owner=request.user)
        form = LeadTaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.owner = request.user
            task.lead = lead
            task.save()
            log_activity(
                request.user,
                lead,
                LeadActivity.ActivityType.TASK_ADDED,
                f"Created task '{task.title}' for {lead.name}.",
            )
            messages.success(request, "Task created.")
        else:
            messages.error(request, "Could not create the task.")
        return redirect(get_safe_next_url(request, reverse("tasks")))


class ToggleTaskView(LoginRequiredMixin, View):
    def post(self, request, task_id):
        task = get_object_or_404(LeadTask, pk=task_id, owner=request.user)
        task.is_completed = not task.is_completed
        task.completed_at = timezone.now() if task.is_completed else None
        task.save(update_fields=["is_completed", "completed_at", "updated_at"])
        activity_type = (
            LeadActivity.ActivityType.TASK_COMPLETED if task.is_completed else LeadActivity.ActivityType.TASK_ADDED
        )
        summary = f"Marked task '{task.title}' as completed." if task.is_completed else f"Reopened task '{task.title}'."
        log_activity(request.user, task.lead, activity_type, summary)
        messages.success(request, "Task updated.")
        return redirect(get_safe_next_url(request, reverse("tasks")))


class DeleteLeadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk, owner=request.user)
        lead_name = lead.name
        lead.delete()
        messages.success(request, f"Deleted {lead_name}.")
        return redirect("lead_list")


class UpdateLeadStageView(LoginRequiredMixin, View):
    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk, owner=request.user)
        new_stage = request.POST.get("stage", "")
        if new_stage not in dict(Lead.Stage.choices):
            messages.error(request, "Invalid stage.")
            return redirect("lead_detail", pk=pk)
        lead.stage = new_stage
        lead.save(update_fields=["stage", "updated_at"])
        log_activity(
            request.user,
            lead,
            LeadActivity.ActivityType.STAGE_CHANGED,
            f"Moved {lead.name} to {lead.get_stage_display()}.",
        )
        messages.success(request, "Stage updated.")
        return redirect(get_safe_next_url(request, reverse("lead_detail", args=[pk])))


class ScoreLeadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk, owner=request.user)
        score, reason = score_lead(lead)
        lead.score = score
        lead.reason = reason
        lead.last_scored_at = timezone.now()
        lead.save(update_fields=["score", "reason", "last_scored_at", "updated_at"])
        log_activity(
            request.user,
            lead,
            LeadActivity.ActivityType.SCORE_UPDATED,
            f"Updated AI score for {lead.name} to {score}.",
            reason,
        )
        messages.success(request, "Lead scored successfully.")
        return redirect(get_safe_next_url(request, reverse("lead_detail", args=[pk])))


class GenerateEmailView(LoginRequiredMixin, View):
    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk, owner=request.user)
        email_body = generate_outreach_email(lead)
        first_line, _, remainder = email_body.partition("\n")
        subject = first_line.replace("Subject:", "").strip() if first_line.lower().startswith("subject:") else ""
        body = remainder.strip() if subject else email_body
        lead.generated_email = email_body
        lead.save(update_fields=["generated_email", "updated_at"])
        GeneratedEmail.objects.create(owner=request.user, lead=lead, subject=subject, body=body)
        log_activity(
            request.user,
            lead,
            LeadActivity.ActivityType.EMAIL_GENERATED,
            f"Generated outreach email for {lead.name}.",
        )
        messages.success(request, "Outreach email generated.")
        return redirect(get_safe_next_url(request, reverse("lead_detail", args=[pk])))
