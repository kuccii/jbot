_registry: dict[str, type] = {}


def register(name: str):
    def decorator(cls):
        _registry[name] = cls
        cls.name = name
        return cls
    return decorator


def get_scraper(name: str):
    if name not in _registry:
        raise ValueError(f"Unknown scraper: {name}. Available: {list(_registry.keys())}")
    return _registry[name]()


def list_scrapers() -> list[str]:
    return list(_registry.keys())
