# Native voice output integration

The native voice path carries explicit `voice_request_id` metadata from the PTT conversation command through the canonical completed assistant event. `NativeCoreBridge.voiceResponseFinal` is emitted only for the correlated request; keyboard messages remain QML requests and never trigger speech. The bridge uses the existing local Piper provider and native Windows playback when available, with fail-closed cleanup. Live TTS and stop-speaking validation remain pending human retest.
