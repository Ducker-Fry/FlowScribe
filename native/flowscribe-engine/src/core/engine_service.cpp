#include "flowscribe/engine/core/engine_service.h"

#include "flowscribe/engine/protocol/codec.h"

#include <chrono>
#include <filesystem>
#include <iostream>
#include <thread>

namespace flowscribe::engine::core {

EngineService::EngineService()
    : EngineService(load_engine_options_from_env()) {
}

EngineService::EngineService(EngineOptions options)
    : options_(options),
      scheduler_(options.verbose) {
    transcription::RuntimePoolOptions runtime_pool_options;
    runtime_pool_options.max_runtime_count = options_.runtime_max_count;
    runtime_pool_options.verbose = options_.verbose;
    runtime_pool_ = std::make_unique<transcription::RuntimePool>(runtime_pool_options);
    if (options_.verbose) {
        std::cout << "engine options: worker_count=" << options_.worker_count
                  << ", runtime_max_count=" << options_.runtime_max_count << std::endl;
    }

    WorkerCallbacks callbacks;
    callbacks.on_event = [this](const protocol::JobEvent& event) {
        push_job_event(event);
    };
    callbacks.on_result = [this](const protocol::JobResult& result) {
        push_job_result(result);
    };
    callbacks.on_error = [this](const protocol::JobError& error) {
        push_job_error(error);
    };
    WorkerPoolOptions worker_options;
    worker_options.worker_count = options_.worker_count;
    worker_options.verbose = options_.verbose;
    worker_options.mock_job_delay = options_.mock_job_delay;
    worker_pool_ = std::make_unique<WorkerPool>(
        scheduler_,
        job_manager_,
        *runtime_pool_,
        std::move(callbacks),
        worker_options);
    worker_pool_->start();
}

EngineService::~EngineService() = default;

void EngineService::run(std::unique_ptr<ipc::NamedPipeConnection> conn) {
    if (!conn || !conn->is_valid()) {
        return;
    }

    {
        std::lock_guard<std::mutex> lock(conn_mutex_);
        conn_ = std::move(conn);
    }
    dispatcher_.start([this](const protocol::Message& msg) {
        return write_message(msg);
    });

    while (true) {
        protocol::Message req;
        std::string error;

        ipc::NamedPipeConnection* active_conn = nullptr;
        {
            std::lock_guard<std::mutex> lock(conn_mutex_);
            active_conn = conn_.get();
        }

        if (!active_conn) {
            break;
        }

        const auto read_status = active_conn->try_read_message(req, error);
        if (read_status == ipc::ReadMessageStatus::NoMessage) {
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
            continue;
        }
        if (read_status != ipc::ReadMessageStatus::Message) {
            break;
        }

        protocol::Message rep;
        handle_message(req, rep);
        dispatcher_.send_response(rep);
        if (req.header.kind == protocol::MessageKind::SubmitJobRequest) {
            const auto submit_rep = protocol::from_json_obj<protocol::SubmitJobResult>(
                nlohmann::json::parse(rep.json_payload));
            if (submit_rep.ok) {
                const auto submit_req = protocol::from_json_obj<protocol::SubmitJobRequest>(
                    nlohmann::json::parse(req.json_payload));
                scheduler_.enqueue(submit_req);
            }
        }
    }

    dispatcher_.stop();
    if (worker_pool_) {
        worker_pool_->stop();
    }

    std::lock_guard<std::mutex> lock(conn_mutex_);
    conn_.reset();
}

void EngineService::handle_message(const protocol::Message& req, protocol::Message& rep) {
    using Kind = protocol::MessageKind;

    if (req.header.kind == Kind::HelloRequest) {
        const auto hello_req = protocol::from_json_obj<protocol::HelloRequest>(
            nlohmann::json::parse(req.json_payload));

        protocol::HelloResult hello_rep;
        handle_hello(hello_req, hello_rep);
        rep = protocol::make_message(Kind::HelloResult, nlohmann::json(hello_rep).dump());
        return;
    }

    if (req.header.kind == Kind::LoadModelRequest) {
        const auto load_req = protocol::from_json_obj<protocol::LoadModelRequest>(
            nlohmann::json::parse(req.json_payload));

        protocol::LoadModelResult load_rep;
        handle_load_model(load_req, load_rep);
        rep = protocol::make_message(Kind::LoadModelResult, nlohmann::json(load_rep).dump());
        return;
    }

    if (req.header.kind == Kind::SubmitJobRequest) {
        const auto submit_req = protocol::from_json_obj<protocol::SubmitJobRequest>(
            nlohmann::json::parse(req.json_payload));

        protocol::SubmitJobResult submit_rep;
        handle_submit_job(submit_req, submit_rep);
        rep = protocol::make_message(Kind::SubmitJobResult, nlohmann::json(submit_rep).dump());
        return;
    }

    if (req.header.kind == Kind::CancelJobRequest) {
        const auto cancel_req = protocol::from_json_obj<protocol::CancelJobRequest>(
            nlohmann::json::parse(req.json_payload));

        protocol::CancelJobResult cancel_rep;
        handle_cancel_job(cancel_req, cancel_rep);
        rep = protocol::make_message(Kind::CancelJobResult, nlohmann::json(cancel_rep).dump());
        return;
    }

    if (req.header.kind == Kind::QueryJobRequest) {
        const auto query_req = protocol::from_json_obj<protocol::QueryJobRequest>(
            nlohmann::json::parse(req.json_payload));

        protocol::QueryJobResult query_rep;
        handle_query_job(query_req, query_rep);
        rep = protocol::make_message(Kind::QueryJobResult, nlohmann::json(query_rep).dump());
        return;
    }

    protocol::JobError error;
    error.code = "unsupported_message";
    error.message = "unsupported message kind";
    rep = protocol::make_message(Kind::JobError, nlohmann::json(error).dump());
}

void EngineService::handle_hello(const protocol::HelloRequest& req, protocol::HelloResult& rep) {
    (void)req;
    rep.ok = true;
    rep.engine_version = "flowscribe-engine-v1.0.0";
    rep.protocol_version = protocol::PROTOCOL_VERSION;
}

void EngineService::handle_load_model(
    const protocol::LoadModelRequest& req,
    protocol::LoadModelResult& rep) {
    const auto start = std::chrono::steady_clock::now();
    std::cout << "load model requested: name=" << req.model_name
              << ", path=" << req.model_path
              << ", use_gpu=" << (req.use_gpu ? "true" : "false") << std::endl;

    if (req.model_path.empty()) {
        rep.ok = false;
        rep.error = "model_path is required";
        return;
    }

    if (req.model_name.empty()) {
        rep.ok = false;
        rep.error = "model_name is required";
        return;
    }

    std::error_code ec;
    if (!std::filesystem::exists(req.model_path, ec) || ec) {
        rep.ok = false;
        rep.error = "model file does not exist";
        return;
    }

    if (req.model_name == "__mock__") {
        const auto load_result = runtime_pool_->load_mock_model();
        if (!load_result.ok) {
            rep.ok = false;
            rep.error = load_result.error;
            return;
        }

        mock_model_ = true;
        model_loaded_ = true;
        model_path_ = req.model_path;
        model_name_ = req.model_name;

        const auto elapsed = std::chrono::steady_clock::now() - start;
        rep.ok = true;
        rep.error.clear();
        rep.model_load_time_ms =
            std::chrono::duration_cast<std::chrono::milliseconds>(elapsed).count();
        std::cout << "mock model loaded in " << rep.model_load_time_ms << " ms" << std::endl;
        return;
    }

    transcription::RuntimeModelConfig config;
    config.model_name = req.model_name;
    config.model_path = req.model_path;
    config.use_gpu = req.use_gpu;
    const auto load_result = runtime_pool_->load_model(config);
    if (!load_result.ok) {
        rep.ok = false;
        rep.error = load_result.error;
        std::cout << "load model failed: " << load_result.error << std::endl;
        return;
    }

    mock_model_ = false;
    model_loaded_ = true;
    model_path_ = req.model_path;
    model_name_ = req.model_name;

    const auto elapsed = std::chrono::steady_clock::now() - start;
    rep.ok = true;
    rep.error.clear();
    rep.model_load_time_ms = std::chrono::duration_cast<std::chrono::milliseconds>(elapsed).count();
    rep.runtime_count = static_cast<int64_t>(load_result.runtime_count);
    std::cout << "model loaded in " << rep.model_load_time_ms
              << " ms, runtime_count=" << load_result.runtime_count << std::endl;
}

void EngineService::handle_submit_job(
    const protocol::SubmitJobRequest& req,
    protocol::SubmitJobResult& rep) {
    rep.job_id = req.job_id;

    if (!model_loaded_) {
        rep.ok = false;
        rep.error = "model is not loaded";
        return;
    }

    if (req.job_id.empty()) {
        rep.ok = false;
        rep.error = "job_id is required";
        return;
    }

    if (req.audio_path.empty()) {
        rep.ok = false;
        rep.error = "audio_path is required";
        return;
    }

    std::error_code ec;
    if (!std::filesystem::exists(req.audio_path, ec) || ec) {
        rep.ok = false;
        rep.error = "audio file does not exist";
        return;
    }

    std::string error;
    if (!job_manager_.create_queued(req, error)) {
        rep.ok = false;
        rep.error = error;
        return;
    }

    rep.ok = true;
    rep.error.clear();
}

void EngineService::handle_cancel_job(
    const protocol::CancelJobRequest& req,
    protocol::CancelJobResult& rep) {
    rep.job_id = req.job_id;

    if (req.job_id.empty()) {
        rep.ok = false;
        rep.error = "job_id is required";
        return;
    }

    std::string error;
    if (!scheduler_.cancel_queued(req.job_id)) {
        const auto job = job_manager_.get(req.job_id);
        if (job.has_value() && job->status == "running") {
            rep.ok = false;
            rep.error = "running job cancellation is not supported yet";
            return;
        }
    }

    if (!job_manager_.mark_canceled_if_queued(req.job_id, error)) {
        rep.ok = false;
        rep.error = error;
        return;
    }

    rep.ok = true;
    rep.error.clear();
}

void EngineService::handle_query_job(
    const protocol::QueryJobRequest& req,
    protocol::QueryJobResult& rep) {
    rep.job_id = req.job_id;

    if (req.job_id.empty()) {
        rep.ok = false;
        rep.error = "job_id is required";
        return;
    }

    const auto job = job_manager_.get(req.job_id);
    if (!job.has_value()) {
        rep.ok = false;
        rep.error = "job not found";
        return;
    }

    rep.ok = true;
    rep.error.clear();
    rep.job = *job;
}

void EngineService::push_job_event(const protocol::JobEvent& event) {
    const protocol::Message msg = protocol::make_message(
        protocol::MessageKind::JobEvent,
        nlohmann::json(event).dump());
    dispatcher_.send_event(msg);
}

void EngineService::push_job_result(const protocol::JobResult& result) {
    const protocol::Message msg = protocol::make_message(
        protocol::MessageKind::JobResult,
        nlohmann::json(result).dump());
    dispatcher_.send_event(msg);
}

void EngineService::push_job_error(const protocol::JobError& error) {
    const protocol::Message msg = protocol::make_message(
        protocol::MessageKind::JobError,
        nlohmann::json(error).dump());
    dispatcher_.send_event(msg);
}

bool EngineService::write_message(const protocol::Message& msg) {
    std::lock_guard<std::mutex> lock(conn_mutex_);
    if (!conn_ || !conn_->is_valid()) {
        return false;
    }

    std::string error;
    if (!conn_->write_message(msg, error)) {
        if (error == "connection closed") {
            return false;
        }
        std::cerr << "Failed to send message: " << error << std::endl;
        return false;
    }
    return true;
}

} // namespace flowscribe::engine::core
