using System.Runtime.InteropServices;
using WasapiCaptureHelper.Serialization;

namespace WasapiCaptureHelper.Commands;

internal static class VersionCommand
{
    public const string HelperName = "WasapiCaptureHelper";
    public const string HelperVersion = "0.1.0";

    public static int Run()
    {
        JsonConsole.Write(new
        {
            command = "version",
            name = HelperName,
            version = HelperVersion,
            runtime = RuntimeInformation.FrameworkDescription,
            platform = RuntimeInformation.RuntimeIdentifier,
        });

        return 0;
    }

    public static int RunInvalidCommand(string commandName)
    {
        JsonConsole.WriteError(
            string.IsNullOrWhiteSpace(commandName)
                ? "Missing command. Expected one of: version, probe, list-devices, capture."
                : $"Unknown command '{commandName}'. Expected one of: version, probe, list-devices, capture.");

        return 4;
    }
}
