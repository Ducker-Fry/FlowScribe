#include "flowscribe/engine/transcription/transcript_assembler.h"

#include <algorithm>

namespace flowscribe::engine::transcription {

namespace {

bool text_equal(const std::string& left, const std::string& right) {
    return left == right;
}

bool overlaps(const protocol::TranscriptSegment& left, const protocol::TranscriptSegment& right) {
    return left.start < right.end && right.start < left.end;
}

} // namespace

protocol::JobResult TranscriptAssembler::assemble(
    const std::string& job_id,
    const ChunkPlan& plan,
    std::vector<ChunkTranscriptionResult> chunk_results,
    size_t runtime_count,
    size_t effective_parallel_chunks,
    int chunk_threads,
    std::vector<protocol::ChunkMetric> chunk_metrics) const {
    std::sort(chunk_results.begin(), chunk_results.end(), [](const auto& left, const auto& right) {
        return left.chunk.index < right.chunk.index;
    });

    protocol::JobResult out;
    out.job_id = job_id;
    out.duration_seconds = plan.duration_seconds;
    out.chunked_enabled = true;
    out.chunk_count = static_cast<int>(plan.chunks.size());
    out.runtime_count = static_cast<int>(runtime_count);
    out.effective_parallel_chunks = static_cast<int>(effective_parallel_chunks);
    out.chunk_threads = chunk_threads;
    out.chunk_seconds = plan.chunk_seconds;
    out.overlap_seconds = plan.overlap_seconds;
    std::sort(chunk_metrics.begin(), chunk_metrics.end(), [](const auto& left, const auto& right) {
        return left.index < right.index;
    });
    out.chunk_metrics = std::move(chunk_metrics);

    for (const auto& chunk_result : chunk_results) {
        const auto& chunk = chunk_result.chunk;
        for (auto segment : chunk_result.result.segments) {
            const double local_content_start = chunk.content_start_seconds - chunk.start_seconds;
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
            out.segments.push_back(std::move(segment));
        }
    }

    std::sort(out.segments.begin(), out.segments.end(), [](const auto& left, const auto& right) {
        if (left.start == right.start) {
            return left.end < right.end;
        }
        return left.start < right.start;
    });

    std::vector<protocol::TranscriptSegment> filtered;
    filtered.reserve(out.segments.size());
    for (auto& segment : out.segments) {
        if (!filtered.empty() &&
            text_equal(filtered.back().text, segment.text) &&
            overlaps(filtered.back(), segment)) {
            continue;
        }
        segment.id = static_cast<int>(filtered.size());
        filtered.push_back(std::move(segment));
    }
    out.segments = std::move(filtered);
    return out;
}

} // namespace flowscribe::engine::transcription
