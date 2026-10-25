using System.IO;
using System.IO.Pipes;
using System.Security.Principal;
using System.Windows;
using Velopack;

namespace ManiacSoftwares.PESE;

internal static class Program
{
    [STAThread]
    public static int Main(string[] args)
    {
        if (args.Length > 0 && args[0] == "--capture-screens")
            return Acceptance.CaptureScreenshots(args.Skip(1).ToArray());
        // Installer/update hooks must run before WPF or the single-instance gate.
        VelopackApp.Build().Run();
        if (args.Length > 0 && args[0] is "--accept-updater" or "--accept-update-restarted")
            return UpdateAcceptance.RunAsync(args[0], args.Skip(1).ToArray()).GetAwaiter().GetResult();
        if (args.Length > 0 && args[0] == "--self-test")
            return Acceptance.RunAsync(args.Skip(1).ToArray()).GetAwaiter().GetResult();

        var sid = WindowsIdentity.GetCurrent().User!.Value;
        var instanceName = "ManiacSoftwares.PESE." + sid;
        using var mutex = new Mutex(true, @"Local\" + instanceName, out var first);
        if (!first)
        {
            try
            {
                using var pipe = new NamedPipeClientStream(".", instanceName, PipeDirection.Out);
                pipe.Connect(1500);
                pipe.WriteByte(1);
            }
            catch { /* The first window may still be starting. Never start another writer. */ }
            return 0;
        }
        using var lifetime = new CancellationTokenSource();
        var app = new Application { ShutdownMode = ShutdownMode.OnMainWindowClose };
        var window = new MainWindow();
        _ = Task.Run(async () =>
        {
            while (!lifetime.IsCancellationRequested)
            {
                try
                {
                    using var pipe = new NamedPipeServerStream(instanceName, PipeDirection.In, 1,
                        PipeTransmissionMode.Byte, PipeOptions.Asynchronous | PipeOptions.CurrentUserOnly);
                    await pipe.WaitForConnectionAsync(lifetime.Token);
                    app.Dispatcher.Invoke(() =>
                    {
                        if (window.WindowState == WindowState.Minimized) window.WindowState = WindowState.Normal;
                        window.Show(); window.Activate();
                        window.Topmost = true; window.Topmost = false;
                    });
                }
                catch (OperationCanceledException) { break; }
                catch { await Task.Delay(200); }
            }
        });
        app.DispatcherUnhandledException += (_, e) =>
        {
            Log.Write("ui_failure", e.Exception.GetType().Name);
            MessageBox.Show("PESE encountered a problem. Restart the app. Your Brain remains in its selected folder.", "PESE");
            e.Handled = true;
        };
        try { app.Run(window); return 0; }
        finally { lifetime.Cancel(); mutex.ReleaseMutex(); }
    }
}

internal static class Paths
{
    internal static string? AcceptanceProfile;
    public static string Install => AppContext.BaseDirectory;
    public static string Profile => AcceptanceProfile ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "ManiacSoftwares", "PESE");
    public static string Settings => Path.Combine(Profile, "desktop-settings.json");
    public static string Recommended => Path.Combine(Profile, "Brain");
    public static string? LoadBrain()
    {
        if (!File.Exists(Settings)) return null;
        using var doc = System.Text.Json.JsonDocument.Parse(File.ReadAllText(Settings));
        return doc.RootElement.GetProperty("brainPath").GetString()
            ?? throw new InvalidDataException("The saved Brain location is invalid.");
    }
}

internal static class Log
{
    // Operational event codes only; never log process streams or request URLs.
    public static void Write(string code, string detail = "")
    {
        try
        {
            var dir = Path.Combine(Paths.Profile, "Logs"); Directory.CreateDirectory(dir);
            var file = Path.Combine(dir, "desktop.log");
            if (File.Exists(file) && new FileInfo(file).Length > 2 * 1024 * 1024)
                File.Move(file, file + ".previous", true);
            File.AppendAllText(file, $"{DateTimeOffset.UtcNow:O} {code} {detail}\n");
        }
        catch { }
    }

    public static void WriteDiagnostic(string section, string message)
    {
        try
        {
            var dir = Path.Combine(Paths.Profile, "Logs"); Directory.CreateDirectory(dir);
            var file = Path.Combine(dir, "desktop.log");
            if (File.Exists(file) && new FileInfo(file).Length > 2 * 1024 * 1024)
                File.Move(file, file + ".previous", true);
            File.AppendAllText(file, $"{DateTimeOffset.UtcNow:O} [DIAGNOSTIC:{section}] {message}\n");
        }
        catch { }
    }
}
