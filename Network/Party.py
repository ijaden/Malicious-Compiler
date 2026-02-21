import socket
import json
import time
import select
import uuid
import math

NODE_MAP = {
    0: 5000,
    1: 5001,
    2: 5002,
    3: 5003
}

MAX_UDP_PAYLOAD = 32 * 1024


class Party:
    def __init__(self, node_id):
        self.node_id = node_id
        self.port = NODE_MAP[node_id]
        self.peers = [pid for pid in NODE_MAP if pid != node_id]

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
        self.sock.bind(('127.0.0.1', self.port))
        self.sock.setblocking(False)


        self._msg_buffer = {}

        self._fragment_buffer = {}

        print(f"[*] Party {self.node_id} listening on {self.port}")

    def _send_raw_bytes(self, target_id, data_bytes):

        target_port = NODE_MAP[target_id]
        try:
            self.sock.sendto(data_bytes, ('127.0.0.1', target_port))
        except BlockingIOError:
            pass
        except OSError as e:
            if e.errno == 90:
                print(f"[Error] Packet too long even after chunking? Size: {len(data_bytes)}")
            raise e

    def _send_packet(self, target_id, payload):

        json_bytes = json.dumps(payload).encode('utf-8')
        total_len = len(json_bytes)

        if total_len <= MAX_UDP_PAYLOAD:
            self._send_raw_bytes(target_id, json_bytes)
            return

        msg_id = str(uuid.uuid4())
        num_chunks = math.ceil(total_len / MAX_UDP_PAYLOAD)

        for i in range(num_chunks):
            start = i * MAX_UDP_PAYLOAD
            end = start + MAX_UDP_PAYLOAD
            chunk_data = json_bytes[start:end]

            frag_packet = {
                '__frag': True,
                'uid': msg_id,
                'i': i,
                'n': num_chunks,
                'd': chunk_data.decode('latin1')
            }


            frag_bytes = json.dumps(frag_packet).encode('utf-8')
            self._send_raw_bytes(target_id, frag_bytes)

    def _handle_recv_data(self, data_bytes):

        try:
            msg = json.loads(data_bytes.decode('utf-8'))
        except:
            return None, False


        if msg.get('__frag') is True:
            uid = msg['uid']
            idx = msg['i']
            total = msg['n']

            chunk_content = msg['d'].encode('latin1')

            if uid not in self._fragment_buffer:
                self._fragment_buffer[uid] = {'chunks': {}, 'total': total, 'recvd_size': 0}


            if idx not in self._fragment_buffer[uid]['chunks']:
                self._fragment_buffer[uid]['chunks'][idx] = chunk_content
                self._fragment_buffer[uid]['recvd_size'] += 1


            if self._fragment_buffer[uid]['recvd_size'] == total:

                chunks = self._fragment_buffer[uid]['chunks']
                full_bytes = b''.join([chunks[i] for i in range(total)])


                del self._fragment_buffer[uid]


                try:
                    full_payload = json.loads(full_bytes.decode('utf-8'))
                    return full_payload, True
                except:
                    print("Error parsing reassembled JSON")
                    return None, False
            else:
                return None, False

        else:

            return msg, True

    def barrier(self):

        print(f"[{self.node_id}] Waiting at barrier...")
        ready_peers = set()
        while len(ready_peers) < len(self.peers):
            for pid in self.peers:
                self._send_packet(pid, {'t': 'READY', 'src': self.node_id})

            ready, _, _ = select.select([self.sock], [], [], 0.5)
            if ready:
                try:
                    data, _ = self.sock.recvfrom(65535)

                    msg, is_complete = self._handle_recv_data(data)
                    if is_complete and msg and msg.get('t') == 'READY':
                        ready_peers.add(msg.get('src'))
                except Exception as e:
                    pass
            time.sleep(0.1)
        print(f"[{self.node_id}] Barrier cleared. Network ready.")

    def broadcast(self, value, round_id):

        payload = {
            't': 'DATA',
            'r': round_id,
            'src': self.node_id,
            'val': value
        }
        for pid in self.peers:
            self._send_packet(pid, payload)

    def receive_round(self, round_id, expected_senders=None):

        received = {}

        if expected_senders is None:
            wait_list = self.peers
        else:
            wait_list = expected_senders


        for pid in wait_list:
            key = (round_id, pid)
            if key in self._msg_buffer:
                received[pid] = self._msg_buffer.pop(key)

        while len(received) < len(wait_list):
            ready, _, _ = select.select([self.sock], [], [], 1.0)
            if ready:
                try:
                    data, _ = self.sock.recvfrom(65535)


                    msg, is_complete = self._handle_recv_data(data)

                    if is_complete and msg:
                        r_in = msg.get('r')
                        src = msg.get('src')
                        val = msg.get('val')

                        if r_in == round_id:
                            if src in wait_list and src not in received:
                                received[src] = val
                        elif r_in is not None and r_in > round_id:

                            self._msg_buffer[(r_in, src)] = val

                except Exception as e:
                    print(f"Error processing packet: {e}")

        return received