using WasapiCaptureHelper.Audio;
using WasapiCaptureHelper.Serialization;

namespace WasapiCaptureHelper.Commands;

internal static class ListDevicesCommand
{
    public static int Run()
    {
        try
        {
            var service = new DeviceEnumerationService();
            var devices = service.ListOutputDevices();
            var defaultDevice = devices.FirstOrDefault(device => device.IsDefault);

            JsonConsole.Write(new
            {
                command = "list-devices",
                default_output_id = defaultDevice?.Id,
                devices,
            });

            return 0;
        }
        catch (Exception ex)
        {
            JsonConsole.WriteError(ex.Message);
            return 2;
        }
    }
}
