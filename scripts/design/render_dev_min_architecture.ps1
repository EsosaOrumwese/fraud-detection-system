param(
  [ValidateSet("all", "with_icons", "without_icons")]
  [string]$Set = "all",

  [ValidateSet("dagre", "elk")]
  [string]$MermaidLayout = "dagre",

  [ValidateSet("dot", "neato", "fdp", "sfdp", "twopi", "circo")]
  [string]$GraphvizEngine = "dot",

  [ValidateSet("default", "neutral", "forest", "dark")]
  [string]$MermaidTheme = "neutral",

  [int]$MermaidWidth = 2400,
  [int]$MermaidHeight = 1600,

  [string]$InputRoot = "docs/design/platform/dev_min/architecture",
  [switch]$SkipGraphviz,
  [switch]$SkipMermaid
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Assert-Docker {
  $null = Get-Command docker -ErrorAction SilentlyContinue
  if (-not $?) {
    throw "Docker CLI is not installed or not on PATH."
  }

  docker info *> $null
  if ($LASTEXITCODE -ne 0) {
    throw "Docker daemon is not running."
  }
}

function To-WorkspacePath([string]$absPath, [string]$repoRoot) {
  $rel = $absPath.Substring($repoRoot.Length).TrimStart('\', '/')
  return "/workspace/" + ($rel -replace "\\", "/")
}

function Render-GraphvizFile {
  param(
    [string]$InputFile,
    [string]$RepoRoot,
    [string]$MountSpec,
    [string]$Engine
  )

  $inWs = To-WorkspacePath -absPath $InputFile -repoRoot $RepoRoot
  $outSvgWs = ($inWs -replace "\.dot$", ".svg")
  $outPngWs = ($inWs -replace "\.dot$", ".png")

  & docker run --rm --entrypoint $Engine -v $MountSpec -w /workspace patrickchugh/terravision:latest -Tsvg $inWs -o $outSvgWs
  if ($LASTEXITCODE -ne 0) { throw "Graphviz SVG render failed for $InputFile" }

  & docker run --rm --entrypoint $Engine -v $MountSpec -w /workspace patrickchugh/terravision:latest -Tpng $inWs -o $outPngWs
  if ($LASTEXITCODE -ne 0) { throw "Graphviz PNG render failed for $InputFile" }
}

function Render-MermaidFile {
  param(
    [string]$InputFile,
    [string]$RepoRoot,
    [string]$MountSpec,
    [string]$ConfigPathWs,
    [string]$Theme,
    [int]$Width,
    [int]$Height,
    [bool]$UseIconPacks
  )

  $inWs = To-WorkspacePath -absPath $InputFile -repoRoot $RepoRoot
  $outSvgWs = ($inWs -replace "\.mmd$", ".svg")
  $outPngWs = ($inWs -replace "\.mmd$", ".png")

  $argsCommon = @(
    "run", "--rm",
    "-v", $MountSpec,
    "-w", "/workspace",
    "minlag/mermaid-cli",
    "-i", $inWs,
    "-c", $ConfigPathWs,
    "-t", $Theme,
    "-w", $Width.ToString(),
    "-H", $Height.ToString()
  )

  if ($UseIconPacks) {
    $argsCommon += @("--iconPacks", "@iconify-json/simple-icons", "--iconPacks", "@iconify-json/mdi")
  }

  $argsSvg = @($argsCommon + @("-o", $outSvgWs, "-b", "transparent"))
  & docker @argsSvg
  if ($LASTEXITCODE -ne 0) { throw "Mermaid SVG render failed for $InputFile" }

  $argsPng = @($argsCommon + @("-o", $outPngWs, "-b", "white"))
  & docker @argsPng
  if ($LASTEXITCODE -ne 0) { throw "Mermaid PNG render failed for $InputFile" }
}

Assert-Docker

$repoRoot = (Resolve-Path ".").Path
$inputRootAbs = Join-Path $repoRoot $InputRoot
if (-not (Test-Path $inputRootAbs)) {
  throw "Input root does not exist: $inputRootAbs"
}

$paths = switch ($Set) {
  "all"          { @((Join-Path $inputRootAbs "without_icons"), (Join-Path $inputRootAbs "with_icons")) }
  "with_icons"   { @((Join-Path $inputRootAbs "with_icons")) }
  "without_icons"{ @((Join-Path $inputRootAbs "without_icons")) }
}

foreach ($p in $paths) {
  if (-not (Test-Path $p)) {
    throw "Expected folder missing: $p"
  }
}

$renderDirAbs = Join-Path $inputRootAbs "_render"
New-Item -ItemType Directory -Path $renderDirAbs -Force | Out-Null

$cfgObj = @{
  flowchart = @{
    defaultRenderer = $MermaidLayout
  }
}
$cfgAbs = Join-Path $renderDirAbs "mermaid.render.config.json"
$cfgObj | ConvertTo-Json -Depth 5 | Set-Content -Path $cfgAbs -Encoding utf8

$mountSpec = "${repoRoot}:/workspace"
$cfgWs = To-WorkspacePath -absPath $cfgAbs -repoRoot $repoRoot

if (-not $SkipGraphviz) {
  $dotFiles = foreach ($p in $paths) {
    Get-ChildItem -Path $p -Filter "*.graphviz.dot" -File
  }
  foreach ($f in $dotFiles) {
    Render-GraphvizFile -InputFile $f.FullName -RepoRoot $repoRoot -MountSpec $mountSpec -Engine $GraphvizEngine
  }
}

if (-not $SkipMermaid) {
  $mmdFiles = foreach ($p in $paths) {
    Get-ChildItem -Path $p -Filter "*.mmd" -File
  }
  foreach ($f in $mmdFiles) {
    $useIcons = ($f.Directory.Name -eq "with_icons")
    Render-MermaidFile -InputFile $f.FullName -RepoRoot $repoRoot -MountSpec $mountSpec -ConfigPathWs $cfgWs -Theme $MermaidTheme -Width $MermaidWidth -Height $MermaidHeight -UseIconPacks:$useIcons
  }
}

if (Test-Path $cfgAbs) {
  Remove-Item -Path $cfgAbs -Force
}
if (Test-Path $renderDirAbs) {
  $remaining = @(Get-ChildItem -Path $renderDirAbs -Force)
  if ($remaining.Count -eq 0) {
    Remove-Item -Path $renderDirAbs -Force
  }
}

Write-Host "Render complete."
Write-Host "Set: $Set"
Write-Host "Mermaid layout: $MermaidLayout"
Write-Host "Graphviz engine: $GraphvizEngine"
Write-Host "Input root: $inputRootAbs"
