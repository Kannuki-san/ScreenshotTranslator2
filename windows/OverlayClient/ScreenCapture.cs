using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Runtime.InteropServices;

namespace OverlayClient;

public static class ScreenCapture
{
    public static byte[] CaptureRectToPngBytes(RectInt rect)
    {
        if (rect.Width <= 0 || rect.Height <= 0)
            throw new ArgumentException("Invalid capture size.");

        IntPtr hdcSrc = IntPtr.Zero;
        IntPtr hdcDest = IntPtr.Zero;
        IntPtr hBitmap = IntPtr.Zero;
        IntPtr hOld = IntPtr.Zero;

        try
        {
            hdcSrc = GetDC(IntPtr.Zero);
            if (hdcSrc == IntPtr.Zero)
                throw new InvalidOperationException("GetDC failed.");

            hdcDest = CreateCompatibleDC(hdcSrc);
            if (hdcDest == IntPtr.Zero)
                throw new InvalidOperationException("CreateCompatibleDC failed.");

            hBitmap = CreateCompatibleBitmap(hdcSrc, rect.Width, rect.Height);
            if (hBitmap == IntPtr.Zero)
                throw new InvalidOperationException("CreateCompatibleBitmap failed.");

            hOld = SelectObject(hdcDest, hBitmap);
            if (hOld == IntPtr.Zero)
                throw new InvalidOperationException("SelectObject failed.");

            if (!BitBlt(hdcDest, 0, 0, rect.Width, rect.Height, hdcSrc, rect.X, rect.Y, CopyPixelOperation.SourceCopy | CopyPixelOperation.CaptureBlt))
                throw new InvalidOperationException("BitBlt failed.");

            using var bmp = Image.FromHbitmap(hBitmap);
            using var ms = new MemoryStream();
            bmp.Save(ms, ImageFormat.Png);
            return ms.ToArray();
        }
        finally
        {
            if (hOld != IntPtr.Zero && hdcDest != IntPtr.Zero) SelectObject(hdcDest, hOld);
            if (hBitmap != IntPtr.Zero) DeleteObject(hBitmap);
            if (hdcDest != IntPtr.Zero) DeleteDC(hdcDest);
            if (hdcSrc != IntPtr.Zero) ReleaseDC(IntPtr.Zero, hdcSrc);
        }
    }

    public static byte[] DrawGuideRect(byte[] cleanPng)
    {
        using var ms = new MemoryStream(cleanPng);
        using var bmp = new Bitmap(ms);
        using var g = Graphics.FromImage(bmp);
        g.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
        using var pen = new Pen(Color.Red, 3);
        g.DrawRectangle(pen, 2, 2, bmp.Width - 4, bmp.Height - 4);

        using var outStream = new MemoryStream();
        bmp.Save(outStream, ImageFormat.Png);
        return outStream.ToArray();
    }

    #region Win32
    [DllImport("user32.dll")]
    private static extern IntPtr GetDC(IntPtr hWnd);

    [DllImport("user32.dll")]
    private static extern int ReleaseDC(IntPtr hWnd, IntPtr hDC);

    [DllImport("gdi32.dll")]
    private static extern IntPtr CreateCompatibleDC(IntPtr hdc);

    [DllImport("gdi32.dll")]
    private static extern bool DeleteDC(IntPtr hdc);

    [DllImport("gdi32.dll")]
    private static extern IntPtr CreateCompatibleBitmap(IntPtr hdc, int nWidth, int nHeight);

    [DllImport("gdi32.dll")]
    private static extern IntPtr SelectObject(IntPtr hdc, IntPtr hgdiobj);

    [DllImport("gdi32.dll")]
    private static extern bool DeleteObject(IntPtr hObject);

    [DllImport("gdi32.dll")]
    private static extern bool BitBlt(
        IntPtr hdcDest,
        int nXDest,
        int nYDest,
        int nWidth,
        int nHeight,
        IntPtr hdcSrc,
        int nXSrc,
        int nYSrc,
        CopyPixelOperation dwRop);
    #endregion
}
