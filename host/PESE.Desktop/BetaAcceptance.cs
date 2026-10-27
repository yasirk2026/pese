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
        Paths.AcceptanceProfile = Path.Combine(output, "LocalAppData", "ManiacSoftwares", "PESE");
        var originalDocuments = SHA256.HashData(File.ReadAllBytes(Path.Combine(fixture, "firestore_documents.json")));
        var checks = new List<object>(); var code = 1;
        var app = new Application();
        var window = new MainWindow(fixture) { ShowInTaskbar = false, ShowActivated = false, Opacity = .01 };
        window.Loaded += async (_, _) =>
        {
            BrainProcess? restarted = null;
            try
            {
                await Wait(() => Task.FromResult(window.AcceptanceCore is not null && window.AcceptanceBrain is { Running: true }), 180);
                var core = window.AcceptanceCore!; var brain = window.AcceptanceBrain!;
                var initial = await Get(brain, "/api/intelligence/beta/status");
                Check(initial.GetProperty("supported").GetBoolean(), "compiled closed BETA channel");
                Check(!initial.GetProperty("participation").GetProperty("accepted").GetBoolean(), "no implicit participation");
                var query = File.ReadAllText(Path.Combine(fixture, ".pese-beta-query.txt"));
                core.Navigate(brain.Origin + "/neural-genesis/");
                await Wait(async () => (await core.ExecuteScriptAsync("Boolean(document.querySelector('[data-testid=neural-genesis-lab]') && document.body.innerText.includes('I affirmatively accept'))")) == "true");
                using (var shot = File.Create(Path.Combine(output, "beta-agreement.png")))
                    await core.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png, shot);
                using var docs = JsonDocument.Parse(File.ReadAllText(Path.Combine(fixture, "firestore_documents.json")));
                var ids = string.Join(", ", docs.RootElement.EnumerateObject().Select(p => p.Value.GetProperty("id").GetString()));
                await core.ExecuteScriptAsync("""
                    (() => { const field=Array.from(document.querySelectorAll('label')).find(e=>e.textContent.includes('Document IDs eligible'))?.querySelector('input');
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
                await Put(brain, new { neural = false });
                var baseline = await Get(brain, "/api/search?q=" + Uri.EscapeDataString(query));
                await Put(brain, new { neural = true });
                var neural = await Get(brain, "/api/search?q=" + Uri.EscapeDataString(query));
                var trace = neural.GetProperty("hybrid_trace").GetProperty("neural_ranking");
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
                checks.Add(new { actualWpfWebView2 = true, agreementViaUi = true, eligibleOrderChanged = true,
                    baselineOrder = before, neuralOrder = after, inference = trace, captured = savedCount, pauseVerified = true });
                await window.AcceptanceStopAsync();
                restarted = new BrainProcess();
                await restarted.StartAsync(fixture, CancellationToken.None);
                var persisted = await Get(restarted, "/api/intelligence/beta/status");
                Check(persisted.GetProperty("participation").GetProperty("accepted").GetBoolean(), "agreement persists across real engine restart");
                Check(persisted.GetProperty("model").GetProperty("checkpoint").GetString() == status.GetProperty("model").GetProperty("checkpoint").GetString(), "checkpoint restart identity");
                await restarted.Client.PostAsync(restarted.Origin + "/api/intelligence/beta/exit", null);
                Check((await Get(restarted, "/api/intelligence/beta/status")).GetProperty("ranking_mode").GetString() == "deterministic_maae", "safe BETA exit");
                await restarted.DisposeAsync(); restarted = null;
                var finalDocuments = SHA256.HashData(File.ReadAllBytes(Path.Combine(fixture, "firestore_documents.json")));
                Check(originalDocuments.SequenceEqual(finalDocuments), "canonical documents preserved");
                checks.Add(new { restartPersistence = true, safeExit = true, canonicalDocumentsUnchanged = true, networkUpload = false });
                code = 0;
            }
            catch (Exception error) { checks.Add(new { error = error.Message }); }
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
