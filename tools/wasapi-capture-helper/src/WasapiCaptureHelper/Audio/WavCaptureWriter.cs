namespace WasapiCaptureHelper.Audio;

internal sealed class WavCaptureWriter
{
    public void EnsureOutputDirectory(string outputPath)
    {
        if (File.Exists(outputPath))
        {
            File.Delete(outputPath);
        }

        var directory = Path.GetDirectoryName(outputPath);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }
    }
}
