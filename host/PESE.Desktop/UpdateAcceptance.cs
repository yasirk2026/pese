using System.IO;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Nodes;
using Velopack;
using Velopack.Sources;
using Velopack.Logging;

namespace ManiacSoftwares.PESE;

// Explicit opt-in CLI. Every writable path must belong to a marked disposable case.
internal static class UpdateAcceptance
{
    internal static async Task<int> RunAsync(string mode, string[] args)
    {
        if (args.Length != 1) return 2;
        var planPath = Path.GetFullPath(args[0]);
        var root = Path.GetDirectoryName(planPath)!;
        if (!File.Exists(Path.Combine(root, ".pese-disposable-fixture"))) return 2;
        var report = Path.Combine(root, mode == "--accept-updater" ? "update-before.json" : "update-after.json");
        try
        {
            using var plan = JsonDocument.Parse(File.ReadAllText(planPath));
            string Owned(string key)
            {
                var path = Path.GetFullPath(plan.RootElement.GetProperty(key).GetString()!);
                if (!path.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidDataException("Acceptance path is outside its disposable case.");
                return path;
            }
            var install = Owned("install");
            if (!Path.GetFullPath(Paths.Install).StartsWith(install + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("Run the installed disposable executable.");
            var path = Owned("brain");
            if (path.StartsWith(install + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("The Brain must be outside the installation.");
            Paths.AcceptanceProfile = Path.Combine(root, "LocalAppData", "ManiacSoftwares", "PESE");
            Directory.CreateDirectory(Paths.AcceptanceProfile);
            var identity = JsonDocument.Parse(File.ReadAllText(Path.Combine(path, "pese-brain.json")))
                .RootElement.GetProperty("brainId").GetString();
            Dictionary<string, string> Digests()
            {
                var result = Directory.EnumerateFiles(path, "*", SearchOption.AllDirectories)
                    .Where(p => !p.Contains(Path.DirectorySeparatorChar + "semantic_index" + Path.DirectorySeparatorChar)
                        && !Path.GetFileName(p).StartsWith('.') && !p.EndsWith("-shm") && !p.EndsWith("-wal"))
                    .ToDictionary(p => Path.GetRelativePath(path, p), p => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(p))));
                result["desktop-pointer"] = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(Paths.Settings)));
                return result;
            }
            var states = new List<UpdateState>();
            var updates = new SoftwareUpdates(state => { lock (states) states.Add(state); },
                () => new UpdateManager(Owned("feed"), new UpdateOptions { ExplicitChannel = SoftwareUpdates.Channel }));
            await using var brain = new BrainProcess();
            await brain.StartAsync(path, CancellationToken.None);
            var health = JsonDocument.Parse(await brain.Client.GetStringAsync(brain.Origin + "/health")).RootElement.Clone();
            var original = Digests();
            // A real serving request is outstanding when graceful engine shutdown is requested.
            var search = brain.Client.GetAsync(brain.Origin + "/api/search?q=PESE&debug=true");
            if (mode == "--accept-update-restarted")
            {
                var expected = plan.RootElement.GetProperty("targetVersion").GetString();
                if (SoftwareUpdates.Version != expected) throw new InvalidDataException("The restarted binary is the wrong version.");
                using var before = JsonDocument.Parse(File.ReadAllText(Path.Combine(root, "update-before.json")));
                var baseline = before.RootElement.GetProperty("canonical").Deserialize<Dictionary<string, string>>()!;
                if (baseline.Count != original.Count || baseline.Any(x => !original.TryGetValue(x.Key, out var value) || value != x.Value))
                    throw new InvalidDataException("Canonical state or pointer changed during update.");
                using var result = await search;
                result.EnsureSuccessStatusCode();
                await brain.StopForUpdateAsync(CancellationToken.None);
                File.WriteAllText(report, JsonSerializer.Serialize(new { passed = true, version = SoftwareUpdates.Version,
                    identity, health, canonical = Digests(), engineExited = !brain.Running, realRestart = true }, new JsonSerializerOptions { WriteIndented = true }));
                return 0;
            }
            var failureReceipt = Path.Combine(root, "download-faults-passed.json");
            if (!File.Exists(failureReceipt))
            {
                await FailureChecksAsync(Owned("feed"));
                File.WriteAllText(failureReceipt, JsonSerializer.Serialize(new { passed = true, version = SoftwareUpdates.Version }));
            }
            await updates.CheckAsync();
            if (updates.State.status != "available") throw new InvalidDataException("The installed updater did not find the target.");
            if (string.IsNullOrWhiteSpace(updates.State.releaseNotes)) throw new InvalidDataException("The update has no package release notes.");
            await updates.DownloadAsync(CancellationToken.None);
            if (updates.State.status != "ready") throw new InvalidDataException("The package did not download and verify.");
            using var searchResult = await search;
            searchResult.EnsureSuccessStatusCode();
            var handedOff = false;
            await updates.ApplyAsync(async () =>
            {
                var inFlight = brain.Client.GetAsync(brain.Origin + "/api/search?q=PESE&debug=true");
                await brain.StopForUpdateAsync(CancellationToken.None);
                using var completed = await inFlight;
                completed.EnsureSuccessStatusCode();
                var final = Digests();
                // Searches legitimately append zero-authority shadow observations.
                // Activation must preserve the exact DB after all those writes drain.
                if (original.Count != final.Count || original.Where(x => x.Key != "search_sync_feedback.db")
                    .Any(x => !final.TryGetValue(x.Key, out var value) || value != x.Value))
                    throw new InvalidDataException("Canonical data changed while draining the fixture engine.");
                File.WriteAllText(report, JsonSerializer.Serialize(new { passed = true, version = SoftwareUpdates.Version,
                    identity, health, canonical = final, states, activeSearchCompleted = true,
                    engineExited = !brain.Running, handoff = "requested; success requires update-after.json" }, new JsonSerializerOptions { WriteIndented = true }));
            }, () => handedOff = true, new[] { "--accept-update-restarted", planPath });
            return handedOff ? 0 : throw new InvalidOperationException("The update did not hand off to Velopack.", updates.LastError);
        }
        catch (Exception exc)
        {
            File.WriteAllText(report, JsonSerializer.Serialize(new { passed = false, error = exc.ToString() }, new JsonSerializerOptions { WriteIndented = true }));
            return 1;
        }
    }

    private static async Task FailureChecksAsync(string feed)
    {
        void Check(bool value, string label)
        { if (!value) throw new InvalidOperationException("Updater safety check failed: " + label); }
        var unavailable = new SoftwareUpdates(_ => { }, () => throw new HttpRequestException("Controlled offline source"));
        await unavailable.CheckAsync();
        Check(unavailable.State.status == "failed", "offline check must fail honestly");
        var stopped = false;
        await unavailable.ApplyAsync(() => { stopped = true; return Task.CompletedTask; }, () => { });
        Check(!stopped, "apply without a verified download must not stop the engine");
        var missingNotes = Path.Combine(Directory.GetParent(feed)!.FullName, "missing-notes-feed");
        Directory.CreateDirectory(missingNotes);
        var metadata = JsonNode.Parse(File.ReadAllText(Path.Combine(feed, "releases.win.json")))!;
        foreach (var asset in metadata["Assets"]!.AsArray()) asset!["NotesMarkdown"] = "";
        File.WriteAllText(Path.Combine(missingNotes, "releases.win.json"), metadata.ToJsonString());
        var invalid = new SoftwareUpdates(_ => { }, () => new UpdateManager(missingNotes,
            new UpdateOptions { ExplicitChannel = SoftwareUpdates.Channel }));
        await invalid.CheckAsync();
        Check(invalid.State.status == "failed", "release notes required before offering installation");
        await invalid.DownloadAsync(CancellationToken.None);
        Check(invalid.State.status == "failed", "invalid metadata cannot be bypassed by a download command");
        foreach (var failure in new[] { "interrupted", "checksum" })
        {
            var source = new FailureSource(feed, failure);
            var test = new SoftwareUpdates(_ => { }, () => new UpdateManager(source, new UpdateOptions { ExplicitChannel = SoftwareUpdates.Channel }));
            await Task.WhenAll(test.CheckAsync(), test.CheckAsync());
            Check(source.Checks == 1, "duplicate release checks");
            Check(test.State.status == "available", "controlled feed discovery");
            await test.DownloadAsync(CancellationToken.None);
            Check(test.State.status == "failed", failure + " download");
            var applied = false;
            await test.ApplyAsync(() => { applied = true; return Task.CompletedTask; }, () => { });
            Check(!applied, "failed download must not activate");
        }
    }

    private sealed class FailureSource(string feed, string failure) : IUpdateSource
    {
        private readonly SimpleFileSource inner = new(new DirectoryInfo(feed));
        internal int Checks;
        public async Task<VelopackAssetFeed> GetReleaseFeed(IVelopackLogger logger, string? appId, string channel,
            Guid? stagingId = null, VelopackAsset? latestLocalRelease = null)
        {
            Interlocked.Increment(ref Checks);
            await Task.Delay(200);
            return await inner.GetReleaseFeed(logger, appId, channel, stagingId, latestLocalRelease);
        }
        public async Task DownloadReleaseEntry(IVelopackLogger logger, VelopackAsset releaseEntry,
            string localFile, Action<int> progress, CancellationToken cancelToken = default)
        {
            if (failure == "interrupted")
            {
                await File.WriteAllBytesAsync(localFile, new byte[] { 1, 2, 3 }, cancelToken);
                progress(1);
                throw new IOException("Controlled interrupted transfer");
            }
            await inner.DownloadReleaseEntry(logger, releaseEntry, localFile, progress, cancelToken);
            using var file = File.Open(localFile, FileMode.Open, FileAccess.ReadWrite);
            file.WriteByte(0); // Corrupt a package after transfer; Velopack must reject it.
        }
    }
}
