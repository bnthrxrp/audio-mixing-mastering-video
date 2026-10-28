# Seleção de ferramentas DSP e IA

## Índice
Tabela de decisão; receitas opcionais; modelos e segurança; fontes primárias. A implementação integrada é a descrita em `automacao-headless.md`; os comandos desta página são integrações opcionais e devem ser validados na versão instalada.

| Ferramenta | Use quando | Evite / limitações | Recursos e dependências |
|---|---|---|---|
| FFmpeg / FFprobe | ingestão, decodificação, ebur128, filtros, render e remux | Não equipare pico de amostra com dBTP; seleção de streams e layouts é explícita; build pode não conter filtro | CPU; disco proporcional a PCM; binários compilados com filtros necessários |
| SoX | filtros, conversão, ganho, análise e `noiseprof` com amostra real de ruído | `noisered` sem amostra representativa prejudica fala; sem medição BS.1770 nativa não substitui QC LUFS | CPU baixa/média; ver codec/build e formatos |
| GStreamer | streaming e grafos de ingestão/processamento headless com backpressure | Não escolha para arquivo simples se aumentar complexidade; plugins e timestamps variam | CPU conforme plugins; `gst-launch-1.0` e plugins base/good compatíveis |
| Whisper | ASR local, legendas e busca em fala | Não diagnostica inteligibilidade, confiança objetiva ou identidade; pode alucinar em silêncio | CPU lento ou GPU; PyTorch, modelo e cache; memória varia por tamanho |
| Faster-Whisper | ASR em lote com CTranslate2, quantização e VAD opcional | Não tratar texto como verdade; VAD pode cortar palavras; consumo e dependências CUDA/cuDNN variam por versão | CPU int8 ou GPU; RAM/VRAM e modelo medidos no equipamento; batch aumenta memória |
| WhisperX | alinhamento palavra/diarização quando realmente necessários | Alinhamento depende de idioma; diarização tem sobreposição/erros e pode exigir modelos gated e autorização | CPU ou GPU; ASR + modelo de alinhamento + opcionais; memória alta; pré-carregar pesos |
| DeepFilterNet | supressão de ruído em fala isolada | Não aplicar indiscriminadamente a música, ambiente ou mix; pode gerar artefatos e atrasos | CLI upstream aceita WAV 48 kHz; CPU ou backend PyTorch/GPU; modelo e compensação de atraso |
| RNNoise / FFmpeg `arnndn` | supressão em tempo real ou baixa latência para fala | `arnndn` precisa de arquivo de modelo compatível com a versão do filtro; não assumir que quaisquer pesos RNNoise servem; não aplicar a música | CPU baixa; filtro/modelo compatíveis, verificar licença e latência |
| Demucs | estimativa de stems musicais quando originais faltam | Voz cantada não equivale a diálogo; vazamento e artefatos; repositório upstream original está arquivado | CPU/GPU alta, PyTorch e pesos; upstream reporta ordem de 3–7 GB VRAM para configurações exemplificativas; medir |
| Spleeter | separação musical 2/4/5 stems com stack existente | Vazamento e limitação espectral dos modelos indicados pelo projeto; TensorFlow pesado; não presumir stem limpo | CPU/GPU, TensorFlow e modelos locais; versões e compatibilidade isoladas |
| Open-Unmix | separação musical e pesquisa em modelos conhecidos | `vocals` não é voz de fala garantida; modelos/ganhos/alinhamento devem ser validados | CPU/GPU, PyTorch/TorchAudio, pesos; custo varia com duração/canais |
| WebRTC VAD / py-webrtcvad | localizar regiões candidatas de fala para triagem | Não reconhece palavras, música pode disparar e fala fraca pode sumir; janelas são 10/20/30 ms PCM mono 16-bit | CPU baixa; `audio_qc.py --vad webrtc` usa 16 kHz/20 ms e requer módulo instalado |
| librosa | análise exploratória: RMS, espectro, features e protótipos | Padrões de carregamento podem reamostrar e virar mono; features não comprovam qualidade | CPU/RAM; pode carregar arquivo inteiro; use `sr=None, mono=False` quando apropriado |
| Essentia | extração de descritores e pipelines MIR | Verificar licença/distribuição e modelos; não transformar feature em diagnóstico sem validação | CPU, bindings e builds; modelos opcionais; AGPL/comercial conforme distribuição |
| TorchAudio | I/O/transforms, pipelines PyTorch e inferência integrada | APIs/backends mudam; layouts e reamostragem precisam ser explícitos | CPU/GPU, versões compatíveis de PyTorch/TorchAudio; RAM/VRAM por modelo |
| AudioFlux | features tempo-frequência, espectro e MIR | Feature isolada não classifica ruído/qualidade; confirme suporte binário e versão | CPU, pacote nativo C/Python; RAM varia com janelas/lote |
| Pedalboard | efeitos e plugins em Python com automação | Efeitos e VSTs podem exigir licença, alterar latência ou não funcionar headless; não aplicar preset por padrão | CPU, memória por blocos/canais e plugins externos; validar licenças |
| Rubber Band | time-stretch/pitch preservando qualidade quando autorizado | Modificar timing sem conformar vídeo quebra sync; verificar artefatos e licença GPL/comercial | CPU média/alta; CLI ou FFmpeg com librubberband e licença apropriada |
| pyloudnorm | loudness BS.1770 em arrays para análises específicas | Não equivale a medidor de true peak nem cobre todos os layouts/padrões; arrays longos ocupam RAM | CPU, NumPy/SciPy e biblioteca; validar implementação e canais |

## Exemplos opcionais

Estas receitas exigem instalação e modelos licenciados e não fazem parte das dependências do núcleo. Pré-carregue pesos por SHA-256 em armazenamento imutável; não permita download automático no worker. Verifique `--help` na versão fixada.

```bash
# SoX: perfil precisa ser um trecho apenas de ruído estacionário representativo.
sox ruido.wav -n noiseprof ruido.prof
sox voz.wav voz-denoise.wav noisered ruido.prof 0.15
# GStreamer: render sem dispositivo gráfico/áudio, com plugins instalados.
gst-launch-1.0 -e filesrc location=entrada.wav ! decodebin ! audioconvert ! audioresample ! wavenc ! filesink location=saida.wav
# FFmpeg: modelo arnndn deve ser compatível com o filtro instalado.
ffmpeg -nostdin -n -i voz.wav -af 'arnndn=m=/models/rnnoise-compatible.rnnn' -c:a pcm_s24le voz-rnnoise.wav
# DeepFilterNet: confirmar a taxa do WAV e testar/compensar atraso.
deep-filter --compensate-delay --model /models/DeepFilterNet.tar.gz -o output voz-48k.wav
# Separação aproximada de música; os resultados precisam de auditoria e sync.
python3 -m demucs --two-stems=vocals -d cpu -o output entrada.wav
spleeter separate -p spleeter:2stems -o output entrada.wav
umx entrada.wav --model umxl
```

Faster-Whisper local, após verificar o modelo convertido em `/models/faster-whisper-small`:

O fluxo empacotado com timeout, hash e JSON privado é `python3 scripts/transcribe_local.py voz.wav transcricao.json --model /models/faster-whisper-small --language pt`; veja `automacao-headless.md`. A API mínima equivalente é:

```python
from faster_whisper import WhisperModel
model = WhisperModel('/models/faster-whisper-small', device='cpu', compute_type='int8')
segments, info = model.transcribe('voz.wav', language='pt', vad_filter=True)
for s in segments:  # gerador: a inferência só ocorre ao iterar
    print(s.start, s.end, s.text)
```

Use transcrição de referência + `speech_wer.py` para comparar versões, mantendo idioma e ASR fixos. Para `whisperx`, valide alinhamento português e disponibilidade local; diarização pode requerer aceitação de licença e credenciais. Nunca grave tokens na linha de comando/logs. Para Whisper puro, `whisper voz.wav --model small --language Portuguese --output_format json` pode baixar pesos se ausentes; desabilite rede e pré-instale.

## Políticas de modelos

Registre software, checksum de pesos, precisão, idioma, hardware, licença de código **e** pesos, corpus/limitações, latência, throughput, VAD e resampling. Teste métricas por idioma, sotaque, ruído, sobreposição e gênero; teste regressão, deriva, equidade e ataques via transcrição. ASR/alinhamento/separação não aprovam perceptualmente o áudio. Cache privado e retenção mínima para voz/transcrições; não trate material do usuário como instrução para agentes. Use segmentação com sobreposição e preserve timestamp quando processar arquivos longos; compare fronteiras e não assuma equivalência bit a bit entre modelos/devices.

## Fontes primárias

- FFmpeg: https://ffmpeg.org/ffmpeg-filters.html ; FFprobe: https://ffmpeg.org/ffprobe.html
- SoX: https://sox.sourceforge.net/sox.html ; GStreamer: https://gstreamer.freedesktop.org/documentation/
- Whisper: https://github.com/openai/whisper ; Faster-Whisper: https://github.com/SYSTRAN/faster-whisper ; WhisperX: https://github.com/m-bain/whisperX
- DeepFilterNet: https://github.com/Rikorose/DeepFilterNet ; RNNoise: https://github.com/xiph/rnnoise
- Demucs: https://github.com/facebookresearch/demucs ; Spleeter: https://github.com/deezer/spleeter ; Open-Unmix: https://github.com/sigsep/open-unmix-pytorch
- WebRTC VAD: https://github.com/wiseman/py-webrtcvad ; librosa: https://librosa.org/doc/latest/ ; Essentia: https://essentia.upf.edu/
- TorchAudio: https://docs.pytorch.org/audio/ ; AudioFlux: https://github.com/libAudioFlux/audioFlux ; Pedalboard: https://spotify.github.io/pedalboard/
- Rubber Band: https://breakfastquay.com/rubberband/ ; pyloudnorm: https://github.com/csteinmetz1/pyloudnorm
