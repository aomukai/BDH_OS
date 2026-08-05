# Deploy Qwen3.6 TurboQuant Executor

The configured immediate local fallback is
`qwen3.6-35b-a3b-q4-k-m-turboquant`; direct DeepSeek V4 Flash is primary when
`DEEPSEEK_API_KEY` is available from the repository `.env`. Qwen uses a revision-pinned Q4_K_M GGUF,
the TurboQuant llama.cpp fork, GPU 0, CPU-resident MoE experts, and a preferred
256,000-token context with a 128,000-token startup fallback.

The executor harness starts and stops the Docker container for each bounded
job. Do not run a separate persistent server on port 8080 for pipeline work.

## Prerequisites

Install and configure NVIDIA Container Toolkit:

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor \
    -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -sL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

Then verify that this succeeds:

```bash
docker run --rm --gpus all \
  nvidia/cuda:12.4.1-base-ubuntu22.04 \
  nvidia-smi
```

Ensure `/home/aomukai/executor` is on storage with at least 45 GiB free before
downloading the model and CUDA build image.

## Download and verify the model

```bash
install -d /home/aomukai/executor/models/qwen3.6-35b-a3b

curl --fail --location --continue-at - --retry 5 \
  'https://huggingface.co/bartowski/Qwen_Qwen3.6-35B-A3B-GGUF/resolve/5c2410d71524f4f72b023ce8daf7a80528226d5f/Qwen_Qwen3.6-35B-A3B-Q4_K_M.gguf' \
  --output /home/aomukai/executor/models/qwen3.6-35b-a3b/Qwen_Qwen3.6-35B-A3B-Q4_K_M.gguf

echo 'b46fedd33e0bfb0cae308aa3c158d0a4b2c4a1d2185a1ed6f093cdaf39064772  /home/aomukai/executor/models/qwen3.6-35b-a3b/Qwen_Qwen3.6-35B-A3B-Q4_K_M.gguf' | \
  sha256sum --check
```

## Build the pinned TurboQuant runtime

```bash
install -d /home/aomukai/executor/runtimes

git clone --branch feature/turboquant-kv-cache \
  https://github.com/TheTom/llama-cpp-turboquant.git \
  /home/aomukai/executor/runtimes/llama-cpp-turboquant-8a891f4b

git -C /home/aomukai/executor/runtimes/llama-cpp-turboquant-8a891f4b \
  checkout 8a891f4b566efdbd3cea92fafee3227a0a267683

docker run --rm \
  --gpus '"device=0"' \
  -v /home/aomukai/executor/runtimes/llama-cpp-turboquant-8a891f4b:/src \
  -w /src \
  nvidia/cuda:12.4.1-devel-ubuntu22.04 \
  bash -lc '
    apt-get update &&
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
      build-essential cmake ninja-build &&
    cmake -S . -B build -G Ninja \
      -DCMAKE_BUILD_TYPE=Release \
      -DGGML_CUDA=ON \
      -DCMAKE_CUDA_ARCHITECTURES=86 &&
    cmake --build build --target llama-server -j
  '
```

## Validate

Static configuration validation does not require the model installation:

```bash
python3 training/executor/run_bakeoff.py verify
```

Once the runtime and model are installed, run one bounded representative job:

```bash
python3 training/executor/run_bakeoff.py run \
  --model qwen3.6-35b-a3b-q4-k-m-turboquant \
  --task msm-script-authoring
```

Inspect the server log to confirm the selected context, `turbo4` K cache,
`turbo3` V cache, 36 CPU MoE layers, locked memory, and GPU 0. Then run the
complete bake-off before unattended operation:

```bash
python3 training/executor/run_bakeoff.py run \
  --model qwen3.6-35b-a3b-q4-k-m-turboquant
```

Only treat the model as operationally commissioned after the complete bake-off
and a long-context retrieval probe pass. Until then, the checked-in routing is
configured but the external runtime remains unverified.
