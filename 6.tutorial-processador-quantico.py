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
# para aplicar instruções sequencialmente, e até condicionalmente dependendo ddo resultado de
# instruções anteriores.
