param(
  [string]$DotRoot = "docs/design/platform/dev_min/architecture/with_icons",
  [string]$IconRootRelative = "/workspace/docs/design/platform/assets/iconpack_professional_18"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$tagMap = @{
  "S3"        = "s3.png"
  "DDB"       = "dynamodb.png"
  "BUDGET"    = "budget.png"
  "CLOUD"     = "aws.png"
  "KAFKA"     = "kafka.png"
  "KEY"       = "key.png"
  "ARTIFACT"  = "doc.png"
  "ECS"       = "ecs.png"
  "RDS"       = "rds.png"
  "KINESIS"   = "kinesis.png"
  "SSM"       = "key.png"
  "VPC"       = "vpc.png"
  "SG"        = "security.png"
  "LOG"       = "cloudwatch.png"
  "SA"        = "person.png"
  "INTERNET"  = "internet.png"
  "IGW"       = "gateway.png"
  "RT"        = "route.png"
  "ROUTE"     = "route.png"
  "SUBNET"    = "subnet.png"
  "ASSOC"     = "route.png"
  "DB-SUBNET" = "subnet.png"
  "NOTE"      = "note.png"
}

$nodeFallback = @{
  "auth_config" = "terraform.png"
  "auth_tf_state" = "s3.png"
  "auth_tf_lock" = "dynamodb.png"
}

$fileScopedNoIconNodes = @{
  # Engineering view is intentionally dense. Keep icons on primary infra resources and
  # suppress them on many helper/parameter nodes for readability.
  "dev_min_engineering_view.graphviz.dot" = @(
    "dm_remote_state",
    "dm_task_control",
    "dm_task_oracle",
    "dm_task_reporter",
    "dm_task_migrations",
    "dm_ssm_bootstrap",
    "dm_ssm_key",
    "dm_ssm_secret",
    "dm_ssm_db_user",
    "dm_ssm_db_password",
    "dm_ssm_db_dsn",
    "dm_ssm_ig_api",
    "dm_manifest",
    "dm_catalog",
    "cf_sa_runtime",
    "cf_sa_manager",
    "cf_api_runtime",
    "cf_api_manager",
    "cf_ssm_bootstrap",
    "cf_ssm_key",
    "cf_ssm_secret"
  )
}

function Resolve-IconFromNode {
  param(
    [string]$NodeId,
    [string]$Attrs
  )
  $id = $NodeId.ToLowerInvariant()
  $a = $Attrs.ToLowerInvariant()

  if ($id -match '^(core_s3|truth_s3|auth_tf_state)' -or $id -match 's3_' -or $a -match 'label="[^"]*s3') { return "s3.png" }
  if ($id -match 'ddb|dynamo|lock' -or $a -match 'label="[^"]*dynamodb') { return "dynamodb.png" }
  if ($id -match 'budget' -or $a -match 'label="[^"]*budget') { return "budget.png" }
  if ($id -match 'ssm|api|key|cred' -or $a -match 'label="[^"]*(ssm|key|credential)') { return "key.png" }
  if ($id -match 'kinesis' -or $a -match 'label="[^"]*kinesis') { return "kinesis.png" }
  if ($id -match 'ecs|service_|task_|dm_ecs_cluster|runtime-probe|daemons' -or $a -match 'label="[^"]*ecs') { return "ecs.png" }
  if ($id -match '(subnet|db_subnet)' -or $a -match 'label="[^"]*(aws_subnet|db_subnet_group|public subnet|private subnet)') { return "subnet.png" }
  if ($id -match 'rds|postgres|db_instance|db_' -or $a -match 'label="[^"]*(rds|postgres)') { return "rds.png" }
  if ($id -match 'kafka|topic|cf_' -or $a -match 'label="[^"]*(kafka|confluent)') { return "kafka.png" }
  if ($id -match 'cloudwatch|logs' -or $a -match 'label="[^"]*cloudwatch') { return "cloudwatch.png" }
  if ($id -match 'vpc' -or $a -match 'label="[^"]*vpc') { return "vpc.png" }
  if ($id -match 'igw|gateway' -or $a -match 'label="[^"]*gateway') { return "gateway.png" }
  if ($id -match 'route|rt_|rta' -or $a -match 'label="[^"]*route') { return "route.png" }
  if ($id -match 'sg_' -or $a -match 'label="[^"]*security group') { return "security.png" }
  if ($id -match 'internet' -or $a -match 'label="[^"]*public internet') { return "internet.png" }
  if ($id -match 'manifest|catalog|artifact' -or $a -match 'label="[^"]*(manifest|catalog|artifact)') { return "doc.png" }
  if ($id -match 'sa_|runtime user|topic-manager' -or $a -match 'label="[^"]*service account') { return "person.png" }
  if ($id -match 'auth_config|remote_state' -or $a -match 'label="[^"]*(terraform|remote_state)') { return "terraform.png" }
  return $null
}

$root = (Resolve-Path ".").Path
$dotAbs = Join-Path $root $DotRoot
if (-not (Test-Path $dotAbs)) {
  throw "Dot root not found: $dotAbs"
}

$files = Get-ChildItem -Path $dotAbs -Filter "*.graphviz.dot" -File
foreach ($file in $files) {
  $fileName = $file.Name
  $suppressSet = @{}
  if ($fileScopedNoIconNodes.ContainsKey($fileName)) {
    foreach ($node in $fileScopedNoIconNodes[$fileName]) { $suppressSet[$node] = $true }
  }

  $lines = Get-Content $file.FullName
  $outLines = foreach ($line in $lines) {
    $m = [regex]::Match($line, '^(?<indent>\s*)(?<id>[A-Za-z0-9_]+)\s+\[(?<attrs>.+)\];\s*$')
    if (-not $m.Success) { $line; continue }

    $indent = $m.Groups["indent"].Value
    $id = $m.Groups["id"].Value
    $attrs = $m.Groups["attrs"].Value

    if ($attrs -match 'shape=note') {
      # Keep note shapes simple and readable.
      "$indent$id [$attrs];"
      continue
    }

    # Reset previously injected image settings if present.
    $attrs = [regex]::Replace($attrs, '\s*,?\s*image="[^"]*"', '')
    $attrs = [regex]::Replace($attrs, '\s*,?\s*imagescale=(true|false)', '')
    $attrs = [regex]::Replace($attrs, '\s*,?\s*imagepos="[^"]*"', '')
    $attrs = [regex]::Replace($attrs, '\s*,?\s*labelloc="[^"]*"', '')

    $icon = $null
    $tagMatch = [regex]::Match($attrs, 'label="\[(?<tag>[A-Z0-9-]+)\]\s*')
    if ($tagMatch.Success) {
      $tag = $tagMatch.Groups["tag"].Value
      if ($tagMap.ContainsKey($tag)) {
        $icon = $tagMap[$tag]
        $attrs = [regex]::Replace($attrs, 'label="\[[A-Z0-9-]+\]\s*', 'label="', 1)
      }
    }
    if (($null -eq $icon) -and $nodeFallback.ContainsKey($id)) {
      $icon = $nodeFallback[$id]
    }
    if ($null -eq $icon) {
      $icon = Resolve-IconFromNode -NodeId $id -Attrs $attrs
    }

    if ($suppressSet.ContainsKey($id)) {
      $icon = $null
    }

    if ($null -eq $icon) {
      "$indent$id [$attrs];"
      continue
    }

    $iconPath = "$IconRootRelative/$icon"
    $attrs = "$attrs, image=""$iconPath"", imagescale=true, imagepos=""ml"", labelloc=""b"""
    "$indent$id [$attrs];"
  }

  Set-Content -Path $file.FullName -Value $outLines -Encoding utf8
}

Write-Host "Applied professional icon mapping to: $dotAbs"
