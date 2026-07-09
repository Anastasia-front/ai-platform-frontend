from django.contrib import messages as django_messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from ..services import backend_api
from .utils import (
    AGENT_MODES,
    app_context,
    auth_required,
    handle_api_error,
    resource_slug,
    resolve_chat,
    resolve_project,
    session_token,
    with_slug,
    with_slugs,
)

@auth_required
@require_POST
def new_chat(request, project_slug):
    token = session_token(request)
    project, project_error = resolve_project(token, project_slug)
    if project_error:
        django_messages.error(request, project_error)
        return redirect("dashboard:projects")

    title = request.POST.get("title", "").strip() or "New chat"
    agent_name = "assistant"

    try:
        chat = backend_api.create_chat(
            token,
            project["id"],
            title,
            agent_name=agent_name,
        )
        return redirect(
            "dashboard:chat_detail",
            project_slug=resource_slug(project, "name"),
            chat_slug=resource_slug(chat, "title"),
        )
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)
        return redirect(
            "dashboard:project_detail", project_slug=resource_slug(project, "name")
        )


@auth_required
def chat_detail(request, project_slug, chat_slug):
    token = session_token(request)
    project, project_error = resolve_project(token, project_slug)
    context = app_context(
        request,
        active_project_slug=project_slug,
        active_chat_slug=chat_slug,
    )

    if project_error:
        context["page_error"] = project_error
        return render(request, "dashboard/chat/workspace.html", context)

    project = with_slug(project, "name")
    context["active_project"] = project

    chat, chat_error = resolve_chat(token, project["id"], chat_slug)
    if chat_error:
        context["page_error"] = chat_error
        return render(request, "dashboard/chat/workspace.html", context)

    chat = with_slug(chat, "title")

    try:
        context["active_chat"] = chat
        context["chats"] = with_slugs(
            backend_api.list_project_chats(token, project["id"]),
            "title",
        )
        context["chat_messages"] = backend_api.list_messages(token, chat["id"])
        context["documents"] = backend_api.list_project_documents(token, project["id"])
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        context["page_error"] = exc.message

    return render(request, "dashboard/chat/workspace.html", context)


@auth_required
@require_POST
def delete_chat(request, project_slug, chat_slug):
    token = session_token(request)
    project, project_error = resolve_project(token, project_slug)
    if project_error:
        django_messages.error(request, project_error)
        return redirect("dashboard:projects")

    chat, chat_error = resolve_chat(token, project["id"], chat_slug)
    if chat_error:
        django_messages.error(request, chat_error)
        return redirect(
            "dashboard:project_detail", project_slug=resource_slug(project, "name")
        )

    try:
        backend_api.delete_chat(token, chat["id"])
        django_messages.success(request, "Chat deleted.")
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)

    return redirect(
        "dashboard:project_detail", project_slug=resource_slug(project, "name")
    )


@auth_required
@require_POST
def send_chat_message(request, project_slug, chat_slug):
    content = request.POST.get("content", "").strip()
    agent_name = request.POST.get("agent_name", "assistant")
    if agent_name not in {mode["value"] for mode in AGENT_MODES}:
        agent_name = "assistant"

    token = session_token(request)
    chat_messages = []
    error = None

    project, project_error = resolve_project(token, project_slug)
    chat = None

    if project_error:
        error = project_error
    else:
        chat, chat_error = resolve_chat(token, project["id"], chat_slug)
        if chat_error:
            error = chat_error

    if not content and error is None:
        error = "Message cannot be empty."
    elif error is None:
        try:
            backend_api.send_message(token, chat["id"], content, agent_name=agent_name)
            chat_messages = backend_api.list_messages(token, chat["id"])
        except backend_api.BackendAPIError as exc:
            handle_api_error(request, exc)
            error = exc.message

    if request.headers.get("HX-Request"):
        return render(
            request,
            "dashboard/chat/_messages.html",
            {"chat_messages": chat_messages, "message_error": error},
        )

    if error:
        django_messages.error(request, error)
    return redirect(
        "dashboard:chat_detail", project_slug=project_slug, chat_slug=chat_slug
    )

