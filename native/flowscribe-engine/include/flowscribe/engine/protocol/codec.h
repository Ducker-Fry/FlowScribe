#pragma once

#include "message.h"

#include <cstdint>
#include <string>
#include <unordered_map>
#include <vector>

#include <json.hpp>

namespace flowscribe::engine::protocol {


void write_u16_le(std::vector<uint8_t>& buffer, size_t offset, uint16_t value);

void write_u32_le(std::vector<uint8_t>& buffer, size_t offset, uint32_t value);

class MessageKindRegistry {
public:
    using Kind = MessageKind;
    using StrMap = std::unordered_map<Kind, std::string>;
    using RevMap = std::unordered_map<std::string, Kind>;

    static MessageKindRegistry& instance() {
        static MessageKindRegistry inst;
        return inst;
    }

    void register_kind(Kind kind, const std::string& name) {
        kind_to_str_[kind] = name;
        str_to_kind_[name] = kind;
    }

    std::string to_str(Kind kind) const {
        auto it = kind_to_str_.find(kind);
        return it != kind_to_str_.end() ? it->second : "unknown";
    }

    Kind from_str(const std::string& name) const {
        auto it = str_to_kind_.find(name);
        return it != str_to_kind_.end() ? it->second : static_cast<Kind>(0);
    }

    bool is_known(Kind kind) const {
        return kind_to_str_.contains(kind);
    }

private:
    MessageKindRegistry();

    StrMap kind_to_str_;
    RevMap str_to_kind_;
};

#define REGISTER_MESSAGE_KIND(registry, kind, name) \
    (registry).register_kind(::flowscribe::engine::protocol::MessageKind::kind, name)

template <typename T>
void read_optional(const nlohmann::json& j, const char* key, T& value) {
    if (j.contains(key) && !j.at(key).is_null()) {
        j.at(key).get_to(value);
    }
}

template <typename T>
nlohmann::json to_json_obj(const T& obj) {
    nlohmann::json j;
    to_json(j, obj);
    return j;
}

template <typename T>
T from_json_obj(const nlohmann::json& j) {
    T obj;
    from_json(j, obj);
    return obj;
}

std::vector<uint8_t> encode_message(const Message& msg);
Message make_message(MessageKind kind, const std::string& json_payload);

bool decode_frame_header(const uint8_t* data, FrameHeader& out_header);
bool decode_frame_header(const std::vector<uint8_t>& data, FrameHeader& out_header);
bool decode_message(const std::vector<uint8_t>& data, Message& out_message, std::string& error);

#define BIND_JSON_STRUCT(Type) \
    void to_json(nlohmann::json& j, const Type& value); \
    void from_json(const nlohmann::json& j, Type& value)

BIND_JSON_STRUCT(HelloRequest);
BIND_JSON_STRUCT(HelloResult);
BIND_JSON_STRUCT(LoadModelRequest);
BIND_JSON_STRUCT(LoadModelResult);
BIND_JSON_STRUCT(ProgressiveOptions);
BIND_JSON_STRUCT(SubmitJobRequest);
BIND_JSON_STRUCT(SubmitJobResult);
BIND_JSON_STRUCT(CancelJobRequest);
BIND_JSON_STRUCT(CancelJobResult);
BIND_JSON_STRUCT(QueryJobRequest);
BIND_JSON_STRUCT(QueryJobResult);
BIND_JSON_STRUCT(JobEvent);
BIND_JSON_STRUCT(WordTiming);
BIND_JSON_STRUCT(TranscriptSegment);
BIND_JSON_STRUCT(ChunkMetric);
BIND_JSON_STRUCT(JobResult);
BIND_JSON_STRUCT(JobStatus);
BIND_JSON_STRUCT(JobError);
BIND_JSON_STRUCT(ShutdownRequest);
BIND_JSON_STRUCT(ShutdownResult);

#undef BIND_JSON_STRUCT


} // namespace flowscribe::engine::protocol
