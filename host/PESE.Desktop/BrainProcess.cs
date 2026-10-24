using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace ManiacSoftwares.PESE;

internal sealed class BrainProcess : IAsyncDisposable
{
    private Process? process;
    private Job? job;
    private Task? outputTask, errorTask;
    public string Token { get; } = Convert.ToHexString(RandomNumberGenerator.GetBytes(32));
    public string? Origin { get; private set; }
    public int ProcessId => process?.Id ?? 0;
    public bool Running => process is { HasExited: false };
    public HttpClient Client { get; } = new() { Timeout = TimeSpan.FromSeconds(120) };

    internal static ProcessStartInfo StartInfo()
    {
        var python = Path.Combine(Paths.Install, "runtime", "python", "python.exe");
        if (!File.Exists(python)) throw new FileNotFoundException("The bundled Python runtime is missing. Reinstall PESE.");
        var info = new ProcessStartInfo(python)
        {
            UseShellExecute = false, CreateNoWindow = true, WorkingDirectory = Paths.Install,
            RedirectStandardInput = true, RedirectStandardOutput = true, RedirectStandardError = true,
            StandardInputEncoding = new UTF8Encoding(false), StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8
        };
        info.ArgumentList.Add("-B"); info.ArgumentList.Add("-u");
        info.ArgumentList.Add("-m"); info.ArgumentList.Add("engine.desktop.launcher");
        // Isolated CPython ignores PYTHONPATH; remove inherited development flags as well.
        foreach (var key in info.Environment.Keys.Where(k => k.StartsWith("PESE_", StringComparison.OrdinalIgnoreCase)
                     || k.StartsWith("PYTHON", StringComparison.OrdinalIgnoreCase)).ToArray()) info.Environment.Remove(key);
        return info;
    }

    public static async Task<JsonElement> CommandAsync(string action, string path)
    {
        using var owned = new Job();
        using var child = new Process { StartInfo = StartInfo() };
        child.Start(); owned.Add(child);
        var stdout = child.StandardOutput.ReadToEndAsync();
        var stderr = child.StandardError.ReadToEndAsync();
        await child.StandardInput.WriteLineAsync(JsonSerializer.Serialize(new { action, brainPath = path }));
        child.StandardInput.Close();
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(30));
        await child.WaitForExitAsync(timeout.Token);
        var result = await stdout; await stderr;
        JsonElement root;
        try { root = JsonDocument.Parse(result.Trim()).RootElement.Clone(); }
        catch { throw new InvalidOperationException("The bundled Brain service could not validate this folder. Reinstall PESE if this continues."); }
        if (child.ExitCode != 0 || !root.GetProperty("ok").GetBoolean())
            throw new InvalidOperationException(root.GetProperty("message").GetString());
        return root;
    }

    public async Task StartAsync(string path, CancellationToken cancellation)
    {
        try
        {
            job = new Job(); process = new Process { StartInfo = StartInfo(), EnableRaisingEvents = true };
            process.Start(); job.Add(process);
            // Child blocks on stdin before any Brain import or write, until job ownership is established.
            errorTask = Task.Run(async () => { while (await process.StandardError.ReadLineAsync() is not null) { } });
            await process.StandardInput.WriteLineAsync(JsonSerializer.Serialize(new { action = "serve", brainPath = path, token = Token }));
            process.StandardInput.Close();
            using var startup = CancellationTokenSource.CreateLinkedTokenSource(cancellation);
            startup.CancelAfter(TimeSpan.FromSeconds(120));
            string? line;
            while ((line = await process.StandardOutput.ReadLineAsync(startup.Token)) is not null)
            {
                if (line.StartsWith("PESE_PORT ") && int.TryParse(line[10..], out var port) && port is > 0 and <= 65535)
                { Origin = $"http://127.0.0.1:{port}"; break; }
                if (line.StartsWith("{\"ok\": false")) ThrowProtocolError(line);
            }
            if (Origin is null) throw new InvalidOperationException("Your Brain could not start. Verify the Brain and installation assets.");
            string? launchError = null;
            outputTask = Task.Run(async () =>
            {
                while (await process.StandardOutput.ReadLineAsync() is { } next)
                    if (next.StartsWith("{\"ok\": false"))
                    {
                        try { launchError = JsonDocument.Parse(next).RootElement.GetProperty("message").GetString(); } catch { }
                    }
            });
            Client.DefaultRequestHeaders.Add("X-PESE-Token", Token);
            while (!startup.IsCancellationRequested)
            {
                if (process.HasExited)
                {
                    await outputTask;
                    throw new InvalidOperationException(launchError ?? "Your Brain stopped during startup. Verify the installation and selected folder.");
                }
                try
                {
                    using var probe = CancellationTokenSource.CreateLinkedTokenSource(startup.Token);
                    probe.CancelAfter(TimeSpan.FromSeconds(2));
                    using var health = await Client.GetAsync(Origin + "/health", probe.Token);
                    if (health.IsSuccessStatusCode)
                    {
                        using var body = JsonDocument.Parse(await health.Content.ReadAsStringAsync(probe.Token));
                        if (body.RootElement.GetProperty("status").GetString() == "healthy")
                        { Log.Write("brain_ready"); return; }
                    }
                }
                catch (HttpRequestException) { }
                catch (OperationCanceledException) when (!startup.IsCancellationRequested) { }
                await Task.Delay(200, startup.Token);
            }
            startup.Token.ThrowIfCancellationRequested();
        }
        catch { await DisposeAsync(); throw; }
    }
    private static void ThrowProtocolError(string line)
    {
        using var json = JsonDocument.Parse(line);
        throw new InvalidOperationException(json.RootElement.GetProperty("message").GetString());
    }

    public async ValueTask DisposeAsync()
    {
        if (process is { HasExited: false })
        {
            try
            {
                if (Origin is not null)
                {
                    using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(2));
                    using var response = await Client.PostAsync(Origin + "/desktop/shutdown", null, timeout.Token);
                }
                using var grace = new CancellationTokenSource(TimeSpan.FromSeconds(5));
                await process.WaitForExitAsync(grace.Token);
            }
            catch { Log.Write("brain_forced_stop"); }
        }
        job?.Dispose(); job = null; // Kernel closes every remaining descendant.
        if (process is not null)
        {
            try { await process.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(5)); } catch { }
            process.Dispose(); process = null;
        }
        Client.Dispose();
        Log.Write("brain_stopped");
    }
}
