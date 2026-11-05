#pragma once
#include <Unreal/UObject.hpp>
#include <Unreal/FMemory.hpp>
#include <array>
#include <cstdint>
#include <cstring>
#include <string>

// Each territory's level actor keeps separate spawn lists by enemy size. A camp usually has only
// the sizes it normally uses, and asking it for a size it lacks crashes the game. Filling an empty
// list from the nearest size the camp does have lets any size stand there. Runs on BeginPlay, before
// anything can spawn, and only changes lists that are empty.
namespace spawn {
struct RawArray {unsigned char* data;std::int32_t num;std::int32_t max;};
constexpr std::size_t transform_bytes=48;
constexpr std::array<const wchar_t*,6> sizes{L"S",L"M",L"L",L"2L",L"3L",L"4L"};

inline RawArray* field(RC::Unreal::UObject* actor,const std::wstring& name) {
    return static_cast<RawArray*>(actor->GetValuePtrByPropertyName(name.c_str()));
}
inline bool sane(const RawArray& a) {
    return a.num>=0 && a.num<=4096 && a.max>=a.num && (a.num==0 || a.data!=nullptr);
}
inline void copy(RawArray& to,const RawArray& from,std::size_t element,std::uint32_t alignment) {
    if(from.num<=0) return;
    const auto bytes=static_cast<std::size_t>(from.num)*element;
    auto* block=static_cast<unsigned char*>(RC::Unreal::FMemory::Malloc(bytes,alignment));
    std::memcpy(block,from.data,bytes);
    if(to.data) RC::Unreal::FMemory::Free(to.data);
    to.data=block;to.num=from.num;to.max=from.num;
}
// Index of the nearest non-empty list, preferring the smaller one on a tie, or -1.
template<class Count> int nearest(int wanted,Count count) {
    for(int distance=1;distance<static_cast<int>(sizes.size());++distance)
        for(const int index:{wanted-distance,wanted+distance})
            if(index>=0 && index<static_cast<int>(sizes.size()) && count(index)>0) return index;
    return -1;
}
// Returns the number of lists filled, or -1 if the actor doesn't look as reviewed (nothing is changed).
inline int fill(RC::Unreal::UObject* actor) {
    std::array<RawArray*,6> ground{},fly{},check{},ray{};
    for(std::size_t i=0;i<sizes.size();++i) {
        const std::wstring size(sizes[i]);
        ground[i]=field(actor,L"TerritoryGroundSpawnPoints_"+size);
        fly[i]=field(actor,L"TerritoryFlySpawnPoints_"+size);
        check[i]=field(actor,L"TerritoryFlySpawnPointsCheckGround_"+size);
        ray[i]=field(actor,L"TerritoryFlySpawnPointsRaycast_"+size);
        if(!ground[i] || !fly[i] || !check[i] || !ray[i]) return -1;
        if(!sane(*ground[i]) || !sane(*fly[i]) || !sane(*check[i]) || !sane(*ray[i])) return -1;
    }
    int filled=0;
    std::array<int,6> ground_counts{},fly_counts{};
    for(std::size_t i=0;i<sizes.size();++i) {ground_counts[i]=ground[i]->num;fly_counts[i]=fly[i]->num;}
    for(int i=0;i<static_cast<int>(sizes.size());++i) {
        if(ground_counts[i]==0) {
            const int source=nearest(i,[&](int k){return ground_counts[k];});
            if(source>=0) {copy(*ground[i],*ground[source],transform_bytes,16);++filled;}
        }
        if(fly_counts[i]==0) {
            const int source=nearest(i,[&](int k){return fly_counts[k];});
            if(source>=0) {
                copy(*fly[i],*fly[source],transform_bytes,16);
                copy(*check[i],*check[source],1,1);
                copy(*ray[i],*ray[source],transform_bytes,16);
                ++filled;
            }
        }
    }
    return filled;
}
}
