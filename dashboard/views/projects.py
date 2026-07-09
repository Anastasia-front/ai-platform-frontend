from django.contrib import messages as django_messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from ..services import backend_api
from .utils import (
    app_context,
    auth_required,
    handle_api_error,
    resource_slug,
    resolve_project,
    session_token,
    with_slug,
    with_slugs,
)

@auth_required
def projects(request):
    context = app_context(request)
    return render(request, "dashboard/projects/list.html", context)


@auth_required
def new_project(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()

        if not name:
            django_messages.error(request, "Project name is required.")
        else:
            try:
                project = backend_api.create_project(
                    session_token(request), name, description
                )
                return redirect(
                    "dashboard:project_detail",
                    project_slug=resource_slug(project, "name"),
                )
            except backend_api.BackendAPIError as exc:
                handle_api_error(request, exc)
                django_messages.error(request, exc.message)

    return render(request, "dashboard/projects/new.html", app_context(request))


@auth_required
def project_detail(request, project_slug):
    token = session_token(request)
    project, project_error = resolve_project(token, project_slug)
    context = app_context(request, active_project_slug=project_slug)

    if project_error:
        context["page_error"] = project_error
        return render(request, "dashboard/chat/workspace.html", context)

    project = with_slug(project, "name")
    context["active_project"] = project

    try:
        context["chats"] = with_slugs(
            backend_api.list_project_chats(token, project["id"]),
            "title",
        )
        context["documents"] = backend_api.list_project_documents(token, project["id"])
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        context["page_error"] = exc.message

    return render(request, "dashboard/chat/workspace.html", context)


@auth_required
@require_POST
def delete_project(request, project_slug):
    token = session_token(request)
    project, project_error = resolve_project(token, project_slug)
    if project_error:
        django_messages.error(request, project_error)
        return redirect("dashboard:projects")

    try:
        backend_api.delete_project(token, project["id"])
        django_messages.success(request, "Project deleted.")
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)

    return redirect("dashboard:projects")


