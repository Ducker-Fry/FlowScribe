using WasapiCaptureHelper.Audio;
using WasapiCaptureHelper.Models;
using WasapiCaptureHelper.Serialization;

namespace WasapiCaptureHelper.Commands;

internal static class ProbeCommand
{
    public static int Run()
    {
        try
        {
            var service = new DeviceEnumerationService();
            var defaultDevice = service.GetDefaultOutputDevice();

            if (defaultDevice is null)
            {
                JsonConsole.Write(new ProbeResult(
                    Command: "probe",
                    Supported: false,
                    DefaultOutputDevice: null,
                    Reason: "No active output device available for loopback capture."));
                return 2;
            }

            JsonConsole.Write(new ProbeResult(
                Command: "probe",
                Supported: true,
                DefaultOutputDevice: defaultDevice,
                Reason: null));
            return 0;
        }
        catch (Exception ex)
        {
            JsonConsole.Write(new ProbeResult(
                Command: "probe",
                Supported: false,
                DefaultOutputDevice: null,
                Reason: ex.Message));
            return 2;
        }
    }
}
