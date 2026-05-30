#pragma once

#include "flowscribe/engine/protocol/message.h"

#include <mutex>
#include <optional>
#include <string>
#include <unordered_map>

namespace flowscribe::engine::core {

class JobManager {
public:
    bool create_queued(const protocol::SubmitJobRequest& req, std::string& error);
    bool mark_running(const std::string& job_id);
    bool update_progress(const std::string& job_id, double progress);
    bool mark_completed(const protocol::JobResult& result);
    bool mark_failed(const std::string& job_id, const std::string& error);
    bool mark_canceled_if_queued(const std::string& job_id, std::string& error);
    std::optional<protocol::JobStatus> get(const std::string& job_id) const;

private:
    static int64_t now_ms();

    mutable std::mutex mutex_;
    std::unordered_map<std::string, protocol::JobStatus> jobs_;
};

}
