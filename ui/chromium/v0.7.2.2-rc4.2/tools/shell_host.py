# AURA P0.6.2.3 FILE + PRODUCTIVITY SERVICE BRIDGE
# AURA P0.6.2.2.1 DIRECT RESEARCH CUTOVER
# AURA P0.6.2.2 CORE SERVICE BRIDGE FOUNDATION
# AURA P0.6.1.4 DYNAMIC NAVIGATION VIEW SUPPORT
# AURA P0.6.1.3.1 MAP TILE Z16 HOTFIX
# AURA P0.6.1.3 NAVIGATION VOICE BRIDGE
# AURA P0.7.0 WORKSPACE CONTEXT: maps accepted
from __future__ import annotations
import argparse, ctypes, json, logging, mimetypes, os, queue, runpy, secrets, shutil, subprocess, sys, threading, time, urllib.parse
import urllib.error, urllib.request
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


# AURA P0.8.5.2.2 RUNTIME PATH CONSUMER
def _aura_p08522_valid_core(path:Path)->bool:
    return (path/'core'/'version.py').is_file() and (path/'VERSION').is_file()

def _aura_p08522_load_paths(core:Path):
    import importlib.util
    module_path=core/'core'/'runtime'/'aura_paths.py'
    if not module_path.is_file():
        raise RuntimeError('AuraPaths introuvable: '+str(module_path))
    spec=importlib.util.spec_from_file_location('aura_paths_shell_host_p08522',module_path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.AuraPaths.resolve(core_root=core)

def _aura_p08522_resolve_runtime_paths(args):
    host_root=Path(__file__).resolve().parents[1]
    core_candidates=[]

    if getattr(args,'core',None):
        core_candidates.append(Path(args.core))
    env_core=str(os.getenv('AURA_ROOT') or '').strip()
    if env_core:
        core_candidates.append(Path(env_core))

    cfg=host_root/'aura_ui_config.json'
    if cfg.is_file():
        try:
            raw=json.loads(cfg.read_text(encoding='utf-8')).get('core_root')
            if raw:
                core_candidates.append(Path(raw))
        except Exception:
            pass

    current=host_root.parent/'current.json'
    if current.is_file():
        try:
            raw=json.loads(current.read_text(encoding='utf-8')).get('core_root')
            if raw:
                core_candidates.append(Path(raw))
        except Exception:
            pass

    core_candidates.extend([host_root,*host_root.parents])

    core=None
    seen=set()
    for raw in core_candidates:
        try:
            candidate=raw.expanduser().resolve(strict=False)
        except Exception:
            candidate=raw.expanduser().absolute()
        key=str(candidate).casefold()
        if key in seen:
            continue
        seen.add(key)
        if _aura_p08522_valid_core(candidate):
            core=candidate
            break
    if core is None:
        raise RuntimeError('AURA Core introuvable pour shell_host.py')

    paths=_aura_p08522_load_paths(core)

    if getattr(args,'ui_root',None):
        root=Path(args.ui_root).expanduser().resolve(strict=False)
    else:
        env_ui=str(os.getenv('AURA_UI_ROOT') or '').strip()
        root=Path(env_ui).expanduser().resolve(strict=False) if env_ui else host_root

    # The active host file is authoritative if a stale locator points elsewhere.
    if not (root/'tools'/'shell_host.py').is_file():
        root=host_root

    os.environ['AURA_ROOT']=str(core)
    os.environ['AURA_UI_ROOT']=str(root)
    os.environ['AURA_DEPLOYMENT_MODE']=str(paths.deployment_mode)
    return core,root,paths



# AURA P0.8.5.3.4 — adaptive workload budget.
def _aura_p08534_workload_ms(core:Path,name:str,fallback:int)->int:
    try:
        import importlib.util
        module_path=Path(core)/'adaptive_profile.py'
        spec=importlib.util.spec_from_file_location('aura_adaptive_shell_p08534',module_path)
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        profile=module.resolve_adaptive_profile(core_root=Path(core))
        value=int(getattr(profile,name,int(fallback)))
        return max(10,min(10000,value))
    except Exception:
        return int(fallback)

RELEASE='0.7.2.2-rc4.2'; CORE_VERSION='0.7.2.2'; CORE_BUILD='2026.08.21.47'
ALLOWED={
    'bridge.ready','bridge.aura_start','bridge.aura_exit','bridge.error','bridge.services_ready',
    'startup_progress','startup_ready','state','provider','operation_started','operation_finished',
    'voice_status','voice_amplitude','voice_warmup_start','voice_warmup_end','voice_transcription',
    'hardware_display_probe','hardware_compute_probe','user_message','aura_message','personal_result','command_result','error',
    'weather_workspace',
    'skill_activity'
}
ALLOWED_PREFIXES=('research.','weather.','voice.service.','file.','task.','reminder.','note.','productivity.','memory.','system.','bridge.','workspace.',)
COMMANDS={'send_message','mic_start','mic_stop','stop_speaking','voice_speak','nav_speak','research_query','weather_current','file_clear','task_create','task_complete','reminder_create','reminder_delete','note_create','note_delete','memory_create','memory_delete','memory_private','memory_clear_profile','system_open_safe_app','system_authorize_folder','system_revoke_folder','system_open_folder','system_scan_folder','system_read_authorized_file','system_analyze_authorized_file','system_analyze_authorized_project','workspace_context'}

class EventHub:
    def __init__(self):
        self.cv=threading.Condition(); self.seq=0; self.items=deque(maxlen=3000)
    def send(self,t,data=None):
        t=str(t or '')
        if t not in ALLOWED and not any(t.startswith(prefix) for prefix in ALLOWED_PREFIXES):return
        with self.cv:
            self.seq+=1
            self.items.append({'seq':self.seq,'ts':time.time(),'type':t,'data':data or {}})
            self.cv.notify_all()
    def wait(self,seq,timeout=12):
        with self.cv:
            got=[x for x in self.items if x['seq']>seq]
            if got:return got
            self.cv.wait(timeout)
            return [x for x in self.items if x['seq']>seq]

class ShellRuntime:
    def __init__(self,root:Path,core:Path):
        self.root=root; self.core=core; self.dist=root/'dist'; self.hub=EventHub()
        self.token=secrets.token_urlsafe(32); self.shutdown=threading.Event(); self.client_closed=threading.Event()
        self.browser=None; self.httpd=None; self.port=0; self.last_pcm=0.0; self.last_heartbeat=time.monotonic()
        self.client_seen=False; self.profile=None; self.main_window=None; self.ui_ready=False
        self.service_bridge=None
        self.commands=queue.Queue(maxsize=32)
        self.voice_lock=threading.Lock(); self.voice_warming=False; self.voice_ready=False; self.voice_warm_started=0.0; self.voice_last_result='unknown'
        self.nav_voice_lock=threading.Lock()
        self.file_revision=-1
        self.upload_dir=self.root.parent.parent/'runtime'/'uploads'/f'session-{os.getpid()}-{self.token[:8]}'
        self.upload_dir.mkdir(parents=True,exist_ok=True)
    def log(self,msg,*a,**kw):logging.getLogger('aura.rc4_2.shell').info(msg,*a,**kw)
    def voice_transition(self,active:bool,*,ok=None,result='unknown',source='bridge'):
        """Publish one authoritative Camilla state.

        RC4.2 latches READY once XTTS residency/use is positively observed.
        A later non-fatal prewarm refusal must never downgrade a working
        Camilla session to LIMITED. Model release/shutdown is handled explicitly.
        """
        now=time.perf_counter(); event=None
        nonfatal_defer={'ram-available','ram-hard-percent','vram-percent','display-gpu-guard','vram-unmeasured','ollama-resident','dual-probe-required'}
        result_s=str(result or 'unknown')
        with self.voice_lock:
            if active:
                # Do not regress a positively observed resident XTTS instance.
                if self.voice_ready:
                    self.voice_warming=False
                    self.voice_last_result='loaded'
                elif not self.voice_warming:
                    self.voice_warming=True; self.voice_warm_started=now; self.voice_last_result='warming'
                    event=('voice_warmup_start',{'active':True,'source':source})
            else:
                resolved=bool(ok)
                elapsed=round(max(0.0,now-self.voice_warm_started),3) if self.voice_warm_started else 0.0
                if self.voice_ready and not resolved and result_s in nonfatal_defer:
                    # Resource policy may refuse a *new* preload even though the
                    # already resident voice is healthy. Keep READY authoritative.
                    self.voice_warming=False
                    self.voice_last_result='loaded'
                    resolved=True
                    result_s='loaded'
                changed=self.voice_warming or (resolved != self.voice_ready) or (result_s != self.voice_last_result)
                self.voice_warming=False; self.voice_ready=resolved; self.voice_last_result=result_s
                if changed:event=('voice_warmup_end',{'ok':resolved,'result':result_s,'elapsed_seconds':elapsed,'source':source})
        if event:
            self.log('Camilla state event=%s ok=%s result=%s source=%s',event[0],event[1].get('ok'),event[1].get('result'),source)
            self.hub.send(*event)

def windows_display_adapter():
    if os.name!='nt':return ''
    try:
        class DD(ctypes.Structure):
            _fields_=[('cb',ctypes.c_ulong),('DeviceName',ctypes.c_wchar*32),('DeviceString',ctypes.c_wchar*128),('StateFlags',ctypes.c_ulong),('DeviceID',ctypes.c_wchar*128),('DeviceKey',ctypes.c_wchar*128)]
        enum=ctypes.windll.user32.EnumDisplayDevicesW; i=0; active=[]
        while True:
            d=DD(); d.cb=ctypes.sizeof(d)
            if not enum(None,i,ctypes.byref(d),0):break
            if (d.StateFlags&0x1) and not (d.StateFlags&0x8) and d.DeviceString.strip():active.append(d.DeviceString.strip())
            i+=1
        intel=[x for x in active if 'intel' in x.casefold() or 'iris' in x.casefold()]
        return (intel or active or [''])[0]
    except Exception:return ''

def inject_display_hint(rt:ShellRuntime):
    name=windows_display_adapter()
    vendor='Intel' if ('intel' in name.casefold() or 'iris' in name.casefold()) else ('NVIDIA' if any(x in name.casefold() for x in ('nvidia','geforce','rtx')) else 'unknown')
    if name:
        try:
            from runtime.hardware_runtime import hardware_runtime
            lock=getattr(hardware_runtime,'_lock',None)
            if lock:
                with lock:
                    hardware_runtime._gl_vendor=vendor; hardware_runtime._gl_renderer=name; hardware_runtime._gl_version='windows-display-probe'
            else:
                hardware_runtime._gl_vendor=vendor; hardware_runtime._gl_renderer=name; hardware_runtime._gl_version='windows-display-probe'
            logging.getLogger('aura.runtime.hardware').info("Windows display adapter probe vendor='%s' adapter='%s' source=EnumDisplayDevicesW opengl_independent=True",vendor,name)
        except Exception:logging.getLogger('aura.rc4_2.shell').exception('Display hint injection failed')
    rt.hub.send('hardware_display_probe',{'ok':bool(name),'source':'win32-enum-display-devices','vendor':vendor,'adapter':name})
    return name

def compute_gpu_name():
    try:
        import torch
        if torch.cuda.is_available():return str(torch.cuda.get_device_name(0) or 'NVIDIA CUDA')
    except Exception:pass
    return 'NVIDIA CUDA'

def observe_xtts_ready(rt:ShellRuntime, engine, *, source='observer'):
    """Return True only when the Core itself proves XTTS is resident/used."""
    try:
        if bool(engine.xtts_model_loaded()):
            rt.voice_transition(False,ok=True,result='loaded',source=source)
            return True
    except Exception:
        pass
    try:
        status=engine.status()
        last=str(getattr(status,'last_engine_used','') or getattr(engine,'_last_engine_used','')).casefold()
        # A completed/active XTTS route is also definitive runtime evidence.
        if last=='xtts':
            rt.voice_transition(False,ok=True,result='xtts-active',source=source)
            return True
    except Exception:
        pass
    return False

def patch_voice(rt:ShellRuntime):
    try:
        from voice.voice_engine import VoiceEngine
        orig=VoiceEngine.set_visual_amplitude_callback
        if not getattr(orig,'_aura_rc42_shell',False):
            def wrapped(self,callback):
                def combined(level):
                    now=time.monotonic()
                    if now-rt.last_pcm>=1/30:
                        rt.last_pcm=now
                        try:rt.hub.send('voice_amplitude',{'level':max(0.0,min(1.0,float(level)))})
                        except Exception:pass
                    if callable(callback):
                        try:callback(level)
                        except Exception:pass
                return orig(self,combined)
            wrapped._aura_rc42_shell=True; VoiceEngine.set_visual_amplitude_callback=wrapped
    except Exception:rt.log('Voice amplitude patch unavailable',exc_info=True)

    # Definitive activity hooks. If the Core selects/uses XTTS successfully,
    # the visual shell must immediately converge to READY even if a previous
    # warmup result was stale or a Qt timer was delayed.
    try:
        from voice.voice_engine import VoiceEngine
        for method_name in ('open_realtime_voice_session','open_realtime_xtts_session'):
            orig_method=getattr(VoiceEngine,method_name,None)
            if callable(orig_method) and not getattr(orig_method,'_aura_rc42_shell',False):
                def make_session_wrapper(orig_fn):
                    def session_wrapper(self,*a,**kw):
                        out=orig_fn(self,*a,**kw)
                        try:
                            if out is not None and self.output_backend_kind()=='xtts':
                                observe_xtts_ready(rt,self,source='xtts-session')
                        except Exception:pass
                        return out
                    session_wrapper._aura_rc42_shell=True
                    return session_wrapper
                setattr(VoiceEngine,method_name,make_session_wrapper(orig_method))
        orig_speak=getattr(VoiceEngine,'speak',None)
        if callable(orig_speak) and not getattr(orig_speak,'_aura_rc42_shell',False):
            def speak_wrapper(self,*a,**kw):
                # If already resident, promote before playback begins.
                observe_xtts_ready(rt,self,source='speak-entry')
                out=orig_speak(self,*a,**kw)
                observe_xtts_ready(rt,self,source='speak-exit')
                return out
            speak_wrapper._aura_rc42_shell=True
            VoiceEngine.speak=speak_wrapper
    except Exception:rt.log('Voice activity readiness hooks unavailable',exc_info=True)

    # Secondary Guardian instrumentation. RC4.2 no longer relies on this
    # method alone because the Core can finish XTTS residency through other
    # paths (controlled trial, user-triggered load, async worker cleanup).
    try:
        from runtime.resource_guardian import ResourceGuardian
        orig=ResourceGuardian.conditional_xtts_prewarm
        if not getattr(orig,'_aura_rc42_shell',False):
            def warm(self,*a,**kw):
                rt.voice_transition(True,source='resource-guardian')
                try:
                    result=orig(self,*a,**kw)
                    last=str(getattr(self,'_xtts_prewarm_last_result','unknown'))
                    # Only a positive Guardian result is authoritative enough
                    # to close WARMING here. A False result can mean another
                    # Core path took over; MainWindow/poll will settle it.
                    if bool(result):
                        rt.voice_transition(False,ok=True,result=last,source='resource-guardian')
                    return result
                except Exception:
                    # The MainWindow state mirror owns the final LIMITED/READY
                    # decision, avoiding a false terminal state during handoff.
                    raise
            warm._aura_rc42_shell=True; ResourceGuardian.conditional_xtts_prewarm=warm
    except Exception:rt.log('Voice warmup Guardian patch unavailable',exc_info=True)


# AURA P0.5.2.1 WEATHER PAYLOAD SSE BRIDGE
def _aura_p0521_json_safe(value, depth=0):
    if depth > 9:
        return None
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(k)[:80]: _aura_p0521_json_safe(v, depth+1) for k,v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_aura_p0521_json_safe(v, depth+1) for v in value[:2500]]
    return str(value)[:500]

def patch_hidden_shell(rt:ShellRuntime):
    from ui.main_window import MainWindow
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtWidgets import QApplication

    # Browser weather workspace bridge: publish the exact structured Core payload.
    _aura_p0521_weather_original = getattr(MainWindow, '_show_weather_popup', None)
    if callable(_aura_p0521_weather_original) and not getattr(_aura_p0521_weather_original, '_aura_p0521_weather_bridge', False):
        def _aura_p0521_weather_popup(self, data):
            try:
                rt.hub.send('weather_workspace', _aura_p0521_json_safe(dict(data or {})))
            except Exception:
                rt.log('P0.5.2.1 weather payload bridge failed', exc_info=True)
            return _aura_p0521_weather_original(self, data)
        _aura_p0521_weather_popup._aura_p0521_weather_bridge = True
        MainWindow._show_weather_popup = _aura_p0521_weather_popup


    # AURA P0.8.5.4.7.5.1 — MAPS WORKSPACE SSE BRIDGE
    # Mirror the successful structured Core Maps payload to the final Three.js
    # workspace. The event uses the already-allowlisted "workspace." SSE prefix.
    _aura_p0854751_maps_original = getattr(MainWindow, '_show_maps_popup', None)
    if callable(_aura_p0854751_maps_original) and not getattr(_aura_p0854751_maps_original, '_aura_p0854751_maps_bridge', False):
        def _aura_p0854751_maps_popup(self, data):
            _payload = _aura_p0521_json_safe(dict(data or {}))
            try:
                rt.hub.send('workspace.maps_route', _payload)
                rt.log(
                    'P0.8.5.4.7.5.1 Maps workspace payload published mode=%s origin=%r destination=%r points=%s',
                    str(_payload.get('mode') or ''),
                    _payload.get('origin_label') or _payload.get('origin'),
                    _payload.get('label') or _payload.get('destination'),
                    len(_payload.get('route_points') or []),
                )
            except Exception:
                rt.log('P0.8.5.4.7.5.1 Maps workspace payload bridge failed', exc_info=True)
            return _aura_p0854751_maps_original(self, data)
        _aura_p0854751_maps_popup._aura_p0854751_maps_bridge = True
        MainWindow._show_maps_popup = _aura_p0854751_maps_popup


    # Authoritative bridge: mirror the Core's own Camilla preload state.
    # This catches every completion route, not only conditional_xtts_prewarm.
    orig_voice_state=getattr(MainWindow,'_set_xtts_preload_ui_state',None)
    if callable(orig_voice_state) and not getattr(orig_voice_state,'_aura_rc42_shell',False):
        def mirrored_voice_state(self,active:bool,*,result:str=''):
            out=orig_voice_state(self,active,result=result)
            if active:
                rt.voice_transition(True,source='main-window-state')
            else:
                loaded=False
                try:loaded=bool(self.aura_core.voice_engine.xtts_model_loaded())
                except Exception:pass
                ok=loaded or str(result) in {'loaded','loaded-by-user','already-loaded'}
                rt.voice_transition(False,ok=ok,result=str(result or ('loaded' if loaded else 'unknown')),source='main-window-state')
            return out
        mirrored_voice_state._aura_rc42_shell=True
        MainWindow._set_xtts_preload_ui_state=mirrored_voice_state

    orig_init=MainWindow.__init__
    if getattr(orig_init,'_aura_rc42_shell',False):return
    def hidden_init(self,*a,**kw):
        orig_init(self,*a,**kw); rt.main_window=self
        try:
            from services.core_bridge import AuraCoreServiceBridge
            rt.service_bridge=AuraCoreServiceBridge(self.aura_core)
            rt.log('AURA Core Service Bridge ready version=%s',rt.service_bridge.VERSION)
            # P0.6.3.2 — UI workspace context is ephemeral and never persisted.
            self._aura_workspace_context='home'
            self._aura_workspace_context_contract={}
            # P0.6.2.5 — Reminder due checks are now owned by ProductivityService.
            # Stop the legacy MainWindow QTimer scheduler to prevent duplicate
            # triggers while keeping its NotificationService presentation.
            try:
                self.scheduler.stop()
                rt.log('Legacy ReminderScheduler stopped; Core Service runtime owns due checks')
                rt.hub.send('reminder.runtime.ready',{'mode':'core-service-runtime-poll','interval_seconds':1.0})
            except Exception:
                rt.log('Legacy ReminderScheduler stop failed',exc_info=True)
        except Exception:
            rt.service_bridge=None
            rt.log('AURA Core Service Bridge initialization failed',exc_info=True)
            rt.hub.send('bridge.error',{'stage':'core-service-bridge','error':'initialization_failed'})
        try:
            if self.aura_core.voice_engine.xtts_model_loaded():
                rt.voice_transition(False,ok=True,result='already-loaded',source='main-window-init')
            elif bool(getattr(self,'_xtts_local_first_preloading',False)):
                rt.voice_transition(True,source='main-window-init')
        except Exception:pass
        try:self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True)
        except Exception:pass
        try:self.startup_progress.connect(lambda p,phase:rt.hub.send('startup_progress',{'percent':int(p),'phase':str(phase)[:90]}))
        except Exception:pass
        def on_ready():
            rt.ui_ready=True; rt.hub.send('startup_ready',{'ready':True,'interaction_ready':True})
        try:self.startup_ready.connect(on_ready)
        except Exception:pass
        timer=QTimer(self)
        _aura_service_poll_ms=_aura_p08534_workload_ms(rt.core,'shell_service_poll_ms',30)
        timer.setInterval(_aura_service_poll_ms)
        rt.log('Adaptive workload: service bridge poll=%dms',_aura_service_poll_ms)
        def tick():
            if rt.shutdown.is_set():
                # AURA P0.8.5.4.7.6.1.3 — HIDDEN MAINWINDOW CLEAN SHUTDOWN
                # Browser/client shutdown must pass through the hidden Core
                # MainWindow.closeEvent() before QApplication quits. closeEvent()
                # already owns XTTS prewarm cancellation + QThread quit/wait.
                if not getattr(self, '_aura_p08547613_shutdown_started', False):
                    self._aura_p08547613_shutdown_started = True
                    try:
                        rt.log(
                            'P0.8.5.4.7.6.1.3 Shell shutdown delegating to MainWindow.close() '
                            'voice_warming=%s voice_ready=%s',
                            rt.voice_warming,
                            rt.voice_ready,
                        )
                        self.close()
                    except Exception:
                        rt.log(
                            'P0.8.5.4.7.6.1.3 MainWindow.close() failed during shell shutdown',
                            exc_info=True,
                        )
                app=QApplication.instance()
                if app is not None:app.quit()
                return
            if rt.service_bridge is not None:
                try:
                    _service_updates=rt.service_bridge.poll() or {}
                    for _weather_payload in list(_service_updates.get('weather') or []):
                        rt.hub.send('weather_workspace', _aura_p0521_json_safe(dict(_weather_payload or {})))
                    for _reminder in list(_service_updates.get('reminders_triggered') or []):
                        if not isinstance(_reminder,dict):
                            continue
                        try:
                            self.aura_core.handle_reminder_triggered(_reminder)
                        except Exception:
                            rt.log('Reminder Conversation presentation failed',exc_info=True)
                        try:
                            _content=str(_reminder.get('content') or 'Rappel')[:500]
                            _app_name=str(getattr(self.notification_service,'app_name','AURA') or 'AURA')
                            self.notification_service.notify(f'{_app_name} — Rappel',_content)
                        except Exception:
                            rt.log('Reminder desktop notification failed',exc_info=True)
                    # P0.6.2.3 compatibility sync: Three.js owns file selection,
                    # while the mature 26.8.x document analysis lane remains in
                    # MainWindow for this release. No analysis logic is copied.
                    rev=rt.service_bridge.files.revision
                    if rev!=rt.file_revision:
                        rt.file_revision=rev
                        self._active_document_context=rt.service_bridge.files.active_context
                except Exception:rt.log('Core Service Bridge poll failed',exc_info=True)
            for _ in range(4):
                try:cmd=rt.commands.get_nowait()
                except queue.Empty:break
                action=cmd.get('action',''); ok=True; err=''
                # AURA_V23_SKILL_REGISTRY_SHELL_CONSULT_BIND
                # v2.3 foundation is consultative only: registry metadata is
                # resolved before dispatch, while existing executors and
                # authorization gates retain complete execution ownership.
                _aura_v23_skill = None
                try:
                    from runtime.aura_skill_registry_v230 import resolve_skill_for_command
                    _aura_v23_skill = resolve_skill_for_command(action)
                    if _aura_v23_skill is not None:
                        _aura_v23_skill_event = {
                            'command': str(action),
                            'skill_id': str(_aura_v23_skill.get('skill_id') or ''),
                            'owner': str(_aura_v23_skill.get('owner') or ''),
                            'risk': str(_aura_v23_skill.get('risk') or ''),
                            'mode': 'consult',
                        }
                        rt.log(
                            'v2.3 skill consult command=%s skill=%s owner=%s risk=%s',
                            _aura_v23_skill_event['command'],
                            _aura_v23_skill_event['skill_id'],
                            _aura_v23_skill_event['owner'],
                            _aura_v23_skill_event['risk'],
                        )
                        try:
                            rt.hub.send('skill_activity', _aura_v23_skill_event)
                        except Exception:
                            rt.log('v2.3 skill_activity publish failed', exc_info=True)
                except Exception:
                    # Registry observability must never break a validated
                    # command path during the v2.3 consult phase.
                    rt.log('v2.3 skill registry consult unavailable action=%s', action, exc_info=True)

                # AURA_V23_SERVICE_SKILLS_BATCH_ACTIVE_CUTOVER
                def _aura_v23_emit_skill_execute(_command, _result=None):
                    try:
                        _meta = _aura_v23_skill
                        if _meta is None or str(_meta.get('command') or '') != str(_command):
                            from runtime.aura_skill_registry_v230 import resolve_skill_for_command
                            _meta = resolve_skill_for_command(_command)
                        if _meta is None:
                            return
                        _phase = 'completed'
                        if isinstance(_result, dict):
                            if 'accepted' in _result:
                                _phase = 'accepted' if bool(_result.get('accepted')) else 'rejected'
                            elif 'ok' in _result:
                                _phase = 'accepted' if bool(_result.get('ok')) else 'rejected'
                        rt.hub.send(
                            'skill_activity',
                            {
                                'command': str(_command),
                                'skill_id': str(_meta.get('skill_id') or ''),
                                'owner': str(_meta.get('owner') or ''),
                                'risk': str(_meta.get('risk') or ''),
                                'mode': 'execute',
                                'phase': _phase,
                            },
                        )
                    except Exception:
                        rt.log('v2.3 skill execute event failed command=%s', _command, exc_info=True)
                try:
                    if action=='send_message':
                        _text=cmd.get('text','')
                        _safe_app=''
                        _authorized_folder=''
                        _authorized_file=None
                        _authorized_file_analysis=None
                        _authorized_project_analysis=None
                        _blocked_process=''
                        _direct_research=False
                        if rt.service_bridge is not None:
                            try:
                                _safe_app=rt.service_bridge.system.match_safe_app_request(_text)
                            except Exception:
                                _safe_app=''
                            try:
                                _authorized_folder=rt.service_bridge.system.match_authorized_folder_request(_text)
                            except Exception:
                                _authorized_folder=''
                            try:
                                _authorized_file=rt.service_bridge.system.match_authorized_file_read_request(_text)
                            except Exception:
                                _authorized_file=None
                            try:
                                _authorized_file_analysis=rt.service_bridge.system.match_authorized_file_analysis_request(_text)
                            except Exception:
                                _authorized_file_analysis=None
                            try:
                                _authorized_project_analysis=rt.service_bridge.system.match_authorized_project_analysis_request(_text)
                            except Exception:
                                _authorized_project_analysis=None
                            try:
                                _blocked_process=rt.service_bridge.system.match_unallowlisted_process_request(_text)
                            except Exception:
                                _blocked_process=''
                            try:
                                from tools.search_intent import should_route_explicit_search_to_web
                                _direct_research=bool(
                                    should_route_explicit_search_to_web(
                                        _text,
                                        has_active_document=bool(
                                            getattr(self, "_active_document_context", None)
                                        ),
                                    )
                                )
                            except Exception:
                                _direct_research=False
                        if _safe_app:
                            # Direct deterministic desktop action: preserve normal
                            # Conversation/continuity events without invoking an LLM.
                            try:
                                self.aura_core.handle_user_message(_text)
                                _prepared=rt.service_bridge.system.plan_safe_app_launch(_safe_app)
                                _plan=_prepared.get('plan') if isinstance(_prepared,dict) else None
                                try:
                                    if rt.main_window is not None:
                                        rt.main_window._record_canonical_safe_desktop_plan(
                                            _plan,
                                            source="shell-safe-app-chat",
                                            app_id=_safe_app,
                                            denied_reason=str(_prepared.get('reason') or _prepared.get('error') or '') if isinstance(_prepared,dict) else '',
                                        )
                                except Exception:
                                    rt.log('Router contract safe-app chat record failed',exc_info=True)
                                result=(
                                    rt.service_bridge.system.execute_safe_app_launch(_plan)
                                    if _plan is not None
                                    else {k:v for k,v in dict(_prepared or {}).items() if k!='plan'}
                                )
                                ok=bool(result.get('ok'))
                                err='' if ok else str(result.get('error') or 'safe_app_launch_failed')
                                if ok:
                                    try:
                                        if rt.main_window is not None:
                                            rt.main_window._record_router_evidence(
                                                "LOCAL_CORE",
                                                "system-safe-app",
                                                f"safe-app-opened · {_safe_app}",
                                                source="system-safe-app-result",
                                            )
                                    except Exception:
                                        rt.log('Router evidence safe-app chat failed',exc_info=True)
                                    _label=str(result.get('label') or _safe_app)
                                    _reply=f"J'ouvre {_label}."
                                    self.aura_core.handle_aura_response(_reply)
                                    def _safe_app_voice(_text=_reply):
                                        try:rt.service_bridge.voice.speak(_text,source='system-safe-app')
                                        except Exception:rt.log('Safe app voice feedback failed',exc_info=True)
                                    threading.Thread(target=_safe_app_voice,daemon=True,name='AuraSafeAppVoice').start()
                                else:
                                    self.aura_core.handle_error("Je n'ai pas pu ouvrir cette application de façon sécurisée.")
                            except Exception:
                                ok=False;err='safe_app_route_failed'
                                rt.log('Safe app direct route failed',exc_info=True)
                        elif _authorized_project_analysis:
                            try:
                                self.aura_core.handle_user_message(_text)
                                _prepared=rt.service_bridge.system.plan_authorized_project_analysis(
                                    _authorized_project_analysis.get('folder_id',''),
                                    analysis_mode=_authorized_project_analysis.get('mode',''),
                                    query=_authorized_project_analysis.get('query',''),
                                )
                                _plan=_prepared.get('plan') if isinstance(_prepared,dict) else None
                                try:
                                    if rt.main_window is not None:
                                        rt.main_window._record_canonical_authorized_project_analysis_plan(
                                            _plan,source="shell-authorized-project-chat",
                                            legacy_reason=str(_prepared.get('error') or 'authorized-project-analysis-not-owned') if isinstance(_prepared,dict) else 'authorized-project-analysis-not-owned',
                                        )
                                except Exception:
                                    rt.log('Router authorized-project chat record failed',exc_info=True)
                                _result=(
                                    rt.service_bridge.system.execute_authorized_project_analysis(_plan)
                                    if _plan is not None
                                    else {k:v for k,v in dict(_prepared or {}).items() if k!='plan'}
                                )
                                if bool(_result.get('ok')):
                                    try:
                                        if rt.main_window is not None:
                                            rt.main_window._record_router_evidence(
                                                "LOCAL_CORE","system-authorized-project",
                                                f"authorized-project-{str(_result.get('mode') or '')} · {str(_result.get('folder_label') or '')}",
                                                source="system-authorized-project-result",
                                            )
                                    except Exception:
                                        rt.log('Router authorized-project evidence failed',exc_info=True)
                                    _title={
                                        'summary':'Synthèse locale du projet',
                                        'search':'Recherche multi-fichiers du projet',
                                        'context':'Contexte multi-fichiers du projet',
                                    }.get(str(_result.get('mode') or ''),'Analyse locale du projet')
                                    _label=str(_result.get('folder_label') or 'Projet')
                                    _reply=(f"{_title} {_label} :\\n\\n{str(_result.get('text') or '')[:5000]}"
                                            f"\\n\\nSources locales : {int(_result.get('files_extracted') or 0)} fichier(s).")
                                    _spoken=f"Analyse locale multi-fichiers du projet {_label} terminée."
                                else:
                                    _reply="Je n’ai pas pu analyser ce projet autorisé localement."
                                    _spoken=_reply
                                self.aura_core.handle_aura_response(_reply)
                                def _project_voice(_text=_spoken):
                                    try:rt.service_bridge.voice.speak(_text,source='authorized-project-intelligence')
                                    except Exception:rt.log('Authorized project voice failed',exc_info=True)
                                threading.Thread(target=_project_voice,daemon=True,name='AuraAuthorizedProjectVoice').start()
                            except Exception:
                                ok=False;err='authorized_project_analysis_failed'
                                rt.log('Authorized project chat route failed',exc_info=True)
                        elif _authorized_file_analysis:
                            try:
                                self.aura_core.handle_user_message(_text)
                                _prepared=rt.service_bridge.system.plan_authorized_file_analysis(
                                    _authorized_file_analysis.get('folder_id',''),
                                    _authorized_file_analysis.get('file_id',''),
                                    analysis_mode=_authorized_file_analysis.get('mode',''),
                                    query=_authorized_file_analysis.get('query',''),
                                )
                                _plan=_prepared.get('plan') if isinstance(_prepared,dict) else None
                                try:
                                    if rt.main_window is not None:
                                        rt.main_window._record_canonical_local_document_analysis_plan(
                                            _plan,
                                            source="shell-local-document-chat",
                                            legacy_reason=str(_prepared.get('error') or 'local-document-analysis-not-owned') if isinstance(_prepared,dict) else 'local-document-analysis-not-owned',
                                        )
                                except Exception:
                                    rt.log('Router local-document chat record failed',exc_info=True)
                                _result=(
                                    rt.service_bridge.system.execute_authorized_file_analysis(_plan)
                                    if _plan is not None
                                    else {k:v for k,v in dict(_prepared or {}).items() if k!='plan'}
                                )
                                if bool(_result.get('ok')):
                                    try:
                                        if rt.main_window is not None:
                                            rt.main_window._record_router_evidence(
                                                "LOCAL_CORE","system-local-document",
                                                f"local-document-{str(_result.get('mode') or '')} · {str(_result.get('name') or '')}",
                                                source="system-local-document-result",
                                            )
                                    except Exception:
                                        rt.log('Router local-document evidence failed',exc_info=True)
                                    _title={
                                        'summary':'Résumé local',
                                        'search':'Recherche locale',
                                        'context':'Contexte local',
                                    }.get(str(_result.get('mode') or ''),'Analyse locale')
                                    _reply=f"{_title} de {str(_result.get('name') or 'fichier')} :\\n\\n{str(_result.get('text') or '')[:3500]}"
                                    _spoken=f"Analyse locale de {str(_result.get('name') or 'fichier')} terminée."
                                else:
                                    _reply="Je n’ai pas pu effectuer cette analyse documentaire locale."
                                    _spoken=_reply
                                self.aura_core.handle_aura_response(_reply)
                                def _analysis_voice(_text=_spoken):
                                    try:
                                        rt.service_bridge.voice.speak(_text,source='local-document-intelligence')
                                    except Exception:
                                        rt.log('Local document voice failed',exc_info=True)
                                threading.Thread(
                                    target=_analysis_voice,daemon=True,
                                    name='AuraLocalDocumentVoice',
                                ).start()
                            except Exception:
                                ok=False;err='local_document_analysis_failed'
                                rt.log('Local document chat route failed',exc_info=True)
                        elif _authorized_file:
                            try:
                                self.aura_core.handle_user_message(_text)
                                _prepared=rt.service_bridge.system.plan_authorized_file_read(
                                    _authorized_file.get('folder_id',''),
                                    _authorized_file.get('file_id',''),
                                )
                                _plan=_prepared.get('plan') if isinstance(_prepared,dict) else None
                                try:
                                    if rt.main_window is not None:
                                        rt.main_window._record_canonical_authorized_file_read_plan(
                                            _plan,
                                            source="shell-authorized-file-chat",
                                            legacy_reason=str(_prepared.get('error') or 'authorized-file-read-not-owned') if isinstance(_prepared,dict) else 'authorized-file-read-not-owned',
                                        )
                                except Exception:
                                    rt.log('Router authorized-file chat record failed',exc_info=True)

                                _result=(
                                    rt.service_bridge.system.execute_authorized_file_read(_plan)
                                    if _plan is not None
                                    else {k:v for k,v in dict(_prepared or {}).items() if k!='plan'}
                                )
                                if bool(_result.get('ok')):
                                    try:
                                        if rt.main_window is not None:
                                            rt.main_window._record_router_evidence(
                                                "LOCAL_CORE",
                                                "system-authorized-file",
                                                f"authorized-file-read · {str(_result.get('name') or '')}",
                                                source="system-authorized-file-result",
                                            )
                                    except Exception:
                                        rt.log('Router authorized-file evidence failed',exc_info=True)

                                    _name=str(_result.get('name') or 'fichier')
                                    _chars=int(_result.get('text_chars') or 0)
                                    _preview=str(_result.get('preview') or '')
                                    _chat_preview=_preview[:1400].strip()
                                    _reply=(
                                        f"J’ai lu {_name} localement ({_chars} caractères)."
                                        + (f"\\n\\nAperçu local :\\n{_chat_preview}" if _chat_preview else "")
                                    )
                                    _spoken=f"J’ai lu {_name} localement."
                                else:
                                    _error=str(_result.get('error') or 'authorized_file_read_failed')
                                    if _error=='native_document_requires_document_lane':
                                        _reply="Ce PDF est visuel. Je ne l’envoie pas dans le cloud depuis Desktop Intelligence."
                                    else:
                                        _reply="Je n’ai pas pu lire ce fichier autorisé localement."
                                    _spoken=_reply
                                self.aura_core.handle_aura_response(_reply)
                                def _file_voice(_text=_spoken):
                                    try:
                                        rt.service_bridge.voice.speak(
                                            _text,
                                            source='authorized-file-read',
                                        )
                                    except Exception:
                                        rt.log('Authorized file voice failed',exc_info=True)
                                threading.Thread(
                                    target=_file_voice,
                                    daemon=True,
                                    name='AuraAuthorizedFileVoice',
                                ).start()
                            except Exception:
                                ok=False;err='authorized_file_read_failed'
                                rt.log('Authorized file chat route failed',exc_info=True)
                        elif _authorized_folder:
                            try:
                                self.aura_core.handle_user_message(_text)
                                _prepared=rt.service_bridge.system.plan_folder_action(
                                    "OPEN_AUTHORIZED_FOLDER",
                                    _authorized_folder,
                                )
                                _plan=_prepared.get('plan') if isinstance(_prepared,dict) else None
                                try:
                                    if rt.main_window is not None:
                                        rt.main_window._record_canonical_authorized_folder_plan(
                                            _plan,
                                            source="shell-authorized-folder-chat",
                                            legacy_reason=str(_prepared.get('error') or 'authorized-folder-open-not-owned') if isinstance(_prepared,dict) else 'authorized-folder-open-not-owned',
                                        )
                                except Exception:
                                    rt.log('Router authorized-folder chat record failed',exc_info=True)
                                _result=(
                                    rt.service_bridge.system.execute_folder_action(_plan)
                                    if _plan is not None
                                    else {k:v for k,v in dict(_prepared or {}).items() if k!='plan'}
                                )
                                if bool(_result.get('ok')):
                                    try:
                                        if rt.main_window is not None:
                                            rt.main_window._record_router_evidence(
                                                "LOCAL_CORE",
                                                "system-authorized-folder",
                                                f"authorized-folder-opened · {_authorized_folder}",
                                                source="system-authorized-folder-result",
                                            )
                                    except Exception:
                                        rt.log('Router authorized-folder evidence failed',exc_info=True)
                                    _reply=f"J'ouvre le dossier {str(_result.get('label') or 'autorisé')}."
                                else:
                                    _reply="Ce dossier autorisé n’est plus disponible."
                                self.aura_core.handle_aura_response(_reply)
                                def _folder_voice(_text=_reply):
                                    try:
                                        rt.service_bridge.voice.speak(_text,source='authorized-folder')
                                    except Exception:
                                        rt.log('Authorized folder voice failed',exc_info=True)
                                threading.Thread(
                                    target=_folder_voice,
                                    daemon=True,
                                    name='AuraAuthorizedFolderVoice',
                                ).start()
                            except Exception:
                                ok=False;err='authorized_folder_open_failed'
                                rt.log('Authorized folder chat route failed',exc_info=True)
                        elif _blocked_process:
                            # Explicit arbitrary process launch: fail closed
                            # locally. Never send an execution request to an LLM.
                            try:
                                self.aura_core.handle_user_message(_text)
                                _denial=rt.service_bridge.system.deny_unallowlisted_process_request(
                                    _blocked_process
                                )
                                try:
                                    if rt.main_window is not None:
                                        rt.main_window._record_canonical_desktop_policy_denial(
                                            action=str(_denial.get('action') or 'RUN_PROGRAM'),
                                            allowed=bool(_denial.get('policy_allowed')),
                                            target=_blocked_process,
                                            source="shell-desktop-policy-deny",
                                        )
                                        rt.main_window._record_router_evidence(
                                            "LOCAL_CORE",
                                            "system-policy-deny",
                                            f"blocked RUN_PROGRAM · {_blocked_process}",
                                            source="system-policy-deny-result",
                                        )
                                except Exception:
                                    rt.log('Router desktop denial evidence failed',exc_info=True)

                                _reply=(
                                    f"Je ne peux pas lancer {_blocked_process} : "
                                    "l’exécution de programmes hors de l’allowlist sécurisée est verrouillée."
                                )
                                self.aura_core.handle_aura_response(_reply)
                                def _deny_voice(_text=_reply):
                                    try:
                                        rt.service_bridge.voice.speak(
                                            _text,
                                            source='system-policy-deny',
                                        )
                                    except Exception:
                                        rt.log('Desktop policy deny voice failed',exc_info=True)
                                threading.Thread(
                                    target=_deny_voice,
                                    daemon=True,
                                    name='AuraDesktopPolicyDenyVoice',
                                ).start()
                            except Exception:
                                ok=False;err='desktop_policy_deny_failed'
                                rt.log('Desktop policy deny route failed',exc_info=True)
                        elif _direct_research:
                            # P0.6.4.1.1 — this route intentionally bypasses
                            # MainWindow, so record the already-selected route
                            # here before ResearchService starts. Shadow only:
                            # no routing decision or execution behavior changes.
                            try:
                                if rt.main_window is not None:
                                    rt.main_window._record_canonical_tool_contract(
                                        name="web_search",
                                        category="web_search",
                                        action="WEB_SEARCH",
                                        source="shell-direct-research",
                                        legacy_reason="direct-core-service-explicit-search",
                                    )
                            except Exception:
                                rt.log('Router contract direct research record failed',exc_info=True)
                            result=rt.service_bridge.research.start(_text)
                            ok=bool(result.get('accepted'))
                            err='' if ok else str(result.get('error') or 'research_rejected')
                            if ok:
                                rt.hub.send('research.route',{'mode':'core-service-direct','source':'send_message'})
                        else:
                            self._on_user_message(_text)
                    elif action=='mic_start':self._on_microphone_pressed()
                    elif action=='mic_stop':self._on_microphone_released()
                    elif action=='stop_speaking':
                        # AURA_V23_VOICE_SKILL_ACTIVE_CUTOVER
                        from runtime.aura_skill_executor_v230 import execute_registered_skill
                        def _aura_v23_stop_owner(_command,_payload):
                            if rt.service_bridge is not None:
                                return rt.service_bridge.voice.stop_speaking()
                            return self.aura_core.voice_engine.stop_speaking()
                        _aura_v23_result=execute_registered_skill(
                            'stop_speaking',
                            {},
                            _aura_v23_stop_owner,
                            source='shell-stop-speaking',
                        )
                        _aura_v23_emit_skill_execute('stop_speaking', _aura_v23_result)
                    elif action=='research_query':
                        if rt.service_bridge is None:
                            ok=False; err='core_service_bridge_unavailable'
                        else:
                            try:
                                if rt.main_window is not None:
                                    rt.main_window._record_canonical_tool_contract(
                                        name="web_search",
                                        category="web_search",
                                        action="WEB_SEARCH",
                                        source="shell-research-action",
                                        legacy_reason="direct-core-service-research-action",
                                    )
                            except Exception:
                                rt.log('Router contract research_query record failed',exc_info=True)
                            from runtime.aura_skill_executor_v230 import execute_registered_skill
                            result=execute_registered_skill(
                                'research_query',
                                {'text': cmd.get('text','')},
                                lambda _c,_p: rt.service_bridge.research.start(_p.get('text','')),
                                source='shell-research-action',
                            )
                            ok=bool(result.get('accepted'))
                            err='' if ok else str(result.get('error') or 'research_rejected')
                            _aura_v23_emit_skill_execute('research_query', result)
                    elif action=='weather_current':
                        if rt.service_bridge is None:
                            ok=False; err='core_service_bridge_unavailable'
                        else:
                            try:
                                if rt.main_window is not None:
                                    rt.main_window._record_canonical_tool_contract(
                                        name="weather",
                                        category="weather",
                                        action="WEB_WEATHER",
                                        source="shell-weather-current",
                                        legacy_reason="direct-weather-current",
                                    )
                            except Exception:
                                rt.log('Router contract weather_current record failed',exc_info=True)
                            try:
                                _lat=float(cmd.get('latitude'))
                                _lon=float(cmd.get('longitude'))
                                _accuracy=cmd.get('accuracy')
                                _accuracy=float(_accuracy) if _accuracy is not None else None
                            except (TypeError,ValueError):
                                ok=False; err='invalid_coordinates'
                            else:
                                # AURA_V23_WEATHER_SKILL_ACTIVE_CUTOVER
                                # The skill layer orchestrates only. WeatherService.start_current
                                # remains the canonical execution owner.
                                from runtime.aura_skill_executor_v230 import execute_registered_skill

                                def _aura_v23_weather_existing_owner(_command, _payload):
                                    if _command != 'weather_current':
                                        raise RuntimeError('unexpected_weather_skill_command:' + str(_command))
                                    return rt.service_bridge.weather.start_current(
                                        _payload.get('latitude'),
                                        _payload.get('longitude'),
                                        accuracy=_payload.get('accuracy'),
                                    )

                                result=execute_registered_skill(
                                    'weather_current',
                                    {
                                        'latitude': _lat,
                                        'longitude': _lon,
                                        'accuracy': _accuracy,
                                    },
                                    _aura_v23_weather_existing_owner,
                                    source='shell-weather-current',
                                )
                                ok=bool(result.get('accepted'))
                                err='' if ok else str(result.get('error') or 'weather_rejected')
                                if ok:
                                    try:
                                        rt.hub.send(
                                            'skill_activity',
                                            {
                                                'command': 'weather_current',
                                                'skill_id': 'weather',
                                                'owner': 'services.core_bridge',
                                                'risk': 'network_read',
                                                'mode': 'execute',
                                                'phase': 'accepted',
                                            },
                                        )
                                    except Exception:
                                        rt.log('v2.3 weather skill execute event failed', exc_info=True)
                    elif action=='system_open_safe_app':
                        if rt.service_bridge is None:
                            ok=False; err='core_service_bridge_unavailable'
                        else:
                            _app_id=str(cmd.get('app_id','') or '').casefold().strip()
                            _prepared=rt.service_bridge.system.plan_safe_app_launch(_app_id)
                            _plan=_prepared.get('plan') if isinstance(_prepared,dict) else None
                            try:
                                if rt.main_window is not None:
                                    rt.main_window._record_canonical_safe_desktop_plan(
                                        _plan,
                                        source="shell-system-action",
                                        app_id=_app_id,
                                        denied_reason=str(_prepared.get('reason') or _prepared.get('error') or '') if isinstance(_prepared,dict) else '',
                                    )
                            except Exception:
                                rt.log('Router contract safe-app action record failed',exc_info=True)
                            # AURA_V23_SYSTEM_SKILL_ACTIVE_CUTOVER
                            from runtime.aura_skill_executor_v230 import execute_registered_skill
                            result=execute_registered_skill(
                                'system_open_safe_app',
                                {'plan':_plan,'prepared':_prepared,'app_id':_app_id},
                                lambda _c,_p: (
                                    rt.service_bridge.system.execute_safe_app_launch(_p.get('plan'))
                                    if _p.get('plan') is not None
                                    else {k:v for k,v in dict(_p.get('prepared') or {}).items() if k!='plan'}
                                ),
                                source='shell-system-open-safe-app',
                            )
                            _aura_v23_emit_skill_execute('system_open_safe_app', result)
                            ok=bool(result.get('ok'))
                            err='' if ok else str(result.get('error') or 'safe_app_launch_failed')
                            if ok:
                                try:
                                    if rt.main_window is not None:
                                        rt.main_window._record_router_evidence(
                                            "LOCAL_CORE",
                                            "system-safe-app",
                                            f"safe-app-opened · {_app_id}",
                                            source="system-safe-app-result",
                                        )
                                except Exception:
                                    rt.log('Router evidence safe-app action failed',exc_info=True)
                    elif action in {
                        'system_authorize_folder',
                        'system_revoke_folder',
                        'system_open_folder',
                        'system_scan_folder',
                    }:
                        if rt.service_bridge is None:
                            ok=False; err='core_service_bridge_unavailable'
                        else:
                            if action=='system_authorize_folder':
                                _prepared=rt.service_bridge.system.plan_authorize_folder(
                                    cmd.get('path',''),
                                    cmd.get('label',''),
                                )
                            else:
                                _map={
                                    'system_revoke_folder':'REVOKE_AUTHORIZED_FOLDER',
                                    'system_open_folder':'OPEN_AUTHORIZED_FOLDER',
                                    'system_scan_folder':'LIST_AUTHORIZED_FOLDER',
                                }
                                _prepared=rt.service_bridge.system.plan_folder_action(
                                    _map[action],
                                    cmd.get('folder_id',''),
                                )
                            _plan=_prepared.get('plan') if isinstance(_prepared,dict) else None
                            try:
                                if rt.main_window is not None:
                                    rt.main_window._record_canonical_authorized_folder_plan(
                                        _plan,
                                        source=f"shell-{action}",
                                        legacy_reason=str(_prepared.get('error') or 'authorized-folder-action-not-owned') if isinstance(_prepared,dict) else 'authorized-folder-action-not-owned',
                                    )
                            except Exception:
                                rt.log('Router authorized-folder action record failed',exc_info=True)

                            from runtime.aura_skill_executor_v230 import execute_registered_skill
                            def _aura_v23_system_folder_owner(_command,_payload):
                                _owner_plan=_payload.get('plan')
                                _owner_prepared=_payload.get('prepared')
                                if _owner_plan is None:
                                    return {k:v for k,v in dict(_owner_prepared or {}).items() if k!='plan'}
                                if _command=='system_authorize_folder':
                                    return rt.service_bridge.system.execute_authorize_folder(_owner_plan)
                                return rt.service_bridge.system.execute_folder_action(_owner_plan)
                            result=execute_registered_skill(
                                action,
                                {'plan':_plan,'prepared':_prepared,'folder_id':cmd.get('folder_id','')},
                                _aura_v23_system_folder_owner,
                                source='shell-system-folder-action',
                            )
                            _aura_v23_emit_skill_execute(action, result)

                            ok=bool(result.get('ok'))
                            err='' if ok else str(result.get('error') or 'authorized_folder_action_failed')
                            if ok:
                                _route=(
                                    'system-folder-registry'
                                    if action in {'system_authorize_folder','system_revoke_folder'}
                                    else 'system-authorized-folder'
                                )
                                try:
                                    if rt.main_window is not None:
                                        rt.main_window._record_router_evidence(
                                            "LOCAL_CORE",
                                            _route,
                                            f"{action} · {str(result.get('folder_id') or '')}",
                                            source="system-authorized-folder-result",
                                        )
                                except Exception:
                                    rt.log('Router authorized-folder evidence failed',exc_info=True)
                    elif action=='system_read_authorized_file':
                        if rt.service_bridge is None:
                            ok=False;err='core_service_bridge_unavailable'
                        else:
                            _prepared=rt.service_bridge.system.plan_authorized_file_read(
                                cmd.get('folder_id',''),
                                cmd.get('file_id',''),
                            )
                            _plan=_prepared.get('plan') if isinstance(_prepared,dict) else None
                            try:
                                if rt.main_window is not None:
                                    rt.main_window._record_canonical_authorized_file_read_plan(
                                        _plan,
                                        source="shell-system-read-authorized-file",
                                        legacy_reason=str(_prepared.get('error') or 'authorized-file-read-not-owned') if isinstance(_prepared,dict) else 'authorized-file-read-not-owned',
                                    )
                            except Exception:
                                rt.log('Router authorized-file action record failed',exc_info=True)

                            from runtime.aura_skill_executor_v230 import execute_registered_skill
                            result=execute_registered_skill(
                                'system_read_authorized_file',
                                {'plan':_plan,'prepared':_prepared},
                                lambda _c,_p: (
                                    rt.service_bridge.system.execute_authorized_file_read(_p.get('plan'))
                                    if _p.get('plan') is not None
                                    else {k:v for k,v in dict(_p.get('prepared') or {}).items() if k!='plan'}
                                ),
                                source='shell-system-read-authorized-file',
                            )
                            _aura_v23_emit_skill_execute('system_read_authorized_file', result)
                            ok=bool(result.get('ok'))
                            err='' if ok else str(result.get('error') or 'authorized_file_read_failed')
                            if ok:
                                try:
                                    if rt.main_window is not None:
                                        rt.main_window._record_router_evidence(
                                            "LOCAL_CORE",
                                            "system-authorized-file",
                                            f"system_read_authorized_file · {str(result.get('name') or '')}",
                                            source="system-authorized-file-result",
                                        )
                                except Exception:
                                    rt.log('Router authorized-file evidence failed',exc_info=True)
                    elif action=='system_analyze_authorized_file':
                        if rt.service_bridge is None:
                            ok=False;err='core_service_bridge_unavailable'
                        else:
                            _prepared=rt.service_bridge.system.plan_authorized_file_analysis(
                                cmd.get('folder_id',''),cmd.get('file_id',''),
                                analysis_mode=cmd.get('mode',''),
                                query=cmd.get('query',''),
                            )
                            _plan=_prepared.get('plan') if isinstance(_prepared,dict) else None
                            try:
                                if rt.main_window is not None:
                                    rt.main_window._record_canonical_local_document_analysis_plan(
                                        _plan,source="shell-system-analyze-authorized-file",
                                        legacy_reason=str(_prepared.get('error') or 'local-document-analysis-not-owned') if isinstance(_prepared,dict) else 'local-document-analysis-not-owned',
                                    )
                            except Exception:
                                rt.log('Router local-document action record failed',exc_info=True)
                            from runtime.aura_skill_executor_v230 import execute_registered_skill
                            result=execute_registered_skill(
                                'system_analyze_authorized_file',
                                {'plan':_plan,'prepared':_prepared},
                                lambda _c,_p: (
                                    rt.service_bridge.system.execute_authorized_file_analysis(_p.get('plan'))
                                    if _p.get('plan') is not None
                                    else {k:v for k,v in dict(_p.get('prepared') or {}).items() if k!='plan'}
                                ),
                                source='shell-system-analyze-authorized-file',
                            )
                            _aura_v23_emit_skill_execute('system_analyze_authorized_file', result)
                            ok=bool(result.get('ok'))
                            err='' if ok else str(result.get('error') or 'local_document_analysis_failed')
                            if ok:
                                try:
                                    if rt.main_window is not None:
                                        rt.main_window._record_router_evidence(
                                            "LOCAL_CORE","system-local-document",
                                            f"system_analyze_authorized_file · {str(result.get('mode') or '')} · {str(result.get('name') or '')}",
                                            source="system-local-document-result",
                                        )
                                except Exception:
                                    rt.log('Router local-document evidence failed',exc_info=True)
                    elif action=='system_analyze_authorized_project':
                        if rt.service_bridge is None:
                            ok=False;err='core_service_bridge_unavailable'
                        else:
                            _prepared=rt.service_bridge.system.plan_authorized_project_analysis(
                                cmd.get('folder_id',''),
                                analysis_mode=cmd.get('mode',''),
                                query=cmd.get('query',''),
                            )
                            _plan=_prepared.get('plan') if isinstance(_prepared,dict) else None
                            try:
                                if rt.main_window is not None:
                                    rt.main_window._record_canonical_authorized_project_analysis_plan(
                                        _plan,source="shell-system-analyze-authorized-project",
                                        legacy_reason=str(_prepared.get('error') or 'authorized-project-analysis-not-owned') if isinstance(_prepared,dict) else 'authorized-project-analysis-not-owned',
                                    )
                            except Exception:
                                rt.log('Router authorized-project action record failed',exc_info=True)
                            from runtime.aura_skill_executor_v230 import execute_registered_skill
                            result=execute_registered_skill(
                                'system_analyze_authorized_project',
                                {'plan':_plan,'prepared':_prepared},
                                lambda _c,_p: (
                                    rt.service_bridge.system.execute_authorized_project_analysis(_p.get('plan'))
                                    if _p.get('plan') is not None
                                    else {k:v for k,v in dict(_p.get('prepared') or {}).items() if k!='plan'}
                                ),
                                source='shell-system-analyze-authorized-project',
                            )
                            _aura_v23_emit_skill_execute('system_analyze_authorized_project', result)
                            ok=bool(result.get('ok'))
                            err='' if ok else str(result.get('error') or 'authorized_project_analysis_failed')
                            if ok:
                                try:
                                    if rt.main_window is not None:
                                        rt.main_window._record_router_evidence(
                                            "LOCAL_CORE","system-authorized-project",
                                            f"system_analyze_authorized_project · {str(result.get('mode') or '')} · {str(result.get('folder_label') or '')}",
                                            source="system-authorized-project-result",
                                        )
                                except Exception:
                                    rt.log('Router authorized-project evidence failed',exc_info=True)
                    elif action=='workspace_context':
                        # AURA_V23_DEVELOPER_SKILL_STRUCTURAL_CUTOVER_V2
                        # The existing shell/MainWindow state remains the canonical owner.
                        from runtime.aura_skill_executor_v230 import execute_registered_skill

                        def _aura_v23_workspace_context_owner(_command,_payload):
                            _workspace=str(_payload.get('workspace') or 'home').strip().casefold()
                            self._aura_workspace_context=_workspace
                            if bool(_payload.get('clear_context')):
                                self._aura_workspace_context_contract={'schema':'aura.workspace-context.v2','workspace':_workspace,'cleared':True,'facts':[],'refs':[]}
                            elif isinstance(_payload.get('context'),dict):
                                self._aura_workspace_context_contract=dict(_payload.get('context'))
                            _published=getattr(self,'_aura_workspace_context_contract',None)
                            if not isinstance(_published,dict) or str(_published.get('workspace') or '').casefold()!=_workspace:_published=None
                            rt.hub.send(
                                'workspace.context',
                                {'workspace':_workspace,'source':'threejs-workspace-manager','context':_published},
                            )
                            return {
                                'ok':True,
                                'workspace':_workspace,
                                'published':bool(isinstance(_published,dict)),
                            }

                        _aura_v23_result=execute_registered_skill(
                            'workspace_context',
                            {
                                'workspace':cmd.get('workspace'),
                                'clear_context':bool(cmd.get('clear_context')),
                                'context':cmd.get('context'),
                            },
                            _aura_v23_workspace_context_owner,
                            source='shell-workspace-context',
                        )
                        _aura_v23_emit_skill_execute('workspace_context', _aura_v23_result)
                    elif action=='file_load':
                        if rt.service_bridge is None:
                            ok=False; err='core_service_bridge_unavailable'
                        else:
                            result=rt.service_bridge.files.load(cmd.get('path',''))
                            ok=bool(result.get('accepted'))
                            err='' if ok else str(result.get('error') or 'file_load_rejected')
                    elif action=='file_clear':
                        if rt.service_bridge is None:
                            ok=False; err='core_service_bridge_unavailable'
                        else:
                            from runtime.aura_skill_executor_v230 import execute_registered_skill
                            _aura_v23_result=execute_registered_skill(
                                'file_clear',
                                {},
                                lambda _c,_p: rt.service_bridge.files.clear(),
                                source='shell-file-clear',
                            )
                            self._active_document_context=None
                            _aura_v23_emit_skill_execute('file_clear', _aura_v23_result)
                    elif action=='task_create':
                        if rt.service_bridge is None:ok=False; err='core_service_bridge_unavailable'
                        else:
                            from runtime.aura_skill_executor_v230 import execute_registered_skill
                            _aura_v23_result=execute_registered_skill(
                                'task_create',
                                {'title':cmd.get('title',''),'due_date':cmd.get('due_date','')},
                                lambda _c,_p: rt.service_bridge.productivity.create_task(
                                    _p.get('title',''), due_date=_p.get('due_date','')
                                ),
                                source='shell-task-create',
                            )
                            _aura_v23_emit_skill_execute('task_create', _aura_v23_result)
                    elif action=='task_complete':
                        if rt.service_bridge is None:ok=False; err='core_service_bridge_unavailable'
                        else:
                            from runtime.aura_skill_executor_v230 import execute_registered_skill
                            result=execute_registered_skill(
                                'task_complete',
                                {'identifier':cmd.get('identifier','')},
                                lambda _c,_p: rt.service_bridge.productivity.complete_task(_p.get('identifier','')),
                                source='shell-task-complete',
                            )
                            ok=bool(result.get('ok')); err='' if ok else str(result.get('error') or 'task_complete_failed')
                            _aura_v23_emit_skill_execute('task_complete', result)
                    elif action=='reminder_create':
                        if rt.service_bridge is None:ok=False; err='core_service_bridge_unavailable'
                        else:
                            from runtime.aura_skill_executor_v230 import execute_registered_skill
                            _aura_v23_result=execute_registered_skill(
                                'reminder_create',
                                {'content':cmd.get('content',''),'trigger_at':cmd.get('trigger_at','')},
                                lambda _c,_p: rt.service_bridge.productivity.create_reminder(
                                    _p.get('content',''), _p.get('trigger_at','')
                                ),
                                source='shell-reminder-create',
                            )
                            _aura_v23_emit_skill_execute('reminder_create', _aura_v23_result)
                    elif action=='reminder_delete':
                        if rt.service_bridge is None:ok=False; err='core_service_bridge_unavailable'
                        else:
                            from runtime.aura_skill_executor_v230 import execute_registered_skill
                            result=execute_registered_skill(
                                'reminder_delete',
                                {'id':cmd.get('id',0)},
                                lambda _c,_p: rt.service_bridge.productivity.delete_reminder(_p.get('id',0)),
                                source='shell-reminder-delete',
                            )
                            ok=bool(result.get('ok')); err='' if ok else str(result.get('error') or 'reminder_delete_failed')
                            _aura_v23_emit_skill_execute('reminder_delete', result)
                    elif action=='note_create':
                        if rt.service_bridge is None:ok=False; err='core_service_bridge_unavailable'
                        else:
                            from runtime.aura_skill_executor_v230 import execute_registered_skill
                            _aura_v23_result=execute_registered_skill(
                                'note_create',
                                {'content':cmd.get('content',''),'title':cmd.get('title','')},
                                lambda _c,_p: rt.service_bridge.productivity.create_note(
                                    _p.get('content',''), title=_p.get('title','')
                                ),
                                source='shell-note-create',
                            )
                            _aura_v23_emit_skill_execute('note_create', _aura_v23_result)
                    elif action=='note_delete':
                        if rt.service_bridge is None:ok=False; err='core_service_bridge_unavailable'
                        else:
                            from runtime.aura_skill_executor_v230 import execute_registered_skill
                            result=execute_registered_skill(
                                'note_delete',
                                {'id':cmd.get('id',0)},
                                lambda _c,_p: rt.service_bridge.productivity.delete_note(_p.get('id',0)),
                                source='shell-note-delete',
                            )
                            ok=bool(result.get('ok')); err='' if ok else str(result.get('error') or 'note_delete_failed')
                            _aura_v23_emit_skill_execute('note_delete', result)
                    elif action=='memory_create':
                        if rt.service_bridge is None:ok=False; err='core_service_bridge_unavailable'
                        else:
                            try:
                                from runtime.aura_skill_executor_v230 import execute_registered_skill
                                result=execute_registered_skill(
                                    'memory_create',
                                    {
                                        'content':cmd.get('content',''),
                                        'memory_type':cmd.get('memory_type',''),
                                        'importance':cmd.get('importance',3),
                                    },
                                    lambda _c,_p: rt.service_bridge.memory.remember(
                                        _p.get('content',''),
                                        memory_type=_p.get('memory_type',''),
                                        importance=_p.get('importance',3),
                                    ),
                                    source='shell-memory-create',
                                )
                                ok=bool(result.get('ok'));err='' if ok else str(result.get('error') or 'memory_create_failed')
                                _aura_v23_emit_skill_execute('memory_create', result)
                            except RuntimeError as exc:
                                ok=False;err=str(exc)
                    elif action=='memory_delete':
                        if rt.service_bridge is None:ok=False; err='core_service_bridge_unavailable'
                        else:
                            from runtime.aura_skill_executor_v230 import execute_registered_skill
                            result=execute_registered_skill(
                                'memory_delete',
                                {'id':cmd.get('id',0)},
                                lambda _c,_p: rt.service_bridge.memory.forget(_p.get('id',0)),
                                source='shell-memory-delete',
                            )
                            ok=bool(result.get('ok'));err='' if ok else str(result.get('error') or 'memory_delete_failed')
                            _aura_v23_emit_skill_execute('memory_delete', result)
                    elif action=='memory_private':
                        if rt.service_bridge is None:ok=False; err='core_service_bridge_unavailable'
                        else:
                            from runtime.aura_skill_executor_v230 import execute_registered_skill
                            result=execute_registered_skill(
                                'memory_private',
                                {'enabled':bool(cmd.get('enabled'))},
                                lambda _c,_p: rt.service_bridge.memory.set_private_mode(bool(_p.get('enabled'))),
                                source='shell-memory-private',
                            )
                            ok=bool(result.get('ok'));err='' if ok else 'memory_private_failed'
                            _aura_v23_emit_skill_execute('memory_private', result)
                    elif action=='memory_clear_profile':
                        if rt.service_bridge is None:ok=False; err='core_service_bridge_unavailable'
                        else:
                            from runtime.aura_skill_executor_v230 import execute_registered_skill
                            result=execute_registered_skill(
                                'memory_clear_profile',
                                {},
                                lambda _c,_p: rt.service_bridge.memory.clear_profile(),
                                source='shell-memory-clear-profile',
                            )
                            ok=bool(result.get('ok'));err='' if ok else 'memory_clear_failed'
                            _aura_v23_emit_skill_execute('memory_clear_profile', result)
                    elif action=='voice_speak':
                        voice_text=safe_text(cmd.get('text',''),520).strip()
                        voice_source=safe_text(cmd.get('source','ui-feedback'),80).strip() or 'ui-feedback'
                        if not voice_text:
                            ok=False; err='empty_voice_speech'
                        else:
                            def _aura_ui_speak_worker(_text=voice_text,_source=voice_source,_window=self):
                                if not rt.nav_voice_lock.acquire(blocking=False):
                                    rt.log('AURA UI voice prompt dropped reason=voice_busy source=%s chars=%s',_source,len(_text))
                                    return
                                try:
                                    active_thread=getattr(_window,'_tts_thread',None)
                                    is_running=getattr(active_thread,'isRunning',None)
                                    if callable(is_running) and bool(is_running()):
                                        rt.log('AURA UI voice prompt dropped reason=conversation_tts_active source=%s chars=%s',_source,len(_text))
                                        return
                                    from runtime.aura_skill_executor_v230 import execute_registered_skill
                                    def _aura_v23_ui_voice_owner(_command,_payload):
                                        if rt.service_bridge is not None:
                                            return rt.service_bridge.voice.speak(
                                                _payload.get('text',''),
                                                source=_payload.get('source','ui-feedback'),
                                            )
                                        engine=getattr(getattr(_window,'aura_core',None),'voice_engine',None)
                                        if engine is not None:
                                            return engine.speak(_payload.get('text',''))
                                        return None
                                    _aura_v23_result=execute_registered_skill(
                                        'voice_speak',
                                        {'text':_text,'source':_source},
                                        _aura_v23_ui_voice_owner,
                                        source='shell-ui-voice',
                                    )
                                    _aura_v23_emit_skill_execute('voice_speak', _aura_v23_result)
                                except Exception as voice_exc:
                                    rt.log('AURA UI voice failed source=%s type=%s detail=%s',_source,type(voice_exc).__name__,str(voice_exc)[:180])
                                finally:
                                    rt.nav_voice_lock.release()
                            threading.Thread(target=_aura_ui_speak_worker,daemon=True,name='AuraUIVoice').start()
                    elif action=='nav_speak':
                        nav_text=safe_text(cmd.get('text',''),360).strip()
                        if not nav_text:
                            ok=False; err='empty_nav_speech'
                        else:
                            def _aura_nav_speak_worker(_text=nav_text,_window=self):
                                if not rt.nav_voice_lock.acquire(blocking=False):
                                    rt.log('AURA navigation voice prompt dropped reason=voice_busy chars=%s',len(_text))
                                    return
                                try:
                                    # Do not collide with an active conversational TTS worker.
                                    active_thread=getattr(_window,'_tts_thread',None)
                                    is_running=getattr(active_thread,'isRunning',None)
                                    if callable(is_running) and bool(is_running()):
                                        rt.log('AURA navigation voice prompt dropped reason=conversation_tts_active chars=%s',len(_text))
                                        return
                                    engine=getattr(getattr(_window,'aura_core',None),'voice_engine',None)
                                    if engine is None:
                                        rt.log('AURA navigation voice unavailable reason=no_voice_engine')
                                        return
                                    from runtime.aura_skill_executor_v230 import execute_registered_skill
                                    def _aura_v23_nav_voice_owner(_command,_payload):
                                        if rt.service_bridge is not None:
                                            return rt.service_bridge.voice.speak(
                                                _payload.get('text',''),
                                                source='navigation-guidance',
                                            )
                                        return engine.speak(_payload.get('text',''))
                                    _aura_v23_result=execute_registered_skill(
                                        'nav_speak',
                                        {'text':_text},
                                        _aura_v23_nav_voice_owner,
                                        source='shell-navigation-voice',
                                    )
                                    _aura_v23_emit_skill_execute('nav_speak', _aura_v23_result)
                                    observe_xtts_ready(rt,engine,source='navigation-guidance')
                                except Exception as nav_exc:
                                    rt.log('AURA navigation voice failed type=%s detail=%s',type(nav_exc).__name__,str(nav_exc)[:180])
                                finally:
                                    rt.nav_voice_lock.release()
                            threading.Thread(target=_aura_nav_speak_worker,daemon=True,name='AuraNavigationVoice').start()
                    else:ok=False; err='unsupported'
                except Exception as e:
                    ok=False; err=type(e).__name__; logging.getLogger('aura.rc4_2.shell').exception('UI command failed action=%s',action)
                rt.hub.send('command_result',{'action':action,'ok':ok,'error':err})
        timer.timeout.connect(tick); timer.start(); self._aura_rc42_command_timer=timer

        # Two independent residency observers: Qt timer + daemon thread.
        # RC4.1 relied on the hidden window timer; the field report proved that
        # it could fail to converge even while the Core was already speaking.
        voice_timer=QTimer(self); voice_timer.setInterval(500)
        def voice_tick():
            try:
                if observe_xtts_ready(rt,self.aura_core.voice_engine,source='qt-resident-poll'):
                    return
                warming=bool(getattr(self,'_xtts_local_first_preloading',False))
                if warming:rt.voice_transition(True,source='qt-resident-poll')
            except Exception:pass
        voice_timer.timeout.connect(voice_tick); voice_timer.start(); self._aura_rc42_voice_timer=voice_timer
        QTimer.singleShot(0,voice_tick)

        def resident_thread():
            while not rt.shutdown.wait(.35):
                try:
                    engine=self.aura_core.voice_engine
                    observe_xtts_ready(rt,engine,source='thread-resident-poll')
                except Exception:
                    pass
        threading.Thread(target=resident_thread,daemon=True,name='AuraRC42VoiceReady').start()
    hidden_init._aura_rc42_shell=True; MainWindow.__init__=hidden_init
    def noop(*a,**kw):return None
    MainWindow.showMaximized=noop; MainWindow.show=noop; MainWindow.raise_=noop; MainWindow.activateWindow=noop

def safe_text(value,limit=4000):
    return str(value or '').replace('\x00','')[:limit]

def connect_events(rt:ShellRuntime):
    from core.event_bus import event_bus
    event_bus.state_changed.connect(lambda s:rt.hub.send('state',{'state':str(s)}))
    event_bus.provider_changed.connect(lambda p,m:rt.hub.send('provider',{'provider':str(p),'model':str(m)}))
    event_bus.operation_started.connect(lambda n,p:rt.hub.send('operation_started',{'name':str(n)}))
    event_bus.operation_finished.connect(lambda n,p:rt.hub.send('operation_finished',{'name':str(n)}))
    event_bus.voice_status_changed.connect(lambda s:rt.hub.send('voice_status',{'status':str(s)}))
    event_bus.voice_transcription.connect(lambda t:rt.hub.send('voice_transcription',{'text':safe_text(t)}))
    event_bus.user_message.connect(lambda t:rt.hub.send('user_message',{'text':safe_text(t),'chars':len(str(t or ''))}))
    event_bus.aura_message.connect(lambda t:rt.hub.send('aura_message',{'text':safe_text(t),'chars':len(str(t or ''))}))
    event_bus.error_occurred.connect(lambda t:rt.hub.send('error',{'text':safe_text(t,800),'chars':len(str(t or ''))}))
    def _runtime_service_event(name,payload):
        name=safe_text(name,120).strip()
        if not name:return
        try:data=_aura_p0521_json_safe(payload if isinstance(payload,dict) else {'value':payload})
        except Exception:data={'value':safe_text(payload,1000)}
        rt.hub.send(name,data)
    event_bus.runtime_event.connect(_runtime_service_event)

# AURA P0.5.2.7.1 MAP TILE LOOPBACK PROXY
_AURA_MAP_TILE_UPSTREAM = "https://tile.openstreetmap.org"
_AURA_MAP_TILE_USER_AGENT = "AURA-Personal-Assistant/0.7.2.2 (personal desktop application)"
_AURA_MAP_TILE_MAX_BYTES = 2 * 1024 * 1024
_AURA_MAP_TILE_LOCKS = {}
_AURA_MAP_TILE_LOCKS_GUARD = threading.Lock()

def _aura_map_tile_cache_root():
    local = str(os.getenv("LOCALAPPDATA") or "").strip()
    base = Path(local) if local else (Path.home() / "AppData" / "Local")
    return base / "AURA" / "cache" / "map_tiles" / "osm"

def _aura_map_tile_validate(z, x, y):
    z = int(z); x = int(x); y = int(y)
    if z < 0 or z > 16:
        raise ValueError("zoom")
    n = 1 << z
    if x < 0 or x >= n or y < 0 or y >= n:
        raise ValueError("coordinates")
    return z, x, y

def _aura_map_tile_cache_path(z, x, y):
    return _aura_map_tile_cache_root() / str(z) / str(x) / f"{y}.png"

def _aura_map_tile_lock(key):
    with _AURA_MAP_TILE_LOCKS_GUARD:
        lock = _AURA_MAP_TILE_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _AURA_MAP_TILE_LOCKS[key] = lock
        return lock

def _aura_map_tile_get(rt, z, x, y):
    z, x, y = _aura_map_tile_validate(z, x, y)
    cache = _aura_map_tile_cache_path(z, x, y)

    try:
        if cache.is_file() and cache.stat().st_size > 100:
            return cache.read_bytes(), "cache"
    except Exception:
        pass

    lock = _aura_map_tile_lock((z, x, y))
    with lock:
        try:
            if cache.is_file() and cache.stat().st_size > 100:
                return cache.read_bytes(), "cache"
        except Exception:
            pass

        url = f"{_AURA_MAP_TILE_UPSTREAM}/{z}/{x}/{y}.png"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": _AURA_MAP_TILE_USER_AGENT,
                "Accept": "image/png,image/*;q=0.8,*/*;q=0.5",
                "Accept-Encoding": "identity",
                "Connection": "close",
            },
            method="GET",
        )

        try:
            with urllib.request.urlopen(req, timeout=8.0) as response:
                status = int(getattr(response, "status", 200) or 200)
                ctype = str(response.headers.get("Content-Type", "image/png") or "image/png")
                data = response.read(_AURA_MAP_TILE_MAX_BYTES + 1)
        except urllib.error.HTTPError as exc:
            try:
                rt.log("AURA map tile upstream HTTP error z=%s x=%s y=%s status=%s", z, x, y, exc.code)
            except Exception:
                pass
            raise RuntimeError(f"tile_http_{exc.code}") from exc
        except Exception as exc:
            try:
                rt.log("AURA map tile upstream error z=%s x=%s y=%s type=%s detail=%s", z, x, y, type(exc).__name__, str(exc)[:180])
            except Exception:
                pass
            raise

        if status != 200:
            raise RuntimeError(f"tile_http_{status}")
        if len(data) <= 100 or len(data) > _AURA_MAP_TILE_MAX_BYTES:
            raise RuntimeError("tile_size_invalid")
        if not (data.startswith(b"\x89PNG\r\n\x1a\n") or "image/png" in ctype.casefold()):
            raise RuntimeError("tile_content_invalid")

        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            tmp = cache.with_suffix(".png.tmp")
            tmp.write_bytes(data)
            tmp.replace(cache)
        except Exception as exc:
            try:
                rt.log("AURA map tile cache write ignored z=%s x=%s y=%s detail=%s", z, x, y, str(exc)[:160])
            except Exception:
                pass

        try:
            rt.log("AURA map tile proxy network z=%s x=%s y=%s bytes=%s", z, x, y, len(data))
        except Exception:
            pass
        return data, "network"

# AURA P0.5.2.8 OVERPASS CARTOGRAPHIC CONTEXT PROXY
_AURA_MAP_CONTEXT_ENDPOINT = "https://overpass-api.de/api/interpreter"
_AURA_MAP_CONTEXT_USER_AGENT = "AURA-Personal-Assistant/0.7.2.2 (personal desktop application)"
_AURA_MAP_CONTEXT_TTL_SECONDS = 14 * 24 * 60 * 60
_AURA_MAP_CONTEXT_MAX_BYTES = 8 * 1024 * 1024
_AURA_MAP_CONTEXT_LOCKS = {}
_AURA_MAP_CONTEXT_LOCKS_GUARD = threading.Lock()

def _aura_map_context_cache_root():
    local = str(os.getenv("LOCALAPPDATA") or "").strip()
    base = Path(local) if local else (Path.home() / "AppData" / "Local")
    return base / "AURA" / "cache" / "map_context" / "overpass_places_v3"

def _aura_map_context_validate(lat, lon, radius_km):
    lat = float(lat)
    lon = float(lon)
    radius_km = int(round(float(radius_km)))

    if not (-84.5 <= lat <= 84.5):
        raise ValueError("lat")
    while lon > 180:
        lon -= 360
    while lon < -180:
        lon += 360

    radius_km = max(35, min(220, radius_km))
    return lat, lon, radius_km

def _aura_map_context_cache_path(lat, lon, radius_km):
    lat_key = f"{lat:+08.3f}".replace("+", "p").replace("-", "m")
    lon_key = f"{lon:+09.3f}".replace("+", "p").replace("-", "m")
    return _aura_map_context_cache_root() / f"{lat_key}_{lon_key}_{radius_km}.json"

def _aura_map_context_lock(key):
    with _AURA_MAP_CONTEXT_LOCKS_GUARD:
        lock = _AURA_MAP_CONTEXT_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _AURA_MAP_CONTEXT_LOCKS[key] = lock
        return lock

def _aura_map_context_perp_distance(pt, start, end):
    x, y = float(pt[0]), float(pt[1])
    x1, y1 = float(start[0]), float(start[1])
    x2, y2 = float(end[0]), float(end[1])

    dx = x2 - x1
    dy = y2 - y1
    if abs(dx) < 1e-12 and abs(dy) < 1e-12:
        return ((x-x1)**2 + (y-y1)**2) ** 0.5

    t = ((x-x1)*dx + (y-y1)*dy) / (dx*dx + dy*dy)
    t = max(0.0, min(1.0, t))
    px = x1 + t*dx
    py = y1 + t*dy
    return ((x-px)**2 + (y-py)**2) ** 0.5

def _aura_map_context_simplify(points, epsilon):
    if len(points) <= 2:
        return points

    start = points[0]
    end = points[-1]
    best_i = -1
    best_d = 0.0

    for i in range(1, len(points)-1):
        d = _aura_map_context_perp_distance(points[i], start, end)
        if d > best_d:
            best_d = d
            best_i = i

    if best_i >= 0 and best_d > epsilon:
        left = _aura_map_context_simplify(points[:best_i+1], epsilon)
        right = _aura_map_context_simplify(points[best_i:], epsilon)
        return left[:-1] + right

    return [start, end]

def _aura_map_context_population(tags):
    raw = str((tags or {}).get("population") or "")
    digits = "".join(ch for ch in raw if ch.isdigit())
    try:
        return int(digits) if digits else 0
    except Exception:
        return 0

def _aura_map_context_city_priority(tags):
    tags = tags or {}
    place = str(tags.get("place") or "").casefold()
    pop = _aura_map_context_population(tags)

    base = {
        "city": 10,
        "town": 7,
        "village": 4,
    }.get(place, 3)

    if pop >= 5_000_000:
        base += 3
    elif pop >= 1_000_000:
        base += 2
    elif pop >= 150_000:
        base += 1

    if str(tags.get("capital") or "").strip():
        base += 1

    return min(14, base)

def _aura_map_context_distance2(lat, lon, center_lat, center_lon):
    mean = (float(lat)+float(center_lat))*0.5*3.141592653589793/180.0
    cos_m = max(0.18, abs(__import__("math").cos(mean)))
    dx = (float(lon)-float(center_lon))*cos_m
    dy = float(lat)-float(center_lat)
    return dx*dx + dy*dy

def _aura_map_context_parse(raw, center_lat, center_lon, radius_km):
    elements = list((raw or {}).get("elements") or [])
    coastlines = []
    cities = []
    total_points = 0

    # Simplification is adaptive: retain a visibly smooth coastline without
    # returning huge OSM geometries to the renderer.
    epsilon = max(0.00018, min(0.0012, radius_km / 260000.0))

    for el in elements:
        et = str(el.get("type") or "")
        tags = el.get("tags") or {}

        if et == "way" and str(tags.get("natural") or "") == "coastline":
            geom = el.get("geometry") or []
            pts = []

            for p in geom:
                try:
                    pts.append([float(p["lon"]), float(p["lat"])])
                except Exception:
                    continue

            if len(pts) >= 2:
                pts = _aura_map_context_simplify(pts, epsilon)

                # Hard safety cap for pathological ways.
                if len(pts) > 900:
                    stride = max(1, len(pts)//900)
                    pts = pts[::stride]
                    if pts[-1] != geom[-1]:
                        try:
                            pts.append([float(geom[-1]["lon"]), float(geom[-1]["lat"])])
                        except Exception:
                            pass

                if len(pts) >= 2:
                    coastlines.append(pts)
                    total_points += len(pts)

        elif et == "node":
            place = str(tags.get("place") or "").casefold()
            if place not in {"city","town","village"}:
                continue

            name = str(tags.get("name") or "").strip()
            if not name:
                continue

            try:
                lat = float(el["lat"])
                lon = float(el["lon"])
            except Exception:
                continue

            cities.append({
                "n": name,
                "lat": lat,
                "lon": lon,
                "p": _aura_map_context_city_priority(tags),
                "place": place,
                "population": _aura_map_context_population(tags),
                "_d": _aura_map_context_distance2(lat, lon, center_lat, center_lon),
            })

    # Keep the nearest towns/villages plus the most important cities.
    cities.sort(key=lambda c: (-int(c["p"]), float(c["_d"])))
    important = cities[:34]
    nearest = sorted(cities, key=lambda c: float(c["_d"]))[:28]

    merged = {}
    for city in important + nearest:
        key = (
            str(city["n"]).casefold(),
            round(float(city["lat"]), 4),
            round(float(city["lon"]), 4),
        )
        merged[key] = city

    cities = sorted(
        merged.values(),
        key=lambda c: (-int(c["p"]), float(c["_d"]))
    )[:52]

    for city in cities:
        city.pop("_d", None)

    # Global point safety cap.
    if total_points > 16000:
        ratio = max(2, int(total_points / 14000))
        trimmed = []
        for line in coastlines:
            if len(line) > 4:
                reduced = line[::ratio]
                if reduced[-1] != line[-1]:
                    reduced.append(line[-1])
                trimmed.append(reduced)
            else:
                trimmed.append(line)
        coastlines = trimmed

    return {
        "ok": True,
        "source": "openstreetmap-overpass-places",
        "center_lat": center_lat,
        "center_lon": center_lon,
        "radius_km": radius_km,
        "coastlines": coastlines,
        "cities": cities,
    }

def _aura_map_context_get(rt, lat, lon, radius_km):
    lat, lon, radius_km = _aura_map_context_validate(lat, lon, radius_km)
    cache = _aura_map_context_cache_path(lat, lon, radius_km)
    now = time.time()

    try:
        if cache.is_file():
            age = now - cache.stat().st_mtime
            if age <= _AURA_MAP_CONTEXT_TTL_SECONDS:
                data = json.loads(cache.read_text(encoding="utf-8"))
                data["cache_state"] = "cache"
                return data
    except Exception:
        pass

    key = (round(lat,3), round(lon,3), radius_km)
    lock = _aura_map_context_lock(key)

    with lock:
        try:
            if cache.is_file():
                age = now - cache.stat().st_mtime
                if age <= _AURA_MAP_CONTEXT_TTL_SECONDS:
                    data = json.loads(cache.read_text(encoding="utf-8"))
                    data["cache_state"] = "cache"
                    return data
        except Exception:
            pass

        # AURA P0.5.2.8.3 PLACES ONLY CONTEXT
        # The coastline is rendered immediately from Aura's bundled world
        # vectors. Overpass is now reserved for nearby populated places.
        radius_m = min(int(radius_km * 1000), 100000)
        village_m = min(radius_m, 45000)

        query = f"""
[out:json][timeout:7];
(
  node["place"~"^(city|town)$"](around:{radius_m},{lat:.6f},{lon:.6f});
  node["place"="village"](around:{village_m},{lat:.6f},{lon:.6f});
);
out body;
""".strip()

        body = urllib.parse.urlencode({"data": query}).encode("utf-8")
        req = urllib.request.Request(
            _AURA_MAP_CONTEXT_ENDPOINT,
            data=body,
            headers={
                "User-Agent": _AURA_MAP_CONTEXT_USER_AGENT,
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                "Accept-Encoding": "identity",
                "Connection": "close",
            },
            method="POST",
        )

        stale = None
        try:
            if cache.is_file():
                stale = json.loads(cache.read_text(encoding="utf-8"))
        except Exception:
            stale = None

        try:
            with urllib.request.urlopen(req, timeout=10.0) as response:
                status = int(getattr(response, "status", 200) or 200)
                raw_bytes = response.read(_AURA_MAP_CONTEXT_MAX_BYTES + 1)

            if status != 200:
                raise RuntimeError(f"context_http_{status}")
            if len(raw_bytes) > _AURA_MAP_CONTEXT_MAX_BYTES:
                raise RuntimeError("context_response_too_large")

            raw = json.loads(raw_bytes.decode("utf-8"))
            data = _aura_map_context_parse(raw, lat, lon, radius_km)
            data["cache_state"] = "network"

            try:
                cache.parent.mkdir(parents=True, exist_ok=True)
                tmp = cache.with_suffix(".json.tmp")
                tmp.write_text(
                    json.dumps(data, ensure_ascii=False, separators=(",",":")),
                    encoding="utf-8"
                )
                tmp.replace(cache)
            except Exception as exc:
                try:
                    rt.log(
                        "AURA map context cache write ignored detail=%s",
                        str(exc)[:180]
                    )
                except Exception:
                    pass

            try:
                rt.log(
                    "AURA map context network lat=%.3f lon=%.3f r=%skm coast=%s cities=%s",
                    lat, lon, radius_km,
                    len(data.get("coastlines") or []),
                    len(data.get("cities") or [])
                )
            except Exception:
                pass

            return data

        except Exception as exc:
            try:
                rt.log(
                    "AURA map context upstream error lat=%.3f lon=%.3f r=%s type=%s detail=%s",
                    lat, lon, radius_km,
                    type(exc).__name__,
                    str(exc)[:220]
                )
            except Exception:
                pass

            if stale:
                stale["cache_state"] = "stale-cache"
                stale["ok"] = True
                return stale

            raise

# AURA P0.6.1 NAVIGATION GEOCODE + ROUTING PROXY
_AURA_NAV_GEOCODER_ENDPOINT = os.getenv(
    "AURA_NAV_GEOCODER_URL",
    "https://nominatim.openstreetmap.org/search"
).strip()
_AURA_NAV_ROUTER_BASE = os.getenv(
    "AURA_NAV_ROUTER_URL",
    "https://routing.openstreetmap.de/routed-car"
).strip().rstrip("/")
_AURA_NAV_USER_AGENT = "AURA-Personal-Assistant/0.7.2.2 (personal desktop navigation)"
_AURA_NAV_GEOCODE_TTL_SECONDS = 30 * 24 * 60 * 60
_AURA_NAV_ROUTE_TTL_SECONDS = 6 * 60 * 60
_AURA_NAV_MAX_BYTES = 8 * 1024 * 1024
_AURA_NAV_RATE_LOCK = threading.Lock()
_AURA_NAV_LAST_REQUEST = {
    "geocode": 0.0,
    "route": 0.0,
}

def _aura_nav_cache_root():
    local = str(os.getenv("LOCALAPPDATA") or "").strip()
    base = Path(local) if local else (Path.home() / "AppData" / "Local")
    return base / "AURA" / "cache" / "navigation"

def _aura_nav_safe_key(value):
    import hashlib
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:32]

def _aura_nav_cache_read(path, ttl):
    try:
        if path.is_file() and (time.time() - path.stat().st_mtime) <= ttl:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data["cache_state"] = "cache"
                return data
    except Exception:
        pass
    return None

def _aura_nav_cache_write(path, data):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, separators=(",",":")),
            encoding="utf-8"
        )
        tmp.replace(path)
    except Exception:
        pass

def _aura_nav_rate_limit(kind):
    # Public endpoints used by this personal build are deliberately kept
    # below one network request per second per service.
    with _AURA_NAV_RATE_LOCK:
        now = time.monotonic()
        last = float(_AURA_NAV_LAST_REQUEST.get(kind, 0.0))
        wait = 1.05 - (now - last)
        if wait > 0:
            time.sleep(wait)
        _AURA_NAV_LAST_REQUEST[kind] = time.monotonic()

def _aura_nav_float(value, lo, hi, name):
    n = float(value)
    if not (lo <= n <= hi):
        raise ValueError(name)
    return n

def _aura_nav_geocode(rt, query, bias_lat=None, bias_lon=None):
    q = " ".join(str(query or "").split()).strip()
    if not q or len(q) > 180:
        raise ValueError("q")

    bias = ""
    lat = lon = None
    try:
        if bias_lat is not None and bias_lon is not None:
            lat = _aura_nav_float(bias_lat, -84.0, 84.0, "lat")
            lon = _aura_nav_float(bias_lon, -180.0, 180.0, "lon")
            bias = f"|{lat:.3f}|{lon:.3f}"
    except Exception:
        lat = lon = None

    key = _aura_nav_safe_key(q.casefold() + bias)
    cache = _aura_nav_cache_root() / "geocode" / f"{key}.json"
    cached = _aura_nav_cache_read(cache, _AURA_NAV_GEOCODE_TTL_SECONDS)
    if cached:
        return cached

    params = {
        "q": q,
        "format": "jsonv2",
        "limit": "5",
        "addressdetails": "1",
        "accept-language": "fr,en",
    }

    # Viewbox is a ranking bias only, not a hard bound.
    if lat is not None and lon is not None:
        lon_pad = 4.5
        lat_pad = 3.2
        params["viewbox"] = (
            f"{max(-180,lon-lon_pad):.5f},"
            f"{min(84,lat+lat_pad):.5f},"
            f"{min(180,lon+lon_pad):.5f},"
            f"{max(-84,lat-lat_pad):.5f}"
        )
        params["bounded"] = "0"

    url = _AURA_NAV_GEOCODER_ENDPOINT + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": _AURA_NAV_USER_AGENT,
            "Accept": "application/json",
            "Accept-Language": "fr,en;q=0.8",
            "Connection": "close",
        },
        method="GET",
    )

    _aura_nav_rate_limit("geocode")
    with urllib.request.urlopen(req, timeout=10.0) as response:
        status = int(getattr(response, "status", 200) or 200)
        raw = response.read(_AURA_NAV_MAX_BYTES + 1)

    if status != 200:
        raise RuntimeError(f"geocode_http_{status}")
    if len(raw) > _AURA_NAV_MAX_BYTES:
        raise RuntimeError("geocode_response_too_large")

    items = json.loads(raw.decode("utf-8"))
    if not isinstance(items, list) or not items:
        return {"ok":False,"error":"destination_not_found"}

    def score(item):
        importance = float(item.get("importance") or 0.0)
        cls = str(item.get("class") or "")
        typ = str(item.get("type") or "")
        place_bonus = 0.0
        if cls == "place" and typ in {"city","town","village","municipality"}:
            place_bonus = 0.35
        distance_bonus = 0.0
        if lat is not None and lon is not None:
            try:
                ilat=float(item["lat"]); ilon=float(item["lon"])
                dx=(ilon-lon)*max(.25,abs(__import__("math").cos(lat*3.141592653589793/180)))
                dy=ilat-lat
                distance=(dx*dx+dy*dy)**0.5
                distance_bonus=max(0.0,0.28-distance*0.025)
            except Exception:
                pass
        return importance + place_bonus + distance_bonus

    best=max(items,key=score)
    try:
        plat=float(best["lat"]); plon=float(best["lon"])
    except Exception:
        raise RuntimeError("invalid_geocode_result")

    addr=best.get("address") or {}
    short=(
        addr.get("city") or addr.get("town") or addr.get("village") or
        addr.get("municipality") or best.get("name") or q
    )
    state=addr.get("state") or addr.get("region")
    country=addr.get("country")
    short_label=", ".join([str(x) for x in (short,state,country) if x]) or q

    data={
        "ok":True,
        "source":"nominatim",
        "cache_state":"network",
        "place":{
            "lat":plat,
            "lon":plon,
            "label":str(best.get("display_name") or short_label),
            "short_label":short_label,
            "display_name":str(best.get("display_name") or ""),
            "type":str(best.get("type") or ""),
            "class":str(best.get("class") or ""),
            "osm_type":str(best.get("osm_type") or ""),
            "osm_id":best.get("osm_id"),
            "boundingbox":best.get("boundingbox"),
        }
    }
    _aura_nav_cache_write(cache,data)
    try:
        rt.log(
            "AURA navigation geocode q=%s result=%s lat=%.5f lon=%.5f",
            q[:80], short_label[:100], plat, plon
        )
    except Exception:
        pass
    return data

# AURA P0.6.6.0 MAPS DESKTOP TRIP PLANNING: optional OSRM alternatives
def _aura_nav_route(rt, from_lat, from_lon, to_lat, to_lon, profile="driving", alternatives=False):
    if str(profile or "driving") != "driving":
        raise ValueError("profile")

    flt=_aura_nav_float(from_lat,-84.0,84.0,"from_lat")
    fln=_aura_nav_float(from_lon,-180.0,180.0,"from_lon")
    tlt=_aura_nav_float(to_lat,-84.0,84.0,"to_lat")
    tln=_aura_nav_float(to_lon,-180.0,180.0,"to_lon")

    want_alternatives = str(alternatives or "").strip().casefold() in {"1","true","yes","on"}
    key=_aura_nav_safe_key(
        f"driving|{flt:.5f}|{fln:.5f}|{tlt:.5f}|{tln:.5f}|alt={int(want_alternatives)}"
    )
    cache=_aura_nav_cache_root()/"routes"/f"{key}.json"
    cached=_aura_nav_cache_read(cache,_AURA_NAV_ROUTE_TTL_SECONDS)
    if cached:
        return cached

    coords=f"{fln:.6f},{flt:.6f};{tln:.6f},{tlt:.6f}"
    query=urllib.parse.urlencode({
        "overview":"full",
        "geometries":"geojson",
        "steps":"true",
        "alternatives":"true" if want_alternatives else "false",
        "annotations":"false",
    })
    url=f"{_AURA_NAV_ROUTER_BASE}/route/v1/driving/{coords}?{query}"
    req=urllib.request.Request(
        url,
        headers={
            "User-Agent":_AURA_NAV_USER_AGENT,
            "Accept":"application/json",
            "Accept-Language":"fr,en;q=0.8",
            "Connection":"close",
        },
        method="GET",
    )

    _aura_nav_rate_limit("route")
    with urllib.request.urlopen(req,timeout=15.0) as response:
        status=int(getattr(response,"status",200) or 200)
        raw=response.read(_AURA_NAV_MAX_BYTES+1)

    if status != 200:
        raise RuntimeError(f"route_http_{status}")
    if len(raw)>_AURA_NAV_MAX_BYTES:
        raise RuntimeError("route_response_too_large")

    payload=json.loads(raw.decode("utf-8"))
    if str(payload.get("code") or "") != "Ok":
        code=str(payload.get("code") or "route_unavailable")
        if code == "NoRoute":
            return {"ok":False,"error":"route_no_route"}
        raise RuntimeError(code)

    routes=payload.get("routes") or []
    if not routes:
        return {"ok":False,"error":"route_no_route"}

    def _normalize_route(selected):
        geometry=selected.get("geometry") or {}
        coords_out=geometry.get("coordinates") or []
        if not isinstance(coords_out,list) or len(coords_out)<2:
            raise RuntimeError("route_geometry_missing")

        steps=[]
        for leg in selected.get("legs") or []:
            for step in leg.get("steps") or []:
                maneuver=step.get("maneuver") or {}
                steps.append({
                    "distance":float(step.get("distance") or 0),
                    "duration":float(step.get("duration") or 0),
                    "name":str(step.get("name") or ""),
                    "mode":str(step.get("mode") or ""),
                    "driving_side":str(step.get("driving_side") or ""),
                    "maneuver":{
                        "type":str(maneuver.get("type") or ""),
                        "modifier":str(maneuver.get("modifier") or ""),
                        "exit":maneuver.get("exit"),
                        "bearing_before":maneuver.get("bearing_before"),
                        "bearing_after":maneuver.get("bearing_after"),
                        "location":maneuver.get("location"),
                    }
                })
        return {
            "distance":float(selected.get("distance") or 0),
            "duration":float(selected.get("duration") or 0),
            "weight":float(selected.get("weight") or 0),
            "weight_name":str(selected.get("weight_name") or ""),
            "geometry":{"type":"LineString","coordinates":coords_out},
            "steps":steps,
        }

    normalized_routes=[_normalize_route(route) for route in routes[:3]]
    data={
        "ok":True,
        "source":"osrm-routing.openstreetmap.de",
        "cache_state":"network",
        "route":normalized_routes[0],
        "routes":normalized_routes,
        "alternatives_requested":want_alternatives,
        "alternative_count":max(0,len(normalized_routes)-1),
    }
    _aura_nav_cache_write(cache,data)
    try:
        rt.log(
            "AURA navigation route dist=%.0fm duration=%.0fs points=%s steps=%s alternatives=%s",
            data["route"]["distance"],data["route"]["duration"],
            len(data["route"]["geometry"]["coordinates"]),len(data["route"]["steps"]),
            data.get("alternative_count",0)
        )
    except Exception:
        pass
    return data


# AURA P0.6.6.1 POI PLACES OVERPASS PROXY
# AURA P0.6.6.1.7 ADAPTIVE POI QUERY PIPELINE
# AURA P0.6.6.1.6 SEGMENTED OVERPASS CORRIDOR
_AURA_NAV_POI_TTL_SECONDS = 4 * 60 * 60
_AURA_NAV_POI_STALE_SECONDS = 7 * 24 * 60 * 60
_AURA_NAV_POI_MAX_RESULTS = 80
_AURA_NAV_POI_OVERPASS_LIMIT = 180
_AURA_NAV_POI_MAX_BYTES = 3 * 1024 * 1024
# AURA P0.6.6.1.5 OVERPASS ENDPOINT HEALTH
_AURA_NAV_POI_HTTP_TIMEOUT_SECONDS = 11.0
_AURA_NAV_POI_ENDPOINT_COOLDOWN_SECONDS = 45.0
_AURA_NAV_POI_ENDPOINT_HEALTH = {}

def _aura_nav_poi_endpoints():
    raw = str(os.getenv("AURA_NAV_OVERPASS_URLS") or "").strip()
    if raw:
        items = [x.strip() for x in raw.split(";") if x.strip()]
        if items:
            return tuple(items[:3])
    return (
        "https://overpass.private.coffee/api/interpreter",
        "https://overpass-api.de/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    )

def _aura_nav_poi_geometry(raw):
    if not isinstance(raw, list) or not raw:
        raise ValueError("poi_geometry")
    points = []
    for item in raw[:512]:
        try:
            if isinstance(item, dict):
                lon = _aura_nav_float(item.get("lon"), -180.0, 180.0, "poi_lon")
                lat = _aura_nav_float(item.get("lat"), -84.0, 84.0, "poi_lat")
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                lon = _aura_nav_float(item[0], -180.0, 180.0, "poi_lon")
                lat = _aura_nav_float(item[1], -84.0, 84.0, "poi_lat")
            else:
                continue
        except Exception:
            continue
        if not points or abs(points[-1][0]-lon) > 1e-9 or abs(points[-1][1]-lat) > 1e-9:
            points.append((lon, lat))
    if not points:
        raise ValueError("poi_geometry")
    max_points = 28
    if len(points) > max_points:
        sampled = []
        for i in range(max_points):
            idx = round(i * (len(points)-1) / (max_points-1))
            p = points[idx]
            if not sampled or sampled[-1] != p:
                sampled.append(p)
        points = sampled
    return points

def _aura_nav_poi_selector_lines(category, around):
    selectors = {
        "parking": [f'nwr["amenity"="parking"]{around};'],
        "fuel": [f'nwr["amenity"="fuel"]{around};'],
        "charging": [f'nwr["amenity"="charging_station"]{around};'],
        "restaurant": [f'nwr["amenity"~"^(restaurant|fast_food|cafe)$"]{around};'],
        "hotel": [f'nwr["tourism"~"^(hotel|motel|hostel|guest_house)$"]{around};'],
        "services": [
            f'nwr["amenity"~"^(pharmacy|hospital|clinic|toilets|drinking_water|atm|car_wash)$"]{around};',
            f'nwr["shop"~"^(supermarket|convenience)$"]{around};',
            f'nwr["highway"~"^(rest_area|services)$"]{around};',
        ],
    }
    if category not in selectors:
        raise ValueError("poi_category")
    return selectors[category]

def _aura_nav_poi_haversine(a, b):
    import math
    lon1, lat1 = a
    lon2, lat2 = b
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2-lat1)
    dl = math.radians(lon2-lon1)
    h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 6371000.0 * 2.0 * math.atan2(math.sqrt(h), math.sqrt(max(0.0, 1.0-h)))

def _aura_nav_poi_route_metrics(point, route):
    import math
    if len(route) == 1:
        return _aura_nav_poi_haversine(point, route[0]), 0.0

    cumulative = [0.0]
    for i in range(len(route)-1):
        cumulative.append(cumulative[-1] + _aura_nav_poi_haversine(route[i], route[i+1]))

    best_d = float("inf")
    best_along = 0.0
    plon, plat = point
    for i in range(len(route)-1):
        a = route[i]; b = route[i+1]
        ref_lat = math.radians((plat + a[1] + b[1]) / 3.0)
        scale_x = 6371000.0 * max(0.05, math.cos(ref_lat)) * math.pi / 180.0
        scale_y = 6371000.0 * math.pi / 180.0
        ax = (a[0]-plon) * scale_x; ay = (a[1]-plat) * scale_y
        bx = (b[0]-plon) * scale_x; by = (b[1]-plat) * scale_y
        vx = bx-ax; vy = by-ay
        denom = vx*vx + vy*vy
        t = 0.0 if denom <= 1e-9 else max(0.0, min(1.0, -(ax*vx + ay*vy)/denom))
        qx = ax + t*vx; qy = ay + t*vy
        d = (qx*qx + qy*qy) ** 0.5
        if d < best_d:
            best_d = d
            seg = max(0.0, cumulative[i+1]-cumulative[i])
            best_along = cumulative[i] + t*seg
    return best_d, best_along

def _aura_nav_poi_name(category, tags):
    raw = str(tags.get("name") or tags.get("brand") or tags.get("operator") or "").strip()
    if raw:
        return raw[:180]
    return {
        "parking":"Parking",
        "fuel":"Station-service",
        "charging":"Borne de recharge",
        "restaurant":"Restaurant",
        "hotel":"Hôtel",
        "services":"Service utile",
    }.get(category, "Lieu utile")

def _aura_nav_poi_address(tags):
    street = " ".join(x for x in (str(tags.get("addr:housenumber") or "").strip(), str(tags.get("addr:street") or "").strip()) if x)
    city = " ".join(x for x in (str(tags.get("addr:postcode") or "").strip(), str(tags.get("addr:city") or "").strip()) if x)
    values = [x for x in (street, city) if x]
    return ", ".join(values)[:240]

def _aura_nav_poi_stale_cache(path):
    try:
        if path.is_file() and (time.time() - path.stat().st_mtime) <= _AURA_NAV_POI_STALE_SECONDS:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("ok"):
                data["cache_state"] = "stale-cache"
                return data
    except Exception:
        pass
    return None

def _aura_nav_poi_endpoint_mark(endpoint, ok):
    now = time.time()
    state = _AURA_NAV_POI_ENDPOINT_HEALTH.setdefault(str(endpoint), {})
    if ok:
        state["success_at"] = now
        state["failures"] = 0
        state.pop("failed_at", None)
    else:
        state["failed_at"] = now
        state["failures"] = int(state.get("failures") or 0) + 1


def _aura_nav_poi_endpoint_candidates():
    now = time.time()
    ranked = []
    for index, endpoint in enumerate(_aura_nav_poi_endpoints()):
        state = _AURA_NAV_POI_ENDPOINT_HEALTH.get(str(endpoint), {})
        failed_at = float(state.get("failed_at") or 0.0)
        success_at = float(state.get("success_at") or 0.0)
        cooling = bool(failed_at and (now - failed_at) < _AURA_NAV_POI_ENDPOINT_COOLDOWN_SECONDS)
        ranked.append((1 if cooling else 0, -success_at, index, endpoint))
    ranked.sort()
    return tuple(item[3] for item in ranked)

def _aura_nav_poi_route_length(route):
    total = 0.0
    for i in range(max(0, len(route)-1)):
        total += _aura_nav_poi_haversine(route[i], route[i+1])
    return total


def _aura_nav_poi_corridor_boxes(route, radius):
    import math
    margin = float(radius) + 250.0
    if not route:
        return []
    total_m = _aura_nav_poi_route_length(route)
    if len(route) <= 2:
        target_boxes = 1
    elif total_m <= 60000:
        target_boxes = 3
    elif total_m <= 150000:
        target_boxes = 4
    elif total_m <= 300000:
        target_boxes = 6
    else:
        target_boxes = 8
    target_boxes = max(1, min(target_boxes, len(route)-1))
    boxes = []
    last = len(route)-1
    for i in range(target_boxes):
        start = int(round(i * last / target_boxes))
        end = int(round((i+1) * last / target_boxes))
        a = max(0, start-1 if i else start)
        b = min(len(route), end+2 if i < target_boxes-1 else end+1)
        chunk = route[a:b]
        if not chunk:
            continue
        lons = [p[0] for p in chunk]; lats = [p[1] for p in chunk]
        mid_lat = sum(lats) / max(1, len(lats))
        dlat = margin / 111320.0
        dlon = margin / (111320.0 * max(0.12, math.cos(math.radians(mid_lat))))
        south=max(-84.0,min(lats)-dlat); north=min(84.0,max(lats)+dlat)
        west=max(-180.0,min(lons)-dlon); east=min(180.0,max(lons)+dlon)
        boxes.append((south,west,north,east))
    return boxes


def _aura_nav_poi_query_for_box(category, bbox):
    south,west,north,east=bbox
    area=f"({south:.6f},{west:.6f},{north:.6f},{east:.6f})"
    body="".join(_aura_nav_poi_selector_lines(category, area))
    return f"[out:json][timeout:11];({body});out center tags 100;"


def _aura_nav_poi_query_for_boxes(category, boxes):
    body=[]
    for south,west,north,east in boxes:
        area=f"({south:.6f},{west:.6f},{north:.6f},{east:.6f})"
        body.extend(_aura_nav_poi_selector_lines(category, area))
    return f"[out:json][timeout:11];({''.join(body)});out center tags 160;"


def _aura_nav_poi_fetch_payload(rt, endpoints, overpass_q, providers_used):
    encoded = urllib.parse.urlencode({"data": overpass_q}).encode("utf-8")
    last_exc = None
    for endpoint in list(endpoints):
        try:
            req = urllib.request.Request(
                endpoint,
                data=encoded,
                headers={
                    "User-Agent": _AURA_NAV_USER_AGENT,
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Connection": "close",
                },
                method="POST",
            )
            _aura_nav_rate_limit("poi")
            with urllib.request.urlopen(req, timeout=_AURA_NAV_POI_HTTP_TIMEOUT_SECONDS) as response:
                status = int(getattr(response, "status", 200) or 200)
                raw = response.read(_AURA_NAV_POI_MAX_BYTES + 1)
            if status != 200:
                raise RuntimeError(f"poi_http_{status}")
            if len(raw) > _AURA_NAV_POI_MAX_BYTES:
                raise RuntimeError("poi_response_too_large")
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise RuntimeError("poi_invalid_payload")
            _aura_nav_poi_endpoint_mark(endpoint, True)
            if endpoint in endpoints:
                endpoints.remove(endpoint); endpoints.insert(0, endpoint)
            if endpoint not in providers_used:
                providers_used.append(endpoint)
            return payload, endpoint, None
        except Exception as exc:
            last_exc = exc
            _aura_nav_poi_endpoint_mark(endpoint, False)
            try:
                rt.log("AURA POI endpoint failed endpoint=%s type=%s detail=%s", endpoint, type(exc).__name__, str(exc)[:180])
            except Exception:
                pass
    return None, None, last_exc

def _aura_nav_poi_search(rt, category, radius_m, geometry):
    category = str(category or "").strip().casefold()
    if category not in {"parking","fuel","charging","restaurant","hotel","services"}:
        raise ValueError("poi_category")
    try:
        radius = int(float(radius_m))
    except Exception:
        raise ValueError("poi_radius")
    radius = max(500, min(5000, radius))
    route = _aura_nav_poi_geometry(geometry)

    route_key = "|".join(f"{lon:.4f},{lat:.4f}" for lon,lat in route)
    key = _aura_nav_safe_key(f"{category}|{radius}|adaptive-v2|{route_key}")
    cache = _aura_nav_cache_root() / "pois" / f"{key}.json"
    cached = _aura_nav_cache_read(cache, _AURA_NAV_POI_TTL_SECONDS)
    if cached:
        return cached

    boxes = _aura_nav_poi_corridor_boxes(route, radius)
    if not boxes:
        raise ValueError("poi_geometry")

    endpoints = list(_aura_nav_poi_endpoint_candidates())
    raw_elements = []
    raw_seen = set()
    providers_used = []
    segments_checked = 0
    partial = False
    last_exc = None
    sparse_batch = category in {"fuel","charging","hotel"}
    raw_target = 90 if category in {"fuel","charging","hotel"} else (110 if category == "parking" else 140)

    def merge_payload(payload):
        nonlocal raw_elements
        for element in (payload or {}).get("elements") or []:
            if not isinstance(element, dict):
                continue
            identity=(str(element.get("type") or "node"), element.get("id"))
            if identity in raw_seen:
                continue
            raw_seen.add(identity); raw_elements.append(element)
            if len(raw_elements) >= raw_target:
                break

    if sparse_batch:
        payload, _, last_exc = _aura_nav_poi_fetch_payload(
            rt, endpoints, _aura_nav_poi_query_for_boxes(category, boxes), providers_used
        )
        if payload is None:
            stale = _aura_nav_poi_stale_cache(cache)
            if stale:
                return stale
            if last_exc:
                raise last_exc
            raise RuntimeError("poi_unavailable")
        merge_payload(payload)
        segments_checked = len(boxes)
    else:
        for bbox in boxes:
            if len(raw_elements) >= raw_target:
                break
            payload, _, fetch_exc = _aura_nav_poi_fetch_payload(
                rt, endpoints, _aura_nav_poi_query_for_box(category, bbox), providers_used
            )
            if payload is None:
                last_exc = fetch_exc or last_exc
                if raw_elements:
                    partial = True
                    break
                stale = _aura_nav_poi_stale_cache(cache)
                if stale:
                    return stale
                if last_exc:
                    raise last_exc
                raise RuntimeError("poi_unavailable")
            segments_checked += 1
            merge_payload(payload)

    elements = raw_elements
    places = []
    seen = set()
    tolerance = float(radius) + 350.0
    for element in elements:
        if not isinstance(element, dict):
            continue
        tags = element.get("tags") or {}
        if not isinstance(tags, dict):
            tags = {}
        lat = element.get("lat"); lon = element.get("lon")
        if lat is None or lon is None:
            center = element.get("center") or {}
            lat = center.get("lat"); lon = center.get("lon")
        try:
            lat = _aura_nav_float(lat, -84.0, 84.0, "poi_lat")
            lon = _aura_nav_float(lon, -180.0, 180.0, "poi_lon")
        except Exception:
            continue

        osm_type = str(element.get("type") or "node")
        osm_id = element.get("id")
        identity = f"{osm_type}:{osm_id}"
        if identity in seen:
            continue
        dist, along = _aura_nav_poi_route_metrics((lon,lat), route)
        if float(dist) > tolerance:
            continue
        seen.add(identity)
        item = {
            "id": identity,
            "category": category,
            "name": _aura_nav_poi_name(category, tags),
            "lat": lat,
            "lon": lon,
            "distance_to_route_m": round(float(dist), 1),
            "route_offset_m": round(float(along), 1),
            "address": _aura_nav_poi_address(tags),
            "opening_hours": str(tags.get("opening_hours") or "")[:160],
            "brand": str(tags.get("brand") or "")[:120],
            "operator": str(tags.get("operator") or "")[:120],
            "access": str(tags.get("access") or "")[:60],
            "fee": str(tags.get("fee") or "")[:40],
            "capacity": str(tags.get("capacity") or "")[:40],
            "kind": str(tags.get("amenity") or tags.get("tourism") or tags.get("shop") or tags.get("highway") or "")[:80],
            "osm_type": osm_type,
            "osm_id": osm_id,
        }
        if category == "charging":
            item["charging"] = {
                "type2": str(tags.get("socket:type2") or "")[:40],
                "ccs": str(tags.get("socket:type2_combo") or tags.get("socket:ccs") or "")[:40],
                "chademo": str(tags.get("socket:chademo") or "")[:40],
            }
        places.append(item)

    if len(route) >= 2:
        places.sort(key=lambda p: (float(p.get("route_offset_m") or 0), float(p.get("distance_to_route_m") or 0), str(p.get("name") or "")))
    else:
        places.sort(key=lambda p: (float(p.get("distance_to_route_m") or 0), str(p.get("name") or "")))
    places = places[:_AURA_NAV_POI_MAX_RESULTS]

    data = {
        "ok": True,
        "source": "openstreetmap-overpass",
        "provider": str(providers_used[0] if providers_used else ""),
        "providers_used": providers_used,
        "cache_state": "network-partial" if partial else "network",
        "query_mode": "adaptive-sparse-batch" if sparse_batch else "adaptive-segmented-corridor",
        "partial": bool(partial),
        "segments_checked": segments_checked,
        "segments_total": len(boxes),
        "category": category,
        "radius_m": radius,
        "route_points": len(route),
        "count": len(places),
        "places": places,
    }
    _aura_nav_cache_write(cache, data)
    try:
        rt.log("AURA POI adaptive category=%s radius=%sm route_points=%s route_km=%.1f mode=%s segments=%s/%s results=%s partial=%s", category, radius, len(route), _aura_nav_poi_route_length(route)/1000.0, "sparse-batch" if sparse_batch else "segmented", segments_checked, len(boxes), len(places), partial)
    except Exception:
        pass
    return data

# AURA P0.6.6.2 TRAFFIC + WEATHER CONTEXT PROXY
_AURA_NAV_CONTEXT_WEATHER_URL = os.getenv(
    "AURA_NAV_WEATHER_URL", "https://api.open-meteo.com/v1/forecast"
).strip()
_AURA_NAV_CONTEXT_TTL_SECONDS = 12 * 60
_AURA_NAV_CONTEXT_STALE_SECONDS = 6 * 60 * 60
_AURA_NAV_CONTEXT_MAX_BYTES = 2 * 1024 * 1024
_AURA_NAV_CONTEXT_HTTP_TIMEOUT_SECONDS = 8.5


def _aura_nav_context_geometry(raw):
    if not isinstance(raw, list) or len(raw) < 2:
        raise ValueError("context_geometry")
    out = []
    for item in raw[:96]:
        try:
            if isinstance(item, dict):
                lon = _aura_nav_float(item.get("lon"), -180.0, 180.0, "context_lon")
                lat = _aura_nav_float(item.get("lat"), -84.0, 84.0, "context_lat")
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                lon = _aura_nav_float(item[0], -180.0, 180.0, "context_lon")
                lat = _aura_nav_float(item[1], -84.0, 84.0, "context_lat")
            else:
                continue
        except Exception:
            continue
        p = (lon, lat)
        if not out or out[-1] != p:
            out.append(p)
    if len(out) < 2:
        raise ValueError("context_geometry")
    if len(out) > 64:
        sampled = []
        for i in range(64):
            idx = round(i * (len(out)-1) / 63)
            p = out[idx]
            if not sampled or sampled[-1] != p:
                sampled.append(p)
        out = sampled
    return out


def _aura_nav_context_sample_route(route, count):
    count = max(2, min(5, int(count)))
    if len(route) <= 2:
        return [(0.0, route[0]), (1.0, route[-1])]
    cumulative = [0.0]
    for i in range(len(route)-1):
        cumulative.append(cumulative[-1] + _aura_nav_poi_haversine(route[i], route[i+1]))
    total = cumulative[-1]
    if total <= 1.0:
        return [(0.0, route[0]), (1.0, route[-1])]
    result = []
    for i in range(count):
        fraction = i / (count-1)
        target = total * fraction
        best = min(range(len(cumulative)), key=lambda j: abs(cumulative[j]-target))
        result.append((fraction, route[best]))
    return result


def _aura_nav_context_num(seq, idx):
    try:
        value = seq[idx]
        return None if value is None else float(value)
    except Exception:
        return None


def _aura_nav_context_risk(sample):
    code = int(sample.get("weather_code") or 0)
    gust = float(sample.get("wind_gusts") or 0.0)
    wind = float(sample.get("wind_speed") or 0.0)
    precip = float(sample.get("precipitation") or 0.0)
    prob = float(sample.get("precipitation_probability") or 0.0)
    visibility = sample.get("visibility")
    visibility = float(visibility) if visibility is not None else 999999.0
    score = 0
    reasons = []
    if code >= 95:
        score = max(score, 2); reasons.append("orages possibles")
    if code in {66,67,75,77,85,86}:
        score = max(score, 2); reasons.append("précipitations hivernales")
    elif code in {71,73}:
        score = max(score, 1); reasons.append("neige possible")
    if gust >= 80:
        score = max(score, 2); reasons.append("fortes rafales")
    elif gust >= 55 or wind >= 45:
        score = max(score, 1); reasons.append("vent soutenu")
    if precip >= 7:
        score = max(score, 2); reasons.append("fortes précipitations")
    elif precip >= 2 or (prob >= 75 and precip > 0):
        score = max(score, 1); reasons.append("pluie probable")
    if visibility < 1200:
        score = max(score, 2); reasons.append("visibilité très réduite")
    elif visibility < 5000 or code in {45,48}:
        score = max(score, 1); reasons.append("visibilité réduite")
    level = "difficult" if score >= 2 else "watch" if score == 1 else "normal"
    return level, reasons


def _aura_nav_context_cache_path(route, departure_ts, duration_s):
    key = "|".join([
        *(f"{p[0]:.3f},{p[1]:.3f}" for p in route),
        str(int(float(departure_ts or 0)//900)),
        str(int(float(duration_s or 0)//300)),
        "weather-v1",
    ])
    return _aura_nav_cache_root() / "route-context" / f"{_aura_nav_safe_key(key)}.json"


def _aura_nav_context_stale(path):
    try:
        if path.is_file() and (time.time() - path.stat().st_mtime) <= _AURA_NAV_CONTEXT_STALE_SECONDS:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data["cache_state"] = "stale-cache"
                return data
    except Exception:
        pass
    return None


def _aura_nav_context_forecast(rt, geometry, duration_s, distance_m, departure_ts):
    route = _aura_nav_context_geometry(geometry)
    try:
        duration = max(60.0, min(36*3600.0, float(duration_s)))
    except Exception:
        raise ValueError("context_duration")
    try:
        distance = max(0.0, float(distance_m or 0.0))
    except Exception:
        distance = 0.0
    now = time.time()
    try:
        departure = float(departure_ts)
    except Exception:
        departure = now
    adjusted = False
    if departure < now - 2*3600:
        departure = now
        adjusted = True
    if departure > now + 7*24*3600:
        raise ValueError("weather_horizon")

    if distance <= 60000:
        sample_count = 3
    elif distance <= 250000:
        sample_count = 4
    else:
        sample_count = 5
    route_samples = _aura_nav_context_sample_route(route, sample_count)
    cache = _aura_nav_context_cache_path([p for _,p in route_samples], departure, duration)
    cached = _aura_nav_cache_read(cache, _AURA_NAV_CONTEXT_TTL_SECONDS)
    if cached:
        return cached

    latitudes = ",".join(f"{p[1]:.5f}" for _,p in route_samples)
    longitudes = ",".join(f"{p[0]:.5f}" for _,p in route_samples)
    params = {
        "latitude": latitudes,
        "longitude": longitudes,
        "hourly": "temperature_2m,apparent_temperature,precipitation_probability,precipitation,weather_code,wind_speed_10m,wind_gusts_10m,visibility",
        "forecast_days": "8",
        "timeformat": "unixtime",
        "timezone": "GMT",
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
    }
    url = _AURA_NAV_CONTEXT_WEATHER_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": _AURA_NAV_USER_AGENT, "Accept": "application/json", "Connection": "close"},
        method="GET",
    )
    stale = _aura_nav_context_stale(cache)
    try:
        _aura_nav_rate_limit("weather")
        with urllib.request.urlopen(req, timeout=_AURA_NAV_CONTEXT_HTTP_TIMEOUT_SECONDS) as response:
            status = int(getattr(response, "status", 200) or 200)
            raw = response.read(_AURA_NAV_CONTEXT_MAX_BYTES + 1)
        if status != 200:
            raise RuntimeError(f"weather_http_{status}")
        if len(raw) > _AURA_NAV_CONTEXT_MAX_BYTES:
            raise RuntimeError("weather_response_too_large")
        payload = json.loads(raw.decode("utf-8"))
        locations = payload if isinstance(payload, list) else [payload]
        if len(locations) != len(route_samples):
            raise RuntimeError("weather_location_count")
        samples = []
        overall_score = 0
        overall_reasons = []
        for i, ((fraction, point), location) in enumerate(zip(route_samples, locations)):
            hourly = (location or {}).get("hourly") or {}
            times = hourly.get("time") or []
            if not times:
                continue
            eta = departure + duration * fraction
            try:
                nearest = min(range(len(times)), key=lambda j: abs(float(times[j]) - eta))
            except Exception:
                continue
            if abs(float(times[nearest]) - eta) > 3*3600:
                continue
            sample = {
                "fraction": round(float(fraction), 4),
                "lat": round(float(point[1]), 6),
                "lon": round(float(point[0]), 6),
                "eta_ts": int(round(eta)),
                "forecast_ts": int(float(times[nearest])),
                "temperature": _aura_nav_context_num(hourly.get("temperature_2m") or [], nearest),
                "apparent_temperature": _aura_nav_context_num(hourly.get("apparent_temperature") or [], nearest),
                "precipitation_probability": _aura_nav_context_num(hourly.get("precipitation_probability") or [], nearest),
                "precipitation": _aura_nav_context_num(hourly.get("precipitation") or [], nearest),
                "weather_code": _aura_nav_context_num(hourly.get("weather_code") or [], nearest),
                "wind_speed": _aura_nav_context_num(hourly.get("wind_speed_10m") or [], nearest),
                "wind_gusts": _aura_nav_context_num(hourly.get("wind_gusts_10m") or [], nearest),
                "visibility": _aura_nav_context_num(hourly.get("visibility") or [], nearest),
            }
            level, reasons = _aura_nav_context_risk(sample)
            sample["risk_level"] = level
            sample["risk_reasons"] = reasons[:3]
            score = 2 if level == "difficult" else 1 if level == "watch" else 0
            overall_score = max(overall_score, score)
            for reason in reasons:
                if reason not in overall_reasons:
                    overall_reasons.append(reason)
            samples.append(sample)
        level = "difficult" if overall_score >= 2 else "watch" if overall_score == 1 else "normal"
        data = {
            "ok": True,
            "source": "open-meteo",
            "cache_state": "network",
            "departure_ts": int(round(departure)),
            "departure_adjusted": bool(adjusted),
            "duration_s": round(duration, 1),
            "distance_m": round(distance, 1),
            "traffic": {
                "live": False,
                "source": "osrm-routing-baseline",
                "message": "Trafic temps réel non connecté · durée OSRM hors trafic live",
            },
            "risk": {"level": level, "reasons": overall_reasons[:5]},
            "weather_samples": samples,
            "weather_sample_count": len(samples),
        }
        _aura_nav_cache_write(cache, data)
        try:
            rt.log(
                "AURA route context weather samples=%s risk=%s distance=%.0fm duration=%.0fs departure=%s",
                len(samples), level, distance, duration, int(departure)
            )
        except Exception:
            pass
        return data
    except Exception as exc:
        try:
            rt.log("AURA route context weather upstream failed type=%s detail=%s", type(exc).__name__, str(exc)[:220])
        except Exception:
            pass
        if stale:
            return stale
        raise

# AURA P0.6.6.3 SEND TO PHONE LOCAL QR SERVICE
import math
_AURA_NAV_SHARE_MAX_URL = 1800
_AURA_NAV_SHARE_MAX_MATRIX = 177


def _aura_nav_share_coord(value, lo, hi, field):
    try:
        value = float(value)
    except Exception:
        raise ValueError(field)
    if not math.isfinite(value) or value < lo or value > hi:
        raise ValueError(field)
    return value


def _aura_nav_share_point(value, field):
    if not isinstance(value, dict):
        raise ValueError(field)
    lat = _aura_nav_share_coord(value.get('lat'), -85.0, 85.0, field + '_lat')
    lon = _aura_nav_share_coord(value.get('lon'), -180.0, 180.0, field + '_lon')
    label = str(value.get('label') or '').strip()[:180]
    return {'lat': lat, 'lon': lon, 'label': label}


def _aura_nav_share_coord_text(point):
    return f"{point['lat']:.6f},{point['lon']:.6f}"


def _aura_nav_share_build_url(provider, origin, destination, use_phone_location):
    provider = str(provider or 'google').strip().lower()
    if provider not in {'google', 'apple'}:
        raise ValueError('share_provider')
    dest = _aura_nav_share_coord_text(destination)
    if provider == 'google':
        params = [('api', '1'), ('destination', dest), ('travelmode', 'driving'), ('dir_action', 'navigate')]
        if not use_phone_location:
            params.insert(1, ('origin', _aura_nav_share_coord_text(origin)))
        return 'https://www.google.com/maps/dir/?' + urllib.parse.urlencode(params)
    # Apple Maps legacy map link remains broadly compatible across Apple platforms.
    params = [('daddr', dest), ('dirflg', 'd')]
    if not use_phone_location:
        params.insert(0, ('saddr', _aura_nav_share_coord_text(origin)))
    return 'https://maps.apple.com/?' + urllib.parse.urlencode(params)


def _aura_nav_share_qr_rows(url):
    if not isinstance(url, str) or not url or len(url) > _AURA_NAV_SHARE_MAX_URL:
        raise ValueError('share_url')
    try:
        from aura_qr_vendor.main import QRCode
        from aura_qr_vendor.constants import ERROR_CORRECT_M
    except Exception as exc:
        raise RuntimeError('share_qr_backend') from exc
    qr = QRCode(version=None, error_correction=ERROR_CORRECT_M, box_size=1, border=4)
    qr.add_data(url, optimize=20)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    size = len(matrix)
    if size < 21 or size > _AURA_NAV_SHARE_MAX_MATRIX or any(len(row) != size for row in matrix):
        raise RuntimeError('share_qr_matrix')
    return [''.join('1' if cell else '0' for cell in row) for row in matrix]


def _aura_nav_share_payload(data):
    if not isinstance(data, dict):
        raise ValueError('share_request')
    origin = _aura_nav_share_point(data.get('origin'), 'share_origin')
    destination = _aura_nav_share_point(data.get('destination'), 'share_destination')
    provider = str(data.get('provider') or 'google').strip().lower()
    use_phone_location = bool(data.get('use_phone_location'))
    url = _aura_nav_share_build_url(provider, origin, destination, use_phone_location)
    rows = _aura_nav_share_qr_rows(url)
    return {
        'ok': True,
        'provider': provider,
        'url': url,
        'use_phone_location': use_phone_location,
        'origin': origin,
        'destination': destination,
        'qr': {'size': len(rows), 'rows': rows},
        'route_fidelity': 'provider_recalculates',
        'privacy': 'QR generated locally; coordinates leave AURA only when the mobile map link is opened.',
    }



# AURA P0.7.4 VITALS LOCAL READ-ONLY BRIDGE
def _aura_p074_vitals_file(rt):
    override=str(os.getenv('AURA_VITALS_FILE') or '').strip()
    if override:
        return Path(override).expanduser()
    local=str(os.getenv('LOCALAPPDATA') or '').strip()
    if local:
        return Path(local)/'AURA'/'vitals'/'latest.json'
    return rt.root.parent/'vitals'/'latest.json'

def _aura_p074_num(value, lo, hi):
    try:n=float(value)
    except Exception:return None
    if not (lo <= n <= hi):return None
    return n

def _aura_p074_text(value, limit=120):
    return ' '.join(str(value or '').split())[:limit]

def _aura_p074_activity(raw):
    raw=raw if isinstance(raw,dict) else {}
    spec={
        'move_kcal':(0,20000),'move_goal_kcal':(1,20000),
        'exercise_min':(0,1440),'exercise_goal_min':(1,1440),
        'stand_hours':(0,24),'stand_goal_hours':(1,24),
        'steps':(0,200000),'distance_km':(0,500),'active_energy_kcal':(0,20000),
    }
    return {k:_aura_p074_num(raw.get(k),*bounds) for k,bounds in spec.items()}

def _aura_p074_sanitize(raw):
    raw=raw if isinstance(raw,dict) else {}
    data=raw.get('data') if isinstance(raw.get('data'),dict) else raw
    out={
        'source':_aura_p074_text(raw.get('source') or data.get('source'),80),
        'device':_aura_p074_text(raw.get('device') or data.get('device'),100),
        'updated_at':_aura_p074_text(raw.get('updated_at') or data.get('updated_at'),60),
        'heart_rate_bpm':_aura_p074_num(data.get('heart_rate_bpm'),20,260),
        'resting_heart_rate_bpm':_aura_p074_num(data.get('resting_heart_rate_bpm'),20,200),
        'hrv_ms':_aura_p074_num(data.get('hrv_ms'),0,500),
        'spo2_percent':_aura_p074_num(data.get('spo2_percent'),50,100),
        'temperature_c':_aura_p074_num(data.get('temperature_c'),25,45),
        'respiratory_rate_bpm':_aura_p074_num(data.get('respiratory_rate_bpm'),4,60),
        'sleep_duration_hours':_aura_p074_num(data.get('sleep_duration_hours'),0,24),
        'activity':_aura_p074_activity(data.get('activity')),
        'heart_rate_series':[], 'workouts':[],
    }
    series=data.get('heart_rate_series') if isinstance(data.get('heart_rate_series'),list) else []
    for item in series[-1440:]:
        if not isinstance(item,dict):continue
        bpm=_aura_p074_num(item.get('bpm'),20,260); stamp=_aura_p074_text(item.get('time'),40)
        if bpm is not None and stamp:out['heart_rate_series'].append({'time':stamp,'bpm':bpm})
    workouts=data.get('workouts') if isinstance(data.get('workouts'),list) else []
    for item in workouts[:20]:
        if not isinstance(item,dict):continue
        name=_aura_p074_text(item.get('name') or item.get('type'),80)
        if not name:continue
        out['workouts'].append({
            'name':name,'start':_aura_p074_text(item.get('start'),40),
            'duration_min':_aura_p074_num(item.get('duration_min'),0,1440),
            'distance_km':_aura_p074_num(item.get('distance_km'),0,500),
            'energy_kcal':_aura_p074_num(item.get('energy_kcal'),0,20000),
            'avg_heart_rate_bpm':_aura_p074_num(item.get('avg_heart_rate_bpm'),20,260),
        })
    return out

def _aura_p074_vitals_snapshot(rt):
    path=_aura_p074_vitals_file(rt)
    base={'ok':True,'connected':False,'read_only':True,'external_network':False,'path':str(path),'schema':'aura.vitals.local.v1'}
    try:
        if not path.is_file():return base
        if path.stat().st_size > 2*1024*1024:return {**base,'error':'snapshot_too_large'}
        raw=json.loads(path.read_text(encoding='utf-8'))
        data=_aura_p074_sanitize(raw)
        has=any(data.get(k) is not None for k in ('heart_rate_bpm','hrv_ms','spo2_percent','temperature_c','respiratory_rate_bpm','sleep_duration_hours')) or any(v is not None for v in data.get('activity',{}).values())
        return {**base,'connected':bool(has),'source':data.get('source',''),'device':data.get('device',''),'updated_at':data.get('updated_at',''),'mtime':path.stat().st_mtime,'data':data}
    except (OSError,ValueError,TypeError,json.JSONDecodeError) as exc:
        return {**base,'error':'invalid_snapshot','detail':type(exc).__name__}
# AURA P0.7.4 VITALS LOCAL READ-ONLY BRIDGE END

def make_handler(rt:ShellRuntime):
    class H(BaseHTTPRequestHandler):
        server_version='AURA-RC4.2/1.0'; protocol_version='HTTP/1.1'
        def log_message(self,*a):return
        def end_headers(self):
            self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            super().end_headers()
        def auth(self):
            q=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            return secrets.compare_digest((q.get('token')or[''])[0],rt.token)
        def origin_ok(self):
            o=self.headers.get('Origin','')
            return not o or o in {f'http://127.0.0.1:{rt.port}',f'http://localhost:{rt.port}'}
        def send_json(self,code,obj):
            b=json.dumps(obj,separators=(',',':'),ensure_ascii=False).encode('utf-8'); self.send_response(code); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
        def read_json(self,max_bytes=8192):
            n=int(self.headers.get('Content-Length','0') or 0)
            if n<0 or n>max_bytes:raise ValueError('payload_too_large')
            raw=self.rfile.read(n) if n else b'{}'
            return json.loads(raw.decode('utf-8','strict'))
        # AURA_M180_UI4_R4_R1_MUSIC_PROXY
        def _aura_music_proxy(self,path,method):
            import json as _j
            import urllib.request as _u
            import urllib.error as _e
            try:
                suffix=str(path)[len('/api/music-premium'):]
                if not suffix.startswith('/'):
                    suffix='/'+suffix
                target='http://127.0.0.1:18180'+suffix
                body=None
                headers={'Accept':'application/json'}
                if str(method).upper()=='POST':
                    try:
                        n=int(self.headers.get('Content-Length','0') or 0)
                    except Exception:
                        n=0
                    if n<0 or n>(10*1024*1024):
                        return self.send_json(413,{'ok':False,'error':'music_proxy_payload_too_large'})
                    body=self.rfile.read(n) if n else b'{}'
                    headers['Content-Type']='application/json'
                req=_u.Request(target,data=body,headers=headers,method=str(method).upper())
                with _u.urlopen(req,timeout=15) as resp:
                    raw=resp.read()
                    try:
                        payload=_j.loads(raw.decode('utf-8')) if raw else {'ok':True}
                    except Exception:
                        payload={'ok':False,'error':'music_proxy_invalid_json'}
                    return self.send_json(int(getattr(resp,'status',200) or 200),payload)
            except _e.HTTPError as exc:
                try:
                    raw=exc.read()
                    payload=_j.loads(raw.decode('utf-8')) if raw else {'ok':False,'error':'music_bridge_http_error'}
                except Exception:
                    payload={'ok':False,'error':'music_bridge_http_error'}
                return self.send_json(int(getattr(exc,'code',502) or 502),payload)
            except Exception as exc:
                try:
                    rt.log('AURA music premium proxy failed type=%s detail=%s',type(exc).__name__,str(exc)[:220])
                except Exception:
                    pass
                return self.send_json(502,{'ok':False,'error':'music_bridge_unavailable','detail':str(exc)[:220]})
        def do_POST(self):
            path=urllib.parse.urlparse(self.path).path
            if not self.auth() or not self.origin_ok():return self.send_json(403,{'ok':False,'error':'forbidden'})

            # AURA I18N R2 â€” authenticated locale settings endpoint
            if path=='/api/locale':
                try:
                    body=self.read_json()
                    action=str((body or {}).get('action') or 'get').strip().casefold()
                    locale_path=(Path(os.environ.get('APPDATA') or (Path.home()/'AppData'/'Roaming'))/'AURA'/'config'/'locale.json')

                    def _current_locale():
                        try:
                            if locale_path.is_file():
                                raw=json.loads(locale_path.read_text(encoding='utf-8'))
                                loc=str(raw.get('locale') or '').strip()
                                if loc in {'fr-FR','en-US'}:
                                    return loc
                        except Exception:
                            pass
                        raw=str(os.environ.get('AURA_LOCALE') or 'fr-FR').strip()
                        return 'en-US' if raw.lower().startswith('en') else 'fr-FR'

                    if action=='get':
                        return self.send_json(200,{'ok':True,'locale':_current_locale(),'hot_switch':True})

                    if action!='set':
                        return self.send_json(400,{'ok':False,'error':'unsupported_locale_action'})

                    loc=str((body or {}).get('locale') or '').strip()
                    if loc not in {'fr-FR','en-US'}:
                        return self.send_json(400,{'ok':False,'error':'unsupported_locale'})

                    locale_path.parent.mkdir(parents=True,exist_ok=True)
                    tmp=locale_path.with_suffix('.json.tmp')
                    tmp.write_text(json.dumps({
                        'schema':'aura.locale.v1',
                        'locale':loc,
                        'ui_language':loc,
                        'conversation_language':loc,
                    },ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                    os.replace(tmp,locale_path)

                    lang='en' if loc=='en-US' else 'fr'
                    response_lang='English' if loc=='en-US' else 'French'
                    os.environ['AURA_LOCALE']=loc
                    os.environ['STT_LANGUAGE']=lang
                    os.environ['AURA_TTS_LANGUAGE']=lang
                    os.environ['XTTS_LANGUAGE']=lang
                    os.environ['AURA_RESPONSE_LANGUAGE']=response_lang

                    try:
                        from config.settings import settings as _aura_i18n_settings
                        _aura_i18n_settings.STT_LANGUAGE=lang
                        _aura_i18n_settings.XTTS_LANGUAGE=lang
                    except Exception:
                        pass

                    try:
                        boot=Path(rt.root)/'dist'/'assets'/'aura-selected-locale.js'
                        boot.parent.mkdir(parents=True,exist_ok=True)
                        boot.write_text('window.__AURA_BOOT_LOCALE__='+json.dumps(loc)+';\n',encoding='utf-8')
                    except Exception:
                        pass

                    try:
                        rt.hub.send('locale.changed',{'locale':loc,'language':lang})
                    except Exception:
                        pass

                    return self.send_json(200,{
                        'ok':True,
                        'locale':loc,
                        'stt_language':lang,
                        'tts_language':lang,
                        'response_language':response_lang,
                        'hot_switch':True,
                    })
                except Exception as e:
                    logging.getLogger('aura.rc4_2.shell').exception('AURA locale update failed')
                    return self.send_json(500,{'ok':False,'error':type(e).__name__})
            if path.startswith('/api/music-premium/'):
                return self._aura_music_proxy(path,'POST')
            if path=='/api/heartbeat':
                rt.last_heartbeat=time.monotonic(); rt.client_seen=True
                return self.send_json(200,{'ok':True,'voice_ready':rt.voice_ready,'voice_warming':rt.voice_warming,'voice_result':rt.voice_last_result,'voice_state':('ready' if rt.voice_ready else 'warming' if rt.voice_warming else 'standby')})
            if path=='/api/client-info':
                try:
                    info=self.read_json(2048); rt.log('Visual adapter report renderer=%s dpr=%s',str(info.get('webgl_renderer',''))[:220],info.get('dpr'))
                except Exception:pass
                return self.send_json(200,{'ok':True})
            if path=='/api/files/upload':
                if not rt.ui_ready:return self.send_json(409,{'ok':False,'error':'runtime_not_ready'})
                try:n=int(self.headers.get('Content-Length','0') or 0)
                except Exception:return self.send_json(400,{'ok':False,'error':'invalid_content_length'})
                max_bytes=25*1024*1024
                if n<=0:return self.send_json(400,{'ok':False,'error':'empty_file'})
                if n>max_bytes:return self.send_json(413,{'ok':False,'error':'file_too_large','max_bytes':max_bytes})
                raw_name=urllib.parse.unquote(str(self.headers.get('X-AURA-Filename','') or '')).strip()
                name=Path(raw_name).name[:240]
                ext=Path(name).suffix.casefold()
                allowed={'.pdf','.docx','.pptx','.xlsx','.txt','.md','.log','.py','.json','.csv','.tsv','.xml','.yaml','.yml','.ini','.cfg','.toml','.html','.htm'}
                if not name or ext not in allowed:return self.send_json(415,{'ok':False,'error':'unsupported_file_type'})
                safe_name=''.join(ch if (ch.isalnum() or ch in '._- ()[]') else '_' for ch in name).strip(' .') or ('document'+ext)
                target=(rt.upload_dir/f'{time.time_ns()}_{safe_name}').resolve()
                try:target.relative_to(rt.upload_dir.resolve())
                except Exception:return self.send_json(403,{'ok':False,'error':'invalid_upload_path'})
                remaining=n
                try:
                    with target.open('wb') as handle:
                        while remaining>0:
                            chunk=self.rfile.read(min(1024*1024,remaining))
                            if not chunk:raise ValueError('incomplete_upload')
                            handle.write(chunk); remaining-=len(chunk)
                    if target.stat().st_size!=n:raise ValueError('incomplete_upload')
                    rt.commands.put_nowait({'action':'file_load','path':str(target)})
                except queue.Full:
                    target.unlink(missing_ok=True);return self.send_json(429,{'ok':False,'error':'command_queue_full'})
                except Exception:
                    target.unlink(missing_ok=True);return self.send_json(400,{'ok':False,'error':'upload_failed'})
                return self.send_json(202,{'ok':True,'accepted':'file_load','name':name,'size_bytes':n})
            if path=='/api/nav/pois':
                try:
                    data = self.read_json(65536)
                    result = _aura_nav_poi_search(
                        rt,
                        data.get('category'),
                        data.get('radius_m', 2000),
                        data.get('geometry'),
                    )
                    return self.send_json(200, result)
                except (ValueError, TypeError):
                    return self.send_json(400, {'ok':False,'error':'invalid_poi_request'})
                except (urllib.error.URLError, TimeoutError):
                    return self.send_json(502, {'ok':False,'error':'poi_unavailable'})
                except (BrokenPipeError, ConnectionResetError):
                    return
                except Exception as exc:
                    try:
                        rt.log(
                            'AURA navigation POI failed type=%s detail=%s',
                            type(exc).__name__, str(exc)[:220]
                        )
                    except Exception:
                        pass
                    return self.send_json(502, {'ok':False,'error':'poi_unavailable'})
            # AURA ROADMAP V25-F1 — POST /api/roadmap-conversation
            if path=='/api/roadmap-conversation':
                if not self.auth() or not self.origin_ok():return self.send_json(403,{'ok':False,'error':'forbidden'})
                if not rt.ui_ready:return self.send_json(409,{'ok':False,'error':'runtime_not_ready'})
                try:data=self.read_json(32768)
                except Exception:return self.send_json(400,{'ok':False,'error':'invalid_json'})
                try:
                    _text=str(data.get('text') or '').strip()
                    _root=Path(os.environ.get('AURA_ROOT') or Path(__file__).resolve().parents[4]).resolve()
                    if str(_root) not in sys.path:sys.path.insert(0,str(_root))
                    from runtime.aura_roadmap_conversation_v25f import handle_roadmap_conversation_v25f
                    _result=handle_roadmap_conversation_v25f(_text,root=_root)
                    if _result.get('handled'):
                        _user={'text':_text,'message':_text,'content':_text,'source':'roadmap-v25f'}
                        _reply=str(_result.get('response') or '')
                        _aura={'text':_reply,'message':_reply,'content':_reply,'source':'roadmap-v25f','intent':_result.get('intent')}
                        rt.hub.send('user_message',_user)
                        rt.hub.send('aura_message',_aura)
                    return self.send_json(200,_result)
                except Exception as exc:
                    rt.log('Roadmap V25-F1 conversation failed',exc_info=True)
                    return self.send_json(400,{'ok':False,'error':type(exc).__name__,'message':str(exc)[:800]})
            # AURA ROADMAP V25-E1 — POST /api/roadmap
            if path=='/api/roadmap':
                if not self.auth() or not self.origin_ok():return self.send_json(403,{'ok':False,'error':'forbidden'})
                if not rt.ui_ready:return self.send_json(409,{'ok':False,'error':'runtime_not_ready'})
                try:data=self.read_json(65536)
                except Exception:return self.send_json(400,{'ok':False,'error':'invalid_json'})
                try:
                    _root=Path(os.environ.get('AURA_ROOT') or Path(__file__).resolve().parents[4]).resolve()
                    if str(_root) not in sys.path:sys.path.insert(0,str(_root))
                    from runtime.aura_roadmap_http_bridge_v25e import RoadmapHttpBridgeV25E
                    _result=RoadmapHttpBridgeV25E(root=_root).mutate(data)
                    return self.send_json(200,_result)
                except Exception as exc:
                    rt.log('Roadmap V25-E1 mutation failed',exc_info=True)
                    return self.send_json(400,{'ok':False,'error':type(exc).__name__,'message':str(exc)[:800]})
            if path=='/api/action':
                if not rt.ui_ready:return self.send_json(409,{'ok':False,'error':'runtime_not_ready'})
                try:data=self.read_json(16384)
                except Exception:return self.send_json(400,{'ok':False,'error':'invalid_json'})
                action=str(data.get('action',''))
                if action not in COMMANDS:return self.send_json(403,{'ok':False,'error':'action_not_allowed'})
                cmd={'action':action}
                if action=='send_message':
                    text=safe_text(data.get('text',''),4000).strip()
                    if not text:return self.send_json(400,{'ok':False,'error':'empty_message'})
                    cmd['text']=text
                elif action=='voice_speak':
                    text=safe_text(data.get('text',''),520).strip()
                    if not text:return self.send_json(400,{'ok':False,'error':'empty_voice_speech'})
                    cmd['text']=text
                    cmd['source']=safe_text(data.get('source','ui-feedback'),80).strip() or 'ui-feedback'
                elif action=='nav_speak':
                    text=safe_text(data.get('text',''),360).strip()
                    if not text:return self.send_json(400,{'ok':False,'error':'empty_nav_speech'})
                    cmd['text']=text
                elif action=='research_query':
                    text=safe_text(data.get('text',''),800).strip()
                    if not text:return self.send_json(400,{'ok':False,'error':'empty_research_query'})
                    cmd['text']=text
                elif action=='weather_current':
                    try:
                        _lat=float(data.get('latitude'))
                        _lon=float(data.get('longitude'))
                        _accuracy=data.get('accuracy')
                        _accuracy=float(_accuracy) if _accuracy is not None else None
                    except (TypeError,ValueError):
                        return self.send_json(400,{'ok':False,'error':'invalid_coordinates'})
                    if not (-90.0<=_lat<=90.0 and -180.0<=_lon<=180.0):
                        return self.send_json(400,{'ok':False,'error':'invalid_coordinates'})
                    cmd['latitude']=_lat;cmd['longitude']=_lon;cmd['accuracy']=_accuracy
                elif action=='system_open_safe_app':
                    app_id=safe_text(data.get('app_id',''),40).casefold().strip()
                    if app_id not in {'calculator','notepad','explorer','paint'}:
                        return self.send_json(400,{'ok':False,'error':'app_not_allowlisted'})
                    cmd['app_id']=app_id
                elif action=='system_authorize_folder':
                    folder_path=str(data.get('path','') or '').replace('\x00',' ').strip()[:1024]
                    label=safe_text(data.get('label',''),80).strip()
                    if not folder_path:
                        return self.send_json(400,{'ok':False,'error':'empty_folder_path'})
                    cmd['path']=folder_path;cmd['label']=label
                elif action in {'system_revoke_folder','system_open_folder','system_scan_folder'}:
                    folder_id=safe_text(data.get('folder_id',''),32).casefold().strip()
                    if len(folder_id)!=16 or any(ch not in '0123456789abcdef' for ch in folder_id):
                        return self.send_json(400,{'ok':False,'error':'invalid_folder_id'})
                    cmd['folder_id']=folder_id
                elif action=='system_read_authorized_file':
                    folder_id=safe_text(data.get('folder_id',''),32).casefold().strip()
                    file_id=safe_text(data.get('file_id',''),32).casefold().strip()
                    for value,label in ((folder_id,'folder_id'),(file_id,'file_id')):
                        if len(value)!=16 or any(ch not in '0123456789abcdef' for ch in value):
                            return self.send_json(400,{'ok':False,'error':f'invalid_{label}'})
                    cmd['folder_id']=folder_id;cmd['file_id']=file_id
                elif action=='system_analyze_authorized_file':
                    folder_id=safe_text(data.get('folder_id',''),32).casefold().strip()
                    file_id=safe_text(data.get('file_id',''),32).casefold().strip()
                    mode=safe_text(data.get('mode',''),16).casefold().strip()
                    query=safe_text(data.get('query',''),600).strip()
                    for value,label in ((folder_id,'folder_id'),(file_id,'file_id')):
                        if len(value)!=16 or any(ch not in '0123456789abcdef' for ch in value):
                            return self.send_json(400,{'ok':False,'error':f'invalid_{label}'})
                    if mode not in {'summary','search','context'}:
                        return self.send_json(400,{'ok':False,'error':'invalid_analysis_mode'})
                    if mode in {'search','context'} and not query:
                        return self.send_json(400,{'ok':False,'error':'analysis_query_required'})
                    cmd['folder_id']=folder_id;cmd['file_id']=file_id
                    cmd['mode']=mode;cmd['query']=query
                elif action=='system_analyze_authorized_project':
                    folder_id=safe_text(data.get('folder_id',''),32).casefold().strip()
                    mode=safe_text(data.get('mode',''),16).casefold().strip()
                    query=safe_text(data.get('query',''),600).strip()
                    if len(folder_id)!=16 or any(ch not in '0123456789abcdef' for ch in folder_id):
                        return self.send_json(400,{'ok':False,'error':'invalid_folder_id'})
                    if mode not in {'summary','search','context'}:
                        return self.send_json(400,{'ok':False,'error':'invalid_project_analysis_mode'})
                    if mode in {'search','context'} and not query:
                        return self.send_json(400,{'ok':False,'error':'project_query_required'})
                    cmd['folder_id']=folder_id;cmd['mode']=mode;cmd['query']=query
                elif action=='workspace_context':
                    # AURA P0.7.2 WORKSPACE CONTEXT CONTRACT: sanitized metadata v2
                    workspace=safe_text(data.get('workspace','home'),32).casefold().strip() or 'home'
                    if workspace not in {'home','talk','plan','weather','memory','system','maps'}:
                        return self.send_json(400,{'ok':False,'error':'invalid_workspace'})
                    cmd['workspace']=workspace
                    cmd['clear_context']=bool(data.get('clear_context',False))
                    raw_ctx=data.get('context')
                    if raw_ctx is not None:
                        if not isinstance(raw_ctx,dict):return self.send_json(400,{'ok':False,'error':'invalid_workspace_context'})
                        ctx={'schema':'aura.workspace-context.v2','workspace':workspace,'submode':safe_text(raw_ctx.get('submode',''),40).strip(),'target':safe_text(raw_ctx.get('target',''),280).strip(),'summary':safe_text(raw_ctx.get('summary',''),1400).strip(),'facts':[],'refs':[],'cleared':bool(raw_ctx.get('cleared',False))}
                        facts=raw_ctx.get('facts') if isinstance(raw_ctx.get('facts'),list) else []
                        for item in facts[:12]:
                            if not isinstance(item,dict):continue
                            label=safe_text(item.get('label') or item.get('key',''),80).strip();value=safe_text(item.get('value',''),320).strip()
                            if label and value:ctx['facts'].append({'key':safe_text(item.get('key',''),40).strip(),'label':label,'value':value,'source':safe_text(item.get('source',''),48).strip()})
                        refs=raw_ctx.get('refs') if isinstance(raw_ctx.get('refs'),list) else []
                        for item in refs[:8]:
                            if not isinstance(item,dict):continue
                            label=safe_text(item.get('label',''),180).strip()
                            if label:ctx['refs'].append({'type':safe_text(item.get('type',''),32).strip(),'id':safe_text(item.get('id',''),96).strip(),'label':label})
                        cmd['context']=ctx
                elif action=='file_clear':
                    pass
                elif action=='task_create':
                    title=safe_text(data.get('title',''),280).strip()
                    if not title:return self.send_json(400,{'ok':False,'error':'empty_task_title'})
                    cmd['title']=title;cmd['due_date']=safe_text(data.get('due_date',''),64).strip()
                elif action=='task_complete':
                    identifier=safe_text(data.get('identifier',''),280).strip()
                    if not identifier:return self.send_json(400,{'ok':False,'error':'empty_task_identifier'})
                    cmd['identifier']=identifier
                elif action=='reminder_create':
                    content=safe_text(data.get('content',''),500).strip();trigger=safe_text(data.get('trigger_at',''),80).strip()
                    if not content or not trigger:return self.send_json(400,{'ok':False,'error':'invalid_reminder'})
                    cmd['content']=content;cmd['trigger_at']=trigger
                elif action in {'reminder_delete','note_delete'}:
                    try:item_id=int(data.get('id',0) or 0)
                    except Exception:item_id=0
                    if item_id<=0:return self.send_json(400,{'ok':False,'error':'invalid_id'})
                    cmd['id']=item_id
                elif action=='note_create':
                    content=str(data.get('content','') or '').replace('\\x00',' ').strip()[:8000]
                    if not content:return self.send_json(400,{'ok':False,'error':'empty_note_content'})
                    cmd['content']=content;cmd['title']=safe_text(data.get('title',''),220).strip()
                elif action=='memory_create':
                    content=str(data.get('content','') or '').replace('\\x00',' ').strip()[:1800]
                    if not content:return self.send_json(400,{'ok':False,'error':'empty_memory'})
                    memory_type=safe_text(data.get('memory_type',''),40).casefold().strip()
                    if memory_type not in {'','fact','preference','project','goal','habit'}:
                        return self.send_json(400,{'ok':False,'error':'invalid_memory_type'})
                    try:importance=max(1,min(5,int(data.get('importance',3) or 3)))
                    except Exception:importance=3
                    cmd['content']=content;cmd['memory_type']=memory_type;cmd['importance']=importance
                elif action=='memory_delete':
                    try:item_id=int(data.get('id',0) or 0)
                    except Exception:item_id=0
                    if item_id<=0:return self.send_json(400,{'ok':False,'error':'invalid_memory_id'})
                    cmd['id']=item_id
                elif action=='memory_private':
                    cmd['enabled']=bool(data.get('enabled'))
                elif action=='memory_clear_profile':
                    if safe_text(data.get('confirm',''),32).strip().upper()!='EFFACER':
                        return self.send_json(400,{'ok':False,'error':'confirmation_required'})
                try:rt.commands.put_nowait(cmd)
                except queue.Full:return self.send_json(429,{'ok':False,'error':'command_queue_full'})
                return self.send_json(202,{'ok':True,'accepted':action})
            if path=='/api/nav/share':
                try:
                    data=self.read_json(16384)
                except Exception:
                    return self.send_json(400,{'ok':False,'error':'invalid_share_request'})
                try:
                    result=_aura_nav_share_payload(data)
                    return self.send_json(200,result)
                except ValueError as exc:
                    try:rt.log('AURA send-to-phone rejected code=%s',str(exc)[:80])
                    except Exception:pass
                    return self.send_json(400,{'ok':False,'error':'invalid_share_request'})
                except (BrokenPipeError,ConnectionResetError):
                    return
                except Exception as exc:
                    try:rt.log('AURA send-to-phone QR failed type=%s detail=%s',type(exc).__name__,str(exc)[:220])
                    except Exception:pass
                    return self.send_json(500,{'ok':False,'error':'share_qr_unavailable'})
            if path=='/api/nav/context':
                try:
                    data=self.read_json(65536)
                except Exception:
                    return self.send_json(400,{'ok':False,'error':'invalid_context_request'})
                try:
                    result=_aura_nav_context_forecast(
                        rt,
                        data.get('geometry'),
                        data.get('duration_s'),
                        data.get('distance_m'),
                        data.get('departure_ts'),
                    )
                    return self.send_json(200,result)
                except ValueError as exc:
                    code=str(exc)
                    if code=='weather_horizon':
                        return self.send_json(422,{'ok':False,'error':'weather_horizon'})
                    return self.send_json(400,{'ok':False,'error':'invalid_context_request'})
                except (urllib.error.URLError,TimeoutError):
                    return self.send_json(502,{'ok':False,'error':'route_context_unavailable'})
                except (BrokenPipeError,ConnectionResetError):
                    return
                except Exception as exc:
                    try:rt.log('AURA route context proxy failed type=%s detail=%s',type(exc).__name__,str(exc)[:220])
                    except Exception:pass
                    return self.send_json(502,{'ok':False,'error':'route_context_unavailable'})
            if path in {'/api/shutdown','/api/client-close'}:
                if path=='/api/client-close':rt.client_closed.set()
                rt.shutdown.set(); return self.send_json(200,{'ok':True})
            return self.send_json(404,{'ok':False})
        def do_GET(self):
            _aura_music_path=urllib.parse.urlparse(self.path).path
            if _aura_music_path.startswith('/api/music-premium/'):
                if not self.auth() or not self.origin_ok():return self.send_json(403,{'ok':False,'error':'forbidden'})
                return self._aura_music_proxy(_aura_music_path,'GET')

            # AURA_ADF_H_R6_2_SELFTEST_ENDPOINT_BEGIN
            if str(getattr(self, 'path', '')).startswith('/api/developer-selftest'):
                import hmac as _aura_r62_hmac
                import json as _aura_r62_json
                import os as _aura_r62_os
                from pathlib import Path as _AuraR62Path
                from urllib.parse import urlparse as _aura_r62_urlparse, parse_qs as _aura_r62_parse_qs
                try:
                    _aura_r62_u = _aura_r62_urlparse(str(self.path))
                    _aura_r62_q = _aura_r62_parse_qs(_aura_r62_u.query)
                    _aura_r62_supplied = str((_aura_r62_q.get('token') or [''])[0])
                    _aura_r62_session = _AuraR62Path(_aura_r62_os.environ.get('LOCALAPPDATA') or '') / 'AURA' / 'ui' / 'runtime' / 'rc4_2_session.json'
                    _aura_r62_sd = _aura_r62_json.loads(_aura_r62_session.read_text(encoding='utf-8')) if _aura_r62_session.is_file() else {}
                    _aura_r62_expected = str(_aura_r62_sd.get('token') or _aura_r62_sd.get('auth_token') or _aura_r62_sd.get('session_token') or '')
                    if (not _aura_r62_expected) or (not _aura_r62_hmac.compare_digest(_aura_r62_supplied, _aura_r62_expected)):
                        _aura_r62_payload = _aura_r62_json.dumps({'ok': False, 'error': 'unauthorized'}).encode('utf-8')
                        self.send_response(403)
                        self.send_header('Content-Type', 'application/json; charset=utf-8')
                        self.send_header('Cache-Control', 'no-store')
                        self.send_header('Content-Length', str(len(_aura_r62_payload)))
                        self.end_headers()
                        self.wfile.write(_aura_r62_payload)
                        return
                    _aura_r62_root = _AuraR62Path(_aura_r62_os.environ.get('AURA_ROOT') or _AuraR62Path(__file__).resolve().parents[4]).resolve()
                    _aura_r62_state_file = _aura_r62_root / 'runtime' / 'developer_fabric' / 'live_selftest_transaction_state.json'
                    _aura_r62_state = _aura_r62_json.loads(_aura_r62_state_file.read_text(encoding='utf-8')) if _aura_r62_state_file.is_file() else {'pending': None, 'last_receipt': None, 'last_rollback': None}
                    _aura_r62_payload = _aura_r62_json.dumps({'ok': True, 'state': _aura_r62_state}, ensure_ascii=False).encode('utf-8')
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json; charset=utf-8')
                    self.send_header('Cache-Control', 'no-store')
                    self.send_header('Content-Length', str(len(_aura_r62_payload)))
                    self.end_headers()
                    self.wfile.write(_aura_r62_payload)
                    return
                except Exception as _aura_r62_exc:
                    _aura_r62_payload = _aura_r62_json.dumps({'ok': False, 'error': type(_aura_r62_exc).__name__}).encode('utf-8')
                    self.send_response(500)
                    self.send_header('Content-Type', 'application/json; charset=utf-8')
                    self.send_header('Cache-Control', 'no-store')
                    self.send_header('Content-Length', str(len(_aura_r62_payload)))
                    self.end_headers()
                    self.wfile.write(_aura_r62_payload)
                    return
            # AURA_ADF_H_R6_2_SELFTEST_ENDPOINT_END
            u=urllib.parse.urlparse(self.path); path=u.path
            if path=='/api/events':
                if not self.auth():self.send_error(403);return
                self.send_response(200); self.send_header('Content-Type','text/event-stream'); self.send_header('Connection','keep-alive'); self.end_headers(); seq=0; rt.client_seen=True; rt.last_heartbeat=time.monotonic()
                try:
                    while not rt.shutdown.is_set():
                        items=rt.hub.wait(seq,10)
                        if not items:self.wfile.write(b': keepalive\n\n'); self.wfile.flush(); continue
                        for item in items:
                            seq=item['seq']; payload=json.dumps(item,separators=(',',':'),ensure_ascii=False).encode('utf-8')
                            self.wfile.write(b'id: '+str(seq).encode()+b'\n'); self.wfile.write(b'data: '+payload+b'\n\n')
                        self.wfile.flush()
                except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass
                return

            # AURA P0.5.2.7.1 MAP TILE LOOPBACK PROXY
            if path.startswith('/api/map-tile/'):
                if not self.auth():
                    return self.send_json(403, {'ok':False,'error':'forbidden'})
                try:
                    tail = path[len('/api/map-tile/'):]
                    parts = tail.split('/')
                    if len(parts) != 3:
                        raise ValueError("path")
                    z_s, x_s, y_file = parts
                    y_s = y_file[:-4] if y_file.casefold().endswith('.png') else y_file
                    z, x, y = _aura_map_tile_validate(z_s, x_s, y_s)
                    data, source = _aura_map_tile_get(rt, z, x, y)

                    self.send_response(200)
                    self.send_header('Content-Type', 'image/png')
                    self.send_header('Content-Length', str(len(data)))
                    self.send_header('Cache-Control', 'public, max-age=86400')
                    self.send_header('X-AURA-Map-Source', source)
                    self.send_header('X-Content-Type-Options', 'nosniff')
                    self.end_headers()
                    self.wfile.write(data)
                    return
                except ValueError:
                    return self.send_json(400, {'ok':False,'error':'invalid_map_tile'})
                except (BrokenPipeError, ConnectionResetError):
                    return
                except Exception as exc:
                    try:
                        rt.log('AURA map tile proxy failed type=%s detail=%s', type(exc).__name__, str(exc)[:220])
                    except Exception:
                        pass
                    return self.send_json(502, {'ok':False,'error':'map_tile_unavailable'})

            # AURA P0.5.2.8 OVERPASS CARTOGRAPHIC CONTEXT PROXY
            if path == '/api/map-context':
                if not self.auth():
                    return self.send_json(403, {'ok':False,'error':'forbidden'})
                try:
                    parsed = urllib.parse.urlparse(self.path)
                    query = urllib.parse.parse_qs(parsed.query)
                    lat = (query.get('lat') or [None])[0]
                    lon = (query.get('lon') or [None])[0]
                    radius_km = (query.get('radius_km') or [120])[0]

                    data = _aura_map_context_get(rt, lat, lon, radius_km)
                    return self.send_json(200, data)
                except (ValueError, TypeError):
                    return self.send_json(400, {'ok':False,'error':'invalid_map_context'})
                except (BrokenPipeError, ConnectionResetError):
                    return
                except Exception as exc:
                    try:
                        rt.log(
                            'AURA map context proxy failed type=%s detail=%s',
                            type(exc).__name__,
                            str(exc)[:220]
                        )
                    except Exception:
                        pass
                    return self.send_json(502, {'ok':False,'error':'map_context_unavailable'})

            # AURA P0.6.1 NAVIGATION GEOCODE + ROUTING PROXY
            if path == '/api/nav/geocode':
                if not self.auth():
                    return self.send_json(403, {'ok':False,'error':'forbidden'})
                try:
                    parsed = urllib.parse.urlparse(self.path)
                    query = urllib.parse.parse_qs(parsed.query)
                    q = (query.get('q') or [''])[0]
                    lat = (query.get('lat') or [None])[0]
                    lon = (query.get('lon') or [None])[0]
                    data = _aura_nav_geocode(rt, q, lat, lon)
                    status = 200 if data.get('ok') else 404
                    return self.send_json(status, data)
                except (ValueError, TypeError):
                    return self.send_json(400, {'ok':False,'error':'invalid_geocode'})
                except (urllib.error.URLError, TimeoutError):
                    return self.send_json(502, {'ok':False,'error':'geocode_unavailable'})
                except (BrokenPipeError, ConnectionResetError):
                    return
                except Exception as exc:
                    try:
                        rt.log(
                            'AURA navigation geocode failed type=%s detail=%s',
                            type(exc).__name__, str(exc)[:220]
                        )
                    except Exception:
                        pass
                    return self.send_json(502, {'ok':False,'error':'geocode_unavailable'})

            if path == '/api/nav/route':
                if not self.auth():
                    return self.send_json(403, {'ok':False,'error':'forbidden'})
                try:
                    parsed = urllib.parse.urlparse(self.path)
                    query = urllib.parse.parse_qs(parsed.query)
                    data = _aura_nav_route(
                        rt,
                        (query.get('from_lat') or [None])[0],
                        (query.get('from_lon') or [None])[0],
                        (query.get('to_lat') or [None])[0],
                        (query.get('to_lon') or [None])[0],
                        (query.get('profile') or ['driving'])[0],
                        (query.get('alternatives') or ['false'])[0],
                    )
                    status = 200 if data.get('ok') else 404
                    return self.send_json(status, data)
                except (ValueError, TypeError):
                    return self.send_json(400, {'ok':False,'error':'invalid_route'})
                except (urllib.error.URLError, TimeoutError):
                    return self.send_json(502, {'ok':False,'error':'route_unavailable'})
                except (BrokenPipeError, ConnectionResetError):
                    return
                except Exception as exc:
                    try:
                        rt.log(
                            'AURA navigation route failed type=%s detail=%s',
                            type(exc).__name__, str(exc)[:220]
                        )
                    except Exception:
                        pass
                    return self.send_json(502, {'ok':False,'error':'route_unavailable'})
            # AURA P0.7.4 VITALS LOOPBACK READ-ONLY ENDPOINT
            if path=='/api/vitals':
                if not self.auth():return self.send_json(403,{'ok':False,'error':'forbidden'})
                return self.send_json(200,_aura_p074_vitals_snapshot(rt))
            if path=='/api/files/status':
                if not self.auth():return self.send_json(403,{'ok':False})
                if rt.service_bridge is None:return self.send_json(503,{'ok':False,'error':'core_service_bridge_unavailable'})
                return self.send_json(200,rt.service_bridge.files.status())
            if path=='/api/productivity':
                if not self.auth():return self.send_json(403,{'ok':False})
                if rt.service_bridge is None:return self.send_json(503,{'ok':False,'error':'core_service_bridge_unavailable'})
                return self.send_json(200,rt.service_bridge.productivity.snapshot())
            if path=='/api/memory':
                if not self.auth():return self.send_json(403,{'ok':False})
                if rt.service_bridge is None:return self.send_json(503,{'ok':False,'error':'core_service_bridge_unavailable'})
                parsed=urllib.parse.urlparse(self.path)
                query=urllib.parse.parse_qs(parsed.query)
                include_sensitive=str((query.get('sensitive') or ['0'])[0]).casefold() in {'1','true','yes','on'}
                return self.send_json(200,rt.service_bridge.memory.snapshot(include_sensitive=include_sensitive))
            if path=='/api/system':
                if not self.auth():return self.send_json(403,{'ok':False})
                if rt.service_bridge is None:return self.send_json(503,{'ok':False,'error':'core_service_bridge_unavailable'})
                snapshot=rt.service_bridge.system.snapshot()
                try:
                    from core.version import AURA_BUILD,AURA_RELEASE_CHANNEL,AURA_RELEASE_DATE,AURA_VERSION
                    snapshot=dict(snapshot or {})
                    snapshot['runtime_metadata']={
                        'schema':'aura.runtime-metadata.v1',
                        'product':{
                            'version':AURA_VERSION,
                            'build':AURA_BUILD,
                            'release_channel':AURA_RELEASE_CHANNEL,
                            'release_date':AURA_RELEASE_DATE,
                        },
                        'ui':{'release':RELEASE},
                    }
                except Exception:
                    rt.log('Runtime metadata assembly failed',exc_info=True)
                return self.send_json(200,snapshot)
            if path=='/api/router-contract':
                if not self.auth():return self.send_json(403,{'ok':False})
                window=rt.main_window
                snapshot=dict(getattr(window,'_last_router_contract',{}) or {}) if window is not None else {}
                evidence=dict(getattr(window,'_last_router_evidence',{}) or {}) if window is not None else {}
                decisions=list(getattr(window,'_router_contract_history',[]) or [])[-48:] if window is not None else []
                evidence_history=list(getattr(window,'_router_evidence_history',[]) or [])[-64:] if window is not None else []
                readiness={}
                if window is not None:
                    try: readiness=dict(window._router_guardrails_snapshot() or {})
                    except Exception: rt.log('Router guardrails snapshot failed',exc_info=True)
                return self.send_json(200,{
                    'ok':True,
                    'decision':snapshot,
                    'evidence':evidence,
                    'decisions':decisions,
                    'evidence_history':evidence_history,
                    'readiness':readiness,
                })
            if path=='/api/services':
                if not self.auth():return self.send_json(403,{'ok':False})
                if rt.service_bridge is None:return self.send_json(503,{'ok':False,'error':'core_service_bridge_unavailable'})
                try:return self.send_json(200,rt.service_bridge.manifest())
                except Exception:
                    rt.log('Core Service Bridge manifest failed',exc_info=True)
                    return self.send_json(500,{'ok':False,'error':'service_manifest_failed'})
            # AURA P0.8.5.1 HARDWARE PROFILE ROUTE
            if path=='/api/hardware-profile':
                if not self.auth():return self.send_json(403,{'ok':False,'error':'forbidden'})
                try:
                    from hardware_profile_p0851 import build_hardware_profile
                    qs=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query);force=str((qs.get('refresh') or ['0'])[0]).lower() in {'1','true','yes'}
                    return self.send_json(200,build_hardware_profile(rt,force=force))
                except Exception as e:
                    rt.log('P0.8.5.1 hardware profile error: %s',e);return self.send_json(500,{'ok':False,'error':'hardware_profile_failed'})
            # ADF-H R5 R2 DEPLOYED DEVELOPER FABRIC ENDPOINT
            if path=='/api/developer-fabric':
                if not self.auth():return self.send_json(403,{'ok':False})
                try:
                    import pathlib as _adfp, json as _adfj
                    _root_raw=str(os.environ.get('AURA_ROOT') or '').strip()
                    if not _root_raw:
                        return self.send_json(503,{'ok':False,'error':'aura_root_unavailable'})
                    _root=_adfp.Path(_root_raw).expanduser().resolve(strict=False)
                    _state={'schema':'aura.developer-mode-state.v1','enabled':False}
                    _sp=_root/'runtime'/'developer_fabric'/'developer_mode_state.json'
                    if _sp.is_file():
                        try:_state.update(_adfj.loads(_sp.read_text(encoding='utf-8')))
                        except Exception:pass
                    _req={'schema':'aura.developer-workspace-request.v1','serial':0,'requested_at':None}
                    _rp=_root/'runtime'/'developer_fabric'/'developer_workspace_request.json'
                    if _rp.is_file():
                        try:_req.update(_adfj.loads(_rp.read_text(encoding='utf-8')))
                        except Exception:pass
                    _audit=None
                    _ap=_root/'.aura_audit'/'head.json'
                    if _ap.is_file():
                        try:_audit=_adfj.loads(_ap.read_text(encoding='utf-8'))
                        except Exception:_audit={'error':'unreadable'}
                    _tx=[]
                    _tr=_root/'.aura_transactions'
                    if _tr.is_dir():
                        try:
                            _receipts=sorted(_tr.rglob('receipt.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:12]
                            for _p in _receipts:
                                try:
                                    _r=_adfj.loads(_p.read_text(encoding='utf-8'))
                                    _tx.append({'transaction_id':_r.get('transaction_id'),'tests_passed':_r.get('tests_passed'),'rolled_back':_r.get('rolled_back')})
                                except Exception:pass
                        except Exception:pass
                    return self.send_json(200,{'ok':True,'developer_mode':_state,'workspace_request':_req,'audit_head':_audit,'recent_transactions':_tx,'safety':{'staging_required':True,'tests_required':True,'explicit_apply_required':True,'critical_dual_gate':True,'constitutional_release_gate':True,'rollback_guard':True}})
                except Exception as _exc:
                    return self.send_json(500,{'ok':False,'error':'developer_fabric_status_failed','type':type(_exc).__name__})
            # AURA ROADMAP V25-E1 — GET /api/roadmap
            if path=='/api/roadmap':
                if not self.auth():return self.send_json(403,{'ok':False,'error':'forbidden'})
                try:
                    _root=Path(os.environ.get('AURA_ROOT') or Path(__file__).resolve().parents[4]).resolve()
                    if str(_root) not in sys.path:sys.path.insert(0,str(_root))
                    from runtime.aura_roadmap_http_bridge_v25e import RoadmapHttpBridgeV25E
                    return self.send_json(200,RoadmapHttpBridgeV25E(root=_root).snapshot())
                except Exception as exc:
                    rt.log('Roadmap V25-E1 snapshot failed',exc_info=True)
                    return self.send_json(500,{'ok':False,'error':type(exc).__name__,'message':str(exc)[:800]})
            if path=='/api/status':
                if not self.auth():return self.send_json(403,{'ok':False})
                return self.send_json(200,{'ok':True,'release':RELEASE,'port':rt.port,'interaction_ready':rt.ui_ready,'voice_ready':rt.voice_ready,'voice_warming':rt.voice_warming,'voice_result':rt.voice_last_result,'voice_state':('ready' if rt.voice_ready else 'warming' if rt.voice_warming else 'standby'),'core_service_bridge':bool(rt.service_bridge),'core_service_bridge_version':getattr(rt.service_bridge,'VERSION','') if rt.service_bridge is not None else ''})
            rel='index.html' if path in {'/',''} else path.lstrip('/'); target=(rt.dist/rel).resolve()
            try:target.relative_to(rt.dist.resolve())
            except Exception:self.send_error(403);return
            if not target.is_file():self.send_error(404);return
            data=target.read_bytes(); ctype=mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
            self.send_response(200); self.send_header('Content-Type',ctype); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
    return H

def find_browser():
    env=os.environ; roots=[Path(env.get('PROGRAMFILES','')),Path(env.get('PROGRAMFILES(X86)','')),Path(env.get('LOCALAPPDATA',''))]; candidates=[]
    for r in roots:
        if str(r):candidates += [r/'Google/Chrome/Application/chrome.exe',r/'Microsoft/Edge/Application/msedge.exe']
    candidates += [Path(shutil.which('chrome') or ''),Path(shutil.which('msedge') or ''),Path(shutil.which('chromium') or '')]
    for p in candidates:
        try:
            if p.is_file():return p
        except Exception:pass
    return None

def launch_browser(rt:ShellRuntime):
    b=find_browser()
    if not b:raise RuntimeError('Chrome ou Edge introuvable pour la coque AURA RC4.2')
    runtime_dir=rt.root.parent/'runtime'; runtime_dir.mkdir(parents=True,exist_ok=True); rt.profile=runtime_dir/f'chrome-profile-{os.getpid()}'; shutil.rmtree(rt.profile,ignore_errors=True)
    url=f'http://127.0.0.1:{rt.port}/?token={urllib.parse.quote(rt.token)}'
    args=[str(b),f'--app={url}',f'--user-data-dir={rt.profile}','--start-fullscreen','--no-first-run','--no-default-browser-check','--disable-session-crashed-bubble','--disable-features=TranslateUI']
    flags=getattr(subprocess,'CREATE_NO_WINDOW',0) if os.name=='nt' else 0
    rt.browser=subprocess.Popen(args,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags)
    rt.log('AURA RC4.2 visual host browser=%s pid=%s gpu_policy=intel-balanced powerPreference=default bidirectional=True',b.name,rt.browser.pid)
    def watch():
        try:rt.browser.wait()
        except Exception:return
        if rt.client_seen:rt.shutdown.set()
    threading.Thread(target=watch,daemon=True,name='AuraRC41BrowserWatch').start()

def start_server(rt:ShellRuntime):
    rt.httpd=ThreadingHTTPServer(('127.0.0.1',0),make_handler(rt)); rt.port=rt.httpd.server_address[1]
    threading.Thread(target=rt.httpd.serve_forever,daemon=True,name='AuraRC41Http').start()

def session_file(rt):return rt.root.parent/'runtime'/'rc4_2_session.json'
def write_session(rt):
    p=session_file(rt); p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps({'schema':'aura.ui.rc4.2.session.v1','release':RELEASE,'pid':os.getpid(),'port':rt.port,'token':rt.token,'root':str(rt.root),'started_at':time.time()},indent=2)+'\n',encoding='utf-8')
def cleanup(rt):
    # AURA_M180_UI4_R4_R5_MUSIC_STOP_ON_SHELL_CLEANUP
    # This runs only when the real AURA shell exits through main/finally.
    try:
        import urllib.request as _aura_music_shutdown_request
        _aura_music_req=_aura_music_shutdown_request.Request(
            "http://127.0.0.1:18180/lifecycle/close",
            data=b"{}",
            headers={"Content-Type":"application/json"},
            method="POST",
        )
        with _aura_music_shutdown_request.urlopen(_aura_music_req,timeout=1.0) as _aura_music_resp:
            _aura_music_resp.read()
        try:
            logging.getLogger("aura.rc4_2.shell").info(
                "AURA Music premium playback stopped from shell cleanup"
            )
        except Exception:
            pass
    except Exception as _aura_music_shutdown_exc:
        try:
            logging.getLogger("aura.rc4_2.shell").warning(
                "AURA Music premium cleanup stop failed type=%s detail=%s",
                type(_aura_music_shutdown_exc).__name__,
                str(_aura_music_shutdown_exc)[:180],
            )
        except Exception:
            pass
    try:
        if rt.httpd:rt.httpd.shutdown(); rt.httpd.server_close()
    except Exception:pass
    try:
        if rt.browser and rt.browser.poll() is None:rt.browser.terminate(); rt.browser.wait(timeout=3)
    except Exception:
        try:rt.browser.kill()
        except Exception:pass
    try:session_file(rt).unlink(missing_ok=True)
    except Exception:pass
    if rt.profile:shutil.rmtree(rt.profile,ignore_errors=True)
    try:shutil.rmtree(rt.upload_dir,ignore_errors=True)
    except Exception:pass
def setup_logging(root):
    logdir=root/'logs'; logdir.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(level=logging.INFO,format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',handlers=[logging.FileHandler(logdir/'aura_rc42_shell.log',encoding='utf-8')])


# AURA_V123_REAL_HOST_WEB_BRIDGE_BEGIN
_aura_v123_connect_events_base = connect_events

# AURA_V123_AWAITABLE_HUB_COMPLETION_BEGIN
def _aura_v123_complete_hub_send(rt, result):
    import asyncio
    import inspect

    if not inspect.isawaitable(result):
        return True

    loop_candidates = []
    for owner in (rt, getattr(rt, "hub", None)):
        if owner is None:
            continue
        for attr_name in ("loop", "_loop", "event_loop", "_event_loop"):
            candidate = getattr(owner, attr_name, None)
            if candidate is not None and candidate not in loop_candidates:
                loop_candidates.append(candidate)

    for loop in loop_candidates:
        try:
            if loop.is_running():
                future = asyncio.run_coroutine_threadsafe(result, loop)
                future.result(timeout=3.0)
                return True
        except Exception:
            continue

    try:
        asyncio.run(result)
        return True
    except Exception:
        logging.getLogger(__name__).exception("AURA v1.2.3 awaitable hub.send completion failed")
        return False
# AURA_V123_AWAITABLE_HUB_COMPLETION_END

def connect_events(rt):
    _aura_v123_connect_events_base(rt)
    try:
        from runtime.personal_result_web_sink_v123 import register_personal_result_sink_v123
        from runtime.personal_result_ipc_v123 import start_personal_result_ipc_server_v123

        def _aura_v123_forward_personal_result(payload):
            data = payload if isinstance(payload, dict) else {"kind":"generic","count":0,"items":[]}
            result = rt.hub.send('personal_result', data)
            _aura_v123_complete_hub_send(rt, result)

        rt._aura_v123_forward_personal_result = _aura_v123_forward_personal_result
        register_personal_result_sink_v123(_aura_v123_forward_personal_result)
        rt._aura_v123_personal_result_ipc = start_personal_result_ipc_server_v123(_aura_v123_forward_personal_result)
    except Exception:
        logging.getLogger(__name__).exception("AURA v1.2.3 personal_result web/IPC bridge bind failed")
# AURA_V123_REAL_HOST_WEB_BRIDGE_END
# AURA_V123_ESCAPE_WATCHDOG_BEGIN
def _aura_v123_escape_watchdog():
    if os.name != "nt":
        return
    try:
        import ctypes
        import time as _aura_time
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        VK_ESCAPE = 0x1B
        VK_F11 = 0x7A
        KEYEVENTF_KEYUP = 0x0002
        MONITOR_DEFAULTTONEAREST = 0x00000002

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long),
            ]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", RECT),
                ("rcWork", RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        previous_down = False
        while True:
            down = bool(user32.GetAsyncKeyState(VK_ESCAPE) & 0x8000)
            if down and not previous_down:
                hwnd = user32.GetForegroundWindow()
                if hwnd:
                    title_buf = ctypes.create_unicode_buffer(512)
                    class_buf = ctypes.create_unicode_buffer(256)
                    user32.GetWindowTextW(hwnd, title_buf, len(title_buf))
                    user32.GetClassNameW(hwnd, class_buf, len(class_buf))
                    title = title_buf.value.lower()
                    klass = class_buf.value.lower()

                    rect = RECT()
                    monitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
                    mi = MONITORINFO()
                    mi.cbSize = ctypes.sizeof(MONITORINFO)

                    covers_monitor = False
                    if user32.GetWindowRect(hwnd, ctypes.byref(rect)) and monitor and user32.GetMonitorInfoW(monitor, ctypes.byref(mi)):
                        tolerance = 4
                        covers_monitor = (
                            rect.left <= mi.rcMonitor.left + tolerance
                            and rect.top <= mi.rcMonitor.top + tolerance
                            and rect.right >= mi.rcMonitor.right - tolerance
                            and rect.bottom >= mi.rcMonitor.bottom - tolerance
                        )

                    is_aura_chrome = (
                        "aura" in title
                        and ("chrome_widgetwin" in klass or "chrome" in klass)
                    )
                    if is_aura_chrome and covers_monitor:
                        user32.keybd_event(VK_F11, 0, 0, 0)
                        user32.keybd_event(VK_F11, 0, KEYEVENTF_KEYUP, 0)
                        _aura_time.sleep(0.35)
            previous_down = down
            _aura_time.sleep(0.04)
    except Exception:
        logging.getLogger(__name__).exception("AURA v1.2.3 ESC watchdog failed")


def _aura_v123_start_escape_watchdog():
    try:
        import threading as _aura_threading
        t = _aura_threading.Thread(
            target=_aura_v123_escape_watchdog,
            name="AURA-v123-EscapeWatchdog",
            daemon=True,
        )
        t.start()
        return t
    except Exception:
        logging.getLogger(__name__).exception("AURA v1.2.3 ESC watchdog start failed")
        return None
# AURA_V123_ESCAPE_WATCHDOG_END

def main():
    _aura_v123_start_escape_watchdog()
    ap=argparse.ArgumentParser(); ap.add_argument('--core'); ap.add_argument('--ui-root'); args=ap.parse_args(); core,root,_aura_paths=_aura_p08522_resolve_runtime_paths(args); setup_logging(root); rt=ShellRuntime(root,core)

    # AURA P0.2.8 ACTIVE THREEJS PCM SINK
    # Installed into the ui_root actually resolved by launch_aura_ui_v0722_rc42.py.
    import builtins as _aura_p028_builtins
    def _aura_p028_threejs_pcm_sink(level):
        try:
            value=max(0.0,min(1.0,float(level)))
        except Exception:
            value=0.0
        now=time.monotonic()
        if now-rt.last_pcm>=1/30:
            rt.last_pcm=now
            try:
                rt.hub.send('voice_amplitude',{'level':value})
            except Exception:
                pass
    _aura_p028_builtins._aura_rc42_pcm_sink=_aura_p028_threejs_pcm_sink
    logging.getLogger('aura.rc4_2.shell').info(
        'AURA P0.2.8 ACTIVE Three.js PCM sink ready ui_root=%s max_hz=30',
        root,
    )
    # AURA P0.2.9 ACTIVE APPDATA THREEJS PCM SINK
    # This is the actual installed RC4.2 shell under %LOCALAPPDATA%\\AURA\\ui\\...
    # P0.2.7 in ui/main_window.py publishes real XTTSTTS amplitude here via builtins.
    import builtins as _aura_p029_builtins
    _aura_p029_state={'first':False,'count':0,'peak':0.0}

    def _aura_p029_threejs_pcm_sink(level):
        try:
            value=max(0.0,min(1.0,float(level)))
        except Exception:
            value=0.0

        _aura_p029_state['count']+=1
        if value>_aura_p029_state['peak']:
            _aura_p029_state['peak']=value

        if not _aura_p029_state['first']:
            _aura_p029_state['first']=True
            logging.getLogger('aura.rc4_2.shell').info(
                'AURA P0.2.9 PCM first event received level=%.4f transport=builtins->hub',
                value,
            )

        now=time.monotonic()
        if now-rt.last_pcm>=1/30:
            rt.last_pcm=now
            try:
                rt.hub.send('voice_amplitude',{'level':value})
            except Exception:
                pass

    _aura_p029_builtins._aura_rc42_pcm_sink=_aura_p029_threejs_pcm_sink
    logging.getLogger('aura.rc4_2.shell').info(
        'AURA P0.2.9 ACTIVE Three.js PCM sink ready ui_root=%s max_hz=30',
        root,
    )
    if not (core/'main.py').is_file() or not (root/'dist'/'index.html').is_file():return 2
    os.environ['OPENGL_ORB_ENABLED']='false'; os.environ['AURA_UI_HOST']='threejs-rc4.2'; os.chdir(core); sys.path.insert(0,str(core))
    try:
        start_server(rt); write_session(rt); display=inject_display_hint(rt); compute=compute_gpu_name(); rt.p0851_display_gpu=display; rt.p0851_compute_gpu=compute; rt.hub.send('hardware_compute_probe',{'ok':True,'adapter':compute,'source':'cuda-runtime'})
        rt.hub.send('bridge.ready',{'core_files_modified':False,'transport':'sse+post-loopback-token','display_gpu':display,'compute_gpu':compute,'gpu_policy':'intel-balanced','ui_release':RELEASE,'conversation_text_local_only':True,'bidirectional':True,'path_resolver':'aura.paths.v1','deployment_mode':_aura_paths.deployment_mode})
        launch_browser(rt); connect_events(rt); patch_voice(rt); patch_hidden_shell(rt)
        rt.hub.send('bridge.aura_start',{'version':CORE_VERSION,'expected_build':CORE_BUILD,'opengl_disabled_in_memory':True,'single_visible_window':True})
        sys.argv=[str(core/'main.py')]
        try:runpy.run_path(str(core/'main.py'),run_name='__main__')
        except SystemExit as e:
            code=e.code if isinstance(e.code,int) else 0; rt.hub.send('bridge.aura_exit',{'code':code}); return code
        return 0
    except Exception as e:
        rt.hub.send('bridge.error',{'error_type':type(e).__name__,'message':str(e)[:220]}); logging.getLogger('aura.rc4_2.shell').exception('RC4.2 shell fatal error'); return 3
    finally:cleanup(rt)
if __name__=='__main__':raise SystemExit(main())