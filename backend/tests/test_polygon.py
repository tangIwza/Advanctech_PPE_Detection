import numpy as np
import pytest
from pydantic import ValidationError

from backend.geometry import point_in_polygon
from backend.monitor import draw_overlay
from backend.rules import evaluate_zones, inside
from backend.schemas import Zone, ZoneInput
from backend.tests.conftest import example_detections, zone_payload

L_SHAPE = [{"x":x,"y":y} for x,y in [(0.1,0.1),(0.9,0.1),(0.9,0.4),(0.4,0.4),(0.4,0.9),(0.1,0.9)]]


def polygon_zone(kind="restricted", **changes):
    value = {**zone_payload(kind=kind),"shape":"polygon","points":L_SHAPE,**changes}
    return Zone(**value,id="polygon-zone",updated_at="2026-11-12T00:00:00+00:00")


def test_concave_zone_uses_polygon_not_its_bounding_rectangle():
    result = evaluate_zones(example_detections(), [polygon_zone(),polygon_zone("ppe")], {0}, {6,9})
    assert result["zone_results"][0]["occupancy"] == 1
    assert len(result["violations"]) == 1
    assert result["violations"][0]["track_id"] == 1
    assert result["violations"][0]["kind"] == "intrusion"
    # Person 2 is inside the bounding rectangle but outside the L-shaped region.
    assert not inside(example_detections()[1],polygon_zone())


def test_polygon_boundary_winding_and_anchor():
    points=[(0.1,0.1),(0.9,0.1),(0.9,0.4),(0.4,0.4),(0.4,0.9),(0.1,0.9)]
    for vertices in (points,list(reversed(points))):
        assert point_in_polygon((0.1,0.5),vertices)
        assert point_in_polygon((0.1,0.1),vertices)
        assert point_in_polygon((0.25,0.8),vertices)
        assert not point_in_polygon((0.75,0.8),vertices)
    upper=[{"x":0,"y":0},{"x":1,"y":0},{"x":1,"y":0.6},{"x":0,"y":0.6}]
    assert not inside(example_detections()[0],polygon_zone(points=upper))
    assert inside(example_detections()[0],polygon_zone(points=upper,anchor="centroid"))


@pytest.mark.parametrize("points", [
    [{"x":0,"y":0},{"x":1,"y":1}],
    [{"x":0,"y":0},{"x":1,"y":1},{"x":0,"y":1},{"x":1,"y":0}],
    [{"x":0,"y":0},{"x":1,"y":0},{"x":1,"y":1},{"x":0,"y":0}],
    [{"x":0,"y":0},{"x":0.5,"y":0.5},{"x":1,"y":1}],
    [{"x":-0.1,"y":0},{"x":1,"y":0},{"x":1,"y":1}],
    [{"x":float("nan"),"y":0},{"x":1,"y":0},{"x":1,"y":1}],
    [{"x":0.1,"y":0.1},{"x":0.101,"y":0.1},{"x":0.1,"y":0.101}],
])
def test_invalid_polygons_cannot_be_stored(points):
    with pytest.raises(ValidationError):
        polygon_zone(points=points)


def test_api_persists_polygon_and_converts_it_back_to_rectangle(client,settings):
    value={**zone_payload(kind="restricted"),"shape":"polygon","points":L_SHAPE}
    del value["rect"]
    response=client.post("/api/zones",json=value)
    assert response.status_code == 201
    zone=response.json()
    assert zone["rect"] == {"x1":0.1,"y1":0.1,"x2":0.9,"y2":0.9}
    assert zone["points"] == L_SHAPE
    assert client.patch("/api/zones/"+zone["id"],json={"enabled":False,"expected_version":1}).status_code == 200
    from backend.store import Store
    from backend.tests.conftest import NAMES
    assert Store(settings,NAMES).zone(zone["id"]).shape == "polygon"
    changed=client.patch("/api/zones/"+zone["id"],json={"shape":"rectangle","points":None,"expected_version":2})
    assert changed.status_code == 200
    assert changed.json()["points"] is None and changed.json()["shape"] == "rectangle"
    assert client.patch("/api/zones/"+zone["id"],json={"shape":"polygon","points":L_SHAPE,"expected_version":3}).status_code == 200


def test_legacy_rectangle_records_and_invalid_geometry(client):
    legacy=ZoneInput(**zone_payload())
    assert legacy.shape == "rectangle" and legacy.points is None
    assert client.post("/api/zones",json={**zone_payload(),"points":L_SHAPE}).status_code == 422
    assert client.post("/api/zones",json={**zone_payload(),"shape":"polygon"}).status_code == 422
    assert client.post("/api/zones",json={**zone_payload(),"shape":"polygon","points":L_SHAPE[:2]}).status_code == 422


def test_snapshot_draws_polygon_edges_instead_of_a_rectangle():
    points=[{"x":0.1,"y":0.1},{"x":0.9,"y":0.1},{"x":0.1,"y":0.9}]
    zone=polygon_zone(points=points)
    image=draw_overlay(np.zeros((100,100,3),dtype=np.uint8),[],[zone],{"violations":[{"zone_id":zone.id,"track_id":1}]})
    assert image[50,50].any()  # Actual diagonal polygon boundary.
    assert not image[90,50].any()  # Bounding-box bottom edge is not a polygon edge.
