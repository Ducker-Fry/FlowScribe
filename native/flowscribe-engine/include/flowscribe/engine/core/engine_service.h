#pragma once

#include <memory>
#include <mutex>
#include <string>

#include "flowscribe/engine/core/engine_options.h"
#include "flowscribe/engine/core/job_manager.h"
#include "flowscribe/engine/core/outbound_dispatcher.h"
#include "flowscribe/engine/core/scheduler.h"
#include "flowscribe/engine/core/worker_pool.h"
#include "flowscribe/engine/ipc/named_pipe_connection.h"
#include "flowscribe/engine/protocol/message.h"
#include "flowscribe/engine/transcription/runtime_pool.h"

namespace flowscribe::engine::core {

class EngineService {
public:
    EngineService();
    explicit EngineService(EngineOptions options);
    ~EngineService();

    void run(std::unique_ptr<ipc::NamedPipeConnection> conn);

private:
    void handle_message(const protocol::Message& req, protocol::Message& rep);
    void handle_hello(const protocol::HelloRequest& req, protocol::HelloResult& rep);
    void handle_load_model(const protocol::LoadModelRequest& req, protocol::LoadModelResult& rep);
    void handle_submit_job(const protocol::SubmitJobRequest& req, protocol::SubmitJobResult& rep);
    void handle_cancel_job(const protocol::CancelJobRequest& req, protocol::CancelJobResult& rep);
    void handle_query_job(const protocol::QueryJobRequest& req, protocol::QueryJobResult& rep);

    void push_job_event(const protocol::JobEvent& event);
    void push_job_result(const protocol::JobResult& result);
    void push_job_error(const protocol::JobError& error);
    bool write_message(const protocol::Message& msg);

    std::unique_ptr<transcription::RuntimePool> runtime_pool_;
    EngineOptions options_;
    JobManager job_manager_;
    JobScheduler scheduler_;
    OutboundDispatcher dispatcher_;
    std::unique_ptr<WorkerPool> worker_pool_;
    bool model_loaded_ = false;
    bool mock_model_ = false;
    std::string model_path_;
    std::string model_name_;

    std::unique_ptr<ipc::NamedPipeConnection> conn_;
    std::mutex conn_mutex_;
};

} // namespace flowscribe::engine::core
