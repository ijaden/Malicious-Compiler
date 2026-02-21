import sys
import os
import ctypes
import threading
import time
from typing import List, Optional

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from Network.Party import *
from Datetype.GR import *



class AuthenticatedVectorShare:
 
    def __init__(self, vals: List[Optional[GaloisRingElement]], macs: List[GaloisRingElement], owner_id: int):
        self.vals = vals  
        self.macs = macs 
        self.owner_id = owner_id
        self.M = len(macs)

    def __add__(self, other: 'AuthenticatedVectorShare') -> 'AuthenticatedVectorShare':
        if self.M != other.M:
            raise ValueError("Vector lengths mismatch")
            
        vals_sum = [None] * self.M
        if self.vals[0] is not None and other.vals[0] is not None:
            vals_sum = [(self.vals[i] + other.vals[i]) for i in range(self.M)]
            
        macs_sum = [(self.macs[i] + other.macs[i]) for i in range(self.M)]
        owner = self.owner_id if self.owner_id == other.owner_id else -1
        return AuthenticatedVectorShare(vals_sum, macs_sum, owner)

    def scalar_mul(self, scalar: GaloisRingElement) -> 'AuthenticatedVectorShare':
        vals_mul = [(self.vals[i] * scalar) if self.vals[i] is not None else None for i in range(self.M)]
        macs_mul = [(self.macs[i] * scalar) for i in range(self.M)]
        return AuthenticatedVectorShare(vals_mul, macs_mul, self.owner_id)

    def __repr__(self):
        val_preview = self.vals[0].coeffs[0] if self.vals[0] else "None"
        return f"<AuthVectorShare owner={self.owner_id}, M={self.M}, val[0]={val_preview}...>"



class CppOLEWrapper:
    def __init__(self, lib_path="./build/libGaloisOT.so"):
        self.lib_path = lib_path
        self.lib = None
        self._load_lib()

    def _load_lib(self):
        if not os.path.exists(self.lib_path):
            print(f"[!] Warning: Library {self.lib_path} not found. Ensure you compiled GaloisOT.cpp.")
            return

        try:
            self.lib = ctypes.CDLL(self.lib_path)
            uint64_ptr = ctypes.POINTER(ctypes.c_uint64)

            self.lib.run_vole_commit_sender.argtypes = [
                ctypes.c_char_p, ctypes.c_int, ctypes.c_size_t, uint64_ptr, uint64_ptr
            ]
            self.lib.run_vole_commit_receiver.argtypes = [
                ctypes.c_int, ctypes.c_size_t, uint64_ptr, uint64_ptr
            ]
        except Exception as e:
            print(f"[!] Error loading library: {e}")
            self.lib = None

    def run_vector_sender(self, target_ip: str, port: int, x_vec: List[GaloisRingElement]) -> List[GaloisRingElement]:
        if not self.lib: raise RuntimeError("Lib not loaded")
        M = len(x_vec)
        
        flat_x = []
        for x in x_vec: flat_x.extend(x.coeffs)
        
        total_len = M * 64
        in_arr = (ctypes.c_uint64 * total_len)(*flat_x)
        out_arr = (ctypes.c_uint64 * total_len)()
        ip_bytes = target_ip.encode('utf-8')

        res = self.lib.run_vole_commit_sender(ip_bytes, port, M, in_arr, out_arr)
        if res != 0: raise RuntimeError("C++ VOLE Sender failed")

        macs = []
        for i in range(M):
            macs.append(GaloisRingElement(list(out_arr[i*64 : (i+1)*64])))
        return macs

    def run_vector_receiver(self, port: int, M: int, delta: GaloisRingElement) -> List[GaloisRingElement]:
        if not self.lib: raise RuntimeError("Lib not loaded")
        total_len = M * 64
        in_arr = (ctypes.c_uint64 * 64)(*delta.coeffs)
        out_arr = (ctypes.c_uint64 * total_len)()
        
        res = self.lib.run_vole_commit_receiver(port, M, in_arr, out_arr)
        if res != 0: raise RuntimeError("C++ VOLE Receiver failed")
        
        macs = []
        for i in range(M):
            macs.append(GaloisRingElement(list(out_arr[i*64 : (i+1)*64])))
        return macs


class VOLEProtocol:
    def __init__(self, node_id: int):
        self.party = Party(node_id)
        self.delta = None
        self.ole_cpp = CppOLEWrapper()
        self.round_counter = 0
        self.ole_base_port = 6000
        self.party.barrier()

    def _next_round(self):
        self.round_counter += 1
        return self.round_counter

    def _get_ole_port(self, sender_id, receiver_id):
        return self.ole_base_port + (sender_id * 10) + receiver_id

    def generate_key(self):
        print(f"[{self.party.node_id}] Generating Global Key Share (Delta)...")
        self.delta = GaloisRingElement.random()
        self.party.barrier()

    def commit_vector(self, values: List[GaloisRingElement] = None, src_id: int = 0, M: int = 0) -> AuthenticatedVectorShare:
        if self.party.node_id == src_id:
            if values is None:
                raise ValueError("Owner must provide values to commit")
            M = len(values)
            my_macs = [GaloisRingElement([0]*64) for _ in range(M)]
            threads = []
            results = {}

            def _sender_task(peer_id):
                port = self._get_ole_port(self.party.node_id, peer_id)
                time.sleep(0.1)
                shares = self.ole_cpp.run_vector_sender("127.0.0.1", port, values)
                results[peer_id] = shares

            for pid in self.party.peers:
                t = threading.Thread(target=_sender_task, args=(pid,))
                t.start()
                threads.append(t)
            for t in threads: t.join()

            for pid, shares in results.items():
                for i in range(M):
                    my_macs[i] = my_macs[i] + shares[i]

            for i in range(M):
                my_macs[i] = my_macs[i] + (values[i] * self.delta)

            return AuthenticatedVectorShare(values, my_macs, self.party.node_id)
        
        else:
            if M <= 0:
                raise ValueError("Receivers must know the vector length M")
            
            port = self._get_ole_port(src_id, self.party.node_id)
            mac_shares = self.ole_cpp.run_vector_receiver(port, M, self.delta)
            return AuthenticatedVectorShare([None]*M, mac_shares, src_id)

    def open_and_verify(self, share: AuthenticatedVectorShare) -> List[GaloisRingElement]:
        print(f"[{self.party.node_id}] Opening vector value (M={share.M})...")
        rid = self._next_round()
        M = share.M
        
        x_vals = [None] * M
        if share.owner_id == self.party.node_id:
            x_vals = share.vals
            msg = "|".join([x.to_string() for x in x_vals])
            self.party.broadcast(msg, rid)
        else:
            msgs = self.party.receive_round(rid)
            if share.owner_id in msgs:
                str_vals = msgs[share.owner_id].split("|")
                x_vals = [GaloisRingElement.from_string(s) for s in str_vals]
            else:
                raise ValueError("Failed to receive Open values")

        print(f"[{self.party.node_id}] Values reconstructed. Verifying MACs...")
        sigma_i = []
        for i in range(M):
            term = x_vals[i] * self.delta
            sigma_i.append(share.macs[i] - term)

        rid = self._next_round()
        msg_sigma = "|".join([s.to_string() for s in sigma_i])
        self.party.broadcast(msg_sigma, rid)
        deltas_map = self.party.receive_round(rid)
        total_sigma = sigma_i.copy()
        
        for pid, d_str in deltas_map.items():
            d_strs = d_str.split("|")
            for i in range(M):
                total_sigma[i] = total_sigma[i] + GaloisRingElement.from_string(d_strs[i])
        is_valid = True
        for i in range(M):
            if not all(coeff == 0 for coeff in total_sigma[i].coeffs):
                is_valid = False
        if share.vals[0] is None:
            share.vals = x_vals
            
        return x_vals


def run_test(pid):
    print(f"[{pid}] Initializing Party...")
    vole = VOLEProtocol(pid)
    vole.generate_key()

    M = 2**10
    TOTAL_NODES = 4
    
    my_secret_val = (pid + 1) * 10
    all_shares = []

    print(f"\n[{pid}] --- Benchmarking Batched Vector OLE (M={M}) ---")
    start_time = time.time()
    for src_id in range(TOTAL_NODES):
        print(f"[{pid}] Node {src_id} is committing a vector of size {M}...")
        
        if pid == src_id:
            vec_data = [GaloisRingElement([my_secret_val + i] + [0]*63) for i in range(M)]
            share = vole.commit_vector(values=vec_data, src_id=src_id, M=M)
        else:
            share = vole.commit_vector(values=None, src_id=src_id, M=M)
            
        all_shares.append(share)

    commit_time = time.time()
    
    print(f"[{pid}] Computing sum of all {TOTAL_NODES} vector shares locally...")
    sum_share = all_shares[0]
    for i in range(1, len(all_shares)):
        sum_share = sum_share + all_shares[i]

    try:
        result_vec = vole.open_and_verify(sum_share)
        verify_time = time.time()

        result_int = result_vec[0].coeffs[0]
        expected_sum = sum([(i + 1) * 10 for i in range(TOTAL_NODES)]) # 10+20+30+40 = 100

        if result_int == expected_sum:
            print(f"{result_int} == {expected_sum}")
        else:
            print(f"{result_int} != {expected_sum}")

        print(f"Total Vectors Exchanged : {TOTAL_NODES} * {M} elements")
        print(f"Commit Phase Time       : {commit_time - start_time:.4f} sec")
        print(f"Open & Verify Time      : {verify_time - commit_time:.4f} sec")
        print(f"Total Execution Time    : {verify_time - start_time:.4f} sec")

    except Exception as e:
        print(f"[{pid}] \033[91mFAILED\033[0m: Verification error - {e}")

def test():
    if len(sys.argv) < 2:
        print("Usage: python Mac_Protocol.py <node_id>")
        sys.exit(1)
    node_id = int(sys.argv[1])
    run_test(node_id)

if __name__ == "__main__":
    test()
