$ErrorActionPreference = "Stop"

$base = "http://localhost:8000"
$logFile = Join-Path $PSScriptRoot "..\\api_demo_result.log"

function LogLine {
  param([string]$Text)
  $line = "{0} | {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Text
  Write-Output $line
  Add-Content -Path $logFile -Value $line -Encoding UTF8
}

if (Test-Path $logFile) {
  Remove-Item $logFile -Force
}

LogLine "START API demo"

$login = Invoke-RestMethod -Method Post -Uri "$base/auth/login" -ContentType "application/json" -Body (@{ username = "admin"; password = "admin123" } | ConvertTo-Json)
$token = $login.access_token
$h = @{ Authorization = "Bearer $token" }
LogLine ("LOGIN ok user={0}" -f $login.user.username)

$suffix = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$demoUser = Invoke-RestMethod -Method Post -Uri "$base/users" -Headers $h -ContentType "application/json" -Body (@{
  username = "demo_op_$suffix"
  password = "demo123456"
} | ConvertTo-Json)
LogLine ("CREATE USER username={0} role={1}" -f $demoUser.username, $demoUser.role)

$opLogin = Invoke-RestMethod -Method Post -Uri "$base/auth/login" -ContentType "application/json" -Body (@{
  username = $demoUser.username
  password = "demo123456"
} | ConvertTo-Json)
$opHeaders = @{ Authorization = "Bearer $($opLogin.access_token)" }
LogLine ("LOGIN operator user={0}" -f $opLogin.user.username)

$opTables = Invoke-RestMethod -Method Get -Uri "$base/tables" -Headers $opHeaders
LogLine ("OPERATOR LIST TABLES count={0}" -f $opTables.Count)

$forbiddenStatus = "no-error"
try {
  Invoke-RestMethod -Method Post -Uri "$base/users" -Headers $opHeaders -ContentType "application/json" -Body (@{
    username = "denied_$suffix"
    password = "demo123456"
  } | ConvertTo-Json) | Out-Null
} catch {
  $forbiddenStatus = [int]$_.Exception.Response.StatusCode
}
LogLine ("OPERATOR CREATE USER STATUS={0}" -f $forbiddenStatus)

$tableA = Invoke-RestMethod -Method Post -Uri "$base/tables" -Headers $h -ContentType "application/json" -Body (@{
  name = "DemoTableA-$suffix"
  schema = @{
    fields = @(
      @{ key = "brand"; label = "brand"; type = "text" },
      @{ key = "level"; label = "level"; type = "select"; options = @("A", "B", "S") }
    )
  }
} | ConvertTo-Json -Depth 10)
LogLine ("CREATE table {0}" -f $tableA.name)

$tableB = Invoke-RestMethod -Method Post -Uri "$base/tables" -Headers $h -ContentType "application/json" -Body (@{
  name = "DemoTableB-$suffix"
  schema = @{
    fields = @(
      @{ key = "batch"; label = "batch"; type = "text" },
      @{ key = "location"; label = "location"; type = "text" }
    )
  }
} | ConvertTo-Json -Depth 10)
LogLine ("CREATE table {0}" -f $tableB.name)

$null = Invoke-RestMethod -Method Patch -Uri "$base/tables/$($tableA.id)" -Headers $h -ContentType "application/json" -Body (@{
  schema = @{
    fields = @(
      @{ key = "brand"; label = "brand"; type = "text" },
      @{ key = "level"; label = "level"; type = "select"; options = @("A", "B", "S", "X") },
      @{ key = "origin"; label = "origin"; type = "text" }
    )
  }
} | ConvertTo-Json -Depth 10)
LogLine ("UPDATE schema table={0}" -f $tableA.name)

$codeA = "DEMO-A-$suffix"
$in = Invoke-RestMethod -Method Post -Uri "$base/stock/in" -Headers $h -ContentType "application/json" -Body (@{
  table_id = $tableA.id
  code = $codeA
  name = "Apple"
  quantity = 10
  properties = @{ brand = "RF"; level = "A"; origin = "CN" }
} | ConvertTo-Json -Depth 10)
LogLine ("STOCK IN code={0} qty=10 now={1}" -f $codeA, $in.quantity)

$out = Invoke-RestMethod -Method Post -Uri "$base/stock/out" -Headers $h -ContentType "application/json" -Body (@{
  table_id = $tableA.id
  code = $codeA
  quantity = 3
} | ConvertTo-Json -Depth 10)
LogLine ("STOCK OUT code={0} qty=3 now={1}" -f $codeA, $out.quantity)

$itemB = Invoke-RestMethod -Method Post -Uri "$base/items" -Headers $h -ContentType "application/json" -Body (@{
  table_id = $tableB.id
  name = "Milk"
  code = "DEMO-B-$suffix"
  quantity = 20
  properties = @{ batch = "B2026"; location = "C-01" }
} | ConvertTo-Json -Depth 10)
LogLine ("CREATE item id={0} code={1}" -f $itemB.id, $itemB.code)

$itemB2 = Invoke-RestMethod -Method Patch -Uri "$base/items/$($itemB.id)" -Headers $h -ContentType "application/json" -Body (@{
  quantity = 25
  properties_patch = @{ location = "C-02" }
} | ConvertTo-Json -Depth 10)
LogLine ("UPDATE item code={0} qty={1}" -f $itemB2.code, $itemB2.quantity)

$listA = Invoke-RestMethod -Method Get -Uri "$base/items?table_id=$($tableA.id)" -Headers $h
$listB = Invoke-RestMethod -Method Get -Uri "$base/items?table_id=$($tableB.id)" -Headers $h
LogLine ("LIST items tableA={0} tableB={1}" -f $listA.Count, $listB.Count)

Invoke-RestMethod -Method Delete -Uri "$base/items/$($itemB.id)" -Headers $h
LogLine ("DELETE item id={0}" -f $itemB.id)

$apiInfo = Invoke-RestMethod -Method Get -Uri "$base/integration/api-info" -Headers $h
$apiRef = Invoke-RestMethod -Method Get -Uri "$base/integration/api-reference" -Headers $h
$apiRefCount = if ($apiRef -is [System.Collections.IDictionary]) { $apiRef.Count } else { @($apiRef.PSObject.Properties).Count }
LogLine ("API INFO docs={0}" -f $apiInfo.docs_url)
LogLine ("API REFERENCE groups={0}" -f $apiRefCount)

$apiKey = Invoke-RestMethod -Method Post -Uri "$base/integration/api-keys" -Headers $h -ContentType "application/json" -Body (@{ name = "Demo-AI-Key-$suffix" } | ConvertTo-Json)
LogLine ("CREATE API KEY prefix={0}" -f $apiKey.key_prefix)

$keyHeaders = @{ "X-API-Key" = $apiKey.api_key }
$tablesViaKey = Invoke-RestMethod -Method Get -Uri "$base/tables" -Headers $keyHeaders
LogLine ("CALL /tables via API key count={0}" -f $tablesViaKey.Count)

$logs = Invoke-RestMethod -Method Get -Uri "$base/integration/logs?limit=8" -Headers $h
foreach ($row in $logs) {
  LogLine ("LOG {0} | {1}" -f $row.action, $row.summary)
}

LogLine "END API demo"
