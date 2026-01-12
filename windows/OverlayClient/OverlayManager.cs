using System;
using System.Windows;

namespace OverlayClient;

public sealed class OverlayManager
{
    private readonly AppSettings _settings;
    private OverlayWindow? _current;

    public OverlayManager(AppSettings settings)
    {
        _settings = settings;
    }

    public void ShowOverlay(RectInt bboxPx, string status, string text)
    {
        if (_settings.Overlay.Interaction.ReplaceExisting)
        {
            _current?.Close();
            _current = null;
        }

        var win = new OverlayWindow(_settings);
        win.SetContent(status, text);

        var topLeft = Win32Helpers.ToDip(bboxPx.X, bboxPx.Y);
        var bottomRight = Win32Helpers.ToDip(bboxPx.Right, bboxPx.Bottom);
        win.Left = topLeft.X;
        win.Top = topLeft.Y;
        win.Width = Math.Max(1, bottomRight.X - topLeft.X);
        win.Height = Math.Max(1, bottomRight.Y - topLeft.Y);

        win.Show();
        _current = win;
    }

    public void ShowDebugRoi(RectInt roi, int durationMs = 700)
    {
        if (!_settings.Overlay.Preview.ShowRoiPreview)
            return;
        int ms = Math.Max(100, _settings.Overlay.Preview.DurationMs);
        var win = new DebugRoiWindow(ms);
        win.ShowAt(roi);
    }

    public void CloseCurrent()
    {
        _current?.Close();
        _current = null;
    }
}
