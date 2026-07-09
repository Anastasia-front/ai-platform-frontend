from django.shortcuts import render

from .utils import MAIN_ENDPOINTS, app_context, auth_required

@auth_required
def settings_function(request):
    return render(
        request,
        "dashboard/utility/settings.html",
        app_context(request, endpoints=MAIN_ENDPOINTS),
    )

