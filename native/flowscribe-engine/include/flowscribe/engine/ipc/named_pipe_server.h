#pragma once

#include <windows.h>
#include <memory>
#include <string>

#include "flowscribe/engine/ipc/named_pipe_connection.h"

namespace flowscribe::engine::ipc
{

    class NamedPipeServer
    {
    public:
        static constexpr const char *PIPE_NAME = R"(\\.\pipe\flowscribe-engine-v1)";
        static constexpr DWORD PIPE_BUFFER_SIZE = 65536;

        NamedPipeServer();
        ~NamedPipeServer();

        bool create_pipe(std::string &error);
        std::unique_ptr<NamedPipeConnection> wait_for_connection(std::string &error);

        void close();
        bool is_valid() const { return pipe_handle_ != INVALID_HANDLE_VALUE; }

    private:
        HANDLE pipe_handle_ = INVALID_HANDLE_VALUE;
    };

} // namespace flowscribe::engine::ipc