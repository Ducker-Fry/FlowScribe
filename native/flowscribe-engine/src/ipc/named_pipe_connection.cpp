#include "flowscribe/engine/ipc/named_pipe_connection.h"

namespace flowscribe::engine::ipc {

NamedPipeConnection::NamedPipeConnection(HANDLE pipe_handle)
    : pipe_handle_(pipe_handle) {
}

NamedPipeConnection::~NamedPipeConnection() {
    close();
}

NamedPipeConnection::NamedPipeConnection(NamedPipeConnection&& other) noexcept
    : pipe_handle_(other.pipe_handle_) {
    other.pipe_handle_ = INVALID_HANDLE_VALUE;
}

NamedPipeConnection& NamedPipeConnection::operator=(NamedPipeConnection&& other) noexcept {
    if (this != &other) {
        close();
        pipe_handle_ = other.pipe_handle_;
        other.pipe_handle_ = INVALID_HANDLE_VALUE;
    }
    return *this;
}

void NamedPipeConnection::close() {
    if (pipe_handle_ != INVALID_HANDLE_VALUE) {
        ::CloseHandle(pipe_handle_);
        pipe_handle_ = INVALID_HANDLE_VALUE;
    }
}

bool NamedPipeConnection::read_exact(void* buffer, size_t size, std::string& error) {
    error.clear();

    DWORD bytes_read = 0;
    char* ptr = static_cast<char*>(buffer);
    size_t remaining = size;

    while (remaining > 0) {
        const BOOL ok = ::ReadFile(
            pipe_handle_,
            ptr,
            static_cast<DWORD>(remaining),
            &bytes_read,
            nullptr);

        if (!ok || bytes_read == 0) {
            error = "read failed or connection closed";
            return false;
        }

        ptr += bytes_read;
        remaining -= bytes_read;
    }

    return true;
}

bool NamedPipeConnection::write_exact(const void* buffer, size_t size, std::string& error) {
    error.clear();

    DWORD bytes_written = 0;
    const char* ptr = static_cast<const char*>(buffer);
    size_t remaining = size;

    while (remaining > 0) {
        const BOOL ok = ::WriteFile(
            pipe_handle_,
            ptr,
            static_cast<DWORD>(remaining),
            &bytes_written,
            nullptr);

        if (!ok || bytes_written == 0) {
            const DWORD last_error = ::GetLastError();
            if (last_error == ERROR_BROKEN_PIPE ||
                last_error == ERROR_NO_DATA ||
                last_error == ERROR_PIPE_NOT_CONNECTED) {
                error = "connection closed";
            } else {
                error = "write failed";
            }
            return false;
        }

        ptr += bytes_written;
        remaining -= bytes_written;
    }

    return true;
}

bool NamedPipeConnection::read_message(protocol::Message& out_msg, std::string& error) {
    error.clear();
    out_msg = {};

    uint8_t header_buf[protocol::FRAME_HEADER_SIZE] = {};
    if (!read_exact(header_buf, protocol::FRAME_HEADER_SIZE, error)) {
        return false;
    }

    protocol::FrameHeader header;
    if (!protocol::decode_frame_header(header_buf, header)) {
        error = "invalid frame header";
        return false;
    }

    if (header.payload_len > protocol::MAX_PAYLOAD_SIZE) {
        error = "payload exceeds maximum size";
        return false;
    }

    std::vector<uint8_t> payload_buf(header.payload_len);
    if (header.payload_len > 0 &&
        !read_exact(payload_buf.data(), header.payload_len, error)) {
        return false;
    }

    std::vector<uint8_t> full_msg;
    full_msg.reserve(protocol::FRAME_HEADER_SIZE + payload_buf.size());
    full_msg.insert(full_msg.end(), header_buf, header_buf + protocol::FRAME_HEADER_SIZE);
    full_msg.insert(full_msg.end(), payload_buf.begin(), payload_buf.end());

    return protocol::decode_message(full_msg, out_msg, error);
}

ReadMessageStatus NamedPipeConnection::try_read_message(
    protocol::Message& out_msg,
    std::string& error) {
    error.clear();
    out_msg = {};

    DWORD bytes_available = 0;
    uint8_t header_buf[protocol::FRAME_HEADER_SIZE] = {};
    DWORD bytes_read = 0;
    const BOOL peek_ok = ::PeekNamedPipe(
        pipe_handle_,
        header_buf,
        protocol::FRAME_HEADER_SIZE,
        &bytes_read,
        &bytes_available,
        nullptr);

    if (!peek_ok) {
        const DWORD last_error = ::GetLastError();
        if (last_error == ERROR_BROKEN_PIPE || last_error == ERROR_PIPE_NOT_CONNECTED) {
            error = "connection closed";
            return ReadMessageStatus::Closed;
        }

        error = "PeekNamedPipe failed";
        return ReadMessageStatus::Error;
    }

    if (bytes_available == 0) {
        return ReadMessageStatus::NoMessage;
    }

    if (bytes_available < protocol::FRAME_HEADER_SIZE ||
        bytes_read < protocol::FRAME_HEADER_SIZE) {
        return ReadMessageStatus::NoMessage;
    }

    protocol::FrameHeader header;
    if (!protocol::decode_frame_header(header_buf, header)) {
        error = "invalid frame header";
        return ReadMessageStatus::Error;
    }

    if (header.payload_len > protocol::MAX_PAYLOAD_SIZE) {
        error = "payload exceeds maximum size";
        return ReadMessageStatus::Error;
    }

    const DWORD message_size =
        protocol::FRAME_HEADER_SIZE + static_cast<DWORD>(header.payload_len);
    if (bytes_available < message_size) {
        return ReadMessageStatus::NoMessage;
    }

    if (!read_message(out_msg, error)) {
        return ReadMessageStatus::Error;
    }

    return ReadMessageStatus::Message;
}

bool NamedPipeConnection::write_message(const protocol::Message& msg, std::string& error) {
    const auto bytes = protocol::encode_message(msg);
    return write_exact(bytes.data(), bytes.size(), error);
}

} // namespace flowscribe::engine::ipc
