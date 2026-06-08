_registry: list[type] = []


def register(cls):
    _registry.append(cls)
    return cls


def get_applier(url: str):
    for applier_cls in _registry:
        instance = applier_cls()
        for pattern in instance.url_patterns:
            if pattern in url:
                return instance
    return None
