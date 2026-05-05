from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Lead, LeadNote, LeadTask


class DateTimeLocalInput(forms.DateTimeInput):
    input_type = "datetime-local"


class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Username"}))
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Password"})
    )


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={"class": "form-control"}))

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing_class} form-control".strip()


class AccountForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ("username", "first_name", "last_name", "email")
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
        }


class LeadForm(forms.ModelForm):
    tags_input = forms.CharField(
        required=False,
        label="Tags",
        help_text="Comma-separated labels such as SaaS, inbound, strategic.",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "SaaS, enterprise, inbound"}),
    )

    class Meta:
        model = Lead
        fields = [
            "name",
            "email",
            "company",
            "job_title",
            "industry",
            "phone",
            "website",
            "city",
            "source",
            "stage",
            "priority",
            "score",
            "notes_summary",
            "last_contacted_at",
            "next_follow_up_at",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "company": forms.TextInput(attrs={"class": "form-control"}),
            "job_title": forms.TextInput(attrs={"class": "form-control"}),
            "industry": forms.TextInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "website": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://"}),
            "city": forms.TextInput(attrs={"class": "form-control"}),
            "source": forms.TextInput(attrs={"class": "form-control"}),
            "stage": forms.Select(attrs={"class": "form-select"}),
            "priority": forms.Select(attrs={"class": "form-select"}),
            "score": forms.NumberInput(attrs={"class": "form-control", "min": 0, "max": 100}),
            "notes_summary": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "last_contacted_at": DateTimeLocalInput(attrs={"class": "form-control"}),
            "next_follow_up_at": DateTimeLocalInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["score"].required = False
        self.fields["last_contacted_at"].required = False
        self.fields["next_follow_up_at"].required = False
        if self.instance.pk:
            self.fields["tags_input"].initial = ", ".join(self.instance.tags.values_list("name", flat=True))


class LeadNoteForm(forms.ModelForm):
    class Meta:
        model = LeadNote
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "placeholder": "Capture context, objections, or next steps."}
            )
        }


class LeadTaskForm(forms.ModelForm):
    class Meta:
        model = LeadTask
        fields = ["title", "due_date", "priority", "notes"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Schedule follow-up call"}),
            "due_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "priority": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Optional task notes"}),
        }
