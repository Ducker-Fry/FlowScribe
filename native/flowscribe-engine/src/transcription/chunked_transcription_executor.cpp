#include "flowscribe/engine/transcription/chunked_transcription_executor.h"

#include "flowscribe/engine/transcription/transcript_assembler.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <exception>
#include <mutex>
#include <thread>
#include <vector>

#include "whisper.h"

namespace flowscribe::engine::transcription {

namespace {

std::vector<protocol::TranscriptSegment> adjusted_chunk_segments(
    const protocol::JobResult& chunk_result,
    const AudioChunk& chunk) {
    std::vector<protocol::TranscriptSegment> adjusted;
    adjusted.reserve(chunk_result.segments.size());

    const double local_content_start = chunk.content_start_seconds - chunk.start_seconds;
    for (auto segment : chunk_result.segments) {
        if (chunk.index > 1) {
            if (segment.end <= local_content_start) {
                continue;
            }
            if (segment.start < local_content_start) {
                segment.start = local_content_start;
            }
        }

        segment.start += chunk.start_seconds;
        segment.end += chunk.start_seconds;

        std::vector<protocol::WordTiming> adjusted_words;
        adjusted_words.reserve(segment.words.size());
        for (auto word : segment.words) {
            if (chunk.index > 1) {
                if (word.end <= local_content_start) {
                    continue;
                }
                if (word.start < local_content_start) {
                    word.start = local_content_start;
                }
            }
            word.start += chunk.start_seconds;
            word.end += chunk.start_seconds;
            adjusted_words.push_back(std::move(word));
        }
        segment.words = std::move(adjusted_words);
        adjusted.push_back(std::move(segment));
    }

    std::sort(adjusted.begin(), adjusted.end(), [](const auto& left, const auto& right) {
        if (left.start == right.start) {
            return left.end < right.end;
        }
        return left.start < right.start;
    });
    return adjusted;
}

} // namespace

ChunkedTranscriptionExecutor::ChunkedTranscriptionExecutor(RuntimePool& runtime_pool)
    : runtime_pool_(runtime_pool) {
}

bool ChunkedTranscriptionExecutor::transcribe(
    const protocol::SubmitJobRequest& req,
    protocol::JobResult& out,
    std::string& error,
    std::function<void(const protocol::JobEvent&)> event_callback) const {
    error.clear();
    out = {};
    out.job_id = req.job_id;

    std::vector<float> pcmf32;
    if (!WhisperRuntime::read_pcm(req.audio_path, pcmf32, error)) {
        return false;
    }

    ChunkPlanner planner;
    ChunkPlan plan;
    try {
        plan = planner.plan(
            pcmf32.size(),
            WHISPER_SAMPLE_RATE,
            req.progressive.chunk_seconds,
            req.progressive.overlap_seconds);
    } catch (const std::exception& exc) {
        error = exc.what();
        return false;
    }

    if (plan.chunks.empty()) {
        error = "audio contains no samples";
        return false;
    }

    const size_t parallel_chunks =
        effective_parallel_chunks(plan.chunks.size(), req.progressive.max_workers);
    const int chunk_threads = resolve_chunk_threads(req, parallel_chunks);
    if (event_callback) {
        protocol::JobEvent event;
        event.job_id = req.job_id;
        event.status = "chunks_planned";
        event.progress = 0.0;
        event.current_seconds = 0.0;
        event.total_seconds = plan.duration_seconds;
        event.chunk_count = static_cast<int>(plan.chunks.size());
        event_callback(event);
    }
    std::atomic<size_t> next_index{0};
    std::atomic<int> completed_chunks{0};
    std::mutex results_mutex;
    std::vector<ChunkTranscriptionResult> results;
    results.reserve(plan.chunks.size());
    std::vector<protocol::ChunkMetric> chunk_metrics;
    chunk_metrics.reserve(plan.chunks.size());
    std::string first_error;
    std::mutex error_mutex;

    auto worker = [&] {
        while (true) {
            const size_t chunk_pos = next_index.fetch_add(1);
            if (chunk_pos >= plan.chunks.size()) {
                return;
            }

            {
                std::lock_guard<std::mutex> lock(error_mutex);
                if (!first_error.empty()) {
                    return;
                }
            }

            const auto chunk = plan.chunks[chunk_pos];
            std::vector<float> slice(
                pcmf32.begin() + static_cast<std::ptrdiff_t>(chunk.sample_start),
                pcmf32.begin() + static_cast<std::ptrdiff_t>(chunk.sample_end));

            protocol::JobResult chunk_result;
            std::string chunk_error;
            protocol::ChunkMetric metric;
            metric.index = chunk.index;
            metric.start = chunk.start_seconds;
            metric.end = chunk.end_seconds;
            metric.threads = chunk_threads;

            const auto acquire_started = std::chrono::steady_clock::now();
            auto lease = runtime_pool_.acquire();
            const auto transcribe_started = std::chrono::steady_clock::now();
            metric.acquire_wait_seconds =
                std::chrono::duration<double>(transcribe_started - acquire_started).count();
            metric.runtime_slot = static_cast<int>(lease.slot_index());

            if (event_callback) {
                protocol::JobEvent event;
                event.job_id = req.job_id;
                event.status = "chunk_started";
                event.progress = static_cast<double>(completed_chunks.load()) /
                    static_cast<double>(plan.chunks.size());
                event.current_seconds = chunk.content_start_seconds;
                event.total_seconds = plan.duration_seconds;
                event.chunk_index = chunk.index;
                event.chunk_count = static_cast<int>(plan.chunks.size());
                event.completed_chunks = completed_chunks.load();
                event.runtime_slot = metric.runtime_slot;
                event_callback(event);
            }

            if (!lease.runtime().transcribe_pcm(req, slice, chunk_threads, chunk_result, chunk_error)) {
                std::lock_guard<std::mutex> lock(error_mutex);
                if (first_error.empty()) {
                    first_error = "chunk " + std::to_string(chunk.index) + " failed: " + chunk_error;
                }
                return;
            }
            const auto finished = std::chrono::steady_clock::now();
            metric.elapsed_seconds = std::chrono::duration<double>(finished - transcribe_started).count();
            auto event_segments = adjusted_chunk_segments(chunk_result, chunk);

            std::lock_guard<std::mutex> lock(results_mutex);
            results.push_back(ChunkTranscriptionResult{chunk, std::move(chunk_result)});
            chunk_metrics.push_back(metric);
            const int done = completed_chunks.fetch_add(1) + 1;
            if (event_callback) {
                protocol::JobEvent event;
                event.job_id = req.job_id;
                event.status = "chunk_completed";
                event.progress = static_cast<double>(done) / static_cast<double>(plan.chunks.size());
                event.current_seconds = chunk.end_seconds;
                event.total_seconds = plan.duration_seconds;
                event.chunk_index = chunk.index;
                event.chunk_count = static_cast<int>(plan.chunks.size());
                event.completed_chunks = done;
                event.runtime_slot = metric.runtime_slot;
                event.segments = std::move(event_segments);
                event_callback(event);
            }
        }
    };

    std::vector<std::thread> workers;
    workers.reserve(parallel_chunks);
    for (size_t i = 0; i < parallel_chunks; ++i) {
        workers.emplace_back(worker);
    }
    for (auto& thread : workers) {
        if (thread.joinable()) {
            thread.join();
        }
    }

    if (!first_error.empty()) {
        error = first_error;
        return false;
    }
    if (results.size() != plan.chunks.size()) {
        error = "chunked transcription did not complete all chunks";
        return false;
    }

    TranscriptAssembler assembler;
    out = assembler.assemble(
        req.job_id,
        plan,
        std::move(results),
        runtime_pool_.runtime_count(),
        parallel_chunks,
        chunk_threads,
        std::move(chunk_metrics));
    return true;
}

size_t ChunkedTranscriptionExecutor::effective_parallel_chunks(
    size_t chunk_count,
    int requested_workers) const {
    const size_t runtime_count = runtime_pool_.runtime_count();
    const size_t worker_limit =
        requested_workers <= 0 ? runtime_count : static_cast<size_t>(requested_workers);
    return std::max<size_t>(1, std::min({chunk_count, runtime_count, worker_limit}));
}

int ChunkedTranscriptionExecutor::resolve_chunk_threads(
    const protocol::SubmitJobRequest& req,
    size_t parallel_chunks) const {
    if (req.threads > 0) {
        return req.threads;
    }

    const unsigned int hardware_threads = std::max(1u, std::thread::hardware_concurrency());
    const size_t divisor = std::max<size_t>(1, parallel_chunks);
    const size_t shared_threads =
        std::max<size_t>(1, static_cast<size_t>(hardware_threads) / divisor);
    return static_cast<int>(std::min<size_t>(8, shared_threads));
}

} // namespace flowscribe::engine::transcription
