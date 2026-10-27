using System.IO;
using System.Security.Cryptography;
using System.Text.Json;
using System.Windows;

namespace ManiacSoftwares.PESE;

// Actual startup gate, constrained to explicitly marked synthetic fixtures.
internal static class TrainingUpdateAcceptance
{
    internal static int Run(string[] args)
    {
        if (!Paths.RequiresTrainingAgreement || args.Length != 3 || args[2] is not ("accept" or "decline")) return 2;
        var fixture = Path.GetFullPath(args[0]); var output = Path.GetFullPath(args[1]); var decision = args[2];
        if (!File.Exists(Path.Combine(fixture, ".pese-disposable-fixture")) || Directory.Exists(output) ||
            output.StartsWith(fixture + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)) return 2;
        Directory.CreateDirectory(output);
        Paths.AcceptanceProfile = Path.Combine(output, "LocalAppData", "ManiacSoftwares", "PESE");
        Directory.CreateDirectory(Paths.Profile);
        File.WriteAllText(Paths.Settings, JsonSerializer.Serialize(new { brainPath = fixture }));
        var documents = SHA256.HashData(File.ReadAllBytes(Path.Combine(fixture, "firestore_documents.json")));
        var pointer = SHA256.HashData(File.ReadAllBytes(Paths.Settings));
        TrainingAgreementDialog.TestDecision = decision;
        TrainingAgreementDialog.TestCapture = Path.Combine(output, "startup-privacy-agreement.png");
        var app = new Application { ShutdownMode = ShutdownMode.OnMainWindowClose };
        var window = new MainWindow(fixture) { ShowActivated = false, ShowInTaskbar = false, Opacity = .01 };
        var code = 1; JsonElement? status = null; string? error = null;
        window.Closed += (_, _) =>
        {
            var preserved = documents.SequenceEqual(SHA256.HashData(File.ReadAllBytes(Path.Combine(fixture, "firestore_documents.json")))) &&
                pointer.SequenceEqual(SHA256.HashData(File.ReadAllBytes(Paths.Settings)));
            if (decision == "decline" && window.TrainingAgreementDeclined && window.TrainingOnboardingReceipt is null && preserved) code = 0;
            File.WriteAllText(Path.Combine(output, "startup-acceptance.json"), JsonSerializer.Serialize(new {
                passed = code == 0 && preserved, decision, applicationClosed = true,
                packageId = SoftwareUpdates.PackageId, channel = SoftwareUpdates.Channel, version = SoftwareUpdates.Version,
                declinedBeforeEngineStart = window.TrainingAgreementDeclined && window.TrainingOnboardingReceipt is null,
                canonicalAndPointerPreserved = preserved, receipt = window.TrainingOnboardingReceipt, status, error,
                syntheticOnly = true, realOwnerActivated = false
            }, new JsonSerializerOptions { WriteIndented = true }));
        };
        window.Loaded += async (_, _) =>
        {
            try
            {
                var deadline = DateTime.UtcNow.AddSeconds(180);
                while (DateTime.UtcNow < deadline && !window.TrainingAgreementDeclined &&
                       (window.AcceptanceBrain is not { Running: true } || window.AcceptanceCore is null))
                {
                    if (window.AcceptanceError is not null) throw new InvalidOperationException(window.AcceptanceError);
                    await Task.Delay(100);
                }
                if (decision == "decline") {
                    if (!window.TrainingAgreementDeclined) throw new TimeoutException("Decline did not close startup");
                    return;
                }
                var brain = window.AcceptanceBrain ?? throw new InvalidOperationException("No serving engine after consent");
                status = JsonDocument.Parse(await brain.Client.GetStringAsync(brain.Origin + "/api/intelligence/beta/status")).RootElement.Clone();
                var state = status.Value.GetProperty("participation");
                using var docs = JsonDocument.Parse(File.ReadAllText(Path.Combine(fixture, "firestore_documents.json")));
                if (!state.GetProperty("accepted").GetBoolean() || state.GetProperty("feedback_scope").GetArrayLength() != docs.RootElement.EnumerateObject().Count() ||
                    state.GetProperty("retention_days").GetInt32() != 7 || status.Value.GetProperty("privacy").GetProperty("allow_journal_learning").GetBoolean() ||
                    status.Value.GetProperty("training_running").GetBoolean()) throw new InvalidOperationException("Startup consent/scope policy mismatch");
                code = 0;
                await window.AcceptanceStopAsync(); window.Close();
            }
            catch (Exception failure)
            {
                error = failure.Message; await window.AcceptanceStopAsync(); window.Close();
            }
        };
        app.Run(window);
        TrainingAgreementDialog.TestDecision = null; TrainingAgreementDialog.TestCapture = null;
        return code;
    }
}
