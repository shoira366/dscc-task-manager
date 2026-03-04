import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from tasks.models import RegistrationRequest

User = get_user_model()


@pytest.mark.django_db
def test_dashboard_requires_login(client):
    resp = client.get(reverse("dashboard"))
    assert resp.status_code in (301, 302)
    assert "/accounts/login" in resp["Location"]


@pytest.mark.django_db
def test_admin_sees_admin_dashboard(client):
    _ = User.objects.create_user(
        username="admin1",
        password="pass12345",
        is_staff=True,
        is_superuser=True,
    )
    client.login(username="admin1", password="pass12345")

    resp = client.get(reverse("dashboard"))
    assert resp.status_code == 200

    # These strings should exist in your admin dashboard section
    assert b"Users" in resp.content
    assert b"Approvals" in resp.content


@pytest.mark.django_db
def test_normal_user_does_not_see_admin_dashboard(client):
    _ = User.objects.create_user(username="u1", password="pass12345")
    client.login(username="u1", password="pass12345")

    resp = client.get(reverse("dashboard"))
    assert resp.status_code == 200

    # Normal users should not see admin-only blocks
    assert b"Admin Dashboard" not in resp.content


@pytest.mark.django_db
def test_request_access_creates_pending_request(client):
    url = reverse("request_access")

    payload = {
        "username": "newuser1",
        "email": "newuser1@example.com",
        "password1": "StrongPass123!",
        "password2": "StrongPass123!",
    }

    resp = client.post(url, data=payload)
    assert resp.status_code in (200, 302)

    rr = RegistrationRequest.objects.get(username="newuser1")
    assert rr.status.lower() == "pending"


@pytest.mark.django_db
def test_admin_can_approve_request_creates_user(client):
    _ = User.objects.create_user(
        username="admin2",
        password="pass12345",
        is_staff=True,
        is_superuser=True,
    )
    client.login(username="admin2", password="pass12345")

    rr = RegistrationRequest.objects.create(
        username="approved_user",
        email="approved@example.com",
        password="StrongPass123!",
        status="pending",
    )

    resp = client.post(reverse("approve_request", args=[rr.pk]))
    assert resp.status_code in (200, 302)

    rr.refresh_from_db()
    assert rr.status.lower() == "approved"

    u = User.objects.get(username="approved_user")
    assert u.email == "approved@example.com"
    # should be normal member account, not admin
    assert u.is_staff is False
    assert u.is_superuser is False


@pytest.mark.django_db
def test_admin_can_reject_request_does_not_create_user(client):
    _ = User.objects.create_user(
        username="admin3",
        password="pass12345",
        is_staff=True,
        is_superuser=True,
    )
    client.login(username="admin3", password="pass12345")

    rr = RegistrationRequest.objects.create(
        username="rejected_user",
        email="rejected@example.com",
        password="StrongPass123!",
        status="pending",
    )

    resp = client.post(reverse("reject_request", args=[rr.pk]))
    assert resp.status_code in (200, 302)

    rr.refresh_from_db()
    assert rr.status.lower() == "rejected"

    assert not User.objects.filter(username="rejected_user").exists()
