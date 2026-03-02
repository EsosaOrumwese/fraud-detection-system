param(
  [Parameter(Mandatory = $true)][string]$Region,
  [Parameter(Mandatory = $true)][string]$VirtualClusterId,
  [Parameter(Mandatory = $true)][string]$ExecutionRoleArn,
  [Parameter(Mandatory = $true)][string]$ReleaseLabel,
  [Parameter(Mandatory = $true)][string]$ScriptS3Uri,
  [Parameter(Mandatory = $true)][string]$PlatformRunId,
  [Parameter(Mandatory = $true)][string]$ScenarioRunId,
  [Parameter(Mandatory = $true)][string]$WspRef,
  [Parameter(Mandatory = $true)][string]$SrReadyRef,
  [string]$LogGroupName = "/emr-eks/fraud-platform-dev-full",
  [int]$Iterations = 900,
  [double]$SleepSeconds = 1.0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Start-LaneJob {
  param(
    [Parameter(Mandatory = $true)][string]$LaneRef,
    [Parameter(Mandatory = $true)][string]$LogPrefix
  )

  $jobDriver = @{
    sparkSubmitJobDriver = @{
      entryPoint          = $ScriptS3Uri
      entryPointArguments = @(
        "--lane-ref", $LaneRef,
        "--platform-run-id", $PlatformRunId,
        "--scenario-run-id", $ScenarioRunId,
        "--iterations", "$Iterations",
        "--sleep-seconds", "$SleepSeconds"
      )
      sparkSubmitParameters = "--conf spark.executor.instances=1 --conf spark.executor.cores=1 --conf spark.executor.memory=1G --conf spark.driver.memory=1G"
    }
  } | ConvertTo-Json -Depth 10 -Compress

  $monitoring = @{
    monitoringConfiguration = @{
      persistentAppUI = "ENABLED"
      cloudWatchMonitoringConfiguration = @{
        logGroupName        = $LogGroupName
        logStreamNamePrefix = $LogPrefix
      }
    }
  } | ConvertTo-Json -Depth 10 -Compress

  $jobDriverFile = Join-Path $env:TEMP ("m6_job_driver_" + [guid]::NewGuid().ToString() + ".json")
  $monitoringFile = Join-Path $env:TEMP ("m6_monitoring_" + [guid]::NewGuid().ToString() + ".json")

  try {
    Set-Content -Path $jobDriverFile -Value $jobDriver -Encoding utf8
    Set-Content -Path $monitoringFile -Value $monitoring -Encoding utf8

    $response = aws emr-containers start-job-run `
      --region $Region `
      --name $LaneRef `
      --virtual-cluster-id $VirtualClusterId `
      --execution-role-arn $ExecutionRoleArn `
      --release-label $ReleaseLabel `
      --job-driver ("file://{0}" -f $jobDriverFile) `
      --configuration-overrides ("file://{0}" -f $monitoringFile) `
      | ConvertFrom-Json
  }
  finally {
    Remove-Item -Path $jobDriverFile -Force -ErrorAction SilentlyContinue
    Remove-Item -Path $monitoringFile -Force -ErrorAction SilentlyContinue
  }

  if (-not $response.id) {
    throw "Failed to start EMR job for lane ref $LaneRef"
  }
  return [string]$response.id
}

$wspJobId = Start-LaneJob -LaneRef $WspRef -LogPrefix "wsp-stream"
$srJobId = Start-LaneJob -LaneRef $SrReadyRef -LogPrefix "sr-ready"

[pscustomobject]@{
  started_at_utc = (Get-Date).ToUniversalTime().ToString("o")
  virtual_cluster_id = $VirtualClusterId
  wsp_ref = $WspRef
  wsp_job_id = $wspJobId
  sr_ready_ref = $SrReadyRef
  sr_ready_job_id = $srJobId
} | ConvertTo-Json -Depth 6
