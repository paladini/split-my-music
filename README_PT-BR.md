<div align="center">

# Split My Music

**Separação de áudio com IA self-hosted — isole voz, acompanhamento musical, bateria, baixo, guitarra e piano de qualquer música em uma interface web simples e privada.**

[![CI](https://github.com/paladini/split-my-music/actions/workflows/ci.yml/badge.svg)](https://github.com/paladini/split-my-music/actions/workflows/ci.yml)
[![Release](https://github.com/paladini/split-my-music/actions/workflows/release.yml/badge.svg)](https://github.com/paladini/split-my-music/actions/workflows/release.yml)
[![Docker Hub](https://img.shields.io/docker/pulls/paladini/split-my-music?logo=docker&label=Docker%20Hub)](https://hub.docker.com/r/paladini/split-my-music)
[![GitHub Release](https://img.shields.io/github/v/release/paladini/split-my-music)](https://github.com/paladini/split-my-music/releases)
[![Python 3.12](https://img.shields.io/badge/python-3.12-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-10b981.svg)](LICENSE)

[English](README.md) · [Docker Hub](https://hub.docker.com/r/paladini/split-my-music) · [Changelog](CHANGELOG.md) · [Segurança](SECURITY.md)

</div>

---

![Interface principal do Split My Music](docs/screenshots/main-interface.png)

O **Split My Music** é uma aplicação web leve e self-hosted baseada na biblioteca open source [`python-audio-separator`](https://github.com/nomadkaraoke/python-audio-separator). Você escolhe ou arrasta uma música, seleciona o que deseja separar, escuta cada faixa na própria página e baixa os arquivos individualmente ou em um único `.zip`.

Tudo acontece localmente no seu servidor, computador pessoal, homelab ou NAS — **suas músicas nunca são enviadas para servidores externos.**

## Principais funcionalidades

- **Linguagem simples, sem jargões:** escolha entre **Vocals & Music**, **Vocals, Drums, Bass & Other** ou **Full Band (6 Tracks)**, com opções avançadas recolhidas para quem quiser escolher modelos específicos.
- **Opções fiéis ao modelo:** a interface mostra apenas as faixas que o modelo selecionado realmente produz.
- **Etapas reais de processamento:** acompanhamento transparente (`Upload` → `Prepare audio` → `Get the AI model` → `Separate` → `Save files`), sem porcentagens inventadas.
- **Player integrado e download em lote:** escute as faixas geradas na própria página e baixe individualmente ou em `.zip`.
- **Formatos sem perda e compactos:** exporte em **WAV**, **FLAC** (sem perda) ou **MP3** (320 kbps), preservando canais mono/estéreo e taxa de amostragem original (MP3 usa a taxa MPEG mais próxima).
- **Cache persistente de modelos:** cada modelo é baixado apenas na primeira utilização e mantido em volume persistente (`/data/models`).
- **Confiabilidade:** fila limitada (`1` trabalho por vez por padrão), checagem prévia de espaço em disco, recuperação automática após reinício do servidor, limpeza programada e mensagens de erro claras sem exposição de stack traces.

![Resultados com players de áudio](docs/screenshots/results-player.png)

---

## Início rápido (Docker — CPU)

### Opção A: Imagem pronta do Docker Hub

```bash
docker run -d \
  --name split-my-music \
  -p 7860:7860 \
  -v split-models:/data/models \
  -v split-jobs:/data/jobs \
  --restart unless-stopped \
  paladini/split-my-music:latest
```

### Opção B: Docker Compose (recomendado para homelab)

```bash
git clone https://github.com/paladini/split-my-music.git
cd split-my-music
docker compose up -d
```

Acesse <http://localhost:7860>. Na primeira execução de um modelo, ele é baixado uma única vez (~50–80 MB para os modelos padrão) para o volume `model-cache`. Os resultados ficam em `./data/jobs` e são removidos automaticamente após 24 horas.

---

## Início rápido (Docker — GPU NVIDIA)

### Pré-requisitos no host

- GPU NVIDIA com driver atualizado (`nvidia-smi` funcionando no host)
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) instalado e configurado para o Docker

### Usando o override do Docker Compose (evita conflito de porta)

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

O arquivo `docker-compose.gpu.yml` **substitui** o serviço CPU no mesmo nome e porta (`7860`), garantindo que CPU e GPU nunca sejam iniciados simultaneamente na mesma porta.

Ou execute diretamente a tag GPU:

```bash
docker run -d \
  --name split-my-music \
  --gpus all \
  -p 7860:7860 \
  -v split-models:/data/models \
  -v split-jobs:/data/jobs \
  --restart unless-stopped \
  paladini/split-my-music:gpu
```

Modelos prontos para **TrueNAS SCALE / NAS** estão em [`deploy/truenas/`](deploy/truenas/).

> [!NOTE]
> **Status honesto de validação:**
> - **CPU e contêiner Docker CPU:** construídos e validados ponta a ponta — a imagem CPU (`paladini/split-my-music:latest`) passou no `HEALTHCHECK`, `/health` e `/api/config`, e a separação real em CPU com `UVR-MDX-NET-Inst_HQ_3.onnx` mais o fluxo completo no navegador foram executados com sucesso.
> - **GPU NVIDIA:** `Dockerfile.gpu` e `docker-compose.gpu.yml` foram validados com `docker compose config` e integrados ao CI/CD, mas **ainda não foram executados em hardware NVIDIA físico** pelo autor.
> - **Apple Silicon / AMD / Intel dentro do Docker:** não possuem aceleração nestes contêineres Linux.

O selo no cabeçalho da interface mostra `CPU` ou `NVIDIA GPU (...)` apenas quando o PyTorch detecta CUDA ativo em tempo de execução.

### Atualização

```bash
docker compose pull && docker compose up -d
# Ou, a partir do código-fonte:
git pull
docker compose up -d --build        # adicione -f docker-compose.gpu.yml para GPU NVIDIA
```

---

## Modelos disponíveis

| Objetivo | Modelo (`python-audio-separator`) | Saídas | Primeiro download | Recomendação | Status de teste |
| --- | --- | --- | --- | --- | --- |
| **Vocals & Music** *(padrão)* | `UVR-MDX-NET-Inst_HQ_3.onnx` | Vocals, Music | ~64 MB | Rápido em CPU e GPU | **Executado ponta a ponta em CPU** |
| **Vocals & Music** *(clareza vocal)* | `Kim_Vocal_2.onnx` | Vocals, Music | ~64 MB | Rápido em CPU e GPU | Validado no catálogo; não executado no CI |
| **Vocals & Music** *(karaoke)* | `UVR_MDXNET_KARA_2.onnx` | Vocals, Music | ~50 MB | Rápido em CPU e GPU (mantém backing vocals em Music) | Validado no catálogo; não executado no CI |
| **4 faixas (Instrumentos)** | `htdemucs.yaml` | Vocals, Drums, Bass, Other | ~80 MB | Funciona em CPU e GPU | Validado no catálogo; não executado no CI |
| **6 faixas (Banda completa)** | `htdemucs_6s.yaml` | Vocals, Drums, Bass, Guitar, Piano, Other | ~53 MB | Funciona em CPU e GPU *(guitarra/piano podem vazar)* | Validado no catálogo; não executado no CI |
| **Vocals & Music** *(estúdio)* | `model_bs_roformer_ep_317_sdr_12.9755.ckpt` | Vocals, Music | ~610 MB | **GPU recomendada** *(muito lento em CPU)* | Validado no catálogo; não executado no CI |

Os tamanhos acima referem-se aos arquivos nos repositórios de origem na data de publicação. Velocidade e qualidade não foram comparadas por benchmark.

### Formatos suportados

- **Entrada:** `MP3`, `WAV`, `FLAC`, `M4A`, `AAC`, `OGG`, `OPUS` (áudio com mais de 2 canais é convertido para estéreo antes da separação).
- **Saída:** `WAV` (sem perda, `pcm_s16le`), `FLAC` (sem perda compactado) e `MP3` (320 kbps).

---

## Configuração (Variáveis de Ambiente)

| Variável | Padrão | Descrição |
| --- | --- | --- |
| `SPLIT_HOST` / `SPLIT_PORT` | `0.0.0.0` / `7860` | Endereço e porta do servidor |
| `SPLIT_MODEL_CACHE_DIR` | `./data/models` (`/data/models` no Docker) | Diretório persistente dos modelos |
| `SPLIT_JOBS_DIR` | `./data/jobs` (`/data/jobs` no Docker) | Diretório de trabalhos e resultados |
| `SPLIT_MAX_UPLOAD_MB` | `200` | Limite máximo de upload (MB) |
| `SPLIT_MAX_DURATION_MINUTES` | `20` | Duração máxima do áudio (minutos) |
| `SPLIT_MAX_CONCURRENT_JOBS` | `1` | Separações simultâneas (`1` evita esgotar RAM/VRAM) |
| `SPLIT_MAX_QUEUE_SIZE` | `5` | Tamanho máximo da fila antes de responder HTTP `429` |
| `SPLIT_MIN_FREE_DISK_MB` | `500` | Espaço mínimo livre em disco (+ tamanho do modelo se não baixado) |
| `SPLIT_RETENTION_HOURS` | `24` | Horas de retenção dos resultados concluídos |
| `SPLIT_MAX_STORED_JOBS` | `20` | Limite máximo de trabalhos finalizados mantidos em disco |
| `SPLIT_CHUNK_DURATION_SECONDS` | `300` | Janela de fatiamento para arquivos longos |
| `SPLIT_LOG_LEVEL` | `INFO` | Nível de logs (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

---

## Privacidade e Segurança

- **Processamento local:** todo o áudio é processado exclusivamente na máquina onde o Split My Music está rodando. Arquivos enviados são removidos ao final do trabalho.
- **Tráfego externo mínimo:** acesso à internet ocorre apenas para baixar um modelo na primeira vez em que ele é utilizado.
- **Proteções implementadas:** nomes de arquivos enviados são sanitizados e nunca viram caminhos no disco; nenhum comando de shell é montado com dados do usuário (`shell=False`); os downloads passam por validação de trabalho e caminho; stack traces ficam apenas nos logs do servidor.
- **Uso em rede local vs. exposição pública:** não há sistema de login. Use em localhost, rede doméstica ou homelab. **Não exponha diretamente na internet sem um proxy reverso com HTTPS, autenticação e revisão dos limites.**
- Processe apenas áudios sobre os quais você possui direito de uso.

---

## Solução de problemas

- **Falha ao baixar modelo:** verifique se o servidor tem acesso ao GitHub Releases e espaço livre suficiente em disco.
- **Falta de memória (OOM):** mantenha `SPLIT_MAX_CONCURRENT_JOBS=1`, use faixas menores ou utilize o modelo padrão `UVR-MDX-NET-Inst_HQ_3`.
- **Selo mostra CPU mesmo com GPU NVIDIA:** confira `nvidia-smi` no host, o NVIDIA Container Toolkit e se o compose override `docker-compose.gpu.yml` foi usado.
- **Servidor ocupado (`429`):** aguarde os trabalhos atuais terminarem ou aumente `SPLIT_MAX_QUEUE_SIZE`.
- **Contêiner unhealthy:** confira `docker compose logs split-my-music` e acesse `GET /health`.

---

## Desenvolvimento e Testes

Requer **Python 3.12** e **FFmpeg** (`ffmpeg` + `ffprobe` no `PATH`).

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt    # Windows: .venv\Scripts\pip install -r requirements.txt
.venv/bin/python main.py                     # Windows: .venv\Scripts\python main.py
```

Executar os testes:

```bash
pytest -m "not real_model"   # Testes rápidos (23 testes unitários e de integração)
pytest -m real_model         # Baixa ~64 MB na 1ª execução e roda separação real em CPU (2 testes)
pytest -v                    # Suíte completa (25 testes)
```

---

## Licença e Créditos

- **Código do Split My Music:** Licença [MIT](LICENSE).
- **Modelos e bibliotecas de terceiros:** baixados em tempo de execução e sujeitos às suas respectivas licenças — veja [THIRD_PARTY.md](THIRD_PARTY.md):
  - [`python-audio-separator`](https://github.com/nomadkaraoke/python-audio-separator) (MIT) — Andrew Beveridge / nomadkaraoke.
  - [Ultimate Vocal Remover](https://github.com/Anjok07/ultimatevocalremovergui) (Anjok07 & aufr33) e contribuidores dos modelos MDX-Net.
  - [Demucs](https://github.com/facebookresearch/demucs) — Meta AI Research (MIT).
  - BS-RoFormer (lucidrains & ViperX).
  - FFmpeg, PyTorch, ONNX Runtime, FastAPI e Uvicorn.
- Visual e fluxo inspirados no projeto [`voice-separator-demucs`](https://github.com/paladini/voice-separator-demucs).
