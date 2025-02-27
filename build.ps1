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
    Write-Host "  -Version       Specify version tag (default: $SCRIPT_VERSION)"
    Write-Host "  -Help          Show this help message"
    Write-Host "  -NoCache       Disable build cache"
    Write-Host "  -Platform      Specify target platforms (default: $NATIVE_PLATFORM)"
    Write-Host "  -AllPlatforms  Build for all supported platforms ($ALL_PLATFORMS)"
}

# 处理命令行参数
if ($Help) {
    Show-Help
    exit 0
}

# 处理版本参数
if ($Version) {
    $SCRIPT_VERSION = $Version
}

# 处理平台参数 - 重要：这些检查的顺序很重要
if ($AllPlatforms) {
    $PLATFORM = $ALL_PLATFORMS
    Write-Host "Building for all platforms: $PLATFORM"
}
elseif ($Platform) {
    $PLATFORM = $Platform
    Write-Host "Building for specified platform(s): $PLATFORM"
}
elseif ($Push) {
    # 如果要推送且没有指定平台，默认为所有平台
    $PLATFORM = $ALL_PLATFORMS
    Write-Host "Push requested, building for all platforms: $PLATFORM"
}
else {
    Write-Host "Building for native platform: $PLATFORM"
}

# 处理缓存参数
if ($NoCache) {
    $CACHE_FROM = "--no-cache"
    Write-Host "Build cache disabled"
}
else {
    Write-Host "Using build cache"
}

Write-Host "`nBuild Configuration Summary:"
Write-Host "----------------------------"
Write-Host "- Image name: ${IMAGE_NAME}"
Write-Host "- Version: ${SCRIPT_VERSION}"
Write-Host "- Push to registry: $($Push.IsPresent)"
Write-Host "- Target platforms: ${PLATFORM}"
Write-Host "- Cache configuration: $(if ($CACHE_FROM -eq '') { 'Enabled' } else { 'Disabled' })"
Write-Host "----------------------------`n"

# 验证 Docker 是否已登录到 Registry（如果需要推送）
if ($Push) {
    try {
        $loginStatus = docker info | Select-String "Username"
        if (-not $loginStatus) {
            Write-Host "Warning: You don't appear to be logged into Docker Hub. Images may fail to push."
            Write-Host "Please run 'docker login' before using the -Push flag."
            
            $proceed = Read-Host "Do you want to continue anyway? (y/N)"
            if ($proceed -ne "y" -and $proceed -ne "Y") {
                Write-Host "Build cancelled."
                exit 1
            }
        }
        else {
            Write-Host "Docker Hub login verified."
        }
    }
    catch {
        Write-Host "Error checking Docker login status: $_"
        Write-Host "Continuing anyway, but push may fail..."
    }
}

# 创建缓存目录（如果不存在）
if ($CACHE_FROM -eq '') {
    New-Item -ItemType Directory -Force -Path $CACHE_DIR | Out-Null
    Write-Host "Cache directory ready: $CACHE_DIR"
}

# 配置 buildx 构建器
$BUILDER = "nsfw-detector-builder"

# 检查 buildx 是否可用
try {
    $buildxVersion = docker buildx version
    Write-Host "Docker Buildx is available: $buildxVersion"
}
catch {
    Write-Host "Error: Docker Buildx is not available. Please install or upgrade Docker Desktop." -ForegroundColor Red
    exit 1
}

# 检查构建器是否存在
$builderExists = $false
try {
    $buildersOutput = docker buildx ls
    $builderExists = $buildersOutput -match $BUILDER
}
catch {
    $builderExists = $false
}

# 创建或使用构建器
if (-not $builderExists) {
    Write-Host "Creating new buildx builder: $BUILDER"
    docker buildx create --name $BUILDER `
        --driver docker-container `
        --driver-opt network=host `
        --buildkitd-flags '--allow-insecure-entitlement security.insecure' `
        --use
}
else {
    Write-Host "Using existing buildx builder: $BUILDER"
    docker buildx use $BUILDER
}

# 确保构建器正在运行
docker buildx inspect --bootstrap

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

# 根据是否推送添加适当标志
if ($Push) {
    # 远程构建模式：推送到仓库
    $BUILD_CMD += " --push"
    Write-Host "Image will be pushed to registry after build"
}
elseif ($PLATFORM -eq $NATIVE_PLATFORM) {
    # 本地构建模式（单一本机平台）：使用 --load
    $BUILD_CMD += " --load"
    Write-Host "Image will be loaded into local Docker daemon"
}
else {
    # 本地构建模式（多平台或非本机平台）
    Write-Host "Warning: Building for non-native platform(s) without push."
    Write-Host "Images will be available through buildx, but not in regular docker images list."
    
    # 询问用户是否要继续
    $proceed = Read-Host "This configuration may not be what you want. Continue? (y/N)"
    if ($proceed -ne "y" -and $proceed -ne "Y") {
        Write-Host "Build cancelled."
        exit 1
    }
}

$BUILD_CMD += " ."

# 执行构建
Write-Host "`nExecuting build command:"
Write-Host $BUILD_CMD
Write-Host "`nBuilding... (this may take a while)"

try {
    Invoke-Expression $BUILD_CMD
    
    if ($LASTEXITCODE -ne 0) {
        throw "Build command failed with exit code $LASTEXITCODE"
    }
    
    Write-Host "Build completed successfully!" -ForegroundColor Green
}
catch {
    Write-Host "Build failed: $_" -ForegroundColor Red
    exit 1
}

# 验证构建结果（仅在推送模式下）
if ($Push) {
    Write-Host "`nVerifying images were pushed to registry..."
    
    $platformList = $PLATFORM -split ','
    $verificationSucceeded = $true
    
    try {
        Write-Host "Checking manifest for ${IMAGE_NAME}:${SCRIPT_VERSION}"
        $manifest = docker manifest inspect "${IMAGE_NAME}:${SCRIPT_VERSION}" | ConvertFrom-Json
        
        Write-Host "Manifest details:"
        foreach ($platform in $platformList) {
            $platformFound = $false
            foreach ($m in $manifest.manifests) {
                $manifestPlatform = "$($m.platform.os)/$($m.platform.architecture)"
                if ($manifestPlatform -eq $platform.Trim()) {
                    Write-Host "✓ Found image for platform: $platform" -ForegroundColor Green
                    $platformFound = $true
                    break
                }
            }
            
            if (-not $platformFound) {
                Write-Host "✗ Missing image for platform: $platform" -ForegroundColor Red
                $verificationSucceeded = $false
            }
        }
        
        if ($verificationSucceeded) {
            Write-Host "`nAll platform images were successfully pushed!" -ForegroundColor Green
        }
        else {
            Write-Host "`nWarning: Some platform images may not have been pushed correctly." -ForegroundColor Yellow
        }
    }
    catch {
        Write-Host "Error verifying pushed images: $_" -ForegroundColor Red
        Write-Host "Images may not have been pushed correctly." -ForegroundColor Yellow
    }
}
elseif ($PLATFORM -eq $NATIVE_PLATFORM) {
    # 显示本地构建的镜像
    Write-Host "`nVerifying local images:"
    docker images "${IMAGE_NAME}"
}

# 清理和切换回默认构建器
Write-Host "`nSwitching back to default builder..."
docker buildx use default

Write-Host "`nBuild process complete!"
if ($Push) {
    Write-Host "Images have been pushed to DockerHub as:"
    Write-Host "- ${IMAGE_NAME}:${SCRIPT_VERSION}"
    Write-Host "- ${IMAGE_NAME}:latest"
}
else {
    Write-Host "Images are available as:"
    if ($PLATFORM -eq $NATIVE_PLATFORM) {
        Write-Host "- ${IMAGE_NAME}:${SCRIPT_VERSION} (local)"
        Write-Host "- ${IMAGE_NAME}:latest (local)"
    }
    else {
        Write-Host "- ${IMAGE_NAME}:${SCRIPT_VERSION} (in buildx cache)"
        Write-Host "- ${IMAGE_NAME}:latest (in buildx cache)"
    }
}