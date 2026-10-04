"""The sidebar — one definition, read by base.html."""

from dataclasses import dataclass

from starlette.requests import Request


@dataclass(frozen=True)
class NavItem:
    label: str
    path: str
    icon: str
    group: str
    active: bool = False


_ITEMS = (
    ("Radar", "/", "mdi-radar", "Signals"),
    ("Signals", "/signal", "mdi-pulse", "Signals"),
    ("Engines", "/engine", "mdi-engine-outline", "Signals"),
    ("Screener", "/screen", "mdi-filter-variant", "Signals"),
    ("Securities", "/security", "mdi-format-list-bulleted", "Universe"),
    ("Ownership", "/ownership", "mdi-chart-pie-outline", "Universe"),
    ("Exclusions", "/exclusion", "mdi-cancel", "Universe"),
    ("Data health", "/health", "mdi-database-check-outline", "Data"),
)


def nav_items(request: Request) -> list[NavItem]:
    path = request.url.path
    return [
        NavItem(
            label,
            item_path,
            icon,
            group,
            path == item_path if item_path == "/" else path == item_path or path.startswith(item_path + "/"),
        )
        for label, item_path, icon, group in _ITEMS
    ]
