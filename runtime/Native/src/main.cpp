#include <Mod/CppUserModBase.hpp>
#include <LuaMadeSimple/LuaMadeSimple.hpp>
#include <Unreal/UObject.hpp>
#include <Unreal/NameTypes.hpp>
#include <Windows.h>
#include <bcrypt.h>
#include <array>
#include <cstdint>
#include <cstring>
#include <iomanip>
#include <sstream>
#include <string>
#include <vector>
#include <stdexcept>
#include <filesystem>
#include <fstream>
#include "reviewed_layout.hpp"
#include "write_arguments.hpp"
#include "persistent_dispatch.hpp"

namespace {
std::string hex(const unsigned char* data, std::size_t size);
bool read(std::uintptr_t address, void* output, std::size_t size) {
    SIZE_T copied{};
    return address > 0x10000 && size <= 65536 &&
        ReadProcessMemory(GetCurrentProcess(), reinterpret_cast<void*>(address), output, size, &copied) && copied == size;
}
std::string digest(const std::vector<unsigned char>& bytes) {
    BCRYPT_ALG_HANDLE algorithm{};BCRYPT_HASH_HANDLE hash{};
    if (BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0)<0) throw std::runtime_error("sha256_unavailable");
    std::array<unsigned char,32> result{};
    auto status=BCryptCreateHash(algorithm,&hash,nullptr,0,nullptr,0,0);
    if(status>=0) status=BCryptHashData(hash,const_cast<unsigned char*>(bytes.data()),static_cast<ULONG>(bytes.size()),0);
    if(status>=0) status=BCryptFinishHash(hash,result.data(),static_cast<ULONG>(result.size()),0);
    if(hash) BCryptDestroyHash(hash);
    BCryptCloseAlgorithmProvider(algorithm,0);
    if(status<0) throw std::runtime_error("sha256_failed");
    return hex(result.data(),result.size());
}
struct Table {
    std::uintptr_t content{};
    std::vector<unsigned char> bytes;
    std::array<int,4> choices{};
};
std::uint64_t encoded(std::uint32_t descriptor,int choice) {
    const auto relative=static_cast<std::int64_t>(reviewed::options[choice])-descriptor;
    return static_cast<std::uint64_t>(relative*2)|1;
}
DWORD window_thread() {
    struct Search {DWORD process;DWORD thread;};
    Search search{GetCurrentProcessId(),0};
    EnumWindows([](HWND window,LPARAM parameter)->BOOL {
        auto& found=*reinterpret_cast<Search*>(parameter);
        DWORD process{};const auto thread=GetWindowThreadProcessId(window,&process);
        wchar_t type[64]{};
        if(process==found.process && IsWindowVisible(window) && GetClassNameW(window,type,64) &&
           std::wstring_view(type)==L"UnrealWindow") {found.thread=thread;return FALSE;}
        return TRUE;
    },reinterpret_cast<LPARAM>(&search));
    return search.thread;
}
bool uncertain_write{};
Table validate(std::uintptr_t address) {
    // ExecuteInGameThread in this UE4SS version drains on ProcessEvent, which
    // may also occur on a loading thread. Never bind to its first invocation.
    // Require this Windows game's own visible UnrealWindow owner thread.
    const auto thread=window_thread();
    if(thread==0) throw std::runtime_error("game_window_thread_unavailable");
    if(thread!=GetCurrentThreadId()) throw std::runtime_error("wrong_thread");
    std::array<unsigned char,0x40> header{};
    if(!read(address,header.data(),header.size())) throw std::runtime_error("unreadable_asset");
    auto* object=reinterpret_cast<RC::Unreal::UObject*>(address);
    if(object->GetFullName()!=L"EndDataObjectEnemyTerritory /Game/DataObject/Field/1200-GRASA/EnemyTerritory.EnemyTerritory")
        throw std::runtime_error("unreviewed_asset_identity");
    Table table;
    // Observed live in the pinned c0a8d4c/game build, then checked by the entire
    // frozen image's structural fingerprint and every serialized name below.
    std::memcpy(&table.content,header.data()+0x38,8);
    table.bytes.resize(reviewed::image_bytes);
    if(!read(table.content,table.bytes.data(),table.bytes.size())) throw std::runtime_error("unreadable_image");
    auto normalized=table.bytes;
    for(std::size_t i=0;i<4;++i) {
        const auto descriptor=reviewed::targets[i].descriptor;
        std::uint64_t value{};std::memcpy(&value,table.bytes.data()+descriptor,8);
        int choice=value==encoded(descriptor,0)?0:value==encoded(descriptor,1)?1:-1;
        if(choice<0) throw std::runtime_error("unreviewed_composition_pointer");
        table.choices[i]=choice;
        value=encoded(descriptor,0);std::memcpy(normalized.data()+descriptor,&value,8);
    }
    for(const auto& patch:reviewed::names) {
        // Find only: no global name is created. Compare exact native token
        // components, avoiding unsafe ToString calls on untrusted indices.
        const RC::Unreal::FName expected(patch.name,RC::Unreal::FNAME_Find);
        std::uint32_t index{},number{};
        std::memcpy(&index,table.bytes.data()+patch.offset,4);
        std::memcpy(&number,table.bytes.data()+patch.offset+4,4);
        if(index!=expected.GetComparisonIndex() || number!=expected.GetNumber()) throw std::runtime_error("name_manifest_differs");
        std::memset(normalized.data()+patch.offset,0,8);
    }
    if(digest(normalized)!=reviewed::masked_sha256) throw std::runtime_error("structure_fingerprint_differs");
    return table;
}
std::string status_json(const Table& table) {
    std::ostringstream out;out << "{\"ok\":true,\"image_bytes\":" << table.bytes.size() << ",\"asset_content\":" << table.content << ",\"choices\":[";
    for(std::size_t i=0;i<4;++i) {if(i)out<<',';out<<table.choices[i];}
    out << "],\"all_names_and_structural_fingerprint_verified\":true,\"uncertain_write\":" << (uncertain_write?"true":"false") << '}';
    return out.str();
}
int table_status(const RC::LuaMadeSimple::Lua& lua) {
    try {lua.set_string(status_json(validate(static_cast<std::uintptr_t>(lua.get_integer(1)))));}
    catch(const std::exception& error) {lua.set_string(std::string("{\"ok\":false,\"reason\":\"")+error.what()+"\"}");}
    return 1;
}
int hash_text(const RC::LuaMadeSimple::Lua& lua) {
    if(!lua.is_string(1)) {lua.set_nil();return 1;}
    const std::string input(lua.get_string(1));
    if(input.size()>512) {lua.set_nil();return 1;}
    try {lua.set_string(digest(std::vector<unsigned char>(input.begin(),input.end())));}
    catch(...) {lua.set_nil();}
    return 1;
}
int random_seed(const RC::LuaMadeSimple::Lua& lua) {
    std::array<unsigned char,16> bytes{};
    if(BCryptGenRandom(nullptr,bytes.data(),static_cast<ULONG>(bytes.size()),BCRYPT_USE_SYSTEM_PREFERRED_RNG)<0) lua.set_nil();
    else lua.set_string(hex(bytes.data(),bytes.size()));
    return 1;
}
std::filesystem::path state_directory() {
    std::array<wchar_t,32768> value{};
    const auto length=GetEnvironmentVariableW(L"LOCALAPPDATA",value.data(),static_cast<DWORD>(value.size()));
    if(length==0 || length>=value.size()) throw std::runtime_error("local_app_data_unavailable");
    return std::filesystem::path(value.data())/L"FFVIIRebirthBiomeRandomizer";
}
std::string read_file(const std::filesystem::path& path) {
    const auto size=std::filesystem::file_size(path);
    if(size==0 || size>16384) throw std::runtime_error("state_file_size_invalid");
    std::ifstream file(path,std::ios::binary);
    if(!file) throw std::runtime_error("state_read_failed");
    std::string value(static_cast<std::size_t>(size),'\0');
    file.read(value.data(),static_cast<std::streamsize>(size));
    if(!file || value.find('\0')!=std::string::npos) throw std::runtime_error("state_read_invalid");
    return value;
}
int read_state(const RC::LuaMadeSimple::Lua& lua) {
    try {
        auto path=state_directory()/L"state-v1.json";
        if(!std::filesystem::exists(path)) {
            const auto backup=state_directory()/L"state-v1.previous.json";
            if(std::filesystem::exists(backup)) path=backup;
            else {lua.set_string("");lua.set_bool(true);return 2;}
        }
        const auto value=read_file(path);lua.set_string(value);lua.set_bool(true);
    }catch(...) {lua.set_string("");lua.set_bool(false);}
    return 2;
}
int write_state(const RC::LuaMadeSimple::Lua& lua) {
    try {
        if(!lua.is_string(1)) throw std::runtime_error("state_payload_type");
        const std::string value(lua.get_string(1));
        if(value.empty() || value.size()>16384) throw std::runtime_error("state_payload_size");
        const auto directory=state_directory();std::filesystem::create_directories(directory);
        const auto path=directory/L"state-v1.json";
        const auto backup=directory/L"state-v1.previous.json";
        const auto temporary=directory/(L"state-v1."+std::to_wstring(GetCurrentProcessId())+L"."+std::to_wstring(GetTickCount64())+L".tmp");
        const auto file=CreateFileW(temporary.c_str(),GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
        if(file==INVALID_HANDLE_VALUE) throw std::runtime_error("state_create_failed");
        DWORD written{};
        const bool complete=WriteFile(file,value.data(),static_cast<DWORD>(value.size()),&written,nullptr) &&
            written==value.size() && FlushFileBuffers(file);
        CloseHandle(file);
        if(!complete || read_file(temporary)!=value) throw std::runtime_error("state_temporary_unverified");
        const bool exists=std::filesystem::exists(path);
        if(exists) {
            const auto previous=read_file(path);
            if(!CopyFileW(path.c_str(),backup.c_str(),FALSE) || read_file(backup)!=previous)
                throw std::runtime_error("state_backup_unverified");
        }
        const bool replaced=exists
            ? ReplaceFileW(path.c_str(),temporary.c_str(),nullptr,0,nullptr,nullptr)!=0
            : MoveFileExW(temporary.c_str(),path.c_str(),MOVEFILE_WRITE_THROUGH)!=0;
        if(!replaced || read_file(path)!=value) throw std::runtime_error("state_commit_unverified");
        lua.set_bool(true);
    }catch(...) {lua.set_bool(false);}
    return 1;
}
int is_game_thread(const RC::LuaMadeSimple::Lua& lua) {
    const auto thread=window_thread();lua.set_bool(thread!=0 && thread==GetCurrentThreadId());return 1;
}
int set_next(const RC::LuaMadeSimple::Lua& lua) {
    try {
        const auto [address,target,expected,desired]=consume_write_arguments(lua);
        if(uncertain_write) throw std::runtime_error("uncertain_write_latched");
        const auto before=validate(address);
        if(before.choices[target]!=expected) throw std::runtime_error("stale_expected_selection");
        if(expected==desired) {lua.set_string(status_json(before));return 1;}
        const auto offset=reviewed::targets[target].descriptor;
        const auto pointer=before.content+offset;
        MEMORY_BASIC_INFORMATION region{};
        if(!VirtualQuery(reinterpret_cast<void*>(pointer),&region,sizeof(region)) || region.State!=MEM_COMMIT ||
           !(region.Protect&(PAGE_READWRITE|PAGE_WRITECOPY)) || (region.Protect&(PAGE_GUARD|PAGE_NOACCESS)) ||
           pointer+8>reinterpret_cast<std::uintptr_t>(region.BaseAddress)+region.RegionSize)
            throw std::runtime_error("destination_not_writable_data");
        auto wanted=before.bytes;const auto value=encoded(offset,static_cast<int>(desired));
        std::memcpy(wanted.data()+offset,&value,8);
        // This changes this row's relative pointer, never the shared vector.
        // Keep the latch set unless exact full-image readback succeeds.
        uncertain_write=true;SIZE_T written{};
        if(!WriteProcessMemory(GetCurrentProcess(),reinterpret_cast<void*>(pointer),&value,8,&written) || written!=8)
            throw std::runtime_error("write_uncertain");
        const auto after=validate(address);
        if(after.content!=before.content || after.bytes!=wanted || after.choices[target]!=desired)
            throw std::runtime_error("write_readback_differs");
        uncertain_write=false;lua.set_string(status_json(after));
    } catch(const std::exception& error) {
        lua.set_string(std::string("{\"ok\":false,\"reason\":\"")+error.what()+"\",\"uncertain_write\":"+(uncertain_write?"true":"false")+"}");
    }
    return 1;
}
std::string hex(const unsigned char* data, std::size_t size) {
    std::ostringstream out;
    for (std::size_t i=0;i<size;++i) out << std::hex << std::setw(2) << std::setfill('0') << unsigned(data[i]);
    return out.str();
}
int inspect(const RC::LuaMadeSimple::Lua& lua) {
    // Read-only discovery. No arbitrary memory writes or engine calls.
    // The Lua caller supplies only the freshly resolved, exact regional asset.
    const auto address=static_cast<std::uintptr_t>(lua.get_integer());
    std::array<unsigned char,256> bytes{};
    if (!read(address,bytes.data(),bytes.size())) { lua.set_string("{\"ok\":false,\"reason\":\"unreadable_asset\"}"); return 1; }
    auto* object=reinterpret_cast<RC::Unreal::UObject*>(address);
    const auto name=object->GetFullName();
    if (name != L"EndDataObjectEnemyTerritory /Game/DataObject/Field/1200-GRASA/EnemyTerritory.EnemyTerritory") {
        lua.set_string("{\"ok\":false,\"reason\":\"unreviewed_asset_identity\"}"); return 1;
    }
    std::ostringstream out;
    out << "{\"ok\":true,\"read_only\":true,\"asset_address\":" << address
        << ",\"asset_hex\":\"" << hex(bytes.data(),bytes.size()) << "\",\"pointer_candidates\":[";
    bool first=true;
    for (std::size_t offset=0x28;offset+8<=bytes.size();offset+=8) {
        std::uintptr_t pointer{};std::memcpy(&pointer,bytes.data()+offset,8);
        if (pointer%8!=0) continue;
        std::array<unsigned char,1024> target{};
        if (!read(pointer,target.data(),target.size())) continue;
        if (!first) out << ',';first=false;
        out << "{\"asset_offset\":" << offset << ",\"address\":" << pointer
            << ",\"hex\":\"" << hex(target.data(),target.size()) << "\"}";
    }
    out << "]}";
    lua.set_string(out.str());return 1;
}
class Runtime : public RC::CppUserModBase {
    PersistentDispatch dispatch{window_thread};
public:
    Runtime() { ModName=STR("BiomeRandomizerRuntime");ModVersion=STR("0.0.3-persistent-prototype");ModAuthors=STR("Codex");ModDescription=STR("Guarded seeded existing-camp respawn selector"); }
    void on_unreal_init() override { dispatch.install(); }
    void on_update() override { dispatch.activate(); }
    void on_lua_stop(RC::StringViewType name,RC::LuaMadeSimple::Lua&,RC::LuaMadeSimple::Lua&,
                     RC::LuaMadeSimple::Lua&,std::vector<RC::LuaMadeSimple::Lua*>&) override {
        if(name==STR("BiomeRandomizerRuntime")) dispatch.detach();
    }
    void on_lua_start(RC::StringViewType name, RC::LuaMadeSimple::Lua& lua, RC::LuaMadeSimple::Lua& main,
                      RC::LuaMadeSimple::Lua& async, std::vector<RC::LuaMadeSimple::Lua*>& hooks) override {
        if (name!=STR("BiomeRandomizerRuntime")) return;
        const auto add=[](RC::LuaMadeSimple::Lua& state) {
            state.register_function("BiomeRandomizerInspectAsset",inspect);
            state.register_function("BiomeRandomizerTableStatus",table_status);
            state.register_function("BiomeRandomizerSetNext",set_next);
            state.register_function("BiomeRandomizerSHA256",hash_text);
            state.register_function("BiomeRandomizerRandomSeed",random_seed);
            state.register_function("BiomeRandomizerReadState",read_state);
            state.register_function("BiomeRandomizerWriteState",write_state);
            state.register_function("BiomeRandomizerIsGameThread",is_game_thread);
        };
        add(lua);add(main);add(async);for(auto* state:hooks) add(*state);
        dispatch.prepare(main);
    }
};
}
extern "C" __declspec(dllexport) RC::CppUserModBase* start_mod() { return new Runtime(); }
extern "C" __declspec(dllexport) void uninstall_mod(RC::CppUserModBase* mod) { delete mod; }
