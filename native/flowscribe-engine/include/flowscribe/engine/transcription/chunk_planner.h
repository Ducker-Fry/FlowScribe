#pragma once

#include <cstddef>
#include <vector>

namespace flowscribe::engine::transcription {

struct AudioChunk {
    int index = 1;
    double start_seconds = 0.0;
    double end_seconds = 0.0;
    double content_start_seconds = 0.0;
    size_t sample_start = 0;
    size_t sample_end = 0;
};

struct ChunkPlan {
    double duration_seconds = 0.0;
    double chunk_seconds = 0.0;
    double overlap_seconds = 0.0;
    int sample_rate = 16000;
    std::vector<AudioChunk> chunks;
};

class ChunkPlanner {
public:
    ChunkPlan plan(
        size_t sample_count,
        int sample_rate,
        double chunk_seconds,
        double overlap_seconds) const;
};

} // namespace flowscribe::engine::transcription
