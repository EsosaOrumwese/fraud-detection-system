param(
    [ValidateSet("start", "stop", "status", "logs")]
    [string]$Action = "start",
    [ValidateSet("narrative", "raw")]
    [string]$Mode = "narrative"
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
        if ($Mode -eq "raw") {
            docker logs -f $Name
            return
        }
        docker logs -f $Name | ForEach-Object {
            $line = $_
            if ($line -match "\\bReady\\.") {
                Write-Host "LocalStack ready."
                return
            }
            if ($line -match "kinesis\\.DescribeStreamSummary => 400") {
                Write-Host "Kinesis: stream missing (expected); creating stream."
                return
            }
            if ($line -match "kinesis\\.CreateStream => 200") {
                Write-Host "Kinesis: stream created."
                return
            }
            if ($line -match "kinesis\\.DescribeStreamSummary => 200") {
                Write-Host "Kinesis: stream active."
                return
            }
            if ($line -match "kinesis\\.PutRecord => 200") {
                Write-Host "Kinesis: record published."
                return
            }
            if ($line -match "kinesis\\.GetShardIterator => 200") {
                Write-Host "Kinesis: shard iterator acquired."
                return
            }
            if ($line -match "kinesis\\.GetRecords => 200") {
                Write-Host "Kinesis: record read."
                return
            }
            if ($line -match "received signal 15") {
                Write-Host "LocalStack shutdown signal received."
                return
            }
            if ($line -match "Stopping all services") {
                Write-Host "LocalStack stopping services."
                return
            }
            if ($line -match "\\bERROR\\b|\\bWARN\\b") {
                Write-Host ("LocalStack warning/error: " + $line)
                return
            }
        }
    }
}
