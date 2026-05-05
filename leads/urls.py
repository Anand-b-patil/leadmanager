from django.urls import path

from . import views

urlpatterns = [
    path("", views.PublicLandingView.as_view(), name="landing"),
    path("app/", views.DashboardView.as_view(), name="dashboard"),
    path("leads/", views.LeadListView.as_view(), name="lead_list"),
    path("leads/export/", views.ExportLeadsView.as_view(), name="export_leads"),
    path("leads/create/", views.LeadCreateView.as_view(), name="lead_create"),
    path("leads/<int:pk>/", views.LeadDetailView.as_view(), name="lead_detail"),
    path("leads/<int:pk>/edit/", views.LeadUpdateView.as_view(), name="lead_edit"),
    path("leads/<int:pk>/delete/", views.DeleteLeadView.as_view(), name="lead_delete"),
    path("leads/<int:pk>/score/", views.ScoreLeadView.as_view(), name="score_lead"),
    path("leads/<int:pk>/generate-email/", views.GenerateEmailView.as_view(), name="generate_email"),
    path("leads/<int:pk>/stage/", views.UpdateLeadStageView.as_view(), name="lead_stage_update"),
    path("leads/<int:lead_id>/notes/add/", views.AddLeadNoteView.as_view(), name="add_lead_note"),
    path("leads/<int:lead_id>/tasks/add/", views.AddLeadTaskView.as_view(), name="add_lead_task"),
    path("pipeline/", views.PipelineView.as_view(), name="pipeline"),
    path("tasks/", views.TasksView.as_view(), name="tasks"),
    path("tasks/add/", views.AddLeadTaskView.as_view(), name="task_create"),
    path("tasks/<int:task_id>/toggle/", views.ToggleTaskView.as_view(), name="toggle_task"),
    path("analytics/", views.AnalyticsView.as_view(), name="analytics"),
    path("ai-workspace/", views.AIWorkspaceView.as_view(), name="ai_workspace"),
    path("account/", views.AccountView.as_view(), name="account"),
]
