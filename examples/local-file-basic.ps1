param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,

    [string]$OutputDir = "outputs\local-basic",
    [string]$Model = "small"
)

flowscribe transcribe $InputPath `
    -o $OutputDir `
    --format txt,md `
    --model $Model `
    --overwrite
