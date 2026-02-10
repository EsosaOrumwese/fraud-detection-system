param(
    [string]$RequiredRegion = "eu-west-2",
    [string]$SsmPrefix = "/fraud-platform/dev_min",
    [switch]$AllowMissingConfluentHandles,
    [switch]$SkipConfluentApiProbe,
    [string]$OutputPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function New-CheckResult {
    param(
        [string]$Name,
        [string]$Status,
        [string]$Detail
    )
    return [PSCustomObject]@{
        name = $Name
        status = $Status
        detail = $Detail
    }
}

function Invoke-AwsText {
    param(
        [string[]]$Arguments
    )
    $output = & aws @Arguments 2>&1
    $code = $LASTEXITCODE
    return [PSCustomObject]@{
        code = $code
        output = ($output | Out-String).Trim()
    }
}

function Resolve-Region {
    $region = (& aws configure get region 2>$null | Out-String).Trim()
    if ([string]::IsNullOrWhiteSpace($region)) {
        if (-not [string]::IsNullOrWhiteSpace($env:AWS_REGION)) {
            return $env:AWS_REGION
        }
        if (-not [string]::IsNullOrWhiteSpace($env:AWS_DEFAULT_REGION)) {
            return $env:AWS_DEFAULT_REGION
        }
        return ""
    }
    return $region
}

$started = [DateTimeOffset]::UtcNow
$checks = New-Object System.Collections.Generic.List[object]
$hardFail = $false

$awsCli = Get-Command aws -ErrorAction SilentlyContinue
if ($null -eq $awsCli) {
    $checks.Add((New-CheckResult -Name "aws_cli_present" -Status "FAIL" -Detail "aws CLI not found in PATH")) | Out-Null
    $hardFail = $true
} else {
    $checks.Add((New-CheckResult -Name "aws_cli_present" -Status "PASS" -Detail "aws CLI available")) | Out-Null
}

$tfCli = Get-Command terraform -ErrorAction SilentlyContinue
if ($null -eq $tfCli) {
    $checks.Add((New-CheckResult -Name "terraform_present" -Status "FAIL" -Detail "terraform not found in PATH")) | Out-Null
    $hardFail = $true
} else {
    $checks.Add((New-CheckResult -Name "terraform_present" -Status "PASS" -Detail "terraform available")) | Out-Null
}

$identity = $null
if (-not $hardFail) {
    $sts = Invoke-AwsText -Arguments @("sts", "get-caller-identity", "--output", "json")
    if ($sts.code -ne 0) {
        $checks.Add((New-CheckResult -Name "aws_identity" -Status "FAIL" -Detail ("sts get-caller-identity failed: " + $sts.output))) | Out-Null
        $hardFail = $true
    } else {
        try {
            $identity = $sts.output | ConvertFrom-Json
            $checks.Add((New-CheckResult -Name "aws_identity" -Status "PASS" -Detail ("arn=" + $identity.Arn + "; account=" + $identity.Account))) | Out-Null
        } catch {
            $checks.Add((New-CheckResult -Name "aws_identity" -Status "FAIL" -Detail "unable to parse sts identity json")) | Out-Null
            $hardFail = $true
        }
    }
}

$resolvedRegion = Resolve-Region
if ([string]::IsNullOrWhiteSpace($resolvedRegion)) {
    $checks.Add((New-CheckResult -Name "aws_region_configured" -Status "FAIL" -Detail "region is unset in aws config and env")) | Out-Null
    $hardFail = $true
} elseif ($resolvedRegion -ne $RequiredRegion) {
    $checks.Add((New-CheckResult -Name "aws_region_configured" -Status "FAIL" -Detail ("resolved region '" + $resolvedRegion + "' does not match required '" + $RequiredRegion + "'"))) | Out-Null
    $hardFail = $true
} else {
    $checks.Add((New-CheckResult -Name "aws_region_configured" -Status "PASS" -Detail ("region=" + $resolvedRegion))) | Out-Null
}

$ssmNames = @(
    "$SsmPrefix/confluent/bootstrap",
    "$SsmPrefix/confluent/api_key",
    "$SsmPrefix/confluent/api_secret"
)

$ssmMissing = New-Object System.Collections.Generic.List[string]
foreach ($name in $ssmNames) {
    $res = Invoke-AwsText -Arguments @("ssm", "get-parameter", "--name", $name, "--with-decryption", "--query", "Parameter.Version", "--output", "text")
    if ($res.code -ne 0) {
        $ssmMissing.Add($name) | Out-Null
    }
}

if ($ssmMissing.Count -gt 0) {
    $detail = "missing handles: " + ($ssmMissing -join ", ")
    if ($AllowMissingConfluentHandles) {
        $checks.Add((New-CheckResult -Name "ssm_handles_present" -Status "WARN" -Detail $detail)) | Out-Null
    } else {
        $checks.Add((New-CheckResult -Name "ssm_handles_present" -Status "FAIL" -Detail $detail)) | Out-Null
        $hardFail = $true
    }
} else {
    $checks.Add((New-CheckResult -Name "ssm_handles_present" -Status "PASS" -Detail "required dev_min confluent handles present")) | Out-Null
}

$confluentProbeStatus = "WARN"
$confluentProbeDetail = "skipped"
if ($SkipConfluentApiProbe) {
    $confluentProbeStatus = "WARN"
    $confluentProbeDetail = "skipped by flag"
} elseif ($ssmMissing.Count -gt 0) {
    $confluentProbeStatus = "FAIL"
    $confluentProbeDetail = "cannot probe without required ssm handles"
    $hardFail = $true
} else {
    $bootstrapRes = Invoke-AwsText -Arguments @("ssm", "get-parameter", "--name", "$SsmPrefix/confluent/bootstrap", "--with-decryption", "--query", "Parameter.Value", "--output", "text")
    $keyRes = Invoke-AwsText -Arguments @("ssm", "get-parameter", "--name", "$SsmPrefix/confluent/api_key", "--with-decryption", "--query", "Parameter.Value", "--output", "text")
    $secretRes = Invoke-AwsText -Arguments @("ssm", "get-parameter", "--name", "$SsmPrefix/confluent/api_secret", "--with-decryption", "--query", "Parameter.Value", "--output", "text")
    if ($bootstrapRes.code -ne 0 -or $keyRes.code -ne 0 -or $secretRes.code -ne 0) {
        $confluentProbeStatus = "FAIL"
        $confluentProbeDetail = "failed to resolve confluent secrets from ssm"
        $hardFail = $true
    } else {
        $bootstrap = $bootstrapRes.output
        $apiKey = $keyRes.output
        $apiSecret = $secretRes.output
        if ([string]::IsNullOrWhiteSpace($bootstrap) -or [string]::IsNullOrWhiteSpace($apiKey) -or [string]::IsNullOrWhiteSpace($apiSecret)) {
            $confluentProbeStatus = "FAIL"
            $confluentProbeDetail = "one or more confluent secret values are empty"
            $hardFail = $true
        } else {
            try {
                $pair = "{0}:{1}" -f $apiKey, $apiSecret
                $authBytes = [System.Text.Encoding]::UTF8.GetBytes($pair)
                $auth = [Convert]::ToBase64String($authBytes)
                $headers = @{ Authorization = "Basic $auth" }
                $null = Invoke-RestMethod -Uri "https://api.confluent.cloud/iam/v2/api-keys" -Headers $headers -Method Get -TimeoutSec 20
                $confluentProbeStatus = "PASS"
                $confluentProbeDetail = "confluent api auth check passed"
            } catch {
                $confluentProbeStatus = "FAIL"
                $confluentProbeDetail = "confluent api auth check failed"
                $hardFail = $true
            }
        }
    }
}
$checks.Add((New-CheckResult -Name "confluent_api_probe" -Status $confluentProbeStatus -Detail $confluentProbeDetail)) | Out-Null

$bucketsRes = Invoke-AwsText -Arguments @("s3api", "list-buckets", "--query", "Buckets[].Name", "--output", "json")
if ($bucketsRes.code -ne 0) {
    $checks.Add((New-CheckResult -Name "aws_s3_list_buckets" -Status "FAIL" -Detail "unable to list buckets")) | Out-Null
    $hardFail = $true
} else {
    $checks.Add((New-CheckResult -Name "aws_s3_list_buckets" -Status "PASS" -Detail "bucket inventory readable")) | Out-Null
}

$trackedEnv = (& git ls-files ".env*" 2>$null | Out-String).Trim()
if ([string]::IsNullOrWhiteSpace($trackedEnv)) {
    $checks.Add((New-CheckResult -Name "secret_hygiene_git_tracked_env" -Status "PASS" -Detail "no .env* files are git-tracked")) | Out-Null
} else {
    $checks.Add((New-CheckResult -Name "secret_hygiene_git_tracked_env" -Status "FAIL" -Detail ".env* files are tracked in git")) | Out-Null
    $hardFail = $true
}

$finished = [DateTimeOffset]::UtcNow
$summary = [PSCustomObject]@{
    started_at_utc = $started.ToString("o")
    finished_at_utc = $finished.ToString("o")
    required_region = $RequiredRegion
    resolved_region = $resolvedRegion
    aws_account = if ($null -ne $identity) { $identity.Account } else { "" }
    aws_principal_arn = if ($null -ne $identity) { $identity.Arn } else { "" }
    ssm_prefix = $SsmPrefix
    checks = $checks
    decision = if ($hardFail) { "FAIL_CLOSED" } else { "PASS" }
}

$json = $summary | ConvertTo-Json -Depth 6

if (-not [string]::IsNullOrWhiteSpace($OutputPath)) {
    $dir = Split-Path -Parent $OutputPath
    if (-not [string]::IsNullOrWhiteSpace($dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    Set-Content -Path $OutputPath -Value $json -Encoding UTF8
}

$summary.checks | ForEach-Object {
    Write-Output ("[{0}] {1}: {2}" -f $_.status, $_.name, $_.detail)
}
Write-Output ("Decision: " + $summary.decision)
if (-not [string]::IsNullOrWhiteSpace($OutputPath)) {
    Write-Output ("Output: " + $OutputPath)
}

if ($summary.decision -eq "FAIL_CLOSED") {
    exit 2
}
exit 0
