#include "flowscribe/engine/core/job_manager.h"

#include <chrono>

namespace flowscribe::engine::core {

int64_t JobManager::now_ms() {
    const auto now = std::chrono::system_clock::now().time_since_epoch();
    return std::chrono::duration_cast<std::chrono::milliseconds>(now).count();
}

bool JobManager::create_queued(const protocol::SubmitJobRequest& req, std::string& error) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (jobs_.contains(req.job_id)) {
        error = "job_id already exists";
        return false;
    }

    protocol::JobStatus job;
    job.job_id = req.job_id;
    job.audio_path = req.audio_path;
    job.status = "queued";
    job.progress = 0.0;
    job.created_at = now_ms();
    jobs_.emplace(req.job_id, std::move(job));
    error.clear();
    return true;
}

bool JobManager::mark_running(const std::string& job_id) {
    std::lock_guard<std::mutex> lock(mutex_);
    auto it = jobs_.find(job_id);
    if (it == jobs_.end()) {
        return false;
    }

    it->second.status = "running";
    it->second.progress = 0.0;
    if (it->second.started_at == 0) {
        it->second.started_at = now_ms();
    }
    return true;
}

bool JobManager::update_progress(const std::string& job_id, double progress) {
    std::lock_guard<std::mutex> lock(mutex_);
    auto it = jobs_.find(job_id);
    if (it == jobs_.end()) {
        return false;
    }

    it->second.progress = progress;
    return true;
}

bool JobManager::mark_completed(const protocol::JobResult& result) {
    std::lock_guard<std::mutex> lock(mutex_);
    auto it = jobs_.find(result.job_id);
    if (it == jobs_.end()) {
        return false;
    }

    it->second.status = "completed";
    it->second.progress = 1.0;
    it->second.finished_at = now_ms();
    it->second.error.clear();
    it->second.result = result;
    return true;
}

bool JobManager::mark_failed(const std::string& job_id, const std::string& error) {
    std::lock_guard<std::mutex> lock(mutex_);
    auto it = jobs_.find(job_id);
    if (it == jobs_.end()) {
        return false;
    }

    it->second.status = "failed";
    it->second.progress = 1.0;
    it->second.finished_at = now_ms();
    it->second.error = error;
    return true;
}

bool JobManager::mark_canceled_if_queued(const std::string& job_id, std::string& error) {
    std::lock_guard<std::mutex> lock(mutex_);
    auto it = jobs_.find(job_id);
    if (it == jobs_.end()) {
        error = "job not found";
        return false;
    }

    if (it->second.status == "running") {
        error = "running job cancellation is not supported yet";
        return false;
    }

    if (it->second.status == "completed" || it->second.status == "failed" ||
        it->second.status == "canceled") {
        error = "job already finished";
        return false;
    }

    if (it->second.status != "queued") {
        error = "job is not queued";
        return false;
    }

    it->second.status = "canceled";
    it->second.progress = 1.0;
    it->second.finished_at = now_ms();
    error.clear();
    return true;
}

std::optional<protocol::JobStatus> JobManager::get(const std::string& job_id) const {
    std::lock_guard<std::mutex> lock(mutex_);
    auto it = jobs_.find(job_id);
    if (it == jobs_.end()) {
        return std::nullopt;
    }
    return it->second;
}

} // namespace flowscribe::engine::core
