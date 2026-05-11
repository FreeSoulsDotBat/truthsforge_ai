$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$EnvFile = Join-Path $RepoRoot "infra\.env"
$EnvExampleFile = Join-Path $RepoRoot "infra\.env.example"
$ComposeFile = Join-Path $RepoRoot "infra\docker-compose.yml"
$ComposeDevFile = Join-Path $RepoRoot "infra\docker-compose.dev.yml"
$LocalDockerConfigDir = Join-Path $RepoRoot ".local\docker-config"

if (-not $env:DOCKER_CONFIG) {
  New-Item -ItemType Directory -Force -Path $LocalDockerConfigDir | Out-Null
  $ConfigPath = Join-Path $LocalDockerConfigDir "config.json"
  if (-not (Test-Path $ConfigPath)) {
    "{}" | Set-Content -Path $ConfigPath -Encoding UTF8
  }
  $env:DOCKER_CONFIG = $LocalDockerConfigDir
}

if (-not (Test-Path $EnvFile)) {
  if (-not (Test-Path $EnvExampleFile)) {
    throw "Couldn't find env file: $EnvFile or $EnvExampleFile"
  }
  $EnvFile = $EnvExampleFile
}

docker compose --env-file $EnvFile -f $ComposeFile -f $ComposeDevFile up -d pgadmin
if ($LASTEXITCODE -ne 0) {
  throw "docker compose up -d pgadmin failed"
}

$ResetCommand = @'
cd /pgadmin4
/venv/bin/python3 setup.py update-user "$PGADMIN_DEFAULT_EMAIL" --password "$PGADMIN_DEFAULT_PASSWORD" --admin --active --no-console >/tmp/pgadmin-reset.log 2>&1
if [ "$?" -ne 0 ]; then
  /venv/bin/python3 setup.py add-user "$PGADMIN_DEFAULT_EMAIL" "$PGADMIN_DEFAULT_PASSWORD" --admin --active --no-console >/tmp/pgadmin-reset.log 2>&1
fi

PGPASS_FILE=/var/lib/pgadmin/truths-forge.pgpass
SERVERS_FILE=/tmp/truths-forge-servers.json

cat > "$PGPASS_FILE" <<EOF
postgres:5432:*:${POSTGRES_USER}:${POSTGRES_PASSWORD}
EOF
chmod 600 "$PGPASS_FILE"

cat > "$SERVERS_FILE" <<EOF
{
  "Servers": {
    "1": {
      "Name": "Truth's Forge Postgres",
      "Group": "Servers",
      "Host": "postgres",
      "Port": 5432,
      "MaintenanceDB": "${POSTGRES_DB}",
      "Username": "${POSTGRES_USER}",
      "SSLMode": "prefer",
      "PassFile": "${PGPASS_FILE}",
      "ConnectionParameters": {
        "sslmode": "prefer",
        "connect_timeout": 10
      }
    }
  }
}
EOF

/venv/bin/python3 setup.py load-servers "$SERVERS_FILE" --user "$PGADMIN_DEFAULT_EMAIL" --auth-source internal --replace >/tmp/pgadmin-servers.log 2>&1
'@

docker exec truths-forge-pgadmin sh -lc $ResetCommand
if ($LASTEXITCODE -ne 0) {
  throw "docker exec truths-forge-pgadmin failed"
}

Write-Host "pgAdmin user and Postgres server reset. Use PGADMIN_DEFAULT_EMAIL and PGADMIN_DEFAULT_PASSWORD from infra\.env."
