using System;
using System.Runtime.InteropServices;
using System.Windows;

namespace OverlayClient;

public sealed class CtrlHoldSelector : IDisposable
{
    private readonly KeyboardHook _keyboard;
    private readonly MouseHook _mouse;
    private readonly AppSettings _settings;
    private bool _ctrlDown;
    private bool _altDown;
    private bool _ctrlDownActive;
    private int _startX;
    private int _startY;
    private int _currentX;
    private int _currentY;
    private LiveRoiWindow? _preview;

    public event Action<RectInt>? RoiSelected;

    public CtrlHoldSelector(AppSettings settings)
    {
        _settings = settings;
        _keyboard = new KeyboardHook();
        _keyboard.CtrlChanged += OnCtrlChanged;
        _keyboard.AltChanged += OnAltChanged;
        _mouse = new MouseHook();
        _mouse.MouseMoved += OnMouseMoved;
    }

    public void Start()
    {
        _keyboard.Start();
        _mouse.Start();
    }

    public void Stop()
    {
        _keyboard.Stop();
        _mouse.Stop();
    }

    public void Dispose()
    {
        Stop();
        _keyboard.Dispose();
        _mouse.Dispose();
    }

    private void OnCtrlChanged(bool down)
    {
        _ctrlDown = down;
        HandleModifierChange();
    }

    private void OnAltChanged(bool down)
    {
        _altDown = down;
        HandleModifierChange();
    }

    private void HandleModifierChange()
    {
        if (!_settings.Gesture.Enabled)
        {
            ClosePreview();
            return;
        }

        bool shouldSelect = ShouldSelect();

        if (shouldSelect && !_ctrlDownActive)
        {
            _ctrlDownActive = true;
            if (GetCursorPos(out var pt))
            {
                _startX = pt.X;
                _startY = pt.Y;
                _currentX = pt.X;
                _currentY = pt.Y;
                ShowPreview();
            }
            return;
        }

        if (!shouldSelect && _ctrlDownActive)
        {
            _ctrlDownActive = false;
            if (GetCursorPos(out var pt))
            {
                int x1 = Math.Min(_startX, pt.X);
                int y1 = Math.Min(_startY, pt.Y);
                int x2 = Math.Max(_startX, pt.X);
                int y2 = Math.Max(_startY, pt.Y);
                var rect = new RectInt(x1, y1, x2 - x1, y2 - y1);
                var normalized = RoiCalculator.NormalizeFromRect(rect, _settings.Roi, applyMargin: false);
                if (!normalized.IsEmpty)
                    RoiSelected?.Invoke(normalized);
            }
            ClosePreview();
        }
    }

    private bool ShouldSelect()
    {
        var mode = (_settings.Gesture.Modifier ?? "ctrl").ToLowerInvariant();
        return mode switch
        {
            "ctrl_alt" => _ctrlDown && _altDown,
            "ctrl" => _ctrlDown,
            "alt" => _altDown,
            _ => _ctrlDown
        };
    }

    private void OnMouseMoved(int x, int y, bool _)
    {
        if (!_ctrlDownActive)
            return;
        _currentX = x;
        _currentY = y;
        UpdatePreview();
    }

    private void ShowPreview()
    {
        if (!_settings.Overlay.Preview.LivePreview)
            return;
        Application.Current.Dispatcher.Invoke(() =>
        {
            _preview ??= new LiveRoiWindow();
            _preview.UpdateRect(BuildRect());
            if (!_preview.IsVisible)
                _preview.Show();
        });
    }

    private void UpdatePreview()
    {
        if (!_settings.Overlay.Preview.LivePreview)
            return;
        Application.Current.Dispatcher.Invoke(() =>
        {
            if (_preview == null)
                return;
            _preview.UpdateRect(BuildRect());
        });
    }

    private void ClosePreview()
    {
        Application.Current.Dispatcher.Invoke(() =>
        {
            _preview?.Close();
            _preview = null;
        });
    }

    private RectInt BuildRect()
    {
        int x1 = Math.Min(_startX, _currentX);
        int y1 = Math.Min(_startY, _currentY);
        int x2 = Math.Max(_startX, _currentX);
        int y2 = Math.Max(_startY, _currentY);
        return new RectInt(x1, y1, x2 - x1, y2 - y1);
    }

    [DllImport("user32.dll")]
    private static extern bool GetCursorPos(out POINT lpPoint);

    [StructLayout(LayoutKind.Sequential)]
    private struct POINT
    {
        public int X;
        public int Y;
    }
}
