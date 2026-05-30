#include "flowscribe/engine/transcription/whisper_runtime.h"

#include "common-whisper.h"
#include "whisper.h"

#include <algorithm>
#include <string>
#include <thread>
#include <vector>

namespace flowscribe::engine::transcription {

WhisperRuntime::~WhisperRuntime() {
    reset();
}

bool WhisperRuntime::load_model(
    const std::string& model_path,
    bool use_gpu,
    std::string& error) {
    error.clear();
    reset();

    whisper_context_params params = whisper_context_default_params();
    params.use_gpu = use_gpu;

    ctx_ = whisper_init_from_file_with_params(model_path.c_str(), params);
    if (ctx_ == nullptr) {
        error = "failed to load whisper model";
        return false;
    }

    return true;
}

bool WhisperRuntime::is_loaded() const {
    return ctx_ != nullptr;
}

bool WhisperRuntime::transcribe(
    const protocol::SubmitJobRequest& req,
    protocol::JobResult& out,
    std::string& error) {
    std::vector<float> pcmf32;
    if (!read_pcm(req.audio_path, pcmf32, error)) {
        return false;
    }
    return transcribe_pcm(req, pcmf32, out, error);
}

bool WhisperRuntime::read_pcm(
    const std::string& audio_path,
    std::vector<float>& pcmf32,
    std::string& error) {
    error.clear();
    pcmf32.clear();
    std::vector<std::vector<float>> pcmf32s;
    if (!read_audio_data(audio_path, pcmf32, pcmf32s, false)) {
        error = "failed to read audio data; expected a readable WAV/audio file";
        return false;
    }

    if (pcmf32.empty()) {
        error = "audio contains no samples";
        return false;
    }
    return true;
}

bool WhisperRuntime::transcribe_pcm(
    const protocol::SubmitJobRequest& req,
    const std::vector<float>& pcmf32,
    protocol::JobResult& out,
    std::string& error) {
    const unsigned int automatic_threads = std::max(1u, std::thread::hardware_concurrency());
    const int thread_count = req.threads > 0 ? req.threads : static_cast<int>(automatic_threads);
    return transcribe_pcm(req, pcmf32, thread_count, out, error);
}

bool WhisperRuntime::transcribe_pcm(
    const protocol::SubmitJobRequest& req,
    const std::vector<float>& pcmf32,
    int thread_count,
    protocol::JobResult& out,
    std::string& error) {
    error.clear();
    out = {};
    out.job_id = req.job_id;

    if (ctx_ == nullptr) {
        error = "model is not loaded";
        return false;
    }

    if (pcmf32.empty()) {
        error = "audio contains no samples";
        return false;
    }

    whisper_sampling_strategy strategy = WHISPER_SAMPLING_GREEDY;
    if (req.beam_size > 1) {
        strategy = WHISPER_SAMPLING_BEAM_SEARCH;
    }

    whisper_full_params params = whisper_full_default_params(strategy);
    params.print_realtime = false;
    params.print_progress = false;
    params.print_timestamps = false;
    params.print_special = false;
    params.translate = req.task == "translate";
    params.language = req.language.empty() || req.language == "auto" ? nullptr : req.language.c_str();
    params.initial_prompt = req.initial_prompt.empty() ? nullptr : req.initial_prompt.c_str();
    params.n_threads = std::max(1, thread_count);
    params.beam_search.beam_size = std::max(1, req.beam_size);

    if (whisper_full(ctx_, params, pcmf32.data(), static_cast<int>(pcmf32.size())) != 0) {
        error = "whisper_full failed";
        return false;
    }

    const int segment_count = whisper_full_n_segments(ctx_);
    out.segments.reserve(static_cast<size_t>(std::max(0, segment_count)));

    for (int i = 0; i < segment_count; ++i) {
        protocol::TranscriptSegment segment;
        segment.id = i;
        segment.start = static_cast<double>(whisper_full_get_segment_t0(ctx_, i)) / 100.0;
        segment.end = static_cast<double>(whisper_full_get_segment_t1(ctx_, i)) / 100.0;

        const char* text = whisper_full_get_segment_text(ctx_, i);
        segment.text = text != nullptr ? text : "";

        out.duration_seconds = std::max(out.duration_seconds, segment.end);
        out.segments.push_back(std::move(segment));
    }

    if (out.duration_seconds <= 0.0) {
        out.duration_seconds = static_cast<double>(pcmf32.size()) / WHISPER_SAMPLE_RATE;
    }

    return true;
}

void WhisperRuntime::reset() {
    if (ctx_ != nullptr) {
        whisper_free(ctx_);
        ctx_ = nullptr;
    }
}

} // namespace flowscribe::engine::transcription
