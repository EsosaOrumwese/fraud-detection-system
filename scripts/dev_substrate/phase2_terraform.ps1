param(
    [ValidateSet("plan", "up", "down", "down_all", "status", "post_destroy_check")]
    [string]$Action,
    [string]$TerraformDir = "infra/terraform/envs/dev_min",
    [string]$Workspace = "dev_min_demo",
    [string]$OutputRoot = "runs/fraud-platform/dev_substrate/phase2",
    [switch]$AllowPaidApply,
    [switch]$AllowPaidDestroyAll,
    [switch]$AutoApprove
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function New-CheckResult {
    param(
        [string]$Name,
        [string]$Status,
        [string]$Detail
    )
    [PSCustomObject]@{
        name = $Name
        status = $Status
        detail = $Detail
    }
}

function Parse-Bool {
    param(
        [string]$Value,
        [bool]$DefaultValue
    )
    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $DefaultValue
    }
    $v = $Value.Trim().ToLowerInvariant()
    return $v -in @("1", "true", "yes", "on")
}

function Require-Env {
    param([string]$Name)
    $value = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "Missing required environment variable: $Name"
    }
    return $value.Trim()
}

function Optional-Env {
    param(
        [string]$Name,
        [string]$DefaultValue = ""
    )
    $value = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $DefaultValue
    }
    return $value.Trim()
}

function Normalize-VersioningStatus {
    param(
        [string]$Value,
        [string]$Name,
        [string]$DefaultValue
    )
    $raw = $Value
    if ([string]::IsNullOrWhiteSpace($raw)) {
        $raw = $DefaultValue
    }
    $normalized = $raw.Trim().ToLowerInvariant()
    switch ($normalized) {
        "enabled" { return "Enabled" }
        "suspended" { return "Suspended" }
        default { throw "Invalid $Name value '$raw' (expected Enabled or Suspended)" }
    }
}

function Invoke-Terraform {
    param([string[]]$Arguments)
    $output = & terraform @Arguments 2>&1
    $code = $LASTEXITCODE
    [PSCustomObject]@{
        code = $code
        output = ($output | Out-String).Trim()
        command = "terraform " + ($Arguments -join " ")
    }
}

function Ensure-TerraformWorkspace {
    param(
        [string]$Directory,
        [string]$WorkspaceName
    )
    $select = Invoke-Terraform -Arguments @("-chdir=$Directory", "workspace", "select", $WorkspaceName)
    if ($select.code -eq 0) {
        return
    }
    $create = Invoke-Terraform -Arguments @("-chdir=$Directory", "workspace", "new", $WorkspaceName)
    if ($create.code -ne 0) {
        throw "Unable to select or create workspace '$WorkspaceName': $($create.output)"
    }
}

function Write-Evidence {
    param(
        [string]$Root,
        [string]$ActionName,
        [object]$Payload
    )
    New-Item -ItemType Directory -Path $Root -Force | Out-Null
    $stamp = [DateTimeOffset]::UtcNow.ToString("yyyyMMddTHHmmssZ")
    $path = Join-Path $Root ("infra_phase2_{0}_{1}.json" -f $stamp, $ActionName)
    $json = $Payload | ConvertTo-Json -Depth 8
    Set-Content -Path $path -Value $json -Encoding UTF8
    return $path
}

$started = [DateTimeOffset]::UtcNow
$checks = New-Object System.Collections.Generic.List[object]
$hardFail = $false

try {
    $tf = Get-Command terraform -ErrorAction SilentlyContinue
    if ($null -eq $tf) {
        throw "terraform CLI not found in PATH"
    }

    if (-not (Test-Path $TerraformDir)) {
        throw "Terraform directory not found: $TerraformDir"
    }

    if ($Action -eq "up" -and -not $AllowPaidApply) {
        throw "phase2-up requires -AllowPaidApply to prevent accidental paid provisioning"
    }

    if ($Action -eq "down_all" -and -not $AllowPaidDestroyAll) {
        throw "phase2-down-all requires -AllowPaidDestroyAll"
    }

    $env:TF_VAR_name_prefix = Optional-Env -Name "DEV_MIN_NAME_PREFIX" -DefaultValue "fraud-platform-dev-min"
    $env:TF_VAR_owner = Optional-Env -Name "DEV_MIN_OWNER" -DefaultValue "fraud-dev"
    $env:TF_VAR_expires_at = Optional-Env -Name "DEV_MIN_EXPIRES_AT"
    $env:TF_VAR_budget_alert_email = Optional-Env -Name "DEV_MIN_BUDGET_ALERT_EMAIL"
    $env:TF_VAR_monthly_budget_limit_usd = Optional-Env -Name "DEV_MIN_BUDGET_LIMIT_USD" -DefaultValue "40"
    $env:TF_VAR_enable_budget_alert = (Parse-Bool -Value (Optional-Env -Name "DEV_MIN_ENABLE_BUDGET_ALERT") -DefaultValue $false).ToString().ToLowerInvariant()
    $env:TF_VAR_demo_log_retention_days = Optional-Env -Name "DEV_MIN_DEMO_LOG_RETENTION_DAYS" -DefaultValue "7"
    $env:TF_VAR_demo_run_id = Optional-Env -Name "DEV_MIN_DEMO_RUN_ID" -DefaultValue "manual"

    $needsVars = $Action -in @("plan", "up", "down", "down_all")
    if ($needsVars) {
        $prefix = $env:TF_VAR_name_prefix
        $env:TF_VAR_aws_region = Require-Env -Name "DEV_MIN_AWS_REGION"
        $env:TF_VAR_object_store_bucket_name = Optional-Env -Name "DEV_MIN_OBJECT_STORE_BUCKET" -DefaultValue ("{0}-object-store" -f $prefix)
        $env:TF_VAR_evidence_bucket_name = Optional-Env -Name "DEV_MIN_EVIDENCE_BUCKET" -DefaultValue ("{0}-evidence" -f $prefix)
        $env:TF_VAR_quarantine_bucket_name = Optional-Env -Name "DEV_MIN_QUARANTINE_BUCKET" -DefaultValue ("{0}-quarantine" -f $prefix)
        $env:TF_VAR_archive_bucket_name = Optional-Env -Name "DEV_MIN_ARCHIVE_BUCKET" -DefaultValue ("{0}-archive" -f $prefix)

        $versioningByRole = [ordered]@{
            object_store = Normalize-VersioningStatus -Value (Optional-Env -Name "DEV_MIN_OBJECT_STORE_VERSIONING_STATUS") -Name "DEV_MIN_OBJECT_STORE_VERSIONING_STATUS" -DefaultValue "Suspended"
            evidence     = Normalize-VersioningStatus -Value (Optional-Env -Name "DEV_MIN_EVIDENCE_VERSIONING_STATUS") -Name "DEV_MIN_EVIDENCE_VERSIONING_STATUS" -DefaultValue "Enabled"
            quarantine   = Normalize-VersioningStatus -Value (Optional-Env -Name "DEV_MIN_QUARANTINE_VERSIONING_STATUS") -Name "DEV_MIN_QUARANTINE_VERSIONING_STATUS" -DefaultValue "Suspended"
            archive      = Normalize-VersioningStatus -Value (Optional-Env -Name "DEV_MIN_ARCHIVE_VERSIONING_STATUS") -Name "DEV_MIN_ARCHIVE_VERSIONING_STATUS" -DefaultValue "Enabled"
            tf_state     = Normalize-VersioningStatus -Value (Optional-Env -Name "DEV_MIN_TF_STATE_VERSIONING_STATUS") -Name "DEV_MIN_TF_STATE_VERSIONING_STATUS" -DefaultValue "Enabled"
        }
        $env:TF_VAR_bucket_versioning_status_by_role = ($versioningByRole | ConvertTo-Json -Compress)
    }

    $tfStateBucket = Optional-Env -Name "DEV_MIN_TF_STATE_BUCKET"
    if (-not [string]::IsNullOrWhiteSpace($tfStateBucket)) {
        $env:TF_VAR_tf_state_bucket_name = $tfStateBucket
    }
    $controlTable = Optional-Env -Name "DEV_MIN_CONTROL_TABLE"
    if (-not [string]::IsNullOrWhiteSpace($controlTable)) {
        $env:TF_VAR_control_table_name = $controlTable
    }
    $igAdmissionTable = Optional-Env -Name "DEV_MIN_IG_ADMISSION_TABLE"
    if (-not [string]::IsNullOrWhiteSpace($igAdmissionTable)) {
        $env:TF_VAR_ig_admission_table_name = $igAdmissionTable
    }
    $igPublishStateTable = Optional-Env -Name "DEV_MIN_IG_PUBLISH_STATE_TABLE"
    if (-not [string]::IsNullOrWhiteSpace($igPublishStateTable)) {
        $env:TF_VAR_ig_publish_state_table_name = $igPublishStateTable
    }
    $lockTable = Optional-Env -Name "DEV_MIN_TF_LOCK_TABLE"
    if (-not [string]::IsNullOrWhiteSpace($lockTable)) {
        $env:TF_VAR_tf_lock_table_name = $lockTable
    }

    $init = Invoke-Terraform -Arguments @("-chdir=$TerraformDir", "init", "-input=false", "-no-color")
    if ($init.code -ne 0) {
        throw "terraform init failed: $($init.output)"
    }
    $checks.Add((New-CheckResult -Name "terraform_init" -Status "PASS" -Detail "init completed")) | Out-Null

    Ensure-TerraformWorkspace -Directory $TerraformDir -WorkspaceName $Workspace
    $checks.Add((New-CheckResult -Name "terraform_workspace" -Status "PASS" -Detail "workspace=$Workspace")) | Out-Null

    switch ($Action) {
        "plan" {
            $env:TF_VAR_enable_core = "true"
            $env:TF_VAR_enable_demo = (Parse-Bool -Value (Optional-Env -Name "DEV_MIN_ENABLE_DEMO") -DefaultValue $true).ToString().ToLowerInvariant()
            $plan = Invoke-Terraform -Arguments @("-chdir=$TerraformDir", "plan", "-input=false", "-no-color")
            if ($plan.code -ne 0) {
                throw "terraform plan failed: $($plan.output)"
            }
            $checks.Add((New-CheckResult -Name "terraform_plan" -Status "PASS" -Detail "plan succeeded")) | Out-Null
        }
        "up" {
            $env:TF_VAR_enable_core = "true"
            $env:TF_VAR_enable_demo = "true"
            $applyArgs = @("-chdir=$TerraformDir", "apply", "-input=false", "-no-color")
            if ($AutoApprove) {
                $applyArgs += "-auto-approve"
            }
            $apply = Invoke-Terraform -Arguments $applyArgs
            if ($apply.code -ne 0) {
                throw "terraform apply (up) failed: $($apply.output)"
            }
            $checks.Add((New-CheckResult -Name "terraform_up" -Status "PASS" -Detail "core+demo applied")) | Out-Null
        }
        "down" {
            $env:TF_VAR_enable_core = "true"
            $env:TF_VAR_enable_demo = "false"
            $applyArgs = @("-chdir=$TerraformDir", "apply", "-input=false", "-no-color")
            if ($AutoApprove) {
                $applyArgs += "-auto-approve"
            }
            $apply = Invoke-Terraform -Arguments $applyArgs
            if ($apply.code -ne 0) {
                throw "terraform apply (down demo) failed: $($apply.output)"
            }
            $checks.Add((New-CheckResult -Name "terraform_down" -Status "PASS" -Detail "demo disabled; core retained")) | Out-Null
        }
        "down_all" {
            $env:TF_VAR_enable_core = "false"
            $env:TF_VAR_enable_demo = "false"
            $applyArgs = @("-chdir=$TerraformDir", "apply", "-input=false", "-no-color")
            if ($AutoApprove) {
                $applyArgs += "-auto-approve"
            }
            $apply = Invoke-Terraform -Arguments $applyArgs
            if ($apply.code -ne 0) {
                throw "terraform apply (down all) failed: $($apply.output)"
            }
            $checks.Add((New-CheckResult -Name "terraform_down_all" -Status "PASS" -Detail "core+demo disabled")) | Out-Null
        }
        "status" {
            $state = Invoke-Terraform -Arguments @("-chdir=$TerraformDir", "state", "list")
            if ($state.code -ne 0) {
                throw "terraform state list failed: $($state.output)"
            }
            $count = 0
            if (-not [string]::IsNullOrWhiteSpace($state.output)) {
                $count = ($state.output -split "`n").Count
            }
            $checks.Add((New-CheckResult -Name "terraform_state_list" -Status "PASS" -Detail "resources_in_state=$count")) | Out-Null

            $outs = Invoke-Terraform -Arguments @("-chdir=$TerraformDir", "output", "-json")
            if ($outs.code -ne 0) {
                throw "terraform output failed: $($outs.output)"
            }
            $checks.Add((New-CheckResult -Name "terraform_output" -Status "PASS" -Detail "output_json_available")) | Out-Null
        }
        "post_destroy_check" {
            $res = & aws resourcegroupstaggingapi get-resources `
                --tag-filters Key=fp_env,Values=dev_min Key=fp_tier,Values=demo `
                --query "ResourceTagMappingList[].ResourceARN" `
                --output json 2>&1
            if ($LASTEXITCODE -ne 0) {
                throw "aws resourcegroupstaggingapi get-resources failed"
            }
            $arns = @()
            try {
                $parsed = ($res | Out-String | ConvertFrom-Json)
                if ($null -ne $parsed) {
                    $arns = @($parsed)
                }
            } catch {
                throw "unable to parse post_destroy_check response"
            }
            if ($arns.Count -gt 0) {
                $checks.Add((New-CheckResult -Name "post_destroy_residual_demo_resources" -Status "FAIL" -Detail ("residual_demo_resources=" + $arns.Count))) | Out-Null
                $hardFail = $true
            } else {
                $checks.Add((New-CheckResult -Name "post_destroy_residual_demo_resources" -Status "PASS" -Detail "no demo-tier resources detected")) | Out-Null
            }
        }
    }
} catch {
    $hardFail = $true
    $checks.Add((New-CheckResult -Name "phase2_action" -Status "FAIL" -Detail $_.Exception.Message)) | Out-Null
}

$finished = [DateTimeOffset]::UtcNow
$summary = [PSCustomObject]@{
    started_at_utc = $started.ToString("o")
    finished_at_utc = $finished.ToString("o")
    action = $Action
    terraform_dir = $TerraformDir
    workspace = $Workspace
    decision = if ($hardFail) { "FAIL_CLOSED" } else { "PASS" }
    checks = $checks
}

$evidencePath = Write-Evidence -Root $OutputRoot -ActionName $Action -Payload $summary
$summary.checks | ForEach-Object {
    Write-Output ("[{0}] {1}: {2}" -f $_.status, $_.name, $_.detail)
}
Write-Output ("Decision: " + $summary.decision)
Write-Output ("Evidence: " + $evidencePath)

if ($hardFail) {
    exit 2
}
exit 0
