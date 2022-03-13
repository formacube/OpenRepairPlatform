from django.conf import settings


def site_title(request):
    return {"site_title": "RepairCafés.ch"}


def settings_variables(request):
    return {'LOCATION': settings.LOCATION}
