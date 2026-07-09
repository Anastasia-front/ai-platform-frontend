from django.shortcuts import render

from ..services import backend_api
from .utils import (
    _endpoints_for,
    app_context,
    auth_required,
    handle_api_error,
    session_token,
    summarize_workflow_run,
    workflow_projects_by_id,
)

@auth_required
def executions(request):
    context = app_context(request, endpoints=_endpoints_for("Executions"))
    try:
        workflow_runs = backend_api.list_workflow_runs(session_token(request))
        workflow_project_map = workflow_projects_by_id(
            session_token(request),
            context.get("projects", []),
        )
        for run in workflow_runs:
            run["project"] = workflow_project_map.get(run.get("workflow_id"))

        active_project = request.GET.get("project", "")
        if active_project:
            workflow_runs = [
                run
                for run in workflow_runs
                if run.get("project", {}).get("slug") == active_project
            ]

        context.update(
            {
                "workflow_runs": workflow_runs,
                "execution_project_tabs": context.get("projects", []),
                "active_execution_project": active_project,
            }
        )
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        context["executions_error"] = exc.message
        context["workflow_runs"] = []
        context["execution_project_tabs"] = []

    return render(request, "dashboard/utility/executions.html", context)


@auth_required
def execution_detail(request, run_id):
    context = app_context(request, endpoints=_endpoints_for("Executions"))
    try:
        workflow_run = backend_api.get_workflow_run(session_token(request), run_id)
        events = backend_api.list_workflow_run_events(session_token(request), run_id)
        context.update(
            {
                "workflow_run": workflow_run,
                "workflow_events": events,
                "workflow_run_summary": summarize_workflow_run(workflow_run, events),
            }
        )
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        context["executions_error"] = exc.message

    return render(request, "dashboard/utility/execution_detail.html", context)


