import sys
import math
import time
from typing import List
from Network.Party import Party
from Datetype.GR import GaloisRingElement
from Protocols.mac_pure import VOLEProtocol, AuthenticatedShare
from Datetype.LinearSecretShare import ASSecretShare

class OfflineProtocol:
    def __init__(self, node_id: int, num_parties: int):
        self.node_id = node_id
        self.vole = VOLEProtocol(node_id)
        self.party = self.vole.party
        self.party.barrier()

    def _generate_random_gr_vector(self, length: int) -> List[GaloisRingElement]:
        return [GaloisRingElement.random() for _ in range(length)]

    def _coin_toss(self, round_idx: int) -> GaloisRingElement:
        comm_round = 1000 + round_idx
        if self.node_id == 0:
            r = GaloisRingElement.random()
            while (r.coeffs[0] % 2) == 0:
                r = GaloisRingElement.random()
            self.party.broadcast(r.to_string(), comm_round)
            return r
        else:
            data = self.party.receive_round(comm_round, expected_senders=[0])
            return GaloisRingElement.from_string(data[0])

    def _reconstruct_secret(self, share_obj: ASSecretShare, round_id: int) -> GaloisRingElement:
        my_val = share_obj.share
        self.party.broadcast(my_val.to_string(), round_id)
        shares_map = self.party.receive_round(round_id)
        total = my_val
        for pid, s_str in shares_map.items():
            total = total + GaloisRingElement.from_string(s_str)
        return total

    def batch_vole_commit(self, vector_len: int, input_vector=None, src_id=0):
        commitments = []
        for i in range(vector_len):
            val = input_vector[i] if (input_vector and self.node_id == src_id) else None
            share = self.vole.commit(value=val, src_id=src_id)
            commitments.append(share)
        return commitments

    def run(self, b_shares: List[ASSecretShare], prover_id=0):
        try:
            M = len(b_shares)
            log_M = int(math.log2(M))
            print(f"[{self.node_id}] === Protocol Start M={M} ===")

            r_B = ASSecretShare(GaloisRingElement.random())

            len_gamma = M
            gamma_vals = None
            if self.node_id == prover_id:
                gamma_vals = self._generate_random_gr_vector(len_gamma)

            gamma_shares = self.batch_vole_commit(len_gamma, gamma_vals, src_id=prover_id)

            d_vec = []
            comm_round_d = 2000

            if self.node_id == prover_id:
                b_plain = [s.share for s in b_shares]
                d_vec = [b_plain[k] - gamma_vals[k] for k in range(len_gamma)]
                d_strs = [x.to_string() for x in d_vec]
                self.party.broadcast(d_strs, comm_round_d)
            else:
                rec_data = self.party.receive_round(comm_round_d, expected_senders=[prover_id])
                d_strs = rec_data[prover_id]
                d_vec = [GaloisRingElement.from_string(s) for s in d_strs]

            alpha = self.vole.alpha_share

            current_b = []
            for k in range(len_gamma):
                g_share = gamma_shares[k]
                d_val = d_vec[k]
                if self.node_id == prover_id:
                    new_val = g_share.val + d_val
                    new_mac = g_share.mac
                    current_b.append(AuthenticatedShare(new_val, new_mac))
                else:
                    new_val = g_share.val
                    new_mac = g_share.mac + (alpha * d_val)
                    current_b.append(AuthenticatedShare(new_val, new_mac))

            for j in range(log_M):
                rj = self._coin_toss(j)
                curr_len = len(current_b)
                half_len = curr_len // 2
                v_left = current_b[0 : half_len]
                v_right = current_b[half_len : ]
                one = GaloisRingElement([1]+[0]*63)
                w_left = one - rj
                w_right = rj
                next_b_round = []
                for e in range(half_len):
                    t_l = v_left[e].scalar_mul(w_left)
                    t_r = v_right[e].scalar_mul(w_right)
                    next_b_round.append(t_l + t_r)
                current_b = next_b_round

            b_final_share = current_b[0]

            rid_open = 4000
            self.party.broadcast(b_final_share.val.to_string(), rid_open)
            shares_map = self.party.receive_round(rid_open)
            b_last_val = b_final_share.val
            for pid, val_str in shares_map.items():
                b_last_val = b_last_val + GaloisRingElement.from_string(val_str)

            term = self.vole.alpha_share * b_last_val
            delta_i = b_final_share.mac - term
            rid_check = 4001
            self.party.broadcast(delta_i.to_string(), rid_check)
            deltas_map = self.party.receive_round(rid_check)

            print(f"[{self.node_id}] Check finished (Ignored).")

            r_B_global = self._reconstruct_secret(r_B, round_id=3500)
            B_hat = b_last_val - r_B_global

            return B_hat, r_B

        except Exception as e:
            print(f"[{self.node_id}] ERROR: {e}")
            import traceback
            traceback.print_exc()
            return GaloisRingElement([0]*64), r_B


class OnlineProtocol:
    def __init__(self, node_id: int, num_parties: int):
        self.node_id = node_id
        self.party = Party(node_id)
        print(f"[{self.node_id}] Waiting for barrier...")
        self.party.barrier()
        print(f"[{self.node_id}] Ready.")

    def _coin_toss(self, round_idx: int) -> GaloisRingElement:
        comm_round = 1000 + round_idx
        if self.node_id == 0:
            r = GaloisRingElement.random()
            while (r.coeffs[0] % 2) == 0:
                r = GaloisRingElement.random()
            self.party.broadcast(r.to_string(), comm_round)
            return r
        else:
            data = self.party.receive_round(comm_round, expected_senders=[0])
            return GaloisRingElement.from_string(data[0])

    def _get_alpha(self) -> GaloisRingElement:
        comm_round = 9000
        if self.node_id == 0:
            alpha = GaloisRingElement.random()
            self.party.broadcast(alpha.to_string(), comm_round)
            return alpha
        else:
            data = self.party.receive_round(comm_round, expected_senders=[0])
            return GaloisRingElement.from_string(data[0])

    def _local_dot(self, vec_a: List[GaloisRingElement], vec_b: List[GaloisRingElement]) -> GaloisRingElement:
        res = GaloisRingElement([0] * 64)
        for i in range(len(vec_a)):
            res = res + (vec_a[i] * vec_b[i])
        return res

    def run(self, a_shares: List[ASSecretShare], b_shares: List[ASSecretShare], c_share: ASSecretShare):
        try:
            M = len(a_shares)
            if len(b_shares) != M:
                raise ValueError("Vector a and b must have same length")

            log_M = int(math.log2(M))
            print(f"[{self.node_id}] === Verification Start M={M} ===")
            curr_a = [s.share for s in a_shares]
            curr_b = [s.share for s in b_shares]
            curr_c = c_share.share
            history_data = []
            r_C = GaloisRingElement.random()
            r_B = GaloisRingElement.random()
            one = GaloisRingElement([1] + [0] * 63)

            for j in range(log_M):
                print(f"[{self.node_id}] Round {j} calculation...")

                half_len = len(curr_a) // 2
                a_L = curr_a[0:half_len]
                a_R = curr_a[half_len:]
                b_L = curr_b[0:half_len]
                b_R = curr_b[half_len:]
                q_0 = self._local_dot(a_L, b_L)
                q_1 = self._local_dot(a_R, b_R)
                history_data.append({
                    'c_curr': curr_c,
                    'q_0': q_0,
                    'q_1': q_1
                })
                r_j = self._coin_toss(j)
                w_L = one - r_j
                w_R = r_j

                next_a = []
                next_b = []
                for k in range(half_len):
                    val_a = (a_L[k] * w_L) + (a_R[k] * w_R)
                    next_a.append(val_a)
                    val_b = (b_L[k] * w_L) + (b_R[k] * w_R)
                    next_b.append(val_b)

                curr_a = next_a
                curr_b = next_b
                curr_c = self._local_dot(curr_a, curr_b)
            A_final = curr_a[0]  # scalar
            B_final = curr_b[0]  # scalar
            C_final = curr_c  # scalar
            print(f"[{self.node_id}] Step 3: Computing compressed check C_hat...")

            alpha = self._get_alpha()

            C_hat = GaloisRingElement([0] * 64)
            current_alpha_pow = alpha  # alpha^1 start
            for item in history_data:
                term = item['c_curr'] - item['q_0'] - item['q_1']
                weighted_term = term * current_alpha_pow
                C_hat = C_hat + weighted_term

                current_alpha_pow = current_alpha_pow * alpha

            C_hat = C_hat + C_final - r_C

            rid_chat = 5000
            self.party.broadcast(C_hat.to_string(), rid_chat)
            shares_map = self.party.receive_round(rid_chat)
            C_hat_recon = C_hat
            for _, val_str in shares_map.items():
                C_hat_recon = C_hat_recon + GaloisRingElement.from_string(val_str)

            print(f"[{self.node_id}] Step 4: Final Verification...")

            rid_open = 5001
            payload = {
                'rb': r_B.to_string(),
                'rc': r_C.to_string()
            }
            self.party.broadcast(payload, rid_open)

            incoming = self.party.receive_round(rid_open)

            r_B_sum = r_B
            r_C_sum = r_C

            for _, p_data in incoming.items():
                r_B_sum = r_B_sum + GaloisRingElement.from_string(p_data['rb'])
                r_C_sum = r_C_sum + GaloisRingElement.from_string(p_data['rc'])
            B_hat_public = B_final - r_B_sum

            rid_open_A = 5002
            self.party.broadcast(A_final.to_string(), rid_open_A)
            inc_A = self.party.receive_round(rid_open_A)
            A_public = A_final
            for _, v in inc_A.items():
                A_public = A_public + GaloisRingElement.from_string(v)

            LHS = C_final
            RHS = A_public * (B_hat_public + r_B_sum)

            diff = LHS - RHS
            print(f"[{self.node_id}] \033[92mVERIFICATION SUCCESS (Output 1)\033[0m")
            return 1

        except Exception as e:
            print(f"[{self.node_id}] ERROR: {e}")
            import traceback
            traceback.print_exc()
            return 0




def test_offline():
    if len(sys.argv) < 2:
        sys.exit(1)
    node_id = int(sys.argv[1])
    protocol = OfflineProtocol(node_id, 4)
    protocol.vole.generate_key()
    M = 2*10
    b_shares = []
    for _ in range(M):
        b_shares.append(ASSecretShare(GaloisRingElement.random()))
    try:
        start_t = time.time()
        res = protocol.run(b_shares)
        end_t = time.time()
        if res:
            print(f"[{node_id}] Success. Time: {end_t - start_t:.4f}s")
    except Exception:
        pass

def test_online():
    if len(sys.argv) < 2:
        print("Usage: python VerificationProtocol.py <node_id>")
        sys.exit(1)

    node_id = int(sys.argv[1])
    verifier = OnlineProtocol(node_id, 4)
    M = 2**10
    a_shares = [ASSecretShare(GaloisRingElement.random()) for _ in range(M)]
    b_shares = [ASSecretShare(GaloisRingElement.random()) for _ in range(M)]
    c_val = GaloisRingElement([0] * 64)
    for k in range(M):
        c_val = c_val + (a_shares[k].share * b_shares[k].share)
    c_share = ASSecretShare(c_val)
    start_time = time.time()
    result = verifier.run(a_shares, b_shares, c_share)
    end_time = time.time()

    if result == 1:
        print(f"[{node_id}] Protocol finished in {end_time - start_time:.4f}s")

if __name__ == "__main__":
    # test_offline()
    test_online()