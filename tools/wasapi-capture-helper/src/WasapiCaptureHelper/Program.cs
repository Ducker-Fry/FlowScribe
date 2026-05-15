using WasapiCaptureHelper.Commands;

var commandName = args.Length > 0 ? args[0].Trim().ToLowerInvariant() : string.Empty;
var commandArgs = args.Skip(1).ToArray();

return commandName switch
{
    "version" => VersionCommand.Run(),
    "probe" => ProbeCommand.Run(),
    "list-devices" => ListDevicesCommand.Run(),
    "capture" => CaptureCommand.Run(commandArgs),
    _ => VersionCommand.RunInvalidCommand(commandName),
};
