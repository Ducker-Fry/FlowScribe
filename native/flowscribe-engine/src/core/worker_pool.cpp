#include "flowscribe/engine/core/worker_pool.h"

#include "flowscribe/engine/transcription/chunked_transcription_executor.h"

#include <chrono>
#include <iostream>
#include <mutex>
#include <stdexcept>
#include <thread>

namespace flowscribe::engine::core {

namespace {

std::mutex g_worker_log_mutex;

void log_worker_line(const std::string& text) {
    std::lock_guard<std::mutex> lock(g_worker_log_mutex);
    std::cout << text << std::endl;
}

} // namespace

WorkerPool::WorkerPool(
    JobScheduler& scheduler,
    JobManager& job_manager,
    transcription::RuntimePool& runtime_pool,
    WorkerCallbacks callbacks,
    WorkerPoolOptions options)
    : scheduler_(scheduler),
      job_manager_(job_manager),
      runtime_pool_(runtime_pool),
      callbacks_(std::move(callbacks)),
      options_(options) {
}

WorkerPool::~WorkerPool() {
    stop();
}

void WorkerPool::start() {
    if (started_) {
        return;
    }

    started_ = true;
    const size_t count = options_.worker_count == 0 ? 1 : options_.worker_count;
    workers_.reserve(count);
    for (size_t i = 0; i < count; ++i) {
        workers_.emplace_back([this, i] {
            worker_loop(i);
        });
    }
}

void WorkerPool::stop() {
    if (!started_) {
        return;
    }

    scheduler_.stop();
    for (auto& worker : workers_) {
        if (worker.joinable()) {
            worker.join();
        }
    }
    workers_.clear();
    started_ = false;
}

void WorkerPool::worker_loop(size_t worker_index) {
    if (options_.verbose) {
        log_worker_line("worker started: " + std::to_string(worker_index));
    }

    protocol::SubmitJobRequest req;
    while (scheduler_.wait_dequeue(req)) {
        execute_job(req);
    }
}

void WorkerPool::execute_job(const protocol::SubmitJobRequest& req) {
    if (options_.verbose) {
        std::cout << "job execution started: " << req.job_id << std::endl;
    }
    const auto start = std::chrono::steady_clock::now();
    const auto current = job_manager_.get(req.job_id);
    if (current.has_value() && current->status == "canceled") {
        return;
    }

    (void)job_manager_.mark_running(req.job_id);

    protocol::JobEvent started;
    started.job_id = req.job_id;
    started.status = "job_started";
    started.progress = 0.0;
    emit_event(started);
    if (options_.verbose) {
        std::cout << "job event emitted: job_started " << req.job_id << std::endl;
    }

    try {
        if (runtime_pool_.is_mock_model()) {
            protocol::JobEvent running;
            running.job_id = req.job_id;
            running.status = "transcribing";
            running.progress = 0.5;
            (void)job_manager_.update_progress(req.job_id, running.progress);
            emit_event(running);

            if (options_.mock_job_delay.count() > 0) {
                std::this_thread::sleep_for(options_.mock_job_delay);
            }

            const auto elapsed = std::chrono::steady_clock::now() - start;
            protocol::JobResult result;
            result.job_id = req.job_id;
            result.duration_seconds = std::chrono::duration<double>(elapsed).count();

            protocol::TranscriptSegment segment;
            segment.id = 0;
            segment.start = 0.0;
            segment.end = result.duration_seconds;
            segment.text = "Sample transcription result for job: " + req.job_id;
            result.segments.push_back(std::move(segment));

            protocol::JobEvent completed;
            completed.job_id = req.job_id;
            completed.status = "job_completed";
            completed.progress = 1.0;
            completed.current_seconds = result.duration_seconds;
            completed.total_seconds = result.duration_seconds;
            emit_event(completed);

            (void)job_manager_.mark_completed(result);
            emit_result(result);
            return;
        }

        protocol::JobEvent running;
        running.job_id = req.job_id;
        running.status = "transcribing";
        running.progress = 0.5;
        (void)job_manager_.update_progress(req.job_id, running.progress);
        emit_event(running);

        protocol::JobResult result;
        std::string error;
        if (req.progressive.enabled) {
            transcription::ChunkedTranscriptionExecutor executor(runtime_pool_);
            if (options_.verbose) {
                std::cout << "chunked transcribe started: " << req.job_id
                          << ", chunk_seconds=" << req.progressive.chunk_seconds
                          << ", overlap_seconds=" << req.progressive.overlap_seconds
                          << ", max_workers=" << req.progressive.max_workers << std::endl;
            }
            if (!executor.transcribe(req, result, error, [this](const protocol::JobEvent& event) {
                    emit_event(event);
                })) {
                throw std::runtime_error(error);
            }
            if (options_.verbose) {
                std::cout << "chunked transcribe finished: " << req.job_id
                          << ", chunk_count=" << result.chunk_count
                          << ", runtime_count=" << result.runtime_count
                          << ", effective_parallel_chunks="
                          << result.effective_parallel_chunks
                          << ", chunk_threads=" << result.chunk_threads << std::endl;
            }
        } else {
            auto lease = runtime_pool_.acquire();
            if (!lease.runtime().is_loaded()) {
                throw std::runtime_error("model not initialized");
            }
            if (options_.verbose) {
                std::cout << "whisper transcribe started: " << req.job_id
                          << ", runtime_slot=" << lease.slot_index() << std::endl;
            }
            if (!lease.runtime().transcribe(req, result, error)) {
                throw std::runtime_error(error);
            }
            result.runtime_count = static_cast<int>(runtime_pool_.runtime_count());
            if (options_.verbose) {
                std::cout << "whisper transcribe finished: " << req.job_id
                          << ", runtime_slot=" << lease.slot_index() << std::endl;
            }
        }

        protocol::JobEvent completed;
        completed.job_id = req.job_id;
        completed.status = "job_completed";
        completed.progress = 1.0;
        completed.current_seconds = result.duration_seconds;
        completed.total_seconds = result.duration_seconds;
        emit_event(completed);

        (void)job_manager_.mark_completed(result);
        emit_result(result);
    } catch (const std::exception& exc) {
        protocol::JobEvent failed;
        failed.job_id = req.job_id;
        failed.status = "job_failed";
        failed.progress = 1.0;
        emit_event(failed);

        protocol::JobError error;
        error.job_id = req.job_id;
        error.code = "job_failed";
        error.message = exc.what();
        (void)job_manager_.mark_failed(req.job_id, error.message);
        emit_error(error);
    }
}

void WorkerPool::emit_event(const protocol::JobEvent& event) {
    if (callbacks_.on_event) {
        callbacks_.on_event(event);
    }
}

void WorkerPool::emit_result(const protocol::JobResult& result) {
    if (callbacks_.on_result) {
        callbacks_.on_result(result);
    }
}

void WorkerPool::emit_error(const protocol::JobError& error) {
    if (callbacks_.on_error) {
        callbacks_.on_error(error);
    }
}

} // namespace flowscribe::engine::core
