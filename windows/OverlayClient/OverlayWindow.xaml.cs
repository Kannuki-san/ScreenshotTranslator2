using System;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Interop;
using System.Windows.Media;

namespace OverlayClient;

public partial class OverlayWindow : Window
{
    private HwndSource? _source;
    private readonly AppSettings _settings;

    public OverlayWindow(AppSettings settings)
    {
        _settings = settings;
        InitializeComponent();

        CloseButton.Click += (_, __) => Close();
        CopyButton.Click += (_, __) =>
        {
            if (!string.IsNullOrEmpty(BodyText.Text))
                Clipboard.SetText(BodyText.Text);
        };

        if (!_settings.Overlay.Header.ShowStatus)
            StatusText.Visibility = Visibility.Collapsed;

        CopyButton.Visibility = _settings.Overlay.Header.Buttons.Copy ? Visibility.Visible : Visibility.Collapsed;
        CloseButton.Visibility = _settings.Overlay.Header.Buttons.Close ? Visibility.Visible : Visibility.Collapsed;

        HeaderRow.Height = new GridLength(Math.Max(16, _settings.Overlay.Header.HeightPx));
        Topmost = _settings.Overlay.Topmost;

        var alpha = (byte)Math.Clamp((int)(_settings.Overlay.Appearance.BackgroundOpacity * 255), 0, 255);
        ChromeBorder.Background = new SolidColorBrush(Color.FromArgb(alpha, 0, 0, 0));
        ChromeBorder.CornerRadius = new CornerRadius(_settings.Overlay.Appearance.CornerRadius);

        BodyText.TextWrapping = _settings.Overlay.Text.Wrap ? TextWrapping.Wrap : TextWrapping.NoWrap;
        BodyText.VerticalScrollBarVisibility = _settings.Overlay.Text.VerticalScrollbar switch
        {
            "visible" => ScrollBarVisibility.Visible,
            "hidden" => ScrollBarVisibility.Hidden,
            _ => ScrollBarVisibility.Auto
        };
        BodyText.FontSize = Math.Max(10, _settings.Overlay.Text.FontSize);

        if (_settings.Overlay.Interaction.CloseOnEsc)
        {
            PreviewKeyDown += (_, e) =>
            {
                if (e.Key == System.Windows.Input.Key.Escape) Close();
            };
        }

        SourceInitialized += (_, __) => AttachHook();
    }

    public void SetContent(string status, string text)
    {
        StatusText.Text = status ?? "";
        BodyText.Text = text ?? "";
    }

    private void AttachHook()
    {
        if (_settings.Overlay.Interaction.PartialClickthrough)
        {
            _source = (HwndSource)PresentationSource.FromVisual(this);
            _source.AddHook(WndProc);
        }
    }

    private IntPtr WndProc(IntPtr hwnd, int msg, IntPtr wParam, IntPtr lParam, ref bool handled)
    {
        const int WM_NCHITTEST = 0x0084;
        const int HTTRANSPARENT = -1;

        if (msg == WM_NCHITTEST)
        {
            // Screen coordinates from lParam (may be in physical pixels)
            int x = (short)(lParam.ToInt64() & 0xFFFF);
            int y = (short)((lParam.ToInt64() >> 16) & 0xFFFF);

            var screenPt = new Point(x, y);

            // Convert to DIP (best-effort)
            var ps = PresentationSource.FromVisual(this);
            if (ps?.CompositionTarget != null)
            {
                var m = ps.CompositionTarget.TransformFromDevice;
                screenPt = m.Transform(screenPt);
            }

            var localPt = PointFromScreen(screenPt);

            // Hit test under pointer
            var hit = VisualTreeHelper.HitTest(Root, localPt);
            if (hit?.VisualHit == null)
            {
                handled = true;
                return new IntPtr(HTTRANSPARENT);
            }

            if (IsInteractive(hit.VisualHit))
            {
                handled = false; // default processing
                return IntPtr.Zero;
            }

            handled = true;
            return new IntPtr(HTTRANSPARENT);
        }

        return IntPtr.Zero;
    }

    private bool IsInteractive(DependencyObject? d)
    {
        while (d != null)
        {
            var name = d.GetType().Name;
            foreach (var allowed in _settings.Overlay.Interaction.InteractiveWhitelist)
            {
                if (string.Equals(name, allowed, StringComparison.OrdinalIgnoreCase))
                    return true;
            }
            d = VisualTreeHelper.GetParent(d);
        }
        return false;
    }
}
