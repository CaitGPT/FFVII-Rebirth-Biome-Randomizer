#pragma once
#include <LuaMadeSimple/LuaMadeSimple.hpp>
#include <Unreal/UObject.hpp>
#include <Unreal/NameTypes.hpp>
#include <Unreal/Common.hpp>
#include <DynamicOutput/Output.hpp>
#include <Windows.h>
#include <chrono>
#include <functional>
#include <memory>
#include <mutex>
#include <string>
#include <string_view>

// Exported by the tested c0a8d4c loader; absent from the older template header.
namespace RC::Unreal {
class UFunction;
namespace Hook {
using ProcessEventCallback=std::function<void(UObject*,UFunction*,void*)>;
RC_UE_API auto RegisterProcessEventPreCallback(ProcessEventCallback) -> void;
}
}

// No async Lua, transient coroutines, or cross-thread Lua hooks. The loader
// starts main.lua on its update thread, then hands its idle persistent state
// to synchronous, verified-window-thread callbacks. Modelled on the parent's
// proven persistent telemetry sampler, without its telemetry or game input.
class PersistentDispatch {
    using Clock=std::chrono::steady_clock;
    struct State {
        std::recursive_mutex mutex;
        RC::LuaMadeSimple::Lua* current{};
        RC::LuaMadeSimple::Lua* pending{};
        DWORD thread{};
        bool alive{true},dispatching{},fault{};
        unsigned long long calls{};
        double max_ms{};
        double total_ms{};
#ifdef BIOME_DIAG
        // Diagnostic builds only: gaps between ProcessEvent calls on the game
        // thread approximate frame stalls, with the selector on or off.
        Clock::time_point last_event{};
        unsigned long long gaps50{},gaps100{},gaps250{},over5{},over16{};
        double max_gap{};
#endif
        Clock::time_point next{},refresh{};
        RC::Unreal::FName begin;
        // The installed SDK spells FName as class; the historical headers
        // spell it struct, changing this getter's mangled return type.
        using NameGetter=const RC::Unreal::FName& (*)(const RC::Unreal::UObject*);
        NameGetter name{};
        DWORD (*window_thread)(){};
        void (*spawn_actor)(RC::Unreal::UObject*,const std::wstring&){};
    };
    std::shared_ptr<State> state=std::make_shared<State>();
    static void log(std::string message) noexcept {
        if(message.size()>1024) message.resize(1024);
        message="[BiomeRandomizerRuntime] "+message+"\n";
        printf_s("%s",message.c_str());
        try {
            const std::wstring wide(message.begin(),message.end());
            RC::Output::send(std::wstring_view(wide));
        } catch(...) {} // logging cannot reopen a failed callback
    }
    static std::string ascii(std::wstring_view value) {
        std::string out;out.reserve(value.size());
        for(auto c:value){if(c>127) return {};out.push_back(static_cast<char>(c));}
        return out;
    }
    static void dispatch(const std::shared_ptr<State>& shared,RC::Unreal::UObject* actor,
                         RC::Unreal::UFunction* function,void* parameters) {
#ifdef BIOME_DIAG
        if(shared->thread && GetCurrentThreadId()==shared->thread) {
            const auto at=Clock::now();
            if(shared->last_event!=Clock::time_point{}) {
                const auto gap=std::chrono::duration<double,std::milli>(at-shared->last_event).count();
                if(gap>shared->max_gap) shared->max_gap=gap;
                if(gap>50) ++shared->gaps50;
                if(gap>100) ++shared->gaps100;
                if(gap>250) ++shared->gaps250;
            }
            shared->last_event=at;
        }
#endif
        std::unique_lock guard(shared->mutex,std::try_to_lock);
        if(!guard || !shared->alive || shared->fault || shared->dispatching ||
           !shared->current || !shared->thread || GetCurrentThreadId()!=shared->thread) return;
        auto* lua=shared->current;
        const int top=lua->get_stack_size();
        shared->dispatching=true;
        try {
            const auto name=shared->name(reinterpret_cast<RC::Unreal::UObject*>(function));
            if(name==shared->begin && actor) {
                const auto full=actor->GetFullName();
                if(full.starts_with(L"EndFieldEnemyTerritoryServerBuildActor ")) {
                    if(shared->spawn_actor) shared->spawn_actor(actor,full);
                } else if(full.starts_with(L"EndFieldEnemyTerritoryActor ")) {
                    constexpr std::wstring_view marker=L"/Game/Level/Game/Field/";
                    const auto at=full.find(marker);
                    if(at!=std::wstring::npos) {
                        const auto start=at+marker.size();const auto end=full.find(L'/',start);
                        if(end!=std::wstring::npos) {
                            const auto region=ascii(std::wstring_view(full).substr(start,end-start));
                            lua->prepare_function_call("BiomeRandomizerTerritoryBegin");lua->set_string(region);lua->call_function(1,0);
                        }
                    }
                }
            }
            if(Clock::now()>=shared->next) {
                const auto started=Clock::now();
                lua->call_function("BiomeRandomizerTick",0,0);
                const auto elapsed=std::chrono::duration<double,std::milli>(Clock::now()-started).count();
                if(elapsed>shared->max_ms) shared->max_ms=elapsed;
                shared->total_ms+=elapsed;
                ++shared->calls;
#ifdef BIOME_DIAG
                if(elapsed>5) ++shared->over5;
                if(elapsed>16) ++shared->over16;
                if(shared->calls%100==0) {
                    log("diag ticks="+std::to_string(shared->calls)+" tick_avg_ms="+std::to_string(shared->total_ms/100)+
                        " tick_max_ms="+std::to_string(shared->max_ms)+" ticks_over5="+std::to_string(shared->over5)+
                        " ticks_over16="+std::to_string(shared->over16)+" gaps50="+std::to_string(shared->gaps50)+
                        " gaps100="+std::to_string(shared->gaps100)+" gaps250="+std::to_string(shared->gaps250)+
                        " max_gap_ms="+std::to_string(shared->max_gap));
                    shared->total_ms=0;shared->max_ms=0;shared->over5=shared->over16=shared->gaps50=shared->gaps100=shared->gaps250=0;shared->max_gap=0;
                }
#else
                // One line every five minutes, so a bug report shows the cost.
                if(shared->calls==1 || shared->calls%3000==0) {
                    const auto window=shared->calls==1?1ull:3000ull;
                    log("persistent calls="+std::to_string(shared->calls)+" avg_ms="+std::to_string(shared->total_ms/window)+
                        " max_ms="+std::to_string(shared->max_ms));
                    shared->total_ms=0;shared->max_ms=0;
                }
#endif
                shared->next=Clock::now()+std::chrono::milliseconds(100);
            }
        } catch(const std::exception& error) {
            shared->fault=true;
            log(std::string("persistent callback stopped: ")+error.what());
        }
        while(lua->get_stack_size()>top) lua->discard_value(-1);
        if(lua->get_stack_size()<top){shared->fault=true;log("persistent stack imbalance; stopped");}
        shared->dispatching=false;
    }
public:
    explicit PersistentDispatch(DWORD (*thread)(),void (*spawn_actor)(RC::Unreal::UObject*,const std::wstring&)){state->window_thread=thread;state->spawn_actor=spawn_actor;}
    void install() {
        state->name=reinterpret_cast<State::NameGetter>(GetProcAddress(GetModuleHandleW(L"UE4SS.dll"),
            "?GetNamePrivate@UObjectBase@Unreal@RC@@QEBAAEBVFName@23@XZ"));
        if(!state->name){state->fault=true;log("pinned name getter unavailable; stopped");return;}
        state->begin=RC::Unreal::FName(L"ReceiveBeginPlay",RC::Unreal::FNAME_Find);
        auto shared=state;
        RC::Unreal::Hook::RegisterProcessEventPreCallback([shared](auto* a,auto* f,void* p){dispatch(shared,a,f,p);});
    }
    void prepare(RC::LuaMadeSimple::Lua& main){std::lock_guard guard(state->mutex);state->pending=&main;}
    void activate() {
        std::lock_guard guard(state->mutex);
        if(Clock::now()>=state->refresh){state->thread=state->window_thread();state->refresh=Clock::now()+std::chrono::seconds(1);}
        if(!state->pending) return;
        auto* main=state->pending;state->pending=nullptr;
        if(!main->is_global_function("BiomeRandomizerTick") || !main->is_global_function("BiomeRandomizerTerritoryBegin")){state->fault=true;log("paired persistent entry points missing; stopped");return;}
        state->current=main;state->next={};
        log("persistent main state attached, period=100ms");
    }
    void detach(){std::lock_guard guard(state->mutex);state->current=nullptr;state->pending=nullptr;}
    ~PersistentDispatch(){std::lock_guard guard(state->mutex);state->alive=false;state->current=nullptr;state->pending=nullptr;}
};
