from typing import Sequence
from bfcl.bfcl import operation, op, gate, circuit
from circuitry import *
"""
operation:
operation.token_op_pairs = [
    ('LID', operation((0, 1))),
    ('INV', operation((1, 0))),
    ('FLS', operation((0, 0, 0, 0))),
    ('AND', operation((0, 0, 0, 1))),
    ('NIM', operation((0, 0, 1, 0))),
    ('FST', operation((0, 0, 1, 1))),
    ('NIF', operation((0, 1, 0, 0))),
    ('SND', operation((0, 1, 0, 1))),
    ('XOR', operation((0, 1, 1, 0))),
    ('LOR', operation((0, 1, 1, 1))),
    ('NOR', operation((1, 0, 0, 0))),
    ('XNR', operation((1, 0, 0, 1))),
    ('NSD', operation((1, 0, 1, 0))),
    ('LIF', operation((1, 0, 1, 1))),
    ('NFT', operation((1, 1, 0, 0))),
    ('IMP', operation((1, 1, 0, 1))),
    ('NND', operation((1, 1, 1, 0))),
    ('TRU', operation((1, 1, 1, 1)))
]
"""


class Gate():
    #from Bristol Fashion file
    # gate_ID,[Number input wires, Number output wires,List of input wires, List of output wires,Gate operation ]
    # 2 1 3 4 5 XOR
    input = []
    output = 0
    is_input: bool = False,
    is_output: bool = False
    def __init__(self, id, BF):

        self.id_num = id
        self.num_input = int(BF[0])
        self.num_output = int(BF[1])
        self.gate_type = BF[-1]
        self.input_wires = []
        self.output_wires = []
        for i in range(0,int(self.num_input)):
            self.input_wires.append(int(BF[2+i]))
        for i in range(0,int(self.num_output)):
            self.output_wires.append(int(BF[-2-i]))
    def toString(self) -> str:
        """
        Emit a Bristol Fashion string for this gate.
        """
        return " ".join([
            str(self.num_input), str(self.num_output),
            " ".join([str(i) for i in self.input_wires]),
            " ".join([str(i) for i in self.output_wires]),
            self.gate_type
        ])



class Circuit():
    c1:circuit
    def __init__(self,name,FromFile=True):
        if FromFile == True:
            self.filename = '/home/jaden/workspace/mpcSok/Benchmark/circuits/%s.txt' %(name)
            self.gates = []
            self.circuit_str = []
            self.wire_num = 0
            self.gate_num=0

            #The below is for the Arithmetic circuits
            self.wire_output_num =0
            self.wire_input_num = 0
            with open(self.filename, 'r') as f:
                i=0
                for line in f:
                    line = line.strip()
                    if line:
                        self.circuit_str.append(line)
                    if i >=4 and line:
                        self.gates.append(Gate(i,line.strip().split()))
                        self.circuit_str.append(line)
                    i = i + 1

            self.c1 = circuit("\n".join(self.circuit_str))
            self.gate_num,self.wire_num= int(self.circuit_str[0].split()[0]),int(self.circuit_str[0].split()[1])
            self.wire_input_num = int(self.circuit_str[1].split()[0])
            self.wire_output_num = int(self.circuit_str[2].split()[0])

        else:
            #for code test
            self.c1 = circuit(name)
    def toString(self):
        return self.circuit_str
    def evaluate(self,inputs:Sequence[Sequence[int]], Mod=2)-> Sequence[Sequence[int]]:
        if Mod == 2:
            # remain to do
            return self.c1.evaluate(inputs)

        else:
            inputs = [b for bs in inputs for b in bs]
            if len(inputs) != self.wire_input_num:
                raise ValueError('The input value is inconsistent with the circuit gate.')
            wire = inputs + [0] * (int(self.wire_num) - len(inputs))
            # If no output wire index is present, use the gate count as the index.
            for g in self.gates:
                re =0 + int(g.gate_type =="MUL")
                for i in range(0,g.num_input):
                    if g.gate_type == "ADD":
                        re = (re + wire[g.input_wires[i]]) % Mod
                    elif g.gate_type =="MUL":
                        re = (re * wire[g.input_wires[i]]) % Mod
                for o in range(0,g.num_output):
                    # print(re)
                    wire[g.output_wires[o]] = re
            return wire[-self.wire_output_num:]
            # return wire



if __name__ == "__main__":
    # s = ['7 36', '2 4 4', '1 1']
    # s.extend(['2 1 0 1 15 AND', '2 1 2 3 16 AND'])
    # s.extend(['2 1 15 16 8 AND', '2 1 4 5 22 AND'])
    # s.extend(['2 1 6 7 23 AND', '2 1 22 23 9 AND'])
    # s.extend(['2 1 8 9 35 AND'])
    # c = Circuit("\n".join(s),False)
    # print(c.evaluate([[1, 0, 1, 1], [1, 1, 1, 0]]))

    c = Circuit("Arithmetic/Adder")
    a = [1,1,1,1]
    b = [1,1,1,1]
    print(c.toString())
    print(c.evaluate([a,b],Mod=10000000))