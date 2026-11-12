"""Normalized simple-polygon geometry shared by validation and zone rules."""

EPSILON = 1e-9


def cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def on_segment(point, a, b):
    return abs(cross(a, b, point)) <= EPSILON and (
        min(a[0], b[0]) - EPSILON <= point[0] <= max(a[0], b[0]) + EPSILON
        and min(a[1], b[1]) - EPSILON <= point[1] <= max(a[1], b[1]) + EPSILON
    )


def segments_intersect(a, b, c, d):
    ab_c, ab_d, cd_a, cd_b = cross(a, b, c), cross(a, b, d), cross(c, d, a), cross(c, d, b)
    return ((ab_c > EPSILON and ab_d < -EPSILON or ab_c < -EPSILON and ab_d > EPSILON)
            and (cd_a > EPSILON and cd_b < -EPSILON or cd_a < -EPSILON and cd_b > EPSILON)) or (
        on_segment(c, a, b) or on_segment(d, a, b) or on_segment(a, c, d) or on_segment(b, c, d)
    )


def polygon_area(points):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(points, points[1:] + points[:1]))) / 2


def validate_polygon(points):
    if not 3 <= len(points) <= 64:
        raise ValueError("Polygon requires between 3 and 64 points")
    for i, a in enumerate(points):
        if any(abs(a[0] - b[0]) < 1e-7 and abs(a[1] - b[1]) < 1e-7 for b in points[i + 1:]):
            raise ValueError("Polygon points must be distinct; do not repeat the first point")
        for j in range(i + 1, len(points)):
            if j == i + 1 or i == 0 and j == len(points) - 1:
                continue
            if segments_intersect(a, points[(i + 1) % len(points)], points[j], points[(j + 1) % len(points)]):
                raise ValueError("Polygon edges must not cross or touch other edges")
    if polygon_area(points) < 0.000025:
        raise ValueError("Polygon is too small or its points are collinear")


def point_in_polygon(point, points):
    """Ray casting, including boundary points, for convex or concave simple polygons."""
    inside = False
    x, y = point
    for a, b in zip(points, points[1:] + points[:1]):
        if on_segment(point, a, b):
            return True
        if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
            inside = not inside
    return inside
