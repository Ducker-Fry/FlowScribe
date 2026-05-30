#include "flowscribe/engine/protocol/codec.h"
#include "flowscribe/engine/transcription/chunk_planner.h"
#include "flowscribe/engine/transcription/runtime_pool.h"
#include "flowscribe/engine/transcription/transcript_assembler.h"

#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

using flowscribe::engine::protocol::CancelJobRequest;
using flowscribe::engine::protocol::FRAME_HEADER_SIZE;
using flowscribe::engine::protocol::HelloRequest;
using flowscribe::engine::protocol::JobResult;
using flowscribe::engine::protocol::Message;
using flowscribe::engine::protocol::MessageKindRegistry;
using flowscribe::engine::protocol::MessageKind;
using flowscribe::engine::protocol::SubmitJobRequest;
using flowscribe::engine::protocol::TranscriptSegment;
using flowscribe::engine::protocol::WordTiming;
using flowscribe::engine::protocol::decode_frame_header;
using flowscribe::engine::protocol::decode_message;
using flowscribe::engine::protocol::encode_message;
using flowscribe::engine::protocol::is_known_message_kind;
using flowscribe::engine::protocol::make_message;
using flowscribe::engine::protocol::message_kind_to_str;
using nlohmann::json;

namespace {

void require(bool condition, const char* message) {
    if (!condition) {
        std::cerr << message << '\n';
        std::exit(1);
    }
}

void test_frame_round_trip() {
    const Message msg = make_message(MessageKind::HelloRequest, R"({"client_id":"test-client"})");
    const std::vector<uint8_t> bytes = encode_message(msg);

    require(bytes.size() == FRAME_HEADER_SIZE + msg.json_payload.size(), "encoded size mismatch");

    flowscribe::engine::protocol::FrameHeader header;
    require(decode_frame_header(bytes, header), "failed to decode frame header");
    require(header.payload_len == msg.json_payload.size(), "payload length mismatch");
    require(header.kind == MessageKind::HelloRequest, "message kind mismatch");

    Message decoded;
    std::string error;
    require(decode_message(bytes, decoded, error), "failed to decode full message");
    require(decoded.json_payload == msg.json_payload, "payload mismatch");
}

void test_json_round_trip() {
    SubmitJobRequest request;
    request.job_id = "job-1";
    request.audio_path = "D:/media/audio.wav";
    request.language = "zh";
    request.task = "transcribe";
    request.vad_filter = true;
    request.beam_size = 8;
    request.threads = 12;
    request.initial_prompt = "domain words";
    request.progressive.enabled = true;
    request.progressive.chunk_seconds = 30.0;
    request.progressive.overlap_seconds = 3.0;
    request.progressive.max_workers = 0;

    const json encoded = request;
    const SubmitJobRequest decoded = encoded.get<SubmitJobRequest>();

    require(decoded.job_id == request.job_id, "submit job_id mismatch");
    require(decoded.audio_path == request.audio_path, "submit audio_path mismatch");
    require(decoded.vad_filter == request.vad_filter, "submit vad_filter mismatch");
    require(decoded.beam_size == request.beam_size, "submit beam_size mismatch");
    require(decoded.threads == request.threads, "submit threads mismatch");
    require(decoded.progressive.chunk_seconds == request.progressive.chunk_seconds,
            "submit progressive chunk mismatch");
    require(decoded.progressive.max_workers == 0, "submit progressive max_workers mismatch");
}

void test_chunk_planner_boundaries() {
    flowscribe::engine::transcription::ChunkPlanner planner;
    const auto plan = planner.plan(1903ull * 16000ull, 16000, 120.0, 5.0);

    require(plan.chunks.size() == 17, "planner chunk count mismatch");
    require(plan.chunks.front().sample_start == 0, "first sample start mismatch");
    require(plan.chunks.front().sample_end == 120ull * 16000ull, "first sample end mismatch");
    require(plan.chunks[1].sample_start == 115ull * 16000ull, "second sample start mismatch");
    require(plan.chunks[1].content_start_seconds == 120.0, "second content start mismatch");
    require(plan.chunks.back().end_seconds == 1903.0, "last chunk end mismatch");
    require(plan.chunks.back().sample_end == 1903ull * 16000ull, "last sample end mismatch");
}

void test_transcript_assembler_overlap_policy() {
    using flowscribe::engine::protocol::JobResult;
    using flowscribe::engine::protocol::ChunkMetric;
    using flowscribe::engine::protocol::TranscriptSegment;
    using flowscribe::engine::transcription::AudioChunk;
    using flowscribe::engine::transcription::ChunkPlan;
    using flowscribe::engine::transcription::ChunkTranscriptionResult;
    using flowscribe::engine::transcription::TranscriptAssembler;

    ChunkPlan plan;
    plan.duration_seconds = 20.0;
    plan.chunk_seconds = 10.0;
    plan.overlap_seconds = 2.0;
    plan.chunks = {
        AudioChunk{1, 0.0, 10.0, 0.0, 0, 10},
        AudioChunk{2, 8.0, 18.0, 10.0, 8, 18},
    };

    JobResult first;
    first.segments = {
        TranscriptSegment{0, 1.0, 3.0, "keep"},
        TranscriptSegment{1, 9.0, 10.5, "dup"},
    };
    JobResult second;
    second.segments = {
        TranscriptSegment{0, 0.5, 1.5, "drop-overlap"},
        TranscriptSegment{1, 1.5, 2.8, "dup"},
        TranscriptSegment{2, 4.0, 5.0, "later"},
    };

    const auto merged = TranscriptAssembler().assemble(
        "job-1",
        plan,
        {ChunkTranscriptionResult{plan.chunks[0], first}, ChunkTranscriptionResult{plan.chunks[1], second}},
        2,
        2,
        8,
        {ChunkMetric{2, 8.0, 18.0, 1, 0.01, 2.0, 8}, ChunkMetric{1, 0.0, 10.0, 0, 0.0, 1.5, 8}});

    require(merged.segments.size() == 3, "assembler segment count mismatch");
    require(merged.segments[0].text == "keep", "assembler first segment mismatch");
    require(merged.segments[1].text == "dup", "assembler duplicate filter mismatch");
    require(merged.segments[2].start == 12.0, "assembler offset mismatch");
    require(merged.chunk_count == 2, "assembler chunk metadata mismatch");
    require(merged.chunk_threads == 8, "assembler chunk threads mismatch");
    require(merged.chunk_metrics.size() == 2, "assembler metrics count mismatch");
    require(merged.chunk_metrics[0].index == 1, "assembler metrics sort mismatch");
}

void test_runtime_pool_auto_policy() {
    using flowscribe::engine::transcription::RuntimeModelConfig;
    using flowscribe::engine::transcription::RuntimePool;
    using flowscribe::engine::transcription::RuntimePoolOptions;

    RuntimePoolOptions options;
    options.max_runtime_count = 0;
    RuntimePool pool(options);

    const auto base = pool.plan_runtime_count(RuntimeModelConfig{"ggml-base.en", "", false});
    const auto small = pool.plan_runtime_count(RuntimeModelConfig{"ggml-small.en", "", false});

    require(base.desired_count == 3, "base desired runtime count mismatch");
    require(small.desired_count == 2, "small desired runtime count mismatch");
}

void test_submit_job_threads_default_is_auto() {
    const json payload = {
        {"job_id", "job-1"},
        {"audio_path", "D:/media/audio.wav"},
    };
    const SubmitJobRequest decoded = payload.get<SubmitJobRequest>();

    require(decoded.threads == 0, "missing submit threads should default to auto");
}

void test_transcript_round_trip() {
    JobResult result;
    result.job_id = "job-1";
    result.duration_seconds = 12.5;

    TranscriptSegment segment;
    segment.id = 1;
    segment.start = 0.5;
    segment.end = 2.0;
    segment.text = "hello world";
    segment.words.push_back(WordTiming{"hello", 0.5, 1.0});
    segment.words.push_back(WordTiming{"world", 1.1, 2.0});
    result.segments.push_back(segment);

    const json encoded = result;
    const JobResult decoded = encoded.get<JobResult>();

    require(decoded.job_id == result.job_id, "job result id mismatch");
    require(decoded.segments.size() == 1, "segment count mismatch");
    require(decoded.segments[0].words.size() == 2, "word count mismatch");
    require(decoded.segments[0].text == segment.text, "segment text mismatch");
}

void test_decode_rejects_bad_frame() {
    const Message msg = make_message(MessageKind::CancelJobRequest, R"({"job_id":"job-1"})");
    std::vector<uint8_t> bytes = encode_message(msg);
    bytes.pop_back();

    Message decoded;
    std::string error;
    require(!decode_message(bytes, decoded, error), "truncated message should fail");
    require(!error.empty(), "decode error should be populated");
}

void test_message_kind_registry() {
    require(is_known_message_kind(MessageKind::SubmitJobRequest), "submit job kind should be known");
    require(std::string(message_kind_to_str(MessageKind::SubmitJobRequest)) == "submit_job_request",
            "submit job kind name mismatch");
    require(MessageKindRegistry::instance().from_str("job_result") == MessageKind::JobResult,
            "job_result reverse mapping mismatch");
    require(!is_known_message_kind(static_cast<MessageKind>(0xFFFF)), "unknown kind should be rejected");
    require(std::string(message_kind_to_str(static_cast<MessageKind>(0xFFFF))) == "unknown",
            "unknown kind string mismatch");
}

} // namespace

int main() {
    (void)sizeof(HelloRequest);
    (void)sizeof(CancelJobRequest);

    test_frame_round_trip();
    test_json_round_trip();
    test_chunk_planner_boundaries();
    test_transcript_assembler_overlap_policy();
    test_runtime_pool_auto_policy();
    test_submit_job_threads_default_is_auto();
    test_transcript_round_trip();
    test_decode_rejects_bad_frame();
    test_message_kind_registry();

    return 0;
}
