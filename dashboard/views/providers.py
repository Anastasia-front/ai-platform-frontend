from django.contrib import messages as django_messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ..services import backend_api
from .utils import (
    _endpoints_for,
    app_context,
    auth_required,
    handle_api_error,
    provider_page_url,
    resource_slug,
    resolve_project,
    session_token,
    with_slug,
)

@auth_required
def providers(request):
    token = session_token(request)
    context = app_context(request, endpoints=_endpoints_for("Providers"))
    active_project = None
    documents = []
    project_slug = request.GET.get("project") or (
        context["projects"][0]["slug"] if context["projects"] else ""
    )

    try:
        context["provider_data"] = backend_api.get_providers(token)
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        context["provider_error"] = exc.message

    if project_slug:
        project, project_error = resolve_project(token, project_slug)
        if project_error:
            context["provider_project_error"] = project_error
        else:
            active_project = with_slug(project, "name")
            try:
                documents = backend_api.list_project_documents(token, project["id"])
            except backend_api.BackendAPIError as exc:
                handle_api_error(request, exc)
                context["provider_project_error"] = exc.message

    context.update(
        {
            "active_project_slug": project_slug,
            "provider_project": active_project,
            "provider_documents": documents,
            "provider_health_result": request.session.pop(
                "provider_health_result", None
            ),
            "embedding_tool_result": request.session.pop("embedding_tool_result", None),
        }
    )
    return render(request, "dashboard/utility/providers.html", context)


@auth_required
@require_POST
def update_chat_provider(request):
    token = session_token(request)
    try:
        backend_api.update_chat_provider_defaults(
            token,
            provider=request.POST.get("provider") or None,
            model=request.POST.get("model") or None,
            fallback_model=request.POST.get("fallback_model") or "",
            base_url=request.POST.get("base_url") or None,
            api_key=request.POST.get("api_key") or None,
        )
        django_messages.success(request, "Chat provider defaults saved.")
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)

    return redirect(provider_page_url(request))


@auth_required
@require_POST
def update_embedding_provider(request):
    token = session_token(request)
    dimensions = request.POST.get("dimensions", "").strip()
    try:
        backend_api.update_embedding_provider_defaults(
            token,
            provider=request.POST.get("provider") or None,
            model=request.POST.get("model") or None,
            dimensions=int(dimensions) if dimensions else None,
            base_url=request.POST.get("base_url") or None,
            api_key=request.POST.get("api_key") or None,
        )
        django_messages.success(request, "Embedding provider defaults saved.")
    except ValueError:
        django_messages.error(request, "Embedding dimensions must be a number.")
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)

    return redirect(provider_page_url(request))


@auth_required
@require_POST
def check_provider_health(request):
    token = session_token(request)
    provider_kind = request.POST.get("kind")
    provider = request.POST.get("provider", "").strip()
    model = request.POST.get("model", "").strip()
    dimensions = request.POST.get("dimensions", "").strip()

    try:
        if provider_kind == "embedding":
            result = backend_api.check_embedding_provider_health(
                token,
                provider,
                model=model,
                dimensions=int(dimensions) if dimensions else None,
            )
        else:
            result = backend_api.check_chat_provider_health(
                token, provider, model=model
            )
        request.session["provider_health_result"] = result
    except ValueError:
        django_messages.error(request, "Embedding dimensions must be a number.")
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)

    return redirect(provider_page_url(request))


@auth_required
@require_POST
def sync_embeddings(request, project_slug):
    token = session_token(request)
    project, project_error = resolve_project(token, project_slug)
    if project_error:
        django_messages.error(request, project_error)
        return redirect("dashboard:providers")

    try:
        request.session["embedding_tool_result"] = backend_api.sync_project_embeddings(
            token,
            project["id"],
        )
        django_messages.success(request, "Project embeddings synced.")
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)

    return redirect(
        f"{reverse('dashboard:providers')}?project={resource_slug(project, 'name')}"
    )


@auth_required
@require_POST
def rebuild_document_embeddings(request, project_slug, document_id):
    token = session_token(request)
    project, project_error = resolve_project(token, project_slug)
    if project_error:
        django_messages.error(request, project_error)
        return redirect("dashboard:providers")

    try:
        request.session["embedding_tool_result"] = (
            backend_api.rebuild_document_embeddings(
                token,
                document_id,
            )
        )
        django_messages.success(request, "Document embeddings rebuilt.")
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)

    return redirect(
        f"{reverse('dashboard:providers')}?project={resource_slug(project, 'name')}"
    )

