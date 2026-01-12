using System;

namespace OverlayClient;

public sealed class DragRoiSelector : IDisposable
{
    private readonly MouseHook _hook;
    private readonly AppSettings _settings;
    private bool _dragging;
    private int _startX;
    private int _startY;
    private int _currentX;
    private int _currentY;

    public event Action<RectInt>? RoiSelected;

    public DragRoiSelector(AppSettings settings)
    {
        _settings = settings;
        _hook = new MouseHook();
        _hook.LeftButtonDown += OnLeftDown;
        _hook.LeftButtonUp += OnLeftUp;
        _hook.MouseMoved += OnMouseMoved;
    }

    public void Start() => _hook.Start();

    public void Stop() => _hook.Stop();

    public void Dispose()
    {
        Stop();
        _hook.Dispose();
    }

    private void OnLeftDown(int x, int y, bool ctrlDown)
    {
        if (!_settings.Gesture.Enabled)
            return;
        if (!ctrlDown)
            return;

        _dragging = true;
        _startX = x;
        _startY = y;
        _currentX = x;
        _currentY = y;
    }

    private void OnMouseMoved(int x, int y, bool _)
    {
        if (!_dragging)
            return;
        _currentX = x;
        _currentY = y;
    }

    private void OnLeftUp(int x, int y, bool _)
    {
        if (!_dragging)
            return;

        _dragging = false;
        _currentX = x;
        _currentY = y;

        int x1 = Math.Min(_startX, _currentX);
        int y1 = Math.Min(_startY, _currentY);
        int x2 = Math.Max(_startX, _currentX);
        int y2 = Math.Max(_startY, _currentY);
        var rect = new RectInt(x1, y1, x2 - x1, y2 - y1);

        var normalized = RoiCalculator.NormalizeFromRect(rect, _settings.Roi, applyMargin: false);
        if (!normalized.IsEmpty)
            RoiSelected?.Invoke(normalized);
    }
}
