#pragma once

#include <windows.h>

#include <string>
#include <vector>

#include "flowscribe/engine/protocol/codec.h"
#include "flowscribe/engine/protocol/message.h"

namespace flowscribe::engine::ipc {

enum class ReadMessageStatus {
    Message,
    NoMessage,
    Closed,
    Error,
};

class NamedPipeConnection {
public:
    explicit NamedPipeConnection(HANDLE pipe_handle);
    ~NamedPipeConnection();

    NamedPipeConnection(const NamedPipeConnection&) = delete;
    NamedPipeConnection& operator=(const NamedPipeConnection&) = delete;

    NamedPipeConnection(NamedPipeConnection&&) noexcept;
    NamedPipeConnection& operator=(NamedPipeConnection&&) noexcept;

    bool read_message(protocol::Message& out_msg, std::string& error);
    ReadMessageStatus try_read_message(protocol::Message& out_msg, std::string& error);
    bool write_message(const protocol::Message& msg, std::string& error);

    bool is_valid() const { return pipe_handle_ != INVALID_HANDLE_VALUE; }
    void close();

private:
    bool read_exact(void* buffer, size_t size, std::string& error);
    bool write_exact(const void* buffer, size_t size, std::string& error);

    HANDLE pipe_handle_ = INVALID_HANDLE_VALUE;
};

} // namespace flowscribe::engine::ipc
