from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from .models import Task, Group, Membership, RegistrationRequest
from .forms import TaskForm, AddMemberForm, TaskStatusForm, RegistrationRequestForm
from django.contrib.auth.models import User


def is_admin(user) -> bool:
    return user.is_superuser or user.is_staff


def is_group_leader(user, group: Group) -> bool:
    if is_admin(user):
        return True
    return Membership.objects.filter(user=user, group=group, role="LEADER").exists()


def user_groups(user):
    return Group.objects.filter(memberships__user=user).distinct()


@login_required
def dashboard(request):
    # last 2 groups for everyone
    groups_qs = user_groups(request.user).order_by("-created_at")
    groups = groups_qs[:2]

    # determine if user is leader anywhere (or admin)
    is_leader_anywhere = (
        request.user.is_superuser
        or request.user.is_staff
        or Membership.objects.filter(user=request.user, role="LEADER").exists()
    )

    # members: only their assigned tasks (no activity feed)
    my_tasks = Task.objects.filter(
        group__in=groups_qs, assigned_to=request.user
    ).order_by("-created_at")[
        :3
    ]  # pick 3 if you want

    # leaders: last 3 tasks they created
    leader_created_tasks = (
        Task.objects.filter(created_by=request.user).order_by("-created_at")[:3]
        if is_leader_anywhere
        else Task.objects.none()
    )

    # admin-only widgets
    pending_count = 0
    users = User.objects.none()
    if is_admin:
        pending_count = RegistrationRequest.objects.filter(
            status=RegistrationRequest.STATUS_PENDING
        ).count()
        users = User.objects.order_by("username")

    return render(
        request,
        "tasks/dashboard.html",
        {
            "groups": groups,
            "my_tasks": my_tasks,
            "is_leader_anywhere": is_leader_anywhere,
            "leader_created_tasks": leader_created_tasks,
            "is_admin": is_admin,
            "pending_count": pending_count,
            "users": users,
        },
    )


@login_required
def group_list(request):
    groups = user_groups(request.user)
    return render(request, "tasks/group_list.html", {"groups": groups})


@login_required
def group_detail(request, pk):
    group = get_object_or_404(Group, pk=pk)
    if not Membership.objects.filter(
        user=request.user, group=group
    ).exists() and not is_admin(request.user):
        return HttpResponseForbidden("You are not a member of this group.")

    members = (
        Membership.objects.filter(group=group)
        .select_related("user")
        .order_by("-role", "user__username")
    )
    tasks = Task.objects.filter(group=group).order_by("-created_at")

    return render(
        request,
        "tasks/group_detail.html",
        {
            "group": group,
            "members": members,
            "tasks": tasks,
            "can_manage": is_group_leader(request.user, group),
        },
    )


@login_required
def task_list(request):
    groups_qs = user_groups(request.user)

    tasks = list(
        Task.objects.filter(group__in=groups_qs)
        .select_related("group", "assigned_to", "created_by")
        .order_by("-created_at")
    )

    is_admin = request.user.is_staff or request.user.is_superuser

    if is_admin:
        leader_group_ids = set(g.pk for g in groups_qs)
    else:
        leader_group_ids = set(
            Membership.objects.filter(user=request.user, role="LEADER").values_list(
                "group_id", flat=True
            )
        )

    for t in tasks:
        t.can_update_status = (
            is_admin
            or t.assigned_to_id == request.user.id
            or t.group_id in leader_group_ids
        )

    return render(
        request,
        "tasks/task_list.html",
        {
            "tasks": tasks,
        },
    )


@login_required
def task_detail(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if not Membership.objects.filter(
        user=request.user, group=task.group
    ).exists() and not is_admin(request.user):
        return HttpResponseForbidden("You are not allowed to view this task.")

    return render(request, "tasks/task_detail.html", {"task": task})


@login_required
def task_create(request):
    if request.method == "POST":
        form = TaskForm(request.POST, user=request.user)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user

            if not is_group_leader(request.user, task.group):
                return HttpResponseForbidden(
                    "Only group leader/admin can create tasks for this group."
                )

            task.save()
            return redirect("group_detail", pk=task.group_id)
    else:
        group_id = request.GET.get("group")
        form = TaskForm(
            user=request.user, initial={"group": group_id} if group_id else None
        )

    return render(request, "tasks/task_form.html", {"form": form})


@login_required
def task_update(request, pk):
    task = get_object_or_404(Task, pk=pk)

    # Assignee can update status/description; leader/admin can update everything
    if not Membership.objects.filter(
        user=request.user, group=task.group
    ).exists() and not is_admin(request.user):
        return HttpResponseForbidden("Not allowed.")

    can_manage = (
        is_group_leader(request.user, task.group)
        or task.assigned_to_id == request.user.id
    )
    if not can_manage:
        return HttpResponseForbidden(
            "Only assignee or leader/admin can edit this task."
        )

    if request.method == "POST":
        form = TaskForm(
            request.POST, instance=task, user=request.user, group=task.group
        )
        if form.is_valid():
            form.save()
            return redirect("task_detail", pk=task.pk)
    else:
        form = TaskForm(instance=task, user=request.user, group=task.group)

    return render(request, "tasks/task_form.html", {"form": form, "task": task})


@require_POST
@login_required
def task_status_update(request, pk):
    task = get_object_or_404(Task, pk=pk)

    # Must be in the same group (member/leader/admin)
    if not request.user.is_staff and not request.user.is_superuser:
        if not Membership.objects.filter(user=request.user, group=task.group).exists():
            return HttpResponseForbidden("Not allowed.")

    # Must be assignee or leader/admin to change status
    if not can_update_task_status(request.user, task):
        return HttpResponseForbidden(
            "You can only update your own tasks (unless leader/admin)."
        )

    form = TaskStatusForm(request.POST, instance=task)
    if form.is_valid():
        form.save()

    return redirect("task_list")


@login_required
def add_member(request, pk):
    group = get_object_or_404(Group, pk=pk)

    if not is_group_leader(request.user, group):
        return HttpResponseForbidden("Only leader/admin can add members.")

    if request.method == "POST":
        form = AddMemberForm(request.POST, group=group)
        if form.is_valid():
            Membership.objects.create(
                group=group,
                user=form.cleaned_data["user"],
                role=form.cleaned_data["role"],
            )
            return redirect("group_detail", pk=group.pk)
    else:
        form = AddMemberForm(group=group)

    return render(request, "tasks/add_member.html", {"group": group, "form": form})


@require_GET
@login_required
def group_members(request):
    group_id = request.GET.get("group_id")
    if not group_id:
        return JsonResponse({"users": []})

    # allow only members/admin to fetch users of that group
    if not request.user.is_staff and not request.user.is_superuser:
        if not Membership.objects.filter(user=request.user, group_id=group_id).exists():
            return JsonResponse({"users": []})

    users = (
        User.objects.filter(memberships__group_id=group_id)
        .distinct()
        .order_by("username")
    )
    data = [{"id": u.id, "username": u.username} for u in users]
    return JsonResponse({"users": data})


def can_update_task_status(user, task) -> bool:
    if user.is_superuser or user.is_staff:
        return True
    if task.assigned_to_id == user.id:
        return True
    return Membership.objects.filter(
        user=user, group=task.group, role="LEADER"
    ).exists()


def request_access(request):
    if request.method == "POST":
        form = RegistrationRequestForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("login")
    else:
        form = RegistrationRequestForm()
    return render(request, "registration/request_access.html", {"form": form})


# ADMIN DASHBOARD
@staff_member_required
def approval_dashboard(request):
    pending = RegistrationRequest.objects.filter(
        status=RegistrationRequest.STATUS_PENDING
    ).order_by("-created_at")
    return render(request, "admin/approval_dashboard.html", {"pending": pending})


@staff_member_required
@transaction.atomic
def approve_request(request, pk: int):
    req = get_object_or_404(RegistrationRequest, pk=pk)

    if request.method != "POST":
        return redirect("approval_dashboard")

    if req.status != RegistrationRequest.STATUS_PENDING:
        messages.warning(request, "Request is not pending anymore.")
        return redirect("approval_dashboard")

    user = User(username=req.username, email=req.email or "")
    user.password = req.password  # already hashed
    user.is_active = True
    user.save()

    req.status = RegistrationRequest.STATUS_APPROVED
    req.save(update_fields=["status"])

    messages.success(request, f"Approved: {user.username}")
    return redirect("approval_dashboard")


@staff_member_required
def reject_request(request, pk: int):
    req = get_object_or_404(RegistrationRequest, pk=pk)

    if request.method == "POST" and req.status == RegistrationRequest.STATUS_PENDING:
        req.status = RegistrationRequest.STATUS_REJECTED
        req.save(update_fields=["status"])
        messages.info(request, f"Rejected: {req.username}")

    return redirect("approval_dashboard")
