#pragma once

#include "flowscribe/engine/core/job_manager.h"
#include "flowscribe/engine/core/scheduler.h"
#include "flowscribe/engine/protocol/message.h"
#include "flowscribe/engine/transcription/runtime_pool.h"

#include <chrono>
#include <functional>
#include <memory>
#include <thread>
#include <vector>

namespace flowscribe::engine::core {

struct WorkerCallbacks {
    std::function<void(const protocol::JobEvent&)> on_event;
    std::function<void(const protocol::JobResult&)> on_result;
    std::function<void(const protocol::JobError&)> on_error;
};

struct WorkerPoolOptions {
    size_t worker_count = 1;
    bool verbose = false;
    std::chrono::milliseconds mock_job_delay{0};
};

class WorkerPool {
public:
    WorkerPool(
        JobScheduler& scheduler,
        JobManager& job_manager,
        transcription::RuntimePool& runtime_pool,
        WorkerCallbacks callbacks,
        WorkerPoolOptions options = {});
    ~WorkerPool();

    WorkerPool(const WorkerPool&) = delete;
    WorkerPool& operator=(const WorkerPool&) = delete;

    void start();
    void stop();

private:
    void worker_loop(size_t worker_index);
    void execute_job(const protocol::SubmitJobRequest& req);
    void emit_event(const protocol::JobEvent& event);
    void emit_result(const protocol::JobResult& result);
    void emit_error(const protocol::JobError& error);

    JobScheduler& scheduler_;
    JobManager& job_manager_;
    transcription::RuntimePool& runtime_pool_;
    WorkerCallbacks callbacks_;
    std::vector<std::thread> workers_;
    bool started_ = false;
    WorkerPoolOptions options_;
};

} // namespace flowscribe::engine::core
