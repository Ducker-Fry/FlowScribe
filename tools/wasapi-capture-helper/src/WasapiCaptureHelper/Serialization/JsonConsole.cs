using System.Text.Json;
using System.Text.Json.Serialization;
using WasapiCaptureHelper.Models;

namespace WasapiCaptureHelper.Serialization;

internal static class JsonConsole
{
    private static readonly JsonSerializerOptions Options = new()
    {
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
    };

    public static void Write<T>(T value)
    {
        Console.Out.WriteLine(JsonSerializer.Serialize(value, Options));
        Console.Out.Flush();
    }

    public static void WriteError(string message)
    {
        Write(new ErrorEvent("error", message));
    }
}
