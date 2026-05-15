namespace WasapiCaptureHelper.Audio;

using NAudio.Wave;
using WasapiCaptureHelper.Commands;
using WasapiCaptureHelper.Models;

internal sealed class WasapiLoopbackCaptureService
{
    public async Task CaptureUntilStopAsync(CaptureOptions options, Action<object> emit)
    {
        var writer = new WavCaptureWriter();
        writer.EnsureOutputDirectory(options.OutputPath);

        var deviceService = new DeviceEnumerationService();
        using var device = deviceService.ResolveOutputDevice(options.DeviceId);
        using var capture = new WasapiLoopbackCapture(device);

        if (options.SampleRate is not null || options.Channels is not null)
        {
            capture.WaveFormat = new WaveFormat(
                options.SampleRate ?? capture.WaveFormat.SampleRate,
                bits: 16,
                channels: options.Channels ?? capture.WaveFormat.Channels);
        }

        var startedAt = DateTimeOffset.UtcNow;
        var stopped = new TaskCompletionSource<Exception?>(TaskCreationOptions.RunContinuationsAsynchronously);

        using var waveWriter = new WaveFileWriter(options.OutputPath, capture.WaveFormat);
        capture.DataAvailable += (_, eventArgs) =>
        {
            if (eventArgs.BytesRecorded > 0)
            {
                waveWriter.Write(eventArgs.Buffer, 0, eventArgs.BytesRecorded);
                waveWriter.Flush();
            }
        };
        capture.RecordingStopped += (_, eventArgs) => stopped.TrySetResult(eventArgs.Exception);

        try
        {
            capture.StartRecording();
        }
        catch (Exception ex)
        {
            throw new UnsupportedCaptureException($"Could not start WASAPI loopback capture: {ex.Message}", ex);
        }

        emit(new CaptureStartEvent(
            Event: "started",
            DeviceId: device.ID,
            DeviceName: device.FriendlyName,
            Output: options.OutputPath));

        await WaitForStopCommandAsync().ConfigureAwait(false);
        emit(new { @event = "stopping" });

        capture.StopRecording();
        var stopException = await stopped.Task.WaitAsync(TimeSpan.FromSeconds(10)).ConfigureAwait(false);
        if (stopException is not null)
        {
            throw stopException;
        }

        waveWriter.Flush();

        var duration = DateTimeOffset.UtcNow - startedAt;
        emit(new CaptureCompleteEvent(
            Event: "completed",
            Output: options.OutputPath,
            DurationSeconds: Math.Round(duration.TotalSeconds, 3)));
    }

    private static Task WaitForStopCommandAsync()
    {
        return Task.Run(() =>
        {
            string? line;
            while ((line = Console.In.ReadLine()) is not null)
            {
                if (string.Equals(line.Trim(), "stop", StringComparison.OrdinalIgnoreCase))
                {
                    return;
                }
            }
        });
    }
}

internal sealed class UnsupportedCaptureException : Exception
{
    public UnsupportedCaptureException(string message)
        : base(message)
    {
    }

    public UnsupportedCaptureException(string message, Exception innerException)
        : base(message, innerException)
    {
    }
}
