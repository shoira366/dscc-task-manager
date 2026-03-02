from django.urls import path
from . import views

urlpatterns = [
    # Home / Dashboard
    path('', views.dashboard, name='dashboard'),

    # Groups
    path('groups/', views.group_list, name='group_list'),
    path('groups/<int:pk>/', views.group_detail, name='group_detail'),
    path('groups/<int:pk>/members/add/', views.add_member, name='add_member'),
    path("api/group-members/", views.group_members, name="group_members"),

    # Tasks
    path('tasks/', views.task_list, name='task_list'),  # tasks in my groups (filter)
    path('tasks/create/', views.task_create, name='task_create'),  # leader/admin only
    path('tasks/<int:pk>/', views.task_detail, name='task_detail'),
    path('tasks/<int:pk>/edit/', views.task_update, name='task_update'),
    path("tasks/<int:pk>/status/", views.task_status_update, name="task_status_update"),
]