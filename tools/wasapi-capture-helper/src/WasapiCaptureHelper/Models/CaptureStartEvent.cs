using System.Text.Json.Serialization;

namespace WasapiCaptureHelper.Models;

internal sealed record CaptureStartEvent(
    [property: JsonPropertyName("event")] string Event,
    [property: JsonPropertyName("device_id")] string DeviceId,
    [property: JsonPropertyName("device_name")] string DeviceName,
    [property: JsonPropertyName("output")] string Output);
