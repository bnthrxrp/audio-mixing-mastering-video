# Fundamentos e diagnóstico

## Fundamentos
Edição: seleção, sincronização, montagem, fades, correção de ruídos e continuidade. Sound design: concepção e construção narrativa de sons, ambientes, Foley e efeitos. Mixagem: combina e automatiza elementos em perspectiva, espaço, dinâmica e tom. Masterização/conformação: valida e prepara a mix final para um destino, com ajustes globais mínimos e entregáveis; em cinema muitas vezes se fala em printmaster e entregas, não em uma masterização musical genérica. Acompanhe imagem, emoção, transições, silêncio intencional e acessibilidade.

Gain staging é controlar níveis em cada estágio, inclusive entradas e saídas dos plugins, sem saturação indesejada; headroom é margem até o limite relevante e não exige um valor mágico. Em ponto flutuante há margem interna, mas conversores, plugins e saída fixa podem clipar. Dynamic range é distância entre partes suaves e intensas; depende do método e não é sinônimo de LRA. RMS resume energia média de uma janela, não percepção padronizada. Sample peak em dBFS é maior amostra digital; true peak em dBTP estima pico reconstruído entre amostras. LUFS/LKFS representam loudness ponderado; LUFS-I mede programa completo com gating apropriado; momentary ~400 ms e short-term ~3 s descrevem variações. Normalização altera ganho conforme política; não garante inteligibilidade ou que cada plataforma aumente arquivos baixos. LRA descreve dispersão estatística, não um alvo universal e é pouco útil para peças muito curtas. Stereo field é posicionamento e largura entre canais; fase/polaridade e atrasos podem causar cancelamento na soma mono. Espectro é distribuição de energia por frequência; mascaramento entre fontes importa mais que um gráfico isolado.

## Matriz de diagnóstico
Para cada linha, compare bypass com volume igualado, considere ambiente e monitoração; números são zonas de investigação, não diagnósticos absolutos. Ferramentas podem ser nativas, com equivalentes como EQ paramétrico, analisador, editor espectral, medidor e automação.

| Problema | Possível causa e identificação | Impacto; correção; ferramentas |
|---|---|---|
| Voz baixa | Ganho inadequado, distância, dinâmica ou máscara; escute frases no contexto, compare trechos e medição short-term | Palavras perdidas; clip gain e automação, reduza competidores, compressão moderada; fader, compressor, loudness meter |
| Voz abafada | Microfone fora de eixo ou excesso de médios-graves; compare referência e varra 150–500 Hz | Menor clareza; corrija captação/posição, atenuação larga moderada, eventual presença; EQ paramétrico |
| Voz estridente | Ressonância, sala ou excesso de 2–5 kHz; identifique em escuta e varredura moderada | Fadiga; EQ dinâmico ou corte localizado, revise mic e comparação em volume igual; EQ, espectro |
| Sibilância | Mic, articulação ou processamento; escute S/CH em diferentes trechos, geralmente 4–10 kHz | Desconforto; de-esser seletivo, clip gain nas sílabas e ajuste de posição; de-esser, edição |
| Ruído de fundo | Ventilação, tráfego, pré, interferência; escute pausas e espectrograma, determine estacionário/variável | Distração; melhor fonte, redução espectral gradual, hum notch 50/60 Hz e harmônicos se apropriado, room tone; denoise/spectral editor |
| Clipping | Saturação no arquivo, gravador, plugin ou bus; forma achatada e audição, verifique estágios | Distorção; use tomada limpa/backup; declip pode melhorar mas não restaurar com garantia; medidor, declip |
| Distorção | Saturação, transdutor, codec, clipping ou processamento; teste bypass e origem | Fadiga e perda; reduza entrada, substitua arquivo, restaure quando possível; medidor, declip e monitoramento |
| Reverberação excessiva | Reflexões ou distância; escute cauda entre palavras e compare microfones | Voz distante; escolha mic mais próximo, edição/ADR, dereverb leve; dereverb e room tone |
| Fase | Múltiplos micros ou estéreo artificial; escute mono, compare canais, correlacionômetro e atrasos | Voz some ou timbre muda; escolha fonte, alinhe tempo conforme contexto, teste inversão de polaridade; delay, polarity, correlation |
| Falta de clareza | Mascaramento, ruído, sala ou excesso de dinâmica; escute em baixo volume e celular | Compreensão cai; automação, subtraia faixa concorrente, limpeza, EQ e dinâmica cuidadosos |
| Falta de presença | Distância, máscara ou timbre; comparação em loudness igual | Voz não se destaca; ajuste balanço antes de reforço sutil de médios/agudos; EQ e automação |
| Mix desbalanceada | Automação irregular ou monitor não confiável; revise cenas e aparelhos | Experiência inconsistente; faders, referência, VCA e automação; medidor e monitores/fones |
| Música compete | Frequências e nível da música coincidem com voz; mute/solo e audição no contexto | Perda de palavras; riding, ducking/sidechain, EQ dinâmico na música, ajuste de arranjo |
| Efeitos exagerados | Picos, densidade ou localização incoerentes; compare com diálogo e imagem | Sobressaltos ou fadiga; automação, equalização, transientes, espacialização e limitação individual quando justificada |

Gate duro pode cortar finais e elevar percepção do ruído ao abrir. Prefira expansão suave, edição manual e ambiência coerente. Regravar ou obter fonte melhor supera processamento extremo. Atenção a plosivas, cliques, hum, vento, dropouts, lipsync e ruído de roupa; diferentes fontes exigem respostas diferentes.
