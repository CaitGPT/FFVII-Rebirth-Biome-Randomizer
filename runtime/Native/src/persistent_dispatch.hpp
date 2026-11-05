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
        Clock::time_point next{},refresh{};
        RC::Unreal::FName begin,end;
        // The installed SDK spells FName as class; the historical headers
        // spell it struct, changing this getter's mangled return type.
        using NameGetter=const RC::Unreal::FName& (*)(const RC::Unreal::UObject*);
        NameGetter name{};
        DWORD (*window_thread)(){};
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
                if(full.find(L" /Game/Level/Game/Field/1200-GRASA/")!=std::wstring::npos &&
                   full.starts_with(L"EndFieldEnemyTerritoryActor "))
                    lua->call_function("BiomeRandomizerTerritoryBegin",0,0);
            } else if(name==shared->end && actor && parameters) {
                const auto full=actor->GetFullName();
                if(full.starts_with(L"EN") && full.find(L" /Game/Level/Game/EndGame.EndGame:")!=std::wstring::npos) {
                    unsigned char reason{};SIZE_T copied{};
                    if(ReadProcessMemory(GetCurrentProcess(),parameters,&reason,1,&copied) && copied==1 && reason==0) {
                        const auto id=ascii(full);
                        if(!id.empty()){lua->prepare_function_call("BiomeRandomizerActorEnd");lua->set_string(id);lua->set_integer(reason);lua->call_function(2,0);}
                    }
                }
            }
            if(Clock::now()>=shared->next) {
                const auto started=Clock::now();
                lua->call_function("BiomeRandomizerTick",0,0);
                const auto elapsed=std::chrono::duration<double,std::milli>(Clock::now()-started).count();
                if(elapsed>shared->max_ms) shared->max_ms=elapsed;
                ++shared->calls;
                if(shared->calls==1 || shared->calls%6000==0)
                    log("persistent calls="+std::to_string(shared->calls)+" thread="+std::to_string(GetCurrentThreadId())+
                        " max_ms="+std::to_string(shared->max_ms));
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
    explicit PersistentDispatch(DWORD (*thread)()){state->window_thread=thread;}
    void install() {
        state->name=reinterpret_cast<State::NameGetter>(GetProcAddress(GetModuleHandleW(L"UE4SS.dll"),
            "?GetNamePrivate@UObjectBase@Unreal@RC@@QEBAAEBVFName@23@XZ"));
        if(!state->name){state->fault=true;log("pinned name getter unavailable; stopped");return;}
        state->begin=RC::Unreal::FName(L"ReceiveBeginPlay",RC::Unreal::FNAME_Find);
        state->end=RC::Unreal::FName(L"ReceiveEndPlay",RC::Unreal::FNAME_Find);
        auto shared=state;
        RC::Unreal::Hook::RegisterProcessEventPreCallback([shared](auto* a,auto* f,void* p){dispatch(shared,a,f,p);});
    }
    void prepare(RC::LuaMadeSimple::Lua& main){std::lock_guard guard(state->mutex);state->pending=&main;}
    void activate() {
        std::lock_guard guard(state->mutex);
        if(Clock::now()>=state->refresh){state->thread=state->window_thread();state->refresh=Clock::now()+std::chrono::seconds(1);}
        if(!state->pending) return;
        auto* main=state->pending;state->pending=nullptr;
        if(!main->is_global_function("BiomeRandomizerTick") || !main->is_global_function("BiomeRandomizerTerritoryBegin") ||
           !main->is_global_function("BiomeRandomizerActorEnd")){state->fault=true;log("paired persistent entry points missing; stopped");return;}
        state->current=main;state->next={};
        log("persistent main state attached, period=100ms");
    }
    void detach(){std::lock_guard guard(state->mutex);state->current=nullptr;state->pending=nullptr;}
    ~PersistentDispatch(){std::lock_guard guard(state->mutex);state->alive=false;state->current=nullptr;state->pending=nullptr;}
};
