# Installing AURA on Windows

AURA is a Windows-first AI assistant. The repository is intended to become reproducible from a clean checkout without copying the developer's private runtime state.

> **Current repair status**
>
> The public repository is undergoing a dependency-closure repair. Until the repository-integrity and clean-install gates are green on `main`, this document describes the target supported installation model.

## 1. What is required?

| Component | Required? | Purpose |
|---|---:|---|
| Windows 10/11 x64 | Yes | Supported desktop platform |
| CPython 3.14.x | Yes | AURA runtime |
| Internet connection during setup | Usually | Python packages, optional models/providers |
| Git | No | Only needed when cloning/developing; ZIP download is fine |
| Ollama | No | Optional local LLM runtime |
| Cloud API key | No if using local AI | Optional OpenAI/Anthropic/Groq/Gemini/etc. |
| NVIDIA GPU / CUDA | No | Optional acceleration for local AI/voice |
| Faster-Whisper | Optional | Local speech-to-text |
| Piper / XTTS / Chatterbox | Optional | Local text-to-speech engines |
| FFmpeg | Optional | Only needed by features that require media/audio conversion |

AURA should remain usable without Ollama and without an NVIDIA GPU when a supported cloud provider is configured.

## 2. Choose an AI mode

### Cloud mode

Use one or more supported remote AI providers.

- Ollama is not required.
- Put your own API credentials in a local `.env` file.
- Never commit `.env` or credentials to GitHub.
- Start from `.env.example`.

### Local mode

Use Ollama for supported local LLM workloads.

- Install Ollama separately on Windows.
- Download at least one compatible local model.
- A cloud API key is not required for local-only AI routes.
- Some AURA integrations still require Internet access independently of the LLM.

### Hybrid mode

This is the preferred advanced configuration.

AURA can use local models when appropriate and fall back to configured cloud providers for capabilities that need them.

## 3. Python dependency profiles

AURA already contains reproducibility profiles under `requirements/`.

### Core

Direct reference dependencies:

```text
PySide6==6.11.1
python-dotenv==1.2.2
requests==2.34.2
psutil==7.2.2
```

The exact transitive Windows/Python 3.14 core lock is:

```text
requirements/locks/windows-py314-core-exact.lock.txt
```

### Voice

The certified reference profile includes:

```text
numpy==2.4.6
sounddevice==0.5.5
faster-whisper==1.2.1
piper-tts==1.6.0
coqui-tts==0.27.5
websockets==16.1.1
```

Voice requirements are defined in:

```text
requirements/voice.in
requirements-voice.txt
requirements-voice-pinned.txt
requirements-xtts.txt
```

### NVIDIA GPU acceleration

The certified reference GPU layer currently records:

```text
torch==2.13.0+cu130
torchaudio==2.11.0+cu130
```

The exact GPU lock is:

```text
requirements/locks/windows-py314-gpu-exact.lock.txt
```

PyTorch CUDA packages must use the official PyTorch CUDA index defined by the lock metadata.

GPU support is optional. AURA installation must not fail simply because CUDA is unavailable.

### Documents

Optional document packages are listed in:

```text
requirements/documents.optional.in
```

These include Word, PDF and spreadsheet readers used by optional document workflows.

## 4. Recommended clean setup

From a fresh checkout:

```bat
py -3.14 -m venv venv
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements\locks\windows-py314-core-exact.lock.txt
```

Then copy the public configuration template:

```bat
copy .env.example .env
```

Edit `.env` locally and configure either:

- at least one cloud provider, or
- Ollama/local provider settings.

Do not commit the resulting `.env`.

## 5. Optional voice setup

For the local voice stack, use the dedicated installer:

```bat
INSTALL_VOICE.bat
```

For XTTS:

```bat
INSTALL_XTTS.bat
```

Voice samples, speaker references and private voice profiles are deliberately excluded from the public repository.

## 6. Environment verification

AURA contains two complementary validators.

Validate the checked-in dependency/lock contract:

```bat
venv\Scripts\python.exe environment\verify_environment.py --portable
```

Validate internal source dependency closure:

```bat
venv\Scripts\python.exe ci\repository_integrity_gate.py
```

On the certified reference PC, a full environment validation can also be run:

```bat
venv\Scripts\python.exe environment\verify_environment.py
```

## 7. Clean-install verification

AURA includes a clean temporary-environment verifier.

Validate the core lock contract without installing packages:

```bat
venv\Scripts\python.exe environment\cold_install_verifier.py --profile core
```

Perform an actual clean network installation:

```bat
venv\Scripts\python.exe environment\cold_install_verifier.py --profile core --network --no-cache
```

Additional supported profiles include `voice`, `gpu` and `full`.

A public AURA release should not be considered reproducible until the appropriate clean-install profile succeeds from a clean checkout.

## 8. Launch

After the environment is prepared:

```bat
RUN_AURA.bat
```

The launcher expects the project-local virtual environment at:

```text
venv\Scripts\python.exe
```

## 9. Reference PC audit

The working AURA installation on the maintainer's reference Windows PC is the source of truth for the current runtime dependency set.

Run:

```bat
AUDIT_AURA_REFERENCE_PC.bat
```

It produces:

```text
ci/reports/reference_machine_audit.json
```

The audit intentionally excludes:

- API keys and environment-variable values
- OAuth/access/refresh tokens
- conversations and personal memories
- private voice samples
- user profile paths

The public dependency manifests and locks should be refreshed only from sanitized audit evidence and then validated through a clean install.

## 10. Release acceptance rule

A GitHub revision is considered installable only when all of the following are true:

```text
0 missing internal modules
0 broken internal imports
PASS public repository gate
PASS repository integrity gate
PASS dependency/lock validation
PASS clean core install
PASS required smoke tests
PASS secret/private-data scan
PASS GitHub Actions
```

Optional voice/GPU capabilities require their corresponding additional clean-install gates.
