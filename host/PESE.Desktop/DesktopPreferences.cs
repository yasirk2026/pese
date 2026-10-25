using System.IO;
using System.Text.Json;

namespace ManiacSoftwares.PESE;

internal sealed record DesktopPreferences(string theme = "dark", bool developerMode = false);

// Independent of the Brain pointer and the engine's per-launch loopback origin.
internal static class DesktopPreferencesStore
{
    internal static string FilePath => Path.Combine(Paths.Profile, "ui-preferences.json");

    internal static DesktopPreferences? Load()
    {
        try
        {
            if (!File.Exists(FilePath)) return null;
            var value = JsonSerializer.Deserialize<DesktopPreferences>(File.ReadAllText(FilePath));
            return value is not null && Valid(value) ? value : null;
        }
        catch { Log.Write("appearance_preferences_unavailable"); return null; }
    }

    private static bool Valid(DesktopPreferences value) => value.theme is "dark" or "light" or "system";

    internal static void Save(string json)
    {
        using var parsed = JsonDocument.Parse(json);
        if (parsed.RootElement.ValueKind != JsonValueKind.Object ||
            parsed.RootElement.EnumerateObject().Any(p => p.Name is not ("theme" or "developerMode")))
            throw new InvalidDataException("Unsupported appearance preference.");
        var value = JsonSerializer.Deserialize<DesktopPreferences>(json) ?? throw new InvalidDataException();
        if (!Valid(value)) throw new InvalidDataException("Unsupported theme.");
        Directory.CreateDirectory(Paths.Profile);
        var temporary = Path.Combine(Paths.Profile, ".ui-preferences-" + Guid.NewGuid().ToString("N") + ".tmp");
        try
        {
            using (var stream = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            {
                JsonSerializer.Serialize(stream, value);
                stream.Flush(true);
            }
            File.Move(temporary, FilePath, true);
        }
        finally { if (File.Exists(temporary)) File.Delete(temporary); }
    }
}
