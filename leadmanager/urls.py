from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import include, path
from django.views.generic import RedirectView

from leads.views import AppLoginView, SignUpView

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "login/",
        AppLoginView.as_view(),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", SignUpView.as_view(), name="signup"),
    path(
        "favicon.ico",
        RedirectView.as_view(url=staticfiles_storage.url("favicon.svg"), permanent=False),
    ),
    path("", include("leads.urls")),
]
