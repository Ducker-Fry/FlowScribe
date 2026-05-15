using System.Text.Json.Serialization;

namespace WasapiCaptureHelper.Models;

internal sealed record ErrorEvent(
    [property: JsonPropertyName("event")] string Event,
    [property: JsonPropertyName("message")] string Message);
