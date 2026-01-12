using System;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Threading;

namespace OverlayClient;

public sealed class DebugRoiWindow : Window
{
    private readonly DispatcherTimer _timer;

    public DebugRoiWindow(int durationMs)
    {
        WindowStyle = WindowStyle.None;
        AllowsTransparency = true;
        Background = Brushes.Transparent;
        Topmost = true;
        ShowInTaskbar = false;
        ResizeMode = ResizeMode.NoResize;
        IsHitTestVisible = false;

        var border = new Border
        {
            BorderBrush = Brushes.Red,
            BorderThickness = new Thickness(2),
            Background = Brushes.Transparent
        };
        Content = border;

        _timer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(durationMs) };
        _timer.Tick += (_, __) => Close();
    }

    public void ShowAt(RectInt rectPx)
    {
        var topLeft = Win32Helpers.ToDip(rectPx.X, rectPx.Y);
        var bottomRight = Win32Helpers.ToDip(rectPx.Right, rectPx.Bottom);
        Left = topLeft.X;
        Top = topLeft.Y;
        Width = Math.Max(1, bottomRight.X - topLeft.X);
        Height = Math.Max(1, bottomRight.Y - topLeft.Y);
        Show();
        _timer.Start();
    }

    protected override void OnClosed(EventArgs e)
    {
        _timer.Stop();
        base.OnClosed(e);
    }
}
