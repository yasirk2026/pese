using System.IO;
using System.Security.Cryptography;
using System.Text.Json;
using System.Windows;
using Microsoft.Web.WebView2.Core;
using Velopack;

namespace ManiacSoftwares.PESE;

internal static class UpdateUiAcceptance
{
    internal static int Run(string[] args)
    {
        if (args.Length != 1) return 2;
        var planPath = Path.GetFullPath(args[0]);
        var root = Path.GetDirectoryName(planPath)!;
        if (!File.Exists(Path.Combine(root, ".pese-disposable-fixture"))) return 2;
        using var plan = JsonDocument.Parse(File.ReadAllText(planPath));
        string Owned(string key)
        {
            var value = Path.GetFullPath(plan.RootElement.GetProperty(key).GetString()!);
            if (!value.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("UI acceptance path escaped its fixture.");
            return value;
        }
        var install = Owned("install");
        if (!Path.GetFullPath(Paths.Install).StartsWith(install + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)) return 2;
        var brain = Owned("brain");
        if (brain.StartsWith(install + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)) return 2;
        var feed = Owned("feed");
        Paths.AcceptanceProfile = Path.Combine(root, "LocalAppData", "ManiacSoftwares", "PESE");
        var app = new Application { ShutdownMode = ShutdownMode.OnMainWindowClose };
        var window = new MainWindow(brain, () => new UpdateManager(feed,
            new UpdateOptions { ExplicitChannel = SoftwareUpdates.Channel }), planPath);
        var passed = false;
        window.Loaded += async (_, _) =>
        {
            try
            {
                async Task Until(Func<Task<bool>> predicate, int seconds = 120)
                {
                    var end = DateTime.UtcNow.AddSeconds(seconds);
                    while (DateTime.UtcNow < end)
                    {
                        if (await predicate()) return;
                        await Task.Delay(200);
                    }
                    throw new TimeoutException("Native update UI acceptance timed out.");
                }
                await Until(() => Task.FromResult(window.UpdateAcceptanceCore is not null));
                var core = window.UpdateAcceptanceCore!;
                async Task<string> Body() => JsonSerializer.Deserialize<string>(await core.ExecuteScriptAsync("document.body.innerText")) ?? "";
                async Task Click(string prefix)
                {
                    var value = JsonSerializer.Serialize(prefix);
                    var clicked = await core.ExecuteScriptAsync($"(() => {{ const b = [...document.querySelectorAll('button')].reverse().find(b => b.innerText.trim().startsWith({value}) && !b.disabled); if (!b) return false; b.click(); return true; }})()");
                    if (clicked != "true") throw new InvalidOperationException("Required update button unavailable: " + prefix);
                }
                core.Navigate(window.UpdateAcceptanceBrain!.Origin + "/settings/?tab=updates");
                await Until(async () => core.Source.Contains("tab=updates") && (await Body()).Contains("Check for updates"));
                await Click("Check for updates");
                var target = plan.RootElement.GetProperty("targetVersion").GetString()!;
                await Until(async () => (await Body()).Contains("Download " + target));
                var notes = await Body();
                var expectedNotes = plan.RootElement.GetProperty("expectedNotes").GetString()!;
                if (string.IsNullOrWhiteSpace(expectedNotes) || !notes.Contains(SoftwareUpdates.Version) || !notes.Contains(target) || !notes.Contains(expectedNotes))
                    throw new InvalidDataException("Native current version, target or package notes missing from Settings.");
                using (var shot = File.Create(Path.Combine(root, "update-notes.png")))
                    await core.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png, shot);
                await Click("Download");
                await Until(async () => (await Body()).Contains("Update and restart"), 300);
                using (var shot = File.Create(Path.Combine(root, "update-ready.png")))
                    await core.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png, shot);
                var canonical = Directory.EnumerateFiles(brain, "*", SearchOption.AllDirectories)
                    .Where(p => !p.Contains(Path.DirectorySeparatorChar + "semantic_index" + Path.DirectorySeparatorChar)
                        && !Path.GetFileName(p).StartsWith('.') && !p.EndsWith("-shm") && !p.EndsWith("-wal"))
                    .ToDictionary(p => Path.GetRelativePath(brain, p), p => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(p))));
                canonical["desktop-pointer"] = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(Paths.Settings)));
                File.WriteAllText(Path.Combine(root, "update-before.json"), JsonSerializer.Serialize(new {
                    passed = true, canonical, version = SoftwareUpdates.Version, target,
                    nativeUi = true, packageNotesVisible = true, readyToRestart = true }));
                passed = true;
                await Click("Update and restart");
            }
            catch (Exception exc)
            {
                File.WriteAllText(Path.Combine(root, "ui-failure.json"), JsonSerializer.Serialize(new { error = exc.ToString() }));
                passed = false;
                window.Close();
            }
        };
        app.Run(window);
        return passed ? 0 : 1;
    }
}
