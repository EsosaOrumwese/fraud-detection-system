param(
    [string]$SsmPrefix = "/fraud-platform/dev_min",
    [string]$Bootstrap = "",
    [string]$ApiKey = "",
    [string]$ApiSecret = "",
    [switch]$FromEnv
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($FromEnv) {
    if ([string]::IsNullOrWhiteSpace($Bootstrap)) { $Bootstrap = $env:DEV_MIN_KAFKA_BOOTSTRAP }
    if ([string]::IsNullOrWhiteSpace($ApiKey)) { $ApiKey = $env:DEV_MIN_KAFKA_API_KEY }
    if ([string]::IsNullOrWhiteSpace($ApiSecret)) { $ApiSecret = $env:DEV_MIN_KAFKA_API_SECRET }
}

if ([string]::IsNullOrWhiteSpace($Bootstrap) -or [string]::IsNullOrWhiteSpace($ApiKey) -or [string]::IsNullOrWhiteSpace($ApiSecret)) {
    Write-Error "Bootstrap, ApiKey, and ApiSecret are required (args or -FromEnv with DEV_MIN_KAFKA_* set)."
    exit 2
}

$targets = @(
    @{ name = "$SsmPrefix/confluent/bootstrap"; value = $Bootstrap },
    @{ name = "$SsmPrefix/confluent/api_key"; value = $ApiKey },
    @{ name = "$SsmPrefix/confluent/api_secret"; value = $ApiSecret }
)

foreach ($item in $targets) {
    $result = & aws ssm put-parameter `
        --name $item.name `
        --type SecureString `
        --overwrite `
        --value $item.value `
        --query "Version" `
        --output text 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error ("Failed to write parameter handle: " + $item.name)
        Write-Error ($result | Out-String)
        exit 3
    }
    Write-Output ("[PASS] wrote handle " + $item.name + " (version " + ($result | Out-String).Trim() + ")")
}

Write-Output "Seed complete (values not printed)."
