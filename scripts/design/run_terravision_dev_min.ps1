param(
    [ValidateSet("all", "core", "confluent", "demo")]
    [string]$Target = "all",
    [string]$Image = "patrickchugh/terravision:latest",
    [string]$OutputRoot = "docs/design/platform/terraform/dev_min",
    [string[]]$Formats = @("svg", "png"),
    [string]$Workspace = "default",
    [switch]$PullImage,
    [switch]$Show,
    [switch]$UseExampleVarfile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Assert-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found on PATH: $Name"
    }
}

function Assert-DockerDaemon {
    docker info 1>$null 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker daemon is not running. Start Docker Desktop, then rerun this script."
    }
}

function Resolve-Varfile {
    param(
        [string]$ModuleRoot,
        [switch]$UseExample
    )
    $primary = Join-Path $ModuleRoot "terraform.tfvars"
    if (Test-Path $primary) {
        return $primary
    }
    if ($UseExample) {
        $example = Join-Path $ModuleRoot "terraform.tfvars.example"
        if (Test-Path $example) {
            return $example
        }
    }
    return $null
}

Assert-Command -Name "docker"
Assert-DockerDaemon

if ($PullImage) {
    Write-Host "Pulling image: $Image"
    docker pull $Image | Out-Host
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$repoRootUnix = $repoRoot -replace "\\", "/"
$outputRootHost = Join-Path $repoRoot $OutputRoot

$modules = switch ($Target) {
    "all" { @("core", "confluent", "demo") }
    default { @($Target) }
}

$awsCredsHost = Join-Path $env:USERPROFILE ".aws"
$awsMountArgs = @()
if (Test-Path $awsCredsHost) {
    $awsMountArgs = @("-v", "${awsCredsHost}:/home/terravision/.aws:ro")
}

foreach ($module in $modules) {
    $moduleRootHost = Join-Path $repoRoot "infra/terraform/dev_min/$module"
    if (-not (Test-Path $moduleRootHost)) {
        throw "Terraform root not found: $moduleRootHost"
    }

    $moduleOutputHost = Join-Path $outputRootHost $module
    New-Item -ItemType Directory -Path $moduleOutputHost -Force | Out-Null

    $varfileHost = Resolve-Varfile -ModuleRoot $moduleRootHost -UseExample:$UseExampleVarfile
    if ($null -eq $varfileHost) {
        Write-Warning "No varfile found for '$module' (terraform.tfvars). Terravision will run without --varfile."
    }

    $sourceContainer = "/workspace/infra/terraform/dev_min/$module"
    $varfileContainer = if ($varfileHost) {
        $rel = Resolve-Path -Relative $varfileHost
        "/workspace/" + ($rel -replace "^[.][/\\]", "" -replace "\\", "/")
    } else {
        $null
    }

    foreach ($format in $Formats) {
        $outfileContainer = "/workspace/$OutputRoot/$module/architecture-$module"
        $dockerArgs = @(
            "run", "--rm",
            "-v", "${repoRootUnix}:/workspace"
        ) + $awsMountArgs + @(
            "-w", "/workspace",
            $Image,
            "draw",
            "--source", $sourceContainer,
            "--workspace", $Workspace,
            "--outfile", $outfileContainer,
            "--format", $format
        )

        if ($varfileContainer) {
            $dockerArgs += @("--varfile", $varfileContainer)
        }
        if ($Show) {
            $dockerArgs += "--show"
        }

        Write-Host "Generating '$module' diagram as '$format'..."
        & docker @dockerArgs
        if ($LASTEXITCODE -ne 0) {
            throw "Terravision failed for module '$module' format '$format' (exit code $LASTEXITCODE)."
        }
    }
}

Write-Host ""
Write-Host "Done. Diagrams are under: $OutputRoot"
