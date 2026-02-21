#include <coroutine>
#include <vector>
#include <iostream>
#include <cstring>
#include <random>
#include <string>

#ifndef MACORO_CPP_20
#define MACORO_CPP_20 1
#endif

#include <cryptoTools/Common/Defines.h>
#include <cryptoTools/Crypto/PRNG.h>
#include <libOTe/Vole/Silent/SilentVoleSender.h>
#include <libOTe/Vole/Silent/SilentVoleReceiver.h>

#include <macoro/sync_wait.h>
#include <coproto/Socket/AsioSocket.h>

using namespace osuCrypto;
namespace cp = coproto;
namespace mc = macoro;

const int D = 64;

struct GR_Block {
    uint64_t coeffs[D];
};

extern "C" {
    void gr_sub(const GR_Block& a, const GR_Block& b, GR_Block& res) { 
        for(int i=0; i<D; i++) res.coeffs[i] = a.coeffs[i] - b.coeffs[i]; 
    }
    void gr_add(const GR_Block& a, const GR_Block& b, GR_Block& res) { 
        for(int i=0; i<D; i++) res.coeffs[i] = a.coeffs[i] + b.coeffs[i]; 
    }
    void gr_random(GR_Block& res) { 
        static std::mt19937_64 rng(std::random_device{}());
        for(int i=0; i<D; i++) res.coeffs[i] = rng(); 
    }

    int run_vole_commit_sender(const char* ip, int port, size_t M, const uint64_t* input_X_ptr, uint64_t* output_MAC_ptr) {
        try {
            std::string address = std::string(ip) + ":" + std::to_string(port);
            auto socket = cp::asioConnect(address, cp::ConnectorType::Client);

            // ==========================================
            // ==========================================
            osuCrypto::SilentVoleSender sender;
            sender.mMalType = osuCrypto::SilentSecType;
            osuCrypto::PRNG prng(osuCrypto::sysRandomSeed());
            
            std::vector<osuCrypto::block> vole_a(M), vole_c(M);
            
            mc::sync_wait(sender.silentSend(vole_a, vole_c, prng, socket));

            std::vector<GR_Block> X(M), D_vec(M), Q(M);
            std::memcpy(X.data(), input_X_ptr, M * sizeof(GR_Block));

            for(size_t i = 0; i < M; i++) {
                GR_Block dummy_A; gr_random(dummy_A);
                gr_sub(X[i], dummy_A, D_vec[i]); // d = X - A
                Q[i] = dummy_A; 
            }
            
            mc::sync_wait(socket.send(coproto::make_span(D_vec)));

            std::memcpy(output_MAC_ptr, Q.data(), M * sizeof(GR_Block));
            mc::sync_wait(socket.flush());
            return 0;
        } catch (const std::exception& e) {
            std::cerr << "[Sender Error] " << e.what() << std::endl;
            return -1;
        }
    }

    int run_vole_commit_receiver(int port, size_t M, const uint64_t* input_delta_ptr, uint64_t* output_MAC_ptr) {
        try {
            std::string address = "0.0.0.0:" + std::to_string(port);
            auto socket = cp::asioConnect(address, cp::ConnectorType::Server);

            osuCrypto::SilentVoleReceiver receiver;
            receiver.mMalType = osuCrypto::SilentSecType;
            osuCrypto::PRNG prng(osuCrypto::sysRandomSeed());

            osuCrypto::block vole_delta = prng.get<osuCrypto::block>();
            std::vector<osuCrypto::block> vole_b(M);

            mc::sync_wait(receiver.silentReceive(vole_delta, vole_b, prng, socket));

            std::vector<GR_Block> D_vec(M), final_MAC(M);

            mc::sync_wait(socket.recv(coproto::make_span(D_vec)));

            for(size_t i = 0; i < M; i++) {
                gr_random(final_MAC[i]); 
            }

            std::memcpy(output_MAC_ptr, final_MAC.data(), M * sizeof(GR_Block));
            mc::sync_wait(socket.flush());
            return 0;
        } catch (const std::exception& e) {
            std::cerr << "[Receiver Error] " << e.what() << std::endl;
            return -1;
        }
    }
}
