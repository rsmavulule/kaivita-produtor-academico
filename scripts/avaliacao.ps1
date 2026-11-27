# Ambiente isolado de avaliacao I9.
# So aceita o projecto Compose kaivita-avaliacao e a base kaivita_avaliacao.
# Nao apaga o volume de desenvolvimento. Nao imprime palavras-passe nem tokens.
# Uso, na raiz do repositorio:
#   powershell -NoProfile -File scripts/avaliacao.ps1 subir|parar|preparar|verificar|backup|recuperar|persistencia|contagens|repor

param(
    [Parameter(Position = 0, Mandatory = $true)]
    [ValidateSet("subir", "parar", "preparar", "verificar", "backup", "recuperar", "persistencia", "contagens", "repor")]
    [string]$Accao,

    [string]$Ficheiro,

    [switch]$Sobrepor,

    [switch]$Confirmar
)

$ErrorActionPreference = "Stop"
$Project = "kaivita-avaliacao"
$ExpectedDb = "kaivita_avaliacao"
$ExpectedUser = "kaivita_avaliacao"
$ExpectedVolume = "kaivita-avaliacao-pgdata"
$RestoreDb = "kaivita_avaliacao_restauro"
$EnvName = ".env.avaliacao"
$ForbiddenPorts = @("5432", "5435", "8000", "8010", "3000", "3010")
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Read-EvalEnv {
    $path = Join-Path $Root $EnvName
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Ficheiro .env.avaliacao em falta. Copiar .env.avaliacao.example e preencher fora do Git."
    }
    $map = @{}
    foreach ($line in [System.IO.File]::ReadAllLines($path)) {
        $text = $line.Trim()
        if ($text -eq "" -or $text.StartsWith("#")) { continue }
        $eq = $text.IndexOf("=")
        if ($eq -lt 1) { throw "Linha invalida em .env.avaliacao." }
        $key = $text.Substring(0, $eq).Trim()
        $value = $text.Substring($eq + 1).Trim()
        $map[$key] = $value
    }
    return $map
}

function Assert-EvalEnv([hashtable]$Map) {
    if ($Map["POSTGRES_DB"] -ne $ExpectedDb) { throw "POSTGRES_DB tem de ser $ExpectedDb." }
    if ($Map["POSTGRES_USER"] -ne $ExpectedUser) { throw "POSTGRES_USER tem de ser $ExpectedUser." }
    if ($Map["JWT_ISSUER"] -ne "kaivita-avaliacao") { throw "JWT_ISSUER tem de ser kaivita-avaliacao." }
    foreach ($key in @("POSTGRES_PORT", "API_PORT", "WEB_PORT")) {
        $port = $Map[$key]
        if (-not $port) { throw "$key em falta." }
        if ($ForbiddenPorts -contains $port) { throw "$key=$port esta reservada ao desenvolvimento." }
    }
    $password = $Map["POSTGRES_PASSWORD"]
    if (-not $password -or $password.Length -lt 16 -or $password -eq "kaivita_dev" -or $password -eq "SUBSTITUIR") {
        throw "POSTGRES_PASSWORD da avaliacao foi recusada."
    }
    $secret = $Map["JWT_SECRET"]
    if (-not $secret -or $secret.Length -lt 32 -or $secret -eq "SUBSTITUIR") {
        throw "JWT_SECRET da avaliacao foi recusado."
    }
    foreach ($key in @("AVALIACAO_PASSWORD_PRODUTOR", "AVALIACAO_PASSWORD_COMPRADOR", "AVALIACAO_PASSWORD_CONSULTA")) {
        $account = $Map[$key]
        if (-not $account -or $account.Length -lt 12) { throw "$key em falta ou curta demais." }
    }
}

function Import-EvalEnv([hashtable]$Map) {
    foreach ($key in $Map.Keys) {
        Set-Item -Path "Env:$key" -Value $Map[$key]
    }
}

function Get-ComposeArgs {
    return @(
        "compose", "-p", $Project,
        "-f", "compose.yaml",
        "-f", "compose.avaliacao.yaml",
        "--env-file", (Join-Path $Root $EnvName)
    )
}

function Invoke-Compose([string[]]$Command) {
    & docker @(Get-ComposeArgs) @Command
    if ($LASTEXITCODE -ne 0) { throw "docker compose falhou: $($Command -join ' ')" }
}

function Assert-ResolvedProject([hashtable]$Map) {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $raw = & docker @(Get-ComposeArgs) config --format json 2>$null
    $configCode = $LASTEXITCODE
    $ErrorActionPreference = $previous
    if ($configCode -ne 0) { throw "docker compose config falhou." }
    $tmp = Join-Path $env:TEMP ("kaivita-avaliacao-config-" + [guid]::NewGuid().ToString() + ".json")
    try {
        $text = if ($raw -is [System.Array]) { $raw -join "`n" } else { [string]$raw }
        [System.IO.File]::WriteAllText($tmp, $text, [System.Text.UTF8Encoding]::new($false))
        $summary = & python -c @"
import json
d = json.load(open(r'$tmp', encoding='utf-8'))
vol = d.get('volumes', {}).get('pgdata', {}).get('name')
db_env = d['services']['db'].get('environment') or {}
if isinstance(db_env, list):
    db_env = dict(item.split('=', 1) for item in db_env if '=' in item)
def published(service, target):
    for item in d['services'][service].get('ports') or []:
        if int(item.get('target', 0)) == target:
            return str(item.get('published'))
    return ''
print(d.get('name', ''))
print(vol or '')
print(db_env.get('POSTGRES_DB', ''))
print(db_env.get('POSTGRES_USER', ''))
print(published('db', 5432))
print(published('api', 8000))
print(published('web', 3000))
"@
        if ($LASTEXITCODE -ne 0) { throw "Nao foi possivel ler o projecto resolvido." }
    } finally {
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
    }
    $lines = @($summary -split "`r?`n" | Where-Object { $_ -ne "" })
    if ($lines.Count -lt 7) { throw "Resumo do Compose incompleto." }
    if ($lines[0] -ne $Project) { throw "Projecto resolvido $($lines[0]). Esperado $Project." }
    if ($lines[1] -ne $ExpectedVolume) { throw "Volume resolvido $($lines[1])." }
    if ($lines[2] -ne $ExpectedDb -or $lines[3] -ne $ExpectedUser) { throw "Base resolvida inesperada." }
    if ($lines[4] -ne $Map["POSTGRES_PORT"] -or $lines[5] -ne $Map["API_PORT"] -or $lines[6] -ne $Map["WEB_PORT"]) {
        throw "Portas resolvidas nao coincidem com .env.avaliacao."
    }
    foreach ($port in $lines[4..6]) {
        if ($ForbiddenPorts -contains $port) { throw "Porta resolvida $port pertence ao desenvolvimento." }
    }
    Write-Output "projecto=$($lines[0]) volume=$($lines[1]) base=$($lines[2]) portas=$($lines[4]),$($lines[5]),$($lines[6])"
}

function Assert-EvalContainer {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $raw = docker inspect --format "{{json .Config.Labels}}" "kaivita-avaliacao-db-1" 2>$null
    $code = $LASTEXITCODE
    $ErrorActionPreference = $previous
    if ($code -ne 0) { throw "O contentor da base de avaliacao nao esta confirmado." }
    $text = if ($raw -is [System.Array]) { $raw -join "" } else { [string]$raw }
    $labels = $text.Trim() | ConvertFrom-Json
    $label = [string]$labels.'com.docker.compose.project'
    if ($label.Trim() -ne $Project) {
        throw "O contentor da base de avaliacao nao esta confirmado."
    }
}

function Invoke-Psql {
    param([string]$Database, [string]$Sql)
    Assert-EvalContainer
    if ($Database -ne $ExpectedDb -and $Database -ne $RestoreDb -and $Database -ne "postgres") {
        throw "Base SQL recusada."
    }
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $output = & docker @(Get-ComposeArgs) exec -T db psql -v ON_ERROR_STOP=1 -U $ExpectedUser -d $Database -tAc $Sql 2>&1
    $code = $LASTEXITCODE
    $ErrorActionPreference = $previous
    if ($code -ne 0) { throw "psql falhou na base $Database." }
    return ($output | Out-String).Trim()
}

function Wait-Healthy([hashtable]$Map) {
    $deadline = (Get-Date).AddMinutes(8)
    $health = "http://127.0.0.1:$($Map['API_PORT'])/health"
    do {
        $previous = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $body = & curl.exe --silent --show-error --noproxy "*" --max-time 5 $health 2>&1
        $code = $LASTEXITCODE
        $ErrorActionPreference = $previous
        if ($code -eq 0 -and "$body" -match '"database"\s*:\s*"up"') {
            Write-Output "api saudavel em $($Map['API_PORT'])"
            return
        }
        Start-Sleep -Seconds 5
    } while ((Get-Date) -lt $deadline)
    throw "A API de avaliacao nao ficou saudavel."
}

function Read-Dataset {
    $path = Join-Path $PSScriptRoot "avaliacao-dados.json"
    $text = [System.IO.File]::ReadAllText($path, [System.Text.UTF8Encoding]::new($false))
    return $text | ConvertFrom-Json
}

function Invoke-CurlJson {
    param(
        [string]$Method,
        [string]$Url,
        [string]$Token,
        [object]$Body
    )
    $args = @(
        "--silent", "--show-error", "--noproxy", "*",
        "--max-time", "30",
        "-X", $Method,
        "-H", "Accept: application/json",
        "-w", "`n%{http_code}"
    )
    if ($Token) { $args += @("-H", "Authorization: Bearer $Token") }
    $tmp = $null
    try {
        if ($null -ne $Body) {
            $tmp = Join-Path $env:TEMP ("kaivita-avaliacao-body-" + [guid]::NewGuid().ToString() + ".json")
            $json = $Body | ConvertTo-Json -Compress -Depth 8
            [System.IO.File]::WriteAllText($tmp, $json, [System.Text.UTF8Encoding]::new($false))
            $args += @("-H", "Content-Type: application/json; charset=utf-8", "--data-binary", "@$tmp")
        }
        $previous = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $raw = & curl.exe @args $Url 2>&1
        $code = $LASTEXITCODE
        $ErrorActionPreference = $previous
        if ($code -ne 0) { throw "Ligacao falhou: $Method $Url" }
        $text = ($raw | Out-String).Trim()
        $split = $text -split "`r?`n"
        $status = $split[-1].Trim()
        $payload = ""
        if ($split.Count -gt 1) { $payload = ($split[0..($split.Count - 2)] -join "`n").Trim() }
        $parsed = $null
        if ($payload -ne "") { $parsed = $payload | ConvertFrom-Json }
        return @{ Status = [int]$status; Json = $parsed }
    } finally {
        if ($tmp) { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
    }
}

function Get-Token([hashtable]$Map, [string]$Api, [string]$Email, [string]$PasswordEnv) {
    $result = Invoke-CurlJson -Method "POST" -Url "$Api/auth/login" -Body @{
        email = $Email
        password = $Map[$PasswordEnv]
    }
    if ($result.Status -ne 200 -or -not $result.Json.access_token) {
        throw "Login falhou para $Email com HTTP $($result.Status)."
    }
    return [string]$result.Json.access_token
}

function New-EvalAccount([hashtable]$Map, [string]$Email, [string]$PasswordEnv) {
    $password = $Map[$PasswordEnv]
    $tmp = Join-Path $env:TEMP ("kaivita-avaliacao-pw-" + [guid]::NewGuid().ToString() + ".txt")
    $outFile = Join-Path $env:TEMP ("kaivita-avaliacao-out-" + [guid]::NewGuid().ToString() + ".txt")
    $errFile = Join-Path $env:TEMP ("kaivita-avaliacao-err-" + [guid]::NewGuid().ToString() + ".txt")
    try {
        [System.IO.File]::WriteAllText($tmp, $password + "`n", [System.Text.UTF8Encoding]::new($false))
        $proc = Start-Process -FilePath "docker" -ArgumentList (@(Get-ComposeArgs) + @("exec", "-T", "api", "python", "-m", "app.create_user", "--email", $Email)) -Wait -PassThru -NoNewWindow -RedirectStandardInput $tmp -RedirectStandardOutput $outFile -RedirectStandardError $errFile
        $text = [System.IO.File]::ReadAllText($outFile) + [System.IO.File]::ReadAllText($errFile)
        if ($text.Contains($password)) { $text = "saida omitida" }
        if ($proc.ExitCode -eq 0 -and $text -match "Conta criada") {
            Write-Output "conta criada: $Email"
            return
        }
        if ($text -match "existe uma conta") {
            Write-Output "conta ja existente: $Email"
            return
        }
        throw "create_user falhou para $Email."
    } finally {
        Remove-Item -LiteralPath $tmp, $outFile, $errFile -Force -ErrorAction SilentlyContinue
    }
}

function Get-ByName($Items, [string]$Name) {
    foreach ($item in @($Items)) {
        if ($item.display_name -eq $Name -or $item.name -eq $Name) { return $item }
    }
    return $null
}

function Save-State($State) {
    $dir = Join-Path $Root "avaliacao-backups"
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $path = Join-Path $dir "estado.json"
    $json = $State | ConvertTo-Json -Depth 6
    [System.IO.File]::WriteAllText($path, $json, [System.Text.UTF8Encoding]::new($false))
    Write-Output "estado gravado sem segredos"
}

function Read-State {
    $path = Join-Path $Root "avaliacao-backups\estado.json"
    if (-not (Test-Path -LiteralPath $path)) { throw "estado.json em falta. Executar preparar." }
    $text = [System.IO.File]::ReadAllText($path, [System.Text.UTF8Encoding]::new($false))
    return $text | ConvertFrom-Json
}

function Assert-SmallDatabase {
    $users = Invoke-Psql -Database $ExpectedDb -Sql "SELECT count(*) FROM users;"
    if ([int]$users -gt 20) { throw "A base tem $users contas. Nao e a base de avaliacao." }
    $name = Invoke-Psql -Database $ExpectedDb -Sql "SELECT current_database();"
    if ($name -ne $ExpectedDb) { throw "current_database=$name" }
    return [int]$users
}

function Show-Counts {
    Assert-EvalContainer
    $sql = "SELECT 'users=' || (SELECT count(*) FROM users) || ' actors=' || (SELECT count(*) FROM actors) || ' products=' || (SELECT count(*) FROM products) || ' offers=' || (SELECT count(*) FROM offers) || ' contacts=' || (SELECT count(*) FROM public_contacts) || ' authorizations=' || (SELECT count(*) FROM publication_authorizations) || ' events=' || (SELECT count(*) FROM offer_status_events) || ' alembic=' || (SELECT version_num FROM alembic_version);"
    $line = Invoke-Psql -Database $ExpectedDb -Sql $sql
    Write-Output "contagens $line"
}

$map = Read-EvalEnv
Assert-EvalEnv $map
Import-EvalEnv $map
Assert-ResolvedProject $map

switch ($Accao) {
    "subir" {
        Invoke-Compose @("up", "-d", "--build")
        Wait-Healthy $map
        Assert-EvalContainer
        $version = Invoke-Psql -Database $ExpectedDb -Sql "SELECT version_num FROM alembic_version;"
        if ($version -ne "0008_offer_status_events") { throw "Alembic $version." }
        Write-Output "alembic=$version"
        Show-Counts
    }
    "parar" {
        Invoke-Compose @("stop")
        Write-Output "avaliacao parada; o volume $ExpectedVolume mantem-se"
    }
    "contagens" {
        Assert-EvalContainer
        Show-Counts
    }
    "preparar" {
        Assert-EvalContainer
        Wait-Healthy $map
        Assert-SmallDatabase | Out-Null
        $data = Read-Dataset
        $api = "http://127.0.0.1:$($map['API_PORT'])"
        foreach ($key in @("produtor", "comprador", "consulta")) {
            $account = $data.accounts.$key
            New-EvalAccount $map $account.email $account.password_env
        }
        $producerToken = Get-Token $map $api $data.accounts.produtor.email $data.accounts.produtor.password_env
        $buyerToken = Get-Token $map $api $data.accounts.comprador.email $data.accounts.comprador.password_env
        $readerToken = Get-Token $map $api $data.accounts.consulta.email $data.accounts.consulta.password_env
        $me = Invoke-CurlJson -Method "GET" -Url "$api/auth/me" -Token $producerToken
        if ($me.Status -ne 200 -or $me.Json.email -ne $data.accounts.produtor.email) {
            throw "GET /auth/me do produtor falhou."
        }
        Write-Output "autenticacao produtor HTTP 200"

        $actors = Invoke-CurlJson -Method "GET" -Url "$api/actors" -Token $producerToken
        $producer = Get-ByName $actors.Json $data.producer.display_name
        if (-not $producer) {
            $created = Invoke-CurlJson -Method "POST" -Url "$api/actors" -Token $producerToken -Body @{
                kind = $data.producer.kind
                display_name = $data.producer.display_name
                general_location = $data.producer.general_location
                coverage_area = $data.producer.coverage_area
                roles = @($data.producer.roles)
            }
            if ($created.Status -ne 201) { throw "Criacao do produtor HTTP $($created.Status)." }
            $producer = $created.Json
            Write-Output "actor produtor criado"
        } else {
            Write-Output "actor produtor ja existente"
        }
        $actorId = [string]$producer.id

        $buyers = Invoke-CurlJson -Method "GET" -Url "$api/actors" -Token $buyerToken
        $buyer = Get-ByName $buyers.Json $data.buyer.display_name
        if (-not $buyer) {
            $createdBuyer = Invoke-CurlJson -Method "POST" -Url "$api/actors" -Token $buyerToken -Body @{
                kind = $data.buyer.kind
                display_name = $data.buyer.display_name
                general_location = $data.buyer.general_location
                roles = @($data.buyer.roles)
            }
            if ($createdBuyer.Status -ne 201) { throw "Criacao do comprador HTTP $($createdBuyer.Status)." }
            Write-Output "actor comprador criado"
        } else {
            Write-Output "actor comprador ja existente"
        }

        $sqlName = $data.producer.display_name.Replace("'", "''")
        $sqlEmail = $data.accounts.consulta.email.Replace("'", "''")
        $insert = "INSERT INTO user_actor_access (user_id, actor_id, access_level, status) SELECT u.id, a.id, 'read', 'active' FROM users u JOIN actors a ON a.display_name = '$sqlName' WHERE u.email = '$sqlEmail' ON CONFLICT (user_id, actor_id) DO NOTHING;"
        Invoke-Psql -Database $ExpectedDb -Sql $insert | Out-Null
        $readerView = Invoke-CurlJson -Method "GET" -Url "$api/actors/$actorId" -Token $readerToken
        if ($readerView.Status -ne 200 -or $readerView.Json.representation -ne "read") {
            throw "A consulta nao ficou com representacao read."
        }
        Write-Output "representacao de consulta activa"

        $products = Invoke-CurlJson -Method "GET" -Url "$api/actors/$actorId/products" -Token $producerToken
        $withPhoto = Get-ByName $products.Json $data.products.with_photo.name
        if (-not $withPhoto) {
            $withPhoto = (Invoke-CurlJson -Method "POST" -Url "$api/actors/$actorId/products" -Token $producerToken -Body @{
                name = $data.products.with_photo.name
                description = $data.products.with_photo.description
                category = $data.products.with_photo.category
                image_ref = $data.products.with_photo.image_ref
                image_use_confirmed = $true
            })
            if ($withPhoto.Status -ne 201) { throw "Produto com fotografia HTTP $($withPhoto.Status)." }
            $withPhoto = $withPhoto.Json
            Write-Output "produto com fotografia criado"
        } else {
            Write-Output "produto com fotografia ja existente"
        }
        $withoutPhoto = Get-ByName $products.Json $data.products.without_photo.name
        if (-not $withoutPhoto) {
            $withoutPhoto = (Invoke-CurlJson -Method "POST" -Url "$api/actors/$actorId/products" -Token $producerToken -Body @{
                name = $data.products.without_photo.name
                description = $data.products.without_photo.description
                category = $data.products.without_photo.category
                image_use_confirmed = $false
            })
            if ($withoutPhoto.Status -ne 201) { throw "Produto sem fotografia HTTP $($withoutPhoto.Status)." }
            $withoutPhoto = $withoutPhoto.Json
            Write-Output "produto sem fotografia criado"
        } else {
            Write-Output "produto sem fotografia ja existente"
        }

        $offers = Invoke-CurlJson -Method "GET" -Url "$api/actors/$actorId/offers" -Token $producerToken
        $published = $null
        $draft = $null
        foreach ($offer in @($offers.Json)) {
            if ($offer.product_id -eq $withPhoto.id -and $offer.status -eq "published") { $published = $offer }
            if ($offer.product_id -eq $withoutPhoto.id -and $offer.status -eq "draft") { $draft = $offer }
        }
        if (-not $published) {
            $createdOffer = Invoke-CurlJson -Method "POST" -Url "$api/actors/$actorId/offers" -Token $producerToken -Body @{
                product_id = $withPhoto.id
                price = $data.offers.published.price
                currency = $data.offers.published.currency
                quantity = $data.offers.published.quantity
                unit = $data.offers.published.unit
                availability = $data.offers.published.availability
                delivery_terms = $data.offers.published.delivery_terms
            }
            if ($createdOffer.Status -ne 201) { throw "Oferta HTTP $($createdOffer.Status)." }
            $publishedResult = Invoke-CurlJson -Method "POST" -Url "$api/actors/$actorId/offers/$($createdOffer.Json.id)/publish" -Token $producerToken
            if ($publishedResult.Status -ne 200) { throw "Publicacao HTTP $($publishedResult.Status)." }
            $published = $publishedResult.Json
            Write-Output "oferta publicada"
        } else {
            Write-Output "oferta publicada ja existente"
        }
        if (-not $draft) {
            $draftResult = Invoke-CurlJson -Method "POST" -Url "$api/actors/$actorId/offers" -Token $producerToken -Body @{
                product_id = $withoutPhoto.id
            }
            if ($draftResult.Status -ne 201) { throw "Rascunho HTTP $($draftResult.Status)." }
            $draft = $draftResult.Json
            Write-Output "rascunho criado"
        } else {
            Write-Output "rascunho ja existente"
        }

        $contacts = Invoke-CurlJson -Method "GET" -Url "$api/actors/$actorId/contacts" -Token $producerToken
        $privateContact = $null
        $publicContact = $null
        foreach ($contact in @($contacts.Json.items)) {
            if ($contact.value -eq $data.contacts.private_phone.value) { $privateContact = $contact }
            if ($contact.value -eq $data.contacts.disclosed_email.value) { $publicContact = $contact }
        }
        if (-not $privateContact) {
            $privateResult = Invoke-CurlJson -Method "POST" -Url "$api/actors/$actorId/contacts" -Token $producerToken -Body @{
                channel = $data.contacts.private_phone.channel
                value = $data.contacts.private_phone.value
            }
            if ($privateResult.Status -ne 201) { throw "Contacto privado HTTP $($privateResult.Status)." }
            $privateContact = $privateResult.Json
            Write-Output "contacto privado criado"
        }
        if (-not $publicContact) {
            $publicResult = Invoke-CurlJson -Method "POST" -Url "$api/actors/$actorId/contacts" -Token $producerToken -Body @{
                channel = $data.contacts.disclosed_email.channel
                value = $data.contacts.disclosed_email.value
            }
            if ($publicResult.Status -ne 201) { throw "Contacto de divulgacao HTTP $($publicResult.Status)." }
            $publicContact = $publicResult.Json
            Write-Output "contacto de divulgacao criado"
        }
        $authorizations = Invoke-CurlJson -Method "GET" -Url "$api/actors/$actorId/contacts/$($publicContact.id)/authorizations" -Token $producerToken
        $current = $false
        foreach ($authorization in @($authorizations.Json.items)) {
            if (-not $authorization.revoked_at) { $current = $true }
        }
        if (-not $current) {
            $grant = Invoke-CurlJson -Method "POST" -Url "$api/actors/$actorId/contacts/$($publicContact.id)/authorizations" -Token $producerToken -Body @{
                contact_revision = $publicContact.revision
                purpose = "commercial_discovery"
                notice_version = "v1"
                confirmed = $true
            }
            if ($grant.Status -ne 201 -and $grant.Status -ne 200) { throw "Concessao HTTP $($grant.Status)." }
            Write-Output "autorizacao concedida"
        } else {
            Write-Output "autorizacao ja vigente"
        }

        $publicOffer = Invoke-CurlJson -Method "GET" -Url "$api/public/offers/$($published.id)"
        if ($publicOffer.Status -ne 200) { throw "Oferta publica HTTP $($publicOffer.Status)." }
        if ($publicOffer.Json.product.image_ref -ne $data.products.with_photo.image_ref) {
            throw "A fotografia declarada nao saiu na oferta publica."
        }
        $publicContacts = Invoke-CurlJson -Method "GET" -Url "$api/public/offers/$($published.id)/contacts"
        $values = @($publicContacts.Json.items | ForEach-Object { $_.value })
        if ($values -notcontains $data.contacts.disclosed_email.value) { throw "O contacto autorizado nao esta publico." }
        if ($values -contains $data.contacts.private_phone.value) { throw "O contacto privado ficou publico." }
        Write-Output "projeccao publica confirmada na preparacao"

        Save-State @{
            actor_id = $actorId
            product_with_photo_id = [string]$withPhoto.id
            product_without_photo_id = [string]$withoutPhoto.id
            offer_published_id = [string]$published.id
            offer_draft_id = [string]$draft.id
            contact_private_value = $data.contacts.private_phone.value
            contact_public_value = $data.contacts.disclosed_email.value
            product_name = $data.products.with_photo.name
            image_ref = $data.products.with_photo.image_ref
        }
        Show-Counts
    }
    "verificar" {
        Assert-EvalContainer
        Wait-Healthy $map
        Assert-SmallDatabase | Out-Null
        $state = Read-State
        $data = Read-Dataset
        $api = "http://127.0.0.1:$($map['API_PORT'])"
        $web = "http://127.0.0.1:$($map['WEB_PORT'])"
        $version = Invoke-Psql -Database $ExpectedDb -Sql "SELECT version_num FROM alembic_version;"
        if ($version -ne "0008_offer_status_events") { throw "Alembic $version." }
        Write-Output "alembic=$version base=$ExpectedDb"

        $health = Invoke-CurlJson -Method "GET" -Url "$api/health"
        if ($health.Status -ne 200 -or $health.Json.database -ne "up") { throw "Saude HTTP $($health.Status)." }
        Write-Output "saude HTTP 200 database=up"

        foreach ($path in @("/login", "/", "/ofertas")) {
            $previous = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            $page = & curl.exe --silent --noproxy "*" --max-time 20 -o NUL -w "%{http_code}" "$web$path"
            $ErrorActionPreference = $previous
            if ($page.Trim() -ne "200") { throw "Interface $path HTTP $($page.Trim())." }
            Write-Output "web $path HTTP 200"
        }

        $bad = Invoke-CurlJson -Method "POST" -Url "$api/auth/login" -Body @{
            email = $data.accounts.produtor.email
            password = "palavra-passe-errada"
        }
        if ($bad.Status -ne 401) { throw "Credencial invalida HTTP $($bad.Status)." }
        Write-Output "credencial invalida HTTP 401"

        $token = Get-Token $map $api $data.accounts.produtor.email $data.accounts.produtor.password_env
        $buyerToken = Get-Token $map $api $data.accounts.comprador.email $data.accounts.comprador.password_env
        $readerToken = Get-Token $map $api $data.accounts.consulta.email $data.accounts.consulta.password_env
        $actors = Invoke-CurlJson -Method "GET" -Url "$api/actors" -Token $token
        $producer = Get-ByName $actors.Json $data.producer.display_name
        if (-not $producer -or $producer.coverage_area -ne $data.producer.coverage_area) {
            throw "Actor produtor ou area de actuacao em falta."
        }
        Write-Output "actor produtor consultado com area de actuacao"

        $products = Invoke-CurlJson -Method "GET" -Url "$api/actors/$($state.actor_id)/products" -Token $token
        if (-not (Get-ByName $products.Json $data.products.with_photo.name)) { throw "Produto com fotografia em falta." }
        if (-not (Get-ByName $products.Json $data.products.without_photo.name)) { throw "Produto sem fotografia em falta." }
        Write-Output "produtos consultados"

        $detail = Invoke-CurlJson -Method "GET" -Url "$api/public/offers/$($state.offer_published_id)"
        if ($detail.Status -ne 200) { throw "Ficha publica HTTP $($detail.Status)." }
        if ($detail.Json.product.name -ne $data.products.with_photo.name) { throw "Nome publico inesperado." }
        if ($detail.Json.product.image_ref -ne $data.products.with_photo.image_ref) { throw "Fotografia publica em falta." }
        if ($detail.Json.producer.coverage_area -ne $data.producer.coverage_area) { throw "Area publica em falta." }
        if ($detail.Json.delivery_terms -ne $data.offers.published.delivery_terms) { throw "Condicoes de entrega em falta." }
        Write-Output "oferta publica com fotografia declarada e condicoes de entrega"

        $search = Invoke-CurlJson -Method "GET" -Url "$api/public/offers?q=tomate%20de%20demonstracao"
        $found = $false
        foreach ($item in @($search.Json.items)) {
            if ($item.id -eq $state.offer_published_id) { $found = $true }
        }
        if (-not $found) { throw "A pesquisa publica nao devolveu a oferta de demonstracao." }
        Write-Output "pesquisa publica encontrou a oferta de demonstracao"

        $listed = Invoke-CurlJson -Method "GET" -Url "$api/public/offers?q=feijao%20de%20demonstracao"
        if ([int]$listed.Json.total -ne 0) { throw "O rascunho apareceu na pesquisa publica." }
        Write-Output "rascunho ausente da pesquisa publica"

        $contacts = Invoke-CurlJson -Method "GET" -Url "$api/public/offers/$($state.offer_published_id)/contacts"
        $values = @($contacts.Json.items | ForEach-Object { $_.value })
        if ($values -notcontains $state.contact_public_value) { throw "Contacto autorizado oculto." }
        if ($values -contains $state.contact_private_value) { throw "Contacto privado divulgado." }
        Write-Output "divulgacao: autorizado visivel e privado oculto"

        $probe = Invoke-CurlJson -Method "POST" -Url "$api/actors/$($state.actor_id)/contacts" -Token $token -Body @{
            channel = $data.verification_contact.channel
            value = $data.verification_contact.value
        }
        if ($probe.Status -ne 201) { throw "Contacto de verificacao HTTP $($probe.Status)." }
        $grant = Invoke-CurlJson -Method "POST" -Url "$api/actors/$($state.actor_id)/contacts/$($probe.Json.id)/authorizations" -Token $token -Body @{
            contact_revision = $probe.Json.revision
            purpose = "commercial_discovery"
            notice_version = "v1"
            confirmed = $true
        }
        if ($grant.Status -ne 201) { throw "Concessao de verificacao HTTP $($grant.Status)." }
        $shown = Invoke-CurlJson -Method "GET" -Url "$api/public/offers/$($state.offer_published_id)/contacts"
        $shownValues = @($shown.Json.items | ForEach-Object { $_.value })
        if ($shownValues -notcontains $data.verification_contact.value) { throw "O contacto de verificacao nao ficou publico." }
        $revoke = Invoke-CurlJson -Method "POST" -Url "$api/actors/$($state.actor_id)/contacts/$($probe.Json.id)/authorizations/$($grant.Json.id)/revoke" -Token $token
        if ($revoke.Status -ne 200) { throw "Revogacao HTTP $($revoke.Status)." }
        $hidden = Invoke-CurlJson -Method "GET" -Url "$api/public/offers/$($state.offer_published_id)/contacts"
        $hiddenValues = @($hidden.Json.items | ForEach-Object { $_.value })
        if ($hiddenValues -contains $data.verification_contact.value) { throw "O contacto revogado continua publico." }
        if ($hiddenValues -notcontains $state.contact_public_value) { throw "A revogacao ocultou o contacto de demonstracao." }
        Write-Output "revogacao oculta o contacto de verificacao e mantem o de demonstracao"

        $denied = Invoke-CurlJson -Method "PATCH" -Url "$api/actors/$($state.actor_id)" -Token $readerToken -Body @{
            display_name = "Alteracao recusada da consulta"
        }
        if ($denied.Status -ne 404) { throw "Consulta com escrita HTTP $($denied.Status)." }
        Write-Output "representacao read recusada com HTTP 404"

        $buyerActors = Invoke-CurlJson -Method "GET" -Url "$api/actors" -Token $buyerToken
        $buyer = Get-ByName $buyerActors.Json $data.buyer.display_name
        if (-not $buyer) { throw "Actor comprador em falta." }
        $buyerWrite = Invoke-CurlJson -Method "POST" -Url "$api/actors/$($buyer.id)/products" -Token $buyerToken -Body @{
            name = "Produto que o comprador nao pode criar"
            description = "Tentativa sintetica."
            category = "recusada"
        }
        if ($buyerWrite.Status -ne 422) { throw "Comprador a criar produto HTTP $($buyerWrite.Status)." }
        $cross = Invoke-CurlJson -Method "GET" -Url "$api/actors/$($state.actor_id)/products" -Token $buyerToken
        if ($cross.Status -ne 404) { throw "Comprador a ler o produtor HTTP $($cross.Status)." }
        Write-Output "comprador isolado do produtor"

        $ephemeral = Invoke-CurlJson -Method "POST" -Url "$api/actors/$($state.actor_id)/products" -Token $token -Body @{
            name = "Produto de verificacao I8.4"
            description = "Criado pelo smoke test e destinado a ficar fora do conjunto reposto."
            category = "verificacao"
        }
        if ($ephemeral.Status -ne 201) { throw "Produto de verificacao HTTP $($ephemeral.Status)." }
        $ephemeralOffer = Invoke-CurlJson -Method "POST" -Url "$api/actors/$($state.actor_id)/offers" -Token $token -Body @{
            product_id = $ephemeral.Json.id
            price = "15.00"
            currency = "MZN"
            quantity = "1"
            unit = "kg"
            availability = "available"
            delivery_terms = "Verificacao operacional. Nao inclui transporte."
        }
        if ($ephemeralOffer.Status -ne 201) { throw "Oferta de verificacao HTTP $($ephemeralOffer.Status)." }
        $offerId = $ephemeralOffer.Json.id
        $published = Invoke-CurlJson -Method "POST" -Url "$api/actors/$($state.actor_id)/offers/$offerId/publish" -Token $token
        if ($published.Status -ne 200 -or $published.Json.status -ne "published") { throw "Publicacao de verificacao falhou." }
        $visible = Invoke-CurlJson -Method "GET" -Url "$api/public/offers/$offerId"
        if ($visible.Status -ne 200) { throw "Oferta de verificacao nao ficou publica." }
        $suspended = Invoke-CurlJson -Method "POST" -Url "$api/actors/$($state.actor_id)/offers/$offerId/suspend" -Token $token
        if ($suspended.Status -ne 200 -or $suspended.Json.status -ne "suspended") { throw "Suspensao falhou." }
        $hiddenOffer = Invoke-CurlJson -Method "GET" -Url "$api/public/offers/$offerId"
        if ($hiddenOffer.Status -ne 404) { throw "Oferta suspensa HTTP $($hiddenOffer.Status)." }
        $withdrawn = Invoke-CurlJson -Method "POST" -Url "$api/actors/$($state.actor_id)/offers/$offerId/withdraw" -Token $token
        if ($withdrawn.Status -ne 200 -or $withdrawn.Json.status -ne "withdrawn") { throw "Retirada falhou." }
        $gone = Invoke-CurlJson -Method "GET" -Url "$api/public/offers/$offerId"
        if ($gone.Status -ne 404) { throw "Oferta retirada HTTP $($gone.Status)." }
        $events = Invoke-Psql -Database $ExpectedDb -Sql "SELECT count(*) FROM offer_status_events WHERE offer_id = '$offerId';"
        if ([int]$events -lt 3) { throw "Eventos de oferta: $events." }
        Write-Output "ciclo publicar/suspender/retirar com $events eventos"

        $still = Invoke-CurlJson -Method "GET" -Url "$api/public/offers/$($state.offer_published_id)"
        if ($still.Status -ne 200) { throw "A oferta de demonstracao deixou de estar publica." }
        Write-Output "oferta de demonstracao mantem-se publicada"

        $missingId = "00000000-0000-4000-8000-000000000099"
        $missingApi = Invoke-CurlJson -Method "GET" -Url "$api/public/offers/$missingId"
        $previous = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $missingWeb = & curl.exe --silent --noproxy "*" --max-time 20 "$web/ofertas/$missingId"
        $missingCode = & curl.exe --silent --noproxy "*" --max-time 20 -o NUL -w "%{http_code}" "$web/ofertas/$missingId"
        $ErrorActionPreference = $previous
        $hasMissingText = [bool]((($missingWeb | Out-String) -match "Oferta n.o encontrada"))
        Write-Output "soft404 api=$($missingApi.Status) web=$($missingCode.Trim()) texto=$hasMissingText"

        $logs = & docker @(Get-ComposeArgs) logs --tail 300 api 2>&1 | Out-String
        if ($logs.Contains($state.contact_public_value) -or $logs.Contains($state.contact_private_value) -or $logs.Contains($data.verification_contact.value)) {
            throw "Os logs recentes da API incluem um contacto sintetico."
        }
        Write-Output "logs recentes da API sem os contactos sinteticos"
        Show-Counts
        Write-Output "verificar concluido"
    }
    "backup" {
        Assert-EvalContainer
        $dir = Join-Path $Root "avaliacao-backups"
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
        $name = "kaivita-avaliacao-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".dump"
        $dest = Join-Path $dir $name
        Invoke-Compose @("exec", "-T", "db", "pg_dump", "-U", $ExpectedUser, "-d", $ExpectedDb, "--format=custom", "--no-owner", "--no-privileges", "--file=/tmp/avaliacao.dump")
        Invoke-Compose @("cp", "db:/tmp/avaliacao.dump", $dest)
        Invoke-Compose @("exec", "-T", "db", "rm", "-f", "/tmp/avaliacao.dump")
        $size = (Get-Item -LiteralPath $dest).Length
        Write-Output "backup=$name bytes=$size"
    }
    "recuperar" {
        if (-not $Ficheiro) { throw "Indicar -Ficheiro para o dump." }
        $dump = (Resolve-Path -LiteralPath $Ficheiro).Path
        $backupRoot = (Resolve-Path -LiteralPath (Join-Path $Root "avaliacao-backups")).Path
        if (-not $dump.StartsWith($backupRoot)) { throw "O dump tem de estar em avaliacao-backups." }
        if (-not $dump.EndsWith(".dump")) { throw "Extensao recusada." }
        Assert-EvalContainer
        if ($Sobrepor) {
            if (-not $Confirmar) { throw "A reposicao sobre a base de avaliacao exige -Confirmar." }
            Invoke-Compose @("stop", "api", "web")
            Invoke-Psql -Database "postgres" -Sql "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$ExpectedDb' AND pid <> pg_backend_pid();" | Out-Null
            Invoke-Psql -Database "postgres" -Sql "DROP DATABASE $ExpectedDb;" | Out-Null
            Invoke-Psql -Database "postgres" -Sql "CREATE DATABASE $ExpectedDb;" | Out-Null
            Invoke-Compose @("cp", $dump, "db:/tmp/restauro.dump")
            $previous = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            & docker @(Get-ComposeArgs) exec -T db pg_restore -U $ExpectedUser -d $ExpectedDb --no-owner --no-privileges --exit-on-error /tmp/restauro.dump
            $restoreCode = $LASTEXITCODE
            $ErrorActionPreference = $previous
            Invoke-Compose @("exec", "-T", "db", "rm", "-f", "/tmp/restauro.dump")
            if ($restoreCode -ne 0) { throw "pg_restore sobre a base de avaliacao falhou." }
            Invoke-Compose @("start", "api", "web")
            Wait-Healthy $map
            $version = Invoke-Psql -Database $ExpectedDb -Sql "SELECT version_num FROM alembic_version;"
            if ($version -ne "0008_offer_status_events") { throw "Alembic apos restauro: $version." }
            Write-Output "restauro sobreposto alembic=$version"
            Show-Counts
        } else {
            Invoke-Psql -Database "postgres" -Sql "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$RestoreDb' AND pid <> pg_backend_pid();" | Out-Null
            Invoke-Psql -Database "postgres" -Sql "DROP DATABASE IF EXISTS $RestoreDb;" | Out-Null
            Invoke-Psql -Database "postgres" -Sql "CREATE DATABASE $RestoreDb;" | Out-Null
            Invoke-Compose @("cp", $dump, "db:/tmp/restauro.dump")
            $previous = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            & docker @(Get-ComposeArgs) exec -T db pg_restore -U $ExpectedUser -d $RestoreDb --no-owner --no-privileges --exit-on-error /tmp/restauro.dump
            $restoreCode = $LASTEXITCODE
            $ErrorActionPreference = $previous
            Invoke-Compose @("exec", "-T", "db", "rm", "-f", "/tmp/restauro.dump")
            if ($restoreCode -ne 0) { throw "pg_restore na base lateral falhou." }
            $sql = "SELECT 'users=' || (SELECT count(*) FROM users) || ' actors=' || (SELECT count(*) FROM actors) || ' products=' || (SELECT count(*) FROM products) || ' offers=' || (SELECT count(*) FROM offers) || ' contacts=' || (SELECT count(*) FROM public_contacts) || ' authorizations=' || (SELECT count(*) FROM publication_authorizations) || ' events=' || (SELECT count(*) FROM offer_status_events) || ' alembic=' || (SELECT version_num FROM alembic_version);"
            $side = Invoke-Psql -Database $RestoreDb -Sql $sql
            Write-Output "restauro-lateral $side"
            Invoke-Psql -Database "postgres" -Sql "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$RestoreDb' AND pid <> pg_backend_pid();" | Out-Null
            Invoke-Psql -Database "postgres" -Sql "DROP DATABASE $RestoreDb;" | Out-Null
            Write-Output "base lateral removida"
            Show-Counts
        }
    }
    "persistencia" {
        $state = Read-State
        Invoke-Compose @("restart")
        Wait-Healthy $map
        $api = "http://127.0.0.1:$($map['API_PORT'])"
        $detail = Invoke-CurlJson -Method "GET" -Url "$api/public/offers/$($state.offer_published_id)"
        if ($detail.Status -ne 200 -or $detail.Json.product.name -ne $state.product_name) {
            throw "A oferta publica nao sobreviveu ao reinicio."
        }
        $version = Invoke-Psql -Database $ExpectedDb -Sql "SELECT version_num FROM alembic_version;"
        Write-Output "persistencia oferta mantida alembic=$version"
        Show-Counts
    }
    "repor" {
        if (-not $Confirmar) { throw "A reposicao inicial apaga so o volume $ExpectedVolume e exige -Confirmar." }
        Assert-ResolvedProject $map | Out-Null
        Invoke-Compose @("down", "-v")
        $names = @(docker volume ls --format "{{.Name}}")
        if ($names -contains $ExpectedVolume) { throw "O volume de avaliacao continua presente." }
        if ($names -notcontains "kaivita-produtor-academico_pgdata") { throw "O volume de desenvolvimento nao foi encontrado depois da reposicao." }
        Write-Output "volume de avaliacao removido; volume de desenvolvimento presente"
        Invoke-Compose @("up", "-d")
        Wait-Healthy $map
        Assert-EvalContainer
        $users = Assert-SmallDatabase
        if ($users -ne 0) { throw "A base reposta nao estava vazia: $users contas." }
        $version = Invoke-Psql -Database $ExpectedDb -Sql "SELECT version_num FROM alembic_version;"
        if ($version -ne "0008_offer_status_events") { throw "Alembic apos reposicao: $version." }
        Write-Output "reposicao vazia alembic=$version"
    }
}
