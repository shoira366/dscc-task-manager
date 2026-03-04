from django.urls import path
from . import views

urlpatterns = [
    # Admin dashboard (Approval, Rejection)
    path("approvals/", views.approval_dashboard, name="approval_dashboard"),
    path("approvals/<int:pk>/approve/", views.approve_request, name="approve_request"),
    path("approvals/<int:pk>/reject/", views.reject_request, name="reject_request"),
    # Home / Dashboard
    path("", views.dashboard, name="dashboard"),
    # Registration
    path("accounts/request-access/", views.request_access, name="request_access"),
    # Groups
    path("groups/", views.group_list, name="group_list"),
    path("groups/<int:pk>/", views.group_detail, name="group_detail"),
    path("groups/<int:pk>/members/add/", views.add_member, name="add_member"),
    path("api/group-members/", views.group_members, name="group_members"),
    # Tasks
    path("tasks/", views.task_list, name="task_list"),  # tasks in my groups (filter)
    path("tasks/create/", views.task_create, name="task_create"),  # leader/admin only
    path("tasks/<int:pk>/", views.task_detail, name="task_detail"),
    path("tasks/<int:pk>/edit/", views.task_update, name="task_update"),
    path("tasks/<int:pk>/status/", views.task_status_update, name="task_status_update"),
]
