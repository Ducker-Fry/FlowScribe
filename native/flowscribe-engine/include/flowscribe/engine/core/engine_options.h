#pragma once

#include <chrono>
#include <algorithm>
#include <string>
#include <vector>

#ifdef _WIN32
#include <cstdlib>
#else
#include <cstdlib>
#endif

namespace flowscribe::engine::core {

struct EngineOptions {
    size_t worker_count = 1;
    size_t runtime_max_count = 0;
    bool verbose = false;
    std::chrono::milliseconds mock_job_delay{0};
};

inline std::string read_env(const char* name) {
#ifdef _WIN32
    size_t required_size = 0;
    getenv_s(&required_size, nullptr, 0, name);
    if (required_size == 0) {
        return {};
    }

    std::vector<char> buffer(required_size);
    getenv_s(&required_size, buffer.data(), buffer.size(), name);
    if (required_size == 0 || buffer.empty()) {
        return {};
    }
    return std::string(buffer.data());
#else
    const char* value = std::getenv(name);
    return value != nullptr ? std::string(value) : std::string();
#endif
}

inline bool read_bool_env(const char* name) {
    const std::string text = read_env(name);
    if (text.empty()) {
        return false;
    }

    return text == "1" || text == "true" || text == "TRUE" || text == "on" || text == "ON";
}

inline std::chrono::milliseconds read_ms_env(const char* name) {
    const std::string value = read_env(name);
    if (value.empty()) {
        return std::chrono::milliseconds{0};
    }

    try {
        return std::chrono::milliseconds{std::max(0, std::stoi(value))};
    } catch (...) {
        return std::chrono::milliseconds{0};
    }
}

inline size_t read_size_env(const char* name, size_t fallback) {
    const std::string value = read_env(name);
    if (value.empty()) {
        return fallback;
    }

    try {
        const int parsed = std::stoi(value);
        return parsed > 0 ? static_cast<size_t>(parsed) : fallback;
    } catch (...) {
        return fallback;
    }
}

inline EngineOptions load_engine_options_from_env() {
    EngineOptions options;
    options.verbose = read_bool_env("FLOWSCRIBE_ENGINE_VERBOSE");
    options.worker_count = read_size_env("FLOWSCRIBE_ENGINE_WORKER_COUNT", 1);
    options.runtime_max_count = read_size_env("FLOWSCRIBE_ENGINE_RUNTIME_MAX_COUNT", 0);
    options.mock_job_delay = read_ms_env("FLOWSCRIBE_ENGINE_MOCK_JOB_DELAY_MS");
    return options;
}

} // namespace flowscribe::engine::core
