# Exemplo Netsquid - Simples camada de enlace

Neste exemplo iremos alcançar uma geração de emaranhamento robusto definindo um protocolo quântico simples de camada de enlace. Este exemplo é inspirado pela camada de enlace proposta por Dahlberg et al. Ver figura: 

![](C:\Users\Junior\AppData\Local\Packages\CanonicalGroupLimited.Ubuntu_79rhkp1fndgsc\LocalState\rootfs\home\junior\netsquid-pt-br\layers_LL1.png)

A camada física é responsável por executar as tentativas de geração de emaranhamento quando requisitadas. Essas tentativas podem ser bem sucedidas ou falhar, e esta informação é propagada à camada de enlace, responsável por gerar este emaranhamento de forma robusta. A camada de enlace (link) recebe requisições da camada de rede para a criação de emaranhamento e irá responder com sucesso assim que for alcançado.

Neste exemplo, iremos explorar implementações simplificadas para os protocolos das camadas física e de enlace. Antes de mergulharmos nos protocolos, vamos descrever um exemplo de rede física no NetSquid, o qual terá o seguinte layout:

![](C:\Users\Junior\AppData\Local\Packages\CanonicalGroupLimited.Ubuntu_79rhkp1fndgsc\LocalState\rootfs\home\junior\netsquid-pt-br\aafig-e136a9d79a1b68165fcb04c47d8657cb7d2036ca.svg)

```python
import abc
from collections import namedtuple, deque
import numpy as np

import netsquid as ns
from netsquid.nodes import Connection, Network
from netsquid.protocols.protocol import Protocol
from netsquid.protocols.serviceprotocol import ServiceProtocol
from netsquid.qubits import QFormalism
from netsquid.qubits.operators import Operator
from netsquid.components import QuantumProcessor, QuantumChannel, ClassicalChannel, Message, QuantumProgram, \
    QuantumDetector
from netsquid.components.instructions import INSTR_INIT, INSTR_EMIT
from netsquid.protocols import NodeProtocol
```

Alice e Bob usarão um esquema de clique único para gerar emaranhamento anunciado (heralded será traduzido como anunciado). Os canais quântico e clássico e o detector necessários para a geração de emaranhamento estão contidos na conexão anunciada. Iremos requisitar o gerador de emaranhamento em Alice, que irá usar a conexão clássica para sincronizar as requisições com Bob. Um nó contém um processador quântico que está conectado a uma conexão anunciada, como mostra o esquema abaixo.


![](C:\Users\Junior\AppData\Local\Packages\CanonicalGroupLimited.Ubuntu_79rhkp1fndgsc\LocalState\rootfs\home\junior\netsquid-pt-br\aafig-89271adffc8daabf412851542a5f2a6eab0899c3.svg)

A rede é configurada como segue:

```python
def cria_rede_exemplo(num_qubits=3):
    rede = Network('RedeEnlaceSimples')
    nos = rede.add_nodes(['Alice', 'Bob'])
    distancia = 2  # em km
    for no in nos:
        no.add_subcomponent(QuantumProcessor(f'memq_{no.name}',
                                             num_positions=num_qubits + 1,
                                             fallback_to_nonphysical=True))
    conexao = ConexaoAnunciada("ConexaoAnunciada",
                               distancia_para_a=distancia / 2,
                               distancia_para_b=distancia / 2,
                               janela_tempo=20)
    rede.add_connection(nos[0], nos[1], connection=conexao, label='quantica')
    rede.add_connection(nos[0], nos[1], delay=distancia / 200000 * 1e9, label='classica')
    return rede
```

Agora, definimos os protocolos necessários. A camada física e de link trabalham juntas, assim, vamos ter uma visão geral completa dos protocolos antes de pensar na implementação.

A camada de link deve responder a requisições CRIAR, emitidas pela camada de rede. Uma requisição CRIAR especifica em nosso caso o número de pares de qubits que queremos gerar. Para este exemplo, assumiremos que a requisição de gerar três qubits acabou de chegar à Alice. O protoloco trabalha da seguinte maneira:

1. A camada de enlace recebe a requisição da camada de rede;
2. A requisição é sincronizada com o outro nó;
3. A cada 100ns, a camada física envia um 'gatilho' (trigger) para a camada de enlace;
4. Ao ser ativada pela camada física, a camada de enlace responde com a primeira requisição na fila;
5. As camadas de enlace enviam uma resposta às suas respectivas camadas físicas com instruções;
6. Os protocolos da camada física criam um par qubit-fóton usando seus processadores quânticos e enviam o fóton para a conexão anunciada;
7. Quando ambos os fótons chegarem ao detector da conexão anunciada, eles são medidos;
8. A conexão anunciada informa à camada física o resultado da medição;
9. O resultado da medição é propagado à camada de enlace, que agora pode decidir enviar uma resposta à camada de rede;
10. Os passos 5 a 9 são repetidos até que o número de pares desejados seja criado.

A camada física é implementada usando o protocolo MHP (MidpointHeraldingProtocol, Protocolo de Anúncio no ponto médio — tradução livre) enquanto a camada de enlace é implementada usando um EGProtocol (Entanglement Generation — protocolo de geração de emaranhamento). O MHP deve acionar o EGP com um temporizador fixo, e iniciar o processo de geração de emaranhamento em uma resposta do EGP. Isto é implementado a seguir:

```python
class MHP(NodeProtocol):
    def __init__(self, no, passo, nome_porta_q):
        super().__init__(node=no)
        self.passo = passo
        self.node.qmemory.ports['out'].forward_output(self.node.ports[nome_porta_q])
        # Iremos esperar por um resultado na porta de entrada
        self.nome_porta = nome_porta_q
        self.nome_porta_q = nome_porta_q
        # Precisamos lembrar se já enviamos um fóton
        self.trigger_label = "TRIGGER"
        self.resposta_label = "RESPOSTA"
        self.add_signal(self.trigger_label)
        self.add_signal(self.resposta_label)
        self._do_task_label = 'do_task_label'
        self.add_signal(self._do_task_label)

    class ProgramaEmissao(QuantumProgram):
        def __init__(self):
            super().__init__(num_qubits=2)

        def program(self):
            # Emite de q2 usando q1
            q1, q2 = self.get_qubit_indices(self.num_qubits)
            self.apply(INSTR_INIT, q1)
            self.apply(INSTR_EMIT, [q1, q2])
            yield self.run()

    def run(self):
        while True:
            # Ao invés de uma duração, especificamos o tempo explicitamente para ser
            # um múltiplo doo passo
            tempo = (1 + (ns.sim_time() // self.passo)) * self.passo
            temporizador_espera = self.await_timer(end_time=tempo)
            sinal_espera = self.await_signal(self, self._do_task_label)
            exprev = yield temporizador_espera | sinal_espera

            if exprev.second_term.value:
                # Inicia a tentativa de emaranhamento
                pos_fila = self.get_signal_result(self._do_task_label)
                prog = self.ProgramaEmissao()
                self.node.qmemory.execute_program(prog, qubit_mapping=[pos_fila + 1, 0])
                porta = self.node.ports[self.nome_porta_q]
                yield self.await_port_input(porta)
                mensagem = porta.rx_input()
                if mensagem.meta.get("header") == 'photonoutcome':
                    saida = mensagem.items[0]
                else:
                    saida = 'FALHA'
                self.send_signal(self.resposta_label, result=(saida, pos_fila + 1))
            else:
                self.send_signal(self.trigger_label)

    def faz_tarefa(self, pos_fila):
        self.send_signal(self._do_task_label, result=pos_fila)
```

O EGP é definido como um serviço: um protocolo que define a interface que a camada de rede pode usar mais explicitamente. Podemos dividir nosso protocolo em duas partes: lidar com a entrada de requisições e lidar com as requisições. Nós vamos usar o serviço para lidar com a entrada de requisições, e as requisições serão manipuladas por um protocolo. Nosso EGP não consegue lidar com múltiplas requisições de uma vez, então usamos uma fila para marcar as requisições. O serviço é implementado como mostrado abaixo por um manipulador de requisições abstrato.

```python
class EGService(ServiceProtocol, metaclass=abc.ABCMeta):
    criar_req = namedtuple('CriarCamadaEnlace', ['id_proposito', 'numero'])
    res_ok = namedtuple('CamadaEnlaceOK', ['id_proposito', 'id_criacao', 'id_qubit_logico'])

    def __init__(self, no, nome=None):
        super().__init__(node=no, name=nome)
        # Registra a requisição e resposta
        self.register_request(self.criar_req, self.criar)
        self.register_response(self.res_ok)
        # Iremos usar uma fila para requisições
        self.fila = deque()
        self._novo_sinal_req = "Nova requisição na fila"
        self.add_signal(self._novo_sinal_req)
        self._id_criacao = 0

    def lida_com_requisicao(self, requisicao, identificador, tempo_inicio=None, **kwargs):
        if tempo_inicio is None:
            tempo_inicio = ns.sim_time()
        self.fila.append((tempo_inicio, (identificador, requisicao, kwargs)))
        self.send_signal(self._novo_sinal_req)
        return kwargs

    def run(self):
        while True:
            yield self.await_signal(self, self._novo_sinal_req)
            while len(self.fila) > 0:
                tempo_inicio, (id_manipulador, requisicao, kwargs) = self.fila.popleft()
                if tempo_inicio > ns.sim_time():
                    yield self.await_timer(end_time=tempo_inicio)
                func = self.request_handlers[id_manipulador]
                args = requisicao._asdict()
                gen = func(**{**args, **kwargs})
                yield from gen

    def _pega_proximo_id_criacao(self):
        # Retorna um identificador de criação único
        self._id_criacao += 1
        return self._id_criacao

    @abc.abstractmethod
    def criar(self, id_proposito, numero, id_criacao, **kwargs):
        pass
```

A sincronização e manipulação da requisição agora podem ser definidas no protocolo:

```python
class EGP(EGService):
    def __init__(self, no, nome_porta_c, nome=None):
        super().__init__(no=no, nome=nome)
        # Requer um protocolo de camada física
        self._nome_mh = "Protocolo_MH"
        # Configura a sincronização de fila
        self.porta_c = self.no.ports[nome_porta_c]
        self.porta_c.bind_input_handler(self._lida_com_msg)

    def adiciona_camada_fisica(self, protocolo_mh):
        self.add_subprotocol(protocolo_mh, name=self._nome_mh)

    def lida_com_requisicao(self, requisicao, identificador, tempo_inicio=None, **kwargs):
        if kwargs.get('id_criacao') is None:
            kwargs['id_criacao'] = self._pega_proximo_id_criacao()
        if tempo_inicio is None:
            tempo_viagem = 10000
            tempo_inicio = ns.sim_time() + tempo_viagem
            # Assegurar que Message não combine especificando um cabeçalho
            self.porta_c.tx_output(
                Message([requisicao, identificador, tempo_inicio, kwargs], cabecalho=requisicao)
            )
        return super().lida_com_requisicao(requisicao, identificador, tempo_inicio, **kwargs)

    def _lida_com_msg(self, msg):
        requisicao, id_manipulador, tempo_inicio, kwargs = msg.items
        self.lida_com_requisicao(requisicao, id_manipulador, tempo_inicio, **kwargs)

    def run(self):
        if self._nome_mh not in self.subprotocols or \
                not isinstance(self.subprotocols[self._nome_mh], Protocol):
            raise ValueError("EGP precisa de um protocolo de camada física.")
        self.start_subprotocols()
        yield from super().run()

    def criar(self, id_proposito, numero, **kwargs):
        id_criacao = kwargs['id_criacao']
        self._id_criacao = id_criacao
        pares_atuais = 0
        sub_proto = self.subprotocols[self._nome_mh]
        espera_trigger = self.await_signal(sub_proto, sub_proto.trigger_label)
        espera_resposta = self.await_signal(sub_proto, sub_proto.resposta_label)
        # Inicia o loop principal
        while pares_atuais < numero:
            exprev = yield espera_trigger | espera_resposta
            for evento in exprev.triggered_events:
                pos_fila = self._lida_com_evento(evento, pares_atuais)
                if pos_fila is not None:
                    resposta = self.res_ok(id_proposito, id_criacao, pos_fila)
                    self.send_response(resposta)
                    pares_atuais += 1

    def _lida_com_evento(self, evento, pares_atuais):
        # Comunica com a camada física nos sinais de trigger e resposta
        sub_proto = self.subprotocols[self._nome_mh]
        label, valor = sub_proto.get_signal_by_event(evento, receiver=self)
        if label == sub_proto.trigger_label:
            sub_proto.faz_tarefa(pos_fila=pares_atuais)
        elif label == sub_proto.resposta_label:
            saida, pos_fila = valor
            # Saída de 1 é |01>+|10>, 2 é |01>-|10>
            # Outras saídas não são estados emaranhados
            if saida == 1 or saida == 2:
                return pos_fila
        return None
```

Falando agora da conexão anunciada... Ela contém um detector para fazer a medição dos fótons que chegam. Neste exemplo, nós temos um detector no meio da conexão.

![](C:\Users\Junior\AppData\Local\Packages\CanonicalGroupLimited.Ubuntu_79rhkp1fndgsc\LocalState\rootfs\home\junior\netsquid-pt-br\aafig-acfb1e06d944ba845256afa3260bb5e5d2e83560.svg)

```python
class ConexaoAnunciada(Connection):
    def __init__(self, nome, distancia_para_a, distancia_para_b, janela_tempo=0):
        super().__init__(name=nome)
        atraso_a = distancia_para_a / 200000 * 1e9
        atraso_b = distancia_para_b / 200000 * 1e9
        canal_a = ClassicalChannel("CanalA", delay=atraso_a)
        canal_b = ClassicalChannel("CanalB", delay=atraso_b)
        canalq_a = QuantumChannel("CanalQA", delay=atraso_a)
        canalq_b = QuantumChannel("CanalQB", delay=atraso_b)
        # Adiciona todos os canais como subcomponentes
        self.add_subcomponent(canal_a)
        self.add_subcomponent(canal_b)
        self.add_subcomponent(canalq_a)
        self.add_subcomponent(canalq_b)
        # Adiciona o detector no ponto médio
        detector = DetectorBSM("PontoMedio", atraso_sistema=janela_tempo)
        self.add_subcomponent(detector)
        # Conecta as portas
        self.ports['A'].forward_input(canalq_a.ports['send'])
        self.ports['B'].forward_input(canalq_b.ports['send'])
        canalq_a.ports['recv'].connect(detector.ports['qin0'])
        canalq_b.ports['recv'].connect(detector.ports['qin1'])
        canal_a.ports['send'].connect(detector.ports['cout0'])
        canal_b.ports['send'].connect(detector.ports['cout1'])
        canal_a.ports['recv'].forward_input(self.ports['A'])
        canal_a.ports['recv'].forward_input(self.ports['A'])
        canal_b.ports['recv'].forward_input(self.ports['B'])
```

A parte principal da conexão anunciada é o DetectorBSM:

```python
class DetectorBSM(QuantumDetector):
    def __init__(self, nome, atraso_sistema=0, tempo_morto=0, modelos=None,
                 saida_meta=None, erro_na_falha=False, propriedades=None):
        super().__init__(nome, num_input_ports=2, num_output_ports=2, meas_operators=cria_operadores(),
                         system_delay=atraso_sistema, dead_time=tempo_morto, models=modelos, output_meta=saida_meta,
                         error_on_fail=erro_na_falha, properties=propriedades)
        self._ids_envio = []

    def preprocessa_entradas(self):
        super().preprocess_inputs()
        for nome_porta, lista_qubit in self._qubits_per_port.items():
            if len(lista_qubit) > 0:
                self._ids_envio.append(nome_porta[3:])

    def informa(self, resultados_porta):
        for nome_porta, saidas in resultados_porta.items():
            if len(saidas) == 0:
                saidas = ['TIMEOUT']
                cabecalho = 'erro'
            else:
                cabecalho = 'photonoutcome'
            # Extrai as ids dos nomes das portas (cout...)
            if nome_porta[4:] in self._ids_envio:
                msg = Message(saidas, header=cabecalho, **self._meta)
                self.ports[nome_porta].tx_output(msg)

    def finaliza(self):
        super().finish()
        self._ids_envio.clear()

```

Juntas estas partes permitem a geração robusta de emaranhamento. Ainda precisamos configurar os protocolos. Um modelo da camada de rede irá enviar a requisição para a camada de enlace em Alice. Fazendo o EGP um subprotocolo da camada de rede, este irá parar quando a camada de rede não tiver mais requisições.

```python
class ProtocoloRede(Protocol):
    def __init__(self, nome, protocolo_emaranhamento, protocolo_emaranhamento_remoto):
        super().__init__(name=nome)
        self.add_subprotocol(protocolo_emaranhamento, "EGP_Alice")
        self.add_subprotocol(protocolo_emaranhamento_remoto, "EGP_Bob")

    def run(self):
        proto = self.subprotocols['EGP_Alice'].start()
        self.subprotocols['EGP_Bob'].start()
        # Inicia com uma única requisição
        req_1 = proto.criar_req(id_proposito=4, numero=3)
        id_criacao = proto.put(req_1)['id_criacao']
        print(f"Esperando por respostas com id_criacao {id_criacao}")
        yield from self.mostra_resultados(proto, req_1)
        req_2 = proto.criar_req(id_proposito=6, numero=2)
        id_criacao = proto.put(req_2)['id_criacao']
        print(f"Esperando por respostas com id_criacao {id_criacao}")
        req_3 = proto.criar_req(id_proposito=4, numero=1)
        id_criacao = proto.put(req_3)['id_criacao']
        print(f"Esperando por respostas com id_criacao {id_criacao}")
        yield from self.mostra_resultados(proto, req_2)
        yield from self.mostra_resultados(proto, req_3)
        print("Todas as requisições de rede foram finalizadas.")

    def mostra_resultados(self, proto, requisicao):
        sinal_ok = proto.get_name(proto.res_ok)
        print(f"Qubits entre Alice e Bob com id propósito {requisicao.id_proposito}:")
        for _ in range(requisicao.numero):
            yield self.await_signal(proto, sinal_ok)
            res = proto.get_signal_result(sinal_ok, self)
            qubits = proto.node.qmemory.peek(res.id_qubit_logico)[0].qstate.qubits
            print(f"    {ns.sim_time():8.0f}: {qubits} com id_criacao {res.id_criacao}")
```

Finalmente, colocamos os protocolos nos nós.

```python
def configura_protocolo(rede):
    nos = rede.nodes
    # Configura Alice
    portas_q = rede.get_connected_ports(*nodes, label='quantica')
    portas_c = rede.get_connected_ports(*nodes, label='classica')
    alice_mhp = MHP(nos['Alice'], 500, portas_q[0])
    alice_egp = EGP(nos['Alice'], portas_c[0])
    alice_egp.adiciona_camada_fisica(alice_mhp)
    # Configura Bob
    bob_mhp = MHP(nos['Bob'], 470, portas_q[1])
    bob_egp = EGP(nos['Bob'], portas_c[1])
    bob_egp.adiciona_camada_fisica(bob_mhp)
    return ProtocoloRede("ProtocoloSimplesEnlace", alice_egp, bob_egp)
```

Para rodar a simulação:

```python
def roda_simulacao():
    ns.sim_reset()
    ns.set_random_state(42)
    ns.set_qstate_formalism(QFormalism.DM)
    rede = cria_rede_exemplo()
    protocolo = configura_protocolo(rede)
    protocolo.start()
    ns.sim_run()
```