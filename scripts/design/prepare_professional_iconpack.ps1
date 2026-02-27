param(
  [string]$AwsPackageRoot = "docs/design/platform/assets/aws_official_icon_package_2026Q1",
  [string]$OutputDir = "docs/design/platform/assets/iconpack_professional",
  [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-AwsIcon {
  param(
    [string]$Root,
    [string]$FileName
  )
  $match = Get-ChildItem -Path $Root -Recurse -File -Filter $FileName |
    Where-Object { $_.FullName -notmatch "\\__MACOSX\\" } |
    Select-Object -First 1
  if ($null -eq $match) {
    throw "Could not find AWS icon: $FileName"
  }
  return $match.FullName
}

$root = (Resolve-Path ".").Path
$awsAbs = Join-Path $root $AwsPackageRoot
$outAbs = Join-Path $root $OutputDir

if (-not (Test-Path $awsAbs)) {
  throw "AWS package root not found: $awsAbs"
}
New-Item -ItemType Directory -Path $outAbs -Force | Out-Null

$awsMap = @{
  "s3.png"       = "Arch_Amazon-Simple-Storage-Service_64.png"
  "dynamodb.png" = "Arch_Amazon-DynamoDB_64.png"
  "ecs.png"      = "Arch_Amazon-Elastic-Container-Service_64.png"
  "rds.png"      = "Arch_Amazon-RDS_64.png"
  "kinesis.png"  = "Arch_Amazon-Kinesis-Data-Streams_64.png"
  "cloudwatch.png" = "Arch_Amazon-CloudWatch_64.png"
  "budget.png"   = "Arch_AWS-Budgets_64.png"
  "vpc.png"      = "Virtual-private-cloud-VPC_32.png"
  "subnet.png"   = "Public-subnet_32.png"
}

foreach ($entry in $awsMap.GetEnumerator()) {
  $dest = Join-Path $outAbs $entry.Key
  if ((-not $Force) -and (Test-Path $dest)) { continue }
  $src = Resolve-AwsIcon -Root $awsAbs -FileName $entry.Value
  Copy-Item -Path $src -Destination $dest -Force
}

$svgMap = @(
  @{ Name = "aws.svg"; Icon = "simple-icons:amazonwebservices"; Color = "232F3E" },
  @{ Name = "terraform.svg"; Icon = "simple-icons:terraform"; Color = "7B42BC" },
  @{ Name = "kafka.svg"; Icon = "simple-icons:apachekafka"; Color = "231F20" },
  @{ Name = "postgres.svg"; Icon = "simple-icons:postgresql"; Color = "336791" },
  @{ Name = "key.svg"; Icon = "mdi:key"; Color = "1F2937" },
  @{ Name = "doc.svg"; Icon = "mdi:file-document-check"; Color = "334155" },
  @{ Name = "security.svg"; Icon = "mdi:shield-lock"; Color = "B91C1C" },
  @{ Name = "route.svg"; Icon = "mdi:source-branch"; Color = "2563EB" },
  @{ Name = "gateway.svg"; Icon = "mdi:router-network"; Color = "0369A1" },
  @{ Name = "internet.svg"; Icon = "mdi:web"; Color = "475569" },
  @{ Name = "note.svg"; Icon = "mdi:alert-outline"; Color = "D97706" },
  @{ Name = "person.svg"; Icon = "mdi:account"; Color = "475569" }
)

foreach ($entry in $svgMap) {
  $svgOut = Join-Path $outAbs $entry.Name
  if ((-not $Force) -and (Test-Path $svgOut)) { continue }
  $encodedIcon = [Uri]::EscapeDataString([string]$entry.Icon)
  $url = "https://api.iconify.design/$encodedIcon.svg?color=%23$($entry.Color)"
  Invoke-WebRequest -Uri $url -OutFile $svgOut
}

$mountSpec = "${root}:/work"
$svgFiles = Get-ChildItem -Path $outAbs -Filter "*.svg" -File
foreach ($svg in $svgFiles) {
  $png = Join-Path $svg.DirectoryName ($svg.BaseName + ".png")
  if ((-not $Force) -and (Test-Path $png)) { continue }
  $svgRel = $svg.FullName.Substring($root.Length).TrimStart('\', '/') -replace "\\", "/"
  $pngRel = $png.Substring($root.Length).TrimStart('\', '/') -replace "\\", "/"
  $cmd = "magick /work/$svgRel /work/$pngRel"
  & docker run --rm -v $mountSpec -w /work --entrypoint /bin/sh dpokidov/imagemagick:latest -c $cmd
  if ($LASTEXITCODE -ne 0) {
    throw "Failed PNG conversion for: $($svg.FullName)"
  }
}

Write-Host "Professional iconpack ready at: $outAbs"
