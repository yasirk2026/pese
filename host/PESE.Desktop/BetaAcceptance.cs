using System.IO;
using System.Net.Http;
using System.Net.Http.Json;
using System.Security.Cryptography;
using System.Text.Json;
using System.Windows;
using Microsoft.Web.WebView2.Core;

namespace ManiacSoftwares.PESE;

// Explicit synthetic acceptance only. Never reads or changes the owner pointer.
internal static class BetaAcceptance
{
    internal static int Run(string[] args)
    {
        if (args.Length != 2 || !File.Exists(Path.Combine(args[0], ".pese-disposable-fixture"))) return 2;
        var fixture = Path.GetFullPath(args[0]); var output = Path.GetFullPath(args[1]);
        Directory.CreateDirectory(output);
        Paths.AcceptanceProfile = Path.Combine(output, "LocalAppData", "ManiacSoftwares", Paths.ProfileName);
        var originalDocuments = SHA256.HashData(File.ReadAllBytes(Path.Combine(fixture, "firestore_documents.json")));
        var checks = new List<object>(); var code = 1;
        var app = new Application();
        var window = new MainWindow(fixture) { ShowInTaskbar = false, ShowActivated = false, Opacity = .01 };
        window.Loaded += async (_, _) =>
        {
            BrainProcess? restarted = null;
            try
            {
                await Wait(() => {
                    if (window.AcceptanceError is not null) throw new InvalidOperationException(window.AcceptanceError);
                    return Task.FromResult(window.AcceptanceCore is not null && window.AcceptanceBrain is { Running: true });
                }, 180);
                var core = window.AcceptanceCore!; var brain = window.AcceptanceBrain!;
                var stablePointer = Path.Combine(output, "LocalAppData", "ManiacSoftwares", "PESE", "desktop-settings.json");
                Directory.CreateDirectory(Path.GetDirectoryName(stablePointer)!);
                File.WriteAllText(stablePointer, JsonSerializer.Serialize(new { brainPath = Paths.IsOwnerBeta ? "synthetic-stable-pointer-sentinel" : fixture }));
                var stablePointerHash = SHA256.HashData(File.ReadAllBytes(stablePointer));
                if (Paths.IsOwnerBeta) await BrainProcess.CommandAsync("connect", fixture);
                Check(stablePointerHash.SequenceEqual(SHA256.HashData(File.ReadAllBytes(stablePointer))), "BETA selection preserves stable pointer");
                Check(JsonDocument.Parse(File.ReadAllText(Paths.Settings)).RootElement.GetProperty("brainPath").GetString() == fixture, "BETA selection writes its own pointer");
                checks.Add(new { betaSelectionPreservesStablePointer = true, betaProfile = Paths.Profile });
                var installation = new Velopack.UpdateManager(output,
                    new Velopack.UpdateOptions { ExplicitChannel = SoftwareUpdates.Channel });
                checks.Add(new { installed = installation.IsInstalled, appId = installation.AppId,
                    packageId = SoftwareUpdates.PackageId, channel = SoftwareUpdates.Channel,
                    version = SoftwareUpdates.Version, ownerBeta = Paths.IsOwnerBeta,
                    application = Paths.Install, profile = Paths.Profile });
                if (File.Exists(Path.Combine(fixture, ".pese-require-installed")))
                    Check(installation.IsInstalled && installation.AppId == SoftwareUpdates.PackageId,
                        "actual installed package identity");
                if (Paths.IsOwnerBeta) {
                    var publicUpdates = new SoftwareUpdates(_ => { });
                    await publicUpdates.CheckAsync();
                    Check(publicUpdates.State.status == "manual", "Owner BETA public feed disabled");
                }
                // Core exists before OpenAsync finishes its initial navigation.
                // Wait for that document before issuing the acceptance navigation.
                await Wait(async () => (await core.ExecuteScriptAsync("Boolean(window.__PESE_CONFIG__ && document.body.innerText.includes('Brain Active'))")) == "true");
                var initial = await Get(brain, "/api/intelligence/beta/status");
                Check(initial.GetProperty("supported").GetBoolean(), "compiled closed BETA channel");
                Check(!initial.GetProperty("participation").GetProperty("accepted").GetBoolean(), "no implicit participation");
                var queries = JsonSerializer.Deserialize<string[]>(File.ReadAllText(Path.Combine(fixture, ".pese-beta-queries.json")))!;
                var query = queries[0];
                core.Navigate(brain.Origin + "/neural-genesis/");
                await Wait(async () => (await core.ExecuteScriptAsync("Boolean(document.querySelector('[data-testid=neural-genesis-lab]') && document.body.innerText.includes('I affirmatively accept'))")) == "true");
                using (var shot = File.Create(Path.Combine(output, "beta-agreement.png")))
                    await core.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png, shot);
                using var docs = JsonDocument.Parse(File.ReadAllText(Path.Combine(fixture, "firestore_documents.json")));
                var ids = string.Join(", ", docs.RootElement.EnumerateObject().Select(p => p.Value.GetProperty("id").GetString()));
                await core.ExecuteScriptAsync("""
                    (() => { const field=document.querySelector('[data-testid=beta-feedback-scope]');
                    if(!field) throw new Error('scope field missing');
                    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(field,
                    """ + JsonSerializer.Serialize(ids) + """
                    ); field.dispatchEvent(new Event('input',{bubbles:true}));
                    Array.from(document.querySelectorAll('label')).find(e=>e.textContent.includes('I affirmatively accept'))?.querySelector('input')?.click(); })()
                    """);
                await Task.Delay(200);
                await core.ExecuteScriptAsync("Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='Accept closed BETA')?.click()");
                await Wait(async () => (await Get(brain, "/api/intelligence/beta/status")).GetProperty("participation").GetProperty("accepted").GetBoolean());
                Check((await Get(brain, "/api/intelligence/beta/status")).GetProperty("participation").GetProperty("feedback_scope").GetArrayLength() > 0, "UI scope persisted");
                JsonElement baseline = default, neural = default;
                foreach (var attempt in queries) {
                    query = attempt;
                    await Put(brain, new { neural = false });
                    baseline = await Get(brain, "/api/search?q=" + Uri.EscapeDataString(query));
                    await Put(brain, new { neural = true });
                    neural = await Get(brain, "/api/search?q=" + Uri.EscapeDataString(query));
                    checks.Add(new { query, trace = neural.GetProperty("hybrid_trace").GetProperty("neural_ranking"),
                        baseline = baseline.GetProperty("results").EnumerateArray().Select(r=>r.GetProperty("doc_id").GetString()).ToArray(),
                        candidate = neural.GetProperty("results").EnumerateArray().Select(r=>r.GetProperty("doc_id").GetString()).ToArray() });
                    if (!baseline.GetProperty("results").EnumerateArray().Select(r=>r.GetProperty("doc_id").GetString()).SequenceEqual(
                        neural.GetProperty("results").EnumerateArray().Select(r=>r.GetProperty("doc_id").GetString()))) break;
                }
                var trace = neural.GetProperty("hybrid_trace").GetProperty("neural_ranking");
                checks.Add(new { attemptedInference = trace });
                Check(trace.GetProperty("authority").GetString() == "BOUNDED_RANKING_ONLY", "actual isolated model applied");
                Check(neural.GetProperty("results").EnumerateArray().Any(r => Math.Abs(r.GetProperty("neural_adjustment").GetDouble()) > 0), "nonzero neural score");
                var before = baseline.GetProperty("results").EnumerateArray().Select(r => r.GetProperty("doc_id").GetString()).ToArray();
                var after = neural.GetProperty("results").EnumerateArray().Select(r => r.GetProperty("doc_id").GetString()).ToArray();
                Check(!before.SequenceEqual(after), "real hybrid result order changed");
                Check(before.Order().SequenceEqual(after.Order()), "eligible membership preserved");
                var top = neural.GetProperty("results")[0];
                var feedback = await brain.Client.PostAsJsonAsync(brain.Origin + "/api/search/feedback", new {
                    query, search_context_id = neural.GetProperty("search_id").GetString(), target_type = "SERP_RESULT",
                    target_id = top.GetProperty("doc_id").GetString(), target_slug = top.GetProperty("slug").GetString(),
                    rank_position = 1, feedback = "DISLIKE", reason = "not relevant" });
                Check(feedback.IsSuccessStatusCode, "feedback provenance and selective capture");
                var status = await Get(brain, "/api/intelligence/beta/status");
                Check(status.GetProperty("evidence").GetProperty("total").GetInt32() > 0, "local queue captured eligible experience");
                var savedCount = status.GetProperty("evidence").GetProperty("total").GetInt32();
                await Put(brain, new { paused = true });
                await Get(brain, "/api/search?q=" + Uri.EscapeDataString(query + " notes"));
                Check((await Get(brain, "/api/intelligence/beta/status")).GetProperty("evidence").GetProperty("total").GetInt32() == savedCount, "pause prevents collection");
                await Put(brain, new { paused = false });
                core.Navigate(brain.Origin + "/neural-genesis/");
                await Wait(async () => (await core.ExecuteScriptAsync("document.body.innerText.includes('experimental bounded neural')")) == "true");
                using (var shot = File.Create(Path.Combine(output, "beta-dashboard.png")))
                    await core.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png, shot);
                Check((await Get(brain, "/desktop/offline-check")).GetProperty("external_connections_blocked").GetBoolean(), "offline boundary");
                checks.Add(new { warmInference = (await Get(brain,"/api/intelligence/beta/status")).GetProperty("inference") });
                checks.Add(new { actualWpfWebView2 = true, agreementViaUi = true, eligibleOrderChanged = true,
                    baselineOrder = before, neuralOrder = after, inference = trace, captured = savedCount, pauseVerified = true });
                await window.AcceptanceStopAsync();
                restarted = new BrainProcess();
                await restarted.StartAsync(fixture, CancellationToken.None);
                var persisted = await Get(restarted, "/api/intelligence/beta/status");
                Check(persisted.GetProperty("participation").GetProperty("accepted").GetBoolean(), "agreement persists across real engine restart");
                Check(persisted.GetProperty("model").GetProperty("checkpoint").GetString() == status.GetProperty("model").GetProperty("checkpoint").GetString(), "checkpoint restart identity");
                // The earlier explicit DISLIKE changed canonical preferences.
                // Compare fallback to a fresh deterministic run with those same
                // preferences, rather than the order before the reaction.
                await Put(restarted, new { neural = false });
                var currentMaae = await Get(restarted, "/api/search?q=" + Uri.EscapeDataString(query));
                var fallbackExpected = currentMaae.GetProperty("results").EnumerateArray().Select(r => r.GetProperty("doc_id").GetString()).ToArray();
                await Put(restarted, new { neural = true });
                // An explicitly labelled damaged POINTER fixture, never a trained
                // candidate or a quality-earned promotion. Exercise real fallback
                // and rollback through the installed engine without changing weights.
                var account = persisted.GetProperty("storage_namespace").GetString()!;
                var pointer = Path.Combine(fixture, ".pese-intelligence-v1", "accounts", account, "beta", "active.json");
                File.WriteAllText(pointer, "{\"version\":1,\"current\":\"damaged-pointer-fixture\",\"previous\":\"base\"}");
                var fallback = await Get(restarted, "/api/search?q=" + Uri.EscapeDataString(query));
                Check(fallback.GetProperty("hybrid_trace").GetProperty("neural_ranking").GetProperty("authority").GetString() == "NONE", "damaged artifact falls back");
                Check(fallbackExpected.SequenceEqual(fallback.GetProperty("results").EnumerateArray().Select(r => r.GetProperty("doc_id").GetString())), "fallback equals MAAE order");
                using (var rolledBack = await restarted.Client.PostAsync(restarted.Origin + "/api/intelligence/beta/rollback", null))
                    Check(rolledBack.IsSuccessStatusCode, "explicit rollback API");
                Check((await Get(restarted, "/api/intelligence/beta/status")).GetProperty("model").GetProperty("checkpoint").GetString() == status.GetProperty("model").GetProperty("checkpoint").GetString(), "rollback restores exact base checkpoint");
                checks.Add(new { artifactFallback = true, fallbackEqualsMaae = true, exactBaseRollback = true,
                    rollbackFixture = "damaged_pointer_only_no_training_or_promotion" });
                await restarted.Client.PostAsync(restarted.Origin + "/api/intelligence/beta/exit", null);
                Check((await Get(restarted, "/api/intelligence/beta/status")).GetProperty("ranking_mode").GetString() == "deterministic_maae", "safe BETA exit");
                await restarted.DisposeAsync(); restarted = null;
                var finalDocuments = SHA256.HashData(File.ReadAllBytes(Path.Combine(fixture, "firestore_documents.json")));
                Check(originalDocuments.SequenceEqual(finalDocuments), "canonical documents preserved");
                checks.Add(new { restartPersistence = true, safeExit = true, canonicalDocumentsUnchanged = true, networkUpload = false });
                code = 0;
            }
            catch (Exception error) {
                checks.Add(new { error = error.Message });
                if (window.AcceptanceCore is { } failedCore) {
                    checks.Add(new { source = failedCore.Source, visibleText = await failedCore.ExecuteScriptAsync("document.body.innerText") });
                    using var failedShot = File.Create(Path.Combine(output, "beta-failure.png"));
                    await failedCore.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png, failedShot);
                }
            }
            finally
            {
                if (restarted is not null) await restarted.DisposeAsync();
                await window.AcceptanceStopAsync();
                File.WriteAllText(Path.Combine(output, "native-beta-acceptance.json"), JsonSerializer.Serialize(new { passed = code == 0, checks }, new JsonSerializerOptions { WriteIndented = true }));
                window.Close();
            }
        };
        app.Run(window); return code;
    }
    private static async Task<JsonElement> Get(BrainProcess brain, string path) => JsonDocument.Parse(await brain.Client.GetStringAsync(brain.Origin + path)).RootElement.Clone();
    private static async Task Put(BrainProcess brain, object changes) { using var result = await brain.Client.PutAsJsonAsync(brain.Origin + "/api/intelligence/beta/settings", changes); result.EnsureSuccessStatusCode(); }
    private static void Check(bool value, string name) { if (!value) throw new InvalidOperationException(name); }
    private static async Task Wait(Func<Task<bool>> ready, int seconds = 90)
    {
        var deadline = DateTime.UtcNow.AddSeconds(seconds);
        while (DateTime.UtcNow < deadline) { if (await ready()) return; await Task.Delay(100); }
        throw new TimeoutException("BETA native acceptance did not reach the expected state");
    }
}
