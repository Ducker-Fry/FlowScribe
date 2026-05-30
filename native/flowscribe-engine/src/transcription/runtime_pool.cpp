#include "flowscribe/engine/transcription/runtime_pool.h"

#include <algorithm>
#include <cctype>
#include <filesystem>
#include <iostream>
#include <stdexcept>

#ifdef _WIN32
#include <windows.h>
#endif

namespace flowscribe::engine::transcription {

namespace {

std::string lowercase(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    return value;
}

} // namespace

RuntimeLease::RuntimeLease(RuntimePool* pool, RuntimeSlot* slot)
    : pool_(pool),
      slot_(slot) {
}

RuntimeLease::~RuntimeLease() {
    release();
}

RuntimeLease::RuntimeLease(RuntimeLease&& other) noexcept
    : pool_(other.pool_),
      slot_(other.slot_) {
    other.pool_ = nullptr;
    other.slot_ = nullptr;
}

RuntimeLease& RuntimeLease::operator=(RuntimeLease&& other) noexcept {
    if (this != &other) {
        release();
        pool_ = other.pool_;
        slot_ = other.slot_;
        other.pool_ = nullptr;
        other.slot_ = nullptr;
    }
    return *this;
}

WhisperRuntime& RuntimeLease::runtime() const {
    if (!slot_ || !slot_->runtime) {
        throw std::runtime_error("runtime lease is not valid");
    }
    return *slot_->runtime;
}

bool RuntimeLease::valid() const {
    return slot_ != nullptr && slot_->runtime != nullptr;
}

size_t RuntimeLease::slot_index() const {
    if (!slot_) {
        throw std::runtime_error("runtime lease is not valid");
    }
    return slot_->index;
}

void RuntimeLease::release() {
    if (pool_ && slot_) {
        pool_->release(slot_);
        pool_ = nullptr;
        slot_ = nullptr;
    }
}

RuntimePool::RuntimePool(RuntimePoolOptions options)
    : options_(options) {
}

RuntimePool::~RuntimePool() {
    clear();
}

RuntimePoolLoadResult RuntimePool::load_model(const RuntimeModelConfig& config) {
    RuntimePoolLoadResult result;
    result.plan = plan_runtime_count(config);

    {
        std::unique_lock<std::mutex> lock(mutex_);
        cv_.wait(lock, [this] {
            return !loading_;
        });
        loading_ = true;
        cv_.wait(lock, [this] {
            return active_leases_ == 0;
        });
    }

    std::vector<std::unique_ptr<RuntimeSlot>> new_slots;
    std::string error;
    const size_t runtime_count = std::max<size_t>(1, result.plan.final_count);

    for (size_t i = 0; i < runtime_count; ++i) {
        auto runtime = std::make_unique<WhisperRuntime>();
        if (!runtime->load_model(config.model_path, config.use_gpu, error)) {
            std::lock_guard<std::mutex> lock(mutex_);
            loading_ = false;
            cv_.notify_all();
            result.ok = false;
            result.error = error;
            if (options_.verbose) {
                std::cout << "runtime pool load failed: " << error << std::endl;
            }
            return result;
        }

        auto slot = std::make_unique<RuntimeSlot>();
        slot->index = i;
        slot->runtime = std::move(runtime);
        new_slots.push_back(std::move(slot));
    }

    {
        std::lock_guard<std::mutex> lock(mutex_);
        slots_ = std::move(new_slots);
        last_plan_ = result.plan;
        loaded_ = true;
        mock_model_ = false;
        loading_ = false;
    }
    cv_.notify_all();

    result.ok = true;
    result.runtime_count = runtime_count;
    if (options_.verbose) {
        std::cout << "runtime pool loaded: count=" << runtime_count
                  << ", desired=" << result.plan.desired_count
                  << ", allowed=" << result.plan.allowed_count << std::endl;
    }
    return result;
}

RuntimePoolLoadResult RuntimePool::load_mock_model() {
    RuntimePoolLoadResult result;
    result.ok = true;
    result.runtime_count = 0;
    result.plan = {};

    {
        std::unique_lock<std::mutex> lock(mutex_);
        cv_.wait(lock, [this] {
            return !loading_;
        });
        loading_ = true;
        cv_.wait(lock, [this] {
            return active_leases_ == 0;
        });
        slots_.clear();
        last_plan_ = result.plan;
        loaded_ = true;
        mock_model_ = true;
        loading_ = false;
    }
    cv_.notify_all();

    return result;
}

RuntimeLease RuntimePool::acquire() {
    std::unique_lock<std::mutex> lock(mutex_);
    cv_.wait(lock, [this] {
        if (loading_ || !loaded_ || mock_model_) {
            return false;
        }
        return std::any_of(slots_.begin(), slots_.end(), [](const auto& slot) {
            return slot && !slot->in_use;
        });
    });

    auto it = std::find_if(slots_.begin(), slots_.end(), [](const auto& slot) {
        return slot && !slot->in_use;
    });
    if (it == slots_.end()) {
        throw std::runtime_error("no runtime slot available");
    }

    RuntimeSlot* slot = it->get();
    slot->in_use = true;
    ++active_leases_;
    if (options_.verbose) {
        std::cout << "runtime slot acquired: index=" << slot->index
                  << ", active_leases=" << active_leases_ << std::endl;
    }
    return RuntimeLease(this, slot);
}

void RuntimePool::clear() {
    {
        std::unique_lock<std::mutex> lock(mutex_);
        cv_.wait(lock, [this] {
            return !loading_;
        });
        loading_ = true;
        cv_.wait(lock, [this] {
            return active_leases_ == 0;
        });
        slots_.clear();
        loaded_ = false;
        mock_model_ = false;
        last_plan_ = {};
        loading_ = false;
    }
    cv_.notify_all();
}

bool RuntimePool::is_loaded() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return loaded_;
}

bool RuntimePool::is_mock_model() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return mock_model_;
}

size_t RuntimePool::runtime_count() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return slots_.size();
}

RuntimePoolPlan RuntimePool::last_plan() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return last_plan_;
}

RuntimePoolPlan RuntimePool::plan_runtime_count(const RuntimeModelConfig& config) const {
    RuntimePoolPlan plan;
    plan.desired_count = model_size_policy(config.model_name, config.model_path);
    plan.estimated_runtime_memory_bytes = estimate_runtime_memory_bytes(config.model_path);
    plan.allowed_count = memory_policy(plan.estimated_runtime_memory_bytes);

    const size_t configured_limit =
        options_.max_runtime_count == 0 ? plan.desired_count : options_.max_runtime_count;
    plan.final_count = std::max<size_t>(
        1,
        (std::min)((std::min)(plan.desired_count, plan.allowed_count), configured_limit));
    return plan;
}

size_t RuntimePool::model_size_policy(
    const std::string& model_name,
    const std::string& model_path) const {
    const std::string text = lowercase(model_name + " " + model_path);
    if (text.find("large") != std::string::npos) {
        return 1;
    }
    if (text.find("medium") != std::string::npos) {
        return 1;
    }
    if (text.find("small") != std::string::npos) {
        return 2;
    }
    if (text.find("base") != std::string::npos) {
        return 3;
    }
    if (text.find("tiny") != std::string::npos) {
        return 4;
    }
    return 1;
}

size_t RuntimePool::memory_policy(uintmax_t estimated_runtime_memory_bytes) const {
    if (estimated_runtime_memory_bytes == 0) {
        return 1;
    }

    const uintmax_t available = available_physical_memory_bytes();
    if (available == 0) {
        return 1;
    }

    return std::max<uintmax_t>(1, available / estimated_runtime_memory_bytes);
}

uintmax_t RuntimePool::estimate_runtime_memory_bytes(const std::string& model_path) const {
    std::error_code ec;
    const uintmax_t model_size = std::filesystem::file_size(model_path, ec);
    if (ec) {
        return 0;
    }

    const auto scaled_model_size =
        static_cast<uintmax_t>(static_cast<double>(model_size) * options_.model_memory_multiplier);
    return scaled_model_size + options_.decode_buffer_margin_bytes;
}

uintmax_t RuntimePool::available_physical_memory_bytes() const {
#ifdef _WIN32
    MEMORYSTATUSEX status;
    status.dwLength = sizeof(status);
    if (GlobalMemoryStatusEx(&status) == 0) {
        return 0;
    }
    return static_cast<uintmax_t>(status.ullAvailPhys);
#else
    return 0;
#endif
}

void RuntimePool::release(RuntimeSlot* slot) {
    {
        std::lock_guard<std::mutex> lock(mutex_);
        if (slot && slot->in_use) {
            slot->in_use = false;
            if (active_leases_ > 0) {
                --active_leases_;
            }
            if (options_.verbose) {
                std::cout << "runtime slot released: index=" << slot->index
                          << ", active_leases=" << active_leases_ << std::endl;
            }
        }
    }
    cv_.notify_all();
}

} // namespace flowscribe::engine::transcription
