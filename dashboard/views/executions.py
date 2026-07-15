from django.contrib import messages as django_messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ..services import backend_api
from .utils import (
    _endpoints_for,
    app_context,
    auth_required,
    execution_input_source,
    handle_api_error,
    redact_secrets,
    session_token,
    summarize_workflow_run,
    workflow_projects_by_id,
)

@auth_required
def executions(request):
    context = app_context(request, endpoints=_endpoints_for("Executions"))
    try:
        page = _positive_int(request.GET.get("page"), 1)
        page_size = 20
        active_status = request.GET.get("status", "")
        if active_status not in EXECUTION_STATUS_FILTERS:
            active_status = ""
        active_project = request.GET.get("project", "")
        active_project_payload = _project_by_slug(
            context.get("projects", []),
            active_project,
        )

        workflow_runs = redact_secrets(
            backend_api.list_workflow_runs(
                session_token(request),
                page=page,
                page_size=page_size,
                status=active_status or None,
                project_id=(
                    active_project_payload.get("id")
                    if active_project_payload
                    else None
                ),
            )
        )
        runs_page = _normalize_runs_page(workflow_runs, page, page_size)
        workflow_project_map = workflow_projects_by_id(
            session_token(request),
            context.get("projects", []),
        )
        for run in runs_page["items"]:
            run["project"] = workflow_project_map.get(run.get("workflow_id"))
            run["input_source"] = execution_input_source(run.get("input") or "")

        context.update(
            {
                "workflow_runs": runs_page["items"],
                "execution_total": runs_page["total"],
                "execution_page": runs_page["page"],
                "execution_page_size": runs_page["page_size"],
                "execution_total_pages": runs_page["total_pages"],
                "execution_last_item_on_page": (
                    len(runs_page["items"]) == 1 and runs_page["page"] > 1
                ),
                "execution_pagination": _pagination_context(
                    request,
                    runs_page["page"],
                    runs_page["total_pages"],
                ),
                "execution_project_tabs": context.get("projects", []),
                "execution_project_filter_tabs": _project_filter_tabs(
                    request,
                    context.get("projects", []),
                    active_project,
                ),
                "active_execution_project": active_project,
                "active_execution_project_id": (
                    active_project_payload.get("id")
                    if active_project_payload
                    else None
                ),
                "execution_status_filters": EXECUTION_STATUS_FILTERS,
                "execution_status_filter_tabs": _status_filter_tabs(
                    request,
                    active_status,
                ),
                "active_execution_status": active_status,
                "active_run_statuses": ACTIVE_RUN_STATUSES,
            }
        )
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        context["executions_error"] = exc.message
        context["workflow_runs"] = []
        context["execution_total"] = 0
        context["execution_project_tabs"] = []

    return render(request, "dashboard/utility/executions.html", context)


ACTIVE_RUN_STATUSES = {"pending", "running"}
EXECUTION_STATUS_FILTERS = {
    "running": "Running",
    "failed": "Failed",
    "canceled": "Cancelled",
}


def _positive_int(value, default):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 1 else default


def _project_by_slug(projects, slug):
    if not slug:
        return None
    for project in projects:
        if project.get("slug") == slug:
            return project
    return None


def _normalize_runs_page(payload, page, page_size):
    if isinstance(payload, list):
        return {
            "items": payload,
            "total": len(payload),
            "page": page,
            "page_size": page_size,
            "total_pages": 1 if payload else 0,
        }
    return {
        "items": payload.get("items", []),
        "total": payload.get("total", 0),
        "page": payload.get("page", page),
        "page_size": payload.get("page_size", page_size),
        "total_pages": payload.get("total_pages", 0),
    }


def _pagination_context(request, page, total_pages):
    if total_pages <= 1:
        return None

    query = request.GET.copy()
    pages = []
    for page_number in range(1, total_pages + 1):
        query["page"] = page_number
        pages.append(
            {
                "number": page_number,
                "url": f"{request.path}?{query.urlencode()}",
                "active": page_number == page,
            }
        )

    query["page"] = page - 1
    previous_url = f"{request.path}?{query.urlencode()}" if page > 1 else ""
    query["page"] = page + 1
    next_url = f"{request.path}?{query.urlencode()}" if page < total_pages else ""

    return {
        "pages": pages,
        "previous_url": previous_url,
        "next_url": next_url,
    }


def _query_url(request, **updates):
    query = request.GET.copy()
    for key, value in updates.items():
        if value:
            query[key] = value
        else:
            query.pop(key, None)
    query["page"] = 1
    return f"{request.path}?{query.urlencode()}"


def _project_filter_tabs(request, projects, active_project):
    tabs = [
        {
            "label": "All",
            "url": _query_url(request, project=""),
            "active": not active_project,
        }
    ]
    for project in projects:
        slug = project.get("slug", "")
        tabs.append(
            {
                "label": project.get("name", "Project"),
                "url": _query_url(request, project=slug),
                "active": active_project == slug,
            }
        )
    return tabs


def _status_filter_tabs(request, active_status):
    tabs = [
        {
            "label": "All",
            "url": _query_url(request, status=""),
            "active": not active_status,
        }
    ]
    for status_value, label in EXECUTION_STATUS_FILTERS.items():
        tabs.append(
            {
                "label": label,
                "url": _query_url(request, status=status_value),
                "active": active_status == status_value,
            }
        )
    return tabs


def _safe_next_url(request):
    next_url = request.POST.get("next", "")
    if next_url.startswith("/"):
        return next_url
    return reverse("dashboard:executions")


def _previous_page_url(path):
    if "page=" not in path:
        return path

    from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

    split = urlsplit(path)
    query = parse_qs(split.query)
    page = _positive_int(query.get("page", ["1"])[0], 1)
    if page <= 1:
        return path

    query["page"] = [str(page - 1)]
    return urlunsplit(
        (
            split.scheme,
            split.netloc,
            split.path,
            urlencode(query, doseq=True),
            split.fragment,
        )
    )


@auth_required
@require_POST
def cancel_execution(request, run_id):
    try:
        backend_api.cancel_workflow_run(session_token(request), run_id)
        django_messages.success(request, f"Execution #{run_id} stopped.")
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)

    next_url = request.POST.get("next", "")
    if next_url.startswith("/"):
        return redirect(next_url)
    return redirect("dashboard:execution_detail", run_id=run_id)


@auth_required
@require_POST
def resume_execution(request, run_id):
    try:
        backend_api.resume_workflow_run(session_token(request), run_id)
        django_messages.success(request, f"Execution #{run_id} resumed.")
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)

    next_url = request.POST.get("next", "")
    if next_url.startswith("/"):
        return redirect(next_url)
    return redirect("dashboard:execution_detail", run_id=run_id)


@auth_required
@require_POST
def retry_execution(request, run_id):
    try:
        result = backend_api.retry_workflow_run(session_token(request), run_id)
        django_messages.success(request, f"Execution #{run_id} retry queued.")
        next_url = request.POST.get("next", "")
        if next_url.startswith("/") and "executions" in next_url:
            return redirect(next_url)
        return redirect("dashboard:execution_detail", run_id=result.get("id", run_id))
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)

    next_url = request.POST.get("next", "")
    if next_url.startswith("/"):
        return redirect(next_url)
    return redirect("dashboard:execution_detail", run_id=run_id)


@auth_required
@require_POST
def delete_execution(request, run_id):
    next_url = _safe_next_url(request)
    try:
        backend_api.delete_workflow_run(session_token(request), run_id)
        django_messages.success(request, f"Execution #{run_id} permanently deleted.")
        next_url = _previous_page_url(next_url) if request.POST.get("last_item_on_page") == "1" else next_url
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)

    return redirect(next_url)


@auth_required
@require_POST
def delete_canceled_executions(request):
    next_url = _safe_next_url(request)
    project_id = request.POST.get("project_id") or None
    try:
        result = backend_api.delete_canceled_workflow_runs(
            session_token(request),
            project_id=project_id,
        )
        deleted = result.get("deleted", 0) if isinstance(result, dict) else 0
        django_messages.success(
            request,
            f"Permanently deleted {deleted} cancelled execution{'s' if deleted != 1 else ''}.",
        )
        next_url = _previous_page_url(next_url)
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)

    return redirect(next_url)


@auth_required
def execution_detail(request, run_id):
    context = app_context(request, endpoints=_endpoints_for("Executions"))
    try:
        workflow_run = backend_api.get_workflow_run(session_token(request), run_id)
        events = backend_api.list_workflow_run_events(session_token(request), run_id)
        workflow_run = redact_secrets(workflow_run)
        events = redact_secrets(events)
        context.update(
            {
                "workflow_run": workflow_run,
                "workflow_events": events,
                "workflow_run_summary": summarize_workflow_run(workflow_run, events),
                "active_run_statuses": ACTIVE_RUN_STATUSES,
            }
        )
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        context["executions_error"] = exc.message

    return render(request, "dashboard/utility/execution_detail.html", context)


@auth_required
def execution_status_partial(request, run_id):
    """HTMX polling target: returns just the status badge fragment for a
    workflow run. Reads current status from the backend only -- reloading
    or navigating away from this page never cancels the Celery task."""
    try:
        workflow_run = backend_api.get_workflow_run(session_token(request), run_id)
        workflow_run = redact_secrets(workflow_run)
    except backend_api.BackendAPIError:
        workflow_run = None

    return render(
        request,
        "dashboard/partials/execution_status.html",
        {"workflow_run": workflow_run, "active_run_statuses": ACTIVE_RUN_STATUSES},
    )
