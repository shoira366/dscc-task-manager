from django import forms
from django.contrib.auth.models import User

from .models import Task, Group, Membership


class TaskForm(forms.ModelForm):
    """
    Create:
      - user must be leader/admin
      - group choices: groups user leads (or all if admin)
      - assigned_to choices: members of selected group
    Edit:
      - if group is passed, lock group field
      - restrict assigned_to to that group's members
    """

    def __init__(self, *args, user=None, group=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.locked_group = group

    # 1) Group queryset (what groups appear in dropdown)
        if group is not None:
            self.fields["group"].queryset = Group.objects.filter(pk=group.pk)
            self.fields["group"].disabled = True
        else:
            if user and (user.is_superuser or user.is_staff):
                self.fields["group"].queryset = Group.objects.all()
            elif user:
                self.fields["group"].queryset = Group.objects.filter(
                    memberships__user=user,
                    memberships__role="LEADER",
                ).distinct()
            else:
                self.fields["group"].queryset = Group.objects.none()

        # 2) Decide which group is currently selected (for assignee filtering)
        chosen_group = group

        # If POST contains group
        if chosen_group is None:
            group_id = self.data.get("group")
            if group_id:
                chosen_group = Group.objects.filter(pk=group_id).first()

        # If GET/initial contains group (e.g. /tasks/create/?group=1)
        if chosen_group is None:
            init_group_id = self.initial.get("group")
            if init_group_id:
                chosen_group = Group.objects.filter(pk=init_group_id).first()

    # 3) Assigned_to queryset depends on chosen_group
        if chosen_group is not None:
            self.fields["assigned_to"].queryset = User.objects.filter(
                memberships__group=chosen_group
            ).distinct().order_by("username")
        else:
            self.fields["assigned_to"].queryset = User.objects.none()

    class Meta:
        model = Task
        fields = ["title", "description", "group", "assigned_to", "status", "priority", "due_date"]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

class TaskStatusForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["status"]

class AddMemberForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=forms.Select(attrs={
            "class": "form-select",
        })
    )

    role = forms.ChoiceField(
        choices=Membership.ROLE_CHOICES,
        widget=forms.Select(attrs={
            "class": "form-select",
        })
    )

    def __init__(self, *args, group: Group, **kwargs):
        super().__init__(*args, **kwargs)
        self.group = group

        # Only users not already in group
        self.fields["user"].queryset = User.objects.exclude(
            memberships__group=group
        ).order_by("username")

        # Better labels
        self.fields["user"].label = "Select user"
        self.fields["role"].label = "Member role"