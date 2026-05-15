using System.Text.Json.Serialization;

namespace WasapiCaptureHelper.Models;

internal sealed record DeviceInfo(
    [property: JsonPropertyName("id")] string Id,
    [property: JsonPropertyName("name")] string Name,
    [property: JsonPropertyName("is_default")] bool IsDefault);
