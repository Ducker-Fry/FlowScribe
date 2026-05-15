using WasapiCaptureHelper.Audio;
using WasapiCaptureHelper.Serialization;

namespace WasapiCaptureHelper.Commands;

internal static class CaptureCommand
{
    public static int Run(string[] args)
    {
        if (!TryParseOptions(args, out var options, out var errorMessage))
        {
            JsonConsole.WriteError(errorMessage);
            return 4;
        }

        try
        {
            var service = new WasapiLoopbackCaptureService();
            service.CaptureUntilStopAsync(options, JsonConsole.Write).GetAwaiter().GetResult();
            return 0;
        }
        catch (UnsupportedCaptureException ex)
        {
            JsonConsole.WriteError(ex.Message);
            return 2;
        }
        catch (ArgumentException ex)
        {
            JsonConsole.WriteError(ex.Message);
            return 4;
        }
        catch (Exception ex)
        {
            JsonConsole.WriteError(ex.Message);
            return 3;
        }
    }

    private static bool TryParseOptions(string[] args, out CaptureOptions options, out string errorMessage)
    {
        options = new CaptureOptions(OutputPath: string.Empty, DeviceId: "default", SampleRate: null, Channels: null);
        errorMessage = string.Empty;

        var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        for (var index = 0; index < args.Length; index++)
        {
            var key = args[index];
            if (!key.StartsWith("--", StringComparison.Ordinal))
            {
                errorMessage = $"Unexpected argument '{key}'.";
                return false;
            }

            if (index + 1 >= args.Length || args[index + 1].StartsWith("--", StringComparison.Ordinal))
            {
                errorMessage = $"Missing value for argument '{key}'.";
                return false;
            }

            values[key] = args[index + 1];
            index++;
        }

        if (!values.TryGetValue("--output", out var outputPath) || string.IsNullOrWhiteSpace(outputPath))
        {
            errorMessage = "Missing required argument: --output <absolute-path>.";
            return false;
        }

        if (!Path.IsPathFullyQualified(outputPath))
        {
            errorMessage = "--output must be an absolute path.";
            return false;
        }

        var deviceId = values.TryGetValue("--device", out var deviceValue) && !string.IsNullOrWhiteSpace(deviceValue)
            ? deviceValue
            : "default";

        if (!TryReadPositiveInt(values, "--sample-rate", out var sampleRate, out errorMessage))
        {
            return false;
        }

        if (!TryReadPositiveInt(values, "--channels", out var channels, out errorMessage))
        {
            return false;
        }

        if (values.Keys.Any(key => key is not "--output" and not "--device" and not "--sample-rate" and not "--channels"))
        {
            var unknown = values.Keys.First(key => key is not "--output" and not "--device" and not "--sample-rate" and not "--channels");
            errorMessage = $"Unknown argument '{unknown}'.";
            return false;
        }

        options = new CaptureOptions(outputPath, deviceId, sampleRate, channels);
        return true;
    }

    private static bool TryReadPositiveInt(
        IReadOnlyDictionary<string, string> values,
        string key,
        out int? result,
        out string errorMessage)
    {
        result = null;
        errorMessage = string.Empty;

        if (!values.TryGetValue(key, out var value))
        {
            return true;
        }

        if (!int.TryParse(value, out var parsed) || parsed <= 0)
        {
            errorMessage = $"{key} must be a positive integer.";
            return false;
        }

        if (key == "--channels" && parsed is not 1 and not 2)
        {
            errorMessage = "--channels must be 1 or 2.";
            return false;
        }

        if (key == "--sample-rate" && parsed < 8000)
        {
            errorMessage = "--sample-rate must be at least 8000.";
            return false;
        }

        result = parsed;
        return true;
    }
}

internal sealed record CaptureOptions(
    string OutputPath,
    string DeviceId,
    int? SampleRate,
    int? Channels);
