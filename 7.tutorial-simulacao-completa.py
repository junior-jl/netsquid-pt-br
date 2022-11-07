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

# As conexões que usaremos entre os nós Alice e Bob são definidas similarmente à antes:

class ConexaoEmaranhada(Connection):
    def __init__(self, comprimento, frequencia_fonte, name="ConexaoEmaranhada"):
        super().__init__(name=name)
        fonteq = QSource(f"fonteq_{name}", StateSampler([ks.b00], [1.0]), num_ports=2,
                timing_model=FixedDelayModel(delay=1e9 / frequencia_fonte),
                status=SourceStatus.INTERNAL)
        self.add_subcomponent(fonteq, name="fonteq")
        canalq_cparaa = QuantumChannel("CanalQ_CparaA", length=comprimento / 2,
                models={"delay_model": FibreDelayModel()})
        canalq_cparab = QuantumChannel("CanalQ_CparaB", length=comprimento / 2,
                models={"delay_model": FibreDelayModel()})
        # Adiciona canais e encaminha a saída do canal quântico para porta externa de saída:
        self.add_subcomponent(canalq_cparaa, forward_output=[("A", "recv")])
        self.add_subcomponent(canalq_cparab, forward_output=[("B", "recv")])
        # Conecta a saída de fonteq à entrada do canal quântico
        fonteq.ports["qout0"].connect(canalq_cparaa.ports["send"])
        fonteq.ports["qout1"].connect(canalq_cparab.ports["send"])

class ConexaoClassica(Connection):
    def __init__(self, comprimento, name="ConexãoClássica"):
        super().__init__(name=name)
        self.add_subcomponent(ClassicalChannel("Canal_AparaB", length=comprimento,
            models={"delay_model": FibreDelayModel()}),
            forward_input=[("A", "send")],
            forward_output=[("B", "recv")]

# Os nós de Alice e Bob usam o mesmo processador quântico

def cria_processador
