from settings import resolve_settings


def create_service(defaults, environment, overrides):
    return {"settings": resolve_settings(defaults, environment, {})}
