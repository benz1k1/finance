"""
Inline-SVG line charts for the server-rendered pages: no chart library is vendored, and a line of
a few hundred points is a path string. ``line_chart`` scales several series onto one plot and
returns what the template needs: paths, axis ticks, end labels and the legend. Pure, so it is
unit-tested on synthetic series.
"""

from dataclasses import dataclass, field
from datetime import date

# Fixed categorical order (never cycled past eight: the page folds the rest away).
PALETTE = ("#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed", "#0891b2", "#be185d", "#4d7c0f")

WIDTH, HEIGHT = 760, 260
PAD_LEFT, PAD_RIGHT, PAD_TOP, PAD_BOTTOM = 44, 150, 12, 26


@dataclass
class Series:
    name: str
    points: list[tuple[date, float]]
    color: str = ""
    path: str = ""
    end_x: float = 0.0
    end_y: float = 0.0
    last: float | None = None


@dataclass
class Chart:
    width: int
    height: int
    series: list[Series]
    x_ticks: list[tuple[float, str]] = field(default_factory=list)
    y_ticks: list[tuple[float, str]] = field(default_factory=list)
    zero_y: float | None = None
    plot: dict[str, float] = field(default_factory=dict)


def _nice_step(span: float, target: int = 5) -> float:
    raw = span / max(1, target)
    magnitude = 10 ** int(f"{raw:e}".split("e")[1])
    for factor in (1, 2, 2.5, 5, 10):
        if raw <= factor * magnitude:
            return factor * magnitude
    return 10 * magnitude


def _smooth_path(points: list[tuple[float, float]]) -> str:
    """A Catmull-Rom spline through the points as cubic Béziers: it passes through every data
    point, so the curve never invents a value, only rounds the corners between them."""
    if len(points) < 3:
        return " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(points))
    out = [f"M{points[0][0]:.1f},{points[0][1]:.1f}"]
    for i in range(len(points) - 1):
        p0 = points[i - 1] if i > 0 else points[i]
        p1, p2 = points[i], points[i + 1]
        p3 = points[i + 2] if i + 2 < len(points) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        out.append(f"C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}")
    return " ".join(out)


def line_chart(
    named: dict[str, list[tuple[date, float]]],
    *,
    unit: str = "",
    zero_line: bool = True,
    smooth: bool = False,
) -> Chart:
    series = [Series(name, pts) for name, pts in named.items() if pts]
    chart = Chart(
        WIDTH,
        HEIGHT,
        series,
        plot={"x0": PAD_LEFT, "x1": WIDTH - PAD_RIGHT, "y0": PAD_TOP, "y1": HEIGHT - PAD_BOTTOM},
    )
    if not series:
        return chart
    dates = sorted({d for s in series for d, _ in s.points})
    values = [v for s in series for _, v in s.points]
    lo, hi = min(values), max(values)
    if zero_line:
        lo, hi = min(lo, 0.0), max(hi, 0.0)
    if hi == lo:
        hi, lo = hi + 1, lo - 1
    step = _nice_step(hi - lo)
    lo, hi = step * (lo // step), step * (-(-hi // step))
    x0, x1, y0, y1 = chart.plot["x0"], chart.plot["x1"], chart.plot["y0"], chart.plot["y1"]
    first, last = dates[0].toordinal(), dates[-1].toordinal()
    span = max(1, last - first)

    def x_of(d: date) -> float:
        return x0 + (x1 - x0) * (d.toordinal() - first) / span

    def y_of(v: float) -> float:
        return y1 - (y1 - y0) * (v - lo) / (hi - lo)

    for i, s in enumerate(series):
        s.color = PALETTE[i % len(PALETTE)]
        pts = sorted(s.points)
        scaled = [(x_of(d), y_of(v)) for d, v in pts]
        if smooth:
            s.path = _smooth_path(scaled)
        else:
            s.path = " ".join(f"{'M' if j == 0 else 'L'}{x:.1f},{y:.1f}" for j, (x, y) in enumerate(scaled))
        s.end_x, s.end_y, s.last = x_of(pts[-1][0]), y_of(pts[-1][1]), pts[-1][1]
    # spread end labels so they do not overlap
    ordered = sorted(series, key=lambda s: s.end_y)
    for prev, cur in zip(ordered, ordered[1:], strict=False):
        if cur.end_y - prev.end_y < 12:
            cur.end_y = prev.end_y + 12
    tick = lo
    while tick <= hi + 1e-9:
        chart.y_ticks.append((round(y_of(tick), 1), f"{tick:g}{unit}"))
        tick += step
    if zero_line and lo <= 0 <= hi:
        chart.zero_y = round(y_of(0.0), 1)
    years = sorted({d.year for d in dates})
    if len(years) <= 2:
        candidates = [d for d in dates if d.day <= 7 and d.month % 3 == 1]
        seen, picked = set(), []
        for d in candidates:
            if (d.year, d.month) not in seen:
                seen.add((d.year, d.month))
                picked.append(d)
        chart.x_ticks = [(round(x_of(d), 1), d.strftime("%b %y")) for d in picked]
    else:
        chart.x_ticks = [(round(x_of(date(y, 1, 1)), 1), str(y)) for y in years if date(y, 1, 1) >= dates[0]]
    return chart


def donut_dasharray(fractions: list[float], gap: float = 1.5) -> list[tuple[str, float]]:
    """stroke-dasharray / stroke-dashoffset pairs for a circle of circumference 100 (r = 15.9155),
    one per slice, with a small surface gap between slices."""
    out, offset = [], 25.0
    for frac in fractions:
        length = max(0.0, 100 * frac - gap)
        out.append((f"{length:.2f} {100 - length:.2f}", round(offset - gap / 2, 2)))
        offset -= 100 * frac
    return out


@dataclass
class Sparkline:
    width: int
    height: int
    path: str
    area: str
    first: float
    last: float
    low: float
    high: float
    low_x: float
    high_x: float
    low_y: float
    high_y: float
    change_pct: float
    first_date: date
    last_date: date
    up: bool
    points: list[tuple[float, float, str, float]] = field(
        default_factory=list
    )  # x, y, iso date, close — for the hover


def sparkline(
    points: list[tuple[date, float]], *, width: int = 640, height: int = 72, pad: int = 4
) -> Sparkline | None:
    """A compact single-series line with no axes: the path, a filled area under it, and where the
    low and high sit so the template can label them. Oldest point on the left."""
    pts = sorted(points)
    if len(pts) < 2:
        return None
    values = [v for _, v in pts]
    lo, hi = min(values), max(values)
    span_v = (hi - lo) or 1.0
    first_day, last_day = pts[0][0].toordinal(), pts[-1][0].toordinal()
    span_d = max(1, last_day - first_day)

    def x_of(d: date) -> float:
        return pad + (width - 2 * pad) * (d.toordinal() - first_day) / span_d

    def y_of(v: float) -> float:
        return height - pad - (height - 2 * pad) * (v - lo) / span_v

    scaled = [(x_of(d), y_of(v)) for d, v in pts]
    path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(scaled))
    area = f"{path} L{scaled[-1][0]:.1f},{height - pad} L{scaled[0][0]:.1f},{height - pad} Z"
    low_i = values.index(lo)
    high_i = values.index(hi)
    return Sparkline(
        width,
        height,
        path,
        area,
        values[0],
        values[-1],
        lo,
        hi,
        round(scaled[low_i][0], 1),
        round(scaled[high_i][0], 1),
        round(scaled[low_i][1], 1),
        round(scaled[high_i][1], 1),
        round((values[-1] / values[0] - 1) * 100, 2) if values[0] else 0.0,
        pts[0][0],
        pts[-1][0],
        values[-1] >= values[0],
        [(round(x, 1), round(y, 1), d.isoformat(), v) for (x, y), (d, v) in zip(scaled, pts, strict=True)],
    )
