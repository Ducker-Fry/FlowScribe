#pragma once

#include <string>
#include <vector>

#include "flowscribe/engine/protocol/message.h"

struct whisper_context;

namespace flowscribe::engine::transcription {

class WhisperRuntime {
public:
    WhisperRuntime() = default;
    ~WhisperRuntime();

    WhisperRuntime(const WhisperRuntime&) = delete;
    WhisperRuntime& operator=(const WhisperRuntime&) = delete;

    bool load_model(const std::string& model_path, bool use_gpu, std::string& error);
    bool is_loaded() const;
    bool transcribe(
        const protocol::SubmitJobRequest& req,
        protocol::JobResult& out,
        std::string& error);
    bool transcribe_pcm(
        const protocol::SubmitJobRequest& req,
        const std::vector<float>& pcmf32,
        protocol::JobResult& out,
        std::string& error);
    bool transcribe_pcm(
        const protocol::SubmitJobRequest& req,
        const std::vector<float>& pcmf32,
        int thread_count,
        protocol::JobResult& out,
        std::string& error);

    static bool read_pcm(
        const std::string& audio_path,
        std::vector<float>& pcmf32,
        std::string& error);

private:
    void reset();

    whisper_context* ctx_ = nullptr;
};

} // namespace flowscribe::engine::transcription
