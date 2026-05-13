param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,

    [string]$OutputDir = "outputs\local-timestamps",
    [string]$Model = "small"
)

flowscribe transcribe $InputPath `
    -o $OutputDir `
    --format txt,md,json,srt,vtt `
    --timestamps `
    --word-timestamps `
    --model $Model `
    --overwrite
