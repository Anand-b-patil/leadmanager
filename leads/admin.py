from django.contrib import admin

from .models import GeneratedEmail, Lead, LeadActivity, LeadNote, LeadTag, LeadTask


class LeadNoteInline(admin.TabularInline):
    model = LeadNote
    extra = 0


class LeadTaskInline(admin.TabularInline):
    model = LeadTask
    extra = 0


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "owner",
        "company",
        "stage",
        "priority",
        "score",
        "next_follow_up_at",
        "updated_at",
    )
    search_fields = ("name", "email", "company", "industry", "owner__username")
    list_filter = ("stage", "priority", "industry", "owner")
    autocomplete_fields = ("owner",)
    filter_horizontal = ("tags",)
    inlines = [LeadNoteInline, LeadTaskInline]


@admin.register(LeadTag)
class LeadTagAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "created_at")
    search_fields = ("name", "owner__username")
    autocomplete_fields = ("owner",)


@admin.register(LeadNote)
class LeadNoteAdmin(admin.ModelAdmin):
    list_display = ("lead", "owner", "created_at")
    search_fields = ("lead__name", "owner__username", "content")
    autocomplete_fields = ("owner", "lead")


@admin.register(LeadTask)
class LeadTaskAdmin(admin.ModelAdmin):
    list_display = ("title", "lead", "owner", "priority", "due_date", "is_completed")
    list_filter = ("priority", "is_completed")
    search_fields = ("title", "lead__name", "owner__username")
    autocomplete_fields = ("owner", "lead")


@admin.register(LeadActivity)
class LeadActivityAdmin(admin.ModelAdmin):
    list_display = ("summary", "lead", "owner", "activity_type", "created_at")
    list_filter = ("activity_type",)
    search_fields = ("summary", "lead__name", "owner__username")
    autocomplete_fields = ("owner", "lead")


@admin.register(GeneratedEmail)
class GeneratedEmailAdmin(admin.ModelAdmin):
    list_display = ("lead", "owner", "subject", "created_at")
    search_fields = ("lead__name", "subject", "owner__username")
    autocomplete_fields = ("owner", "lead")
