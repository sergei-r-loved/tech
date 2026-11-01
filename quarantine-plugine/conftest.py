from pathlib import Path
import warnings

import pytest

pytest_plugins = ["pytester"]

PATH_TO_QUARANTINE = Path(__file__).resolve().parent / "quarantine.txt"


def get_quarantine_list(source: Path) -> set[str] | None:
    try:
        lines = source.read_text(encoding="utf-8").splitlines()
    except OSError, UnicodeDecodeError:
        return None
    lines = [line.strip() for line in lines]
    return {s for s in lines if s and not s.startswith("#")}


def pytest_collection_modifyitems(session, config, items):
    quarantinied = get_quarantine_list(PATH_TO_QUARANTINE) or set()
    matched = set()
    for item in items:
        base = item.nodeid.split("[")[
            0
        ]  # test_p в файле накрывает test_p[a], test_p[b]
        hit = (
            item.nodeid
            if item.nodeid in quarantinied
            else base
            if base in quarantinied
            else None
        )

        if hit:
            matched.add(hit)
            item.add_marker(pytest.mark.xfail(reason="Quarantined", strict=False))

    collected_files = {item.nodeid.split("::")[0] for item in items}
    for missing in quarantinied - matched:
        if missing.split("::")[0] in collected_files:
            warnings.warn(f"quarantine: {missing} не найден — проверь путь от rootdir")
