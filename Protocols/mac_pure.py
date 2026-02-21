import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)
from Network.Party import *
from Datetype.GR import *

class AuthenticatedShare:
    def __init__(self, val_share: GaloisRingElement, mac_share: GaloisRingElement):
        self.val = val_share
        self.mac = mac_share

    def __add__(self, other):
        return AuthenticatedShare(self.val + other.val, self.mac + other.mac)

    def __sub__(self, other):
        return AuthenticatedShare(self.val - other.val, self.mac - other.mac)

    def scalar_mul(self, scalar: GaloisRingElement):
        return AuthenticatedShare(self.val * scalar, self.mac * scalar)

    def __repr__(self):
        return f"<AuthShare val={self.val.coeffs[0]}...>"


class VOLEProtocol:
    def __init__(self, node_id):
        self.party = Party(node_id)
        self.round_counter = 0
        self.alpha_share = None
        self.party.barrier()

    def _next_round(self):
        self.round_counter += 1
        return self.round_counter

    def generate_key(self):
        print(f"[{self.party.node_id}] Generating Global Key Share...")
        self.alpha_share = GaloisRingElement.random()

    def commit(self, value: GaloisRingElement = None, src_id=0) -> AuthenticatedShare:
        rid = self._next_round()


        if self.party.node_id != src_id:
            payload = {
                't': 'DATA',
                'r': rid,
                'src': self.party.node_id,
                'val': self.alpha_share.to_string()
            }
            self.party._send_packet(src_id, payload)

        global_alpha = None
        if self.party.node_id == src_id:
            global_alpha = self.alpha_share

            received_alphas = self.party.receive_round(rid)

            for pid, val_str in received_alphas.items():
                part_alpha = GaloisRingElement.from_string(val_str)
                global_alpha = global_alpha + part_alpha

        rid = self._next_round()

        if self.party.node_id == src_id:
            val_shares = {}
            running_val_sum = GaloisRingElement([0] * 64)
            for pid in self.party.peers:
                s = GaloisRingElement.random()
                val_shares[pid] = s
                running_val_sum = running_val_sum + s
            my_val_share = value - running_val_sum
            val_shares[self.party.node_id] = my_val_share
            global_mac = global_alpha * value
            mac_shares = {}
            running_mac_sum = GaloisRingElement([0] * 64)
            for pid in self.party.peers:
                s = GaloisRingElement.random()
                mac_shares[pid] = s
                running_mac_sum = running_mac_sum + s
            my_mac_share = global_mac - running_mac_sum
            mac_shares[self.party.node_id] = my_mac_share


            dist_payload = {}
            for pid in NODE_MAP:
                dist_payload[str(pid)] = {
                    'v': val_shares[pid].to_string(),
                    'm': mac_shares[pid].to_string()
                }

            self.party.broadcast(dist_payload, rid)
            return AuthenticatedShare(my_val_share, my_mac_share)

        else:

            incoming = self.party.receive_round(rid, expected_senders=[src_id])

            src_data = incoming[src_id]
            my_data = src_data[str(self.party.node_id)]
            v_share = GaloisRingElement.from_string(my_data['v'])
            m_share = GaloisRingElement.from_string(my_data['m'])

            return AuthenticatedShare(v_share, m_share)

    def open_and_verify(self, share: AuthenticatedShare):
        print(f"[{self.party.node_id}] Opening value...")
        rid = self._next_round()


        self.party.broadcast(share.val.to_string(), rid)
        shares_map = self.party.receive_round(rid)

        reconstructed_val = share.val
        for pid, val_str in shares_map.items():
            reconstructed_val = reconstructed_val + GaloisRingElement.from_string(val_str)

        print(f"[{self.party.node_id}] Value reconstructed. Verifying MAC...")

        term = self.alpha_share * reconstructed_val
        delta_i = share.mac - term

        rid = self._next_round()
        self.party.broadcast(delta_i.to_string(), rid)

        deltas_map = self.party.receive_round(rid)

        total_delta = delta_i
        for pid, d_str in deltas_map.items():
            total_delta = total_delta + GaloisRingElement.from_string(d_str)

        is_valid = all(c == 0 for c in total_delta.coeffs)

        if is_valid:
            print(f"[{self.party.node_id}] MAC Check: PASS.")
            return reconstructed_val
        else:
            raise ValueError(f"[{self.party.node_id}] MAC Check: FAILED!")

def run_test(pid):

    print(f"[{pid}] Initializing Party...")
    vole = VOLEProtocol(pid)


    vole.generate_key()


    my_secret_val = (pid + 1) * 10

    all_shares = []

    TOTAL_NODES = 4

    for src_id in range(TOTAL_NODES):
        print(f"\n[{pid}] --- Round {src_id}: Node {src_id} is committing ---")

        if pid == src_id:

            coeffs = [0] * 64
            coeffs[0] = my_secret_val
            secret_element = GaloisRingElement(coeffs)

            print(f"[{pid}] I am committing value: {my_secret_val}")
            share = vole.commit(value=secret_element, src_id=src_id)
        else:
            print(f"[{pid}] Waiting for Node {src_id} to commit...")
            share = vole.commit(value=None, src_id=src_id)

        all_shares.append(share)

    print(f"\n[{pid}] All commitments received. Total shares: {len(all_shares)}")


    print(f"[{pid}] Computing sum of all shares locally...")

    sum_share = all_shares[0]
    for i in range(1, len(all_shares)):
        sum_share = sum_share + all_shares[i]

    print(f"[{pid}] Opening and Verifying result...")

    try:

        result_element = vole.open_and_verify(sum_share)

        result_int = result_element.coeffs[0]
        print(f"[{pid}] \033[92mSUCCESS\033[0m: Verified Result = {result_int}")


        expected_sum = sum([(i + 1) * 10 for i in range(TOTAL_NODES)])

        if result_int == expected_sum:
            print(f"[{pid}] \033[92mCHECK PASS\033[0m: {result_int} == {expected_sum}")
        else:
            print(f"[{pid}] \033[91mCHECK FAIL\033[0m: {result_int} != {expected_sum}")

    except Exception as e:
        print(f"[{pid}] \033[91mFAILED\033[0m: Verification error - {e}")

def test():
    if len(sys.argv) < 2:
        print("Usage: python test_all_commit.py <node_id>")
        sys.exit(1)
    node_id = int(sys.argv[1])
    run_test(node_id)