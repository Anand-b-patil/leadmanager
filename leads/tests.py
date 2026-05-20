from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.test.utils import override_settings

from .ai_service import score_lead
from .models import GeneratedEmail, Lead, LeadActivity, LeadTag, LeadTask


class CRMViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(username="alice", email="alice@example.com", password="secret123")
        self.other_user = get_user_model().objects.create_user(
            username="bob", email="bob@example.com", password="secret123"
        )
        self.client.login(username="alice", password="secret123")

    def create_lead(self, **kwargs):
        defaults = {
            "owner": self.user,
            "name": "Ava Stone",
            "email": "ava@example.com",
            "company": "Northwind Labs",
            "industry": "SaaS",
        }
        defaults.update(kwargs)
        return Lead.objects.create(**defaults)

    def test_public_landing_loads(self):
        self.client.logout()
        response = self.client.get(reverse("landing"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SignalDesk")

    def test_dashboard_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_create_lead_with_tags(self):
        response = self.client.post(
            reverse("lead_create"),
            {
                "name": "Ava Stone",
                "email": "ava@example.com",
                "company": "Northwind Labs",
                "industry": "SaaS",
                "job_title": "Head of Growth",
                "phone": "",
                "website": "",
                "city": "",
                "source": "Referral",
                "stage": Lead.Stage.NEW,
                "priority": Lead.Priority.HIGH,
                "score": "",
                "notes_summary": "Warm intro from partner.",
                "last_contacted_at": "",
                "next_follow_up_at": "",
                "tags_input": "inbound, strategic",
            },
        )
        lead = Lead.objects.get(email="ava@example.com")
        self.assertRedirects(response, reverse("lead_detail", args=[lead.pk]))
        self.assertEqual(lead.owner, self.user)
        self.assertEqual(lead.tags.count(), 2)
        task = LeadTask.objects.get(lead=lead)
        self.assertEqual(task.title, "Initial follow-up")
        self.assertEqual(task.priority, lead.priority)
        self.assertTrue(LeadActivity.objects.filter(lead=lead, activity_type=LeadActivity.ActivityType.LEAD_CREATED).exists())
        self.assertTrue(LeadActivity.objects.filter(lead=lead, activity_type=LeadActivity.ActivityType.TASK_ADDED).exists())

    def test_create_lead_with_duplicate_email_shows_form_error(self):
        self.create_lead(email="ava@example.com")

        response = self.client.post(
            reverse("lead_create"),
            {
                "name": "Ava Stone Duplicate",
                "email": "ava@example.com",
                "company": "Northwind Labs",
                "industry": "SaaS",
                "job_title": "Head of Growth",
                "phone": "",
                "website": "",
                "city": "",
                "source": "Referral",
                "stage": Lead.Stage.NEW,
                "priority": Lead.Priority.HIGH,
                "score": "",
                "notes_summary": "Warm intro from partner.",
                "last_contacted_at": "",
                "next_follow_up_at": "",
                "tags_input": "inbound, strategic",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You already have a lead with this email address.")
        self.assertEqual(Lead.objects.filter(owner=self.user, email="ava@example.com").count(), 1)

    def test_update_lead_with_duplicate_email_shows_form_error(self):
        original = self.create_lead(name="Ava Stone", email="ava@example.com")
        other = self.create_lead(name="Mia Chen", email="mia@example.com", company="Bluebird", industry="Finance")

        response = self.client.post(
            reverse("lead_edit", args=[other.pk]),
            {
                "name": other.name,
                "email": original.email,
                "company": other.company,
                "industry": other.industry,
                "job_title": "",
                "phone": "",
                "website": "",
                "city": "",
                "source": "",
                "stage": other.stage,
                "priority": other.priority,
                "score": "",
                "notes_summary": "",
                "last_contacted_at": "",
                "next_follow_up_at": "",
                "tags_input": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You already have a lead with this email address.")
        other.refresh_from_db()
        self.assertEqual(other.email, "mia@example.com")

    def test_user_only_sees_owned_leads(self):
        own = self.create_lead(name="Alice Lead", email="alicelead@example.com")
        Lead.objects.create(
            owner=self.other_user,
            name="Bob Lead",
            email="boblead@example.com",
            company="Beta",
            industry="Finance",
        )
        response = self.client.get(reverse("lead_list"))
        self.assertContains(response, own.name)
        self.assertNotContains(response, "Bob Lead")

    def test_task_create_and_toggle_flow(self):
        lead = self.create_lead()
        create_response = self.client.post(
            reverse("task_create"),
            {
                "lead_id": lead.pk,
                "title": "Call the buyer",
                "due_date": "2026-05-10",
                "priority": Lead.Priority.HIGH,
                "notes": "Prepare pricing context.",
                "next": reverse("tasks"),
            },
        )
        task = LeadTask.objects.get(title="Call the buyer")
        self.assertRedirects(create_response, reverse("tasks"))
        toggle_response = self.client.post(reverse("toggle_task", args=[task.pk]), {"next": reverse("tasks")})
        task.refresh_from_db()
        self.assertRedirects(toggle_response, reverse("tasks"))
        self.assertTrue(task.is_completed)

    @patch("leads.views.score_lead", return_value=(87, "High intent and strong SaaS fit."))
    def test_score_lead_updates_record_and_logs_activity(self, mocked_score):
        lead = self.create_lead()
        response = self.client.post(reverse("score_lead", args=[lead.pk]), {"next": reverse("lead_detail", args=[lead.pk])})
        lead.refresh_from_db()
        self.assertRedirects(response, reverse("lead_detail", args=[lead.pk]))
        self.assertEqual(lead.score, 87)
        self.assertEqual(lead.reason, "High intent and strong SaaS fit.")
        self.assertIsNotNone(lead.last_scored_at)
        self.assertTrue(
            LeadActivity.objects.filter(lead=lead, activity_type=LeadActivity.ActivityType.SCORE_UPDATED).exists()
        )
        mocked_score.assert_called_once()

    @patch(
        "leads.views.generate_outreach_email",
        return_value="Subject: Intro for Northwind\n\nHi Ava,\n\nWould love to connect.\n\nBest,\nTeam",
    )
    def test_generate_email_creates_history(self, mocked_email):
        lead = self.create_lead()
        response = self.client.post(
            reverse("generate_email", args=[lead.pk]),
            {"next": reverse("lead_detail", args=[lead.pk])},
        )
        lead.refresh_from_db()
        self.assertRedirects(response, reverse("lead_detail", args=[lead.pk]))
        self.assertIn("Subject: Intro for Northwind", lead.generated_email)
        self.assertEqual(GeneratedEmail.objects.filter(lead=lead).count(), 1)
        mocked_email.assert_called_once()

    def test_export_only_returns_owned_leads(self):
        self.create_lead(name="Alice Lead", email="alicelead@example.com")
        Lead.objects.create(
            owner=self.other_user,
            name="Bob Lead",
            email="boblead@example.com",
            company="Beta",
            industry="Finance",
        )
        response = self.client.get(reverse("export_leads"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alice Lead")
        self.assertNotContains(response, "Bob Lead")


class AIScoringTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="carol", email="carol@example.com", password="secret123")

    def create_lead(self, **kwargs):
        defaults = {
            "owner": self.user,
            "name": "Ava Stone",
            "email": "ava@northwindlabs.com",
            "company": "Northwind Labs",
            "industry": "SaaS",
            "job_title": "Head of Growth",
            "website": "https://northwindlabs.com",
            "phone": "555-0102",
            "source": "Referral",
            "priority": Lead.Priority.HIGH,
            "notes_summary": "Warm intro from an implementation partner.",
        }
        defaults.update(kwargs)
        return Lead.objects.create(**defaults)

    @override_settings(GEMINI_API_KEY="")
    def test_score_lead_uses_heuristic_when_ai_is_unconfigured(self):
        lead = self.create_lead()

        score, reason = score_lead(lead)

        self.assertGreater(score, 50)
        self.assertIn("Heuristic score based on", reason)
        self.assertNotIn("currently unavailable", reason)

    @patch("leads.ai_service._get_model")
    def test_score_lead_falls_back_to_heuristic_when_ai_call_fails(self, mocked_get_model):
        lead = self.create_lead()

        class BrokenModel:
            def generate_content(self, prompt):
                raise RuntimeError("boom")

        mocked_get_model.return_value = BrokenModel()

        score, reason = score_lead(lead)

        self.assertGreater(score, 50)
        self.assertIn("Heuristic score based on", reason)
