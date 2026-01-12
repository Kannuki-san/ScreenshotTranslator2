using System;
using System.Text.Json.Serialization;

namespace OverlayClient;

public readonly struct RectInt
{
    public RectInt(int x, int y, int width, int height)
    {
        X = x;
        Y = y;
        Width = width;
        Height = height;
    }

    public int X { get; }
    public int Y { get; }
    public int Width { get; }
    public int Height { get; }
    public int Right => X + Width;
    public int Bottom => Y + Height;
    public int Area => Math.Max(0, Width) * Math.Max(0, Height);
    public bool IsEmpty => Width <= 0 || Height <= 0;
}

public sealed class InferenceResponse
{
    [JsonPropertyName("target_bbox")] public BBox? TargetBbox { get; set; }
    [JsonPropertyName("ocr_text")] public string? OcrText { get; set; }
    [JsonPropertyName("ja_translation")] public string? JaTranslation { get; set; }
    [JsonPropertyName("detected_language")] public string? DetectedLanguage { get; set; }
    [JsonPropertyName("confidence")] public double? Confidence { get; set; }
    [JsonPropertyName("notes")] public string? Notes { get; set; }
    [JsonPropertyName("roi_fallback")] public RoiFallback? RoiFallback { get; set; }
}

public sealed class BBox
{
    [JsonPropertyName("x1")] public int X1 { get; set; }
    [JsonPropertyName("y1")] public int Y1 { get; set; }
    [JsonPropertyName("x2")] public int X2 { get; set; }
    [JsonPropertyName("y2")] public int Y2 { get; set; }

    public int Width => X2 - X1;
    public int Height => Y2 - Y1;
}

public sealed class RoiFallback
{
    [JsonPropertyName("ocr_text")] public string? OcrText { get; set; }
    [JsonPropertyName("ja_translation")] public string? JaTranslation { get; set; }
}

public sealed class InferenceResult
{
    public InferenceResponse? Parsed { get; init; }
    public string? Raw { get; init; }
    public string? Error { get; init; }
}
