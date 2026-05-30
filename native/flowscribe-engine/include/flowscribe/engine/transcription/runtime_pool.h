#pragma once

#include "flowscribe/engine/transcription/whisper_runtime.h"

#include <condition_variable>
#include <cstdint>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

namespace flowscribe::engine::transcription {

struct RuntimeModelConfig {
    std::string model_name;
    std::string model_path;
    bool use_gpu = false;
};

struct RuntimePoolOptions {
    size_t max_runtime_count = 0;
    bool verbose = false;
    double model_memory_multiplier = 2.0;
    uintmax_t decode_buffer_margin_bytes = 512ull * 1024ull * 1024ull;
};

struct RuntimePoolPlan {
    size_t desired_count = 1;
    size_t allowed_count = 1;
    size_t final_count = 1;
    uintmax_t estimated_runtime_memory_bytes = 0;
};

struct RuntimePoolLoadResult {
    bool ok = false;
    std::string error;
    size_t runtime_count = 0;
    RuntimePoolPlan plan;
};

class RuntimePool;

struct RuntimeSlot {
    size_t index = 0;
    std::unique_ptr<WhisperRuntime> runtime;
    bool in_use = false;
};

class RuntimeLease {
public:
    RuntimeLease() = default;
    ~RuntimeLease();

    RuntimeLease(const RuntimeLease&) = delete;
    RuntimeLease& operator=(const RuntimeLease&) = delete;

    RuntimeLease(RuntimeLease&& other) noexcept;
    RuntimeLease& operator=(RuntimeLease&& other) noexcept;

    WhisperRuntime& runtime() const;
    bool valid() const;
    size_t slot_index() const;
    void release();

private:
    friend class RuntimePool;

    RuntimeLease(RuntimePool* pool, RuntimeSlot* slot);

    RuntimePool* pool_ = nullptr;
    RuntimeSlot* slot_ = nullptr;
};

class RuntimePool {
public:
    explicit RuntimePool(RuntimePoolOptions options = {});
    ~RuntimePool();

    RuntimePool(const RuntimePool&) = delete;
    RuntimePool& operator=(const RuntimePool&) = delete;

    RuntimePoolLoadResult load_model(const RuntimeModelConfig& config);
    RuntimePoolLoadResult load_mock_model();
    RuntimeLease acquire();
    void clear();

    bool is_loaded() const;
    bool is_mock_model() const;
    size_t runtime_count() const;
    RuntimePoolPlan last_plan() const;
    RuntimePoolPlan plan_runtime_count(const RuntimeModelConfig& config) const;

private:
    friend class RuntimeLease;

    size_t model_size_policy(const std::string& model_name, const std::string& model_path) const;
    size_t memory_policy(uintmax_t estimated_runtime_memory_bytes) const;
    uintmax_t estimate_runtime_memory_bytes(const std::string& model_path) const;
    uintmax_t available_physical_memory_bytes() const;
    void release(RuntimeSlot* slot);

    RuntimePoolOptions options_;
    mutable std::mutex mutex_;
    std::condition_variable cv_;
    std::vector<std::unique_ptr<RuntimeSlot>> slots_;
    RuntimePoolPlan last_plan_;
    size_t active_leases_ = 0;
    bool loading_ = false;
    bool loaded_ = false;
    bool mock_model_ = false;
};

} // namespace flowscribe::engine::transcription
