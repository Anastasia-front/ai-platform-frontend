from django.shortcuts import render

from .utils import AGENT_MODES, WORKFLOW_TEMPLATES, app_context, auth_required


def guide_template_steps(template):
    input_steps = []

    if template["key"] == "contract-review":
        input_steps = ["Set up template", template.get("select_label", "Select document")]
    elif template["key"] == "resume-screening":
        input_steps = ["Job description document", "CV documents"]
    elif template["key"] == "job-vacancy":
        input_steps = [template.get("select_label", "Select document")]

    return [
        {"name": step_name}
        for step_name in input_steps
    ] + [{"name": step["name"]} for step in template["steps"]]


def guide_workflow_templates():
    return [
        template | {"guide_steps": guide_template_steps(template)}
        for template in WORKFLOW_TEMPLATES
    ]


@auth_required
def guide(request):
    return render(
        request,
        "dashboard/utility/guide.html",
        app_context(request)
        | {
            "guide_agent_modes": AGENT_MODES,
            "guide_workflow_templates": guide_workflow_templates(),
        },
    )
