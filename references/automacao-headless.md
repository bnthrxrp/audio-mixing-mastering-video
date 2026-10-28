# Automação headless executável

## Índice
Requisitos e comandos; stems e tratamento; WER; lote; Docker; vídeo; testes; limites.

## Requisitos e execução
Linux/POSIX, Python 3.10+, `ffmpeg` e `ffprobe` no PATH; ebur128 com medição de true peak e filtros `loudnorm`, `afftdn` e `sidechaincompress` no build. Confira `ffmpeg -filters` e `ffmpeg -version`. O núcleo não faz download de modelos e usa apenas biblioteca padrão Python. O VAD WebRTC é opcional e precisa de pacote compatível `webrtcvad`; teste seu binário e licença no ambiente. Execute a partir da raiz da Skill.

```bash
python3 scripts/audio_qc.py entrada.mp4 --stream 0 --target-i -16 --target-tp -2 --tolerance-lu 0.5 --strict --report entrada.qc.json
python3 scripts/normalize_loudness.py entrada.wav master.wav --target-i -16 --target-tp -2 --target-lra 11 --timeout 600
python3 scripts/audio_qc.py master.wav --target-i -16 --target-tp -2 --strict --report master.qc.json
```

`--stream` é índice entre streams de áudio; omita se existe exatamente uma. Saída JSON em stdout ou em `--report` novo. `--strict` retorna 2 se LUFS e TP não forem ambos `pass`; retorna 1 em erro, inclusive decodificação. Sem `--strict`, não confunda código 0 com QC aprovado. Para mono destinado à reprodução dual-mono use `--dual-mono` nos dois scripts. O medidor ebur128 dá resolução de saída de 0,1; ele não implementa âncora de diálogo ATSC ou necessariamente a edição mais nova de todos os perfis BS.1770. Verifique canais, matriz e medidor antes de qualquer alegação de conformidade.

A normalização rejeita automaticamente fallback dinâmico de `loudnorm`; `--allow-dynamic` é opt-in porque pode alterar dinâmica. `--target-lra` é parâmetro do filtro, não aprovação de LRA. O WAV float de 32 bits é escrito em diretório temporário no mesmo filesystem e promovido sem sobrescrita após teste independente de LUFS/TP, duração e canais; adicione outro gate se forem obrigatórios. Converta ao formato final somente depois de verificar headroom e meça novamente. A precisão de 0,1 no relatório não é garantia de medição metrológica. Ajuste taxa `--sample-rate`, tolerância, `--max-seconds` e `--timeout` conforme a política.

## Diagnóstico e tratamento de stems

```bash
python3 scripts/audio_qc.py mix.wav --voice-stem voz.wav --music-stem musica.wav --stems-synchronized --vad energy --report stems.json
# Opcional: --vad webrtc requer import webrtcvad instalado; não há fallback silencioso.
python3 scripts/correct_audio.py denoise voz.wav voz-limpa.wav --noise-confirmed --noise-floor-dbfs -40 --reduction-db 6
python3 scripts/gain_voice.py voz.wav voz-amplificada.wav --isolated-voice --gain-db 3 --target-tp -2
python3 scripts/correct_audio.py duck voz.wav musica.wav musica-abaixada.wav --stems-synchronized
```

`--stems-synchronized` atesta que conteúdo e ganhos se referem à mesma timeline; os scripts só verificam duração e timestamp, não podem confirmar alinhamento de conteúdo. `denoise` exige decisão externa de que ruído é indesejado. Ele só promove quando os mesmos quadros não vocais apresentam melhora mediana >=1 dB, voz candidata não perde mais de 1,5 dB na mediana, duração/canais/taxa são mantidos e pico não aumenta em excesso. `gain_voice.py` limita ganho a 6 dB e exige stem isolado e teto true peak; ganho também eleva ruído. `duck` cria **somente o stem de música processado**, não uma mix final. Requer sobreposição suficiente, redução mediana entre 0,5 e 10 dB durante voz e preservação aproximada das pausas. São gates energéticos, não teste de artefatos nem compreensão. Rejeição significa nenhum arquivo promovido. É possível que uma correção realmente útil não passe; não force thresholds para mascarar falhas.

Misture os stems com roteamento/pan/ganhos aprovados e duração validada. Com dois WAV já alinhados e mesmo layout, um exemplo que não normaliza ganhos e pode produzir pico excessivo é:

```bash
ffmpeg -nostdin -n -i 'voz.wav' -i 'musica-abaixada.wav' -filter_complex '[0:a:0][1:a:0]amix=inputs=2:duration=longest:normalize=0[a]' -map '[a]' -c:a pcm_f32le 'mix-candidata.wav'
python3 scripts/audio_qc.py mix-candidata.wav --target-i -16 --target-tp -2 --strict --report mix-qc.json
```

Não some áudio float acima de 0 dBFS e depois grave diretamente em PCM inteiro: pode clipar antes do QC. Garanta headroom **antes** da soma e/ou renderize intermediário float, valide e limite conforme especificação. O exemplo acima só serve se os níveis já têm headroom suficiente; prefira intermediário `pcm_f32le` e medir antes da conversão.

## Fala e WER

`python3 scripts/transcribe_local.py voz.wav transcricao.json --model /models/whisper-small-ct2 --language pt --device cpu --compute-type int8 --vad-filter` executa ASR opcional com `faster-whisper` instalado e modelo convertido **local**, incluindo tokenizer/configuração. Pré-verifique pesos/licença; isole a rede do contêiner. O script extrai a stream para mono 16 kHz, executa worker com timeout, registra hashes de entrada/modelo, evita download e promove JSON privado sem sobrescrever. Timestamps são relativos à stream extraída e não resolvem offsets de vídeo. O núcleo não instala nem distribui modelo ou dependência ASR.

Para obter texto do JSON com permissões restritas e comparar com uma referência:

```bash
umask 077
python3 -c 'import json; from pathlib import Path; d=json.loads(Path("transcricao.json").read_text(encoding="utf-8")); Path("transcricao.txt").write_text(" ".join(s["text"] for s in d["segments"]), encoding="utf-8")'
python3 scripts/speech_wer.py roteiro.txt transcricao.txt --warning-wer 0.2
```

WER usa distância de palavras com Unicode NFKC/casefold; limiar é exemplo, não norma. Referência vazia falha; menos de cinco palavras é indeterminado. ASR, diferenças de edição e normalização podem produzir falsos alertas; WER não é teste direto de inteligibilidade.

## Lote local e logs

```bash
python3 scripts/batch_qc.py input/ reports/ --jobs 2 --target-i -16 --target-tp -2 --strict --max-attempts 2
```

Somente diretório de primeiro nível, sem envio à rede. Cria JSON por SHA-256 de conteúdo + configuração + versões/scripts; log JSONL registra id, estado, tentativas, tempo e gate. Arquivos idênticos compartilham relatório, cujo caminho identifica a primeira fonte analisada; caminhos podem aparecer **dentro do relatório**, restrinja ACL/retenção. Repetições consultam cache; promoção sem sobrescrita evita conflito. Timeout encerra grupo de processos e faz até três tentativas com backoff; erro de conteúdo e gate falho não geram retry. Cache corrompido ou fonte modificada gera falha. 0 = todos concluídos (e, se `--strict`, todos aprovados); 1 = falha. Não implementa fila distribuída, persistência de estados transitórios, leases, métricas Prometheus nem garantias de exatamente uma execução; veja arquitetura enterprise.

## Docker e recursos

`docker build -f assets/Dockerfile -t audio-qc .` usa exemplo que ainda precisa de digest/base e snapshot de pacotes fixados para produção. Com diretórios com permissões para UID 10001:

```bash
docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=256m --cpus 2 --memory 1g \
  -v "$PWD/input:/data/in:ro" -v "$PWD/output:/data/out:rw" audio-qc \
  /data/in/entrada.wav --target-i -16 --target-tp -2 --strict --report /data/out/qc.json
```

Contêiner não testado se Docker não estiver disponível. Em produção aplique seccomp, filesystem e rede restritos, limite de arquivo/duração, quotas e não-root. FFmpeg/FFprobe abrem arquivos locais; isole entradas não confiáveis por mount, usuário e namespaces. Logs, hashes e transcrições podem ser dados sensíveis.

## Vídeo e sincronismo

Processar WAV não substitui áudio do vídeo. Com contrato conhecido, `ffmpeg -i video.mp4 -i master.wav -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 192k saida.mp4` é exemplo restrito a uma faixa; não preserva automaticamente outras faixas/legendas/chapters. Mapeie tudo necessário, preserve PTS/start/timecode, não use `-shortest` para esconder drift e compare `ffprobe` e duração. Meça **após codec** porque TP e loudness podem mudar. Streams adicionais, multicanal ou formatos imersivos exigem validação específica.

## Verificação

`python3 -m unittest discover -s tests -v` usa fixtures sintéticas e FFmpeg reais: clipping, silêncio, fallback dinâmico, normalização/QC, correções, WER, idempotência e falhas. Acrescente fixtures representativas reais e testes de tolerância de medidor, codecs, sync, políticas e escala antes de produção. Nenhum teste sintético certifica qualidade auditiva.
