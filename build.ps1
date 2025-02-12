# build.ps1

# 默认配置值
$script:ImageName = "vxlink/nsfw_detector"
$script:Version = "v1.8"  # 默认版本，如果无法读取 build.version 文件时使用
$script:Push = $false
$script:CacheDir = "$env:USERPROFILE\.docker\nsfw_detector_cache"
$script:CacheFrom = ""

# 读取 build.version 文件
$VersionFile = Join-Path $PSScriptRoot "build.version"
if (Test-Path $VersionFile) {
    $script:Version = (Get-Content $VersionFile).Trim()
    Write-Host "Using version from build.version: $Version"
} else {
    Write-Host "Warning: version file not found at $VersionFile, using default version $Version"
}

# 获取本机平台
$script:NativePlatform = $(docker version --format '{{.Server.Os}}/{{.Server.Arch}}').Replace('x86_64', 'amd64')

# 设置目标平台
$script:AllPlatforms = "linux/amd64,linux/arm64"
$script:Platform = $NativePlatform  # 默认仅构建本机平台

function Show-Help {
    Write-Host "Usage: .\build.ps1 [options]"
    Write-Host "Options:"
    Write-Host "  -Push         Push images to registry after building (default: false)"
    Write-Host "  -Version      Specify version tag (default: v1.8)"
    Write-Host "  -NoCache      Disable build cache"
    Write-Host "  -Platform     Specify target platforms (default: native platform)"
    Write-Host "  -AllPlatforms Build for all supported platforms"
    Write-Host "  -Help         Show this help message"
}

# 参数定义
param(
    [switch]$Push,
    [string]$Version,
    [switch]$NoCache,
    [string]$Platform,
    [switch]$AllPlatforms,
    [switch]$Help
)

# 处理帮助参数
if ($Help) {
    Show-Help
    exit 0
}

# 处理参数
if ($Push) {
    $script:Push = $true
    $script:Platform = $AllPlatforms  # 推送时默认构建所有平台
}

if ($Version) {
    $script:Version = $Version
}

if ($NoCache) {
    $script:CacheFrom = "--no-cache"
}

if ($Platform) {
    $script:Platform = $Platform
}

if ($AllPlatforms) {
    $script:Platform = $AllPlatforms
}

# 显示配置信息
Write-Host "Building with configuration:"
Write-Host "- Version: $Version"
Write-Host "- Push to registry: $Push"
Write-Host "- Native platform: $NativePlatform"
Write-Host "- Target platforms: $Platform"
Write-Host "- Cache enabled: $(if ($CacheFrom -eq '') { 'yes' } else { 'no' })"

# 创建缓存目录
if (-not (Test-Path $CacheDir)) {
    New-Item -ItemType Directory -Path $CacheDir -Force | Out-Null
}

# 配置 buildx 构建器
$BuilderName = "nsfw-detector-builder"
$builderExists = $null
try {
    $builderExists = docker buildx inspect $BuilderName 2>$null
} catch {
    $builderExists = $null
}

if (-not $builderExists) {
    docker buildx create --name $BuilderName `
        --driver docker-container `
        --driver-opt network=host `
        --buildkitd-flags '--allow-insecure-entitlement security.insecure' `
        --use
} else {
    docker buildx use $BuilderName
}

# 设置缓存配置参数
if ($CacheFrom -eq "") {
    $CacheConfig = "--cache-from=type=local,src=$CacheDir --cache-to=type=local,dest=$CacheDir,mode=max"
} else {
    $CacheConfig = $CacheFrom
}

# 构建基础命令
$BuildCmd = "docker buildx build " +
    "--platform $Platform " +
    "--tag ${ImageName}:${Version} " +
    "--tag ${ImageName}:latest " +
    "--file dockerfile " +
    "$CacheConfig " +
    "--build-arg BUILDKIT_INLINE_CACHE=1"

if ($Push) {
    # 远程构建模式：推送到仓库
    $BuildCmd += " --push"
} elseif ($Platform -eq $NativePlatform) {
    # 本地构建模式（单一本机平台）：使用 --load
    $BuildCmd += " --load"
} else {
    # 本地构建模式（多平台或非本机平台）
    Write-Host "Warning: Building for non-native platform(s). Images will be available through docker buildx, but not in regular docker images list."
}

$BuildCmd += " ."

# 执行构建
Write-Host "Executing build command..."
Invoke-Expression $BuildCmd

# 验证构建结果（仅在推送模式下）
if ($Push) {
    Write-Host "Verifying manifest for version $Version..."
    docker manifest inspect "${ImageName}:${Version}"

    Write-Host "Verifying manifest for latest..."
    docker manifest inspect "${ImageName}:latest"
}

# 清理和切换构建器
if ($Push) {
    docker buildx use default
} else {
    Write-Host "Build completed for platform(s): $Platform"
}

Write-Host "Build complete!"
Write-Host "Built images:"
Write-Host "- ${ImageName}:${Version}"
Write-Host "- ${ImageName}:latest"

if ($Push) {
    Write-Host "Images have been pushed to registry"
} elseif ($Platform -eq $NativePlatform) {
    Write-Host "Images are available locally via 'docker images'"
} else {
    Write-Host "Images are available through buildx"
}