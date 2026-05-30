#include "flowscribe/engine/ipc/named_pipe_server.h"

#include <array>

namespace flowscribe::engine::ipc {

namespace {

std::string configured_pipe_name() {
    std::array<char, 512> buffer = {};
    const DWORD written = ::GetEnvironmentVariableA(
        "FLOWSCRIBE_ENGINE_PIPE_NAME",
        buffer.data(),
        static_cast<DWORD>(buffer.size()));
    if (written > 0 && written < buffer.size()) {
        return std::string(buffer.data(), written);
    }
    return NamedPipeServer::PIPE_NAME;
}

} // namespace

NamedPipeServer::NamedPipeServer() = default;

NamedPipeServer::~NamedPipeServer() {
    close();
}

bool NamedPipeServer::create_pipe(std::string& error) {
    error.clear();
    const std::string pipe_name = configured_pipe_name();

    pipe_handle_ = ::CreateNamedPipeA(
        pipe_name.c_str(),
        PIPE_ACCESS_DUPLEX,
        PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
        PIPE_UNLIMITED_INSTANCES,
        PIPE_BUFFER_SIZE,
        PIPE_BUFFER_SIZE,
        0,
        nullptr);

    if (pipe_handle_ == INVALID_HANDLE_VALUE) {
        error = "CreateNamedPipe failed";
        return false;
    }

    return true;
}

std::unique_ptr<NamedPipeConnection> NamedPipeServer::wait_for_connection(std::string& error) {
    error.clear();

    const BOOL ok = ::ConnectNamedPipe(pipe_handle_, nullptr);
    if (!ok && ::GetLastError() != ERROR_PIPE_CONNECTED) {
        error = "ConnectNamedPipe failed";
        return nullptr;
    }

    HANDLE conn_handle = pipe_handle_;
    pipe_handle_ = INVALID_HANDLE_VALUE;

    return std::make_unique<NamedPipeConnection>(conn_handle);
}

void NamedPipeServer::close() {
    if (pipe_handle_ != INVALID_HANDLE_VALUE) {
        ::CloseHandle(pipe_handle_);
        pipe_handle_ = INVALID_HANDLE_VALUE;
    }
}

} // namespace flowscribe::engine::ipc
