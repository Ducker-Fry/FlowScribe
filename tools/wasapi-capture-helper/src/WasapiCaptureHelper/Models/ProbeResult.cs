using System.Text.Json.Serialization;

namespace WasapiCaptureHelper.Models;

internal sealed record ProbeResult(
    [property: JsonPropertyName("command")] string Command,
    [property: JsonPropertyName("supported")] bool Supported,
    [property: JsonPropertyName("default_output_device")] DeviceInfo? DefaultOutputDevice,
    [property: JsonPropertyName("reason")] string? Reason);
