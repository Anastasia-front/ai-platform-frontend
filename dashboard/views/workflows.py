from django.contrib import messages as django_messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ..services import backend_api
from .utils import (
    CONTRACT_REVIEW_STEPS,
    JOB_VACANCY_STEPS,
    WORKFLOW_TEMPLATES,
    _endpoints_for,
    app_context,
    auth_required,
    find_contract_review_workflow,
    find_document,
    find_job_vacancy_workflow,
    find_workflow_by_name,
    find_workflow_template,
    generic_template_input,
    handle_api_error,
    next_workflow_step_id_hint,
    parse_depends_on,
    resolve_project,
    resolve_project_workflow,
    resource_slug,
    resume_screening_input,
    session_token,
    with_slug,
    with_slugs,
    workflow_template_url,
    workflow_url,
)

ACTIVE_RUN_STATUSES = {"pending", "running"}
ACTIVE_DOCUMENT_STATUSES = {"queued", "processing", "cancelling"}


def _redirect_after_workflow_run(request, project, workflow, template_key, run_result):
    run_id = run_result.get("id")

    if run_id:
        django_messages.success(
            request,
            f"Workflow run #{run_id} started.",
        )
        return redirect("dashboard:execution_detail", run_id=run_id)

    request.session["workflow_run_result"] = run_result
    django_messages.success(request, "Workflow started.")

    if template_key:
        request.session["open_workflow_template"] = template_key
        return redirect(workflow_template_url(project, workflow, template_key))

    return redirect(workflow_url(project, workflow))


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

    next_step_id_hint = None
    if active_workflow:
        try:
            workflow_steps = sorted(
                backend_api.list_workflow_steps(token, active_workflow["id"]),
                key=lambda step: step.get("step_order", 0),
            )
            next_step_id_hint = next_workflow_step_id_hint(workflow_steps)
        except backend_api.BackendAPIError as exc:
            handle_api_error(request, exc)
            context["workflow_error"] = exc.message

    workflow_templates_context = []
    for template in WORKFLOW_TEMPLATES:
        template_workflow = (
            find_workflow_by_name(workflows_payload, template["name"])
            if workflows_payload
            else None
        )

        if template.get("hidden_from_generic_loop"):
            continue

        workflow_templates_context.append(
            {
                "key": template["key"],
                "name": template["name"],
                "description": template["description"],
                "select_label": template.get("select_label", "Select document"),
                "multi_doc": template.get("multi_doc", False),
                "steps": template["steps"],
                "workflow": template_workflow,
                "setup_url": reverse(
                    "dashboard:setup_workflow_template",
                    args=[project_slug, template["key"]],
                )
                if project_slug
                else "",
                "run_url": reverse(
                    "dashboard:run_workflow_template",
                    args=[project_slug, template["key"]],
                )
                if project_slug
                else "",
            }
        )

    context.update(
        {
            "active_project_slug": project_slug,
            "workflow_project": active_project,
            "workflows": workflows_payload,
            "active_workflow": active_workflow,
            "workflow_steps": workflow_steps,
            "next_step_id_hint": next_step_id_hint,
            "project_documents": project_documents,
            "contract_review_workflow": contract_review_workflow,
            "contract_review_timeline": CONTRACT_REVIEW_STEPS,
            "job_vacancy_workflow": job_vacancy_workflow,
            "job_vacancy_timeline": JOB_VACANCY_STEPS,
            "workflow_templates": workflow_templates_context,
            "active_document_statuses": ACTIVE_DOCUMENT_STATUSES,
            "open_workflow_template": request.GET.get("template")
            or request.session.pop("open_workflow_template", ""),
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
def rename_workflow(request, project_slug, workflow_slug):
    token = session_token(request)
    project, workflow, error = resolve_project_workflow(
        token, project_slug, workflow_slug
    )
    if error:
        django_messages.error(request, error)
        return redirect("dashboard:workflows")

    name = request.POST.get("name", "").strip()
    if not name:
        django_messages.error(request, "Workflow name is required.")
        return redirect(workflow_url(project, workflow))

    try:
        workflow = backend_api.update_workflow(token, workflow["id"], name)
        django_messages.success(request, "Workflow renamed.")
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)

    return redirect(
        f"{reverse('dashboard:workflows')}?project={resource_slug(project, 'name')}"
        f"&workflow={resource_slug(workflow, 'name')}"
    )


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
        return _redirect_after_workflow_run(request, project, workflow, None, run_result)
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)

    return redirect(workflow_url(project, workflow))


@auth_required
@require_POST
def setup_contract_review(request, project_slug):
    """Compatibility wrapper preserving the legacy URL; delegates to the generic view."""
    return setup_workflow_template(request, project_slug, "contract-review")


@auth_required
@require_POST
def run_contract_review(request, project_slug):
    """Compatibility wrapper preserving the legacy URL; delegates to the generic view."""
    return run_workflow_template(request, project_slug, "contract-review")


@auth_required
@require_POST
def setup_job_vacancy(request, project_slug):
    """Compatibility wrapper preserving the legacy URL; delegates to the generic view."""
    return setup_workflow_template(request, project_slug, "job-vacancy")


@auth_required
@require_POST
def run_job_vacancy(request, project_slug):
    """Compatibility wrapper preserving the legacy URL; delegates to the generic view."""
    return run_workflow_template(request, project_slug, "job-vacancy")


@auth_required
@require_POST
def setup_workflow_template(request, project_slug, template_key):
    template = find_workflow_template(template_key)
    if not template:
        django_messages.error(request, "Unknown workflow template.")
        return redirect("dashboard:workflows")

    token = session_token(request)
    project, project_error = resolve_project(token, project_slug)
    if project_error:
        django_messages.error(request, project_error)
        return redirect("dashboard:workflows")

    try:
        workflows_payload = backend_api.list_project_workflows(token, project["id"])
        workflow = find_workflow_by_name(workflows_payload, template["name"])
        if not workflow:
            workflow = backend_api.create_workflow(
                token, project["id"], template["name"]
            )

        existing_steps = backend_api.list_workflow_steps(token, workflow["id"])
        if not existing_steps:
            created_step_ids = []
            for step in template["steps"]:
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

        django_messages.success(request, f"{template['name']} workflow is ready.")
        request.session["open_workflow_template"] = template["key"]
        return redirect(workflow_template_url(project, workflow, template["key"]))
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)
        return redirect(
            f"{reverse('dashboard:workflows')}?project={resource_slug(project, 'name')}"
            f"&template={template['key']}"
        )


@auth_required
@require_POST
def run_workflow_template(request, project_slug, template_key):
    template = find_workflow_template(template_key)
    if not template:
        django_messages.error(request, "Unknown workflow template.")
        return redirect("dashboard:workflows")

    token = session_token(request)
    project, project_error = resolve_project(token, project_slug)
    if project_error:
        django_messages.error(request, project_error)
        return redirect("dashboard:workflows")

    project_url = (
        f"{reverse('dashboard:workflows')}?project={resource_slug(project, 'name')}"
        f"&template={template['key']}"
    )

    try:
        workflows_payload = backend_api.list_project_workflows(token, project["id"])
        workflow = find_workflow_by_name(workflows_payload, template["name"])
        if not workflow:
            django_messages.error(
                request, f"Set up {template['name']} before running it."
            )
            return redirect(project_url)

        documents = backend_api.list_project_documents(token, project["id"])

        if template.get("form_type") == "vacancy":
            vacancy_link = (
                request.POST.get("vacancy_link", "").strip()
                or request.POST.get("vacancy_text", "").strip()
            )
            vacancy_context = request.POST.get("vacancy_context", "").strip()
            cv_document_id = request.POST.get("cv_document_id", "").strip()

            if not vacancy_link:
                django_messages.error(request, "Enter a vacancy link first.")
                return redirect(project_url)

            if not cv_document_id:
                django_messages.error(request, "Select a CV document first.")
                return redirect(project_url)

            cv_document = find_document(documents, cv_document_id)
            if not cv_document:
                django_messages.error(request, "Selected CV document was not found.")
                return redirect(workflow_template_url(project, workflow, template["key"]))

            if not cv_document.get("text"):
                django_messages.error(
                    request, "The selected CV document has no extracted text yet."
                )
                return redirect(workflow_template_url(project, workflow, template["key"]))

            run_result = backend_api.run_workflow(
                token,
                workflow["id"],
                template["input_builder"](
                    template, vacancy_link, vacancy_context, cv_document
                ),
            )
        elif template.get("multi_doc"):
            job_description_id = request.POST.get("job_description_id", "").strip()
            cv_document_ids = []
            for document_id in request.POST.getlist("cv_document_ids"):
                document_id = document_id.strip()
                if document_id and document_id not in cv_document_ids:
                    cv_document_ids.append(document_id)

            if not job_description_id or not cv_document_ids:
                django_messages.error(
                    request, "Select a job description and at least one CV document."
                )
                return redirect(project_url)

            if len(cv_document_ids) > 10:
                django_messages.error(
                    request, "Select no more than 10 CV documents."
                )
                return redirect(project_url)

            job_description = find_document(documents, job_description_id)
            cv_documents = [
                document
                for document_id in cv_document_ids
                if (document := find_document(documents, document_id))
            ]
            if not job_description or not cv_documents:
                django_messages.error(request, "Selected documents were not found.")
                return redirect(workflow_template_url(project, workflow, template["key"]))

            if not job_description.get("text") or any(
                not cv.get("text") for cv in cv_documents
            ):
                django_messages.error(
                    request,
                    "All selected documents must have extracted text before running.",
                )
                return redirect(workflow_template_url(project, workflow, template["key"]))

            run_result = backend_api.run_workflow(
                token,
                workflow["id"],
                resume_screening_input(template, job_description, cv_documents),
            )
        else:
            document_id = request.POST.get("document_id", "").strip()
            if not document_id:
                django_messages.error(request, "Select a project document first.")
                return redirect(project_url)

            document = find_document(documents, document_id)
            if not document:
                django_messages.error(request, "Selected document was not found.")
                return redirect(workflow_template_url(project, workflow, template["key"]))

            if not document.get("text"):
                django_messages.error(
                    request,
                    "This document has no extracted text yet. Process or re-upload it before running.",
                )
                return redirect(workflow_template_url(project, workflow, template["key"]))

            input_builder = template.get("input_builder", generic_template_input)
            run_result = backend_api.run_workflow(
                token,
                workflow["id"],
                input_builder(template, document),
            )

        return _redirect_after_workflow_run(
            request,
            project,
            workflow,
            template["key"],
            run_result,
        )
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)
        return redirect(
            f"{reverse('dashboard:workflows')}?project={resource_slug(project, 'name')}"
            f"&template={template['key']}"
        )
