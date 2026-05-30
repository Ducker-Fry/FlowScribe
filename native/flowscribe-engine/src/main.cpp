#include <iostream>
#include <string>
#include <utility>

#include "flowscribe/engine/core/engine_service.h"
#include "flowscribe/engine/ipc/named_pipe_server.h"

int main() {
    flowscribe::engine::ipc::NamedPipeServer server;
    std::string error;

    if (!server.create_pipe(error)) {
        std::cerr << "create pipe failed: " << error << std::endl;
        return 1;
    }

    std::cout << "engine running, waiting python client..." << std::endl;

    auto conn = server.wait_for_connection(error);
    if (!conn) {
        std::cerr << "accept failed: " << error << std::endl;
        return 1;
    }

    std::cout << "client connected, start handling messages" << std::endl;

    flowscribe::engine::core::EngineService service;
    service.run(std::move(conn));

    std::cout << "client disconnected, exit" << std::endl;
    return 0;
}
