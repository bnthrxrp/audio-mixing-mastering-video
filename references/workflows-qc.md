# Workflows, análise e checklists

## Recepção e diagnóstico técnico
Confirme material, autorização para editar, formato e destino. Receba picture lock, referência, timecode e frame rate (incluindo drop-frame), handles, AAF/OMF e mídia embutida/links, áudio original, stems DX/MX/FX, efeitos e versões separadas quando houver. Cheque duração, amostragem, canais, sincronismo, links, fontes e limitações; peça exportações WAV sincronizadas quando não abrir uma sessão. Para apenas mix estéreo, observe que ajustes individuais são limitados e separação por IA pode criar artefatos.

Se ferramentas locais existem, use ffprobe para codec, canais, duração e taxa; use ffmpeg ebur128=peak=true para LUFS-I, short-term e true peak, anotando versão, janela e layout. Exemplo local (caminhos fornecidos, sem shell inseguro): `ffmpeg -hide_banner -nostats -i INPUT -filter_complex ebur128=peak=true -f null -` — leia resumo final; suporte de true peak depende da compilação. Inspecione por segmentos com timestamps usando busca/extração e escuta real se disponível. `volumedetect` dá média e pico de amostra, não LUFS nem true peak; `loudnorm` pode fornecer estatísticas mas seu resultado não prova conformidade de todos os perfis. Detecção de clipping digital só sugere ocorrência, não prova ausência de distorção analógica; mono/correlação, espectro e análise automática não identificam por si inteligibilidade ou qualidade. Em material longo examine início, meio, fim, máximos, transições e trechos reportados; relate cobertura e lacunas.

## Fluxos por projeto
1. **Institucional:** briefing e canais → picture lock → voz/entrevistas e ruídos → música de apoio e marca → automação → master de destino → teste celular e aprovação; preserve naturalidade e versão sem música quando solicitada.
2. **Redes sociais:** formato, duração e público → voz compreensível nos primeiros segundos → música/FX sem mascaramento → controle de picos e mono → export → teste no dispositivo/publicação e legendas revisadas. Atenção a recortes e mudanças após upload.
3. **Comercial:** receba duração, frames e specs da emissora → sincronize locução, trilha, marca e impactos → garanta inteligibilidade e identificação sonora → meça integrado, short-term e TP conforme perfil → export e QC do arquivo exato; se EBU short-form verificar s1. Entregue versões e direitos acordados.
4. **Curso online:** normalize consistência de captação entre aulas → edite pausas/respirações com naturalidade → alinhe vozes → música discreta → defina alvo consistente por série → valide fone/celular e acessibilidade → export por aula e cheque início/fim.
5. **Documentário:** organize cenas, micros e ambientes → escolha tomadas por inteligibilidade e autenticidade → room tone, montagem de diálogo e possível ADR → ambientes e efeitos discretos → música narrativa → controle de dinâmica por meio e destino → continuidade e QC completo.
6. **Entrevista:** sincronize câmeras/gravadores → priorize melhor fonte por pessoa → controle vazamento/fase sem duplicar micros → limpe e nivele frases → música somente onde útil → escuta contínua e revisão de cortes, ruídos e nomes.
7. **Podcast em vídeo:** sincronize gravações, vídeo e convidados remotos → limpe canais e vazamento → nivele individualmente, automatize e comprima de forma leve → mix de vozes/intros → loudness consistente → checar mono, longas pausas e drift de sincronismo.
8. **Corporativo:** identifique sala, equipamento, restrições e distribuição → restaure fala sem apagar natureza → nivele apresentadores e chamadas remotas → reduza música durante conteúdo → ajuste para telas de notebook/salas → confira nomes, versões, confidencialidade e QC.

## Checklists
### Antes da mixagem
- [ ] Briefing, uso, criativo, prazo, destino e versão atual das especificações aprovados.
- [ ] Picture lock, FPS/timecode, sync, duração, canais, sample rate, arquivos e links conferidos; originais preservados.
- [ ] Monitoração funcional, referências apropriadas, sessão roteada, buses nomeados, backups e stems previstos.
- [ ] Inventário de problemas, prioridades e necessidade de regravação; direitos de música/efeitos e recursos de acessibilidade encaminhados.

### Durante a mixagem
- [ ] Escuta no contexto da imagem; diálogo, música, FX e ambientes com função narrativa.
- [ ] Ruídos, edições, fades, continuidade, ambiência e sincronia revisados; sem corte de finais de palavras.
- [ ] Gain staging, EQ e dinâmica em bypass igualado; automação de frases, música e transientes.
- [ ] Mono, fase, canais, aparelhos comuns e volume baixo conferidos; pausas auditivas.

### Antes da masterização
- [ ] Mix aprovada e problemas locais resolvidos na origem; stems e versão salvos.
- [ ] Sem clipping nos estágios relevantes; headroom suficiente, roteamento e render corretos.
- [ ] Destino, loudness, método de medição, TP, layout, codec e tolerâncias confirmados.

### Antes da exportação
- [ ] Alvo e true peak medidos no programa completo conforme contrato; dinâmica e naturalidade preservadas.
- [ ] Canais, ordem, downmix, sample rate, bit depth, codec, duração, timecode, nomes e versões conferidos.
- [ ] Renders adicionais, stems, M&E, arquivos de projeto e metadados só conforme pedido; dither apropriado.

### QC final
- [ ] Reabra e escute o arquivo entregue integralmente quando viável, com início/fim, transições, silêncio, lipsync e integridade.
- [ ] Meça LUFS-I, TP e demais parâmetros exigidos no arquivo final e após codec; registre método, tolerância e resultado.
- [ ] Verifique mapeamento de canais, estéreo/mono/downmix, metadados, formato e ausência de artefatos de compressão.
- [ ] Teste celular, fones e dispositivo representativo; compare referência em volume igual. Marque limitações de escuta/cobertura e pendências; confirme aprovação e guarda de versões.
