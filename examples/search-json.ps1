param(
    [Parameter(Mandatory = $true)]
    [string]$TranscriptPath,

    [Parameter(Mandatory = $true)]
    [string]$Query,

    [int]$Limit = 10
)

flowscribe search $TranscriptPath $Query `
    --limit $Limit `
    --context-chars 50
