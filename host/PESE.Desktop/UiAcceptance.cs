using System.Diagnostics;
using System.IO;
using System.Text.Json;
using System.Windows;
using Microsoft.Web.WebView2.Core;

namespace ManiacSoftwares.PESE;

// Explicit opt-in product harness. It never changes the user's Brain pointer.
internal static class UiAcceptance
{
    internal static int Run(string[] args)
    {
        if (args.Length != 2 || !File.Exists(Path.Combine(args[0], ".pese-disposable-fixture"))) return 2;
        var output = Path.GetFullPath(args[1]);
        Directory.CreateDirectory(output);
        Paths.AcceptanceProfile = Path.Combine(output, "LocalAppData", "ManiacSoftwares", "PESE");
        var checks = new List<object>();
        var code = 1;
        var app = new Application();
        var window = new MainWindow(Path.GetFullPath(args[0]));
        window.Loaded += async (_, _) =>
        {
            int? enginePid = null;
            try
            {
                await Task.Delay(10000);
                if (window.AcceptanceCore is null && window.AcceptanceBrain is { Running: true })
                {
                    window.UpdateLayout();
                    var bitmap = new System.Windows.Media.Imaging.RenderTargetBitmap(
                        (int)window.ActualWidth, (int)window.ActualHeight, 96, 96, System.Windows.Media.PixelFormats.Pbgra32);
                    bitmap.Render(window);
                    var encoder = new System.Windows.Media.Imaging.PngBitmapEncoder();
                    encoder.Frames.Add(System.Windows.Media.Imaging.BitmapFrame.Create(bitmap));
                    using var image = File.Create(Path.Combine(output, "native-startup.png"));
                    encoder.Save(image);
                    checks.Add(new { nativeStartupBeforeWebView = true });
                }
                await Wait(() => Task.FromResult(window.AcceptanceCore is not null && window.AcceptanceBrain is { Running: true }), 900);
                var core = window.AcceptanceCore!;
                var brain = window.AcceptanceBrain!;
                enginePid = brain.ProcessId;
                await Wait(async () => (await core.ExecuteScriptAsync("Boolean(window.__PESE_CONFIG__ && document.querySelector('input'))")) == "true");
                var queries = new[] { "when did I buy my bicycle", "Japanese beginner roadmap", "Next.js server components vs client components", "PageRank internal linking", "japanise begnner roadmp", "PESE" };
                var anyPaa = false;
                var anyRelated = false;
                for (var index = 0; index < queries.Length; index++)
                {
                    core.Navigate(brain.Origin + "/search/?q=" + Uri.EscapeDataString(queries[index]));
                    await Wait(async () => (await core.ExecuteScriptAsync("Boolean(new URL(location.href).searchParams.get('q') === " + JsonSerializer.Serialize(queries[index]) + " && document.querySelector('article') && !document.body.innerText.includes('Checking grounded discovery suggestions'))")) == "true");
                    await Task.Delay(900);
                    await Wait(async () => (await core.ExecuteScriptAsync("!document.body.innerText.includes('Checking grounded discovery suggestions')")) == "true");
                    var state = JsonDocument.Parse(await core.ExecuteScriptAsync("""
                        (() => ({ results: document.querySelectorAll('article').length,
                          paa: document.querySelectorAll('section[aria-label="You Might Also Ask"] button').length,
                          related: document.querySelectorAll('section[aria-label="Related Searches"] a').length,
                          discoveryError: document.body.innerText.includes('Some discovery suggestions could not load'),
                          feedback: document.querySelectorAll('[data-testid="search-sync-feedback-controls"]').length,
                          corrected: document.body.innerText.includes('Showing results for:') }))()
                        """)).RootElement.Clone();
                    Check(state.GetProperty("results").GetInt32() > 0, "normal results");
                    Check(!state.GetProperty("discoveryError").GetBoolean(), "discovery request succeeded");
                    Check(state.GetProperty("feedback").GetInt32() > 0, "feedback controls");
                    anyPaa |= state.GetProperty("paa").GetInt32() > 0;
                    anyRelated |= state.GetProperty("related").GetInt32() > 0;
                    checks.Add(new { queryIndex = index + 1, state });
                    await core.ExecuteScriptAsync("document.querySelector('section[aria-label=\"You Might Also Ask\"]')?.scrollIntoView({block:'center'})");
                    using var image = File.Create(Path.Combine(output, $"search-{index + 1}.png"));
                    await core.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png, image);
                    if (index == queries.Length - 1)
                    {
                        await core.ExecuteScriptAsync("document.querySelector('section[aria-label=\"Related Searches\"]')?.scrollIntoView({block:'center'})");
                        using var relatedImage = File.Create(Path.Combine(output, "related.png"));
                        await core.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png, relatedImage);
                    }
                }
                Check(anyPaa, "at least one eligible PAA query renders");
                Check(anyRelated, "at least one eligible related query renders");
                core.Navigate(brain.Origin + "/settings/?tab=brain");
                await Wait(async () => (await core.ExecuteScriptAsync("document.body.innerText.includes('Restore unavailable')")) == "true");
                await core.ExecuteScriptAsync("Array.from(document.querySelectorAll('button')).find(button => button.textContent.includes('Restore unavailable'))?.scrollIntoView({block:'center'})");
                using (var image = File.Create(Path.Combine(output, "settings.png")))
                    await core.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png, image);
                var offline = JsonDocument.Parse(await brain.Client.GetStringAsync(brain.Origin + "/desktop/offline-check"));
                Check(offline.RootElement.GetProperty("external_connections_blocked").GetBoolean(), "offline boundary");
                var disabled = await brain.Client.PostAsync(brain.Origin + "/api/sync/restore", null);
                Check((int)disabled.StatusCode == 409, "restore fails closed");
                checks.Add(new { offlineBoundary = true, restoreDisabled = true, actualWpfWebView2 = true });
                code = 0;
            }
            catch (Exception error)
            {
                checks.Add(new { error = error.Message });
            }
            finally
            {
                enginePid ??= window.AcceptanceBrain?.ProcessId;
                await window.AcceptanceStopAsync();
                var orphan = false;
                if (enginePid is int pid)
                {
                    try { using var process = Process.GetProcessById(pid); orphan = !process.HasExited; }
                    catch (ArgumentException) { }
                }
                if (orphan) code = 1;
                checks.Add(new { engineExited = !orphan });
                File.WriteAllText(Path.Combine(output, "ui-acceptance.json"), JsonSerializer.Serialize(new { passed = code == 0, checks }, new JsonSerializerOptions { WriteIndented = true }));
                window.Close();
            }
        };
        app.Run(window);
        return code;
    }

    private static void Check(bool condition, string label)
    {
        if (!condition) throw new InvalidOperationException(label);
    }

    private static async Task Wait(Func<Task<bool>> ready, int seconds = 120)
    {
        var deadline = DateTime.UtcNow.AddSeconds(seconds);
        while (DateTime.UtcNow < deadline)
        {
            try { if (await ready()) return; } catch (InvalidOperationException) { }
            await Task.Delay(200);
        }
        throw new TimeoutException("Desktop acceptance did not reach its expected UI state.");
    }
}
