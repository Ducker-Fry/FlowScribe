#include "flowscribe/engine/core/outbound_dispatcher.h"

namespace flowscribe::engine::core {

OutboundDispatcher::~OutboundDispatcher() {
    stop();
}

void OutboundDispatcher::start(Writer writer) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (started_) {
        return;
    }

    writer_ = std::move(writer);
    stopping_ = false;
    started_ = true;
    writer_thread_ = std::thread([this] {
        writer_loop();
    });
}

void OutboundDispatcher::stop(bool drain) {
    {
        std::lock_guard<std::mutex> lock(mutex_);
        if (!started_) {
            return;
        }
        stopping_ = true;
        if (!drain) {
            while (!queue_.empty()) {
                queue_.pop();
            }
        }
    }
    cv_.notify_all();

    if (writer_thread_.joinable()) {
        writer_thread_.join();
    }

    std::lock_guard<std::mutex> lock(mutex_);
    while (!queue_.empty()) {
        queue_.pop();
    }
    writer_ = {};
    started_ = false;
}

void OutboundDispatcher::send_response(const protocol::Message& msg) {
    enqueue(msg);
}

void OutboundDispatcher::send_event(const protocol::Message& msg) {
    enqueue(msg);
}

void OutboundDispatcher::enqueue(const protocol::Message& msg) {
    {
        std::lock_guard<std::mutex> lock(mutex_);
        if (!started_ || stopping_) {
            return;
        }
        queue_.push(msg);
    }
    cv_.notify_one();
}

void OutboundDispatcher::writer_loop() {
    while (true) {
        protocol::Message msg;
        Writer writer;
        {
            std::unique_lock<std::mutex> lock(mutex_);
            cv_.wait(lock, [this] {
                return stopping_ || !queue_.empty();
            });

            if (stopping_ && queue_.empty()) {
                return;
            }

            msg = std::move(queue_.front());
            queue_.pop();
            writer = writer_;
        }

        if (!writer || !writer(msg)) {
            std::lock_guard<std::mutex> lock(mutex_);
            stopping_ = true;
            return;
        }
    }
}

} // namespace flowscribe::engine::core
