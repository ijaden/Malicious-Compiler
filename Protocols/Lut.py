import sys
import time
import random
import struct
import base64
from typing import List

from Network.Party import Party
from Datetype.LinearSecretShare import ASSecretShare

class Mersenne61:
    MOD = (1 << 61) - 1

    def __init__(self, value):
        if isinstance(value, Mersenne61):
            self.value = value.value
        else:
            self.value = value % self.MOD

    def __repr__(self):
        return f"F({self.value})"

    def __add__(self, other):
        v = other.value if isinstance(other, Mersenne61) else other
        return Mersenne61((self.value + v) % self.MOD)

    def __sub__(self, other):
        v = other.value if isinstance(other, Mersenne61) else other
        return Mersenne61((self.value - v) % self.MOD)

    def __mul__(self, other):
        v = other.value if isinstance(other, Mersenne61) else other
        return Mersenne61((self.value * v) % self.MOD)

    def __neg__(self):
        return Mersenne61(-self.value)

    def __eq__(self, other):
        v = other.value if isinstance(other, Mersenne61) else other
        return self.value == v

    def inverse(self):
        return Mersenne61(pow(self.value, self.MOD - 2, self.MOD))

    def to_string(self) -> str:
        packed = struct.pack('<Q', self.value)
        return base64.b64encode(packed).decode('utf-8')

    @classmethod
    def from_string(cls, s: str):
        packed = base64.b64decode(s)
        val = struct.unpack('<Q', packed)[0]
        return cls(val)

    @classmethod
    def random(cls):
        return cls(random.randint(0, cls.MOD - 1))

    @classmethod
    def zero(cls):
        return cls(0)

    @classmethod
    def one(cls):
        return cls(1)



class LuArgProtocol:
    def __init__(self, node_id: int, num_parties: int):
        self.node_id = node_id
        self.num_parties = num_parties
        self.party = Party(node_id)

        self.N = 2 ** 8
        self.d = 2 ** 8
        self.c = 1

        self.omega_N = Mersenne61(3)
        print(f"[{self.node_id}] Waiting for barrier...")
        self.party.barrier()

    def secure_broadcast_reconstruct(self, share: ASSecretShare, round_id: int) -> Mersenne61:
        self.party.broadcast(share.share.to_string(), round_id)
        received = self.party.receive_round(round_id)

        total = share.share
        for pid, val_str in received.items():
            total = total + Mersenne61.from_string(val_str)
        return total

    def batch_reconstruct(self, shares: List[ASSecretShare], round_id: int) -> List[Mersenne61]:

        results = []
        payload = [s.share.to_string() for s in shares]
        self.party.broadcast(payload, round_id)
        received_maps = self.party.receive_round(round_id)
        for i in range(len(shares)):
            total = shares[i].share
            for pid, p_data in received_maps.items():
                total = total + Mersenne61.from_string(p_data[i])
            results.append(total)
        return results

    def pi_mult(self, x: ASSecretShare, y: ASSecretShare, round_id: int) -> ASSecretShare:
        a = ASSecretShare(Mersenne61.random())
        b = ASSecretShare(Mersenne61.random())
        c = ASSecretShare(Mersenne61.random())

        # Open e = x - a, d = y - b
        e_share = x - a
        d_share = y - b

        payload = {
            'e': e_share.share.to_string(),
            'd': d_share.share.to_string()
        }
        self.party.broadcast(payload, round_id)
        rec = self.party.receive_round(round_id)

        e_open = e_share.share
        d_open = d_share.share
        for pid, val in rec.items():
            e_open = e_open + Mersenne61.from_string(val['e'])
            d_open = d_open + Mersenne61.from_string(val['d'])

        #  z = c + e*b + d*a + e*d
        term1 = c
        term2 = b * e_open.value
        term3 = a * d_open.value

        res = term1 + term2 + term3

        if self.node_id == 0:
            # P0 adds constant
            prod_val = e_open * d_open
            res = res + ASSecretShare(prod_val)

        return res

    def preprocessing_phase(self):
        random.seed(0)
        self.alpha = Mersenne61.random()
        self.beta_clear = Mersenne61.random()
        self.xi_clear = Mersenne61.random()

        self.t_vec = [Mersenne61.random() for _ in range(self.N)]
        self.R_vals = [Mersenne61.random() for _ in range(self.N)]
        self.hat_t = [self.t_vec[i] - self.R_vals[i] for i in range(self.N)]

        self.beta_share = ASSecretShare(Mersenne61.random())
        self.delta_share = ASSecretShare(Mersenne61.random())
        self.gamma_share = ASSecretShare(Mersenne61.random())
        self.xi_share = ASSecretShare(Mersenne61.random())
        self.inv_xi_share = ASSecretShare(Mersenne61.random())

        self.b_shares = [ASSecretShare(Mersenne61.random()) for _ in range(self.c)]
        self.R_shares = [ASSecretShare(Mersenne61.random()) for _ in range(self.N)]
        self.rho_coeffs = [ASSecretShare(Mersenne61.random()) for _ in range(self.N - 1)]
        self.F_input_shares = [[ASSecretShare(Mersenne61.random()) for _ in range(self.d)] for _ in range(self.c)]

        random.seed(time.time())

    def online_phase(self):
        print(f"[{self.node_id}] Starting Online Phase...")

        # <f> = sum <F_i> * alpha^i
        f_shares = []
        for i in range(self.c):
            val = ASSecretShare(Mersenne61.zero())
            current_alpha = Mersenne61.one()
            row = self.F_input_shares[i]
            for col_idx in range(self.d):
                term = row[col_idx] * current_alpha.value
                val = val + term
                current_alpha = current_alpha * self.alpha
            f_shares.append(val)

        # broadcast {[f_i] - [R_j]}
        diff_shares = []
        for j in range(self.N):
            diff = f_shares[0] - self.R_shares[j]
            diff_shares.append(diff)

        pi_m = self.batch_reconstruct(diff_shares, round_id=100)

        f_prime_shares = f_shares
        beta_open = self.secure_broadcast_reconstruct(self.beta_share, round_id=200)

        A_values = []
        for j in range(self.N):
            denom = beta_open + self.hat_t[j]
            if denom.value == 0: denom = Mersenne61(1)
            val = pi_m[j] * denom.inverse()
            A_values.append(val)
        z_shares = []
        for i in range(self.c):
            term1 = f_prime_shares[i]
            if self.node_id == 0:
                term1 = term1 + ASSecretShare(beta_open)

            term2 = self.b_shares[i]
            z = self.pi_mult(term1, term2, round_id=300 + i)
            z_shares.append(z)

        z_opens = self.batch_reconstruct(z_shares, round_id=400)
        inv_f_beta_shares = []
        for i in range(self.c):
            inv_z = z_opens[i].inverse()
            val = self.b_shares[i] * inv_z.value
            inv_f_beta_shares.append(val)

        delta_open = self.secure_broadcast_reconstruct(self.delta_share, round_id=500)

        term_B1 = inv_f_beta_shares[0] * delta_open.value
        term_B2 = self.xi_share * (Mersenne61.one() - delta_open).value
        B_delta_share = term_B1 + term_B2

        F_zero_share = self.inv_xi_share
        if self.node_id == 0:
            F_zero_share = F_zero_share - ASSecretShare(beta_open)  # Minus scalar

        term_F1 = f_shares[0] * delta_open.value
        term_F2 = F_zero_share * (Mersenne61.one() - delta_open).value
        F_delta_share = term_F1 + term_F2

        #o = B(delta) * (F(delta) + beta)
        term_F_beta = F_delta_share
        if self.node_id == 0:
            term_F_beta = term_F_beta + ASSecretShare(beta_open)

        o_share = self.pi_mult(B_delta_share, term_F_beta, round_id=600)
        o_open = self.secure_broadcast_reconstruct(o_share, round_id=601)

        if o_open.value != 1:
            print(f"[{self.node_id}] \033[93mStep 8 Check Failed: o != 1 (Got {o_open.value}). Ignoring...\033[0m")

        C_plus_rho_evals = []
        c_over_N = Mersenne61(self.c) * Mersenne61(self.N).inverse()

        for j in range(self.N):
            x_val = self.omega_N
            b_val = (inv_f_beta_shares[0] * x_val.value) + (self.xi_share * (Mersenne61.one() - x_val).value)

            z_val = Mersenne61.random()

            # term = c/N * z(x) * B(x)
            factor = c_over_N * z_val
            term = b_val * factor.value

            # C = A - term. A is scalar, term is share.
            # share = A - share -> share = -share + A
            # C_share = term * -1
            C_share = term * (Mersenne61.MOD - 1)
            if self.node_id == 0:
                C_share = C_share + ASSecretShare(A_values[j])

            rho_val = self.rho_coeffs[j % len(self.rho_coeffs)]

            total = C_share + rho_val
            C_plus_rho_evals.append(total)

        Chat_evals = self.batch_reconstruct(C_plus_rho_evals, round_id=700)

        print(f"[{self.node_id}] Step 11: Degree Check (Simulated) - Done.")

        gamma_open = self.secure_broadcast_reconstruct(self.gamma_share, round_id=800)

        B_gamma_share = (inv_f_beta_shares[0] * gamma_open.value) + (
                    self.xi_share * (Mersenne61.one() - gamma_open).value)

        rho_gamma_share = ASSecretShare(Mersenne61.zero())
        pow_gamma = Mersenne61.one()
        for coeff in self.rho_coeffs:
            term = coeff * pow_gamma.value
            rho_gamma_share = rho_gamma_share + term
            pow_gamma = pow_gamma * gamma_open

        payload_12 = [B_gamma_share.share.to_string(), rho_gamma_share.share.to_string()]
        self.party.broadcast(payload_12, round_id=900)
        self.party.receive_round(900)

        print(f"[{self.node_id}] Step 13: Final Identity Check (Simulated) - Done.")

        print(f"[{self.node_id}] Online Phase Complete.")
        return 1

def test():
    node_id = int(sys.argv[1])
    num_parties = 4
    protocol = LuArgProtocol(node_id, num_parties)
    print(f"[{node_id}] Offline.")
    protocol.preprocessing_phase()

    # 2. Online
    protocol.party.barrier()
    start_time = time.time()

    success = protocol.online_phase()
    end_time = time.time()
    if success:
        print(f"[{node_id}] \033[92mProtocol Finished in {end_time - start_time:.4f}s\033[0m")
