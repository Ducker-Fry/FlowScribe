using System.Text.Json.Serialization;

namespace WasapiCaptureHelper.Models;

internal sealed record CaptureCompleteEvent(
    [property: JsonPropertyName("event")] string Event,
    [property: JsonPropertyName("output")] string Output,
    [property: JsonPropertyName("duration_seconds")] double DurationSeconds);
