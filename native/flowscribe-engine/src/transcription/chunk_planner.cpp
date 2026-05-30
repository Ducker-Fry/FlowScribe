#include "flowscribe/engine/transcription/chunk_planner.h"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace flowscribe::engine::transcription {

ChunkPlan ChunkPlanner::plan(
    size_t sample_count,
    int sample_rate,
    double chunk_seconds,
    double overlap_seconds) const {
    if (sample_rate <= 0) {
        throw std::invalid_argument("sample_rate must be greater than zero");
    }
    if (chunk_seconds <= 0.0) {
        throw std::invalid_argument("chunk_seconds must be greater than zero");
    }
    if (overlap_seconds < 0.0) {
        throw std::invalid_argument("overlap_seconds cannot be negative");
    }
    if (overlap_seconds >= chunk_seconds) {
        throw std::invalid_argument("overlap_seconds must be smaller than chunk_seconds");
    }

    ChunkPlan result;
    result.duration_seconds = static_cast<double>(sample_count) / static_cast<double>(sample_rate);
    result.chunk_seconds = chunk_seconds;
    result.overlap_seconds = overlap_seconds;
    result.sample_rate = sample_rate;
    if (sample_count == 0) {
        return result;
    }

    const double step_seconds = chunk_seconds - overlap_seconds;
    double start = 0.0;
    int index = 1;
    while (start < result.duration_seconds) {
        const double end = std::min(result.duration_seconds, start + chunk_seconds);
        AudioChunk chunk;
        chunk.index = index;
        chunk.start_seconds = start;
        chunk.end_seconds = end;
        chunk.content_start_seconds = index == 1 ? start : start + overlap_seconds;
        chunk.sample_start = std::min(
            sample_count,
            static_cast<size_t>(std::floor(start * static_cast<double>(sample_rate))));
        chunk.sample_end = std::min(
            sample_count,
            static_cast<size_t>(std::ceil(end * static_cast<double>(sample_rate))));
        result.chunks.push_back(chunk);

        if (end >= result.duration_seconds) {
            break;
        }
        start += step_seconds;
        ++index;
    }
    return result;
}

} // namespace flowscribe::engine::transcription
