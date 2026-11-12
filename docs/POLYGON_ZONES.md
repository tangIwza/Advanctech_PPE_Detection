# Rectangle and Polygon / Pen zones

The public repository was created and the original application pushed before the
polygon work began. Its first commit is `51a62eef4c8431f2e970dfb73e67c68b0d550358`.

In **Live Monitoring**, choose the drawing mode beside **Draw zone**:

- **Rectangle:** drag from one corner to the opposite corner.
- **Polygon / Pen:** click each corner in order. Numbered points and live edges
  preview the outline. Click the first point again, press **Finish polygon**,
  or press **Enter** to close it.
- **Undo** or **Backspace/Delete** removes the last point. **Esc** or **Cancel**
  discards the unfinished drawing. Changing drawing modes clears unfinished points.

After drawing, choose PPE or restricted-zone rules. Both shapes can coexist on the
same source. Polygons allow 3–64 distinct normalized points. Concave shapes and
either winding are supported; crossing/touching nonadjacent edges, repeated points,
straight-line outlines and negligible areas are rejected by both browser and API.

Use **Edit zone** to change rules or numeric coordinates. Use **Redraw zone** to
place a new outline; selecting the other drawing mode converts the zone when saved.
Existing rectangle records load automatically without changing their rules.

## API example

~~~json
{
  "source_id": "sample-video",
  "name": "Restricted polygon",
  "kind": "restricted",
  "shape": "polygon",
  "points": [
    {"x": 0.1, "y": 0.1},
    {"x": 0.9, "y": 0.2},
    {"x": 0.75, "y": 0.95},
    {"x": 0.25, "y": 0.95}
  ],
  "required_class_ids": [],
  "anchor": "feet",
  "enabled": true
}
~~~

Send this to `POST /api/zones`. Coordinates are relative to video dimensions.
Do not repeat the first point at the end. The returned `rect` is derived from the
vertices for bounds and labels. Actual membership uses boundary-inclusive
point-in-polygon, including concave outlines.

`PATCH /api/zones/{id}` accepts `shape`, `points` and `expected_version`.
To convert back to a rectangle, send `shape: "rectangle"`, `points: null` and a
valid `rect`. Updates preserve the source and zone ID. Live overlays, hit testing,
selected vertex markers and saved alert snapshots all follow the polygon outline.

The model and per-person PPE association are shared by both geometry types.
Polygon support changes the zone boundary, not detector accuracy.
