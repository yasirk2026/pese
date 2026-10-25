using System.Reflection;
using System.IO;
using System.Security.Cryptography;
using System.Net.Http;
using Velopack;
using Velopack.Sources;
using Velopack.Locators;

namespace ManiacSoftwares.PESE;

internal sealed record UpdateState(string type = "update_status", string status = "idle",
    string currentVersion = "", string? targetVersion = null, int? progress = null,
    string? error = null, string? releaseNotes = null, string channel = "win");

// Native authority. A web message can request an operation, never supply a feed or command.
internal sealed class SoftwareUpdates
{
    internal const string Repository = "https://github.com/yasirk2026/pese";
    internal const string PackageId = "ManiacSoftwares.PESE";
    internal const string Channel = "win"; // Preserve Alpha.4's package channel.
    internal static string Version => (Assembly.GetExecutingAssembly()
        .GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion ?? "unknown").Split('+')[0];
    private readonly SemaphoreSlim operation = new(1, 1);
    private readonly Func<UpdateManager> factory;
    private readonly Action<UpdateState> publish;
    private UpdateManager? manager;
    private UpdateInfo? pending;
    private bool downloaded;
    internal UpdateState State { get; private set; } = new(currentVersion: Version);

    internal SoftwareUpdates(Action<UpdateState> publish, Func<UpdateManager>? acceptanceFactory = null)
    {
        this.publish = publish;
        // The injected factory exists only for the explicit disposable CLI acceptance harness.
        factory = acceptanceFactory ?? (() => new UpdateManager(
            new GithubSource(Repository, accessToken: null, prerelease: true, downloader: new UpdateDownloader()),
            new UpdateOptions { ExplicitChannel = Channel, AllowVersionDowngrade = false }));
    }

    private void Set(string status, int? progress = null, string? error = null)
    {
        State = new(status: status, currentVersion: manager?.CurrentVersion?.ToString() ?? Version,
            targetVersion: pending?.TargetFullRelease.Version.ToString(), progress: progress,
            error: error, releaseNotes: pending?.TargetFullRelease.NotesMarkdown);
        publish(State);
    }

    internal void SendState() => publish(State);

    private UpdateManager Manager()
    {
        var value = manager ??= factory();
        if (!value.IsInstalled || value.AppId != PackageId)
            throw new InvalidOperationException("Use the installed PESE application to update.");
        return value;
    }

    internal async Task CheckAsync()
    {
        if (!await operation.WaitAsync(0)) return;
        try
        {
            // Keep a verified downloaded package ready until the user applies it.
            if (downloaded) { Set("ready", 100); return; }
            pending = null;
            Set("checking");
            var check = Manager().CheckForUpdatesAsync();
            pending = await check.WaitAsync(TimeSpan.FromSeconds(35));
            if (pending is not null && pending.TargetFullRelease.PackageId != PackageId)
                throw new InvalidDataException("Unexpected update package identity.");
            Set(pending is null ? "up_to_date" : "available");
        }
        catch (Exception exc)
        {
            Log.Write("update_check_failed", exc.GetType().Name);
            Set("failed", error: "Could not check for updates. Check your connection and try again. Local search is still available.");
        }
        finally { operation.Release(); }
    }

    internal async Task DownloadAsync(CancellationToken cancellation)
    {
        if (!await operation.WaitAsync(0)) return;
        try
        {
            if (pending is null || downloaded) { SendState(); return; }
            Set("downloading", 0);
            using var deadline = CancellationTokenSource.CreateLinkedTokenSource(cancellation);
            deadline.CancelAfter(TimeSpan.FromMinutes(30));
            await Manager().DownloadUpdatesAsync(pending, p => Set("downloading", Math.Clamp(p, 0, 100)), deadline.Token);
            VerifyDownloaded();
            downloaded = true;
            Set("ready", 100);
        }
        catch (Exception exc)
        {
            downloaded = false;
            Log.Write("update_download_failed", exc.GetType().Name);
            Set("failed", error: "The update could not be downloaded and verified. Your installed version is unchanged. Try downloading again.");
        }
        finally { operation.Release(); }
    }

    internal async Task ApplyAsync(Func<Task> stopEngine, Action exit, string[]? acceptanceRestartArgs = null)
    {
        if (!await operation.WaitAsync(0)) return;
        try
        {
            if (!downloaded || pending is null) { SendState(); return; }
            VerifyDownloaded();
            Set("installing", 100);
            await stopEngine(); // No forced termination is allowed on the update path.
            Manager().WaitExitThenApplyUpdates(pending.TargetFullRelease, silent: false, restart: true,
                restartArgs: acceptanceRestartArgs ?? Array.Empty<string>());
            Set("restarting", 100);
            exit(); // The updater waits until the host releases its mutex and exits normally.
        }
        catch (Exception exc)
        {
            Log.Write("update_install_failed", exc.GetType().Name);
            Set("failed", error: "The update was not activated. Close and reopen PESE, then retry. Your Brain remains in its selected folder.");
        }
        finally { operation.Release(); }
    }

    private void VerifyDownloaded()
    {
        var asset = pending!.TargetFullRelease;
        if (Path.GetFileName(asset.FileName) != asset.FileName)
            throw new InvalidDataException("Invalid update package filename.");
        var packages = VelopackLocator.Current.PackagesDir ?? throw new InvalidDataException("Package storage is unavailable.");
        var path = Path.Combine(packages, asset.FileName);
        using var stream = File.OpenRead(path);
        var hash = Convert.ToHexString(SHA256.HashData(stream));
        if (stream.Length != asset.Size || string.IsNullOrEmpty(asset.SHA256) ||
            !hash.Equals(asset.SHA256, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("The downloaded package failed SHA-256 verification.");
    }
}

internal sealed class UpdateDownloader : HttpClientFileDownloader
{
    // Release metadata has a short per-request bound. Package streaming uses
    // Velopack's cancellation-aware downloader and the operation's 30 minute deadline.
    public override Task<string> DownloadString(string url, IDictionary<string, string>? headers, double timeout)
        => base.DownloadString(url, headers, Math.Min(timeout, 0.15));
    public override Task<byte[]> DownloadBytes(string url, IDictionary<string, string>? headers, double timeout)
        => base.DownloadBytes(url, headers, Math.Min(timeout, 0.15));
}
