param(
  [ValidateSet("tier0", "parity", "localstack", "engine_fixture", "all")]
  [string]$Tier = "tier0",
  [string]$Python = "python"
)

$marker = ""
switch ($Tier) {
  "tier0" { $marker = "not parity and not localstack and not engine_fixture" }
  "parity" { $marker = "parity" }
  "localstack" { $marker = "localstack" }
  "engine_fixture" { $marker = "engine_fixture" }
  "all" { $marker = "" }
}

if ($marker) {
  & $Python -m pytest tests/services/scenario_runner -m $marker -q
} else {
  & $Python -m pytest tests/services/scenario_runner -q
}
