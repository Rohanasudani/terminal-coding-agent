def resolve_settings(defaults, environment, overrides):
    result = defaults
    for source in (overrides, environment):
        for key, value in source.items():
            if value:
                result[key] = value
    return result
