#include "flowscribe/engine/core/scheduler.h"

#include <algorithm>
#include <iostream>

namespace flowscribe::engine::core {

JobScheduler::JobScheduler(bool verbose)
    : verbose_(verbose) {
}

void JobScheduler::set_verbose(bool verbose) {
    std::lock_guard<std::mutex> lock(mutex_);
    verbose_ = verbose;
}

void JobScheduler::enqueue(const protocol::SubmitJobRequest& req) {
    {
        std::lock_guard<std::mutex> lock(mutex_);
        if (stopping_) {
            return;
        }
        queue_.push_back(req);
        if (verbose_) {
            std::cout << "job queued: " << req.job_id << std::endl;
        }
    }
    cv_.notify_one();
}

bool JobScheduler::wait_dequeue(protocol::SubmitJobRequest& req) {
    std::unique_lock<std::mutex> lock(mutex_);
    cv_.wait(lock, [this] {
        return stopping_ || !queue_.empty();
    });

    if (queue_.empty()) {
        return false;
    }

    req = queue_.front();
    queue_.pop_front();
    if (verbose_) {
        std::cout << "job dequeued: " << req.job_id << std::endl;
    }
    return true;
}

bool JobScheduler::cancel_queued(const std::string& job_id) {
    std::lock_guard<std::mutex> lock(mutex_);
    const auto it = std::find_if(queue_.begin(), queue_.end(), [&job_id](const auto& req) {
        return req.job_id == job_id;
    });
    if (it == queue_.end()) {
        return false;
    }

    queue_.erase(it);
    return true;
}

void JobScheduler::stop() {
    {
        std::lock_guard<std::mutex> lock(mutex_);
        stopping_ = true;
        queue_.clear();
    }
    cv_.notify_all();
}

} // namespace flowscribe::engine::core
