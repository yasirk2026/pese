using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.Wpf;
using Microsoft.Win32;

namespace ManiacSoftwares.PESE;

internal enum ButtonKind
{
    Primary,
    Secondary,
    Tertiary
}

internal sealed class MainWindow : Window
{
    private readonly ContentControl surface = new();
    private readonly CancellationTokenSource lifetime = new();
    private BrainProcess? brain;
    private WebView2? browser;
    private bool closing, canClose;
    private string? selected;
    private readonly System.Windows.Threading.DispatcherTimer monitor = new() { Interval = TimeSpan.FromSeconds(2) };
    private bool isFullscreen;
    private WindowState previousWindowState = WindowState.Normal;
    private WindowStyle previousWindowStyle = WindowStyle.SingleBorderWindow;
    private ResizeMode previousResizeMode = ResizeMode.CanResize;
    private Velopack.UpdateInfo? pendingUpdate;
    private readonly bool acceptanceMode;
    internal CoreWebView2? AcceptanceCore => browser?.CoreWebView2;
    internal BrainProcess? AcceptanceBrain => brain;

    private static readonly Color DarkBase = Color.FromRgb(9, 13, 22);
    private static readonly Color CardBg = Color.FromRgb(17, 24, 39);
    private static readonly Color AccentBlue = Color.FromRgb(37, 99, 235);
    private static readonly Color ButtonSecBg = Color.FromRgb(22, 32, 50);
    private static readonly Brush Ink = new SolidColorBrush(Color.FromRgb(241, 245, 249));
    private static readonly Brush MutedInk = new SolidColorBrush(Color.FromRgb(148, 163, 184));
    private static readonly Brush SubduedInk = new SolidColorBrush(Color.FromRgb(100, 116, 139));
    private static readonly Brush CardBorder = new SolidColorBrush(Color.FromArgb(24, 255, 255, 255));

    private static readonly ControlTemplate ButtonTemplate8 = CreateButtonTemplate(new CornerRadius(8));

    public MainWindow(string? acceptanceBrain = null)
    {
        acceptanceMode = acceptanceBrain is not null;
        var workArea = SystemParameters.WorkArea;
        Title = "PESE — Personal Knowledge Engine";
        Width = Math.Min(1240, workArea.Width); Height = Math.Min(820, workArea.Height);
        MinWidth = Math.Min(850, Width); MinHeight = Math.Min(620, Height);
        WindowStartupLocation = WindowStartupLocation.CenterScreen;
        Background = new SolidColorBrush(DarkBase); Foreground = Ink;
        surface.Background = Background;
        FontFamily = new FontFamily("Segoe UI Variable, Segoe UI, -apple-system, sans-serif"); Content = surface;
        var icoFile = System.IO.Path.Combine(Paths.Install, "pese.ico");
        if (File.Exists(icoFile))
        {
            try { Icon = new System.Windows.Media.Imaging.BitmapImage(new Uri(icoFile)); } catch { }
        }
        PreviewKeyDown += (sender, e) =>
        {
            if (e.Key == System.Windows.Input.Key.F11)
            {
                ToggleFullscreen();
                e.Handled = true;
            }
            else if (e.Key == System.Windows.Input.Key.Escape && isFullscreen)
            {
                ToggleFullscreen();
                e.Handled = true;
            }
        };
        Closing += OnClosing;
        Loaded += async (_, _) =>
        {
            if (acceptanceBrain is null) await BootAsync();
            else await OpenAsync(acceptanceBrain);
        };
        monitor.Tick += async (_, _) =>
        {
            if (brain is not null && !brain.Running && !closing)
            {
                monitor.Stop(); await StopBrainAsync();
                Error("Your Brain stopped unexpectedly", "Restart PESE to reconnect. Your documents remain safely stored in your selected Brain folder.");
            }
        };
    }

    private static ControlTemplate CreateButtonTemplate(CornerRadius radius)
    {
        var template = new ControlTemplate(typeof(System.Windows.Controls.Button));
        var borderFactory = new FrameworkElementFactory(typeof(Border));
        borderFactory.Name = "btnBorder";
        borderFactory.SetBinding(Border.BackgroundProperty, new System.Windows.Data.Binding("Background") { RelativeSource = new System.Windows.Data.RelativeSource(System.Windows.Data.RelativeSourceMode.TemplatedParent) });
        borderFactory.SetBinding(Border.BorderBrushProperty, new System.Windows.Data.Binding("BorderBrush") { RelativeSource = new System.Windows.Data.RelativeSource(System.Windows.Data.RelativeSourceMode.TemplatedParent) });
        borderFactory.SetBinding(Border.BorderThicknessProperty, new System.Windows.Data.Binding("BorderThickness") { RelativeSource = new System.Windows.Data.RelativeSource(System.Windows.Data.RelativeSourceMode.TemplatedParent) });
        borderFactory.SetValue(Border.CornerRadiusProperty, radius);

        var contentPresenter = new FrameworkElementFactory(typeof(ContentPresenter));
        contentPresenter.SetValue(ContentPresenter.HorizontalAlignmentProperty, HorizontalAlignment.Center);
        contentPresenter.SetValue(ContentPresenter.VerticalAlignmentProperty, VerticalAlignment.Center);
        borderFactory.AppendChild(contentPresenter);

        template.VisualTree = borderFactory;

        var triggerOver = new Trigger { Property = System.Windows.Controls.Button.IsMouseOverProperty, Value = true };
        triggerOver.Setters.Add(new Setter(UIElement.OpacityProperty, 0.90));
        template.Triggers.Add(triggerOver);

        var triggerPressed = new Trigger { Property = System.Windows.Controls.Button.IsPressedProperty, Value = true };
        triggerPressed.Setters.Add(new Setter(UIElement.OpacityProperty, 0.75));
        template.Triggers.Add(triggerPressed);

        return template;
    }

    private static UIElement CreatePeseLogoMark(double size = 32)
    {
        var canvas = new Canvas { Width = size, Height = size, Margin = new Thickness(0, 0, 10, 0) };
        var s = size / 32.0;

        // Top facet
        var top = new System.Windows.Shapes.Polygon
        {
            Fill = new SolidColorBrush(Color.FromRgb(59, 130, 246)),
            Stroke = new SolidColorBrush(Color.FromRgb(147, 197, 253)),
            StrokeThickness = 0.8,
            Points = new PointCollection { new Point(16 * s, 3 * s), new Point(27 * s, 9.5 * s), new Point(16 * s, 16 * s), new Point(5 * s, 9.5 * s) }
        };
        // Left facet
        var left = new System.Windows.Shapes.Polygon
        {
            Fill = new SolidColorBrush(Color.FromRgb(37, 99, 235)),
            Stroke = new SolidColorBrush(Color.FromRgb(96, 165, 250)),
            StrokeThickness = 0.8,
            Points = new PointCollection { new Point(5 * s, 9.5 * s), new Point(16 * s, 16 * s), new Point(16 * s, 29 * s), new Point(5 * s, 22.5 * s) }
        };
        // Right facet
        var right = new System.Windows.Shapes.Polygon
        {
            Fill = new SolidColorBrush(Color.FromRgb(29, 78, 216)),
            Stroke = new SolidColorBrush(Color.FromRgb(59, 130, 246)),
            StrokeThickness = 0.8,
            Points = new PointCollection { new Point(16 * s, 16 * s), new Point(27 * s, 9.5 * s), new Point(27 * s, 22.5 * s), new Point(16 * s, 29 * s) }
        };
        // Focal node
        var node = new System.Windows.Shapes.Ellipse
        {
            Width = 4.4 * s,
            Height = 4.4 * s,
            Fill = Brushes.White
        };
        Canvas.SetLeft(node, (16 - 2.2) * s);
        Canvas.SetTop(node, (15.8 - 2.2) * s);

        canvas.Children.Add(top);
        canvas.Children.Add(left);
        canvas.Children.Add(right);
        canvas.Children.Add(node);
        return canvas;
    }

    private StackPanel Card(string title, string text, string? subtitle = null)
    {
        var outerGrid = new Grid
        {
            VerticalAlignment = VerticalAlignment.Center,
            HorizontalAlignment = HorizontalAlignment.Center,
            Margin = new Thickness(24)
        };

        var container = new Border
        {
            Background = new SolidColorBrush(CardBg),
            BorderBrush = CardBorder,
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(16),
            MaxWidth = 540,
            Padding = new Thickness(36, 32, 36, 32)
        };

        var panel = new StackPanel();

        // Top Brand Header
        var brandHeader = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 0, 0, 20) };
        brandHeader.Children.Add(CreatePeseLogoMark(26));
        brandHeader.Children.Add(new TextBlock
        {
            Text = "PESE",
            FontSize = 16,
            FontWeight = FontWeights.Bold,
            Foreground = Ink,
            VerticalAlignment = VerticalAlignment.Center
        });
        brandHeader.Children.Add(new TextBlock
        {
            Text = "0.1.0-alpha.4",
            FontSize = 11,
            FontFamily = new FontFamily("Consolas, Segoe UI"),
            Foreground = SubduedInk,
            VerticalAlignment = VerticalAlignment.Center,
            Margin = new Thickness(8, 0, 0, 0)
        });
        panel.Children.Add(brandHeader);

        // Title
        panel.Children.Add(new TextBlock
        {
            Text = title,
            FontSize = 24,
            FontWeight = FontWeights.SemiBold,
            Foreground = Ink,
            TextWrapping = TextWrapping.Wrap,
            Margin = new Thickness(0, 0, 0, 8)
        });

        // Text
        panel.Children.Add(new TextBlock
        {
            Text = text,
            FontSize = 14,
            Foreground = MutedInk,
            TextWrapping = TextWrapping.Wrap,
            LineHeight = 22,
            Margin = new Thickness(0, 0, 0, subtitle is null ? 20 : 6)
        });

        if (subtitle is not null)
        {
            panel.Children.Add(new TextBlock
            {
                Text = subtitle,
                FontSize = 13,
                Foreground = SubduedInk,
                TextWrapping = TextWrapping.Wrap,
                LineHeight = 20,
                Margin = new Thickness(0, 0, 0, 20)
            });
        }

        container.Child = panel;
        outerGrid.Children.Add(container);
        surface.Content = outerGrid;
        return panel;
    }

    private void AddButton(StackPanel panel, string title, Func<Task> action, ButtonKind kind = ButtonKind.Secondary)
    {
        var button = new System.Windows.Controls.Button
        {
            Content = title,
            Template = ButtonTemplate8,
            FontSize = 14,
            Cursor = System.Windows.Input.Cursors.Hand,
            Margin = new Thickness(0, 4, 0, 4)
        };

        if (kind == ButtonKind.Primary)
        {
            button.Background = new SolidColorBrush(AccentBlue);
            button.Foreground = Brushes.White;
            button.BorderBrush = Brushes.Transparent;
            button.BorderThickness = new Thickness(0);
            button.FontWeight = FontWeights.SemiBold;
            button.Padding = new Thickness(18, 11, 18, 11);
        }
        else if (kind == ButtonKind.Secondary)
        {
            button.Background = new SolidColorBrush(ButtonSecBg);
            button.Foreground = Ink;
            button.BorderBrush = CardBorder;
            button.BorderThickness = new Thickness(1);
            button.FontWeight = FontWeights.Medium;
            button.Padding = new Thickness(18, 10, 18, 10);
        }
        else // Tertiary (Understated / non-destructive)
        {
            button.Background = Brushes.Transparent;
            button.Foreground = MutedInk;
            button.BorderBrush = Brushes.Transparent;
            button.BorderThickness = new Thickness(0);
            button.FontWeight = FontWeights.Normal;
            button.Padding = new Thickness(14, 8, 14, 8);
            button.HorizontalAlignment = HorizontalAlignment.Center;
            button.Margin = new Thickness(0, 8, 0, 0);
        }

        button.Click += async (_, _) =>
        {
            button.IsEnabled = false;
            try { await action(); }
            catch (Exception exc) { Error("Your Brain needs attention", exc.Message); }
            finally { button.IsEnabled = true; }
        };
        panel.Children.Add(button);
    }

    private Task Done(Action action) { action(); return Task.CompletedTask; }

    private async Task BootAsync()
    {
        try
        {
            selected = Paths.LoadBrain();
            if (selected is null) { Welcome(); return; }
            if (!Directory.Exists(selected)) { Recovery(); return; }
            await OpenAsync(selected);
        }
        catch (Exception exc) { Error("Your Brain needs attention", exc.Message); }
    }

    internal void ShowWelcomeForCapture() => Welcome();
    internal void ShowRecoveryForCapture(string path) { selected = path; Recovery(); }

    private void Welcome()
    {
        var panel = Card("Welcome to PESE", "Your personal search and knowledge Brain, running privately on your computer.");
        AddButton(panel, "Get Started", () => Done(ChooseMode), ButtonKind.Primary);
        AddButton(panel, "Locate Existing Brain", LocateAsync, ButtonKind.Secondary);
    }

    private void ChooseMode()
    {
        var panel = Card("Choose how PESE stores your Brain", "Local Mode\nStore your notes, documents, learning signals, and search memory privately on this computer or an external drive.");
        AddButton(panel, "Continue with Local", () => Done(Location), ButtonKind.Primary);
    }

    private void Location()
    {
        var panel = Card("Where should PESE store your Brain?", "Your Brain stays completely separate from the application files and safely survives uninstalling or updating PESE.");

        var locBox = new Border
        {
            Background = new SolidColorBrush(Color.FromRgb(15, 23, 42)),
            BorderBrush = CardBorder,
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(8),
            Padding = new Thickness(12, 10, 12, 10),
            Margin = new Thickness(0, 4, 0, 18)
        };
        var boxStack = new StackPanel();
        boxStack.Children.Add(new TextBlock
        {
            Text = "RECOMMENDED FOLDER",
            FontSize = 10,
            FontFamily = new FontFamily("Consolas, Segoe UI"),
            FontWeight = FontWeights.SemiBold,
            Foreground = SubduedInk,
            Margin = new Thickness(0, 0, 0, 4)
        });
        boxStack.Children.Add(new TextBlock
        {
            Text = Paths.Recommended,
            FontSize = 12,
            FontFamily = new FontFamily("Consolas, Segoe UI"),
            Foreground = Ink,
            TextTrimming = TextTrimming.CharacterEllipsis
        });
        locBox.Child = boxStack;
        panel.Children.Insert(2, locBox);

        AddButton(panel, "Use Recommended Location", () => ExamineAsync(Paths.Recommended, false), ButtonKind.Primary);
        AddButton(panel, "Choose Another Folder", async () =>
        {
            var path = PickFolder("Choose a folder for your PESE Brain");
            if (path is not null) await ExamineAsync(path, false);
        }, ButtonKind.Secondary);
        AddButton(panel, "Locate Existing Brain", LocateAsync, ButtonKind.Tertiary);
    }

    private string? PickFolder(string title)
    {
        var dialog = new OpenFolderDialog { Title = title, Multiselect = false };
        return dialog.ShowDialog(this) == true ? dialog.FolderName : null;
    }

    private async Task LocateAsync()
    {
        var path = PickFolder("Locate Existing PESE Brain — select the folder containing pese-brain.json");
        if (path is not null) await ExamineAsync(path, true);
    }

    private async Task ExamineAsync(string path, bool existingOnly)
    {
        selected = path;
        if (File.Exists(System.IO.Path.Combine(path, "pese-brain.json")))
        {
            Card("Checking your Brain…", path);
            var result = await BrainProcess.CommandAsync("inspect", path);
            var info = result.GetProperty("brain");
            var panel = Card("PESE Brain found", $"{info.GetProperty("document_count").GetInt32()} notes · Brain ID {info.GetProperty("brain_id").GetString()}");

            var locBox = CreatePathBox(path);
            panel.Children.Insert(2, locBox);

            AddButton(panel, "Use This Brain", async () => { await BrainProcess.CommandAsync("connect", path); await OpenAsync(path); }, ButtonKind.Primary);
            AddButton(panel, "Choose Another Folder", () => Done(Location), ButtonKind.Secondary);
        }
        else if (existingOnly)
            Error("This is not a PESE Brain", "Choose the folder that contains pese-brain.json. No files have been changed.");
        else if (Directory.Exists(path) && Directory.EnumerateFileSystemEntries(path).Any())
        {
            var panel = Card("This folder already contains files", "PESE will not overwrite existing data. Create a new PESE Brain subfolder or choose an empty directory.");
            AddButton(panel, "Use a PESE Brain Subfolder", () => ExamineAsync(System.IO.Path.Combine(path, "PESE Brain"), false), ButtonKind.Primary);
            AddButton(panel, "Choose Another Folder", () => Done(Location), ButtonKind.Secondary);
        }
        else
        {
            var panel = Card("Create your Local Brain", "PESE will initialize a new private Brain here with its own identity. Starter knowledge examples will appear when it first opens.");
            var locBox = CreatePathBox(path);
            panel.Children.Insert(2, locBox);

            AddButton(panel, "Create PESE Brain Here", async () =>
            {
                Card("Creating your Brain…", path);
                try { await BrainProcess.CommandAsync("create", path); await OpenAsync(path); }
                catch (Exception exc) { Error("Your Brain could not be created", exc.Message); }
            }, ButtonKind.Primary);
            AddButton(panel, "Choose Another Folder", () => Done(Location), ButtonKind.Secondary);
        }
    }

    private static Border CreatePathBox(string path)
    {
        var border = new Border
        {
            Background = new SolidColorBrush(Color.FromRgb(15, 23, 42)),
            BorderBrush = CardBorder,
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(8),
            Padding = new Thickness(12, 10, 12, 10),
            Margin = new Thickness(0, 4, 0, 18)
        };
        var stack = new StackPanel();
        stack.Children.Add(new TextBlock
        {
            Text = "FOLDER LOCATION",
            FontSize = 10,
            FontFamily = new FontFamily("Consolas, Segoe UI"),
            FontWeight = FontWeights.SemiBold,
            Foreground = SubduedInk,
            Margin = new Thickness(0, 0, 0, 4)
        });
        stack.Children.Add(new TextBlock
        {
            Text = path,
            FontSize = 12,
            FontFamily = new FontFamily("Consolas, Segoe UI"),
            Foreground = Ink,
            TextTrimming = TextTrimming.CharacterEllipsis
        });
        border.Child = stack;
        return border;
    }

    /// <summary>
    /// Requirement 5: Polished redesign of the Brain recovery screen.
    /// Hierarchy:
    ///   - PESE identity / mark
    ///   - "Brain unavailable"
    ///   - Friendly explanation: "PESE can't currently reach your Brain."
    ///   - Secondary explanation: "The drive may be disconnected or its location may have changed."
    ///   - Compact details area showing expected location subtly
    ///   - Actions hierarchy: Primary: Locate Brain, Secondary: Try Again, Tertiary: Create New Brain
    /// </summary>
    private void Recovery()
    {
        var panel = Card(
            "Brain unavailable",
            "PESE can't currently reach your Brain.",
            "The drive may be disconnected or its location may have changed."
        );

        // Compact details area showing expected location subtly
        var detailsBox = new Border
        {
            Background = new SolidColorBrush(Color.FromRgb(15, 23, 42)),
            BorderBrush = CardBorder,
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(8),
            Padding = new Thickness(12, 10, 12, 10),
            Margin = new Thickness(0, 0, 0, 20)
        };
        var detailsStack = new StackPanel();
        detailsStack.Children.Add(new TextBlock
        {
            Text = "EXPECTED LOCATION",
            FontSize = 10,
            FontFamily = new FontFamily("Consolas, Segoe UI"),
            FontWeight = FontWeights.SemiBold,
            Foreground = SubduedInk,
            Margin = new Thickness(0, 0, 0, 4)
        });
        detailsStack.Children.Add(new TextBlock
        {
            Text = selected ?? "Unknown path",
            FontSize = 12,
            FontFamily = new FontFamily("Consolas, Segoe UI"),
            Foreground = new SolidColorBrush(Color.FromRgb(203, 213, 225)),
            TextTrimming = TextTrimming.CharacterEllipsis
        });
        detailsBox.Child = detailsStack;
        panel.Children.Insert(3, detailsBox);

        // Action hierarchy
        // Primary: Locate Brain
        AddButton(panel, "Locate Brain", LocateAsync, ButtonKind.Primary);
        // Secondary: Try Again
        AddButton(panel, "Try Again", BootAsync, ButtonKind.Secondary);
        // Tertiary: Create New Brain (Understated so user never accidentally replaces active Brain)
        AddButton(panel, "Create New Brain", () => Done(Location), ButtonKind.Tertiary);
    }

    private void Error(string title, string message)
    {
        Log.Write("native_recovery");
        var panel = Card(title, message);
        AddButton(panel, "Try Again", BootAsync, ButtonKind.Primary);
        AddButton(panel, "Locate Existing Brain", LocateAsync, ButtonKind.Secondary);
        AddButton(panel, "Create New Brain", () => Done(Location), ButtonKind.Tertiary);

        var prerequisite = System.IO.Path.Combine(Paths.Install, "prerequisites", "VC_redist.x64.exe");
        if (File.Exists(prerequisite))
            AddButton(panel, "Repair Microsoft VC++ Runtime", () => Done(() =>
                Process.Start(new ProcessStartInfo(prerequisite) { UseShellExecute = true })), ButtonKind.Secondary);

        AddButton(panel, "Open Logs Folder", () => Done(() =>
        {
            var logs = System.IO.Path.Combine(Paths.Profile, "Logs"); Directory.CreateDirectory(logs);
            Process.Start(new ProcessStartInfo("explorer.exe", logs) { UseShellExecute = true });
        }), ButtonKind.Tertiary);
    }

    private async Task OpenAsync(string path)
    {
        if (closing) return;
        Card("Waking up your Brain…", "Loading your notes and preparing neural search indices.");
        try
        {
            // Detect the real installed Evergreen runtime before starting the engine.
            _ = CoreWebView2Environment.GetAvailableBrowserVersionString();
            await BrainProcess.CommandAsync("inspect", path);
            lifetime.Token.ThrowIfCancellationRequested();
            brain = new BrainProcess();
            await brain.StartAsync(path, lifetime.Token);
            lifetime.Token.ThrowIfCancellationRequested();
            Card("Opening PESE…", "Your Brain is ready.");
            browser = new WebView2();

            // Requirement 4: Brain management is in Settings -> Brain.
            // Remove raw top toolbar; WebView2 occupies the entire clean window surface.
            surface.Content = browser;

            var env = await CoreWebView2Environment.CreateAsync(null, System.IO.Path.Combine(Paths.Profile, "WebView2"));
            await browser.EnsureCoreWebView2Async(env);
            lifetime.Token.ThrowIfCancellationRequested();
            var core = browser.CoreWebView2;
            try { await core.Profile.ClearBrowsingDataAsync(CoreWebView2BrowsingDataKinds.DiskCache); } catch { }
            core.Settings.AreHostObjectsAllowed = false;
            // Enable web message so Settings -> Brain can trigger Change Brain / Locate Brain
            core.Settings.IsWebMessageEnabled = true;
            core.Settings.IsStatusBarEnabled = false;
            core.Settings.AreDefaultContextMenusEnabled = false;
#if !DEBUG
            core.Settings.AreDevToolsEnabled = false;
            core.Settings.AreBrowserAcceleratorKeysEnabled = false;
#endif
            var origin = brain.Origin!;
            var config = JsonSerializer.Serialize(new { apiBase = origin, token = brain.Token, desktop = true, brainPath = path, version = "0.1.0-alpha.4" });
            // Direct runtime configuration injection and desktop keyboard handlers
            await core.AddScriptToExecuteOnDocumentCreatedAsync(
                "try { " +
                $"  window.__PESE_CONFIG__ = {config}; " +
                "} catch (e) { console.error('Failed to set __PESE_CONFIG__', e); } " +
                "window.addEventListener('keydown', function(e) { " +
                "  if (e.key === 'F11') { e.preventDefault(); window.chrome?.webview?.postMessage('toggle_fullscreen'); } " +
                "  else if (e.key === 'Escape') { window.chrome?.webview?.postMessage('exit_fullscreen'); } " +
                "});");

            core.WebMessageReceived += async (_, e) =>
            {
                try
                {
                    var msg = e.TryGetWebMessageAsString();
                    if (msg == "change_brain" || msg == "new_brain")
                    {
                        await StopBrainAsync();
                        Location();
                    }
                    else if (msg == "locate_brain")
                    {
                        await StopBrainAsync();
                        await LocateAsync();
                    }
                    else if (msg == "toggle_fullscreen")
                    {
                        ToggleFullscreen();
                    }
                    else if (msg == "exit_fullscreen" && isFullscreen)
                    {
                        ToggleFullscreen();
                    }
                    else if (msg == "check_updates")
                    {
                        _ = Task.Run(async () => await CheckForUpdatesAsync(core));
                    }
                    else if (msg == "download_update")
                    {
                        _ = Task.Run(async () => await DownloadUpdateAsync(core));
                    }
                    else if (msg == "install_update")
                    {
                        _ = Task.Run(async () => await ApplyUpdateAndRestartAsync(core));
                    }
                }
                catch { }
            };

            core.NavigationStarting += (_, e) =>
            {
                if (!Internal(e.Uri, origin)) { e.Cancel = true; OpenExternal(e.Uri); }
            };
            core.FrameNavigationStarting += (_, e) => e.Cancel = true;
            core.NewWindowRequested += (_, e) => { e.Handled = true; OpenExternal(e.Uri); };
            core.DownloadStarting += (_, e) => e.Cancel = true;
            core.AddWebResourceRequestedFilter("*", CoreWebView2WebResourceContext.All);
            core.WebResourceRequested += (_, e) =>
            {
                if (!Internal(e.Request.Uri, origin) && !e.Request.Uri.StartsWith("data:") && !e.Request.Uri.StartsWith("blob:"))
                    e.Response = env.CreateWebResourceResponse(Stream.Null, 403, "Local Brain is offline", "Content-Type: text/plain");
            };
            core.PermissionRequested += (_, e) => e.State = CoreWebView2PermissionState.Deny;
            core.ProcessFailed += async (_, _) =>
            {
                await StopBrainAsync(); Error("The PESE interface stopped", "Restart PESE to reopen your Brain.");
            };
            core.Navigate(origin + "/");
            monitor.Start();
            _ = Task.Run(async () =>
            {
                await Task.Delay(3000);
                if (!acceptanceMode) await CheckForUpdatesAsync(core);
            });
        }
        catch (WebView2RuntimeNotFoundException)
        {
            await StopBrainAsync();
            var panel = Card("Microsoft Edge WebView2 Runtime is required", "Install the Microsoft WebView2 Evergreen Runtime, then reopen PESE. For offline computers, use Microsoft's standalone x64 installer. Your Brain is preserved.");
            AddButton(panel, "Open Microsoft WebView2 Download", () => Done(() => OpenExternal("https://developer.microsoft.com/microsoft-edge/webview2/#download-section")), ButtonKind.Primary);
            AddButton(panel, "Try Again", BootAsync, ButtonKind.Secondary);
        }
        catch (OperationCanceledException) when (closing) { }
        catch (Exception exc)
        {
            await StopBrainAsync();
            Error("PESE could not open your Brain", exc is OperationCanceledException
                ? "Startup timed out. Check that your Brain drive is available and the installation is complete, then try again." : exc.Message);
        }
    }

    public void ToggleFullscreen()
    {
        if (!isFullscreen)
        {
            previousWindowState = WindowState;
            previousWindowStyle = WindowStyle;
            previousResizeMode = ResizeMode;

            WindowStyle = WindowStyle.None;
            ResizeMode = ResizeMode.NoResize;
            if (WindowState == WindowState.Maximized)
            {
                WindowState = WindowState.Normal;
            }
            WindowState = WindowState.Maximized;
            isFullscreen = true;
        }
        else
        {
            WindowStyle = previousWindowStyle;
            ResizeMode = previousResizeMode;
            WindowState = previousWindowState;
            isFullscreen = false;
        }
    }

    private async Task CheckForUpdatesAsync(CoreWebView2 core)
    {
        try
        {
            await Dispatcher.InvokeAsync(() =>
                core.PostWebMessageAsJson(JsonSerializer.Serialize(new { type = "update_status", status = "checking" })));

            var app = Velopack.VelopackApp.Build();
            var githubSource = new Velopack.Sources.GithubSource("https://github.com/yasirk2026/pese", null, false);
            var feedDir = System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "ManiacSoftwares.PESE", "packages");
            var devPkgDir = System.IO.Path.Combine(Paths.Install, "..", "..", "dist", "windows", "0.1.0-alpha.4", "packages");

            Velopack.UpdateManager updateManager;
            if (Directory.Exists(feedDir))
            {
                updateManager = new Velopack.UpdateManager(feedDir);
            }
            else if (Directory.Exists(devPkgDir))
            {
                updateManager = new Velopack.UpdateManager(devPkgDir);
            }
            else
            {
                updateManager = new Velopack.UpdateManager(githubSource);
            }

            pendingUpdate = await updateManager.CheckForUpdatesAsync();
            if (pendingUpdate != null)
            {
                var target = pendingUpdate.TargetFullRelease.Version.ToString();
                await Dispatcher.InvokeAsync(() =>
                    core.PostWebMessageAsJson(JsonSerializer.Serialize(new
                    {
                        type = "update_status",
                        status = "available",
                        currentVersion = updateManager.CurrentVersion?.ToString() ?? "0.1.0-alpha.4",
                        targetVersion = target
                    })));
            }
            else
            {
                await Dispatcher.InvokeAsync(() =>
                    core.PostWebMessageAsJson(JsonSerializer.Serialize(new
                    {
                        type = "update_status",
                        status = "up_to_date",
                        currentVersion = updateManager.CurrentVersion?.ToString() ?? "0.1.0-alpha.4"
                    })));
            }
        }
        catch (Exception exc)
        {
            Log.WriteDiagnostic("update_check_failed", exc.Message);
            await Dispatcher.InvokeAsync(() =>
                core.PostWebMessageAsJson(JsonSerializer.Serialize(new
                {
                    type = "update_status",
                    status = "failed",
                    error = "Could not reach update server. You are running offline or the release feed is unavailable."
                })));
        }
    }

    private async Task DownloadUpdateAsync(CoreWebView2 core)
    {
        try
        {
            if (pendingUpdate == null) return;
            var githubSource = new Velopack.Sources.GithubSource("https://github.com/yasirk2026/pese", null, false);
            var feedDir = System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "ManiacSoftwares.PESE", "packages");
            var devPkgDir = System.IO.Path.Combine(Paths.Install, "..", "..", "dist", "windows", "0.1.0-alpha.4", "packages");
            var updateManager = Directory.Exists(feedDir) ? new Velopack.UpdateManager(feedDir) :
                                Directory.Exists(devPkgDir) ? new Velopack.UpdateManager(devPkgDir) :
                                new Velopack.UpdateManager(githubSource);

            await updateManager.DownloadUpdatesAsync(pendingUpdate, progress =>
            {
                Dispatcher.Invoke(() =>
                    core.PostWebMessageAsJson(JsonSerializer.Serialize(new
                    {
                        type = "update_status",
                        status = "downloading",
                        progress
                    })));
            });

            await Dispatcher.InvokeAsync(() =>
                core.PostWebMessageAsJson(JsonSerializer.Serialize(new
                {
                    type = "update_status",
                    status = "ready",
                    progress = 100
                })));
        }
        catch (Exception exc)
        {
            Log.WriteDiagnostic("update_download_failed", exc.Message);
            await Dispatcher.InvokeAsync(() =>
                core.PostWebMessageAsJson(JsonSerializer.Serialize(new
                {
                    type = "update_status",
                    status = "failed",
                    error = "Download failed: " + exc.Message
                })));
        }
    }

    private async Task ApplyUpdateAndRestartAsync(CoreWebView2 core)
    {
        try
        {
            if (pendingUpdate == null) return;
            await Dispatcher.InvokeAsync(() =>
                core.PostWebMessageAsJson(JsonSerializer.Serialize(new
                {
                    type = "update_status",
                    status = "installing"
                })));

            await StopBrainAsync();

            var githubSource = new Velopack.Sources.GithubSource("https://github.com/yasirk2026/pese", null, false);
            var feedDir = System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "ManiacSoftwares.PESE", "packages");
            var devPkgDir = System.IO.Path.Combine(Paths.Install, "..", "..", "dist", "windows", "0.1.0-alpha.4", "packages");
            var updateManager = Directory.Exists(feedDir) ? new Velopack.UpdateManager(feedDir) :
                                Directory.Exists(devPkgDir) ? new Velopack.UpdateManager(devPkgDir) :
                                new Velopack.UpdateManager(githubSource);

            updateManager.ApplyUpdatesAndRestart(pendingUpdate);
        }
        catch (Exception exc)
        {
            Log.WriteDiagnostic("update_install_failed", exc.Message);
            await Dispatcher.InvokeAsync(() =>
                core.PostWebMessageAsJson(JsonSerializer.Serialize(new
                {
                    type = "update_status",
                    status = "failed",
                    error = "Install failed: " + exc.Message
                })));
        }
    }

    internal static bool Internal(string url, string origin)
    {
        if (Uri.TryCreate(url, UriKind.Absolute, out var uri))
            return uri.GetLeftPart(UriPartial.Authority) == origin;
        return true;
    }

    private static void OpenExternal(string url)
    {
        if (!Uri.TryCreate(url, UriKind.Absolute, out var uri) || uri.Scheme is not ("https" or "http" or "mailto")) return;
        try { Process.Start(new ProcessStartInfo(uri.AbsoluteUri) { UseShellExecute = true }); } catch { Log.Write("external_link_failed"); }
    }

    private async Task StopBrainAsync()
    {
        monitor.Stop(); browser?.Dispose(); browser = null;
        var previous = brain; brain = null;
        if (previous is not null) await previous.DisposeAsync();
    }

    internal Task AcceptanceStopAsync() => StopBrainAsync();

    private async void OnClosing(object? sender, CancelEventArgs args)
    {
        if (canClose) return;
        args.Cancel = true;
        if (closing) return;
        closing = true; lifetime.Cancel();
        Card("Closing PESE…", "Finishing your Brain session.");
        await StopBrainAsync(); canClose = true;
        _ = Dispatcher.BeginInvoke(new Action(Close));
    }
}
