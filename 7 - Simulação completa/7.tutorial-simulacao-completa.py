# Tutorial Netsquid - Simulação Completa

# Com os conceitos de componentes, programas quânticos em um processador quântico e
# a explicação de protocolos, podemos finalizar e ajustar um protocolo de teleporte
# completo.

# O exemplo completo está no arquivo: exemplo_teleporte_netsquid.py, aqui são explicadas
# algumas partes do arquivo

# O primeiro passo para rodar uma simulação nno NetSquid é configurar a rede física com todos
# os seus componentes. No tutorial de Nós e Conexões, vimos como configurar uma rede entre
# Alice e Bob. Usaremos a mesma rede aqui. A principal diferença é que queremos que as operações
# quânticas levem algum tempo e sejam ruidosas. Para isso, precisamos de um processador com
# instruções físicas, ao invés de uma memória quântica.

import pandas
from netsquid.components.qprocessor import QuantumProcessor, PhysicalInstruction
from netsquid.nodes import Node, Connection, Network
from netsquid.protocols.protocol import Signals
from netsquid.protocols.nodeprotocols import NodeProtocol
from netsquid.components.qchannel import QuantumChannel
from netsquid.components.cchannel import ClassicalChannel
from netsquid.components.qsource import QSource, SourceStatus
from netsquid.qubits.state_sampler import StateSampler
from netsquid.components.qprogram import QuantumProgram
from netsquid.components.models.qerrormodels import DepolarNoiseModel, DephaseNoiseModel
from netsquid.components.models.delaymodels import FibreDelayModel, FixedDelayModel
from netsquid.util.datacollector import DataCollector
import netsquid as ns
import pydynaa
from netsquid.qubits import ketstates as ks
from netsquid.qubits import qubitapi as qapi
from netsquid.components import instructions as instr


# As conexões que usaremos entre os nós Alice e Bob são definidas similarmente à antes:


class ConexaoEmaranhada(Connection):
    def __init__(self, comprimento, frequencia_fonte, name="ConexaoEmaranhada"):
        super().__init__(name=name)
        fonteq = QSource(
            f"fonteq_{name}",
            StateSampler([ks.b00], [1.0]),
            num_ports=2,
            timing_model=FixedDelayModel(delay=1e9 / frequencia_fonte),
            status=SourceStatus.INTERNAL,
        )
        self.add_subcomponent(fonteq, name="fonteq")
        canalq_cparaa = QuantumChannel(
            "CanalQ_CparaA",
            length=comprimento / 2,
            models={"delay_model": FibreDelayModel()},
        )
        canalq_cparab = QuantumChannel(
            "CanalQ_CparaB",
            length=comprimento / 2,
            models={"delay_model": FibreDelayModel()},
        )
        # Adiciona canais e encaminha a saída do canal quântico para porta externa de saída:
        self.add_subcomponent(canalq_cparaa, forward_output=[("A", "recv")])
        self.add_subcomponent(canalq_cparab, forward_output=[("B", "recv")])
        # Conecta a saída de fonteq à entrada do canal quântico
        fonteq.ports["qout0"].connect(canalq_cparaa.ports["send"])
        fonteq.ports["qout1"].connect(canalq_cparab.ports["send"])


class ConexaoClassica(Connection):
    def __init__(self, comprimento, name="ConexaoClassica"):
        super().__init__(name=name)
        self.add_subcomponent(
            ClassicalChannel(
                "Canal_AparaB",
                length=comprimento,
                models={"delay_model": FibreDelayModel()},
            ),
            forward_input=[("A", "send")],
            forward_output=[("B", "recv")],
        )


# Os nós de Alice e Bob usam o mesmo processador quântico


def cria_processador(taxa_depolar, taxa_defasagem):
    modelo_ruido_medicao = DephaseNoiseModel(
        dephase_rate=taxa_defasagem, time_independent=True
    )
    instrucoes_fisicas = [
        PhysicalInstruction(instr.INSTR_INIT, duration=3, parallel=True),
        PhysicalInstruction(instr.INSTR_H, duration=1, parallel=True, topology=[0, 1]),
        PhysicalInstruction(instr.INSTR_X, duration=1, parallel=True, topology=[0]),
        PhysicalInstruction(instr.INSTR_Z, duration=1, parallel=True, topology=[0]),
        PhysicalInstruction(instr.INSTR_S, duration=1, parallel=True, topology=[0]),
        PhysicalInstruction(
            instr.INSTR_CNOT, duration=4, parallel=True, topology=[(0, 1)]
        ),
        PhysicalInstruction(
            instr.INSTR_MEASURE,
            duration=7,
            parallel=False,
            topology=[0],
            quantum_noise_model=modelo_ruido_medicao,
            apply_q_noise_after=False,
        ),
        PhysicalInstruction(
            instr.INSTR_MEASURE, duration=7, parallel=False, topology=[1]
        ),
    ]
    modelo_ruido_memoria = DepolarNoiseModel(depolar_rate=taxa_depolar)
    processador = QuantumProcessor(
        "processador_quantico",
        num_positions=2,
        memory_noise_models=[modelo_ruido_memoria] * 2,
        phys_instructions=instrucoes_fisicas,
    )
    return processador


# A função a seguir completa a configuração de rede e a retorna:


def configura_rede_exemplo(distancia_nos=4e-3, taxa_depolar=1e7, taxa_defasagem=0.2):
    # Configura os nós Alice e Bob com um processador quântico:
    alice = Node("Alice", qmemory=cria_processador(taxa_depolar, taxa_defasagem))
    bob = Node("Bob", qmemory=cria_processador(taxa_depolar, taxa_defasagem))
    # Cria uma rede
    rede = Network("Rede_teleporte")
    rede.add_nodes([alice, bob])
    # Configura uma conexão clássica entre os nós:
    con_c = ConexaoClassica(comprimento=distancia_nos)
    rede.add_connection(
        alice,
        bob,
        connection=con_c,
        label="classica",
        port_name_node1="cout_bob",
        port_name_node2="cin_alice",
    )
    # Configura conexão emaranhada entre os nós
    frequencia_fonte = 4e4 / distancia_nos
    con_q = ConexaoEmaranhada(
        comprimento=distancia_nos, frequencia_fonte=frequencia_fonte
    )
    porta_ac, porta_bc = rede.add_connection(
        alice,
        bob,
        connection=con_q,
        label="quantica",
        port_name_node1="qin_charlie",
        port_name_node2="qin_charlie",
    )
    alice.ports[porta_ac].forward_input(alice.qmemory.ports["qin1"])
    bob.ports[porta_bc].forward_input(bob.qmemory.ports["qin0"])
    return rede


## Configurando a simulação

# Ao invés de um protocolo, podemos usar um programa quântico para criar o estado a ser teleportado:


class ProgramaEstadoInicial(QuantumProgram):
    default_num_qubits = 1

    def program(self):
        (q1,) = self.get_qubit_indices(1)
        self.apply(instr.INSTR_INIT, q1)
        self.apply(instr.INSTR_H, q1)
        self.apply(instr.INSTR_S, q1)
        yield self.run()


# Da mesma forma, usamos um programa para realizar as medições de Bell:


class ProgramaMedicaoBell(QuantumProgram):
    default_num_qubits = 2

    def program(self):
        q1, q2 = self.get_qubit_indices(2)
        self.apply(instr.INSTR_CNOT, [q1, q2])
        self.apply(instr.INSTR_H, q1)
        self.apply(instr.INSTR_MEASURE, q1, output_key="M1")
        self.apply(instr.INSTR_MEASURE, q2, output_key="M2")
        yield self.run()


# Assim, usamos dois protocolos que rodam no nó de Alice.

# Há algumas diferenças dos protocolos usados aqui e os do tutorial Protocolos. Ao invés de
# iniciar o protocolo de medição de Bell com outro protocolo, este agora cria o programa para
# inicializar um estado. O programa é executado e o protocolo produz (? - yields) até que o
# programa finalize ou tenha recebido o qubit de Charlie na sua memória.


class ProtocoloMedicaoBell(NodeProtocol):
    def run(self):
        qubit_inicializado = False
        emaranhamento_pronto = False
        programa_inicia_qubit = ProgramaEstadoInicial()
        programa_medicao = ProgramaMedicaoBell()
        self.node.qmemory.execute_program(programa_inicia_qubit)
        while True:
            expr = yield (
                self.await_program(self.node.qmemory)
                | self.await_port_input(self.node.ports["qin_charlie"])
            )
            if expr.first_term.value:
                qubit_inicializado = True
            else:
                emaranhamento_pronto = True
            if qubit_inicializado and emaranhamento_pronto:
                # Assim que ambos os qubits chegarem, aplicar programa de medição e enviar a Bob
                yield self.node.qmemory.execute_program(programa_medicao)
                (m1,) = programa_medicao.output["M1"]
                (m2,) = programa_medicao.output["M2"]
                self.node.ports["cout_bob"].tx_output((m1, m2))
                self.send_signal(Signals.SUCCESS)
                qubit_inicializado = False
                emaranhamento_pronto = False
                self.node.qmemory.execute_program(programa_inicia_qubit)


# Do lado de Bob, as correções também devem ser realizadas por meio de instruções. É possível
# executar instruções únicas ao invés de criar um novo programa para isso.
class ProtocoloCorrecao(NodeProtocol):
    def run(self):
        porta_alice = self.node.ports["cin_alice"]
        porta_charlie = self.node.ports["qin_charlie"]
        emaranhamento_pronto = False
        resultados_med = None
        while True:
            # Espera pelos resultados das medições de Alice ou qubit de Charlie chegar
            expr = yield (
                self.await_port_input(porta_alice)
                | self.await_port_input(porta_charlie)
            )
            if expr.first_term.value:  # Se as medições de Alice chegarem
                (resultados_med,) = porta_alice.rx_input().items
            else:
                emaranhamento_pronto = True
            if resultados_med is not None and emaranhamento_pronto:
                # Faz correções
                if resultados_med[0] == 1:
                    self.node.qmemory.execute_instruction(instr.INSTR_Z)
                    yield self.await_program(self.node.qmemory)
                if resultados_med[1] == 1:
                    self.node.qmemory.execute_instruction(instr.INSTR_X)
                    yield self.await_program(self.node.qmemory)
                self.send_signal(Signals.SUCCESS, 0)
                emaranhamento_pronto = False
                resultados_med = None


## Rodando uma simulação

# Agora estamos prontos para uma simulação. Você deve ter notado que os protocolos foram
# ligeiramente ajustados em relação aos protocolos da seção Protocolos. Os resultados são
# resetados e um programa é executado depois de todas as expressões de eventos serem
# provocadas. Isto é feito para configurar os protocolos para múltiplas rodadas. A fonte
# quântica em Charlie é acionada por um temporizador. Cada vez que é acionada, faz Alice
# teleportar mais qubits.

# Uma vez que Bob tenha recebido e corrigido seu qubit, nós comparamos com o estado inicial
# criado por Alice. Isso é feito por um coletor de dados (DataCollector). O coletor escuta
# uma série de eventos e armazena resultados sobre a simulação. Tendo em vista que é usado
# após uma simulação, um coletor de dados pode realizar ações que não são normalmente
# permitidas, como ler o estado completo de qubits (mesmo que estejam armazenados em nós
# diferentes, quebrando a localidade).

# O coletor de dados pega o qubit de Bob, mede a fidelidade e descarta o qubit. A fidelidade
# é armazenada no coletor de dados.


def exemplo_configura_sim(no_A, no_B):
    def coleta_dados_fidelidade(exprev):
        protocolo = exprev.triggered_events[-1].source
        pos_mem = protocolo.get_signal_result(Signals.SUCCESS)
        (qubit,) = protocolo.node.qmemory.pop(pos_mem)
        fidelidade = qapi.fidelity(qubit, ns.y0, squared=True)
        qapi.discard(qubit)
        return {"fidelidade": fidelidade}

    protocolo_alice = ProtocoloMedicaoBell(no_A)
    protocolo_bob = ProtocoloCorrecao(no_B)
    dc = DataCollector(coleta_dados_fidelidade)
    dc.collect_on(
        pydynaa.EventExpression(source=protocolo_bob, event_type=Signals.SUCCESS.value)
    )
    return protocolo_alice, protocolo_bob, dc


# Iremos medir a fidelidade média de 1000 rodadas e rodar o experimento para diferentes taxas
# de depolarização


def roda_experimento(numero_rodadas, taxas_depolar, distancia=4e-3, taxa_defasagem=0.0):
    dados_fidelidade = pandas.DataFrame()
    for i, taxa_depolar in enumerate(taxas_depolar):
        ns.sim_reset()
        rede = configura_rede_exemplo(distancia, taxa_depolar, taxa_defasagem)
        no_a = rede.get_node("Alice")
        no_b = rede.get_node("Bob")
        protocolo_alice, protocolo_bob, dc = exemplo_configura_sim(no_a, no_b)
        protocolo_alice.start()
        protocolo_bob.start()
        con_q = rede.get_connection(no_a, no_b, label="quantica")
        cycle_runtime = (
            con_q.subcomponents["fonteq"]
            .subcomponents["internal_clock"]
            .models["timing_model"]
            .delay
        )
        ns.sim_run(cycle_runtime * numero_rodadas + 1)
        df = dc.dataframe
        df["taxa_depolar"] = taxa_depolar
        dados_fidelidade = dados_fidelidade.append(df)
    return dados_fidelidade


# Usamos a biblioteca matplotlib para mostrar a figura quando a simulação completa for rodada.
# Esta biblioteca não é parte dos requisitos, portanto precisa ser instalada manualmente se
# você deseja gerar o plot.


def cria_plot():
    from matplotlib import pyplot as plt

    taxas_depolar = [1e6 * i for i in range(0, 200, 10)]
    fidelidades = roda_experimento(
        numero_rodadas=1000,
        distancia=4e-3,
        taxas_depolar=taxas_depolar,
        taxa_defasagem=0.0,
    )
    estilo = {
        "kind": "scatter",
        "grid": True,
        "title": "Fidelidade do estado quântico teleportado",
    }
    dados = (
        fidelidades.groupby("taxa_depolar")["fidelidade"]
        .agg(fidelidade="mean", sem="sem")
        .reset_index()
    )
    dados.plot(x="taxa_depolar", y="fidelidade", yerr="sem", **estilo)
    # Por estar usando WSL, não há interface gráfica para visualizar a figura, por isso salvei e não mostrei o plot.
    plt.savefig("7. grafico_simulacao_completa.png")
    # Para mostrar, simplesmente retirar o comentário da linha abaixo.
    # plt.show()


if __name__ == "__main__":
    cria_plot()
