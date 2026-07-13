import json

from django.contrib import messages as django_messages
from django.http import StreamingHttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
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


@auth_required
@require_POST
def stream_chat_message(request, project_slug, chat_slug):
    content = request.POST.get("content", "").strip()
    agent_name = request.POST.get("agent_name", "assistant")
    if agent_name not in {mode["value"] for mode in AGENT_MODES}:
        agent_name = "assistant"
    token = session_token(request)

    project, project_error = resolve_project(token, project_slug)
    if project_error:
        return StreamingHttpResponse(
            f"event: failed\ndata: {json.dumps({'event': 'failed', 'message': project_error})}\n\n",
            content_type="text/event-stream",
            status=404,
        )

    chat, chat_error = resolve_chat(token, project["id"], chat_slug)
    if chat_error:
        return StreamingHttpResponse(
            f"event: failed\ndata: {json.dumps({'event': 'failed', 'message': chat_error})}\n\n",
            content_type="text/event-stream",
            status=404,
        )

    if not content:
        return StreamingHttpResponse(
            'event: failed\ndata: {"event":"failed","message":"Message cannot be empty."}\n\n',
            content_type="text/event-stream",
            status=400,
        )

    try:
        upstream = backend_api.stream_message(token, chat["id"], content, agent_name)
    except backend_api.BackendAPIError as exc:
        return StreamingHttpResponse(
            f"event: failed\ndata: {json.dumps({'event': 'failed', 'message': exc.message})}\n\n",
            content_type="text/event-stream",
            status=exc.status_code or 502,
        )

    def stream():
        buffer = ""
        with upstream:
            for chunk in upstream.iter_content(chunk_size=1):
                if chunk:
                    text = chunk.decode("utf-8", errors="replace")
                    buffer += text

                    while "\n\n" in buffer:
                        frame, buffer = buffer.split("\n\n", 1)
                        yield _with_rendered_message_html(
                            frame,
                            token=token,
                            chat_id=chat["id"],
                            active_project=with_slug(project, "name"),
                            active_chat=with_slug(chat, "title"),
                        )

            if buffer:
                yield buffer

    response = StreamingHttpResponse(stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


def _with_rendered_message_html(frame, *, token, chat_id, active_project=None, active_chat=None):
    if not frame.startswith("event: completed"):
        return f"{frame}\n\n"

    event_name = "completed"
    data_lines = []
    for line in frame.splitlines():
        if line.startswith("event:"):
            event_name = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            data_lines.append(line.removeprefix("data:").strip())

    try:
        payload = json.loads("\n".join(data_lines))
        message_id = payload.get("assistant_message_id")
        if message_id:
            message = backend_api.get_message(token, chat_id, message_id)
            payload["rendered_html"] = render_to_string(
                "dashboard/chat/_message_bubble.html",
                {
                    "message": message,
                    "active_project": active_project,
                    "active_chat": active_chat,
                },
            )
        return f"event: {event_name}\ndata: {json.dumps(payload)}\n\n"
    except (ValueError, backend_api.BackendAPIError):
        return f"{frame}\n\n"
