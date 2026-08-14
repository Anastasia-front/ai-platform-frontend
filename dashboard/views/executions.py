import json

import requests
from django.contrib import messages as django_messages
from django.http import StreamingHttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ..services import backend_api
from .utils import (
    _endpoints_for,
    app_context,
    auth_required,
    execution_input_source,
    execution_template_name,
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
            run["template_name"] = execution_template_name(run)

        token = session_token(request)
        grand_total = _run_count(token)
        status_counts = {
            status_value: _run_count(token, status=status_value)
            for status_value in EXECUTION_STATUS_FILTERS
        }
        project_counts = {
            project.get("id"): _run_count(token, project_id=project.get("id"))
            for project in context.get("projects", [])
        }
        distinct_statuses_present = sum(1 for c in status_counts.values() if c)
        distinct_projects_present = sum(1 for c in project_counts.values() if c)
        show_execution_filters = grand_total > 0 and (
            distinct_statuses_present > 1 or distinct_projects_present > 1
        )

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
                "show_execution_filters": show_execution_filters,
                "execution_project_filter_tabs": _project_filter_tabs(
                    request,
                    context.get("projects", []),
                    active_project,
                    project_counts,
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
                    status_counts,
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
        context["show_execution_filters"] = False

    return render(request, "dashboard/utility/executions.html", context)


ACTIVE_RUN_STATUSES = {"pending", "running"}
EXECUTION_STATUS_FILTERS = {
    "running": "Running",
    "failed": "Failed",
    "canceled": "Cancelled",
}

# Event types shown in the "Events" accordion/count -- lifecycle milestones
# only. partial_output (LLM token chunks, dozens-to-hundreds per step) has
# its own dedicated "Live progress" SSE panel and would otherwise flood this
# list; step_skipped/workflow_queued/workflow_started are similarly noisy
# for this summary view.
EVENT_LOG_TYPES = {
    "step_start",
    "step_done",
    "step_error",
    "workflow_done",
    "workflow_failed",
}


def _for_event_log(events):
    return [e for e in events if (e.get("event_type") or "event") in EVENT_LOG_TYPES]


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


def _run_count(token, status=None, project_id=None):
    payload = backend_api.list_workflow_runs(
        token, page=1, page_size=1, status=status, project_id=project_id
    )
    return _normalize_runs_page(payload, 1, 1)["total"]


def _project_filter_tabs(request, projects, active_project, project_counts):
    tabs = [
        {
            "label": "All",
            "url": _query_url(request, project=""),
            "active": not active_project,
        }
    ]
    for project in projects:
        if not project_counts.get(project.get("id")):
            continue
        slug = project.get("slug", "")
        tabs.append(
            {
                "label": project.get("name", "Project"),
                "url": _query_url(request, project=slug),
                "active": active_project == slug,
            }
        )
    return tabs


def _status_filter_tabs(request, active_status, status_counts):
    tabs = [
        {
            "label": "All",
            "url": _query_url(request, status=""),
            "active": not active_status,
        }
    ]
    for status_value, label in EXECUTION_STATUS_FILTERS.items():
        if not status_counts.get(status_value):
            continue
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
        events = _for_event_log(redact_secrets(events))
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


@auth_required
def execution_actions_partial(request, run_id):
    """HTMX polling target: returns the action buttons (Stop/Retry/Resume)
    for a run, so they stay in sync with the status badge -- which polls
    independently -- instead of freezing at whatever state was rendered on
    initial page load."""
    try:
        workflow_run = backend_api.get_workflow_run(session_token(request), run_id)
        workflow_run = redact_secrets(workflow_run)
    except backend_api.BackendAPIError:
        workflow_run = None

    return render(
        request,
        "dashboard/partials/execution_actions_live.html",
        {
            "workflow_run": workflow_run,
            "active_run_statuses": ACTIVE_RUN_STATUSES,
            "next_url": request.GET.get("next", ""),
            "last_item_on_page": request.GET.get("last_item_on_page", ""),
        },
    )


@auth_required
def execution_content_partial(request, run_id):
    """HTMX polling target: returns the structured result, raw input/output,
    and events for a run. While the run is still pending/running this keeps
    that content in sync with the status badge, which polls independently --
    without this, a page left open across a run finishing would keep showing
    the empty/in-progress content it had at initial page load."""
    try:
        workflow_run = backend_api.get_workflow_run(session_token(request), run_id)
        events = backend_api.list_workflow_run_events(session_token(request), run_id)
        workflow_run = redact_secrets(workflow_run)
        events = _for_event_log(redact_secrets(events))
        workflow_run_summary = summarize_workflow_run(workflow_run, events)
    except backend_api.BackendAPIError:
        workflow_run = None
        events = []
        workflow_run_summary = None

    return render(
        request,
        "dashboard/partials/execution_content.html",
        {
            "workflow_run": workflow_run,
            "workflow_events": events,
            "workflow_run_summary": workflow_run_summary,
            "active_run_statuses": ACTIVE_RUN_STATUSES,
        },
    )


@auth_required
def execution_stream(request, run_id):
    """Proxies the backend's live SSE stream for this run so the browser's
    EventSource can connect same-origin (it can't send an Authorization
    header itself)."""
    token = session_token(request)

    try:
        upstream = backend_api.stream_workflow_run(token, run_id)
    except backend_api.BackendAPIError as exc:
        payload = json.dumps({"event": "failed", "message": exc.message})
        return StreamingHttpResponse(
            f"event: failed\ndata: {payload}\n\n",
            content_type="text/event-stream",
            status=exc.status_code or 502,
        )

    def stream():
        try:
            with upstream:
                for chunk in upstream.iter_content(chunk_size=None):
                    if chunk:
                        yield chunk
        except (requests.exceptions.ChunkedEncodingError, requests.exceptions.ConnectionError):
            # The upstream connection dropped mid-stream (e.g. an idle proxy
            # timeout). End the SSE stream cleanly instead of surfacing a 500 --
            # the client's EventSource will just see the connection close.
            return

    response = StreamingHttpResponse(stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
