# Validation — 12 November 2026

Implemented application: `backend/` and `frontend/`.
The reference UI was inspected before frontend implementation; see [UI_THEME.md](UI_THEME.md).

| Check | Result |
| --- | --- |
| `python -X utf8 -B -m pytest backend/tests -q` | **34 passed** |
| `npm test` | **21 passed**, 4 test files |
| `npm run build` | TypeScript check and Vite production build passed |
| `npx --yes npm@11.6.2 ci --no-fund` | Clean lockfile install passed |
| npm dependency audit after Vitest 4.1.12 patch | **0 vulnerabilities** reported |
| Python requirements resolution (`pip install --dry-run`) | Resolved successfully |
| `run_backend.bat` | Launched FastAPI; model warm-up completed; readiness succeeded |
| Vite development server | Started on 127.0.0.1:5173 |
| Production and development HTTP | `/` and `/api/classes` returned 200 on ports 8000 and 5173 |
| Vite WebSocket proxy | Received frame JSON followed by a valid 169,684-byte JPEG |
| Browser console | No captured warnings or errors in the final tested build |

Backend automated tests use controlled detections to verify correctness independently
of model accuracy. They cover exclusive person-to-PPE association, feet/centroid zone
membership, missing PPE, intrusion, disabled zones, tracking, alert deduplication/grace,
shared snapshots and retention, persisted zone CRUD and version conflicts, invalid
rules, upload content and size validation including chunked requests, protected HTTP
and WebSocket origins, snapshots, acknowledgement, pause/resume, immediate rule edits,
and recovery of events interrupted by a backend restart.

Frontend tests cover normalized rectangle geometry and reverse dragging, zone
selection, dynamic wearable class selection, invalid form handling, matched image /
metadata sequences, obsolete image decode rejection across reconnects, initial alert
history suppression and subsequent deduplication, and invalid tokens.

## Real model integration

Used the actual local checkpoint `models/best.pt`:

```text
SHA-256 b1a4c6457086c77f90c8dab5ebf65086f507b380357844bb72486e076f57c984
10 native classes; person ID 0; wearable PPE IDs 1,2,4,5,6,7,8,9
```

The CPU run processed **1,832 frames** of the looping existing sample video before
the first validation capture. Both intrusion and missing-PPE events were observed
through the real API and browser. The captured API summary is
[validation-real-model.json](validation-real-model.json). Its event totals include
repeated video loops and changing model predictions; they are not counts of unique
people or independently verified safety incidents.

Browser interaction verified:

- Start and loop the real video through the UI.
- Draw two rectangles with actual pointer drags over the video while it runs.
- Save a PPE zone requiring helmet and safety-vest, and a restricted zone.
- Receive per-person missing-PPE alerts and restricted-zone intrusion alerts.
- See red person/zone overlays and inspect the saved intrusion snapshot.
- Disable a zone immediately and observe its violation disappear; re-enable it.
- Acknowledge an alert and filter intrusion history.
- Restart the backend, reload the built frontend, and verify persisted zones/history.
- Inspect the model page showing the actual hash, 10 class names and training metrics.
- Check the SCG light/dark layout at 1440×1000 and mobile layout at 390×844.
- Draw a normalized rectangle at mobile width and open/cancel its rule editor.
- Confirm mobile document width equals viewport width and hidden navigation is removed
  from the accessibility tree; restore the browser's original viewport afterward.
- Stop the stream, leaving zero active events, and release the preview servers.

Screenshots:

- [Desktop monitoring](screenshots/monitoring-desktop.jpg)
- [Dark monitoring](screenshots/monitoring-dark.jpg)
- [Mobile zone editor](screenshots/zone-editor-mobile.jpg)

## Polygon drawing update

The original rectangle-only application was published before the polygon work:
commit 51a62eef4c8431f2e970dfb73e67c68b0d550358.

Added tests cover concave polygon membership, inclusive boundaries, reversed winding,
anchor points, invalid/crossing outlines, persistence, geometry conversion and legacy
rectangles, actual polygon snapshot edges, click-to-close, undo, Enter/Escape,
switching drawing modes, reverse-drag rectangles and editing vertex coordinates.

A browser test used the actual model on port 8001 with a separate
.runtime/polygon-preview data directory. It clicked six vertices, used Undo, closed
the polygon by clicking its first point, edited coordinates, and saved a restricted
polygon alongside a rectangle PPE zone. Both intrusion and missing-PPE events were
observed. Its snapshot opened and both shapes persisted after a page reload.
The mobile document width equalled its 390px viewport and no console warnings/errors
were captured. See [validation-polygon.json](validation-polygon.json),
[pen preview](screenshots/polygon-drawing.jpg) and [saved zones](screenshots/polygon-zones.jpg).

The user's port-8000 application was restarted with the new backend. Its existing
rectangle zone and rules were verified and its sample video returned to the prior
paused state. The new drawing controls were verified there. The isolated port-8001
preview was stopped.

## Practical limits

Physical webcam and RTSP hardware were not available for an end-to-end hardware test.
Their source parsing, capture paths, timeouts and application controls are implemented.
The browser was tested against both actual model inference and the built frontend;
automated rule tests use synthetic detections rather than relying on YOLO predictions.

The supplied checkpoint completed 41 of 100 training epochs. Its recorded validation
mAP@50 is 44.9% and mAP@50–95 is 27.4%. The real video shows missed and occasional
duplicate/false detections. Spatial PPE association can also fail with overlapping or
occluded people. These are model/association limits that require site-specific
evaluation; this validation does not certify safety detection accuracy.

Execution used the machine's existing Python 3.11 / Torch 2.2.2 / NumPy 1.26.4 CPU
environment. Existing OpenCV was 4.13; the reproducible requirements pin OpenCV 4.11
to keep its declared NumPy dependency compatible with this Torch/NumPy baseline.
The dependency set resolved, but a full clean Python virtualenv install was not run.
Authentication and origin rejection were tested locally; public TLS/proxy deployment
and GPU operation were not performed. The deployment instructions describe those
settings without claiming they have been deployed.
