param(
    [ValidateSet("start", "stop", "status", "logs")]
    [string]$Action = "start"
)

$Name = "localstack"
$Image = "localstack/localstack:latest"
$Port = "4566"

switch ($Action) {
    "start" {
        docker run -d --rm -p "$Port`:$Port" -e SERVICES=kinesis --name $Name $Image | Out-Null
        Write-Host "LocalStack started ($Name) on port $Port."
    }
    "stop" {
        docker stop $Name | Out-Null
        Write-Host "LocalStack stopped ($Name)."
    }
    "status" {
        docker ps -a --filter "name=$Name" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    }
    "logs" {
        docker logs -f $Name
    }
}
