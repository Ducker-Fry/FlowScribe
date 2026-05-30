#pragma once

#include "flowscribe/engine/protocol/message.h"

#include <condition_variable>
#include <functional>
#include <mutex>
#include <queue>
#include <thread>

namespace flowscribe::engine::core {

class OutboundDispatcher {
public:
    using Writer = std::function<bool(const protocol::Message&)>;

    OutboundDispatcher() = default;
    ~OutboundDispatcher();

    OutboundDispatcher(const OutboundDispatcher&) = delete;
    OutboundDispatcher& operator=(const OutboundDispatcher&) = delete;

    void start(Writer writer);
    void stop(bool drain = false);
    void send_response(const protocol::Message& msg);
    void send_event(const protocol::Message& msg);

private:
    void enqueue(const protocol::Message& msg);
    void writer_loop();

    Writer writer_;
    std::thread writer_thread_;
    std::mutex mutex_;
    std::condition_variable cv_;
    std::queue<protocol::Message> queue_;
    bool stopping_ = false;
    bool started_ = false;
};

} // namespace flowscribe::engine::core
