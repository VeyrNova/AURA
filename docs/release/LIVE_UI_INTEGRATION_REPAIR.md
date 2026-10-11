# Live UI integration repair — offline status

The native Maps, Weather, Mail and Agenda views were loaded through their real
QML components in offscreen tests. This is **not** a Windows visual acceptance.

## Maps and Weather

`GeoBaseMap.qml` is shared by MapsView and WeatherView. A subsequent lot added
locally bundled Natural Earth land/coastline data at 1:50m and 1:10m; see
`NATURAL_EARTH_INTEGRATION.md` and `app/assets/maps/natural_earth/SOURCE.md`.
The former no-dataset finding here is historical. Windows live review remains
open even though the offscreen map is geographically recognizable.

## Mail and Daily Hub

Production without Gmail read permission now uses a permission-required
backend, never sample inbox data. MailView displays a styled search, sidebar,
permission panel, list area, preview area and read-only status. A separate
fake-backend test exercises inbox and preview without credentials. No Gmail
write was performed. The production QML context injects the same
`googleDaySummaryBridge` instance that AgendaView reads. It prefetches month
summaries asynchronously; the actual day delegate limits Calendar to two
events, shows overflow and Gmail/Tasks badges, including permission state,
and dispatches the popup to Calendar/Mail/Tasks tabs. Real Windows visual
acceptance for Mail and Agenda is still pending.

## Validation on 2026-10-03

- Targeted offscreen tests: 12/12 PASS.
- Headless global: 483 discovered, 233 executed, 233 PASS, 0 FAIL,
  0 failed imports, 0 timeouts, completed. ADF 35/35.
- Native QML self-check: PASS (`ok: true`).
- Python bytecode under `src`, `app`, `tests`, `tools`: 0.
- Network, OAuth, Google write, WebEngine, Git, legacy cutover: none used.

The next strict step is to select and license a suitable **local** GeoJSON
dataset (land/coastline, ideally admin boundaries), add it deliberately to
`app/assets/maps`, then verify geometry density, performance and all four
requested window sizes in a visible Windows session. Do not label these
views visually complete before that review.
