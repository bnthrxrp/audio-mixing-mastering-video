# Audio Mixing & Mastering for Video

Skill para agentes de IA especializados em pós-produção de áudio para vídeo, com foco em execução autônoma em Linux e ambientes headless.

## O que faz

- Orienta diagnóstico, edição, sound design, mixagem, loudness, masterização e controle de qualidade para vídeo.
- Propõe fluxos para redes sociais, cursos, documentários, podcasts, publicidade, streaming, cinema e broadcast.
- Prioriza FFmpeg, SoX, Rubber Band, Whisper, Python, containers e ferramentas abertas. DAWs gráficas são referências opcionais.
- Distingue resultados medidos de hipóteses e testes perceptivos. Valores para plataformas são pontos de partida, salvo especificação documentada.

## Uso da skill

Em um ambiente compatível com skills no formato `SKILL.md`, instale o diretório completo conforme as instruções do seu ambiente e invoque `audio-mixing-mastering-video`. A skill consulta os arquivos em `references/` e, quando aplicável, o script em `scripts/`.

Exemplo de solicitação:

> Use a skill audio-mixing-mastering-video para analisar meu vídeo, melhorar a inteligibilidade do diálogo e preparar uma entrega para YouTube usando ferramentas Linux headless.

## Normalização em duas passagens

Requer Python 3 e FFmpeg com o filtro `loudnorm`. O comando abaixo cria um novo WAV 24-bit e imprime um relatório JSON. O alvo é apenas um exemplo para fala na web, sujeito à especificação do projeto.

```bash
python3 scripts/normalize_loudness.py entrada.wav saida.wav \
  --target-i -16 --target-tp -2 --target-lra 11
```

O script rejeita entrada silenciosa sem medições válidas, não sobrescreve a saída e bloqueia a troca para normalização dinâmica por padrão. Use `--allow-dynamic` somente se essa alteração for aceitável. Meça o arquivo final codificado também: codec, canais e destino podem mudar o resultado. A análise numérica não substitui a escuta nem certifica conformidade com uma especificação.

A documentação operacional, os critérios e exemplos de Docker, FFmpeg e lotes estão em `references/automacao-headless.md`. Padrões e referências estão em `references/loudness-entrega.md`; confirme sempre a edição mais recente e a especificação do destinatário.

## Licença

[MIT](LICENSE). Ferramentas, modelos, artigos e normas de terceiros citados ou utilizados são independentes e mantêm suas próprias licenças e condições.
