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
