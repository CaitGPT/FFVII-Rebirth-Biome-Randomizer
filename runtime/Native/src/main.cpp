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
#include <iterator>
#include <atomic>
#include <mutex>
#include <thread>
#include "reviewed_layout.hpp"
#include "write_arguments.hpp"
#include "persistent_dispatch.hpp"
#include "spawn_points.hpp"
#include <Unreal/UObjectGlobals.hpp>
#include <unordered_map>
#include <memory>
#include <utility>
#include <unordered_set>

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
    std::vector<std::string> choices; // per target: "o" for the game's own, or "t:enemies/c:counts"
};
// Lists the runtime owns: a camp's enemies (FNames, 8 bytes each) and exact counts (one byte each). Made on first
// use and never freed, so a row can point at one for as long as the game runs. Keyed by contents.
std::unordered_map<std::string,std::unique_ptr<unsigned char[]>> owned_lists;
std::unordered_map<std::uintptr_t,std::string> owned_keys;
std::uint64_t relative_to(std::uintptr_t from,std::uintptr_t to) {
    const auto relative=static_cast<std::int64_t>(to)-static_cast<std::int64_t>(from);
    return static_cast<std::uint64_t>(relative*2)|1;
}
std::uintptr_t target_of(std::uintptr_t from,std::uint64_t value) {
    if(!(value&1)) return 0;
    return from+static_cast<std::uintptr_t>(static_cast<std::int64_t>(value)>>1);
}
std::vector<int> numbers(const std::string& text) {
    std::vector<int> out;std::size_t at=0;
    while(at<text.size()) {
        const auto dot=text.find('.',at);const auto part=text.substr(at,dot==std::string::npos?std::string::npos:dot-at);
        if(part.empty() || part.size()>3 || part.find_first_not_of("0123456789")!=std::string::npos) throw std::runtime_error("invalid_composition");
        out.push_back(std::stoi(part));
        if(dot==std::string::npos) break;
        at=dot+1;
    }
    return out;
}
std::string joined(const std::vector<int>& values) {
    std::string out;for(std::size_t i=0;i<values.size();++i) {if(i) out+='.';out+=std::to_string(values[i]);}
    return out;
}
struct Composition {std::vector<int> enemies,counts;};
Composition parse(const std::string& key,std::uint32_t slots) {
    if(key.rfind("t:",0)!=0) throw std::runtime_error("invalid_composition");
    const auto split=key.find("/c:");
    if(split==std::string::npos) throw std::runtime_error("invalid_composition");
    Composition out{numbers(key.substr(2,split-2)),numbers(key.substr(split+3))};
    if(out.enemies.size()!=slots || out.counts.size()!=slots) throw std::runtime_error("invalid_composition");
    return out;
}
const unsigned char* owned(const std::string& key,const std::vector<unsigned char>& bytes) {
    auto found=owned_lists.find(key);
    if(found!=owned_lists.end()) return found->second.get();
    auto block=std::make_unique<unsigned char[]>(bytes.size());
    std::memcpy(block.get(),bytes.data(),bytes.size());
    const auto* raw=block.get();
    owned_keys[reinterpret_cast<std::uintptr_t>(raw)]=key;
    owned_lists[key]=std::move(block);
    return raw;
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
Table validate(std::uintptr_t address,std::size_t table_index) {
    if(table_index>=reviewed::table_count) throw std::runtime_error("unknown_table");
    const auto& reviewed_table=reviewed::tables[table_index];
    // ExecuteInGameThread in this UE4SS version drains on ProcessEvent, which
    // may also occur on a loading thread. Never bind to its first invocation.
    // Require this Windows game's own visible UnrealWindow owner thread.
    const auto thread=window_thread();
    if(thread==0) throw std::runtime_error("game_window_thread_unavailable");
    if(thread!=GetCurrentThreadId()) throw std::runtime_error("wrong_thread");
    std::array<unsigned char,0x40> header{};
    if(!read(address,header.data(),header.size())) throw std::runtime_error("unreadable_asset");
    auto* object=reinterpret_cast<RC::Unreal::UObject*>(address);
    if(object->GetFullName()!=std::wstring(L"EndDataObjectEnemyTerritory ")+reviewed_table.asset)
        throw std::runtime_error("unreviewed_asset_identity");
    Table table;
    // Observed live in the pinned c0a8d4c/game build, then checked by the entire
    // frozen image's structural fingerprint and every serialized name below.
    std::memcpy(&table.content,header.data()+0x38,8);
    table.bytes.resize(reviewed_table.image_bytes);
    table.choices.resize(reviewed_table.target_count);
    if(!read(table.content,table.bytes.data(),table.bytes.size())) throw std::runtime_error("unreadable_image");
    auto normalized=table.bytes;
    const std::string table_tag="T"+std::to_string(table_index)+":";
    for(std::size_t i=0;i<reviewed_table.target_count;++i) {
        const auto& target=reviewed_table.targets[i];
        std::uint64_t enemies{},low{},high{};
        std::memcpy(&enemies,table.bytes.data()+target.descriptor,8);
        std::memcpy(&low,table.bytes.data()+target.min_descriptor,8);
        std::memcpy(&high,table.bytes.data()+target.max_descriptor,8);
        const auto original_enemies=relative_to(table.content+target.descriptor,table.content+target.template_original);
        const auto original_low=relative_to(table.content+target.min_descriptor,table.content+target.min_original);
        const auto original_high=relative_to(table.content+target.max_descriptor,table.content+target.max_original);
        if(enemies==original_enemies && low==original_low && high==original_high) table.choices[i]="o";
        else {
            // Only lists this runtime made may stand in a row; anything else is another writer.
            const auto e=owned_keys.find(target_of(table.content+target.descriptor,enemies));
            const auto lo=target_of(table.content+target.min_descriptor,low),hi=target_of(table.content+target.max_descriptor,high);
            const auto c=owned_keys.find(lo);
            if(e==owned_keys.end() || c==owned_keys.end() || lo!=hi || e->second.rfind(table_tag,0)!=0 || c->second.rfind("C:",0)!=0)
                throw std::runtime_error("unreviewed_composition_pointer");
            table.choices[i]="t:"+e->second.substr(table_tag.size())+"/c:"+c->second.substr(2);
        }
        std::memcpy(normalized.data()+target.descriptor,&original_enemies,8);
        std::memcpy(normalized.data()+target.min_descriptor,&original_low,8);
        std::memcpy(normalized.data()+target.max_descriptor,&original_high,8);
    }
    for(std::size_t n=0;n<reviewed_table.name_count;++n) {
        const auto& patch=reviewed_table.names[n];
        // Find only: no global name is created. Compare exact native token
        // components, avoiding unsafe ToString calls on untrusted indices.
        const RC::Unreal::FName expected(patch.name,RC::Unreal::FNAME_Find);
        std::uint32_t index{},number{};
        std::memcpy(&index,table.bytes.data()+patch.offset,4);
        std::memcpy(&number,table.bytes.data()+patch.offset+4,4);
        if(index!=expected.GetComparisonIndex() || number!=expected.GetNumber()) throw std::runtime_error("name_manifest_differs");
        std::memset(normalized.data()+patch.offset,0,8);
    }
    if(digest(normalized)!=reviewed_table.masked_sha256) throw std::runtime_error("structure_fingerprint_differs");
    return table;
}
std::string status_json(const Table& table) {
    std::ostringstream out;out << "{\"ok\":true,\"image_bytes\":" << table.bytes.size() << ",\"asset_content\":" << table.content << ",\"choices\":[";
    for(std::size_t i=0;i<table.choices.size();++i) {if(i)out<<',';out<<'"'<<table.choices[i]<<'"';}
    out << "],\"all_names_and_structural_fingerprint_verified\":true,\"uncertain_write\":" << (uncertain_write?"true":"false") << '}';
    return out.str();
}
int table_status(const RC::LuaMadeSimple::Lua& lua) {
    try {
        const auto address=static_cast<std::uintptr_t>(lua.get_integer(1));
        const auto table=static_cast<std::size_t>(lua.get_integer(1));
        lua.set_string(status_json(validate(address,table)));
    }
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
    if(size==0 || size>65536) throw std::runtime_error("state_file_size_invalid");
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
void write_state_file(const std::string& value) {
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
}
std::string state_argument(const RC::LuaMadeSimple::Lua& lua) {
    if(!lua.is_string(1)) throw std::runtime_error("state_payload_type");
    std::string value(lua.get_string(1));
    if(value.empty() || value.size()>65536) throw std::runtime_error("state_payload_size");
    return value;
}
int write_state(const RC::LuaMadeSimple::Lua& lua) {
    try {
        write_state_file(state_argument(lua));
        lua.set_bool(true);
    }catch(...) {lua.set_bool(false);}
    return 1;
}
// Flushing, the backup copy and the atomic replace took 700 ms on the game thread
// in a real fight, which is a visible freeze in recorded footage.
std::mutex state_writer;
std::atomic<bool> state_write_failed{false};
int write_state_async(const RC::LuaMadeSimple::Lua& lua) {
    try {
        std::thread([value=state_argument(lua)]{
            std::lock_guard guard(state_writer);
            try {write_state_file(value);} catch(...) {state_write_failed=true;}
        }).detach();
        lua.set_bool(true);
    }catch(...) {lua.set_bool(false);}
    return 1;
}
int state_write_failed_status(const RC::LuaMadeSimple::Lua& lua) {
    lua.set_bool(state_write_failed.load());
    return 1;
}
int is_game_thread(const RC::LuaMadeSimple::Lua& lua) {
    const auto thread=window_thread();lua.set_bool(thread!=0 && thread==GetCurrentThreadId());return 1;
}
int set_next(const RC::LuaMadeSimple::Lua& lua) {
    try {
        const auto arguments=consume_write_arguments(lua);
        const auto address=arguments.address;const auto table_index=static_cast<std::size_t>(arguments.table);
        const auto target=static_cast<std::size_t>(arguments.target);
        if(uncertain_write) throw std::runtime_error("uncertain_write_latched");
        const auto before=validate(address,table_index);
        const auto& reviewed_table=reviewed::tables[table_index];
        if(target>=reviewed_table.target_count) throw std::runtime_error("invalid_selection");
        const auto& reviewed_target=reviewed_table.targets[target];
        if(before.choices[target]!=arguments.expected) throw std::runtime_error("stale_expected_selection");
        if(arguments.expected==arguments.desired) {lua.set_string(status_json(before));return 1;}
        const auto content=before.content;
        std::uintptr_t enemies_at=content+reviewed_target.template_original;
        std::uintptr_t low_at=content+reviewed_target.min_original,high_at=content+reviewed_target.max_original;
        if(arguments.desired!="o") {
            const auto wanted=parse(arguments.desired,reviewed_target.slots);
            std::vector<unsigned char> names(8*reviewed_target.slots),counts(reviewed_target.slots);
            for(std::uint32_t s=0;s<reviewed_target.slots;++s) {
                const auto enemy=wanted.enemies[s];const auto count=wanted.counts[s];
                if(enemy<0 || static_cast<std::size_t>(enemy)>=reviewed_table.catalog_count || enemy>=64 ||
                   !(reviewed_target.allowed[s]&(1ull<<enemy))) throw std::runtime_error("enemy_not_allowed_here");
                if(count<1 || count>12) throw std::runtime_error("count_out_of_range");
                // The table's own copy of this enemy's name, exactly as the game resolved it.
                std::memcpy(names.data()+8*s,before.bytes.data()+reviewed_table.catalog[enemy],8);
                counts[s]=static_cast<unsigned char>(count);
            }
            enemies_at=reinterpret_cast<std::uintptr_t>(owned("T"+std::to_string(table_index)+":"+joined(wanted.enemies),names));
            low_at=high_at=reinterpret_cast<std::uintptr_t>(owned("C:"+joined(wanted.counts),counts));
        }
        const std::array<std::pair<std::uint32_t,std::uint64_t>,3> writes{{
            {reviewed_target.descriptor,relative_to(content+reviewed_target.descriptor,enemies_at)},
            {reviewed_target.min_descriptor,relative_to(content+reviewed_target.min_descriptor,low_at)},
            {reviewed_target.max_descriptor,relative_to(content+reviewed_target.max_descriptor,high_at)}}};
        auto wanted_bytes=before.bytes;
        for(const auto& [offset,value]:writes) {
            const auto pointer=content+offset;
            MEMORY_BASIC_INFORMATION region{};
            if(!VirtualQuery(reinterpret_cast<void*>(pointer),&region,sizeof(region)) || region.State!=MEM_COMMIT ||
               !(region.Protect&(PAGE_READWRITE|PAGE_WRITECOPY)) || (region.Protect&(PAGE_GUARD|PAGE_NOACCESS)) ||
               pointer+8>reinterpret_cast<std::uintptr_t>(region.BaseAddress)+region.RegionSize)
                throw std::runtime_error("destination_not_writable_data");
            std::memcpy(wanted_bytes.data()+offset,&value,8);
        }
        // These change this row's own pointers, never a shared list. Keep the latch set
        // unless exact full-image readback succeeds.
        uncertain_write=true;
        for(const auto& [offset,value]:writes) {
            SIZE_T written{};
            if(!WriteProcessMemory(GetCurrentProcess(),reinterpret_cast<void*>(content+offset),&value,8,&written) || written!=8)
                throw std::runtime_error("write_uncertain");
        }
        const auto after=validate(address,table_index);
        if(after.content!=before.content || after.bytes!=wanted_bytes || after.choices[target]!=arguments.desired)
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
// Spawn lists. Each region keeps its territory spawn actors in their own streamed level, and these
// actors don't report BeginPlay. Finding objects by class or path costs 35-90 ms here, so instead the
// world's short level list is compared each poll. When a spawn level arrives, its own actor list is
// walked once and every allowlisted actor filled. When it leaves, its camps are reported gone so Lua
// can put their tables back before the next level arrives.
struct RawPointers {RC::Unreal::UObject** data;std::int32_t num;std::int32_t max;};
std::unordered_set<std::wstring> spawn_camps;
std::unordered_map<std::wstring,RC::Unreal::UObject*> spawn_ready;
std::unordered_map<RC::Unreal::UObject*,std::vector<std::wstring>> spawn_levels; // spawn level -> its camps
std::vector<RC::Unreal::UObject*> known_levels;
unsigned long long spawn_seen{},spawn_filled{},spawn_refused{},spawn_polls{},spawn_level_changes{};
std::wstring camp_of(const std::wstring& full) {
    const auto at=full.rfind(L'.');
    return at==std::wstring::npos?std::wstring{}:full.substr(at+1);
}
bool sane(const RawPointers* a,int limit) {return a && a->num>=0 && a->num<=limit && a->max>=a->num && (a->num==0 || a->data);}
RawPointers* level_actors(RC::Unreal::UObject* level) {
    // ULevel keeps Actors, then ActorsForGC, directly before its reflected OwningWorld.
    auto* owning=static_cast<unsigned char*>(level->GetValuePtrByPropertyName(STR("OwningWorld")));
    if(!owning) return nullptr;
    auto* actors=reinterpret_cast<RawPointers*>(owning-0x20);
    return sane(actors,200000)?actors:nullptr;
}
std::vector<std::wstring> prepare_spawn_level(RC::Unreal::UObject* level,long long& fresh) {
    std::vector<std::wstring> camps;
    auto* actors=level_actors(level);
    if(!actors) {++spawn_refused;return camps;}
    for(std::int32_t i=0;i<actors->num;++i) {
        auto* actor=actors->data[i];
        if(!actor) continue;
        const auto full=actor->GetFullName();
        if(!full.starts_with(L"EndFieldEnemyTerritoryServerBuildActor ")) continue;
        ++spawn_seen;
        const auto camp=camp_of(full);
        if(!spawn_camps.contains(camp)) continue;
        const int filled=spawn::fill(actor);
        if(filled<0) {++spawn_refused;continue;}
        spawn_filled+=static_cast<unsigned long long>(filled);
        spawn_ready[camp]=actor;camps.push_back(camp);++fresh;
    }
    return camps;
}
int spawn_poll(const RC::LuaMadeSimple::Lua& lua) {
    if(spawn_camps.empty())
        for(const auto& table:reviewed::tables)
            for(std::size_t i=0;i<table.target_count;++i) spawn_camps.insert(table.targets[i].id);
    long long fresh=0,gone=0;
    std::string gone_camps;
    try {
        ++spawn_polls;
        auto* world=reinterpret_cast<RC::Unreal::UObject*>(static_cast<std::uintptr_t>(lua.get_integer(1)));
        if(!world) throw std::runtime_error("no_world");
        auto* levels=static_cast<RawPointers*>(world->GetValuePtrByPropertyName(STR("Levels")));
        if(!sane(levels,4096)) throw std::runtime_error("levels_unreadable");
        const std::vector<RC::Unreal::UObject*> now(levels->data,levels->data+levels->num);
        if(now!=known_levels) {
            ++spawn_level_changes;
            const std::unordered_set<RC::Unreal::UObject*> present(now.begin(),now.end());
            for(auto it=spawn_levels.begin();it!=spawn_levels.end();) {
                if(present.contains(it->first)) {++it;continue;}
                for(const auto& camp:it->second) {
                    spawn_ready.erase(camp);++gone;
                    if(gone_camps.size()<8000) {gone_camps+=gone_camps.empty()?"":",";gone_camps+=std::string(camp.begin(),camp.end());}
                }
                it=spawn_levels.erase(it);
            }
            const std::unordered_set<RC::Unreal::UObject*> before(known_levels.begin(),known_levels.end());
            for(auto* level:now) {
                if(!level || before.contains(level)) continue;
                if(level->GetFullName().find(L"_World_Navigation_Mod_ServerBuild:PersistentLevel")==std::wstring::npos) continue;
                spawn_levels[level]=prepare_spawn_level(level,fresh);
            }
            known_levels=now;
        }
    } catch(...) {++spawn_refused;}
    lua.set_string("{\"fresh\":"+std::to_string(fresh)+",\"gone\":"+std::to_string(gone)+",\"gone_camps\":\""+gone_camps+"\"}");
    return 1;
}
int spawn_is_ready(const RC::LuaMadeSimple::Lua& lua) {
    if(!lua.is_string(1)) {lua.set_bool(false);return 1;}
    const std::string camp(lua.get_string(1));
    lua.set_bool(spawn_ready.contains(std::wstring(camp.begin(),camp.end())));
    return 1;
}
int spawn_stats(const RC::LuaMadeSimple::Lua& lua) {
    lua.set_string("{\"seen\":"+std::to_string(spawn_seen)+",\"filled\":"+std::to_string(spawn_filled)+",\"refused\":"+std::to_string(spawn_refused)+",\"ready\":"+std::to_string(spawn_ready.size())+",\"polls\":"+std::to_string(spawn_polls)+",\"level_changes\":"+std::to_string(spawn_level_changes)+"}");
    return 1;
}
class Runtime : public RC::CppUserModBase {
    PersistentDispatch dispatch{window_thread};
public:
    Runtime() { ModName=STR("BiomeRandomizerRuntime");ModVersion=STR("1.0.0");ModAuthors=STR("Cait GPT (built by AI)");ModDescription=STR("Guarded seeded existing-camp respawn selector"); }
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
            state.register_function("BiomeRandomizerSpawnReady",spawn_is_ready);
            state.register_function("BiomeRandomizerSpawnPoll",spawn_poll);
            state.register_function("BiomeRandomizerSpawnStats",spawn_stats);
            state.register_function("BiomeRandomizerTableStatus",table_status);
            state.register_function("BiomeRandomizerSetNext",set_next);
            state.register_function("BiomeRandomizerSHA256",hash_text);
            state.register_function("BiomeRandomizerRandomSeed",random_seed);
            state.register_function("BiomeRandomizerReadState",read_state);
            state.register_function("BiomeRandomizerWriteState",write_state);
            state.register_function("BiomeRandomizerWriteStateAsync",write_state_async);
            state.register_function("BiomeRandomizerStateWriteFailed",state_write_failed_status);
            state.register_function("BiomeRandomizerIsGameThread",is_game_thread);
        };
        add(lua);add(main);add(async);for(auto* state:hooks) add(*state);
        dispatch.prepare(main);
    }
};
}
#ifndef BIOME_TESTED_LOADER_SHA256
#define BIOME_TESTED_LOADER_SHA256 "3f5e8d934fe91ff26be2ce3585cef0940d3c73b40295adc09fa6e7b62bc0018f"
#endif
namespace {
// This DLL is compiled against one exact UE4SS C++ ABI. A different build can
// still satisfy the imports while laying out classes differently, so compare
// the running loader before touching anything from its interface. Win32 only:
// UE4SS copes with a null mod, and main.lua reports the missing functions.
bool tested_loader() noexcept {
    try {
        const HMODULE module=GetModuleHandleW(L"UE4SS.dll");
        if(!module) return false;
        wchar_t path[MAX_PATH*2]{};
        const auto length=GetModuleFileNameW(module,path,MAX_PATH*2);
        if(!length || length>=MAX_PATH*2) return false;
        std::ifstream file(std::filesystem::path(path),std::ios::binary);
        if(!file) return false;
        const std::vector<unsigned char> bytes((std::istreambuf_iterator<char>(file)),std::istreambuf_iterator<char>());
        return !bytes.empty() && digest(bytes)==BIOME_TESTED_LOADER_SHA256;
    } catch(...) {return false;}
}
}
extern "C" __declspec(dllexport) RC::CppUserModBase* start_mod() {
    if(!tested_loader()) return nullptr;
    return new Runtime();
}
extern "C" __declspec(dllexport) void uninstall_mod(RC::CppUserModBase* mod) { delete mod; }
