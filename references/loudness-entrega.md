# Loudness e entregas — verificado em 28/10/2026

## Leitura da tabela
Contrato e especificação atual de distribuição sempre prevalecem. Os valores em “ponto de partida” são escolhas de engenharia para peças faladas, não normas oficiais de plataforma, nem garantia da normalização de reprodução. Para a tabela digital, teto de −1 dBTP é ponto inicial para master, −2 dBTP é margem conservadora para codec com perdas; medir também após codificação e reduzir mais se necessário. Não há um pico de amostra máximo universal adicional: respeite o teto de true peak da entrega, não exceda 0 dBFS nas amostras e informe dBFS e dBTP separadamente. Picos individuais de voz não são critério de conformidade.

| Destino | LUFS integrado: ponto inicial ou norma | True peak máximo | Pico de amostra / ressalva |
|---|---|---|---|
| YouTube | −16 a −14, sugestão para fala; −14 não é especificação universal confirmada | −1 dBTP; −2 para margem de codec | Abaixo de 0 dBFS; processamento e player variam; upload típico 48 kHz |
| Vimeo | −16 a −14, sugestão | −1 a −2 dBTP | Abaixo de 0 dBFS; confirme requisitos do produto |
| Instagram | −16 a −14, sugestão | −1 a −2 dBTP | Abaixo de 0 dBFS; confira mono/celular e publicação |
| TikTok | −16 a −14, sugestão | −1 a −2 dBTP | Abaixo de 0 dBFS; teste reprodução e evite presumir normalização |
| Facebook | −16 a −14, sugestão | −1 a −2 dBTP | Abaixo de 0 dBFS; a política pode variar por produto |
| LinkedIn | −16 a −14, sugestão | −1 a −2 dBTP | Abaixo de 0 dBFS; teste arquivo publicado |
| E-learning | −18 a −16, sugestão para fala | −1 a −2 dBTP | Abaixo de 0 dBFS; consistência entre aulas importa |
| Institucional/corporativo | −18 a −16, sugestão | −1 a −2 dBTP | Abaixo de 0 dBFS; adapte ao canal |
| Podcast em vídeo | −18 a −16, sugestão estéreo | −1 a −2 dBTP | Abaixo de 0 dBFS; valide distribuição específica |
| TV EBU | −23 LUFS programa; R128 v5, tolerância QC de medição ±0,2 LU; vivo ±1 LU quando aplicável | −1 dBTP produção PCM | Não confundir com limite para distribuição codificada; contrato manda |
| TV ATSC A/85:2026 | Sem metadados e sem acordo prévio: −24 LKFS; conteúdo longo medido por diálogo, curto por programa completo | −2 dBTP | Com metadados, dialnorm corresponde ao loudness; confirmar perfil e contrato |
| Cinema | Sem alvo universal em LUFS; mix conforme sala, formato, criativo e distribuidor | Especificação do distribuidor | Mix theatrical calibrada; DCP/canais/QC especializados; evitar impor perfil web |

As faixas acima são aproximações práticas não comprovadas como requisitos oficiais para cada serviço. Não se presume que a plataforma aumentará volume; normalização ou processamento dinâmico podem variar por player, dispositivo e conta. Um master de −16 LUFS não deve substituir um master de broadcast ou theatrical.

## Normas e medição
- ITU-R BS.1770-5 (2023): algoritmos de loudness e true peak, não define por si só um alvo para todas as plataformas. LUFS e LKFS são numericamente equivalentes quando o mesmo algoritmo/método é usado. Atenção a programa completo versus diálogo/âncora, gating, mapeamento de canais e metadados.
- EBU R128 v5 (2023): −23 LUFS de programa e true peak −1 dBTP para produção linear; o documento de referência e o contrato especificam tolerâncias e exceções. EBU R128 s1 (2020) short form: −23 LUFS integrado (tolerância QC ±0,2 LU), máximo short-term −18 LUFS (+0,2 LU de tolerância QC), −1 dBTP PCM (tolerância de medição ±0,3 dB nas condições especificadas); LRA não é critério útil para peças curtas. Não confunda −18 short-term máximo com alvo integrado.
- EBU R128 s2 (2023): para distribuição streaming, em circunstâncias e arquitetura descritas no suplemento, nível de distribuição provisório −20 a −16 LUFS; não é especificação de upload universal.
- ATSC A/85:2026-07, Anexo M: sem metadados e sem acordo anterior, alvo −24 LKFS e máximo −2 dBTP. Long-form: diálogo como âncora, medido na mix composta com BS.1770-1 sem gate relativo e algoritmo de diálogo ao longo do conteúdo; conteúdo curto usa programa completo BS.1770-3 ou posterior. Metadados devem indicar loudness. Variações de medição aproximadas até ±2 dB no loudness e ±0,5 dB no true peak não são alvos. Para streaming apenas, recomenda alvo único entre −23 e −27 LKFS salvo acordo diverso. Confirme o perfil e contrato; não atribua automaticamente efeito legal à edição.
- Exemplo de perfil específico: Netflix descreve −27 LKFS com diálogo como âncora para um tipo de entrega de dublagem; não extrapole para programa inteiro, outros ativos ou plataformas.

Meça o arquivo inteiro com medidor compatível BS.1770 e gatilho adequado: LUFS-I, máximo short-term/momentary conforme spec, LRA quando relevante, máximo dBTP e canal. Registre início/fim, padrão/versão, áudio medido (mix versus diálogo), amostragem, layout, ferramenta e tolerância. Para peça muito curta/silenciosa gating e LRA podem ser instáveis; indique limitações. Teste mídia entregue decodificada, compare com PCM e audite sincronismo. Não substitua escuta por conformidade numérica.

## Fontes primárias e contexto
- Lightworks, artigo-base (2024): https://lwks.com/blog/the-art-of-mixing-and-mastering-audio-for-video — equilíbrio, narrativa e fluxo, complementado/corrigido por referências abaixo.
- ITU BS.1770-5: https://www.itu.int/rec/R-REC-BS.1770
- EBU R128 v5: https://tech.ebu.ch/publications/r128 e texto https://tech.ebu.ch/docs/r/r128.pdf
- EBU R128 s1: https://tech.ebu.ch/docs/r/r128s1.pdf
- EBU R128 s2: https://tech.ebu.ch/docs/r/r128s2.pdf
- ATSC A/85 e revisão 2026: https://www.atsc.org/atsc-documents/a85-techniques-for-establishing-and-maintaining-audio-loudness-for-digital-television/ e Anexo M: https://www.atsc.org/wp-content/uploads/2026/07/A85-2026-07-Annex-M.pdf
- Dolby cinema e calibração: https://professional.dolby.com/en-gb/cinema/industry/dolby-content-services/
- YouTube encoding: https://support.google.com/youtube/answer/1722171 ; recursos de áudio: https://support.google.com/youtube/answer/16619284
- Netflix dublagem (escopo específico): https://partnerhelp.netflixstudios.com/hc/en-us/articles/38234663714835-BWAV-ADM-Creation-Guidelines-for-Dubbing
- Adobe loudness: https://helpx.adobe.com/br/audition/desktop/editing-audio-files/match-loudness.html
- AES41 metadados: https://tech.ebu.ch/news/aes-audio-metadata-standard-incorporates-24jul12

Atualize fontes oficiais ao entregar números atuais; ao não conseguir verificar, declare data e incerteza. Não use AES41 como norma geral de loudness.
