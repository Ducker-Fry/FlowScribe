#pragma once

#include "flowscribe/engine/protocol/message.h"
#include "flowscribe/engine/transcription/chunk_planner.h"
#include "flowscribe/engine/transcription/runtime_pool.h"

#include <cstddef>
#include <functional>
#include <string>

namespace flowscribe::engine::transcription {

class ChunkedTranscriptionExecutor {
public:
    explicit ChunkedTranscriptionExecutor(RuntimePool& runtime_pool);

    bool transcribe(
        const protocol::SubmitJobRequest& req,
        protocol::JobResult& out,
        std::string& error,
        std::function<void(const protocol::JobEvent&)> event_callback = {}) const;

private:
    size_t effective_parallel_chunks(size_t chunk_count, int requested_workers) const;
    int resolve_chunk_threads(const protocol::SubmitJobRequest& req, size_t parallel_chunks) const;

    RuntimePool& runtime_pool_;
};

} // namespace flowscribe::engine::transcription
