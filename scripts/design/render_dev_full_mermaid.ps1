param(
  [string]$InputRoot = "docs/design/platform/dev_full/visuals",
  [ValidateSet("elk", "dagre")]
  [string]$MermaidLayout = "elk",
  [ValidateSet("neutral", "default", "forest", "dark")]
  [string]$MermaidTheme = "neutral",
  [int]$Width = 2600,
  [int]$Height = 1700
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RendererMode {
  $docker = Get-Command docker -ErrorAction SilentlyContinue
  if ($docker) {
    docker info *> $null
    if ($LASTEXITCODE -eq 0) { return "docker" }
  }

  $mmdc = Get-Command mmdc -ErrorAction SilentlyContinue
  if ($mmdc) { return "local" }

  throw "No Mermaid renderer available. Start Docker or install mmdc."
}

function To-WorkspacePath([string]$absPath, [string]$repoRoot) {
  $rel = $absPath.Substring($repoRoot.Length).TrimStart('\', '/')
  return "/workspace/" + ($rel -replace "\\", "/")
}

$rendererMode = Get-RendererMode

$repoRoot = (Resolve-Path ".").Path
$inputAbs = Join-Path $repoRoot $InputRoot
if (-not (Test-Path $inputAbs)) {
  throw "Input root missing: $inputAbs"
}

$tmpDir = Join-Path $inputAbs "_render"
New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null
$cfgAbs = Join-Path $tmpDir "mermaid.config.json"
@{
  flowchart = @{
    defaultRenderer = $MermaidLayout
  }
} | ConvertTo-Json -Depth 5 | Set-Content -Path $cfgAbs -Encoding utf8

$mmdFiles = Get-ChildItem -Path $inputAbs -Recurse -Filter "*.mmd" -File

foreach ($f in $mmdFiles) {
  $svgAbs = ($f.FullName -replace "\.mmd$", ".svg")
  $pngAbs = ($f.FullName -replace "\.mmd$", ".png")

  if ($rendererMode -eq "docker") {
    $mountSpec = "${repoRoot}:/workspace"
    $cfgWs = To-WorkspacePath -absPath $cfgAbs -repoRoot $repoRoot
    $inWs = To-WorkspacePath -absPath $f.FullName -repoRoot $repoRoot
    $svgWs = To-WorkspacePath -absPath $svgAbs -repoRoot $repoRoot
    $pngWs = To-WorkspacePath -absPath $pngAbs -repoRoot $repoRoot

    & docker run --rm -v $mountSpec -w /workspace minlag/mermaid-cli `
      -i $inWs -o $svgWs -c $cfgWs -t $MermaidTheme -w $Width -H $Height -b transparent
    if ($LASTEXITCODE -ne 0) { throw "Mermaid SVG render failed: $($f.FullName)" }

    & docker run --rm -v $mountSpec -w /workspace minlag/mermaid-cli `
      -i $inWs -o $pngWs -c $cfgWs -t $MermaidTheme -w $Width -H $Height -b white
    if ($LASTEXITCODE -ne 0) { throw "Mermaid PNG render failed: $($f.FullName)" }
  } else {
    & mmdc -i $f.FullName -o $svgAbs -c $cfgAbs -t $MermaidTheme -w $Width -H $Height -b transparent
    if ($LASTEXITCODE -ne 0) { throw "Mermaid SVG render failed: $($f.FullName)" }

    & mmdc -i $f.FullName -o $pngAbs -c $cfgAbs -t $MermaidTheme -w $Width -H $Height -b white
    if ($LASTEXITCODE -ne 0) { throw "Mermaid PNG render failed: $($f.FullName)" }
  }
}

if (Test-Path $cfgAbs) { Remove-Item -Path $cfgAbs -Force }
if (Test-Path $tmpDir) {
  $remaining = @(Get-ChildItem -Path $tmpDir -Force)
  if ($remaining.Count -eq 0) { Remove-Item -Path $tmpDir -Force }
}

Write-Host "Rendered $($mmdFiles.Count) Mermaid files from $inputAbs"
Write-Host "Layout: $MermaidLayout | Theme: $MermaidTheme | Size: ${Width}x${Height} | Renderer: $rendererMode"
