#pragma once

#include "flowscribe/engine/protocol/message.h"
#include "flowscribe/engine/transcription/chunk_planner.h"

#include <vector>

namespace flowscribe::engine::transcription {

struct ChunkTranscriptionResult {
    AudioChunk chunk;
    protocol::JobResult result;
};

class TranscriptAssembler {
public:
    protocol::JobResult assemble(
        const std::string& job_id,
        const ChunkPlan& plan,
        std::vector<ChunkTranscriptionResult> chunk_results,
        size_t runtime_count,
        size_t effective_parallel_chunks,
        int chunk_threads,
        std::vector<protocol::ChunkMetric> chunk_metrics) const;
};

} // namespace flowscribe::engine::transcription
