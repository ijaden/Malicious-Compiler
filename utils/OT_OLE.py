import random
from GR import GaloisRingElement
from Party import *


class SimulatedOT:

    def __init__(self, party: Party):
        self.party = party

    def send_batch(self, receiver_id, messages_list, round_id):
        payload = []
        for m0, m1 in messages_list:
            payload.append((m0.to_string(), m1.to_string()))

        self.party.send_private(receiver_id, {'t': 'OT_BATCH', 'd': payload}, round_id)

    def receive_batch(self, sender_id, choice_bits, round_id):

        while True:
            msgs = self.party.receive_round(round_id)
            if sender_id in msgs and isinstance(msgs[sender_id], dict) and msgs[sender_id].get('t') == 'OT_BATCH':
                raw_data = msgs[sender_id]['d']
                break

        if len(raw_data) != len(choice_bits):
            raise ValueError(f"OT Size Mismatch: expected {len(choice_bits)}, got {len(raw_data)}")

        results = []
        for (s0, s1), bit in zip(raw_data, choice_bits):
            chosen_str = s1 if bit == 1 else s0
            results.append(GaloisRingElement.from_string(chosen_str))

        return results


class GilboaOLE:

    def __init__(self, party: Party):
        self.party = party
        self.ot = SimulatedOT(party)
        self.K = 64

    def _get_scalar_gr(self, val):
        coeffs = [0] * 64
        coeffs[0] = val
        return GaloisRingElement(coeffs)

    def run_sender(self, receiver_id, x_val: GaloisRingElement, round_id) -> GaloisRingElement:
        u_list = []
        ot_pairs = []


        for i in range(self.K):
            u = GaloisRingElement.random()
            u_list.append(u)
            factor = self._get_scalar_gr(1 << i)
            shift_val = x_val * factor

            m0 = u
            m1 = u + shift_val

            ot_pairs.append((m0, m1))


        self.ot.send_batch(receiver_id, ot_pairs, round_id)

        Q = GaloisRingElement([0] * 64)
        for u in u_list:
            Q = Q - u

        return Q

    def run_receiver(self, sender_id, delta_val: GaloisRingElement, round_id) -> GaloisRingElement:

        delta_scalar = delta_val.coeffs[0]
        choice_bits = []
        for i in range(self.K):
            bit = (delta_scalar >> i) & 1
            choice_bits.append(bit)

        t_shares = self.ot.receive_batch(sender_id, choice_bits, round_id)

        T = GaloisRingElement([0] * 64)
        for t in t_shares:
            T = T + t

        return T