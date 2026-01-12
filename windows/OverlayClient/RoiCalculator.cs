using System;
namespace OverlayClient;

public static class RoiCalculator
{
    public static RectInt NormalizeFromRect(RectInt rect, RoiSettings settings, bool applyMargin)
    {
        if (rect.IsEmpty)
            return rect;

        int centerX = rect.X + rect.Width / 2;
        int centerY = rect.Y + rect.Height / 2;
        return NormalizeFromCenter(centerX, centerY, rect.Width, rect.Height, settings, applyMargin);
    }

    private static RectInt NormalizeFromCenter(int centerX, int centerY, int width, int height, RoiSettings settings, bool applyMargin)
    {
        if (applyMargin)
        {
            int marginW = (int)(width * settings.MarginRatio);
            int marginH = (int)(height * settings.MarginRatio);
            width += marginW * 2;
            height += marginH * 2;
        }

        width = Math.Clamp(width, settings.MinWidth, settings.MaxWidth);
        height = Math.Clamp(height, settings.MinHeight, settings.MaxHeight);

        int x = centerX - width / 2;
        int y = centerY - height / 2;
        var roi = new RectInt(x, y, width, height);

        if (settings.ClipToScreen)
        {
            var screen = Win32Helpers.GetVirtualScreenRect();
            roi = Clip(roi, screen);
        }

        return roi;
    }

    private static RectInt Clip(RectInt roi, RectInt screen)
    {
        int x1 = Math.Max(roi.X, screen.X);
        int y1 = Math.Max(roi.Y, screen.Y);
        int x2 = Math.Min(roi.Right, screen.Right);
        int y2 = Math.Min(roi.Bottom, screen.Bottom);
        return new RectInt(x1, y1, Math.Max(0, x2 - x1), Math.Max(0, y2 - y1));
    }
}
