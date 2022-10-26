# Tutorial Netsquid - Protocolos

# De posse de nós (Node) e conexões (Connection) configuradas, podemos atribuir protocolos
# (Protocol) aos nós. Em contraste com componentes, que representam entidades físicas em uma
# simulação (hardware), protocolos são entidades de simulação virtuais que controlam o 
# comportamento dos componentes (software). Por exemplo, um protocolo pode instruir um processador
# quântico a medir um de seus qubits ao receber uma mensagem clássica em uma das portas do nó.
# Nesta seção do tutorial, mostraremos como utilizar protocolos para teleportar um qubit de Alice
# a Bob.

## Protocolo

# Há duas formas de criar protocolos: por meio de callbacks, como foi feito na seção 2 do tutorial,
# ou usando um gerador python. Nesta seção, a segunda opção é explicada; com um gerador, o fluxo
# assíncrono de um protocolo é geralmente mais fácil de seguir. Os principais métodos de protocolos
# são:

## start() - inicia o protocolo e geralmente reseta quaisquer variáveis de estado.
## stop() - para o protocolo, mas não deve modificar nenhum variável de estado.
## reset() - para e reinicia o protocolo.
## run() - aqui o fluxo do protocolo pode ser definido.
### Dentro do método run(), pode-se produzir expressões de evento (EventExpression). yield é usado
### para criar um iterador gerador. Ao executar tal gerador, o protocolo roda até encontrar o
### primeiro yield, onde será suspenso. O gerador lembra onde foi suspenso, assim, quando retomar
### a execução, continua de onde parou, e roda novamente até encontrar o próximo yield.

### Usamos isto para criar retornos de chamada (callbacks) em linha, produzindo uma EventExpression.
### Quando a expressão é provocada - geralmente em um ponto posterior da simulação - o protocolo
### continua e roda até o próximo yield ou return.

# Abaixo, temos um protocolo que 'dorme' por 100 nanossegundos:
import netsquid as ns
from netsquid.protocols import Protocol

class ProtocoloEspera(Protocol):
    def run(self):
        print(f"Iniciando protocolo em {ns.sim_time()}")
        yield self.await_timer(100)
        print(f"Finalizando protocolo em {ns.sim_time()}")

print("Iniciando simulação e protocolo...")
ns.sim_reset()
protocolo = ProtocoloEspera()
protocolo.start()
estatisticas = ns.sim_run()
print(estatisticas)

# Quando um protocolo é finalizado, envia um sinal (Signals) FINISHED (FINALIZADO) para informar
# quaisquer entidades ouvintes. Sinais são eventos de um tipo específico e com um resultado
# opcional. Há vários outros sinais predefinidos, como SUCCESS (SUCESSO) e FAIL (FALHA). Um
# protocolo pode enviar sinais usando o método send_signal().

## O exemplo do ping pong usando protocolos

# Aqui, ao invés de usar funções callback e eventos, podemos escrever um único gerador para toda
# a sequência.

from netsquid.protocols import NodeProtocol
from netsquid.components import QuantumChannel
from netsquid.nodes import Node, DirectConnection
from netsquid.qubits import qubitapi as qapi

class ProtocoloPing(NodeProtocol):
    def run(self):
        print(f"Iniciando ping em t={ns.sim_time()}")
        porta = self.node.ports["porta_para_canal"]
        qubit, = qapi.create_qubits(1)
        porta.tx_output(qubit) # Envia o qubit para Pong
        while True:
            # Espera o recebimento do qubit de volta
            yield self.await_port_input(porta)
            qubit = porta.rx_input().items[0]
            m, prob = qapi.measure(qubit, ns.Z)
            labels_z = ("|0>", "|1>")
            print(f"{ns.sim_time()}: Evento pong! {self.node.name} mediu "
                  f"{labels_z[m]} com probabilidade {prob:.2f}")
            porta.tx_output(qubit) # Envia qubit para B

class ProtocoloPong(NodeProtocol):
    def run(self):
        print("Iniciando pong em t={}".format(ns.sim_time()))
        porta = self.node.ports["porta_para_canal"]
        while True:
            yield self.await_port_input(porta)
            qubit = porta.rx_input().items[0]
            m, prob = qapi.measure(qubit, ns.X)
            labels_x = ("|+>", "|->")
            print(f"{ns.sim_time()}: Evento ping! {self.node.name} mediu "
                  f"{labels_x[m]} com probabilidade {prob:.2f}")
            porta.tx_output(qubit) # envia qubit para Ping

# Podemos rodar esses dois protocolos nos nós das nossas entidades Ping e Pong. Para isso,
# conectamos os dois por meio de uma conexão direta e atribuímos a eles seus protocolos.

ns.sim_reset()
ns.set_random_state(seed=42)
no_ping = Node("Ping", port_names=["porta_para_canal"])
no_pong = Node("Pong", port_names=["porta_para_canal"])
conexao = DirectConnection("Conexão",
                           QuantumChannel("Canal_ED", delay=10),
                           QuantumChannel("Canal_DE", delay=10))
no_ping.ports["porta_para_canal"].connect(conexao.ports["A"])
no_pong.ports["porta_para_canal"].connect(conexao.ports["B"])
protocolo_ping = ProtocoloPing(no_ping)
protocolo_pong = ProtocoloPong(no_pong)

# Agora, podemos rodar a simulação...

protocolo_ping.start()
protocolo_pong.start()
estatisticas = ns.sim_run(91)
print(estatisticas)

# Apesar de esta simulação ter parado em 81 nanossegundos, foi por conta da especificação em
# sim_run(), mas perceba que os protocolos nunca encerram. O que aconteceria se os protocolos
# fossem parados ou resetados?

protocolo_pong.stop()
estatisticas = ns.sim_run()
print(estatisticas)

# Com o protocolo pong sendo finalizado, a simulação roda até que não haja mais eventos. Na 
# operação anterior, pong havia enviado um qubit de volta para ping, mas não havia sido
# processado. Nesta operação, o qubit que estava 'esperando' chegou até o protocolo ping. Este
# o 'pinga' de volta, mas pong não processa, por conta da finalização do protocolo. Nada estava
# a espera do qubit na porta, portanto o qubit foi perdido. Quando pong iniciar novamente, nada
# irá acontecer, já que não há qubit para ser jogado de um lado para outro.

protocolo_pong.start()
estatisticas = ns.sim_run()
print(estatisticas)

# O protocolo ping deve ser reiniciado para criar um novo qubit.

protocolo_ping.reset()
estatisticas = ns.sim_run(duration=51)
print(estatisticas)

## O exemplo do teleporte usando protocolos

# Agora, podemos configurar nosso exemplo do teleporte utilizando protocolos. Alice terá um
# protocolo para criar um estado quântico que deseja teleportar. Por ora, este protocolo não
# precisa produzir nada, irá criar um estado aleatório. Quando o qubit é criado, o protocolo
# sinaliza ao mundo que obteve sucesso e em qual posição da memória o qubit está localizado.

# Você pode pensar que Alice poderia simplesmente enviar um sinal com os resultados das medições,
# ao qual Bob poderia estar ouvindo. No entanto, isto quebraria a localidade; a mensagem seria
# enviada mais rápido que a luz para Bob. Para evitar esta possibilidade, um protocolo de nó
# (NodeProtocol) pode ser usaddo. Tal protocolo possui acesso a um único nó, e também garante
# que protocolos só podem sinalizar a outros protocolos naquele nó, isto é, na mesma localização.
# Se um protocolo deveria ter acesso a um conjunto limitado de nós, um protocolo local
# (LocalProtocol) pode ser usado, ou um protocolo normal (?) se a localidade não for um problema.

from netsquid.protocols import NodeProtocol, Signals

class ProtocoloEstadoInicial(NodeProtocol):
    def run(self):
        qubit, = qapi.create_qubits(1)
        pos_mem = self.node.qmemory.unused_positions[0]
        self.node.qmemory.put(qubit, pos_mem)
        self.node.qmemory.operate(ns.H, pos_mem)
        self.node.qmemory.operate(ns.S, pos_mem)
        self.send_signal(signal_label=Signals.SUCCESS, result=pos_mem)

# Agora Alice precisa de um protocolo para realizar sua medição de Bell. Antes que ela possa
# fazer a medição tanto o qubit que ela quer teleportar como o qubit que está emaranhado com Bob
# precisa estar na sua memória, assim, Alice precisa esperar por ambos. Em princípio, os qubits
# podem chegar em qualquer ordem, portanto, Alice precisa esperar pelos dois simultaneamente.
# Isso pode ser feito combinando as expressões de evento com o operador & (AND):

# expressao_and = yield expressao1 & expressao2

# Alternativamente, o operador | (OR) espera até que uma expressão seja verdadeira:

# expressao_or = yield expressao3 | expressao4 

# A expressão de evento retornada é uma cópia da expressão de evento que foi produzida. Esta cópia
# possui informação acerca de qual expressão foi provocada. Por exemplo...
# expressao_or.first_term.value -> é verdadeiro se expressao3 foi provocada
# expressao_or.second_term.value -> é verdadeiro se expressao4 foi provocada
# Para ver uma lista de eventos que causaram a expressão a ser provocada:
# expressao.or.triggered_events

# Alice espera por um sinal de ProtocoloEstadoInicial (isto é, seu qubit sendo preparado) e até que
# o qubit emaranhado chegue na sua memória. Uma vez que ambos ocorram, ela pode realizar a medição
# e enviar os resultados para Bob.

from pydynaa import EventExpression

class ProtocoloMedicaoBell(NodeProtocol):
    def __init__(self, no, protocolo_qubit):
        super().__init__(no)
        self.add_subprotocol(protocolo_qubit, 'protocoloq')

    def run(self):
        qubit_inicializado = False
        emaranhamento_pronto = False
        while True:
            exprev_sinal = self.await_signal(
                    sender=self.subprotocols['protocoloq'],
                    signal_label=Signals.SUCCESS)
            exprev_porta = self.await_port_input(self.node.ports["qin_charlie"])
            expressao = yield exprev_sinal | exprev_porta
            if expressao.first_term.value:
                # Primeira expressão foi provocada
                qubit_inicializado = True
            else:
                # Segunda expressão foi provocada
                emaranhamento_pronto = True
            if qubit_inicializado and emaranhamento_pronto:
                # Realiza a medição de Bell
                self.no.qmemory.operate(ns.CNOT, [0, 1])
                self.no.qmemory.operate(ns.H, 0)
                m, _ = self.no.qmemory.measure([0, 1])
                # Envia os resultados para Bob
                self.no.ports["cout_bob"].tx_output(m)
                self.send_signal(Signals.SUCCESS)
                print(f"{ns.sim_time():.1f}: Alice recebeu o qubit emaranhado, "
                      f"mediu os qubits e está enviando correções")
                break

    def start(self):
        super().start()
        self.start_subprotocols()

# Bob precisa realizar as correções no qubit que recebeu da fonte. Então, Bob também precisa
# esperar duas coisas ocorrerem: os dados clássicos chegarem de Alice e o qubit emaranhado que
# é colocado na memória de Bob.

class ProtocoloCorrecao(NodeProtocol):

    def __init__(self, no):
        super().__init__(no)

    def run(self):
        porta_alice = self.no.ports["cin_alice"]
        porta_charlie = self.no.ports["qin_charlie"]
        emaranhamento_pronto = False
        resultados_medicao = False
        while True:
            exprev_porta_a = self.await_port_input(porta_alice)
            exprev_porta_c = self.await_port_input(porta_charlie)
            expressao = yield exprev_porta_a | exprev_porta_c
            if expressao.first_term.value:
                resultados_medicao = True
            else:
                emaranhamento_pronto = True
            if resultados_medicao is not None and emaranhamento_pronto:
                if resultados_medicao[0]:
                    self.no.qmemory.operate(ns.Z, 0)
                if resultados_medicao[1]:
                    self.no.qmemory.operate(ns.X, 0)
                self.send_signal(Signals.SUCCESS, 0)
                fidelidade = ns.qubits.fidelity(self.no.qmemory.peek(0)[0],
                                                ns.y0, squared=True)
                print(f"{ns.sim_time():.1f}: Bob recebeu o qubit emaranhado e "
                      f"correções! Fidelidade = {fidelidade:.3f}")
                break

# Para finalizar, nós construímos uma rede exemplo da seção anterior, atribuímos os protocolos
# e rodamos a simulação. Agora, example_network_setup retorna uma rede ao invés de nós e
# conexões. Esta é uma classe conveniente (Network) que guarda todos os nós e conexões de uma rede.

from netsquid.examples.teleportation import example_network_setup
ns.sim_reset()
ns.set_qstate_formalism(ns.QFormalism.DM)
ns.set_random_state(seed=42)
rede = example_network_setup()
alice = rede.get_node("Alice")
bob = rede.get_node("Bob")
protocolo_estado_aleatorio = ProtocoloEstadoInicial(alice)
protocolo_medicao_bell = ProtocoloMedicaoBell(alice, protocolo_estado_aleatorio)
protocolo_correcao = ProtocoloCorrecao(bob)
protocolo_medicao_bell.start()
protocolo_correcao.start()
estatisticas = ns.sim_run(100)
print(estatisticas)
