param(
    [string]$Url = "https://tv.cctv.com/2026/05/12/VIDEBtNAQbQRT5vvxRFP28FR260512.shtml",
    [string]$OutputDir = "outputs\demo-cctv",
    [string]$Model = "small"
)

flowscribe url $Url `
    -o $OutputDir `
    --format txt,md,json `
    --model $Model `
    --language zh `
    --preset zh `
    --max-download-mb 500 `
    --max-duration 00:30:00 `
    --download-timeout 30 `
    --overwrite
