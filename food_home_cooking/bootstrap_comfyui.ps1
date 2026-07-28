[CmdletBinding()]
param(
    [string]$ComfyRoot = "",
    [switch]$InstallRuntime,
    [switch]$InstallModels,
    [switch]$Start,
    [switch]$Restart,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$headers = @{
    "Accept" = "application/vnd.github+json"
    "User-Agent" = "food-home-cooking-comfy-bootstrap"
}

if (-not $ComfyRoot) {
    $workspaceParent = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    $ComfyRoot = Join-Path $workspaceParent "ComfyUI_windows_portable"
}

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Download-File {
    param(
        [string]$Url,
        [string]$Destination
    )
    $destinationPath = [IO.Path]::GetFullPath($Destination)
    $destinationDir = Split-Path -Parent $destinationPath
    New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null
    if ((Test-Path -LiteralPath $destinationPath) -and -not $Force) {
        $length = (Get-Item -LiteralPath $destinationPath).Length
        if ($length -gt 1MB) {
            Write-Host "Already present: $destinationPath"
            return
        }
    }
    Write-Step "Downloading $(Split-Path -Leaf $destinationPath)"
    Invoke-WebRequest -UseBasicParsing -Uri $Url -Headers $headers -OutFile $destinationPath
}

function Get-SevenZip {
    $commands = @("7z", "7zz")
    foreach ($command in $commands) {
        $found = Get-Command $command -ErrorAction SilentlyContinue
        if ($found) {
            return $found.Source
        }
    }
    foreach ($path in @(
        "$env:ProgramFiles\7-Zip\7z.exe",
        "${env:ProgramFiles(x86)}\7-Zip\7z.exe"
    )) {
        if ($path -and (Test-Path -LiteralPath $path)) {
            return $path
        }
    }
    return $null
}

function Install-ComfyRuntime {
    if (Test-Path -LiteralPath (Join-Path $ComfyRoot "run_nvidia_gpu.bat")) {
        Write-Host "ComfyUI Portable already present: $ComfyRoot"
        return
    }

    Write-Step "Resolving the latest official ComfyUI Portable release"
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/Comfy-Org/ComfyUI/releases/latest" -Headers $headers
    $asset = $release.assets |
        Where-Object { $_.name -match "windows_portable.*nvidia.*\.(zip|7z)$" } |
        Sort-Object @{ Expression = { if ($_.name -match "\.zip$") { 0 } else { 1 } } }, name |
        Select-Object -First 1
    if (-not $asset) {
        throw "The latest ComfyUI release did not include a Windows Nvidia Portable asset."
    }

    $archive = Join-Path $env:TEMP $asset.name
    Download-File -Url $asset.browser_download_url -Destination $archive
    $extractParent = Split-Path -Parent $ComfyRoot
    New-Item -ItemType Directory -Force -Path $extractParent | Out-Null
    Write-Step "Extracting $($asset.name)"

    if ($archive.EndsWith(".zip", [StringComparison]::OrdinalIgnoreCase)) {
        Expand-Archive -LiteralPath $archive -DestinationPath $extractParent -Force
    }
    else {
        $sevenZip = Get-SevenZip
        if (-not $sevenZip) {
            throw "The official Portable release is .7z. Install 7-Zip, then rerun this script."
        }
        & $sevenZip x "-o$extractParent" $archive | Out-Host
        if ($LASTEXITCODE -ne 0) {
            throw "7-Zip failed to extract $archive"
        }
    }

    if (-not (Test-Path -LiteralPath (Join-Path $ComfyRoot "run_nvidia_gpu.bat"))) {
        throw "ComfyUI archive extracted, but expected folder was not found: $ComfyRoot"
    }
}

function Get-ComfyModelsRoot {
    $newLayout = Join-Path $ComfyRoot "ComfyUI\models"
    if (Test-Path -LiteralPath (Join-Path $ComfyRoot "ComfyUI")) {
        return $newLayout
    }
    return (Join-Path $ComfyRoot "models")
}

function Ensure-ModelFile {
    param(
        [string]$Url,
        [string]$RelativePath
    )
    $modelsRoot = Get-ComfyModelsRoot
    $destination = Join-Path $modelsRoot $RelativePath
    $legacyDestination = Join-Path (Join-Path $ComfyRoot "models") $RelativePath
    if ((Test-Path -LiteralPath $legacyDestination) -and -not (Test-Path -LiteralPath $destination)) {
        Write-Step "Moving existing model into ComfyUI model directory: $(Split-Path -Leaf $destination)"
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
        Move-Item -LiteralPath $legacyDestination -Destination $destination
        return
    }
    Download-File -Url $Url -Destination $destination
}

function Install-FoodModels {
    if (-not (Test-Path -LiteralPath (Join-Path $ComfyRoot "run_nvidia_gpu.bat"))) {
        throw "ComfyUI Portable is missing. Rerun with -InstallRuntime first."
    }

    $models = @(
        @{
            Url = "https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8/resolve/main/flux-2-klein-4b-fp8.safetensors?download=true"
            Destination = "diffusion_models\flux-2-klein-4b-fp8.safetensors"
        },
        @{
            Url = "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors?download=true"
            Destination = "text_encoders\qwen_3_4b.safetensors"
        },
        @{
            Url = "https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors?download=true"
            Destination = "vae\flux2-vae.safetensors"
        },
        @{
            Url = "https://huggingface.co/notkenski/upscalers/resolve/main/4x-UltraSharp.pth?download=true"
            Destination = "upscale_models\4x-UltraSharp.pth"
        },
        @{
            Url = "https://huggingface.co/ByteDance/SDXL-Lightning/resolve/main/sdxl_lightning_4step.safetensors?download=true"
            Destination = "checkpoints\sdxl_lightning_4step.safetensors"
        }
    )
    foreach ($model in $models) {
        Ensure-ModelFile -Url $model.Url -RelativePath $model.Destination
    }
}

function Stop-ComfyRuntime {
    $pythonRoot = [IO.Path]::GetFullPath((Join-Path $ComfyRoot "python_embeded"))
    $processes = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {
        try {
            $_.Path -and ([IO.Path]::GetFullPath($_.Path)).StartsWith($pythonRoot, [StringComparison]::OrdinalIgnoreCase)
        }
        catch {
            $false
        }
    }
    foreach ($process in $processes) {
        Write-Step "Stopping ComfyUI python process $($process.Id)"
        Stop-Process -Id $process.Id -Force -ErrorAction Stop
    }
}

if ($InstallRuntime) {
    Install-ComfyRuntime
}
if ($InstallModels) {
    Install-FoodModels
}

$startScript = Join-Path $ComfyRoot "start_food_comfyui.cmd"
if (Test-Path -LiteralPath (Join-Path $ComfyRoot "run_nvidia_gpu.bat")) {
    @"
@echo off
cd /d "%~dp0"
.\python_embeded\python.exe -s ComfyUI\main.py --windows-standalone-build --lowvram
"@ | Set-Content -LiteralPath $startScript -Encoding ASCII
    Write-Host "Low-VRAM launcher: $startScript"
}

if ($Restart) {
    Stop-ComfyRuntime
}

if ($Start -or $Restart) {
    if (-not (Test-Path -LiteralPath $startScript)) {
        throw "ComfyUI is not installed at $ComfyRoot. Run with -InstallRuntime first."
    }
    Write-Step "Starting ComfyUI in a separate low-VRAM window"
    Start-Process -FilePath $startScript -WorkingDirectory $ComfyRoot -WindowStyle Hidden
}
