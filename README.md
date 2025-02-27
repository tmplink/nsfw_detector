# NSFW Detector

[中文指南](README_cn.md) | [日本語ガイド](README_jp.md)

## Introduction

This is an NSFW content detector based on [Falconsai/nsfw_image_detection](https://huggingface.co/Falconsai/nsfw_image_detection).  
Model: google/vit-base-patch16-224-in21k

You can try it online(using Public API): [NSFW Detector](https://www.vx.link/nsfw_detector.html)

Compared to other common NSFW detectors, this detector has the following advantages:

* AI-based, providing better accuracy.
* Supports CPU-only inference, can run on most servers.
* Automatically utilizes multiple CPUs to accelerate inference.
* Simple classification with only two categories: nsfw and normal.
* Provides service via API, making it easier to integrate with other applications.
* Docker-based deployment, suitable for distributed deployment.
* Purely local, protecting your data security.

### Performance Requirements

Running this model requires up to 2GB of memory. No GPU support is needed.  
When handling a large number of requests simultaneously, more memory may be required.

### Supported File Types

This detector supports checking the following file types:

* ✅ Images (supported)
* ✅ PDF files (supported)
* ✅ Videos (supported)
* ✅ Files in compressed packages (supported)
* ✅ Doc,Docx (supported)

## Quick Start

### Start the API Server

```bash
docker run -d -p 3333:3333 --name nsfw-detector vxlink/nsfw_detector:latest
```

To check files in local paths on the server, mount the path to the container.
It is recommended to keep the mounted path consistent with the path inside the container to avoid confusion.

```bash
docker run -d -p 3333:3333 -v /path/to/files:/path/to/files --name nsfw-detector vxlink/nsfw_detector:latest
```

Supported architectures: `x86_64`, `ARM64`.

### Use the API for Content Checking

```bash
# Detection
curl -X POST -F "file=@/path/to/image.jpg" http://localhost:3333/check

# Check Local Files
curl -X POST -F "path=/path/to/image.jpg" http://localhost:3333/check
```

### Use the Built-in Web Interface for Detection

Visit: [http://localhost:3333](http://localhost:3333)

## Edit Configuration File

Now, you can configure the detector's behavior by mounting the /tmp directory and creating a file named config in that directory.
You can refer to the [config](config) file as a reference.

* `nsfw_threshold` Sets what NSFW value threshold must be exceeded for a target file to be considered a match and returned as a result.
* `ffmpeg_max_frames` Maximum number of frames to process when handling videos.
* `ffmpeg_max_timeout` Timeout limit when processing videos.

Additionally, since the /tmp directory serves as a temporary directory in the container, configuring it on a high-performance storage device will improve performance.

## Public API

You can use the public API service provided by vx.link.

```bash
# Detect files, automatically recognize file types
curl -X POST -F "file=@/path/to/image.jpg" https://vx.link/public/nsfw
```

* Your submitted images will not be saved.
* Please note that the API rate limit is 30 requests per minute.

## License

This project is open-source under the Apache 2.0 license.
