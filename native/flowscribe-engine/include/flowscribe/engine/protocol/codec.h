#pragma once

#include "message.h"

#include <cstdint>
#include <string>
#include <vector>

#include <json.hpp>

namespace flowscribe::engine::protocol {

std::vector<uint8_t> encode_message(const Message& msg);
Message make_message(MessageKind kind, const std::string& json_payload);

bool decode_frame_header(const uint8_t* data, FrameHeader& out_header);
bool decode_frame_header(const std::vector<uint8_t>& data, FrameHeader& out_header);
bool decode_message(const std::vector<uint8_t>& data, Message& out_message, std::string& error);

void to_json(nlohmann::json& j, const HelloRequest& value);
void from_json(const nlohmann::json& j, HelloRequest& value);

void to_json(nlohmann::json& j, const HelloResult& value);
void from_json(const nlohmann::json& j, HelloResult& value);

void to_json(nlohmann::json& j, const LoadModelRequest& value);
void from_json(const nlohmann::json& j, LoadModelRequest& value);

void to_json(nlohmann::json& j, const LoadModelResult& value);
void from_json(const nlohmann::json& j, LoadModelResult& value);

void to_json(nlohmann::json& j, const ProgressiveOptions& value);
void from_json(const nlohmann::json& j, ProgressiveOptions& value);

void to_json(nlohmann::json& j, const SubmitJobRequest& value);
void from_json(const nlohmann::json& j, SubmitJobRequest& value);

void to_json(nlohmann::json& j, const SubmitJobResult& value);
void from_json(const nlohmann::json& j, SubmitJobResult& value);

void to_json(nlohmann::json& j, const CancelJobRequest& value);
void from_json(const nlohmann::json& j, CancelJobRequest& value);

void to_json(nlohmann::json& j, const CancelJobResult& value);
void from_json(const nlohmann::json& j, CancelJobResult& value);

void to_json(nlohmann::json& j, const JobEvent& value);
void from_json(const nlohmann::json& j, JobEvent& value);

void to_json(nlohmann::json& j, const WordTiming& value);
void from_json(const nlohmann::json& j, WordTiming& value);

void to_json(nlohmann::json& j, const TranscriptSegment& value);
void from_json(const nlohmann::json& j, TranscriptSegment& value);

void to_json(nlohmann::json& j, const JobResult& value);
void from_json(const nlohmann::json& j, JobResult& value);

void to_json(nlohmann::json& j, const JobError& value);
void from_json(const nlohmann::json& j, JobError& value);

void to_json(nlohmann::json& j, const ShutdownRequest& value);
void from_json(const nlohmann::json& j, ShutdownRequest& value);

void to_json(nlohmann::json& j, const ShutdownResult& value);
void from_json(const nlohmann::json& j, ShutdownResult& value);

} // namespace flowscribe::engine::protocol
