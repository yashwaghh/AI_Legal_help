[CmdletBinding()]
param(
    [string]$ProjectId = $(if ($env:GOOGLE_CLOUD_PROJECT) { $env:GOOGLE_CLOUD_PROJECT } else { 'ai-legal-help' }),
    [string]$Region = $env:CLEARCLAUSE_REGION,
    [string]$VertexLocation = $env:CLEARCLAUSE_VERTEX_LOCATION,
    [string]$ManifestPath,
    [string]$PublicDomain = $env:CLEARCLAUSE_PUBLIC_DOMAIN,
    [ValidateSet('runapp', 'loadbalancer')][string]$ExposureMode = 'runapp'
)

$ErrorActionPreference = 'Stop'
$results = [System.Collections.Generic.List[object]]::new()

function Add-Result {
    param([string]$State, [string]$Check, [string]$Details)
    $results.Add([pscustomobject]@{ State = $State; Check = $Check; Details = $Details })
}

function Invoke-GcloudRead {
    param([string[]]$Arguments)
    try {
        $output = @(& gcloud @Arguments --quiet 2>$null)
        return [pscustomobject]@{ ExitCode = $LASTEXITCODE; Lines = $output }
    } catch {
        return [pscustomobject]@{ ExitCode = 127; Lines = @() }
    }
}

if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    Add-Result 'BLOCK' 'Google Cloud CLI' 'gcloud was not found on PATH.'
    $results | Format-Table -AutoSize -Wrap
    exit 2
}

$active = Invoke-GcloudRead @('auth', 'list', '--filter=status:ACTIVE', '--format=value(account)')
if ($active.ExitCode -eq 0 -and @($active.Lines | Where-Object { "$($_)".Trim() }).Count -gt 0) {
    Add-Result 'PASS' 'gcloud authentication' 'An active account is configured; account details are hidden.'
} else {
    Add-Result 'BLOCK' 'gcloud authentication' 'Run gcloud auth login with an account authorized for this project.'
}

$project = Invoke-GcloudRead @('projects', 'describe', $ProjectId, "--format=value(lifecycleState)")
if ($project.ExitCode -eq 0 -and @($project.Lines) -contains 'ACTIVE') {
    Add-Result 'PASS' 'Project access' "Project $ProjectId is active and readable."
} else {
    Add-Result 'BLOCK' 'Project access' 'Project is missing, inactive, or not readable by the active account.'
}

$serviceResult = Invoke-GcloudRead @('services', 'list', '--enabled', "--project=$ProjectId", '--format=value(config.name)')
$enabledServices = @($serviceResult.Lines | ForEach-Object { "$($_)".Trim() } | Where-Object { $_ })
$requiredServices = @(
    'aiplatform.googleapis.com',
    'run.googleapis.com',
    'cloudbuild.googleapis.com',
    'artifactregistry.googleapis.com',
    'firestore.googleapis.com',
    'identitytoolkit.googleapis.com',
    'firebase.googleapis.com',
    'firebaseappcheck.googleapis.com',
    'recaptchaenterprise.googleapis.com',
    'compute.googleapis.com',
    'logging.googleapis.com',
    'monitoring.googleapis.com'
)
if ($serviceResult.ExitCode -ne 0) {
    Add-Result 'BLOCK' 'Required Google APIs' 'Could not read enabled API state; check Service Usage access.'
} else {
    $missingServices = @($requiredServices | Where-Object { $_ -notin $enabledServices })
    if ($missingServices.Count -eq 0) {
        Add-Result 'PASS' 'Required Google APIs' 'All listed APIs are enabled.'
    } else {
        Add-Result 'BLOCK' 'Required Google APIs' "Enable after approval: $($missingServices -join ', ')"
    }
}

if (-not $Region) {
    Add-Result 'BLOCK' 'Approved region' 'Set CLEARCLAUSE_REGION after residency, Vertex availability, and cost review.'
} else {
    Add-Result 'PASS' 'Approved region' "A candidate region is set ($Region); confirm product availability and residency approval."
}

if (-not $VertexLocation) {
    Add-Result 'BLOCK' 'Vertex AI location' 'Set CLEARCLAUSE_VERTEX_LOCATION only after model availability, data residency, and processing terms are reviewed.'
} else {
    Add-Result 'PASS' 'Vertex AI location' "A candidate Vertex location is set ($VertexLocation); confirm the selected model is supported there."
}

if ($ExposureMode -eq 'loadbalancer') {
    if ($PublicDomain -and $PublicDomain -match '^(?=.{1,253}$)([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$') {
        Add-Result 'PASS' 'Public domain' 'A syntactically valid domain is set; confirm ownership and DNS control.'
    } else {
        Add-Result 'BLOCK' 'Public domain' 'A domain under your control is required for the HTTPS load balancer and Cloud Armor path.'
    }
} else {
    Add-Result 'PASS' 'Public URL mode' 'Use Cloud Run generated run.app HTTPS; no custom domain is required. Cloud Armor IP filtering is not attached.'
}

$firebaseVars = @(
    'FIREBASE_API_KEY',
    'FIREBASE_AUTH_DOMAIN',
    'FIREBASE_APP_ID',
    'FIREBASE_APP_CHECK_SITE_KEY'
)
$cloudConfig = Invoke-GcloudRead @('run', 'services', 'describe', 'clearclause-api', "--region=$Region", "--project=$ProjectId", '--format=json')
$cloudEnvNames = @()
if ($cloudConfig.ExitCode -eq 0) {
    try {
        $cloudService = ($cloudConfig.Lines -join "`n") | ConvertFrom-Json
        $cloudEnvNames = @($cloudService.spec.template.spec.containers[0].env | ForEach-Object { $_.name })
    } catch { $cloudEnvNames = @() }
}
$missingFirebaseVars = @($firebaseVars | Where-Object { $_ -notin $cloudEnvNames -and -not [Environment]::GetEnvironmentVariable($_) })
if ($missingFirebaseVars.Count -eq 0) {
    Add-Result 'PASS' 'Firebase browser configuration' 'Required client values exist in the deployed service or current shell; values are not displayed.'
} else {
    Add-Result 'BLOCK' 'Firebase browser configuration' "Missing: $($missingFirebaseVars -join ', ')."
}

$manifestPath = if ($ManifestPath) { $ManifestPath } else { Join-Path (Split-Path -Parent $PSScriptRoot) 'cloudrun-service.yaml' }
if (Test-Path -LiteralPath $manifestPath) {
    $manifest = Get-Content -LiteralPath $manifestPath -Raw
    $ingressPattern = if ($ExposureMode -eq 'loadbalancer') { 'internal-and-cloud-load-balancing' } else { 'all' }
    if ($manifest -match "run\.googleapis\.com/ingress:\s*$ingressPattern" -and
        $manifest -match 'AUTH_MODE\s*\n\s*value:\s*firebase' -and
        $manifest -match 'RATE_LIMIT_BACKEND\s*\n\s*value:\s*firestore' -and
        $manifest -match 'APP_CHECK_REQUIRED\s*\n\s*value:\s*"true"') {
        Add-Result 'PASS' 'Cloud Run template guardrails' "Ingress matches $ExposureMode mode; Firebase auth, Firestore quota, and required App Check are set."
    } else {
        Add-Result 'BLOCK' 'Cloud Run template guardrails' 'Review ingress, Firebase auth, Firestore quota, and App Check settings in cloudrun-service.yaml.'
    }
    $effectiveManifest = ($manifest -split "`r?`n" | Where-Object { $_ -notmatch '^\s*#' }) -join "`n"
    if ($effectiveManifest -match 'REPLACE_WITH|\bPROJECT_ID\b|REGION-docker\.pkg\.dev') {
        Add-Result 'BLOCK' 'Cloud Run release manifest values' 'Replace every template value, including region, Vertex location, Firebase values, service account, and immutable image digest.'
    } else {
        Add-Result 'PASS' 'Cloud Run release manifest values' 'No obvious template placeholders remain in the selected manifest.'
    }
} else {
    Add-Result 'BLOCK' 'Cloud Run template guardrails' 'cloudrun-service.yaml was not found beside the deployment folder.'
}

if ($Region -and $serviceResult.ExitCode -eq 0 -and 'artifactregistry.googleapis.com' -in $enabledServices) {
    $repositories = Invoke-GcloudRead @('artifacts', 'repositories', 'list', "--project=$ProjectId", "--location=$Region", '--format=value(name)')
    if ($repositories.ExitCode -eq 0 -and @($repositories.Lines | Where-Object { "$($_)" -match '(^|/)clearclause$' }).Count -gt 0) {
        Add-Result 'PASS' 'Artifact Registry' 'Repository clearclause exists in the selected region.'
    } else {
        Add-Result 'BLOCK' 'Artifact Registry' 'Create the Docker repository clearclause after region approval.'
    }
} else {
    Add-Result 'BLOCK' 'Artifact Registry' 'Requires the selected region and enabled Artifact Registry API.'
}

if ('firestore.googleapis.com' -in $enabledServices) {
    $databases = Invoke-GcloudRead @('firestore', 'databases', 'list', "--project=$ProjectId", '--format=value(name,type,locationId)')
    if ($databases.ExitCode -eq 0 -and @($databases.Lines | Where-Object { "$($_)" -match '\(default\)' -and "$($_)" -match 'FIRESTORE_NATIVE|firestore-native' }).Count -gt 0) {
        Add-Result 'PASS' 'Firestore database' 'Default Native-mode database is listed.'
    } elseif ($databases.ExitCode -eq 0) {
        Add-Result 'BLOCK' 'Firestore database' 'Create the default Firestore Native database in the approved region.'
    } else {
        Add-Result 'BLOCK' 'Firestore database' 'Database state could not be read; check Firestore API and IAM access.'
    }
} else {
    Add-Result 'BLOCK' 'Firestore database' 'Enable Firestore API after approval, create Native mode, then configure expiresAt TTL.'
}

$serviceAccounts = Invoke-GcloudRead @('iam', 'service-accounts', 'list', "--project=$ProjectId", '--format=value(email)')
$runtimeEmail = "clearclause-runtime@$ProjectId.iam.gserviceaccount.com"
if ($serviceAccounts.ExitCode -eq 0 -and @($serviceAccounts.Lines | Where-Object { "$($_)".Trim() -eq $runtimeEmail }).Count -gt 0) {
    Add-Result 'PASS' 'Runtime service account' 'Dedicated ClearClause runtime account exists; separately verify its two required roles and no extras.'
} else {
    Add-Result 'BLOCK' 'Runtime service account' 'Create a dedicated account; do not run as the default Compute Engine identity.'
}

if ($Region) {
    $services = Invoke-GcloudRead @('run', 'services', 'list', '--platform=managed', "--region=$Region", "--project=$ProjectId", '--format=value(metadata.name)')
    if ($services.ExitCode -eq 0 -and @($services.Lines | Where-Object { "$($_)".Trim() -eq 'clearclause-api' }).Count -gt 0) {
        Add-Result 'PASS' 'Cloud Run service' 'clearclause-api exists; verify it uses the reviewed image digest and production settings.'
    } elseif ($services.ExitCode -eq 0) {
        Add-Result 'BLOCK' 'Cloud Run service' 'No clearclause-api service is deployed in the selected region.'
    } else {
        Add-Result 'BLOCK' 'Cloud Run service' 'Cloud Run service state could not be read; check API and IAM access.'
    }
} else {
    Add-Result 'BLOCK' 'Cloud Run service' 'Set the approved region before checking Cloud Run resources.'
}

$ttl = Invoke-GcloudRead @('firestore', 'fields', 'ttls', 'list', '--collection-group=clearClauseRateLimits', "--project=$ProjectId", '--format=value(ttlConfig.state)')
if ($ttl.ExitCode -eq 0 -and @($ttl.Lines | Where-Object { "$($_)".Trim() -eq 'ACTIVE' }).Count -gt 0) {
    Add-Result 'PASS' 'Firestore TTL' 'TTL is ACTIVE for collection group clearClauseRateLimits and field expiresAt.'
} else {
    Add-Result 'MANUAL' 'Firestore TTL' 'Confirm TTL is ACTIVE for collection group clearClauseRateLimits and field expiresAt.'
}
Add-Result 'MANUAL' 'Firebase and App Check setup' 'Confirm verified-email auth, authorized domain, reCAPTCHA Enterprise registration, and backend token verification with a real browser session.'
if ($ExposureMode -eq 'loadbalancer') {
    Add-Result 'MANUAL' 'HTTPS edge and Cloud Armor' 'Confirm managed certificate, DNS, serverless NEG, attached policy, preview review, and direct run.app block.'
} else {
    Add-Result 'MANUAL' 'Cloud Armor edge limitation' 'Direct run.app is public without Cloud Armor IP filtering; monitor abuse and migrate to a controlled-domain load balancer for stronger edge controls.'
}
Add-Result 'MANUAL' 'Privacy and legal readiness' 'Approve the public privacy notice, Vertex/provider terms, retention, jurisdiction, support owner, and legal boundaries.'
Add-Result 'MANUAL' 'Release verification' 'Complete staging auth, quota, abuse, prompt-injection, citation, accessibility, cost, and rollback evidence.'

$results | Format-Table -AutoSize -Wrap
$blocked = @($results | Where-Object { $_.State -eq 'BLOCK' }).Count
$manual = @($results | Where-Object { $_.State -eq 'MANUAL' }).Count
Write-Output "`nSummary: $blocked blocking check(s), $manual manual sign-off item(s). This script is read-only; it does not enable APIs, create resources, or deploy."
if ($blocked -gt 0) { exit 1 }
exit 0
