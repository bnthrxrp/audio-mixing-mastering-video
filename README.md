# Audio Mixing & Mastering for Video

Skill de pós-produção audiovisual para agentes de IA, com ferramentas de diagnóstico, correção e QC executáveis em Linux/headless. O diretório completo é necessário: [SKILL.md](SKILL.md) encaminha para `references/`, `scripts/` e os contratos em `assets/`.

## Capacidades

- Medição de loudness e true peak, detecção de indicadores de clipping, silêncio, ruído, voz baixa e competição de música, com estados explícitos para incerteza.
- Normalização de duas passagens, redução conservadora de ruído e ducking em stems, ganho limitado de voz e verificação após render.
- QC em lote local com relatórios JSON, logs JSONL, cache por conteúdo, timeout e retry limitado.
- Regras para broadcast/streaming, ferramentas de IA, segurança, escala e hand-offs de agentes especializados.

As heurísticas não garantem inteligibilidade nem qualidade auditiva. O gate objetivo embutido cobre apenas loudness e true peak; outros requisitos precisam de verificações adicionais. A arquitetura de fila distribuída e multiagentes é um contrato de integração, não um serviço já implantado.

## Uso rápido

Requisitos: Python 3.10+, FFmpeg e FFprobe com filtros necessários. O núcleo usa a biblioteca padrão do Python; WebRTC VAD e ferramentas/modelos de IA são opcionais. Os alvos abaixo são exemplos, não requisitos universais.

```bash
python3 scripts/audio_qc.py entrada.wav --target-i -16 --target-tp -2 --strict --report qc.json
python3 scripts/normalize_loudness.py entrada.wav master.wav --target-i -16 --target-tp -2 --target-lra 11
python3 scripts/batch_qc.py input/ reports/ --jobs 2 --target-i -16 --target-tp -2 --strict
python3 -m unittest discover -s tests -v
```

`audio_qc.py --strict` retorna 0 apenas se os dois gates numéricos tiverem alvos e passarem; 2 indica gate falho ou indeterminado e 1, erro. Sem `--strict`, código 0 indica execução concluída, não aprovação. A normalização produz WAV float e rejeita fallback dinâmico por padrão; `--allow-dynamic` só é apropriado se a política permitir. Os scripts não sobrescrevem saídas e nunca modificam o original.

Consulte [automação headless](references/automacao-headless.md), [detecção e correção](references/deteccao-correcao.md), [ferramentas de IA](references/ferramentas-ai.md), [arquitetura enterprise](references/arquitetura-enterprise.md) e [loudness e entrega](references/loudness-entrega.md). Teste com mídia real e perfis de contrato antes de uso operacional.

## Licença

[MIT](LICENSE). Ferramentas, modelos e normas de terceiros têm licenças e condições próprias.
