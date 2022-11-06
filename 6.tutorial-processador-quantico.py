# Tutorial Netsquid - Processador Quântico

# Esta seção do tutorial é dedicada ao componente processador quântico (QuantumProcessor),
# uma subclasse de memória quântica (QuantumMemory) que modela a aplicação (imperfeita) de 
# portas quânticas e outras instruções aos qubits armazenados.

## Instruções para memórias quânticas

# Instruções (Instruction) representam comandos de baixo nível que rodam em uma memória
# quântica e suas sublcasses; em particular, o processador quântico que veremos em breve. O
# módulo netsquid.components.instructions define subclasses que podem ser usadas para criar
# instruções, como a classe IGate para criar instruções de portas quânticas. Além disso,
# também define um conjunto de objetos instrução, por exemplo:
#   - INSTR_INIT -> para inicializar qubits
#   - INSTR_MEASURE -> para medir um qubit
#   - INSTR_H -> para aplicar a porta de Hadamard em um qubit
#   etc...
# Instruções podem ser aplicadas a uma memória quântica usando instruções diretamente como
# objetos chamáveis com a memória quântica como o primeiro argumento:
import netsquid as ns
import netsquid.components.instructions as instr
from netsquid.components.qmemory import QuantumMemory

memoriaq = QuantumMemory("MemQExemplo", num_positions=1)
instr.INSTR_INIT(memoriaq, positions=[0])
instr.INSTR_H(memoriaq, positions=[0])
print("Medição no qubit na memória (posição 0)")
print(instr.INSTR_MEASURE_X(memoriaq, positions=[0]))

# Novas instruções podem ser criadas usando as subclasses base fornecidas, por exemplo, uma
# porta customizada pode ser instanciada como segue:

from netsquid.qubits import operators as ops
INSTR_XY = instr.IGate("porta_xy", ops.X * ops.Y)

# A classe base QuantumProcessor adiciona métodos especializados à QuantumMemory para lidar com
# instruções. Por exemplo, o método execute_instruction() pode ser usado para executar
# instruções, como mostrado abaixo para um circuito de emaranhamento:

from netsquid.components.qprocessor import QuantumProcessor
#       QuantumProcessor(name, [num_positions], [mem_noise_models], [phys_instructions],
#                        [fallback_to_nonphysical], [mem_pos_types], [properties])
# fallback_to_nonphysical -> se True, instruções que não corresponderem à uma instrução física
# serão executadas como instruções não-físicas
procq = QuantumProcessor("ExemploQPU", num_positions=3,
                         fallback_to_nonphysical=True)
procq.execute_instruction(instr.INSTR_INIT, [0, 1])
procq.execute_instruction(instr.INSTR_H, [1])
procq.execute_instruction(instr.INSTR_CNOT, [1, 0])
m1 = procq.execute_instruction(instr.INSTR_MEASURE, [0])
m2 = procq.execute_instruction(instr.INSTR_MEASURE, [1])
print("Medições nas posições 0 e 1 da memória")
print(m1, m2)
print("As medições foram iguais?")
print(m1 == m2) # Verifica se os resultados são iguais
ns.sim_time()

## Instruções físicas

# Instruções devem ser independentes da memória quântica ou do processador em que são executadas.
# Assim, instruções como as executadas acima são efetivamente não-físicas: elas são aplicadas 
# instantaneamente e sem erros. Para modelar a duração de uma instrução física e quaisquer erros
# associados a esta um processador quântico pode especificar um conjunto separado de instruções
# físicas (PhysicalInstruction) que executa instruções que podem ser mapeadas.

# Vamos considerar um exempo de como especificar instruções físicas a um processador quântico que 
# possui as seguintes características:

#   - Três posições de memória para qubits;
#   - Qubits em qualquer posição da memória experimentam ruído de despolarização quando inativos.;
#   - Inicialização de qubits em todas as posições da memória duram 3 nanossegundos;
#   - As portas unitárias Hadamard, X, Z e S podem ser aplicadas às posições de memória 0 e 2 e
#     levam 1 nanossegundo;
#   - A aplicação da porta CNOT dura 4 nanossegundos e só pode ter a posição 1 da memória como alvo;
#   - Todos os qubits podem ser medidos na base padrão (Z), o que leva 7 nanossegundos. Uma medição
#     da posição 1 sofre ruído de despolarização.

# Além disso, algumas instruções podem ser executadas em paralelo em diferentes qubits, isto é, a
# aplicação de uma porta X na posição 0 pode ocorrer simultaneamente à aplicação da porta H na 
# posição 2. Uma configuração que implementa as restrições acima é:

from netsquid.components.models.qerrormodels import DepolarNoiseModel
from netsquid.components.qprocessor import PhysicalInstruction

#       PhysicalInstruction(instruction, duration, [topology], [quantum_noise_model],
#                           [classical_noise_model], [parallel], [apply_q_noise_after], 
#                           **parameters)
instrucoes_fisicas = [
        PhysicalInstruction(instr.INSTR_INIT, duration=3),
        PhysicalInstruction(instr.INSTR_H, duration=1, parallel=True, topology=[0, 2]),
        PhysicalInstruction(instr.INSTR_CNOT, duration=4, parallel=True,
                            topology=[(0, 1), (2, 1)]),
        PhysicalInstruction(instr.INSTR_X, duration=1, parallel=True, topology=[0, 2]),
        PhysicalInstruction(instr.INSTR_Z, duration=1, parallel=True, topology=[0, 2]),
        PhysicalInstruction(instr.INSTR_S, duration=1, parallel=True, topology=[0, 2]),
        PhysicalInstruction(
            instr.INSTR_MEASURE, duration=7, parallel=False,
            quantum_noise_model=DepolarNoiseModel(depolar_rate=0.01, time_independent=True),
            apply_q_noise_after=False, topology=[1]),
        PhysicalInstruction(instr.INSTR_MEASURE, duration=7, parallel=True,
                            topology=[0, 2])
        ]
procq_ruidoso = QuantumProcessor("QPURuidosa", num_positions=3,
                                 mem_noise_models=[DepolarNoiseModel(1e7)] * 3,
                                 phys_instructions=instrucoes_fisicas)

# Para limitar a disponibilidade de instruções físicas para posições de memórias específicas,
# podemos especificar uma topologia. As instruções físicas com suas topologias são mostradas no 
# esquemático abaixo:
# https://docs.netsquid.org/latest-release/_images/QuantumProcessorSchematic.png

# A não ser que o processador quântico seja inicializado com fallback_to_nonphysical=True, irá
# gerar um erro quando não puder mapear a instrução para ser executada com uma instrução física.

# Pela configuração, se executarmos a instrução de inicialização de qubits na memória[0 e 1], é
# esperado que dure 3 nanossegundos:

print("Tempo de simulação antes de inicializar os qubits na memória [0 e 1]")
print(ns.sim_time())
procq_ruidoso.execute_instruction(instr.INSTR_INIT, [0, 1])
ns.sim_run()
print("Tempo após:")
print(ns.sim_time())

# No entanto, problemas aparecem quando tentamos executar o resto ddo nosso circuito de
# emaranhamento: tentar executar instruções sem que as anteriores tenham sido finalizadas
# irá gerar um erro indicando que o processador ainda está ocupado.

# Para evitar ter que chamar ns.sim_run() entre cada instrução, utilizamos programas quânticos
# para aplicar instruções sequencialmente, e até condicionalmente dependendo do resultado de
# instruções anteriores.

## Programas quânticos

# Processadores quânticos podem executar programas quânticos (QuantumProgram). Tais programas
# consistem de instruções que rodam em sequências. As instruções, por padrão, rodam em paralelo
# se o processador quântico e as instruções físicas suportam isto. Além do mais, um programa 
# também suporta lógica de controle. Similar à instruções, um programa é independente ao tipo de 
# processador quântico no qual está rodando. Os índices de qubits referidos em um programa são
# mapeados para as posições da memória em um PQ quando o programa é executado, o qual também 
# mapeia as instruções abstratas paraa as instruções físicas disponíveis. 

# Por exemplo, em sua forma mais básica, um programa pode ser criado como uma sequência de
# instruções:

from netsquid.components.qprogram import QuantumProgram

prog = QuantumProgram(num_qubits=2)
q1, q2 = prog.get_qubit_indices(2) # Pega os índices dos qubits que iremos trabalhar
prog.apply(instr.INSTR_INIT, [q1, q2])
prog.apply(instr.INSTR_H, q1)
prog.apply(instr.INSTR_CNOT, [q1, q2])
prog.apply(instr.INSTR_MEASURE, q1, output_key="m1")
prog.apply(instr.INSTR_MEASURE, q2, output_key="m2")

# Agora, pode ser executado no processador (usando o mesmo processador ruidoso criado acima):

procq_ruidoso.reset()
ns.sim_reset()
procq_ruidoso.execute_program(prog, qubit_mapping = [2, 1])
ns.sim_run()
print(f'Tempo: {ns.sim_time()}')
print('As duas medições foram iguais?')
print(prog.output['m1'] == prog.output['m2'])
print('Medições:')
print(prog.output["m1"], prog.output["m2"])

# Tal sequência de instruções também pode ser criada usando uma subclasse de QuantumProgram:

class ProgramaEmaranhar(QuantumProgram):
    num_qubits_padrao = 2
    # Necessariamente deve ser chamado program
    def program(self):
        q1, q2 = self.get_qubit_indices(2)
        self.apply(instr.INSTR_INIT, [q1, q2])
        self.apply(instr.INSTR_H, q1)
        self.apply(instr.INSTR_CNOT, [q1, q2])
        self.apply(instr.INSTR_MEASURE, q1, output_key="m1")
        self.apply(instr.INSTR_MEASURE, q2, output_key="m2")
        yield self.run()

# Este programa pode ser executado em múltiplos processadores, desde que suportem as instruções.
# Dependendo do processador, o tempo e ruído aplicados podem ser diferentes.

# Múltiplicas sequências são definidas usando repetidas declarações yield chamando o método run().
# Durante o run(), as instruções guardam suas saídas em um dicionário chamado output (saída). Por
# exemplo, aqui, os resultados das medições são armazenados em output['m1'] e output['m2'].
# A lógica de controle pode ser usada para selecionar quais instruções serão chamadas.

class ProgramaQControlado(QuantumProgram):
    num_qubits_padrao = 3

    def program(self):
        q1, q2, q3 = self.get_qubit_indices(3)
        self.apply(instr.INSTR_H, q1)
        self.apply(instr.INSTR_MEASURE, q1, output_key='m1')
        yield self.run()
        # Dependendo da saída de q1, ocorre um flip em q2 ou em q3
        if self.output['m1'][0] == 0:
            self.apply(instr.INSTR_X, q2)
        else:
            self.apply(instr.INSTR_X, q3)
        self.apply(instr.INSTR_MEASURE, q2, output_key='m2')
        self.apply(instr.INSTR_MEASURE, q3, output_key='m3')
        yield self.run(parallel=False)

# O parâmetro parallel no método run() pode ser usado para controlar se o processador irá tentar
# rodar as sequências em paralelo. Para fazer isso, tanto as PhysicalInstruction correspondentes
# e o processador devem suportar isto.

## Exemplo de teleporte local usando programas

# Vamos usar programa para realizar um teleporte local entre os qubits em um único processador
# quântico com instruções físicas imperfeitas, i.e., teleportar o estado de um qubit na posição 0
# da memória para a posição 2.

# Primeiro, os qubits 1 e 2 precisam ser emaranhados. Isto é feito em paralelo à criação do estado
# a ser teleportado. Uma medição de Bell é realizada no qubit 0 e 1 assim que os 3 qubits estão
# prontos. Os resultados da medição precisam ser conhecidos antes da realização das operações de
# correção. Assim, o programa precisa rodar antes da correção ser realizada.

procq_ruidoso.reset()
ns.sim_reset()
ns.set_qstate_formalism(ns.QFormalism.DM)

class ProgramaTeleporte(QuantumProgram):
    num_qubits_padrao = 3

    def program(self):
        q0, q1, q2 = self.get_qubit_indices(3)
        # Emaranha q1 e q2:
        self.apply(instr.INSTR_INIT, [q0, q1, q2])
        self.apply(instr.INSTR_H, q2)
        self.apply(instr.INSTR_CNOT, [q2, q1])
        # Coloca q0 no estado desejado para ser teleportado:
        self.apply(instr.INSTR_H, q0)
        self.apply(instr.INSTR_S, q0)
        # Medição de Bell:
        self.apply(instr.INSTR_CNOT, [q0, q1])
        self.apply(instr.INSTR_H, q0)
        self.apply(instr.INSTR_MEASURE, q0, output_key="M1")
        self.apply(instr.INSTR_MEASURE, q1, output_key="M2")
        yield self.run()
        # Aplica correções:
        if self.output["M2"][0] == 1:
            self.apply(instr.INSTR_X, q2)
        if self.output["M1"][0] == 1:
            self.apply(instr.INSTR_Z, q2)
        yield self.run()

procq_ruidoso.execute_program(ProgramaTeleporte())
ns.sim_run()
qubit = procq_ruidoso.pop(2)
print(qubit)
fidelidade = ns.qubits.fidelity(
        qubit, ns.qubits.outerprod((ns.S*ns.H*ns.s0).arr), squared=True)
print(f"Fidelidade: {fidelidade:.3f}")

## Características adicionais

# O parâmetro physical (físico) pode ser usado para indicar se um processador quântico deve
# corresponder a instrução a uma PhysicalInstruction ou executá-la instantaneamente sem ruído, i.e.,
# não físico.

class ProgramaQCheating(QuantumProgram):
    num_qubits_padrao = 2

    def program(self):
        q1, q2 = self.get_qubit_indices(2)
        self.apply(instr.INSTR_X, q1)
        self.apply(instr.INSTR_SIGNAL, physical=False)
        self.apply(instr.INSTR_Z, q1, physical=False)
        self.apply(instr.INSTR_CNOT, [q1, q2])
        self.apply(instr.INSTR_MEASURE, q1, output_key="m1", physical=False)
        self.apply(instr.INSTR_MEASURE, q2, output_key="m2", physical=False)
        yield self.run()

# Um programa também pode carregar em outro programa usando o método load(). Programas carregados
# compartilham o mesmo dicionário de saída.

class ProgramaQCarregando(QuantumProgram):
    num_qubits_padrao = 2

    def program(self):
        # Roda uma sequência comum
        q1, q2 = self.get_qubit_indices(2)
        self.apply(instr.INSTR_X, q1)
        yield self.run()
        # Carrega e roda outro programa
        yield from self.load(ProgramaQCheating)

# Além disso, programas podem ser concatenados com o operador de adição:
# prog3 = prog1 + prog2
# E ainda, programas podem ser repetidos usando o operador de multiplicação:
# prog2 = prog1 * 5
# Em todos os casos, o dicionário de saída é compartilhado por todos os programas combinados.


