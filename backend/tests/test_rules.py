from dataclasses import replace
import numpy as np
import pytest
from pydantic import ValidationError

from backend.monitor import Monitor
from backend.rules import Detection, PersonTracker, associate_ppe, classify_name, evaluate_zones, inside
from backend.schemas import Rect, Zone, ZoneInput
from backend.store import Store
from backend.tests.conftest import FakeDetector, NAMES, example_detections, zone_payload


def make_zone(kind="ppe", **changes):
    return Zone(**{**zone_payload(kind=kind), **changes}, id="zone-1", updated_at="2026-11-12T00:00:00+00:00")


def test_per_person_ppe_and_intrusion():
    ppe = make_zone()
    restricted = make_zone("restricted").model_copy(update={"id": "zone-2"})
    result = evaluate_zones(example_detections(), [ppe, restricted], {0}, {6,9})
    missing = [item for item in result["violations"] if item["kind"] == "missing_ppe"]
    assert len(missing) == 1 and missing[0]["track_id"] == 2
    assert missing[0]["missing_class_ids"] == [9]
    assert len([item for item in result["violations"] if item["kind"] == "intrusion"]) == 2
    assert result["zone_results"][0]["occupancy"] == 2


def test_ppe_outside_person_cannot_satisfy_rule():
    items = example_detections()[:2] + [Detection(6, "helmet", .9, (.43,.01,.55,.08))]
    result = evaluate_zones(items, [make_zone(required_class_ids=[6])], {0}, {6,9})
    assert len(result["violations"]) == 2


def test_a_ppe_box_has_only_one_owner_even_for_overlapping_people():
    people = [Detection(0,"person",.9,(.1,.1,.7,.9),1), Detection(0,"person",.9,(.2,.1,.8,.9),2)]
    assigned = associate_ppe(people, [Detection(6,"helmet",.9,(.3,.12,.4,.2))])
    assert sum(6 in values for values in assigned.values()) == 1


def test_feet_and_centroid_anchors_are_distinct():
    person = example_detections()[0]
    zone = make_zone(rect=Rect(x1=0,y1=.8,x2=.5,y2=1))
    assert inside(person, zone)
    assert not inside(person, zone.model_copy(update={"anchor": "centroid"}))


def test_disabled_zones_do_not_alert():
    result = evaluate_zones(example_detections(), [make_zone(enabled=False)], {0}, {6,9})
    assert not result["violations"] and result["zone_results"][0]["occupancy"] == 0


@pytest.mark.parametrize("box", [dict(x1=.8,y1=0,x2=.2,y2=1),dict(x1=-.1,y1=0,x2=1,y2=1),dict(x1=0,y1=0,x2=float('nan'),y2=1),dict(x1=0,y1=0,x2=0,y2=1)])
def test_invalid_rectangles(box):
    with pytest.raises(ValidationError):
        Rect(**box)


def test_tracker_immediately_assigns_unique_stable_ids():
    tracker = PersonTracker()
    people = example_detections()[:2]
    tracker.update(people, 0)
    ids = [item.track_id for item in people]
    next_frame = example_detections()[:2]
    tracker.update(next_frame, .1)
    assert [item.track_id for item in next_frame] == ids
    assert len(set(ids)) == 2


def test_body_parts_are_not_wearable_ppe():
    assert classify_name("foot") == "body_part"
    assert classify_name("ear-mufs") == "ppe"
    assert classify_name("person") == "person"
    assert classify_name("no-helmet") == "other"


def test_alert_gate_deduplicates_and_closes_only_after_grace(settings, monkeypatch):
    store = Store(settings, NAMES)
    store.create_zone(ZoneInput(**zone_payload()))
    monitor = Monitor(settings, FakeDetector(settings), store)
    monitor.source = {"id": "test-video", "name": "Fixture", "kind": "video", "loop": False}
    frame = np.zeros((120,160,3), dtype=np.uint8)
    clock = [0.0]
    monkeypatch.setattr('backend.monitor.time.monotonic', lambda: clock[0])
    monitor._evaluate(frame, example_detections(), emit=True)
    assert store.alerts()["total"] == 1
    clock[0] = .1
    monitor._evaluate(frame, example_detections(), emit=True)
    assert store.alerts()["total"] == 1
    equipped = example_detections() + [Detection(9,"safety-vest",.9,(.65,.3,.85,.55))]
    clock[0] = .2
    monitor._evaluate(frame, equipped, emit=True)
    assert len(monitor.gates) == 1
    clock[0] = 2
    monitor._evaluate(frame, equipped, emit=True)
    assert not monitor.gates and store.alerts()["items"][0]["resolved_at"]


def test_pruning_preserves_shared_snapshots(settings):
    store = Store(replace(settings, max_alerts=1), NAMES)
    path = store.snapshots / 'shared.jpg'
    path.write_bytes(b'jpeg')
    payload = {"source_id": "test", "zone_id": "zone", "kind": "intrusion", "source_name": "Test", "missing_classes": []}
    store.add_alert(payload, path.name)
    store.add_alert(payload, path.name)
    store.prune()
    assert store.alerts()["total"] == 1
    assert path.exists()
