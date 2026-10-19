# Case II: Infraestrutura, Monitoramento, Disponibilidade e Governança de TI

As respostas a seguir consideram o motor de suitability do Case I em produção, validando as ordens de compra dos clientes antes da execução e, como proposto no relatório do Case I, acompanhando as carteiras no monitoramento do desenquadramento passivo.

Duas características do motor orientam todas as respostas. A primeira é que o cálculo em si é simples e rápido: uma média ponderada sobre os ativos de uma carteira. O trabalho mais pesado está ao redor dele, em buscar o perfil, a carteira e os preços, e em registrar cada decisão. A segunda é que o motor atua em um processo regulado. Se ele não puder validar uma ordem, a ordem não pode ser executada sem validação. Por isso, nas falhas, o sistema deve sempre escolher o caminho mais seguro para o cliente e para a Genial, mesmo que isso signifique recusar temporariamente uma operação.

---

## Cenário 1: Crescimento de demanda

> Imaginemos que o motor processa 10 mil carteiras por dia. A previsão é chegar a 100 mil. Quais pontos da infraestrutura você avaliaria para suportar esse crescimento?

Antes de decidir o que mudar, vale entender o tamanho real desse crescimento. Se as 100 mil validações acontecerem ao longo das 7 horas em que a bolsa fica aberta para negociação (das 10h às 17h, horário adotado pela B3 desde março de 2026), a média é de aproximadamente 4 validações por segundo. Esse volume médio não é alto, mas a demanda não se distribui de forma uniforme: a abertura do mercado e dias de grande oscilação de preços concentram muitas ordens em poucos minutos. Por isso, a infraestrutura precisa ser avaliada pelos picos, e não apenas pela média.

**1. Medir o sistema atual antes de investir**

O primeiro passo é medir como o sistema se comporta hoje com 10 mil carteiras: uso de processador e memória, tempo de resposta de cada etapa da validação e quantidade de conexões abertas com o banco de dados. Com esses números, é possível estimar qual componente vai chegar ao limite primeiro quando o volume for multiplicado por dez. Sem essa medição, o risco é investir em mais servidores quando o gargalo real está no banco de dados, por exemplo.

**2. Capacidade de processamento da aplicação**

O motor não guarda nenhuma informação entre uma validação e outra: cada chamada recebe os dados, calcula e responde. Isso permite rodar várias cópias da aplicação ao mesmo tempo, com um balanceador de carga distribuindo as requisições entre elas. Para crescer, basta adicionar cópias, o que é chamado de escala horizontal. Essa abordagem é preferível a substituir o servidor atual por um maior (escala vertical), porque um único servidor tem um limite físico de crescimento e, se ele parar, tudo para. Também é possível configurar o número de cópias para aumentar automaticamente nos horários de pico e diminuir quando a demanda cai.

**3. Banco de dados**

O banco de dados costuma ser o primeiro gargalo, porque é compartilhado por todas as cópias da aplicação e é mais difícil de escalar. Cada validação lê o perfil e a carteira do cliente e grava a decisão no histórico de auditoria, então o crescimento multiplica tanto as leituras quanto as escritas. Os pontos a avaliar são:

- **Índices nas consultas mais frequentes**, como a busca da carteira por cliente, para que a consulta continue rápida mesmo com mais dados.
- **Limite de conexões simultâneas.** Com mais cópias da aplicação, o número de conexões abertas com o banco cresce, e o banco tem um limite. É preciso dimensionar esse número para que as requisições não fiquem esperando uma conexão livre.
- **Réplicas de leitura**, que são cópias do banco usadas apenas para consultas. Elas tiram do banco principal o peso das leituras, deixando-o livre para as gravações.
- **Crescimento do histórico de auditoria.** Como os registros devem ser guardados por 5 anos (Resolução CVM 30, art. 14), 100 mil decisões por dia representam cerca de 25 milhões de registros por ano. É necessário planejar o armazenamento e a forma de consultar esse volume, por exemplo separando os registros por período.

**4. Serviços dos quais o motor depende**

O motor depende de outros sistemas para obter o perfil do cliente, a carteira e os preços dos ativos. Se esses sistemas não suportarem dez vezes mais consultas, o motor ficará lento mesmo com capacidade sobrando. É preciso confirmar a capacidade de cada um. Dados que mudam pouco, como o perfil do cliente e o score de risco dos ativos, podem ser mantidos em cache, ou seja, guardados temporariamente em memória para evitar consultas repetidas. O cuidado é atualizar o cache sempre que esses dados mudarem, para que o motor não decida com informação desatualizada.

**5. Separar a validação de compras do monitoramento diário das carteiras**

A validação de uma compra precisa responder na hora, porque o cliente está esperando. Já o monitoramento do desenquadramento passivo recalcula todas as carteiras de uma vez, uma vez por dia. Se as duas atividades disputarem os mesmos recursos, o recálculo de todas as carteiras pode deixar as compras lentas. Por isso, o monitoramento deve rodar separadamente, com as carteiras colocadas em uma fila (uma lista de tarefas processadas em ordem) e calculadas por servidores dedicados a essa atividade, sem interferir na validação das ordens.

**6. Testes de carga**

Por fim, antes de chegar a 100 mil, é importante simular esse volume, incluindo os picos, em um ambiente de testes. O teste confirma se as mudanças resolvem o problema e mostra o próximo limite do sistema antes que os clientes o encontrem.

---

## Cenário 2: Indisponibilidade do servidor

> O servidor responsável pelo processamento ficou indisponível. Como a infraestrutura poderia ser preparada para que as validações continuassem?

Se existe um único servidor processando as validações, qualquer falha nele interrompe todo o serviço. Esse componente é o que se chama de ponto único de falha. A preparação consiste em eliminar esses pontos e definir com antecedência como o sistema deve se comportar quando algo falhar.

**1. Mais de uma cópia da aplicação, em locais diferentes**

A aplicação deve rodar em pelo menos duas cópias, de preferência em locais físicos diferentes (por exemplo, em data centers diferentes). Assim, se um servidor ou até um local inteiro falhar, as outras cópias continuam atendendo. Como o motor não guarda informação entre validações, qualquer cópia pode atender qualquer requisição, o que torna essa redundância simples de implementar.

**2. Balanceador de carga com verificação de saúde**

O balanceador de carga distribui as requisições entre as cópias e verifica periodicamente se cada uma está respondendo. Quando uma cópia para de responder, ele deixa de enviar requisições para ela automaticamente. Para o cliente, a falha passa despercebida, porque as validações seguem sendo feitas pelas cópias restantes.

**3. Banco de dados também redundante**

Ter várias cópias da aplicação não adianta se todas dependerem de um único banco de dados. O banco precisa de uma réplica atualizada em tempo real, pronta para assumir automaticamente caso o principal falhe. Sem isso, o ponto único de falha apenas muda de lugar.

**4. Fila para o processamento que pode esperar**

O monitoramento passivo não precisa de resposta imediata. Se as carteiras a recalcular estiverem em uma fila, uma falha no processamento não faz nenhum trabalho se perder: as carteiras continuam na fila e são processadas assim que o serviço voltar.

**5. Comportamento seguro quando não houver como validar**

Mesmo com redundância, pode acontecer de nenhuma cópia conseguir validar uma ordem. Nesse caso, a ordem não deve ser executada sem validação. O cliente recebe uma mensagem informando que não foi possível concluir a validação naquele momento e que deve tentar novamente. Essa escolha tem um custo comercial, porque uma compra deixa de acontecer, mas executar uma operação sem a verificação de suitability descumpriria a obrigação regulatória da Genial. Entre perder uma venda e executar uma ordem possivelmente inadequada, a primeira opção é a correta.

**6. Recuperação e testes de falha**

As cópias que falharem devem ser reiniciadas ou substituídas automaticamente, e a equipe responsável deve ser alertada. Além disso, a troca para as cópias redundantes precisa ser testada periodicamente, simulando a queda de um servidor de forma controlada. Um mecanismo de contingência que nunca foi testado pode não funcionar justamente quando for necessário.

---

## Cenário 3: Lentidão

> O tempo de validação aumentou de 500 milissegundos para 8 segundos. Quais componentes de infraestrutura você verificaria primeiro?

O ponto de partida é entender onde esse tempo pode estar sendo gasto. O cálculo do motor é uma média ponderada sobre poucos ativos e leva uma fração de milissegundo. Um aumento de 16 vezes no tempo total, portanto, dificilmente vem do cálculo. É muito mais provável que a validação esteja esperando por algo: o banco de dados, um serviço externo ou um recurso do servidor. A ordem de verificação abaixo começa pelas causas mais comuns e mais rápidas de confirmar.

**1. Mudanças recentes**

A primeira pergunta é o que mudou: uma nova versão da aplicação, uma alteração de configuração ou uma mudança na infraestrutura. Boa parte dos problemas de desempenho aparece logo depois de uma mudança, e, se for o caso, desfazê-la é a forma mais rápida de normalizar o serviço enquanto a causa é investigada.

**2. Banco de dados**

O banco é o suspeito mais provável, por três motivos possíveis:

- **Consultas lentas.** Uma consulta que era rápida pode ficar lenta quando a tabela cresce, especialmente se não houver índice adequado. O histórico de auditoria, que só aumenta, é um candidato natural.
- **Bloqueios.** Gravações podem bloquear temporariamente leituras sobre os mesmos dados, fazendo as validações esperarem na fila.
- **Falta de conexões disponíveis.** Se todas as conexões com o banco estiverem ocupadas, cada nova validação espera uma conexão ser liberada. Isso produz exatamente o sintoma descrito: a aplicação continua funcionando, mas cada resposta demora muito mais.

**3. Serviços externos**

Se o serviço que fornece preços ou perfis estiver lento, o motor fica lento junto. É preciso verificar o tempo de resposta de cada um e se existe um tempo máximo de espera configurado. Sem esse limite, uma dependência lenta faz o motor esperar indefinidamente.

**4. Recursos do servidor**

Processador próximo de 100%, memória esgotada ou disco sobrecarregado também causam lentidão. Um caso comum é a falta de memória fazer o sistema usar o disco como memória temporária, o que é muitas vezes mais lento.

**5. Rede**

Por fim, problemas de rede entre a aplicação, o banco e os serviços externos, como demora na comunicação ou quedas de conexão, também acrescentam tempo a cada chamada.

Mais importante do que seguir uma lista é medir. Registrar quanto tempo cada etapa da validação leva (busca do perfil, busca da carteira, cálculo, gravação no histórico) mostra exatamente onde estão os 8 segundos. Com essa informação, a investigação vai direto ao componente responsável, em vez de depender de tentativa e erro.

---

## Cenário 4: Monitoramento

> A aplicação está respondendo, mas nenhuma carteira é validada há 30 minutos. Como o monitoramento poderia detectar essa situação?

Essa situação mostra a diferença entre uma aplicação estar no ar e estar funcionando. Uma verificação de saúde comum apenas pergunta se a aplicação responde, e nesse caso a resposta é sim. Mas o trabalho que importa, validar carteiras, parou. Isso pode acontecer, por exemplo, se o processo que consome a fila de validações travar, se o sistema que envia as ordens parar de enviá-las ou se a conexão com o banco ficar presa. Para detectar esse tipo de falha, o monitoramento precisa observar o resultado do trabalho, e não só se a aplicação está ligada.

**1. Acompanhar a quantidade de validações realizadas**

A métrica mais direta é contar quantas validações são concluídas por minuto e gerar um alerta quando esse número cair a zero, ou ficar muito abaixo do esperado, por alguns minutos seguidos. O cuidado é considerar o horário: à noite, zero validações é normal. Por isso, o alerta deve comparar o volume atual com o volume esperado para aquele horário, ou valer apenas no horário em que o mercado está aberto. Com essa métrica, a situação descrita seria detectada em poucos minutos, e não depois de 30.

**2. Validação de teste periódica**

A cada poucos minutos, o próprio monitoramento envia uma validação de teste, com um cliente fictício e dados conhecidos, e confere se a resposta chega no tempo esperado e com o resultado correto. Por exemplo, a carteira do enunciado deve sempre resultar em Aprovado com risco projetado de 1,81. Esse teste percorre o caminho completo da validação e detecta a falha mesmo em momentos em que não há ordens reais chegando. As validações de teste precisam ser identificadas como tal, para não se misturarem às decisões reais no histórico de auditoria.

**3. Acompanhar a fila de processamento**

Se as validações passam por uma fila, dois sinais indicam que o processamento travou: a fila crescendo sem parar e a mensagem mais antiga ficando cada vez mais velha. Os dois mostram que o trabalho está chegando, mas ninguém está processando.

**4. Verificação de saúde mais completa**

A verificação de saúde da aplicação pode ir além de "estou respondendo" e confirmar também se ela consegue acessar o banco de dados e os serviços dos quais depende. Isso não substitui as medidas anteriores, mas ajuda a identificar a causa mais rapidamente.

**5. Alertas que chegam a quem pode agir**

Por fim, cada alerta deve ser enviado para a equipe responsável e vir acompanhado de um procedimento com os primeiros passos de investigação. Um alerta que ninguém recebe, ou que ninguém sabe como tratar, não reduz o tempo de resposta.

---

## Cenário 5: Mudança em produção

> Como você planejaria uma mudança de infraestrutura em ambiente produtivo, considerando documentação da alteração, avaliação de riscos, testes prévios, aprovação da mudança, comunicação aos envolvidos e plano de contingência?

Para tornar o planejamento concreto, considere uma mudança relacionada ao Cenário 1: migrar o banco de dados do motor para um servidor com mais capacidade. Como o motor valida todas as compras dos clientes, uma falha nessa mudança pode impedir operações ou, no pior caso, deixar ordens sem validação. Por isso, a mudança segue etapas definidas antes de qualquer alteração ser feita. Essas etapas seguem as práticas de gestão de mudanças descritas no ITIL, um dos referenciais mais usados no mercado para a gestão de serviços de TI.

**1. Documentação da alteração**

A mudança é registrada em uma solicitação formal que descreve o que será alterado e por quê, quais sistemas serão afetados, o passo a passo da execução, quem é o responsável, em que horário será feita, como será validado que deu certo e como desfazer a alteração se algo der errado. Esse registro permite que outra pessoa entenda e execute a mudança, e serve como evidência de que as alterações em um sistema regulado são feitas de forma controlada.

**2. Avaliação de riscos**

Antes de executar, é preciso responder o que acontece se a mudança falhar, qual a chance de isso ocorrer e quais outros sistemas podem ser afetados. No exemplo, o impacto seria alto, porque sem banco de dados nenhuma ordem é validada. Essa avaliação define o nível de cuidado das etapas seguintes e o horário da execução. Uma mudança de alto impacto deve ser feita fora do horário em que o mercado está aberto, quando há poucas ou nenhuma ordem sendo enviada.

**3. Testes prévios**

A mudança é executada primeiro em um ambiente de testes, chamado de homologação, que deve ser o mais parecido possível com o ambiente real usado pelos clientes (produção). Nesse ambiente, são rodados os testes automatizados do motor, que conferem os cálculos e os limites de cada status, e um teste de carga, para confirmar que o novo servidor suporta o volume esperado. O procedimento de reversão também é testado, porque um plano de volta que nunca foi executado pode falhar justamente quando for preciso.

**4. Aprovação da mudança**

A mudança é aprovada por pessoas além de quem a propôs, normalmente em um comitê de mudanças que reúne os responsáveis técnicos pelos sistemas afetados. Para mudanças de alto risco, áreas de negócio e de compliance também participam. A aprovação por mais de uma pessoa reduz a chance de um risco passar despercebido e deixa registrado quem autorizou a alteração.

**5. Comunicação aos envolvidos**

Antes da mudança, todos os afetados são avisados sobre o horário, a duração prevista e o possível impacto: outras equipes técnicas, o atendimento ao cliente, os assessores e o compliance. Durante a execução, a equipe informa o andamento, e, ao final, comunica a conclusão ou qualquer problema encontrado. Assim, se algum cliente for afetado, o atendimento já sabe o que está acontecendo e como orientar.

**6. Plano de contingência**

O plano de contingência define, com antecedência, como desfazer a mudança e quando isso deve ser feito. Antes de começar, é feita uma cópia de segurança completa do banco. O plano também estabelece critérios objetivos para a reversão, por exemplo: se, depois da migração, a taxa de erros nas validações ou o tempo de resposta ultrapassar um limite definido durante um certo período, a mudança é revertida. Definir esses critérios antes evita que a decisão seja tomada sob pressão, no meio de um incidente.

**7. Execução e validação final**

Durante a execução, a equipe acompanha as métricas descritas no Cenário 4. Ao final, a validação de teste periódica confirma que o motor voltou a responder corretamente com o novo banco. O resultado da mudança, e qualquer aprendizado obtido, é registrado na solicitação original, fechando o histórico da alteração.

Seguindo essas etapas, a mudança deixa de depender da sorte ou da experiência de uma única pessoa. Cada risco é avaliado antes, cada decisão fica registrada e, se algo der errado, a equipe já sabe exatamente o que fazer.

---

## Referências

- COMISSÃO DE VALORES MOBILIÁRIOS. **Resolução CVM nº 30, de 11 de maio de 2021**. Texto consolidado, art. 14. Disponível em: https://conteudo.cvm.gov.br/export/sites/cvm/legislacao/resolucoes/anexos/001/resol030consolid.pdf
- ECONOMIC NEWS BRASIL. **Horário da B3 muda e redefine funcionamento do pregão no Brasil**. 7 mar. 2026. Disponível em: https://economicnewsbrasil.com.br/2026/03/07/horario-da-b3-muda-e-redefine-funcionamento-do-pregao-no-brasil/
- AXELOS. **ITIL Foundation: ITIL 4 Edition**. Londres: TSO, 2019.
