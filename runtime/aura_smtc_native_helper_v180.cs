
using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using Windows.Media;
using Windows.Storage.Streams;

[assembly: System.Reflection.AssemblyTitle("AURA Music")]
[assembly: System.Reflection.AssemblyProduct("AURA")]
[assembly: System.Reflection.AssemblyDescription("AURA Music Media Session")]
[assembly: System.Reflection.AssemblyCompany("AURA")]
[assembly: System.Reflection.AssemblyVersion("1.8.0.0")]
[assembly: System.Reflection.AssemblyFileVersion("1.8.0.0")]

internal sealed class AuraSmtcHost : Form
{
    const string BaseUrl="http://127.0.0.1:18180";
    const string StatusPath=@"C:\AURA GPT version\data\media\aura_smtc_status_v180.json";
    const int CoverPort=18181;

    [DllImport("shell32.dll", CharSet=CharSet.Unicode)]
    static extern int SetCurrentProcessExplicitAppUserModelID(string appID);

    [DllImport("combase.dll", CharSet=CharSet.Unicode)]
    static extern int WindowsCreateString(string s,int len,out IntPtr hs);
    [DllImport("combase.dll")] static extern int WindowsDeleteString(IntPtr hs);
    [DllImport("combase.dll")] static extern int RoInitialize(uint t);
    [DllImport("combase.dll")] static extern void RoUninitialize();
    [DllImport("combase.dll")]
    static extern int RoGetActivationFactory(IntPtr cls,ref Guid iid,out IntPtr factory);

    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    delegate int GetForWindowDelegate(IntPtr self,IntPtr hwnd,ref Guid riid,out IntPtr smtc);

    readonly JavaScriptSerializer json=new JavaScriptSerializer();
    readonly System.Windows.Forms.Timer timer=new System.Windows.Forms.Timer();
    SystemMediaTransportControls smtc;
    string currentId="";
    string metadataSig="";
    string lastError="";
    string lastButton="";
    bool metadataOk=false;
    bool coverOk=false;
    bool buttonsRegistered=false;
    bool timelineOk=false;
    double lastTimelinePosition=-1;
    double lastTimelineDuration=-1;
    double lastSeekRequest=-1;
    int healthFails=0;
    DateTime started=DateTime.UtcNow;
    byte[] coverBytes=new byte[0];
    string coverType="image/jpeg";
    volatile bool closing=false;

    public AuraSmtcHost()
    {
        ShowInTaskbar=false; FormBorderStyle=FormBorderStyle.None; Opacity=0;
        Width=1; Height=1; StartPosition=FormStartPosition.Manual; Left=-32000; Top=-32000;
        Load+=Loaded; FormClosed+=ClosedHost;
    }

    static bool Failed(int hr){return hr<0;}

    void Loaded(object sender,EventArgs e)
    {
        try
        {
            CreateControl();
            Acquire();
            smtc.IsEnabled=true;
            smtc.IsPlayEnabled=true;
            smtc.IsPauseEnabled=true;
            smtc.IsStopEnabled=true;
            smtc.IsNextEnabled=true;
            smtc.IsPreviousEnabled=true;
            smtc.ButtonPressed+=ButtonPressed;
            smtc.PlaybackPositionChangeRequested+=PlaybackPositionChangeRequested;
            buttonsRegistered=true;
            StartCoverServer();
            timer.Interval=550;
            timer.Tick+=delegate{Poll();};
            timer.Start();
            WriteStatus(true);
        }
        catch(Exception ex)
        {
            lastError=ex.GetType().Name+": "+ex.Message;
            WriteStatus(false);
            BeginInvoke((MethodInvoker)delegate{Close();});
        }
    }

    void Acquire()
    {
        int init=RoInitialize(0);
        if(Failed(init)&&unchecked((uint)init)!=0x80010106u)Marshal.ThrowExceptionForHR(init);
        IntPtr hs=IntPtr.Zero,factory=IntPtr.Zero,p=IntPtr.Zero;
        try
        {
            string cls="Windows.Media.SystemMediaTransportControls";
            int hr=WindowsCreateString(cls,cls.Length,out hs);
            if(Failed(hr))Marshal.ThrowExceptionForHR(hr);
            Guid interop=new Guid("ddb0472d-c911-4a1f-86d9-dc3d71a95f5a");
            hr=RoGetActivationFactory(hs,ref interop,out factory);
            if(Failed(hr)||factory==IntPtr.Zero)Marshal.ThrowExceptionForHR(hr);
            IntPtr vt=Marshal.ReadIntPtr(factory);
            IntPtr fp=Marshal.ReadIntPtr(vt,IntPtr.Size*6);
            var get=(GetForWindowDelegate)Marshal.GetDelegateForFunctionPointer(fp,typeof(GetForWindowDelegate));
            Guid iid=new Guid("99fa3ff4-1742-42a6-902e-087d41f965ec");
            hr=get(factory,Handle,ref iid,out p);
            if(Failed(hr)||p==IntPtr.Zero)Marshal.ThrowExceptionForHR(hr);
            smtc=(SystemMediaTransportControls)Marshal.GetObjectForIUnknown(p);
        }
        finally
        {
            if(p!=IntPtr.Zero)try{Marshal.Release(p);}catch{}
            if(factory!=IntPtr.Zero)try{Marshal.Release(factory);}catch{}
            if(hs!=IntPtr.Zero)try{WindowsDeleteString(hs);}catch{}
        }
    }

    void ButtonPressed(SystemMediaTransportControls sender,SystemMediaTransportControlsButtonPressedEventArgs e)
    {
        string action=null;
        switch(e.Button)
        {
            case SystemMediaTransportControlsButton.Play: action="play_pause"; break;
            case SystemMediaTransportControlsButton.Pause: action="play_pause"; break;
            case SystemMediaTransportControlsButton.Stop: action="stop"; break;
            case SystemMediaTransportControlsButton.Next: action="next"; break;
            case SystemMediaTransportControlsButton.Previous: action="previous"; break;
        }
        if(action==null)return;
        lastButton=action;
        ThreadPool.QueueUserWorkItem(delegate{
            try{Post(action);}catch(Exception ex){lastError="button: "+ex.Message;}
            WriteStatus(true);
        });
    }

    string Get(string path)
    {
        using(var wc=new WebClient()){wc.Encoding=Encoding.UTF8;return wc.DownloadString(BaseUrl+path);}
    }

    void Post(string action)
    {
        using(var wc=new WebClient())
        {
            wc.Headers[HttpRequestHeader.ContentType]="application/json"; wc.Encoding=Encoding.UTF8;
            wc.UploadString(BaseUrl+"/media/command","POST","{\"action\":\""+action+"\"}");
        }
    }

    void PostSeek(double seconds)
    {
        if(Double.IsNaN(seconds)||Double.IsInfinity(seconds))return;
        seconds=Math.Max(0,seconds);
        using(var wc=new WebClient())
        {
            wc.Headers[HttpRequestHeader.ContentType]="application/json";
            wc.Encoding=Encoding.UTF8;
            string val=seconds.ToString("0.###",System.Globalization.CultureInfo.InvariantCulture);
            wc.UploadString(BaseUrl+"/media/seek","POST","{\"position\":"+val+"}");
        }
    }

    void PlaybackPositionChangeRequested(
        SystemMediaTransportControls sender,
        PlaybackPositionChangeRequestedEventArgs e)
    {
        double seconds=e.RequestedPlaybackPosition.TotalSeconds;
        lastSeekRequest=seconds;
        ThreadPool.QueueUserWorkItem(delegate{
            try{PostSeek(seconds);}
            catch(Exception ex){lastError="seek: "+ex.Message;}
            WriteStatus(true);
        });
    }

    static Dictionary<string,object> AsDict(object o){return o as Dictionary<string,object>;}
    static List<object> AsList(object o)
    {
        var l=o as List<object>;
        if(l!=null)return l;
        var a=o as object[];
        if(a!=null)return new List<object>(a);
        return null;
    }
    static string Str(Dictionary<string,object>d,string k)
    {
        object v; return d!=null&&d.TryGetValue(k,out v)&&v!=null?Convert.ToString(v):"";
    }
    // AURA_M180_UI6_R4_R3_LOCALE_SAFE_TIMELINE_NUMERIC_FIX
    static double Num(Dictionary<string,object>d,string k)
    {
        object v;
        if(d==null||!d.TryGetValue(k,out v)||v==null)return 0;

        // JavaScriptSerializer returns JSON numbers as numeric CLR objects.
        // Never round-trip them through Convert.ToString() under the Windows UI locale:
        // on fr-FR, 217.0 can become "217,0", then InvariantCulture interprets
        // the comma as a thousands separator and produces 2170.
        try
        {
            if(v is double)return (double)v;
            if(v is float)return (double)(float)v;
            if(v is decimal)return (double)(decimal)v;
            if(v is int)return (double)(int)v;
            if(v is long)return (double)(long)v;
            if(v is short)return (double)(short)v;
            if(v is uint)return (double)(uint)v;
            if(v is ulong)return (double)(ulong)v;
            if(v is byte)return (double)(byte)v;
            if(v is sbyte)return (double)(sbyte)v;
            return Convert.ToDouble(v,System.Globalization.CultureInfo.InvariantCulture);
        }
        catch
        {
            string s=v as string;
            double x;
            if(s!=null && double.TryParse(
                s,
                System.Globalization.NumberStyles.Float|System.Globalization.NumberStyles.AllowThousands,
                System.Globalization.CultureInfo.InvariantCulture,
                out x))return x;
            if(s!=null && double.TryParse(
                s,
                System.Globalization.NumberStyles.Float|System.Globalization.NumberStyles.AllowThousands,
                System.Globalization.CultureInfo.CurrentCulture,
                out x))return x;
            return 0;
        }
    }
    static bool Bool(Dictionary<string,object>d,string k)
    {
        object v; if(d==null||!d.TryGetValue(k,out v)||v==null)return false;
        if(v is bool)return (bool)v; bool b; return bool.TryParse(Convert.ToString(v),out b)&&b;
    }

    Dictionary<string,object> Status(){return AsDict(json.DeserializeObject(Get("/status")));}

    Dictionary<string,object> Item(string id)
    {
        var root=AsDict(json.DeserializeObject(Get("/playlist")));
        if(root==null)return null;

        Dictionary<string,object> pl=null;
        object po;
        if(root.TryGetValue("playlist",out po))pl=AsDict(po);
        if(pl==null && root.ContainsKey("items"))pl=root;
        if(pl==null)return null;

        object io;
        if(!pl.TryGetValue("items",out io))return null;
        var items=AsList(io);
        if(items==null)return null;

        foreach(var x in items)
        {
            var d=AsDict(x);
            if(d!=null&&Str(d,"id")==id)return d;
        }
        return null;
    }

    void Poll()
    {
        try
        {
            var st=Status(); healthFails=0;
            string id=Str(st,"current_id");
            bool playing=Bool(st,"playing"),paused=Bool(st,"paused");
            double dur=Num(st,"duration_seconds");

            if(string.IsNullOrEmpty(id)||dur<=0)
            {
                smtc.PlaybackStatus=MediaPlaybackStatus.Stopped; WriteStatus(true); return;
            }

            smtc.PlaybackStatus=playing&&!paused?MediaPlaybackStatus.Playing:
                paused?MediaPlaybackStatus.Paused:MediaPlaybackStatus.Stopped;

            double pos=Num(st,"position_seconds");
            pos=Math.Max(0,Math.Min(dur,pos));
            try
            {
                var timeline=new SystemMediaTransportControlsTimelineProperties();
                timeline.StartTime=TimeSpan.Zero;
                timeline.MinSeekTime=TimeSpan.Zero;
                timeline.Position=TimeSpan.FromSeconds(pos);
                timeline.MaxSeekTime=TimeSpan.FromSeconds(dur);
                timeline.EndTime=TimeSpan.FromSeconds(dur);
                smtc.UpdateTimelineProperties(timeline);
                timelineOk=true;
                lastTimelinePosition=pos;
                lastTimelineDuration=dur;
            }
            catch(Exception ex)
            {
                timelineOk=false;
                lastError="timeline: "+ex.GetType().Name+": "+ex.Message;
            }

            if(id!=currentId)
            {
                currentId=id;var item=Item(id);if(item!=null)Metadata(item);
            }
            WriteStatus(true);
        }
        catch(Exception ex)
        {
            healthFails++;lastError="poll: "+ex.GetType().Name+": "+ex.Message;WriteStatus(true);
            if(healthFails>=20&&(DateTime.UtcNow-started).TotalSeconds>15)Close();
        }
    }

    void Metadata(Dictionary<string,object> item)
    {
        string title=Str(item,"title"),artist=Str(item,"artist"),album=Str(item,"album");
        string cover=Str(item,"cover_data_uri");
        string sig=title+"\n"+artist+"\n"+album+"\n"+cover.Length;
        if(sig==metadataSig)return;

        var up=smtc.DisplayUpdater;up.Type=MediaPlaybackType.Music;
        up.MusicProperties.Title=string.IsNullOrEmpty(title)?"AURA Music":title;
        up.MusicProperties.Artist=artist??"";
        up.MusicProperties.AlbumArtist=artist??"";
        try{up.MusicProperties.AlbumTitle=album??"";}catch{}

        coverOk=false;
        if(!string.IsNullOrEmpty(cover))
        {
            int comma=cover.IndexOf(',');
            if(comma>0)
            {
                try
                {
                    string head=cover.Substring(0,comma);
                    coverBytes=Convert.FromBase64String(cover.Substring(comma+1));
                    coverType=head.IndexOf("image/png",StringComparison.OrdinalIgnoreCase)>=0?"image/png":
                        head.IndexOf("image/webp",StringComparison.OrdinalIgnoreCase)>=0?"image/webp":"image/jpeg";
                    string uri="http://127.0.0.1:"+CoverPort+"/cover?v="+DateTime.UtcNow.Ticks;
                    up.Thumbnail=RandomAccessStreamReference.CreateFromUri(new System.Uri(uri));
                    coverOk=true;
                }
                catch(Exception ex){lastError="cover: "+ex.Message;}
            }
        }
        up.Update();metadataSig=sig;metadataOk=true;
    }

    void StartCoverServer()
    {
        var t=new Thread(CoverServer);t.IsBackground=true;t.Name="aura-smtc-cover";t.Start();
    }

    void CoverServer()
    {
        System.Net.Sockets.TcpListener listener=null;
        try
        {
            listener=new System.Net.Sockets.TcpListener(IPAddress.Loopback,CoverPort);listener.Start();
            while(!closing)
            {
                var client=listener.AcceptTcpClient();
                ThreadPool.QueueUserWorkItem(delegate{
                    using(client)
                    {
                        try
                        {
                            var stream=client.GetStream();byte[] req=new byte[2048];stream.Read(req,0,req.Length);
                            byte[] body=coverBytes??new byte[0];
                            string h="HTTP/1.1 200 OK\r\nContent-Type: "+coverType+"\r\nContent-Length: "+body.Length+
                                "\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n";
                            byte[] hb=Encoding.ASCII.GetBytes(h);stream.Write(hb,0,hb.Length);
                            if(body.Length>0)stream.Write(body,0,body.Length);
                        }catch{}
                    }
                });
            }
        }
        catch(Exception ex){lastError="cover_server: "+ex.Message;}
        finally{if(listener!=null)try{listener.Stop();}catch{}}
    }

    void WriteStatus(bool ready)
    {
        try
        {
            var d=new Dictionary<string,object>();
            d["schema"]="aura.smtc.native.v180";d["ready"]=ready;
            d["pid"]=System.Diagnostics.Process.GetCurrentProcess().Id;
            d["current_id"]=currentId;d["metadata_ok"]=metadataOk;d["cover_ok"]=coverOk;
            d["buttons_registered"]=buttonsRegistered;d["last_button"]=lastButton;
            d["timeline_ok"]=timelineOk;
            d["timeline_position_seconds"]=lastTimelinePosition;
            d["timeline_duration_seconds"]=lastTimelineDuration;
            d["last_seek_request_seconds"]=lastSeekRequest;
            d["last_error"]=lastError;d["updated_at"]=DateTime.Now.ToString("o");
            Directory.CreateDirectory(Path.GetDirectoryName(StatusPath));
            File.WriteAllText(StatusPath,json.Serialize(d),Encoding.UTF8);
        }catch{}
    }

    void ClosedHost(object sender,FormClosedEventArgs e)
    {
        closing=true;timer.Stop();
        if(smtc!=null)
        {
            try{smtc.ButtonPressed-=ButtonPressed;}catch{}
            try{smtc.PlaybackPositionChangeRequested-=PlaybackPositionChangeRequested;}catch{}
            try{smtc.PlaybackStatus=MediaPlaybackStatus.Closed;}catch{}
            try{smtc.IsEnabled=false;}catch{}
        }
        WriteStatus(false);try{RoUninitialize();}catch{}
    }

    [STAThread] static void Main()
    {
        try{SetCurrentProcessExplicitAppUserModelID("AURA.Music.Player");}catch{}
        Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new AuraSmtcHost());
    }
}
