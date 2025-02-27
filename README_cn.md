# NSFW Detector

## 简介

这是一个 NSFW 内容检测器，它基于 [Falconsai/nsfw_image_detection](https://huggingface.co/Falconsai/nsfw_image_detection) 。  
模型: google/vit-base-patch16-224-in21k

你可以在这里验证它的准确度：[NSFW 检测器](https://www.vx.link/nsfw_detector.html)

相比其它常见的 NSFW 检测器，这个检测器的优势在于：

* 基于 AI ，准确度更好。
* 支持纯 CPU 推理，可以运行在大部分服务器上。
* 自动调度多个 CPU 加速推理。
* 简单判断，只有两个类别：nsfw 和 normal。
* 以 API 的方式提供服务，更方便集成到其它应用中。
* 基于 Docker 部署，便于分布式部署。
* 纯本地，保护您的数据安全。

### 性能需求

运行这个模型最多需要 2GB 的内存。不需要显卡的支持。  
在同时处理大量请求时，可能需要更多的内存。

### 支持的文件类型

这个检测器支持检查的文件类型：

* ✅ 图片（已支持）
* ✅ PDF 文件（已支持）
* ✅ 视频（已支持）
* ✅ 压缩包中的文件（已支持）
* ✅ Doc,Docx（已支持）

## 快速开始

### 启动 API 服务器

```bash
docker run -d -p 3333:3333 --name nsfw-detector vxlink/nsfw_detector:latest
```

如果要直接检查服务器本地路径的文件，请将路径挂载到容器中。
通常推荐挂载路径与容器内路径一致，以避免混淆。

```bash
docker run -d -p 3333:3333 -v /path/to/files:/path/to/files --name nsfw-detector vxlink/nsfw_detector:latest
```

支持的系统架构：`x86_64`、`ARM64`。

### 使用 API 进行内容检查

```bash
# 检测
curl -X POST -F "file=@/path/to/image.jpg" http://localhost:3333/check

# 检查本地的文件
curl -X POST -F "path=/path/to/image.jpg" http://localhost:3333/check
```

### 使用内置的 Web 界面进行检测

访问地址：[http://localhost:3333](http://localhost:3333)

## 编辑配置文件  

现在，您可以通过挂载 /tmp 目录，并在该目录下创建一个名为  config 的文件，来配置检测器的行为。
您可以查看 [config](config) 文件作为参考。

* `nsfw_threshold` 当目标文件的 NSFW 值超过多少时设定为匹配项目并作为结果返回。
* `ffmpeg_max_frames` 处理视频时最多处理多少帧。
* `ffmpeg_max_timeout` 处理视频时的超时限制。

此外， /tmp 目录作为容器中的临时目录，配置到一个高性能的存储设备上会提高性能。

## 公共 API

可以使用 vx.link 提供的公共 API 服务来检测 NSFW 内容。

```bash
# 检测文件，会自动识别文件类型
curl -X POST -F "file=@/path/to/image.jpg" https://vx.link/public/nsfw
```

* 不会保存你提交的图片。
* 请注意，该 API 速率限制为每分钟 30 次请求。

## 许可证

本项目基于 Apache 2.0 许可证开源。
