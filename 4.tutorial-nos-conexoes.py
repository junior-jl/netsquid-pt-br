# Tutorial Netsquid - Nós e Conexões

# A seção anterior introduziu várias classes base de componentes para melhorar a modelagem
# de uma rede quântica. Nesta seção, comporemos esses componentes juntos em NÓS e CONEXÕES,
# dois exemplos de componentes compostos.
# Ao fim desta seção, teremos uma função que criará a rede automaticamente, a qual será usada
# na próxima seção para completar o esquema do teleporte usando protocolos.

def separador(tamanho = 50):
        """Separador básico de texto para melhor visualização."""
        print('*', end='')
        for i in range(tamanho):
            print('-', end='')
        print('*')

## Nós

# Nós (Node) representam as entidades de localização de uma rede quântica, onde todas as
# operações são locais. O Node (uma subclasse de Component) é um exemplo de componente
# composto que guarda e gerencia subcomponentes por meio de seu atributo subcomponents.

# Até aqui, Alice e Bob são duas entidades genéricas de simulação (Entity). Nesta seção,
# usaremos componentes Nós, descrevendo-os puramente em termos de seu hardware de rede.
# Em uma seção posterior, iremos demonstrar como descrever o comportamento lógico restante
# utilizando entidades de protocolo virtuais.
separador()
import netsquid as ns
from netsquid.nodes import Node
alice = Node("Alice")

# Pode-se pensar em um nó como uma localização para quaisquer componentes locais. Por exemplo,
# se queremos que Alice possua uma memória quântica, podemos adicionar ao seu nó:

from netsquid.components import QuantumMemory
memoriaq = QuantumMemory("MemoriaAlice", num_positions=2)
alice.add_subcomponent(memoriaq, name="memoria1")
print("Subcomponente de alice 'memoria1':")
print(alice.subcomponents["memoria1"])
separador()
# De maneira geral, qualquer componente pode ser adicionado como subcomponente de outro dessa
# forma, desde que uma hierarquia seja mantida de forma consistente. Podemos obter informações
# sobre os subcomponentes e supercomponentes de um componente como segue:

print("Subcomponentes de alice:")
print(alice.subcomponents)
separador()
print("Supercomponente de memoriaq:")
print(memoriaq.supercomponent)
separador()
print("alice não possui supercomponente?")
print(alice.supercomponent is None)
separador()

# Há um tratamento especial para a memória quântica principal (ou processador quântico) em nós:
# este pode ser especificado na inicialização, e pode ser acessado usando o atributo qmemory.
memoriaq_bob = QuantumMemory("MemoriaBob", num_positions=2)
bob = Node("Bob", qmemory=memoriaq_bob)
print(f"bob.qmemory -> {bob.qmemory}")
print(f"memoriaq_bob -> {memoriaq_bob}")
print(f"bob.subcomponents -> {bob.subcomponents}")
separador()

# Assim como qualquer componente, nós podem ter portas (Port). Não é possível conectar portas
# entre componentes com diferentes supercomponentes, por conta disso as portas de um nó servem
# como uma interface externa para todos os seus subcomponentes. Isso ajuda a impor localidade,
# algo que veremos novamente quando discutirmos protocolos. Um subcomponente de um nó pode
# se comunicar pelas portas de um nó encaminhando (forwarding) sua saída ou recebendo uma
# entrada encaminhada. 
# Checar imagem: https://docs.netsquid.org/latest-release/_images/ports_forwarding.png
alice.add_ports(['qin_charlie'])
alice.ports['qin_charlie'].forward_input(alice.qmemory.ports['qin'])

# Dessa forma, quaisquer mensagens transmitidas como entrada à porta qin_charlie de Alice será
# diretamente encaminhada como entrada para a porta qin da sua memória.

## Conexões

# Usando encaminhamento de porta, o nó se torna a única interface exposta. A prática recomendada
# é conectar nós remotos usando componentes conexão (Connection). A classe base Connection
# representa seus pontos finais remotos por duas portas nomeadas A e B, as quais, por padrão
# não estão ligadas ou encaminhaddas. A primeira conexão que iremos construir faz uso de um canal
# de comunicação clássico unidirecional (ClassicalChannel) entre Alice e Bob do exemplo do 
# teleporte.

# Definimos nossa conexão criando uma subclasse de Connection e implementando o comportamento da
# mensagem para as portas A e B. Um Canal tem como portas padrão 'send' e 'recv'. Quando uma 
# mensagem é posta na entrada da conexão (porta A), é encaminhada para a porta send do Canal. 
# Similarmente, a saída da porta recv é encaminhada à porta B.

from netsquid.nodes.connections import Connection
from netsquid.components import ClassicalChannel
from netsquid.components.models import FibreDelayModel

class ConexaoClassica(Connection):
    def __init__(self, comprimento):
        super().__init__(name="ConexãoClássica")
        self.add_subcomponent(ClassicalChannel("Canal_AparaB", length=comprimento,
            models={"delay_model": FibreDelayModel()}))
        self.ports['A'].forward_input(
                self.subcomponents["Canal_AparaB"].ports['send'])
        self.subcomponents["Canal_AparaB"].ports['recv'].forward_output(
                self.ports['B'])

# A alternativa à criação de subclasse seria iniciar um objeto de clase Connection e adicionar
# e conectar o subcomponent canal, como segue:

conexaoc = Connection("ConexãoClássica")
canalc = ClassicalChannel("Canal_AparaB")
conexaoc.add_subcomponent(canalc,
        forward_input=[("A", "send")],
        forward_output=[("B", "recv")])

# Uma conexão emaranhada para teleporte

# Checar imagem: 
# https://docs.netsquid.org/latest-release/_images/aafig-bb64252ef6c7bb51ecbbacba9707d1288ceb73aa.svg
# Uma conexão mais interessante pode ser construída a fim de abranger todo o maquinário de generação
# de emaranhamento de Charlie no exemplo do teleporte. Em particular, esta conexão, que chamaremos
# de ConexaoEmaranhada, pode conter a fonte quântica e os canais quânticos ligados a Alice e Bob.

from netsquid.components.qchannel import QuantumChannel
from netsquid.qubits import StateSampler
from netsquid.components.qsource import QSource, SourceStatus
from netsquid.components.models import FixedDelayModel, DepolarNoiseModel
import netsquid.qubits.ketstates as ks

class ConexaoEmaranhada(Connection):
    def __init__(self, comprimento, frequencia_fonte):
        super().__init__(name="ConexãoEmaranhada")
        modelo_tempo = FixedDelayModel(delay=(1e9 / frequencia_fonte))
        fonteq = QSource("fonteq", StateSampler([ks.b00], [1.0]), num_ports=2,
                timing_model=modelo_tempo,
                status=SourceStatus.INTERNAL)
        self.add_subcomponent(fonteq)
        canalq_cparaa = QuantumChannel("CanalQ_CparaA", length=comprimento / 2,
                models={"delay_model": FibreDelayModel()})
        canalq_cparab = QuantumChannel("CanalQ_CparaB", length=comprimento / 2,
                models={"delay_model": FibreDelayModel()})
        # Adiciona canais e encaminha a saída do canal quãntico para porta externa de saída:
        self.add_subcomponent(canalq_cparaa, forward_output=[("A", "recv")])
        self.add_subcomponent(canalq_cparab, forward_output=[("B", "recv")])
        # Conecta a saída de fonteq à entrada do canal quântico:
        fonteq.ports["qout0"].connect(canalq_cparaa.ports["send"])
        fonteq.ports["qout1"].connect(canalq_cparab.ports["send"])

# O clock interno na fonte quântica irá automaticamente provocar essa conexão a gerar qubits
# emaranhados e enviá-los como saída às portas remotas A e B pelos canais quânticos.

# Na próxima seção do tutorial, iremos adicionar entidades virtuais chamadas protocolos aos
# nós que irão descrever seu comportamento. Protocolos serão muito úteis para fluxos de controle
# complicados, e são mais simples de ler e escrever do que o que foi mostrado até aqui. O método
# a seguir demonstra como configurar uma rede para teleporte que podemos utilizar quando formos
# configurar Protocolos. Na simulação final, iremos ajustar este método para criar e retornar uma
# Rede (Network) ao invés de seus componentes individuais. A classe rede é um componente composto
# que ajuda a criar conexões e gerenciar nós e conexões.

def configura_rede_exemplo(node_distance=4e-3, depolar_rate=1e7):
    # Configura nós Alice e Bob com memórias quânticas:
    modelo_ruido = DepolarNoiseModel(depolar_rate=depolar_rate)
    alice = Node(
            "Alice", port_names=['qin_charlie', 'cout_bob'],
            qmemory=QuantumMemory("MemoriaAlice", num_positions=2,
                memory_noise_models=[modelo_ruido] * 2))
    alice.ports['qin_charlie'].forward_input(alice.qmemory.ports['qin1'])
    bob = Node(
            "Bob", port_names=['qin_charlie', 'cin_alice'],
            qmemory=QuantumMemory("MemoriaBob", num_positions=1,
                memory_noise_models=[modelo_ruido]))
    bob.ports['qin_charlie'].forward_input(bob.qmemory.ports['qin0'])
    # Configura conexão clássica entre os nós:
    con_c = ConexaoClassica(comprimento=node_distance)
    alice.ports['cout_bob'].connect(con_c.ports['A'])
    bob.ports['cin_alice'].connect(con_c.ports['B'])
    # Configura conexão emaranhada entre os nós:
    con_q = ConexaoEmaranhada(comprimento=node_distance, frequencia_fonte=2e7)
    alice.ports['qin_charlie'].connect(con_q.ports['A'])
    bob.ports['qin_charlie'].connect(con_q.ports['B'])
    return alice, bob, con_q, con_c

# Podemos testar parte da nossa rede checando que ao final de cada ciclo os qubits emaranhados
# chegaram a ambas as memórias quânticas

ns.set_qstate_formalism(ns.QFormalism.DM)
alice, bob, *_ = configura_rede_exemplo()
estatisticas = ns.sim_run(15)
qA, = alice.qmemory.peek(positions=[1])
qB, = bob.qmemory.peek(positions=[0])
print("Posição 1 da memória de Alice e Posição 0 da memória de Bob:")
print(qA, qB)
fidelidade = ns.qubits.fidelity([qA, qB], ns.b00)
print(f"Fidelidade de emaranhamento (após espera de 5ns) = {fidelidade:.3f}")
print(estatisticas)    
