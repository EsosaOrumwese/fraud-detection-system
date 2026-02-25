Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$assetsRoot = Join-Path $repoRoot "docs/design/platform/assets/icons"
$awsDest = Join-Path $assetsRoot "aws"
$toolsDest = Join-Path $assetsRoot "tools"

New-Item -ItemType Directory -Force -Path $awsDest | Out-Null
New-Item -ItemType Directory -Force -Path $toolsDest | Out-Null

function Download-Svg {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 30
    if ($resp.StatusCode -ne 200 -or $resp.Content -notmatch "<svg") {
        throw "Expected SVG response from $Url"
    }
    Set-Content -Path $Destination -Value $resp.Content -Encoding UTF8
}

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("aws-svg-icons-" + [System.Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null

try {
    Push-Location $tempRoot
    try {
        npm pack aws-svg-icons | Out-Null
        $tgz = Get-ChildItem -Filter "aws-svg-icons-*.tgz" | Select-Object -First 1 -ExpandProperty FullName
        if (-not $tgz) {
            throw "Failed to download aws-svg-icons package."
        }
        tar -xf $tgz -C $tempRoot
    }
    finally {
        Pop-Location
    }

    $base = Join-Path $tempRoot "package/lib/Architecture-Service-Icons_07302021"
    if (-not (Test-Path $base)) {
        throw "Expected AWS icon payload at $base"
    }

    $awsMap = @{
        "apigateway.svg"   = "Arch_App-Integration/Arch_64/Arch_Amazon-API-Gateway_64.svg"
        "budgets.svg"      = "Arch_AWS-Cost-Management/64/Arch_AWS-Budgets_64.svg"
        "cloudwatch.svg"   = "Arch_Management-Governance/64/Arch_Amazon-CloudWatch_64.svg"
        "dynamodb.svg"     = "Arch_Database/64/Arch_Amazon-DynamoDB_64.svg"
        "ecs.svg"          = "Arch_Containers/64/Arch_Amazon-Elastic-Container-Service_64.svg"
        "eks.svg"          = "Arch_Containers/64/Arch_Amazon-Elastic-Kubernetes-Service_64.svg"
        "glue.svg"         = "Arch_Analytics/Arch_64/Arch_AWS-Glue_64.svg"
        "iam.svg"          = "Arch_Security-Identity-Compliance/64/Arch_AWS-Identity-and-Access-Management_64.svg"
        "kinesis.svg"      = "Arch_Analytics/Arch_64/Arch_Amazon-Kinesis_64.svg"
        "kms.svg"          = "Arch_Security-Identity-Compliance/64/Arch_AWS-Key-Management-Service_64.svg"
        "lambda.svg"       = "Arch_Compute/64/Arch_AWS-Lambda_64.svg"
        "msk.svg"          = "Arch_Analytics/Arch_64/Arch_Amazon-Managed-Streaming-for-Apache-Kafka_64.svg"
        "mwaa.svg"         = "Arch_App-Integration/Arch_64/Arch_Amazon-Managed-Workflows-for-Apache-Airflow_64.svg"
        "rds.svg"          = "Arch_Database/64/Arch_Amazon-RDS_64.svg"
        "s3.svg"           = "Arch_Storage/64/Arch_Amazon-Simple-Storage-Service_64.svg"
        "sagemaker.svg"    = "Arch_Machine-Learning/64/Arch_Amazon-SageMaker_64.svg"
        "sqs.svg"          = "Arch_App-Integration/Arch_64/Arch_Amazon-Simple-Queue-Service_64.svg"
        "ssm.svg"          = "Arch_Management-Governance/64/Arch_AWS-Systems-Manager_64.svg"
        "stepfunctions.svg" = "Arch_App-Integration/Arch_64/Arch_AWS-Step-Functions_64.svg"
        "vpc.svg"          = "Arch_Networking-Content-Delivery/64/Arch_Amazon-Virtual-Private-Cloud_64.svg"
    }

    foreach ($file in $awsMap.Keys) {
        $src = Join-Path $base $awsMap[$file]
        if (-not (Test-Path $src)) {
            throw "Missing source icon: $src"
        }
        Copy-Item -Path $src -Destination (Join-Path $awsDest $file) -Force
    }

    $toolSources = @(
        @{ url = "https://cdn.simpleicons.org/githubactions"; file = "github_actions.svg" },
        @{ url = "https://cdn.simpleicons.org/terraform"; file = "terraform.svg" },
        @{ url = "https://cdn.simpleicons.org/terraform"; file = "tfstate.svg" },
        @{ url = "https://cdn.simpleicons.org/databricks"; file = "databricks.svg" },
        @{ url = "https://static.cdnlogo.com/logos/c/8/confluent.svg"; file = "confluent.svg" }
    )

    foreach ($item in $toolSources) {
        Download-Svg -Url $item.url -Destination (Join-Path $toolsDest $item.file)
    }

    Write-Output "Platform graph logos updated in docs/design/platform/assets/icons"
}
finally {
    if (Test-Path $tempRoot) {
        Remove-Item -Recurse -Force $tempRoot
    }
}
