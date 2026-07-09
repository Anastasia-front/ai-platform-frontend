from django.contrib import messages as django_messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..services import backend_api
from .utils import (
    CONTRACT_REVIEW_NAME,
    CONTRACT_REVIEW_STEPS,
    JOB_VACANCY_NAME,
    JOB_VACANCY_STEPS,
    _endpoints_for,
    app_context,
    auth_required,
    contract_review_input,
    find_contract_review_workflow,
    find_document,
    find_job_vacancy_workflow,
    handle_api_error,
    job_vacancy_input,
    parse_contract_review_output,
    parse_depends_on,
    parse_job_vacancy_output,
    resolve_project,
    resolve_project_workflow,
    resource_slug,
    session_token,
    with_slug,
    with_slugs,
    workflow_template_url,
    workflow_url,
)


@auth_required
def workflows(request):
    token = session_token(request)
    context = app_context(request, endpoints=_endpoints_for("Workflows"))
    projects_payload = context["projects"]
    active_project = None
    active_workflow = None
    workflows_payload = []
    workflow_steps = []
    project_documents = []
    contract_review_workflow = None
    job_vacancy_workflow = None

    project_slug = request.GET.get("project") or (
        projects_payload[0]["slug"] if projects_payload else ""
    )
    workflow_slug = request.GET.get("workflow", "")

    if project_slug:
        project, project_error = resolve_project(token, project_slug)
        if project_error:
            context["workflow_error"] = project_error
        else:
            active_project = with_slug(project, "name")
            try:
                workflows_payload = with_slugs(
                    backend_api.list_project_workflows(token, project["id"]),
                    "name",
                )
                project_documents = backend_api.list_project_documents(
                    token, project["id"]
                )
            except backend_api.BackendAPIError as exc:
                handle_api_error(request, exc)
                context["workflow_error"] = exc.message

    if workflows_payload:
        contract_review_workflow = find_contract_review_workflow(workflows_payload)
        job_vacancy_workflow = find_job_vacancy_workflow(workflows_payload)
        if not workflow_slug:
            workflow_slug = workflows_payload[0]["slug"]
        active_workflow = next(
            (
                workflow
                for workflow in workflows_payload
                if workflow["slug"] == workflow_slug
            ),
            None,
        )

    if active_workflow:
        try:
            workflow_steps = sorted(
                backend_api.list_workflow_steps(token, active_workflow["id"]),
                key=lambda step: step.get("step_order", 0),
            )
        except backend_api.BackendAPIError as exc:
            handle_api_error(request, exc)
            context["workflow_error"] = exc.message

    contract_review_result = request.session.get("contract_review_result")
    if contract_review_result and contract_review_result.get("raw_output"):
        contract_review_result = {
            **contract_review_result,
            "structured": parse_contract_review_output(
                contract_review_result["raw_output"]
            ),
        }
        request.session["contract_review_result"] = contract_review_result

    job_vacancy_result = request.session.get("job_vacancy_result")
    if job_vacancy_result and job_vacancy_result.get("raw_output"):
        job_vacancy_result = {
            **job_vacancy_result,
            "structured": parse_job_vacancy_output(job_vacancy_result["raw_output"]),
        }
        request.session["job_vacancy_result"] = job_vacancy_result

    context.update(
        {
            "active_project_slug": project_slug,
            "workflow_project": active_project,
            "workflows": workflows_payload,
            "active_workflow": active_workflow,
            "workflow_steps": workflow_steps,
            "project_documents": project_documents,
            "contract_review_workflow": contract_review_workflow,
            "contract_review_timeline": CONTRACT_REVIEW_STEPS,
            "contract_review_result": contract_review_result,
            "job_vacancy_workflow": job_vacancy_workflow,
            "job_vacancy_timeline": JOB_VACANCY_STEPS,
            "job_vacancy_result": job_vacancy_result,
            "open_workflow_template": request.session.pop(
                "open_workflow_template",
                request.GET.get("template", ""),
            ),
            "run_result": request.session.pop("workflow_run_result", None),
        }
    )
    return render(request, "dashboard/utility/workflows.html", context)


@auth_required
@require_POST
def create_workflow(request, project_slug):
    token = session_token(request)
    project, project_error = resolve_project(token, project_slug)
    if project_error:
        django_messages.error(request, project_error)
        return redirect("dashboard:workflows")

    name = request.POST.get("name", "").strip()
    if not name:
        django_messages.error(request, "Workflow name is required.")
        return redirect(f"{reverse('dashboard:workflows')}?project={project_slug}")

    try:
        workflow = backend_api.create_workflow(token, project["id"], name)
        django_messages.success(request, "Workflow created.")
        return redirect(
            f"{reverse('dashboard:workflows')}?project={resource_slug(project, 'name')}"
            f"&workflow={resource_slug(workflow, 'name')}"
        )
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)
        return redirect(f"{reverse('dashboard:workflows')}?project={project_slug}")


@auth_required
@require_POST
def delete_workflow(request, project_slug, workflow_slug):
    token = session_token(request)
    project, workflow, error = resolve_project_workflow(
        token, project_slug, workflow_slug
    )
    if error:
        django_messages.error(request, error)
        return redirect("dashboard:workflows")

    try:
        backend_api.delete_workflow(token, workflow["id"])
        django_messages.success(request, "Workflow deleted.")
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)

    return redirect(
        f"{reverse('dashboard:workflows')}?project={resource_slug(project, 'name')}"
    )


@auth_required
@require_POST
def create_workflow_step(request, project_slug, workflow_slug):
    token = session_token(request)
    project, workflow, error = resolve_project_workflow(
        token, project_slug, workflow_slug
    )
    if error:
        django_messages.error(request, error)
        return redirect("dashboard:workflows")

    depends_on = parse_depends_on(request.POST.get("depends_on", ""))
    try:
        backend_api.create_workflow_step(
            token,
            workflow["id"],
            int(request.POST.get("step_order") or 1),
            request.POST.get("name", "").strip(),
            request.POST.get("prompt_template", "").strip(),
            depends_on=depends_on,
            condition=request.POST.get("condition", "").strip(),
        )
        django_messages.success(request, "Workflow step added.")
    except (ValueError, backend_api.BackendAPIError) as exc:
        if isinstance(exc, backend_api.BackendAPIError):
            handle_api_error(request, exc)
            django_messages.error(request, exc.message)
        else:
            django_messages.error(request, "Step order must be a number.")

    return redirect(workflow_url(project, workflow))


@auth_required
@require_POST
def delete_workflow_step(request, project_slug, workflow_slug, step_id):
    token = session_token(request)
    project, workflow, error = resolve_project_workflow(
        token, project_slug, workflow_slug
    )
    if error:
        django_messages.error(request, error)
        return redirect("dashboard:workflows")

    try:
        backend_api.delete_workflow_step(token, step_id)
        django_messages.success(request, "Workflow step deleted.")
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)

    return redirect(workflow_url(project, workflow))


@auth_required
@require_POST
def run_workflow(request, project_slug, workflow_slug):
    token = session_token(request)
    project, workflow, error = resolve_project_workflow(
        token, project_slug, workflow_slug
    )
    if error:
        django_messages.error(request, error)
        return redirect("dashboard:workflows")

    user_input = request.POST.get("input", "").strip()
    if not user_input:
        django_messages.error(request, "Workflow input is required.")
        return redirect(workflow_url(project, workflow))

    try:
        run_result = backend_api.run_workflow(
            token,
            workflow["id"],
            user_input,
        )
        if run_result.get("id"):
            return redirect("dashboard:execution_detail", run_id=run_result["id"])
        request.session["workflow_run_result"] = run_result
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)

    return redirect(workflow_url(project, workflow))


@auth_required
@require_POST
def setup_contract_review(request, project_slug):
    token = session_token(request)
    project, project_error = resolve_project(token, project_slug)
    if project_error:
        django_messages.error(request, project_error)
        return redirect("dashboard:workflows")

    try:
        workflows_payload = backend_api.list_project_workflows(token, project["id"])
        workflow = find_contract_review_workflow(workflows_payload)
        if not workflow:
            workflow = backend_api.create_workflow(
                token, project["id"], CONTRACT_REVIEW_NAME
            )

        existing_steps = backend_api.list_workflow_steps(token, workflow["id"])
        if not existing_steps:
            created_step_ids = []
            for step in CONTRACT_REVIEW_STEPS:
                depends_on = [created_step_ids[-1]] if created_step_ids else []
                created = backend_api.create_workflow_step(
                    token,
                    workflow["id"],
                    step["order"],
                    step["name"],
                    step["prompt"],
                    depends_on=depends_on,
                )
                created_step_ids.append(created["id"])

        django_messages.success(request, "Contract review workflow is ready.")
        request.session["open_workflow_template"] = "contract-review"
        return redirect(workflow_url(project, workflow))
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)
        return redirect(
            f"{reverse('dashboard:workflows')}?project={resource_slug(project, 'name')}"
        )


@auth_required
@require_POST
def run_contract_review(request, project_slug):
    token = session_token(request)
    project, project_error = resolve_project(token, project_slug)
    if project_error:
        django_messages.error(request, project_error)
        return redirect("dashboard:workflows")

    document_id = request.POST.get("document_id", "").strip()
    if not document_id:
        django_messages.error(request, "Select a project document first.")
        return redirect(
            f"{reverse('dashboard:workflows')}?project={resource_slug(project, 'name')}"
        )

    try:
        workflows_payload = backend_api.list_project_workflows(token, project["id"])
        workflow = find_contract_review_workflow(workflows_payload)
        if not workflow:
            django_messages.error(request, "Set up Contract review before running it.")
            return redirect(
                f"{reverse('dashboard:workflows')}?project={resource_slug(project, 'name')}"
            )

        documents = backend_api.list_project_documents(token, project["id"])
        document = next(
            (item for item in documents if str(item.get("id")) == document_id),
            None,
        )
        if not document:
            django_messages.error(request, "Selected document was not found.")
            return redirect(workflow_url(project, workflow))

        if not document.get("text"):
            django_messages.error(
                request,
                "This document has no extracted text yet. Process or re-upload it before review.",
            )
            return redirect(workflow_url(project, workflow))

        run_result = backend_api.run_workflow(
            token,
            workflow["id"],
            contract_review_input(document),
        )
        structured_result = parse_contract_review_output(run_result.get("output", ""))
        request.session["contract_review_result"] = {
            "document_name": document.get("filename", "Selected document"),
            "workflow_name": workflow.get("name", CONTRACT_REVIEW_NAME),
            "created_at": timezone.now().isoformat(timespec="seconds"),
            "raw_output": run_result.get("output", ""),
            "structured": structured_result,
        }
        django_messages.success(request, "Contract review completed and saved.")
        if run_result.get("id"):
            return redirect("dashboard:execution_detail", run_id=run_result["id"])
        return redirect(workflow_url(project, workflow))
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)
        return redirect(
            f"{reverse('dashboard:workflows')}?project={resource_slug(project, 'name')}"
        )


@auth_required
@require_POST
def setup_job_vacancy(request, project_slug):
    token = session_token(request)
    project, project_error = resolve_project(token, project_slug)
    if project_error:
        django_messages.error(request, project_error)
        return redirect("dashboard:workflows")

    try:
        workflows_payload = backend_api.list_project_workflows(token, project["id"])
        workflow = find_job_vacancy_workflow(workflows_payload)
        if not workflow:
            workflow = backend_api.create_workflow(
                token, project["id"], JOB_VACANCY_NAME
            )

        existing_steps = backend_api.list_workflow_steps(token, workflow["id"])
        if not existing_steps:
            created_step_ids = []
            for step in JOB_VACANCY_STEPS:
                depends_on = [created_step_ids[-1]] if created_step_ids else []
                created = backend_api.create_workflow_step(
                    token,
                    workflow["id"],
                    step["order"],
                    step["name"],
                    step["prompt"],
                    depends_on=depends_on,
                )
                created_step_ids.append(created["id"])

        django_messages.success(request, "Vacancy helper workflow is ready.")
        request.session["open_workflow_template"] = "job-vacancy"
        return redirect(workflow_url(project, workflow))
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)
        return redirect(
            f"{reverse('dashboard:workflows')}?project={resource_slug(project, 'name')}"
        )


@auth_required
@require_POST
def run_job_vacancy(request, project_slug):
    token = session_token(request)
    project, project_error = resolve_project(token, project_slug)
    if project_error:
        django_messages.error(request, project_error)
        return redirect("dashboard:workflows")

    vacancy_link = (
        request.POST.get("vacancy_link", "").strip()
        or request.POST.get("vacancy_text", "").strip()
    )
    vacancy_context = request.POST.get("vacancy_context", "").strip()
    cv_document_id = request.POST.get("cv_document_id", "").strip()

    if not vacancy_link:
        django_messages.error(request, "Enter a vacancy link first.")
        return redirect(
            f"{reverse('dashboard:workflows')}?project={resource_slug(project, 'name')}&template=job-vacancy"
        )

    if not cv_document_id:
        django_messages.error(request, "Select a CV document first.")
        return redirect(
            f"{reverse('dashboard:workflows')}?project={resource_slug(project, 'name')}&template=job-vacancy"
        )

    try:
        workflows_payload = backend_api.list_project_workflows(token, project["id"])
        workflow = find_job_vacancy_workflow(workflows_payload)
        if not workflow:
            django_messages.error(
                request, "Set up Vacancy helper before running it."
            )
            return redirect(
                f"{reverse('dashboard:workflows')}?project={resource_slug(project, 'name')}"
            )

        documents = backend_api.list_project_documents(token, project["id"])
        cv_document = find_document(documents, cv_document_id)
        if not cv_document:
            django_messages.error(request, "Selected CV document was not found.")
            return redirect(workflow_template_url(project, workflow, "job-vacancy"))

        if not cv_document.get("text"):
            django_messages.error(
                request, "The selected CV document has no extracted text yet."
            )
            return redirect(workflow_template_url(project, workflow, "job-vacancy"))

        run_result = backend_api.run_workflow(
            token,
            workflow["id"],
            job_vacancy_input(
                vacancy_link=vacancy_link,
                vacancy_context=vacancy_context,
                cv_document=cv_document,
            ),
        )
        request.session["job_vacancy_result"] = {
            "vacancy_source": vacancy_link,
            "cv_document_name": cv_document.get("filename", "Selected CV"),
            "workflow_name": workflow.get("name", JOB_VACANCY_NAME),
            "created_at": timezone.now().isoformat(timespec="seconds"),
            "raw_output": run_result.get("output", ""),
            "structured": parse_job_vacancy_output(run_result.get("output", "")),
        }
        django_messages.success(request, "Vacancy helper completed and saved.")
        if run_result.get("id"):
            return redirect("dashboard:execution_detail", run_id=run_result["id"])
        return redirect(workflow_url(project, workflow))
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)
        return redirect(
            f"{reverse('dashboard:workflows')}?project={resource_slug(project, 'name')}"
        )
