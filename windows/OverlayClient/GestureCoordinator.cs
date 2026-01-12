using System;

namespace OverlayClient;

public sealed class GestureCoordinator : IDisposable
{
    private readonly TranslationService _translation;
    private readonly DragRoiSelector? _dragSelector;
    private readonly CtrlHoldSelector? _ctrlHoldSelector;

    public GestureCoordinator(AppSettings settings, TranslationService translation, DebugLogger logger)
    {
        _translation = translation;

        var mode = (settings.Gesture.Mode ?? "ctrl_hold").ToLowerInvariant();
        if (mode == "ctrl_hold")
        {
            _ctrlHoldSelector = new CtrlHoldSelector(settings);
            _ctrlHoldSelector.RoiSelected += roi => _translation.HandleRoi(roi);
        }
        else if (mode == "ctrl_drag")
        {
            _dragSelector = new DragRoiSelector(settings);
            _dragSelector.RoiSelected += roi => _translation.HandleRoi(roi);
        }
    }

    public void Start()
    {
        _dragSelector?.Start();
        _ctrlHoldSelector?.Start();
    }

    public void Stop()
    {
        _dragSelector?.Stop();
        _ctrlHoldSelector?.Stop();
    }

    public void Dispose()
    {
        _dragSelector?.Dispose();
        _ctrlHoldSelector?.Dispose();
    }
}
