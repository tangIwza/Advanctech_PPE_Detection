"""Pure, deterministic zone rules. All coordinates are normalized xyxy."""

from dataclasses import dataclass
import math

from .schemas import Zone

PERSON_NAMES = {"person", "people", "human", "pedestrian", "worker"}
BODY_PARTS = {"ear", "face", "foot", "feet", "hands", "hand", "head"}
PPE_NAMES = {
    "ear-mufs", "earmuffs", "ear-muffs", "face-mask", "mask", "glasses",
    "safety-glasses", "goggles", "gloves", "helmet", "hardhat", "hard-hat",
    "shoes", "safety-shoes", "safety-suit", "safety-vest", "vest",
    "face-guard", "medical-suit", "ear-protection", "hearing-protection",
}


def classify_name(name):
    name = name.lower().strip().replace("_", "-").replace(" ", "-")
    return "person" if name in PERSON_NAMES else "body_part" if name in BODY_PARTS else "ppe" if name in PPE_NAMES else "other"


@dataclass
class Detection:
    class_id: int
    class_name: str
    confidence: float
    bbox: tuple[float, float, float, float]
    track_id: int | None = None

    def public(self):
        return {"class_id": self.class_id, "class_name": self.class_name,
                "confidence": round(self.confidence, 4), "bbox": list(self.bbox), "track_id": self.track_id}


def area(box):
    return max(0, box[2] - box[0]) * max(0, box[3] - box[1])


def intersection(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def iou(a, b):
    overlap = intersection(a, b)
    return overlap / max(1e-9, area(a) + area(b) - overlap)


class PersonTracker:
    """Short-lived one-to-one IoU tracks for alert deduplication, not identity."""

    def __init__(self):
        self.tracks = {}
        self.next_id = 1

    def update(self, people, now):
        self.tracks = {key: value for key, value in self.tracks.items() if now - value[1] <= 2.0}
        candidates = []
        for index, person in enumerate(people):
            for track_id, (box, _) in self.tracks.items():
                overlap = iou(person.bbox, box)
                if overlap >= 0.2:
                    candidates.append((overlap, index, track_id))
        assigned_people, assigned_tracks = set(), set()
        for _, index, track_id in sorted(candidates, reverse=True):
            if index not in assigned_people and track_id not in assigned_tracks:
                people[index].track_id = track_id
                assigned_people.add(index)
                assigned_tracks.add(track_id)
        for index, person in enumerate(people):
            if index not in assigned_people:
                person.track_id = self.next_id
                self.next_id += 1
            self.tracks[person.track_id] = (person.bbox, now)


def associate_ppe(people, equipment, threshold=0.5):
    """Each PPE box has at most one owner; overlapping workers cannot share it."""
    assigned = {person.track_id: set() for person in people}
    for item in equipment:
        item_area = area(item.bbox)
        if item_area <= 0:
            continue
        candidates = []
        center_x = (item.bbox[0] + item.bbox[2]) / 2
        for person in people:
            ratio = intersection(item.bbox, person.bbox) / item_area
            if ratio >= threshold:
                px = (person.bbox[0] + person.bbox[2]) / 2
                horizontal_distance = abs(center_x - px) / max(1e-6, person.bbox[2] - person.bbox[0])
                candidates.append((ratio, -horizontal_distance, -area(person.bbox), person.track_id))
        if candidates:
            owner = max(candidates)[-1]
            assigned[owner].add(item.class_id)
    return assigned


def inside(person, zone):
    x1, y1, x2, y2 = person.bbox
    point = ((x1 + x2) / 2, y2 if zone.anchor == "feet" else (y1 + y2) / 2)
    rect = zone.rect
    return rect.x1 <= point[0] <= rect.x2 and rect.y1 <= point[1] <= rect.y2


def evaluate_zones(detections, zones: list[Zone], person_ids, ppe_ids, threshold=0.5):
    people = [item for item in detections if item.class_id in person_ids]
    equipment = [item for item in detections if item.class_id in ppe_ids]
    assigned = associate_ppe(people, equipment, threshold)
    violations, zone_results = [], []
    for zone in zones:
        occupants = [person for person in people if zone.enabled and inside(person, zone)]
        offenders = []
        for person in occupants:
            missing = sorted(set(zone.required_class_ids) - assigned[person.track_id])
            if zone.kind == "restricted" or missing:
                offenders.append(person.track_id)
                violations.append({
                    "zone_id": zone.id, "zone_name": zone.name, "source_id": zone.source_id,
                    "track_id": person.track_id, "kind": "intrusion" if zone.kind == "restricted" else "missing_ppe",
                    "missing_class_ids": missing if zone.kind == "ppe" else [],
                    "person_bbox": list(person.bbox),
                })
        zone_results.append({"zone_id": zone.id, "occupancy": len(occupants),
                             "violation_count": len(offenders), "violating_track_ids": offenders})
    return {"violations": violations, "zone_results": zone_results,
            "people": [{"track_id": person.track_id, "present_class_ids": sorted(assigned[person.track_id])} for person in people]}
