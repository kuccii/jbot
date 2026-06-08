from pathlib import Path


def extract_text(cv_path: str) -> str:
    path = Path(cv_path)
    if not path.exists():
        raise FileNotFoundError(f"CV not found: {cv_path}")
    if path.suffix == ".txt":
        return path.read_text(encoding="utf-8")
    else:
        raise ValueError(f"Unsupported format: {path.suffix}. Supported: .txt")
