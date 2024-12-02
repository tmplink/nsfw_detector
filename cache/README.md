# cache

This folder is the cache directory for Hugging Face (HF).

When using online mode, downloaded models will be cached in this folder.

For [offline mode](https://huggingface.co/docs/transformers/main/installation#offline-mode) use, please download the models in advance and specify the model directory,
such as the `Falconsai/nsfw_image_detection` model below.

The folder structure for `./cache/huggingface/hub/models--Falconsai--nsfw_image_detection` is as follows.

```
.
├── blobs
├── refs
│   └── main
└── snapshots
    └── 63e0a066bb08d2ae47324b540fba3adfd4536569
        ├── config.json
        ├── model.safetensors
        └── preprocessor_config.json

5 directories, 4 files
```

For more details, refer to [up@cpu-offline/docker-compose.yml](./../docker/up@cpu-offline/docker-compose.yml).


## Pre-download for offline mode

Running in online mode will automatically download the model.

install cli

```bash
pip install -U "huggingface_hub[cli]"
```

download model

```bash
huggingface-cli download --revision main --cache-dir ./cache/huggingface/hub --include='*.json' Falconsai/nsfw_image_detection
huggingface-cli download --revision main --cache-dir ./cache/huggingface/hub --include='*.safetensors' Falconsai/nsfw_image_detection
```