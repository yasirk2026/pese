using System.IO;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Imaging;

namespace ManiacSoftwares.PESE;

internal sealed class TrainingAgreementDialog : Window
{
    internal static string? TestDecision;
    internal static string? TestCapture;
    internal string[] ExcludedIds => choices.Where(c => c.IsChecked != true).Select(c => (string)c.Tag).ToArray();
    private readonly List<CheckBox> choices = new();

    internal TrainingAgreementDialog(JsonElement prepared)
    {
        Title = "PESE training update — Privacy agreement";
        Width = Math.Min(1050, SystemParameters.WorkArea.Width); Height = Math.Min(850, SystemParameters.WorkArea.Height);
        WindowStartupLocation = WindowStartupLocation.CenterOwner;
        Background = new SolidColorBrush(Color.FromRgb(9, 13, 22)); Foreground = Brushes.White;
        var grid = new DockPanel { Margin = new Thickness(24) };
        var footer = new StackPanel { Margin = new Thickness(0, 16, 0, 0) };
        DockPanel.SetDock(footer, Dock.Bottom); grid.Children.Add(footer);
        var confirm = new CheckBox { Foreground = Brushes.White, Margin = new Thickness(0, 10, 0, 12),
            Content = new TextBlock { Text = "I accept this training/privacy agreement and confirm that my approved materials contain no prohibited sensitive personal content.", TextWrapping = TextWrapping.Wrap } };
        footer.Children.Add(confirm);
        var buttons = new StackPanel { Orientation = Orientation.Horizontal };
        var accept = new Button { Content = "Accept training update and continue", IsEnabled = false, Padding = new Thickness(16, 10, 16, 10), Margin = new Thickness(0, 0, 16, 0) };
        var decline = new Button { Content = "Decline and close PESE", Padding = new Thickness(16, 10, 16, 10) };
        confirm.Checked += (_, _) => accept.IsEnabled = true;
        confirm.Unchecked += (_, _) => accept.IsEnabled = false;
        accept.Click += (_, _) => DialogResult = true;
        decline.Click += (_, _) => DialogResult = false;
        buttons.Children.Add(accept); buttons.Children.Add(decline); footer.Children.Add(buttons);
        var body = new StackPanel();
        body.Children.Add(new TextBlock { Text = prepared.GetProperty("agreement").GetProperty("title").GetString(), FontSize = 25, FontWeight = FontWeights.Bold, Foreground = Brushes.Orange, TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 16) });
        body.Children.Add(new TextBlock { Text = $"Brain: {prepared.GetProperty("brain").GetProperty("brain_id").GetString()} · {prepared.GetProperty("documents").GetArrayLength()} current documents", FontSize = 14, Margin = new Thickness(0, 0, 0, 14) });
        foreach (var statement in prepared.GetProperty("agreement").GetProperty("statements").EnumerateArray())
            body.Children.Add(new TextBlock { Text = "• " + statement.GetString(), FontSize = 14, TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 10), Foreground = statement.GetString()!.StartsWith("IMPORTANT:") ? Brushes.Orange : Brushes.White });
        body.Children.Add(new TextBlock { Text = "Approve the current collection; uncheck documents to exclude. Future additions require another explicit scope approval. Previously excluded documents stay excluded.", TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 10, 0, 10) });
        var excluded = prepared.GetProperty("excluded_document_ids").EnumerateArray().Select(v => v.GetString()).ToHashSet();
        var list = new ListBox { Height = 180, Background = new SolidColorBrush(Color.FromRgb(17, 24, 39)) };
        foreach (var doc in prepared.GetProperty("documents").EnumerateArray())
        {
            var id = doc.GetProperty("id").GetString()!;
            var choice = new CheckBox { Tag = id, Content = doc.GetProperty("title").GetString(), Foreground = Brushes.White,
                IsChecked = !excluded.Contains(id), IsEnabled = !excluded.Contains(id), Margin = new Thickness(6) };
            choices.Add(choice); list.Items.Add(choice);
        }
        body.Children.Add(list);
        body.Children.Add(new TextBlock { Text = "A verified local snapshot and inactive recovery copy are created before activation. Nothing is uploaded. Neural ranking is separate from a training job; candidates require valid reviewed evidence.", TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 12, 0, 0) });
        grid.Children.Add(new ScrollViewer { Content = body, VerticalScrollBarVisibility = ScrollBarVisibility.Auto });
        Content = grid;
        Loaded += (_, _) =>
        {
            if (TestDecision is null) return;
            UpdateLayout();
            if (TestCapture is not null)
            {
                var bitmap = new RenderTargetBitmap((int)ActualWidth, (int)ActualHeight, 96, 96, PixelFormats.Pbgra32);
                bitmap.Render(this); var encoder = new PngBitmapEncoder(); encoder.Frames.Add(BitmapFrame.Create(bitmap));
                using var image = File.Create(TestCapture); encoder.Save(image);
            }
            Dispatcher.BeginInvoke(new Action(() =>
            {
                if (TestDecision == "accept") { confirm.IsChecked = true; accept.RaiseEvent(new RoutedEventArgs(Button.ClickEvent)); }
                else decline.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            }));
        };
    }
}
