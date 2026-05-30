#pragma once

#include "flowscribe/engine/protocol/message.h"

#include <condition_variable>
#include <deque>
#include <mutex>
#include <string>

namespace flowscribe::engine::core {

class JobScheduler {
public:
    explicit JobScheduler(bool verbose = false);
    void set_verbose(bool verbose);
    void enqueue(const protocol::SubmitJobRequest& req);
    bool wait_dequeue(protocol::SubmitJobRequest& req);
    bool cancel_queued(const std::string& job_id);
    void stop();

private:
    std::mutex mutex_;
    std::condition_variable cv_;
    std::deque<protocol::SubmitJobRequest> queue_;
    bool stopping_ = false;
    bool verbose_ = false;
};

} // namespace flowscribe::engine::core
