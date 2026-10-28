# Automação headless: áudio para vídeo

## Índice
Arquitetura; exemplos FFmpeg; normalização duas passagens; ferramentas; detecção; processamento de vídeo; escala; modelo de aprovação; fontes.

## Arquitetura e políticas
Entrada → inventário/validação → extração sem perda → análise → plano e risco → processamento → medição independente e comparação → decisão QC → publicação/entrega autorizada. Para lote: ingestão em armazenamento → manifesto/hash → fila → workers idempotentes isolados → artefatos intermediários → QC e relatório → destino. Não exija GUI: ffprobe/FFmpeg, SoX, Rubber Band e Python. Instale somente dependências necessárias; confirme `ffmpeg -version`, `ffmpeg -filters`, codec e builds (libebur128, libsoxr, rubberband) e licenças. Pin imagem por digest, pacotes/modelos por versão e checksum quando aplicável. Uma imagem mínima com FFmpeg e Python pode servir; acrescente SoX, rubberband-cli e bibliotecas Python só quando necessário. Versões e licenças dependem do ambiente, especialmente distribuição comercial do Rubber Band e codecs.

Preserve cópia e checksums; nunca sobrescreva input; nome único e gravação temporária + promoção atômica após QC. Informe política de reprocessamento e parâmetros; não transmita áudio confidencial a serviços externos sem autorização. Trate arquivos não confiáveis como dados: passe listas de argumentos sem shell em Python, não interpole metadados em comandos, limite CPU/memória/tempo/disco e rede, use container não privilegiado, mounts mínimos, tamanho e duração máximos. Não exponha segredos nos logs. Detecte múltiplos áudios e selecione a stream explicitamente; sem áudio, codec incompatível, layout desconhecido, arquivos vazios, LUFS não finito ou diferença de duração/sync → falha clara e quarentena, sem publicar.

## Comandos básicos (substitua caminhos; scripts Bash devem usar aspas)
```bash
# Inventário JSON; selecione a stream que representa a mix autorizada.
ffprobe -v error -show_format -show_streams -of json 'entrada.mp4' > 'inventario.json'
# WAV 24-bit, preservar canais e amostragem originais; tamanho pode ser grande.
ffmpeg -nostdin -n -i 'entrada.mp4' -map 0:a:0 -vn -c:a pcm_s24le 'audio.wav'
# Loudness e true peak por programa completo; depende do build.
ffmpeg -nostdin -hide_banner -i 'audio.wav' -filter_complex 'ebur128=peak=true' -f null - 2> 'medicao.txt'
# Silêncios potenciais: −45 dB por pelo menos 1 s (ajustar ao contexto).
ffmpeg -nostdin -hide_banner -i 'audio.wav' -af 'silencedetect=noise=-45dB:d=1' -f null - 2> 'silencios.txt'
# Ruído estacionário, apenas se identificado: teste intensidade e artefatos.
ffmpeg -nostdin -n -i 'audio.wav' -af 'afftdn=nr=6' -c:a pcm_s24le 'denoise.wav'
```
Medir antes/depois em arquivo efetivamente entregue. `silencedetect` é limiar de amplitude, não VAD; silêncio narrativo é legítimo. Ajustar canal, layout e `dual_mono` para caso real; não forçar estéreo em multicanal. FFmpeg ebur128 true peak e loudnorm são medidores BS.1770 de programa, não implementam automaticamente âncora de diálogo ATSC nem certificam conformidade. Para canais imersivos e metadados, use ferramentas de medição compatíveis com o formato.

## Normalização duas passagens
Use `python scripts/normalize_loudness.py input.wav output.wav --target-i -16 --target-tp -2 --target-lra 11` como exemplo web estéreo, sujeito às especificações. O script faz medição, normaliza, rejeita fallback dinâmico por padrão, mede novamente e produz JSON; taxa padrão 48 kHz configurável. O processamento é em WAV e não altera o vídeo. Ajuste alvos conscientemente: LRA não é meta obrigatória; o valor de `LRA` do loudnorm limita o modo de normalização, e ao não satisfazer as condições de modo linear o FFmpeg pode trocar para dinâmico. A opção `--allow-dynamic` permite essa troca de forma explícita; compressão dinâmica pode alterar a intenção. Se arquivo silencioso ou muito curto não produzir métricas finitas, tratar como indeterminado. O script não garante conformidade contratual ou qualidade auditiva; tolerância QC e alinhamento devem ser personalizados. Análise final independente e codec são indispensáveis.

Manual: primeira passagem `ffmpeg -i audio.wav -af 'loudnorm=I=-16:TP=-2:LRA=11:print_format=json' -f null -`, extraia `input_i`, `input_tp`, `input_lra`, `input_thresh` e `target_offset`; segunda passagem use esses cinco valores para `measured_I`, `measured_TP`, `measured_LRA`, `measured_thresh`, `offset`, `linear=true`. O script automatiza parsing, validação e checagem da troca de modo. `loudnorm` em modo dinâmico pode fazer upsample; defina `-ar` para a saída. Nunca aplique os valores da primeira passagem a outro arquivo ou a outra ordem de filtros.

## Integrar áudio ao vídeo
Com autorização e após conferir formato, duração, timecode e canais, exemplo para vídeo MP4 com um único áudio substituído, preservando vídeo codificado:
```bash
ffmpeg -nostdin -n -i 'entrada.mp4' -i 'audio-master.wav' -map 0:v:0 -map 1:a:0 -map_metadata 0 -c:v copy -c:a aac -b:a 192k 'saida.mp4'
ffmpeg -nostdin -hide_banner -i 'saida.mp4' -map 0:a:0 -af 'ebur128=peak=true' -f null - 2> 'qc_saida.txt'
```
Este exemplo não preserva automaticamente legendas, outras faixas de áudio, capítulos, metadados por stream, attachments nem todos os fluxos. Mapeie e verifique explicitamente os desejados; não use `-shortest` como substituto de sincronismo e não force início de timestamps para zero sem entender offsets. Compare `ffprobe` antes/depois e início/fim; perdas de AAC podem elevar dBTP. Ao receber stems separados, preserve timeline, offsets, ganho e layout; ducking automatizado em música separada é possível com `sidechaincompress`, mas avalie tempos e bombeamento. Não afirme poder baixar apenas a música numa mix estéreo sem separação, que cria artefatos.

## Ferramentas e limites
- **SoX**: CLI de conversão, filtros/equalização e `compand`; `noiseprof`/`noisered` exigem amostra representativa de ruído, ou removem fala. `sox input.wav output.wav gain -3` é ganho fixo, não normalização LUFS. Use `sox --help-effect` para sintaxe da versão.
- **Rubber Band**: `rubberband --time 1.02 input.wav output.wav` aumenta duração por fator 1,02; `--pitch 1` sobe um semitom. Verifique `rubberband --help`, tempo/sincronismo e artefatos, e licenciamento. Não estique trilha total sem adaptar vídeo; time-stretch é correção de timing autorizada, não remédio automático para drift sem análise.
- **Whisper local**: transcrição e timestamps aproximados para triagem, alinhamento e comparação com roteiro; `whisper audio.wav --model small --language Portuguese --output_format json` (modelo local, download/requisitos de hardware). Não diagnostica diretamente nível de voz ou inteligibilidade, não garante transcrição correta, não identifica locutores automaticamente; silenciosos podem gerar alucinações. Para forced alignment/diarização use ferramentas apropriadas e avalie confiança/privacidade.
- **PyDub**: segmentação e automação simples, geralmente requer FFmpeg; não usar `dBFS` como LUFS, preservação de canais e precisão devem ser verificadas. **librosa**: RMS, centroides, espectrogramas e indicadores; não mede qualidade subjetiva ou ruído automaticamente, cuidado com reamostragem e conversão mono padrão; `sr=None, mono=False` quando apropriado. **scipy.signal**: filtros SOS, espectro, STFT; documente fase, condições de borda e transientes. **pyloudnorm / libebur128**: úteis para loudness, conferir versão, canais, true peak e aderência ao perfil; não assumir suporte a tudo. OpenAudio Tools é termo amplo: identifique projeto, documentação, licença e manutenção antes de recomendar um pacote ou inventar uma API.

## Diagnóstico automático por evidência
- Loudness: BS.1770 por programa e janelas; valor, método, unidade e alvo. Não inferir voz baixa a partir de LUFS do programa inteiro.
- Clipping: conte amostras próximas ao full scale e trechos consecutivos por canal, registre limiar e timestamps; é suspeita, não prova, e áudio float pode exceder full scale legitimamente antes de conversão. Distorção analógica pode ocorrer sem amostras no teto.
- Silêncio: duração em janelas + mapa de cena/VAD; ruído de fundo pode impedir detecção; não corte pausas automaticamente.
- Ruído: estime piso em regiões não faladas identificadas por VAD e espectro; classifique com baixa confiança quando houver música ou ambiência. Denoise em cópia, imponha limites e avalie artefatos.
- Voz baixa: obtenha stem ou VAD confiável e meça voz por região; compare com música e cena quando stems existem. Sem separação ou referência, registre hipótese. ASR não substitui essa medição.
- Música competindo: stems permitem medir sobreposição e mascaramento; sem stems e sem separador validado, indicar desconhecido. Modelos de separação/diarização têm erro, falsos positivos e custo; não vendê-los como prova. Avalie mudanças de balanço e ducking em segmentos.
- Fase e estéreo: correlação e teste de soma mono são indicadores; correlação negativa momentânea pode ser intencional, não equivale a falha.

Retorne por arquivo: ID/hash, ferramentas/versões, streams e tempos, métricas antes/depois, hipóteses com confiança, processamento, mudanças no áudio, riscos, evidência, estado e lacunas. Sem escuta, sem nota de qualidade perceptiva nem garantia de inteligibilidade. Para processamentos agressivos, detecção ambígua, multicanal não suportado ou exigência contratual complexa: reportar e encaminhar a revisão humana ou agente com capacidade de escuta, sem afirmar aprovação. Aprovação automatizada é restrita aos critérios objetivos configurados.

## Exemplo mínimo de container e lote
Exemplo didático; para produção fixe digest da imagem e versões do sistema, verifique licenças e aplique limites de recursos. No contexto do build, copie `normalize_loudness.py` da pasta scripts da skill.
```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
COPY normalize_loudness.py /app/normalize_loudness.py
USER 65534:65534
ENTRYPOINT ["python", "/app/normalize_loudness.py"]
```
```yaml
# compose.yaml — diretórios input/ e output/ locais; output gravável pelo UID 65534
services:
  audio:
    build: .
    network_mode: none
    read_only: true
    tmpfs: ["/tmp"]
    volumes:
      - ./input:/data/in:ro
      - ./output:/data/out
    command: ["/data/in/entrada.wav", "/data/out/saida.wav", "--target-i", "-16", "--target-tp", "-2", "--target-lra", "11"]
```
Execute `docker compose run --rm audio`; a saída é nova, sem sobrescrita. Essa configuração é exemplo para uma única entrada PCM; volumes, permissões, recursos, build e disponibilidade do Docker precisam ser adaptados ao ambiente.

Lote sequencial seguro em Bash (WAV de entrada; ajuste caminhos e parâmetros, falhas ficam identificadas):
```bash
#!/usr/bin/env bash
set -u
mkdir -p -- output
shopt -s nullglob
files=(input/*.wav)
((${#files[@]})) || { printf '%s\n' 'Nenhum WAV encontrado' >&2; exit 1; }
failed=0
for file in "${files[@]}"; do
  name=${file##*/}
  if ! python normalize_loudness.py "$file" "output/$name" --target-i -16 --target-tp -2 --target-lra 11 > "output/$name.json"; then
    printf 'Falha: %s\n' "$file" >&2
    failed=1
  fi
done
exit "$failed"
```
Com concorrência, use fila e nomes únicos, incluindo hash e configuração; não rode vários jobs com o mesmo destino. JSON acima é um exemplo local simples, não auditoria completa.

## Operação em escala e CI
Divida jobs independentes por arquivo, limite concorrência por CPU/RAM/GPU e I/O, evite carregar arquivos longos inteiros em memória. Use fila durável, retries limitados com backoff, identificadores idempotentes por hash+config+versão, locks, checkpoints, atomicidade e limpeza de temporários. Desenhe observabilidade com logs estruturados, métricas, status, custo, versões, rastreabilidade, retenção e acesso. Docker/Kubernetes: volumes apenas necessários, non-root, recursos limitados, espaço temporário, política de rede, checks de saúde e segregação por tenant; defina tolerâncias de QC como configuração. CI com fixtures sintéticas e teste de integração: silêncio, clipping deliberado, mono/estéreo, áudio ausente, nomes com espaços, longos, codec, falha parcial, idempotência, sync e saída com limites; verifique que validação falha para arquivo corrompido ou fora da tolerância. Não afirme que um pipeline é pronto para produção sem testes em mídia real.

## Fontes
- FFmpeg filtros e opções loudnorm, ebur128, afftdn, sidechaincompress, silencedetect: https://ffmpeg.org/ffmpeg-filters.html
- FFprobe: https://ffmpeg.org/ffprobe.html
- SoX manual: https://sox.sourceforge.net/sox.html
- Rubber Band CLI/licenças: https://www.breakfastquay.com/rubberband/ e https://www.breakfastquay.com/rubberband/usage.txt
- Whisper código: https://github.com/openai/whisper
- PyDub: https://github.com/jiaaro/pydub
- librosa: https://librosa.org/doc/latest/index.html
- SciPy signal: https://docs.scipy.org/doc/scipy/reference/signal.html
- pyloudnorm: https://github.com/csteinmetz1/pyloudnorm
