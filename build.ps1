[CmdletBinding()]
param (
    [switch]$Push,
    [string]$Version,
    [switch]$Help,
    [switch]$NoCache,
    [string]$Platform,
    [switch]$AllPlatforms
)

# 设置错误时停止执行
$ErrorActionPreference = "Stop"

# 默认配置值
$IMAGE_NAME = "vxlink/nsfw_detector"
$SCRIPT_VERSION = "v1.8"  # 默认版本，如果无法读取 build.version 文件时使用
$PUSH = $false
$CACHE_DIR = Join-Path $env:USERPROFILE ".docker\nsfw_detector_cache"
$CACHE_FROM = ""

# 读取 build.version 文件
$VERSION_FILE = "./build.version"
if (Test-Path $VERSION_FILE) {
    $SCRIPT_VERSION = (Get-Content $VERSION_FILE).Trim()
    Write-Host "Using version from build.version: $SCRIPT_VERSION"
}
else {
    Write-Host "Warning: version file not found at $VERSION_FILE, using default version $SCRIPT_VERSION"
}

# 检测本机平台
$NATIVE_PLATFORM = (docker version -f '{{.Server.Os}}/{{.Server.Arch}}') -replace 'x86_64', 'amd64'

# 设置目标平台（默认包含所有支持的平台）
$ALL_PLATFORMS = "linux/amd64,linux/arm64"
$PLATFORM = $NATIVE_PLATFORM  # 默认仅构建本机平台

# 帮助信息显示函数
function Show-Help {
    Write-Host "Usage: $($MyInvocation.MyCommand.Name) [options]"
    Write-Host "Options:"
    Write-Host "  -Push          Push images to registry after building (default: false)"
    Write-Host "  -Version       Specify version tag (default: v0.3)"
    Write-Host "  -Help          Show this help message"
    Write-Host "  -NoCache       Disable build cache"
    Write-Host "  -Platform      Specify target platforms (default: native platform)"
    Write-Host "  -AllPlatforms  Build for all supported platforms"
}

# 处理命令行参数
if ($Help) {
    Show-Help
    exit 0
}

if ($Push) {
    $PUSH = $true
    $PLATFORM = $ALL_PLATFORMS  # 推送时默认构建所有平台
}

if ($Version) {
    $SCRIPT_VERSION = $Version
}

if ($NoCache) {
    $CACHE_FROM = "--no-cache"
}

if ($Platform) {
    $PLATFORM = $Platform
}

if ($AllPlatforms) {
    $PLATFORM = $ALL_PLATFORMS
}

Write-Host "Building with configuration:"
Write-Host "- Version: ${SCRIPT_VERSION}"
Write-Host "- Push to registry: ${PUSH}"
Write-Host "- Native platform: ${NATIVE_PLATFORM}"
Write-Host "- Target platforms: ${PLATFORM}"
Write-Host "- Cache enabled: $(if ($CACHE_FROM -eq '') { 'yes' } else { 'no' })"

# 创建缓存目录（如果不存在）
New-Item -ItemType Directory -Force -Path $CACHE_DIR | Out-Null

# 配置 buildx 构建器
$BUILDER = "nsfw-detector-builder"
$builderExists = $null
try {
    $builderExists = docker buildx inspect $BUILDER 2>$null
}
catch {
    $builderExists = $null
}

if (-not $builderExists) {
    docker buildx create --name $BUILDER `
        --driver docker-container `
        --driver-opt network=host `
        --buildkitd-flags '--allow-insecure-entitlement security.insecure' `
        --use
}
else {
    docker buildx use $BUILDER
}

# 设置缓存配置参数
if ($CACHE_FROM -eq "") {
    $CACHE_CONFIG = "--cache-from=type=local,src=${CACHE_DIR} --cache-to=type=local,dest=${CACHE_DIR},mode=max"
}
else {
    $CACHE_CONFIG = $CACHE_FROM
}

# 构建基础命令
$BUILD_CMD = "docker buildx build " +
    "--platform ${PLATFORM} " +
    "--tag ${IMAGE_NAME}:${SCRIPT_VERSION} " +
    "--tag ${IMAGE_NAME}:latest " +
    "--file dockerfile " +
    "${CACHE_CONFIG} " +
    "--build-arg BUILDKIT_INLINE_CACHE=1"

if ($PUSH) {
    # 远程构建模式：推送到仓库
    $BUILD_CMD += " --push"
}
elseif ($PLATFORM -eq $NATIVE_PLATFORM) {
    # 本地构建模式（单一本机平台）：使用 --load
    $BUILD_CMD += " --load"
}
else {
    # 本地构建模式（多平台或非本机平台）：输出到本地 docker 镜像
    Write-Host "Warning: Building for non-native platform(s). Images will be available through docker buildx, but not in regular docker images list."
}

$BUILD_CMD += " ."

# 执行构建
Write-Host "Executing build command..."
Invoke-Expression $BUILD_CMD

# 验证构建结果（仅在推送模式下）
if ($PUSH) {
    Write-Host "Verifying manifest for version ${SCRIPT_VERSION}..."
    docker manifest inspect "${IMAGE_NAME}:${SCRIPT_VERSION}"

    Write-Host "Verifying manifest for latest..."
    docker manifest inspect "${IMAGE_NAME}:latest"
}

# 清理和切换构建器
if ($PUSH) {
    docker buildx use default
}
else {
    Write-Host "Build completed for platform(s): ${PLATFORM}"
}

Write-Host "Build complete!"
Write-Host "Built images:"
Write-Host "- ${IMAGE_NAME}:${SCRIPT_VERSION}"
Write-Host "- ${IMAGE_NAME}:latest"

if ($PUSH) {
    Write-Host "Images have been pushed to registry"
}
elseif ($PLATFORM -eq $NATIVE_PLATFORM) {
    Write-Host "Images are available locally via 'docker images'"
}
else {
    Write-Host "Images are available through buildx"
}