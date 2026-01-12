using System;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace OverlayClient;

public sealed class LiveRoiWindow : Window
{
    private readonly Border _border;

    public LiveRoiWindow()
    {
        WindowStyle = WindowStyle.None;
        AllowsTransparency = true;
        Background = Brushes.Transparent;
        Topmost = true;
        ShowInTaskbar = false;
        ResizeMode = ResizeMode.NoResize;
        IsHitTestVisible = false;

        _border = new Border
        {
            BorderBrush = Brushes.Red,
            BorderThickness = new Thickness(2),
            Background = Brushes.Transparent
        };

        Content = _border;
    }

    public void UpdateRect(RectInt rectPx)
    {
        var topLeft = Win32Helpers.ToDip(rectPx.X, rectPx.Y);
        var bottomRight = Win32Helpers.ToDip(rectPx.Right, rectPx.Bottom);
        Left = topLeft.X;
        Top = topLeft.Y;
        Width = Math.Max(1, bottomRight.X - topLeft.X);
        Height = Math.Max(1, bottomRight.Y - topLeft.Y);
    }
}
