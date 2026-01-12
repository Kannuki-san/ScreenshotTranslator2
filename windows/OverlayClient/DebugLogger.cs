using System;
using System.IO;

namespace OverlayClient;

public sealed class DebugLogger
{
    private readonly bool _enabled;
    private readonly string _path;
    private readonly object _lock = new();

    public DebugLogger(AppSettings settings)
    {
        _enabled = string.Equals(settings.Logging.Level, "debug", StringComparison.OrdinalIgnoreCase);
        _path = Path.Combine(AppContext.BaseDirectory, "overlay_debug.log");
    }

    public bool Enabled => _enabled;

    public void Log(string message)
    {
        if (!_enabled)
            return;
        var line = $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss.fff}] {message}";
        lock (_lock)
        {
            File.AppendAllText(_path, line + Environment.NewLine);
        }
    }
}
