using System.Diagnostics;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Net.Sockets;
using System.Text.Json;
using System.Windows;

namespace ManiacSoftwares.PESE;

// Explicit local CLI acceptance harness. It uses the exact production supervisor.
internal static class Acceptance
{
    public static async Task<int> RunAsync(string[] args)
    {
        if (args.Length < 2) return 2;
        var reportPath = Path.GetFullPath(args[1]);
        var results = new List<object>();
        try
        {
            var path = Path.GetFullPath(args[0]);
            if (!File.Exists(Path.Combine(path, ".pese-disposable-fixture")))
                throw new InvalidOperationException("A marked disposable Brain is required.");
            Paths.AcceptanceProfile = Path.Combine(Path.GetDirectoryName(reportPath)!, "LocalAppData", "ManiacSoftwares", "PESE");
            var cycles = args.Length > 2 ? int.Parse(args[2]) : 10;
            Check(MainWindow.Internal("http://127.0.0.1:1234/search/?q=x", "http://127.0.0.1:1234"), "internal URL");
            Check(!MainWindow.Internal("https://example.com/", "http://127.0.0.1:1234"), "external blocked");
            Check(!MainWindow.Internal("file:///C:/private.txt", "http://127.0.0.1:1234"), "local files blocked");
            await BrainProcess.CommandAsync("inspect", path);
            for (var i = 0; i < cycles; i++)
            {
                var brain = new BrainProcess();
                var watch = Stopwatch.StartNew();
                var progress = new List<BrainStartupProgress>();
                await brain.StartAsync(path, CancellationToken.None, new Progress<BrainStartupProgress>(state => { lock (progress) progress.Add(state); }));
                var startupSeconds = watch.Elapsed.TotalSeconds;
                var pid = brain.ProcessId;
                long peakWorkingSetBytes;
                using (var running = Process.GetProcessById(pid)) peakWorkingSetBytes = running.PeakWorkingSet64;
                var port = new Uri(brain.Origin!).Port;
                using var publicClient = new HttpClient();
                Check((await publicClient.GetAsync(brain.Origin + "/api/stats")).StatusCode == HttpStatusCode.Unauthorized, "private API auth");
                using var forged = new HttpRequestMessage(HttpMethod.Get, brain.Origin + "/health");
                forged.Headers.Add("Origin", "https://example.com"); forged.Headers.Add("X-PESE-Token", brain.Token);
                Check((await publicClient.SendAsync(forged)).StatusCode == HttpStatusCode.Forbidden, "remote origin blocked");
                Check((await publicClient.GetAsync(brain.Origin + "/")).IsSuccessStatusCode, "static root");
                var health = await brain.Client.GetStringAsync(brain.Origin + "/health");
                var offline = await brain.Client.GetStringAsync(brain.Origin + "/desktop/offline-check");
                Check(JsonDocument.Parse(offline).RootElement.GetProperty("external_connections_blocked").GetBoolean(), "external network blocked");
                if (i == 0)
                {
                    var response = await brain.Client.GetStringAsync(brain.Origin + "/api/search?q=when%20did%20I%20buy%20my%20bicycle&debug=true");
                    // Saved only on the explicitly provided disposable acceptance Brain.
                    results.Add(new { search = JsonSerializer.Deserialize<JsonElement>(response) });
                }
                await brain.DisposeAsync();
                bool alive;
                try { using var child = Process.GetProcessById(pid); alive = !child.HasExited; } catch (ArgumentException) { alive = false; }
                Check(!alive, "child exited");
                using var socket = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
                socket.ExclusiveAddressUse = true; socket.Bind(new IPEndPoint(IPAddress.Loopback, port));
                BrainStartupProgress[] events;
                lock (progress) events = progress.ToArray();
                results.Add(new { cycle = i + 1, pid, port, childExited = true, portReleased = true,
                    startupSeconds, peakWorkingSetBytes, readinessEvents = events,
                    health = JsonSerializer.Deserialize<JsonElement>(health) });
            }
            File.WriteAllText(reportPath, JsonSerializer.Serialize(new { passed = true, results }, new JsonSerializerOptions { WriteIndented = true }));
            return 0;
        }
        catch (Exception exc)
        {
            File.WriteAllText(reportPath, JsonSerializer.Serialize(new { passed = false, error = exc.ToString(), results }, new JsonSerializerOptions { WriteIndented = true }));
            return 1;
        }
    }
    private static void Check(bool value, string label)
    { if (!value) throw new InvalidOperationException("Acceptance failed: " + label); }

    public static int CaptureScreenshots(string[] args)
    {
        var outDir = args.Length > 0 ? Path.GetFullPath(args[0]) : Directory.GetCurrentDirectory();
        Directory.CreateDirectory(outDir);
        var logFile = Path.Combine(outDir, "capture.log");
        File.WriteAllText(logFile, $"Starting screenshot capture at {DateTime.Now} into {outDir}\n");

        try
        {
            void RenderToFile(FrameworkElement element, string fileName)
            {
                element.Width = 1240; element.Height = 800;
                element.Measure(new Size(1240, 800));
                element.Arrange(new Rect(0, 0, 1240, 800));
                element.UpdateLayout();
                var rtb = new System.Windows.Media.Imaging.RenderTargetBitmap(1240, 800, 96, 96, System.Windows.Media.PixelFormats.Pbgra32);
                rtb.Render(element);
                var encoder = new System.Windows.Media.Imaging.PngBitmapEncoder();
                encoder.Frames.Add(System.Windows.Media.Imaging.BitmapFrame.Create(rtb));
                var dest = Path.Combine(outDir, fileName);
                using var stream = File.Create(dest);
                encoder.Save(stream);
                File.AppendAllText(logFile, $"Rendered: {dest}\n");
            }

            var app = Application.Current ?? new Application();
            var welcomeWin = new MainWindow();
            welcomeWin.ShowWelcomeForCapture();
            RenderToFile((FrameworkElement)welcomeWin.Content, "10_welcome_screen.png");

            var recoveryWin = new MainWindow();
            recoveryWin.ShowRecoveryForCapture(@"E:\External USB Drive\My PESE Brain");
            RenderToFile((FrameworkElement)recoveryWin.Content, "09_missing_brain_recovery.png");

            File.AppendAllText(logFile, "Screenshots completed successfully.\n");
            return 0;
        }
        catch (Exception ex)
        {
            File.AppendAllText(logFile, $"Error during capture: {ex}\n");
            return 1;
        }
    }
}
