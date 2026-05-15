using NAudio.CoreAudioApi;
using WasapiCaptureHelper.Models;

namespace WasapiCaptureHelper.Audio;

internal sealed class DeviceEnumerationService
{
    public DeviceInfo? GetDefaultOutputDevice()
    {
        using var enumerator = new MMDeviceEnumerator();
        using var device = enumerator.GetDefaultAudioEndpoint(DataFlow.Render, Role.Multimedia);
        return device is null ? null : ToDeviceInfo(device, isDefault: true);
    }

    public IReadOnlyList<DeviceInfo> ListOutputDevices()
    {
        using var enumerator = new MMDeviceEnumerator();
        using var defaultDevice = enumerator.GetDefaultAudioEndpoint(DataFlow.Render, Role.Multimedia);
        var defaultId = defaultDevice?.ID;

        return enumerator
            .EnumerateAudioEndPoints(DataFlow.Render, DeviceState.Active)
            .Select(device => ToDeviceInfo(device, string.Equals(device.ID, defaultId, StringComparison.OrdinalIgnoreCase)))
            .ToArray();
    }

    public MMDevice ResolveOutputDevice(string deviceId)
    {
        using var enumerator = new MMDeviceEnumerator();
        var device = string.Equals(deviceId, "default", StringComparison.OrdinalIgnoreCase)
            ? enumerator.GetDefaultAudioEndpoint(DataFlow.Render, Role.Multimedia)
            : enumerator.GetDevice(deviceId);

        if (device is null || device.State != DeviceState.Active)
        {
            device?.Dispose();
            throw new UnsupportedCaptureException("No active output device available for loopback capture.");
        }

        return device;
    }

    private static DeviceInfo ToDeviceInfo(MMDevice device, bool isDefault)
    {
        return new DeviceInfo(device.ID, device.FriendlyName, isDefault);
    }
}
