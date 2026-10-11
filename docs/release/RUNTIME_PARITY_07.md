# Runtime Parity 07 — Mail Native

Mail Native now has a minimal real domain implementation with no network path in tests. `MailService` consumes a deterministic `FakeMailBackend`; `NativeMailBridge` exposes search, message/thread selection, attachment metadata and prepared send. Sensitive send operations create a `PreparedAction` in the existing repository, cancel without mutation, and execute only after confirmation. No second OAuth or credential store was created.

The native `MailView.qml` is a real QML route with search, list and body detail. It does not execute HTML or call Gmail directly. The NativeWorkspaceView route is `mail`; the official composition creates one MailService and one bridge. Mail QML self-check passed with `--core-mode native --qml-self-check` and an isolated state directory.

The historical Gmail backend was audited read-only: search/list, message detail, thread detail, attachment metadata/content, draft creation and send are present. Reply, forward, archive and labels were not found in the required backend contract and remain `NON_APPLICABLE` until a focused audit proves otherwise. The native implementation currently validates the offline contract and does not claim real Gmail parity or live account behavior.

Maps remains `MAPS_LEGACY_STATUS=PLACEHOLDER_PARTIAL`, `MAPS_NATIVE_STATUS=PLACEHOLDER`, `MAPS_BLOCKS_CUTOVER=NO`. Documents and Contacts remain conversation/workflow helpers in the current UI; historical providers exist, but no autonomous native route was found, so they are classified `LEGACY_PARTIAL`, `NATIVE_NOT_MIGRATED`, non-blocking until scope is explicitly expanded.

Fresh global run: 468 tests discovered, 218 executed, 250 excluded; 218 PASS, 0 FAIL, 0 import failures, 0 timeouts; ADF 35/35. Mail, Weather city, Maps/Mail classification, runtime wiring and QML checks pass. Bytecode scan: 0 `.pyc`. The cutover gate remains BLOCKED because the native Mail adapter is fake/offline only and has not yet been connected to the existing Google identity for read parity. BAT and default `legacy` mode remain unchanged.
