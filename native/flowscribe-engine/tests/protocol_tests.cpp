#include "flowscribe/engine/protocol/codec.h"

#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

using flowscribe::engine::protocol::CancelJobRequest;
using flowscribe::engine::protocol::FRAME_HEADER_SIZE;
using flowscribe::engine::protocol::HelloRequest;
using flowscribe::engine::protocol::JobResult;
using flowscribe::engine::protocol::Message;
using flowscribe::engine::protocol::MessageKind;
using flowscribe::engine::protocol::SubmitJobRequest;
using flowscribe::engine::protocol::TranscriptSegment;
using flowscribe::engine::protocol::WordTiming;
using flowscribe::engine::protocol::decode_frame_header;
using flowscribe::engine::protocol::decode_message;
using flowscribe::engine::protocol::encode_message;
using flowscribe::engine::protocol::make_message;
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
    request.initial_prompt = "domain words";
    request.progressive.enabled = true;
    request.progressive.chunk_seconds = 30.0;
    request.progressive.overlap_seconds = 3.0;

    const json encoded = request;
    const SubmitJobRequest decoded = encoded.get<SubmitJobRequest>();

    require(decoded.job_id == request.job_id, "submit job_id mismatch");
    require(decoded.audio_path == request.audio_path, "submit audio_path mismatch");
    require(decoded.vad_filter == request.vad_filter, "submit vad_filter mismatch");
    require(decoded.beam_size == request.beam_size, "submit beam_size mismatch");
    require(decoded.progressive.chunk_seconds == request.progressive.chunk_seconds,
            "submit progressive chunk mismatch");
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

} // namespace

int main() {
    (void)sizeof(HelloRequest);
    (void)sizeof(CancelJobRequest);

    test_frame_round_trip();
    test_json_round_trip();
    test_transcript_round_trip();
    test_decode_rejects_bad_frame();

    return 0;
}
